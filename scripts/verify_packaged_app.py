#!/usr/bin/env python3
"""Drive the packaged BioBridge.app through its interface and verify its results.

    T=$(mktemp -d -t biobridge-packaged)
    uv run python scripts/verify_packaged_app.py build/biobridge/macos/app/BioBridge.app "$T"

The app runs against an isolated data directory inside the given folder (on this
Mac; not a clean machine). Playwright (Chromium) performs the manual checklist:
pasted variant, VCF upload, progress, Cancel, results, CSV download and Quit.
It also checks that every request stays on 127.0.0.1 (no CDN or other external
asset), that no request fails and that the page logs no errors.

Compare-only mode checks jobs that were already run by hand in the packaged app,
reading the data folder and writing only to the output folder:

    uv run python scripts/verify_packaged_app.py --compare-jobs \
        "$HOME/Library/Application Support/BioBridge" "$(mktemp -d -t biobridge-compare)"

Each completed packaged job is then re-scored from its saved input.vcf with the
development runner and engine (.engine-venv), and the results must be identical
(upstream strings, statuses, reasons, details, warnings), as must the CSV score
columns. Everything is kept in the given folder; a summary goes to
verification.json.
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

from playwright.sync_api import expect, sync_playwright  # noqa: E402

from biobridge.buildinfo import source_digest  # noqa: E402
from biobridge.genome import HG38_MD5  # noqa: E402
from biobridge.reports.csv_report import COLUMNS, PROVENANCE_COLUMNS, write_csv  # noqa: E402
from biobridge.results import rows_from_results  # noqa: E402

DATA = REPO / "tests" / "model" / "data"
DEV_PYTHON = REPO / ".engine-venv" / "bin" / "python"
DEV_RUNNER = REPO / "src" / "biobridge" / "adapters" / "spliceai" / "runner.py"
DEV_REFERENCE = REPO / ".cache" / "reference" / "hg38"
STUB = "BioBridge.app/Contents/MacOS/BioBridge"


def wait(predicate, timeout, what):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.25)
    raise SystemExit(f"timed out waiting for {what}")


def app_pids(app: Path) -> list[int]:
    out = subprocess.run(["pgrep", "-f", str(app / "Contents" / "MacOS" / "BioBridge")],
                         capture_output=True, text=True).stdout
    return [int(p) for p in out.split()]


def run_flow(url: str, folder: Path, report: dict) -> None:
    host = urlparse(url).netloc
    requests, failures, errors = [], [], []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        page.on("request", lambda r: requests.append(r.url))
        page.on("requestfailed", lambda r: failures.append(f"{r.url} {r.failure}"))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))

        page.goto(url)
        expect(page.get_by_role("heading", name="Score variants with SpliceAI")).to_be_visible()

        def run(fill, csv_name, timeout=600_000):
            fill()
            page.get_by_label("These coordinates are GRCh38 (hg38).").check()
            page.get_by_role("button", name="Run SpliceAI").click()
            expect(page.get_by_role("heading", name="Scoring…")).to_be_visible()
            expect(page.get_by_role("heading", name="Results")).to_be_visible(timeout=timeout)
            assert page.get_by_text("MOCK").count() == 0, "packaged app must not show MOCK results"
            with page.expect_download() as info:
                page.get_by_role("link", name="Download CSV").click()
            info.value.save_as(folder / csv_name)
            page.get_by_role("link", name="Score more variants").click()

        # 1. Pasted variant
        t = time.monotonic()
        run(lambda: page.get_by_label("GRCh38 position and alleles").fill("chr17-43057051-C-T"), "pasted.csv")
        report["pasted_seconds"] = round(time.monotonic() - t, 1)
        # 2. VCF upload (16 records on chr17 and chr22, including unscored cases)
        t = time.monotonic()
        run(lambda: page.get_by_label("VCF or VCF.gz, up to 1 MB").set_input_files(
            DATA / "runner_vs_cli_grch38.vcf"), "uploaded.csv")
        report["upload_seconds"] = round(time.monotonic() - t, 1)
        # 3. Progress and Cancel (50 alleles; cancelled after the first is scored)
        page.get_by_label("VCF or VCF.gz, up to 1 MB").set_input_files(DATA / "runtime_50_alleles_grch38.vcf")
        page.get_by_label("These coordinates are GRCh38 (hg38).").check()
        page.get_by_role("button", name="Run SpliceAI").click()
        progress = page.locator("#bb-progress-text")
        expect(progress).to_contain_text("Scored", timeout=120_000)
        expect(progress).not_to_contain_text("Scored 0 of", timeout=60_000)
        report["progress_seen"] = progress.inner_text()
        page.get_by_role("button", name="Cancel").click()
        expect(page.get_by_role("heading", name="Cancelled")).to_be_visible(timeout=30_000)
        # 4. Quit from the page
        page.get_by_role("button", name="Quit BioBridge").click()
        expect(page.get_by_role("heading", name="BioBridge is quitting")).to_be_visible()
        browser.close()

    external = sorted({u for u in requests if urlparse(u).netloc != host})
    report["requests"] = len(requests)
    report["asset_requests"] = sorted({urlparse(u).path for u in requests if "/static/" in u})
    report["external_requests"] = external
    report["failed_requests"] = failures
    report["page_errors"] = errors


def dev_rescore(job: Path, folder: Path) -> dict:
    request = json.loads((job / "request.json").read_text())
    for chrom in request["reference"]:
        stamp = Path(request["reference"][chrom] + ".md5")
        assert stamp.read_text() == HG38_MD5[chrom], f"packaged {chrom} md5 differs"
    dev_request = dict(request, vcf=str(job / "input.vcf"),
                       reference={c: str(DEV_REFERENCE / f"{c}.fa") for c in request["reference"]})
    req_path, out = folder / f"dev-{job.name}.request.json", folder / f"dev-{job.name}.results.json"
    req_path.write_text(json.dumps(dev_request))
    proc = subprocess.run([DEV_PYTHON, DEV_RUNNER, "score", "--request", req_path, "--out", out],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr[-2000:]
    return json.loads(out.read_text())


def compare(job: Path, folder: Path) -> dict:
    packaged = json.loads((job / "results.json").read_text())
    dev = dev_rescore(job, folder)
    for a, b in zip(packaged["records"], dev["records"], strict=True):
        assert a["upstream"] == b["upstream"], f"{job.name} record {a['index']}: upstream differs"
        assert a["alleles"] == b["alleles"], f"{job.name} record {a['index']}: statuses/details differ"
    assert packaged["engine"]["models_sha256"] == dev["engine"]["models_sha256"]
    # CSV: the packaged file vs one written from the development results; provenance
    # columns are excluded (commit, start time and acknowledgment legitimately differ).
    # Only for jobs made from the current source: an earlier build wrote its CSV with
    # earlier code (for example "AG" instead of "none" for all-zero rows before 0005).
    prov = json.loads((job / "provenance.json").read_text())
    same_source = prov.get("biobridge_source_sha256") == source_digest(REPO / "src" / "biobridge")
    if same_source:
        dev_csv = write_csv(rows_from_results(dev), prov, folder / f"dev-{job.name}.csv")
        score_cols = [c for c in COLUMNS if c not in PROVENANCE_COLUMNS]
        read = lambda p: [[r[c] for c in score_cols] for r in csv.DictReader(open(p))]  # noqa: E731
        assert read(job / "results.csv") == read(dev_csv), f"{job.name}: CSV score columns differ"
    return {"job": job.name, "input": prov["input_name"], "records": len(packaged["records"]),
            "rows": len(rows_from_results(packaged)), "identical_to_dev_runner": True,
            "csv_compared": same_source or "no: made by an earlier build",
            "packaged_commit_field": prov["biobridge_commit"]}


def compare_only(home: Path, folder: Path) -> int:
    finished = sorted(p for p in (home / "jobs").iterdir() if (p / "results.json").exists())
    # Jobs from the M0 demo app have no provenance.json and are listed, not compared.
    jobs = [p for p in finished if (p / "provenance.json").exists()]
    results = [compare(job, folder) for job in jobs]
    results += [{"job": p.name, "skipped": "no provenance.json (made before M1)"} for p in finished if p not in jobs]
    (folder / "comparison.json").write_text(json.dumps(results, indent=1))
    print(json.dumps(results, indent=1))
    return 0


def main() -> int:
    if sys.argv[1] == "--compare-jobs":
        return compare_only(Path(sys.argv[2]).resolve(), Path(sys.argv[3]).resolve())
    app, folder = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    home = folder / "Application Support" / "BioBridge"
    home.mkdir(parents=True, exist_ok=True)
    (home / "settings.json").write_text(json.dumps(
        {"engine_license_ack": True, "engine_license_ack_time": "packaged-app verification run"}))
    link = folder / "auth-url"
    if app_pids(app):
        raise SystemExit(f"another instance of {app} is running; quit it first")
    report: dict = {"app": str(app), "data_dir": str(home)}

    t = time.monotonic()
    subprocess.run(["open", "-n", "--env", f"BIOBRIDGE_HOME={home}", "--env", "BIOBRIDGE_NO_BROWSER=1",
                    "--env", f"BIOBRIDGE_AUTH_URL_FILE={link}", str(app)], check=True)
    wait(lambda: link.exists() and link.read_text().startswith("http://127.0.0.1:"), 900, "the sign-in link")
    report["setup_seconds"] = round(time.monotonic() - t, 1)
    run_flow(link.read_text(), folder, report)

    wait(lambda: not app_pids(app), 30, "the app to quit")
    log = [json.loads(line) for line in (home / "logs" / "launcher.log").read_text().splitlines()]
    report["quit_cleanup"] = next(e for e in reversed(log) if e["event"] == "quit_cleanup")
    report["ui_stalls_over_100ms"] = [e["ms"] for e in log if e["event"] == "ui_stall"]

    jobs = sorted(p for p in (home / "jobs").iterdir() if (p / "results.json").exists())
    report["comparisons"] = [compare(job, folder) for job in jobs]
    report["cancelled_jobs_without_results"] = sum(
        1 for p in (home / "jobs").iterdir() if not (p / "results.json").exists())

    ok = (not report["external_requests"] and not report["failed_requests"] and not report["page_errors"]
          and report["quit_cleanup"]["survivors"] == [] and len(report["comparisons"]) == 2)
    report["passed"] = ok
    (folder / "verification.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
