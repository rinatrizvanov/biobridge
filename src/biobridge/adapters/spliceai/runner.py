"""SpliceAI runner, executed as a subprocess inside the engine environment.

    <engine python> runner.py score --request request.json --out results.json

The runner imports the unmodified upstream `spliceai` package and calls its public
`Annotator` and `get_delta_scores` exactly as the upstream CLI does, once with
mask=0 (raw) and once with mask=1 (masked). It never edits upstream code.

Reference chromosomes are separate FASTA files. One Annotator (and one copy of the
five models) is built, and its `ref_fasta` attribute is pointed at the right
chromosome before each record. Upstream reads only `ann.ref_fasta`, and
`normalise_chrom` follows that FASTA's first sequence name.

Channels: structured JSON-lines events go to the original stdout. File descriptor 1
is then redirected to stderr, so anything Keras, TensorFlow or upstream code prints
to stdout (e.g. predict progress bars) ends up in the log, never in the event stream.

This file must run with only the engine environment's packages (stdlib, pysam,
pyfaidx, spliceai); it cannot import biobridge.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
import time
import traceback
from importlib import metadata, resources

REQUEST_SCHEMA = "biobridge.spliceai.request/1"
RESULTS_SCHEMA = "biobridge.spliceai.results/1"
MODEL_FILES = [f"models/spliceai{i}.h5" for i in range(1, 6)]
ANNOTATION_FILES = {"grch37": "annotations/grch37.txt", "grch38": "annotations/grch38.txt"}

# Upstream warning text -> BioBridge reason code (record-level skips).
UPSTREAM_SKIPS = {
    "Skipping record (bad input)": "INVALID_INPUT",
    "Skipping record (fasta issue)": "INVALID_INPUT",
    "Skipping record (ref issue)": "REF_MISMATCH",
    "Skipping record (near chromosome end)": "NEAR_CONTIG_END",
    "Skipping record (ref too long)": "DELETION_TOO_LONG",
}
SCORE_FIELDS = ["DS_AG", "DS_AL", "DS_DG", "DS_DL", "DP_AG", "DP_AL", "DP_DG", "DP_DL"]


class EventStream:
    """JSON-lines events on a private duplicate of the original stdout."""

    def __init__(self) -> None:
        self._out = os.fdopen(os.dup(1), "w", buffering=1)
        os.dup2(2, 1)  # From here on, fd 1 (anything printing to stdout) goes to stderr.

    def emit(self, event: str, **fields) -> None:
        self._out.write(json.dumps({"event": event, **fields}) + "\n")


class WarningCapture(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.WARNING)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


def ucsc_name(chrom: str) -> str:
    return chrom if chrom.startswith("chr") else "chr" + chrom


def sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_upstream(value: str) -> dict:
    """Split one upstream 'ALT|GENE|DS_AG|...|DP_DL' string; '.' stays None, never 0."""
    alt, gene, *scores = value.split("|")
    parsed = {"alt": alt, "gene": gene}
    for field, text in zip(SCORE_FIELDS, scores):
        if text == ".":
            parsed[field] = None
        else:
            parsed[field] = float(text) if field.startswith("DS") else int(text)
    return parsed


def classify(record, alt: str, genes: list[str], skip_reason: str | None) -> str | None:
    """Return a NOT_SCORED reason for one allele, or None if upstream should score it."""
    if skip_reason:
        return skip_reason
    if not genes:
        return "NOT_IN_SPLICEAI_GENE"
    if any(c in alt for c in ".-*<>"):
        return "UNSUPPORTED_ALLELE"  # Upstream silently drops these alleles.
    if len(record.ref) > 1 and len(alt) > 1:
        return "COMPLEX_DELINS"  # Upstream reports '.' for every score.
    return None


def score(request: dict, events: EventStream) -> dict:
    if request.get("schema") != REQUEST_SCHEMA:
        raise ValueError(f"unsupported request schema: {request.get('schema')!r}")
    timings: dict[str, float] = {}
    t0 = time.perf_counter()

    import pysam
    from pyfaidx import Fasta

    with pysam.VariantFile(request["vcf"]) as vcf:
        records = list(vcf)
    timings["read_input_s"] = time.perf_counter() - t0
    events.emit("start", records=len(records))

    reference = {ucsc_name(c): p for c, p in request["reference"].items()}
    needed = [ucsc_name(r.chrom) for r in records if ucsc_name(r.chrom) in reference]
    annotation = request.get("annotation", "grch38")
    distance = int(request.get("distance", 50))
    ann, fastas = None, {}
    if needed:  # With no usable chromosome, every record is CONTIG_NOT_SUPPORTED; skip TensorFlow.
        events.emit("stage", stage="loading_model")
        t = time.perf_counter()
        from spliceai.utils import Annotator, get_delta_scores
        timings["import_s"] = time.perf_counter() - t

        t = time.perf_counter()
        ann = Annotator(reference[needed[0]], annotation)
        timings["model_load_s"] = time.perf_counter() - t
        fastas[needed[0]] = ann.ref_fasta

    capture = WarningCapture()
    logging.getLogger().addHandler(capture)

    out_records = []
    per_record_s = []
    events.emit("stage", stage="scoring")
    for i, rec in enumerate(records):
        t = time.perf_counter()
        chrom = ucsc_name(rec.chrom)
        alts = list(rec.alts or ())
        entry = {
            "index": i, "id": rec.id, "chrom": rec.chrom, "pos": rec.pos, "ref": rec.ref, "alts": alts,
            "upstream": {"raw": [], "masked": []}, "warnings": [], "alleles": [],
        }
        try:
            if chrom not in reference:
                entry["alleles"] = [{"alt": a, "status": "NOT_SCORED", "reason": "CONTIG_NOT_SUPPORTED"}
                                    for a in alts]
            else:
                if chrom not in fastas:
                    fastas[chrom] = Fasta(reference[chrom], rebuild=False)
                ann.ref_fasta = fastas[chrom]

                capture.messages.clear()
                raw = list(get_delta_scores(rec, ann, distance, 0))
                warnings = list(capture.messages)
                capture.messages.clear()
                masked = list(get_delta_scores(rec, ann, distance, 1))
                entry["upstream"] = {"raw": raw, "masked": masked}
                entry["warnings"] = warnings

                skip = next((code for text, code in UPSTREAM_SKIPS.items()
                             if any(w.startswith(text) for w in warnings)), None)
                genes = [str(g) for g in ann.get_name_and_strand(rec.chrom, rec.pos)[0]]
                entry["alleles"] = build_alleles(rec, alts, genes, skip, raw, masked)
            if not alts:
                entry["alleles"] = [{"alt": None, "status": "NOT_SCORED", "reason": "INVALID_INPUT",
                                     "detail": "record has no ALT allele"}]
        except Exception as exc:  # One bad record must not sink the job.
            entry["alleles"] = [{"alt": a, "status": "ERROR", "reason": "ENGINE_ERROR",
                                 "detail": f"{type(exc).__name__}: {exc}"} for a in alts]
            print(traceback.format_exc(), file=sys.stderr)
        per_record_s.append(time.perf_counter() - t)
        out_records.append(entry)
        events.emit("progress", done=i + 1, total=len(records))

    logging.getLogger().removeHandler(capture)
    timings["per_record_s"] = per_record_s
    timings["total_s"] = time.perf_counter() - t0

    package = resources.files("spliceai")
    return {
        "schema": RESULTS_SCHEMA,
        "engine": {
            "spliceai": metadata.version("spliceai"),
            "tensorflow": metadata.version("tensorflow"),
            "keras": metadata.version("keras"),
            "python": sys.version.split()[0],
            "models_sha256": {f: sha256(package / f) for f in MODEL_FILES},
            "annotation": annotation,
            "annotation_sha256": sha256(package / ANNOTATION_FILES[annotation])
            if annotation in ANNOTATION_FILES else None,
        },
        "settings": {"distance": distance, "masks": [0, 1]},
        "timings": timings,
        "records": out_records,
    }


def build_alleles(rec, alts, genes, skip, raw, masked) -> list[dict]:
    """Pair upstream raw/masked strings with alleles and genes; check they are consistent."""
    raw_by_alt: dict[str, list[str]] = {}
    masked_by_alt: dict[str, list[str]] = {}
    for value in raw:
        raw_by_alt.setdefault(value.split("|", 1)[0], []).append(value)
    for value in masked:
        masked_by_alt.setdefault(value.split("|", 1)[0], []).append(value)

    alleles = []
    for alt in alts:
        r, m = raw_by_alt.get(alt, []), masked_by_alt.get(alt, [])
        reason = classify(rec, alt, genes, skip)
        expected_rows = len(genes) if reason in (None, "COMPLEX_DELINS") else 0
        if len(r) != expected_rows or len(m) != expected_rows:
            alleles.append({"alt": alt, "status": "ERROR", "reason": "UNEXPECTED_ENGINE_OUTPUT",
                            "detail": f"expected {expected_rows} result(s) per mask, got {len(r)}/{len(m)}"})
            continue
        rows = []
        for rv, mv in zip(r, m):
            rp, mp = parse_upstream(rv), parse_upstream(mv)
            if rp["gene"] != mp["gene"]:
                raise RuntimeError(f"raw/masked gene order differs: {rv} vs {mv}")
            rows.append({"gene": rp["gene"], "raw": rp, "masked": mp})
        if reason:
            alleles.append({"alt": alt, "status": "NOT_SCORED", "reason": reason, "genes": rows})
        else:
            alleles.append({"alt": alt, "status": "SCORED", "genes": rows})
    return alleles


def main() -> int:
    events = EventStream()
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p_score = sub.add_parser("score")
    p_score.add_argument("--request", required=True)
    p_score.add_argument("--out", required=True)
    args = parser.parse_args()
    try:
        with open(args.request) as fh:
            request = json.load(fh)
        results = score(request, events)
        tmp = args.out + ".part"
        with open(tmp, "w") as fh:
            json.dump(results, fh, indent=1)
        os.replace(tmp, args.out)
        events.emit("done", results=args.out, seconds=round(results["timings"]["total_s"], 3))
        return 0
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        events.emit("error", message=f"{type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
    sys.exit(main())
