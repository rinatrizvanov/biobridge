"""A scoring job, from user input to CSV.

Steps: prepare the input (pasted variant or uploaded VCF) -> parse it with pysam in
the engine environment (`inspect`) -> check the genome build -> enforce the allele
limit -> fetch the needed GRCh38 chromosomes -> score with the runner under the
watchdog -> build rows -> write results.csv and provenance.json.

Every job lives in its own folder under <home>/jobs.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from biobridge import paths
from biobridge.genome import HG38_MD5, normalize_contig
from biobridge.inputs.build import assess_header, build_basis
from biobridge.inputs.text import InputError, parse_variant, to_vcf
from biobridge.inputs.upload import prepare_upload
from biobridge.jobs.engine import INACTIVITY_TIMEOUT, run_engine
from biobridge.provenance import build_info
from biobridge.reports.csv_report import write_csv
from biobridge.results import Row, rows_from_results, summarize
from biobridge.setup.envs import lock_digest, sanitized_env
from biobridge.setup.processes import Cancelled, ChildProcesses
from biobridge.setup.reference import UCSC_HG38, ensure_chromosome

MAX_ALLELES = 50
ADAPTER = "spliceai-runner/1"
DISTANCE = 50


@dataclass
class JobRequest:
    paste: str | None = None
    vcf_bytes: bytes | None = None
    vcf_name: str | None = None
    confirm_grch38: bool = False


@dataclass
class Progress:
    stage: str             # "input", "reference", "loading_model", "scoring", "report" or "done"
    message: str
    done: int | None = None
    total: int | None = None


@dataclass
class JobResult:
    job_dir: Path
    rows: list[Row]
    summary: dict
    csv_path: Path
    provenance: dict
    timings: dict = field(default_factory=dict)


def new_job_dir(base: Path) -> Path:
    job = base / "jobs" / f"{time.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(2)}"
    job.mkdir(parents=True)
    return job


def run_job(
    request: JobRequest,
    base: Path,
    engine_env: Path,
    procs: ChildProcesses,
    on_status: Callable[[Progress], None] = lambda progress: None,
    license_acknowledgment: str = "not recorded",
    inactivity_timeout: float = INACTIVITY_TIMEOUT,
    cancel: threading.Event | None = None,
    runner: Path = paths.RUNNER,
    python: Path | None = None,
    reference_provider: Callable = ensure_chromosome,
) -> JobResult:
    """Run one job. `runner`, `python` and `reference_provider` exist so tests can substitute a
    marked fake engine; the app always uses the defaults."""
    t0 = time.perf_counter()
    timings: dict[str, float] = {}
    started = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    job = new_job_dir(base)
    vcf = job / "input.vcf"
    python = python or engine_env / "bin" / "python"
    env, log = sanitized_env(base), job / "engine.log"
    cancel = cancel or threading.Event()

    def check():
        if cancel.is_set() or procs.closing:
            raise Cancelled("cancelled")

    def engine(args, on_event=lambda e: None):
        check()
        return run_engine(python, runner, args, procs, log, env, on_event, inactivity_timeout)

    # 1. Input
    on_status(Progress("input", "Checking the input…"))
    if (request.paste is None) == (request.vcf_bytes is None):
        raise InputError("Provide either one pasted variant or one VCF file.")
    if request.paste is not None:
        vcf.write_text(to_vcf(parse_variant(request.paste)))
        input_name, input_sha = "pasted variant", hashlib.sha256(request.paste.strip().encode()).hexdigest()
    else:
        info = prepare_upload(request.vcf_bytes, vcf)
        input_name, input_sha = request.vcf_name or "uploaded.vcf", info.sha256

    engine(["inspect", "--vcf", vcf, "--out", job / "inspect.json"])
    inspected = json.loads((job / "inspect.json").read_text())
    if inspected["error"]:
        raise InputError(f"The VCF could not be read: {inspected['error']}.")
    records = inspected["records"]
    if not records:
        raise InputError("The file contains no variants.")
    evidence = None if request.paste is not None else assess_header(inspected["contigs"], inspected["meta"])
    basis = build_basis(evidence, request.confirm_grch38)
    alleles = sum(max(1, len(r["alts"])) for r in records)
    if alleles > MAX_ALLELES:
        raise InputError(f"The file has {alleles} alleles; BioBridge v0.1 scores up to {MAX_ALLELES} at a time.")
    timings["input_s"] = time.perf_counter() - t0

    # 2. Reference chromosomes, fetched only when needed
    t = time.perf_counter()
    needed = sorted({c for r in records if (c := normalize_contig(r["chrom"]))},
                    key=lambda c: (len(c), c))
    reference = {}
    for chrom in needed:
        check()
        on_status(Progress("reference", f"Preparing GRCh38 {chrom}…"))

        def downloading(done, total, chrom=chrom):
            check()  # Raising here aborts the download; the partial file is kept for a later resume.
            on_status(Progress("reference", f"Downloading GRCh38 {chrom}…", done, total))

        reference[chrom] = reference_provider(chrom, base, progress=downloading)
    timings["reference_s"] = time.perf_counter() - t

    # 3. Scoring under the watchdog
    t = time.perf_counter()
    request_path = job / "request.json"
    request_path.write_text(json.dumps({
        "schema": "biobridge.spliceai.request/1", "vcf": str(vcf), "annotation": "grch38",
        "distance": DISTANCE, "reference": {c: str(p) for c, p in reference.items()},
    }))

    total = {"records": len(records)}

    def progress(event):
        if event["event"] == "start":
            total["records"] = event.get("records", total["records"])
        elif event["event"] == "stage" and event.get("stage") == "loading_model":
            on_status(Progress("loading_model", "Loading the SpliceAI model…"))
        elif event["event"] == "stage" and event.get("stage") == "scoring":
            on_status(Progress("scoring", f"Scored 0 of {total['records']}…", 0, total["records"]))
        elif event["event"] == "progress":
            on_status(Progress("scoring", f"Scored {event['done']} of {event['total']}…",
                               event["done"], event["total"]))

    engine(["score", "--request", request_path, "--out", job / "results.json"], progress)
    results = json.loads((job / "results.json").read_text())
    timings["scoring_s"] = time.perf_counter() - t

    # 4. Rows, CSV, provenance
    check()
    on_status(Progress("report", "Preparing the results…"))
    t = time.perf_counter()
    rows = rows_from_results(results)
    summary = summarize(results, rows)
    eng = results["engine"]
    provenance = {
        **build_info(),
        "adapter": ADAPTER,
        "engine_mock": bool(eng.get("mock", False)),  # only the test engine sets this
        "spliceai_version": eng["spliceai"], "tensorflow_version": eng["tensorflow"],
        "keras_version": eng["keras"], "engine_python": eng["python"],
        "engine_lock_sha256": lock_digest(paths.ENGINE_LOCK),
        "models_sha256": "; ".join(f"{Path(k).name}:{v}" for k, v in eng["models_sha256"].items()),
        "annotation": "SpliceAI grch38 (GENCODE V24 canonical, bundled with spliceai)",
        "annotation_sha256": eng["annotation_sha256"],
        "reference_build": "GRCh38 (UCSC hg38)",
        "reference_sources": {c: UCSC_HG38.format(chrom=c) for c in reference},
        "reference_md5s": {c: HG38_MD5[c] for c in reference},
        "max_distance": results["settings"]["distance"],
        "score_modes": "masked (-M 1) and raw (-M 0)",
        "build_basis": basis,
        "build_evidence": None if evidence is None else {"verdict": evidence.verdict, "reasons": evidence.reasons},
        "license_acknowledgment": license_acknowledgment,
        "job_started": started,
        "input_name": input_name, "input_sha256": input_sha,
    }
    csv_path = write_csv(rows, provenance, job / "results.csv")
    timings["report_s"] = time.perf_counter() - t
    timings["total_s"] = time.perf_counter() - t0
    timings["engine"] = {k: v for k, v in results["timings"].items() if k != "per_record_s"}
    timings["engine_per_record_s"] = results["timings"].get("per_record_s", [])
    (job / "provenance.json").write_text(json.dumps({**provenance, "summary": summary, "timings": timings},
                                                    indent=1))
    on_status(Progress("done", "Done."))
    return JobResult(job, rows, summary, csv_path, provenance, timings)
