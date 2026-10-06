"""Fixtures for model tests, which run real SpliceAI inference in the engine environment.

These tests never skip when their prerequisites are missing: if a model test was
selected (`pytest -m model`), a missing engine environment is a failure.
"""

import importlib.util
import os
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def engine_bin():
    env_dir = Path(os.environ.get("BIOBRIDGE_ENGINE_ENV", REPO / ".engine-venv"))
    spliceai = env_dir / "bin" / "spliceai"
    if not spliceai.exists():
        pytest.fail(
            f"SpliceAI engine environment not found at {env_dir}. "
            "Create it with scripts/create_engine_env.sh or set BIOBRIDGE_ENGINE_ENV."
        )
    return spliceai.parent


@pytest.fixture(scope="session")
def reference_set():
    spec = importlib.util.spec_from_file_location(
        "fetch_test_reference", REPO / "scripts" / "fetch_test_reference.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.ensure_set


@pytest.fixture(scope="session")
def model_data():
    return Path(__file__).parent / "data"
