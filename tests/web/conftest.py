"""Shared fixtures: a BioBridge web app driven by the TEST-ONLY fake engine."""

import sys
import time
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from biobridge.web.app import BioBridgeWeb
from biobridge.web.jobs import JobManager

FAKE_RUNNER = Path(__file__).with_name("fake_runner.py")


def fake_reference(chrom, base, progress=None):
    path = base / "fake-reference" / f"{chrom}.fa"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f">{chrom}\nN\n")
    return path


def make_manager(base: Path) -> JobManager:
    return JobManager(base, engine_env=base / "no-engine", license_acknowledgment=lambda: "test",
                      runner=FAKE_RUNNER, python=Path(sys.executable), reference_provider=fake_reference)


@pytest.fixture
def web_factory(tmp_path):
    def make(allowed_host="testserver"):
        return BioBridgeWeb(make_manager(tmp_path / "Application Support" / "BioBridge"), allowed_host)
    return make


def wait_for(predicate, timeout=20.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return predicate()


@pytest.fixture(scope="module", params=["chromium", "webkit"])
def browser(request):
    """A real browser per test module, once for Chromium and once for WebKit."""
    with sync_playwright() as p:
        b = getattr(p, request.param).launch()
        yield b
        b.close()
