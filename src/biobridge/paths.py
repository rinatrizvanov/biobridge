"""Where BioBridge keeps its files on the user's Mac.

Everything BioBridge writes lives in its Application Support and Logs folders, never
inside the app bundle (writing there would break the bundle's code signature).
BIOBRIDGE_HOME relocates both, for tests and portable runs.
"""

from __future__ import annotations

import os
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
SPLICEAI_ADAPTER = PACKAGE / "adapters" / "spliceai"
ENGINE_LOCK = SPLICEAI_ADAPTER / "engine.lock"
RUNNER = SPLICEAI_ADAPTER / "runner.py"


def home() -> Path:
    override = os.environ.get("BIOBRIDGE_HOME")
    if override:
        return Path(override)
    return Path.home() / "Library" / "Application Support" / "BioBridge"


def logs() -> Path:
    override = os.environ.get("BIOBRIDGE_HOME")
    if override:
        return Path(override) / "logs"
    return Path.home() / "Library" / "Logs" / "BioBridge"


def engine_env(base: Path) -> Path:
    return base / "envs" / "spliceai-1.3.1"
