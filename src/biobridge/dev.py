"""Developer command line for running a scoring job without the app (not for end users).

    python -m biobridge.dev score --variant chr17-43057051-C-T --confirm-grch38 \\
        --engine-env .engine-venv --home /tmp/biobridge-dev

    python -m biobridge.dev score --vcf variants.vcf.gz --confirm-grch38 --engine-env .engine-venv
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from biobridge import paths
from biobridge.inputs.text import InputError
from biobridge.jobs.engine import INACTIVITY_TIMEOUT, EngineError
from biobridge.jobs.job import JobRequest, run_job
from biobridge.setup.envs import engine_ready
from biobridge.setup.processes import ChildProcesses


def license_acknowledgment(base: Path) -> str:
    try:
        settings = json.loads((base / "settings.json").read_text())
    except (OSError, ValueError):
        settings = {}
    if settings.get("engine_license_ack"):
        return f"acknowledged in BioBridge at {settings.get('engine_license_ack_time', 'unknown time')}"
    return "developer command line (no in-app acknowledgment)"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m biobridge.dev")
    sub = parser.add_subparsers(dest="command", required=True)
    score = sub.add_parser("score", help="score one pasted variant or a small VCF")
    source = score.add_mutually_exclusive_group(required=True)
    source.add_argument("--variant", help="e.g. chr17-43057051-C-T")
    source.add_argument("--vcf", type=Path, help=".vcf or .vcf.gz (GRCh38)")
    score.add_argument("--confirm-grch38", action="store_true", help="confirm the coordinates are GRCh38")
    score.add_argument("--home", type=Path, default=None, help="BioBridge data folder (default: app's)")
    score.add_argument("--engine-env", type=Path, default=None, help="engine environment (default: app's)")
    score.add_argument("--timeout", type=float, default=INACTIVITY_TIMEOUT, help="engine inactivity timeout, s")
    args = parser.parse_args(argv)

    base = args.home or paths.home()
    base.mkdir(parents=True, exist_ok=True)
    engine_env = args.engine_env or paths.engine_env(base)
    if args.engine_env is None and not engine_ready(engine_env, paths.ENGINE_LOCK):
        print(f"No finished engine environment at {engine_env}. Run the app's setup, or pass "
              "--engine-env (e.g. .engine-venv from scripts/create_engine_env.sh).", file=sys.stderr)
        return 2
    request = JobRequest(
        paste=args.variant,
        vcf_bytes=args.vcf.read_bytes() if args.vcf else None,
        vcf_name=args.vcf.name if args.vcf else None,
        confirm_grch38=args.confirm_grch38,
    )
    t = time.perf_counter()
    try:
        result = run_job(request, base, engine_env, ChildProcesses(),
                         on_status=lambda text: print(f"[{time.perf_counter() - t:6.1f}s] {text}", file=sys.stderr),
                         license_acknowledgment=license_acknowledgment(base),
                         inactivity_timeout=args.timeout)
    except InputError as exc:
        print(f"Input problem: {exc}", file=sys.stderr)
        return 1
    except EngineError as exc:
        print(f"Engine problem: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"job": str(result.job_dir), "csv": str(result.csv_path), "summary": result.summary,
                      "timings_s": {k: round(v, 2) for k, v in result.timings.items() if isinstance(v, float)}},
                     indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
