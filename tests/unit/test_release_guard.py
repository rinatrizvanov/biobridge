"""The shipped app can only run the real engine: the fake engine and its MOCK flag
exist in tests only."""

import tomllib
from pathlib import Path

from biobridge import paths
from biobridge.web.jobs import JobManager

REPO = Path(__file__).resolve().parents[2]


def test_job_manager_defaults_to_the_real_runner(tmp_path):
    manager = JobManager(tmp_path, tmp_path / "engine", license_acknowledgment=lambda: "")
    assert manager.runner == paths.RUNNER
    assert manager.runner.name == "runner.py" and manager.runner.parent.name == "spliceai"
    assert manager.python is None  # i.e. the engine environment's own Python


def test_shipped_code_never_references_the_fake_engine_or_sets_mock():
    for path in (REPO / "src" / "biobridge").rglob("*"):
        if path.suffix in {".py", ".html", ".js", ".css"}:
            text = path.read_text()
            assert "fake_runner" not in text, path
            assert '"mock": True' not in text and "'mock': True" not in text, path


def test_packaged_sources_exclude_tests():
    config = tomllib.loads((REPO / "pyproject.toml").read_text())
    assert config["tool"]["briefcase"]["app"]["biobridge"]["sources"] == ["src/biobridge"]
