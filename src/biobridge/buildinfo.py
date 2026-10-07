"""Which source a BioBridge build came from.

A source checkout asks git directly. The packaged app has no checkout and must never
call git (on a Mac without developer tools, /usr/bin/git opens an install dialog),
so `scripts/build_app.sh` records the facts at build time in `_build_info.json`
inside the package. Nothing is invented: if git cannot be read, the commit is
"unknown". The source digest covers every packaged file, so a recorded commit can
be checked against the code that is actually in the bundle.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from pathlib import Path

BUILD_INFO_NAME = "_build_info.json"
# Files whose changes alter the packaged app.
PACKAGED_PATHS = ("src", "pyproject.toml", "uv.lock")


def source_digest(package: Path) -> str:
    """sha256 over the package's files (relative path and bytes), excluding caches and build info."""
    digest = hashlib.sha256()
    for path in sorted(p for p in package.rglob("*") if p.is_file()):
        rel = path.relative_to(package).as_posix()
        if "__pycache__" in path.parts or path.suffix == ".pyc" or rel == BUILD_INFO_NAME:
            continue
        digest.update(rel.encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


def git_state(repo: Path) -> tuple[str, bool | None]:
    """(full commit sha or "unknown", whether packaged files have uncommitted changes)."""
    try:
        head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                              capture_output=True, text=True, timeout=10)
        status = subprocess.run(["git", "-C", str(repo), "status", "--porcelain", "--untracked-files=all",
                                 "--", *PACKAGED_PATHS], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return "unknown", None
    if head.returncode or status.returncode:
        return "unknown", None
    return head.stdout.strip(), bool(status.stdout.strip())


def describe(commit: str, dirty: bool | None) -> str:
    if commit == "unknown":
        return "unknown"
    if dirty is None:
        return f"{commit} (working-tree state unknown)"
    return f"{commit}+uncommitted changes" if dirty else commit


def collect(repo: Path, package: Path) -> dict:
    commit, dirty = git_state(repo)
    return {"commit": commit, "uncommitted_changes": dirty, "source_sha256": source_digest(package),
            "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}


def read(package: Path) -> dict | None:
    try:
        return json.loads((package / BUILD_INFO_NAME).read_text())
    except (OSError, ValueError):
        return None
