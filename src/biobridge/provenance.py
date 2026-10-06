"""Facts about this BioBridge build and the machine, recorded with every job."""

from __future__ import annotations

import platform
import subprocess

from biobridge import __version__, paths

REPO = paths.PACKAGE.parent.parent


def biobridge_commit() -> str:
    """The git commit, only when running from a source checkout.

    The packaged app never calls git: on a Mac without developer tools, /usr/bin/git
    opens an "install command line tools" dialog.
    """
    if not (REPO / ".git").exists():
        return "unknown"
    try:
        head = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short=12", "HEAD"],
                              capture_output=True, text=True, timeout=5)
        dirty = subprocess.run(["git", "-C", str(REPO), "status", "--porcelain", "--untracked-files=no"],
                               capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    if head.returncode:
        return "unknown"
    return head.stdout.strip() + ("+uncommitted changes" if dirty.stdout.strip() else "")


def host() -> str:
    return f"macOS {platform.mac_ver()[0] or 'unknown'} ({platform.machine()})"


def build_info() -> dict:
    return {"biobridge_version": __version__, "biobridge_commit": biobridge_commit(), "host": host()}
