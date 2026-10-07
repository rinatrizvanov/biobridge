"""Source revision and build status in provenance: real values only, never invented."""

import json
import subprocess

import pytest

from biobridge import buildinfo, provenance


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True,
                   env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid",
                        "PATH": "/usr/bin:/bin", "HOME": str(repo)})


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    (root / "src" / "biobridge").mkdir(parents=True)
    (root / "src" / "biobridge" / "a.py").write_text("x = 1\n")
    (root / "pyproject.toml").write_text("[project]\n")
    (root / "docs").mkdir()
    (root / "docs" / "notes.md").write_text("notes\n")
    git(root, "init", "-q", "-b", "main")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "init")
    return root


def test_clean_and_dirty_states_are_read_from_git(repo):
    commit, dirty = buildinfo.git_state(repo)
    assert len(commit) == 40 and dirty is False
    (repo / "docs" / "notes.md").write_text("edited\n")  # not packaged
    assert buildinfo.git_state(repo)[1] is False
    (repo / "src" / "biobridge" / "b.py").write_text("new\n")  # untracked but packaged
    assert buildinfo.git_state(repo)[1] is True


def test_git_unavailable_gives_unknown_not_an_invented_commit(tmp_path):
    assert buildinfo.git_state(tmp_path) == ("unknown", None)
    assert buildinfo.describe("unknown", None) == "unknown"


def test_descriptions():
    sha = "a" * 40
    assert buildinfo.describe(sha, False) == sha
    assert buildinfo.describe(sha, True) == sha + "+uncommitted changes"
    assert buildinfo.describe(sha, None) == sha + " (working-tree state unknown)"


def test_source_digest_covers_code_but_not_caches_or_the_record_itself(tmp_path):
    pkg = tmp_path / "biobridge"
    (pkg / "__pycache__").mkdir(parents=True)
    (pkg / "a.py").write_text("x = 1\n")
    before = buildinfo.source_digest(pkg)
    (pkg / "__pycache__" / "a.cpython-311.pyc").write_bytes(b"cache")
    (pkg / buildinfo.BUILD_INFO_NAME).write_text("{}")
    assert buildinfo.source_digest(pkg) == before
    (pkg / "a.py").write_text("x = 2\n")
    assert buildinfo.source_digest(pkg) != before


def test_packaged_app_reads_the_recorded_revision(tmp_path, monkeypatch):
    pkg = tmp_path / "app" / "biobridge"
    pkg.mkdir(parents=True)
    monkeypatch.setattr(provenance, "REPO", tmp_path / "app")  # no .git: packaged layout
    monkeypatch.setattr(provenance.paths, "PACKAGE", pkg)
    assert provenance.biobridge_commit() == "unknown"  # nothing recorded -> unknown
    (pkg / buildinfo.BUILD_INFO_NAME).write_text(json.dumps(
        {"commit": "b" * 40, "uncommitted_changes": True, "source_sha256": "x"}))
    assert provenance.biobridge_commit() == "b" * 40 + "+uncommitted changes"
