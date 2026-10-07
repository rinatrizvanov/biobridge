"""Facts about this BioBridge build and the machine, recorded with every job."""

from __future__ import annotations

import platform

from biobridge import __version__, buildinfo, paths

REPO = paths.PACKAGE.parent.parent


def biobridge_commit() -> str:
    """The source revision and whether packaged files had uncommitted changes.

    From a source checkout git is asked directly. The packaged app reads what
    scripts/build_app.sh recorded at build time and never calls git.
    """
    if (REPO / ".git").exists():
        return buildinfo.describe(*buildinfo.git_state(REPO))
    recorded = buildinfo.read(paths.PACKAGE)
    if recorded is None:
        return "unknown"
    return buildinfo.describe(recorded.get("commit", "unknown"), recorded.get("uncommitted_changes"))


def host() -> str:
    return f"macOS {platform.mac_ver()[0] or 'unknown'} ({platform.machine()})"


def build_info() -> dict:
    return {"biobridge_version": __version__, "biobridge_commit": biobridge_commit(),
            "biobridge_source_sha256": buildinfo.source_digest(paths.PACKAGE), "host": host()}
