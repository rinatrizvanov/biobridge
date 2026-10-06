"""Engine install: retries, backoff, completion marker and a clean child environment.

A fake `uv` shell script stands in for the real one. It records its arguments and
environment, creates a fake environment on `venv`, and fails `pip sync` as many
times as the test asks (simulating an interrupted download).
"""

import threading

import pytest

from biobridge.setup.envs import InstallError, engine_ready, install_engine
from biobridge.setup.processes import Cancelled, ChildProcesses

FAKE_UV = r"""#!/bin/sh
state="$(dirname "$0")"
echo "$*" >> "$state/calls.log"
env > "$state/last_env"
if [ "$1" = "venv" ]; then
  for last; do :; done
  mkdir -p "$last/bin"
  printf '#!/bin/sh\nexit $(cat "%s/smoke_rc" 2>/dev/null || echo 0)\n' "$state" > "$last/bin/python"
  chmod +x "$last/bin/python"
  exit 0
fi
if [ "$1" = "pip" ]; then
  n=$(cat "$state/fail_syncs" 2>/dev/null || echo 0)
  if [ "$n" -gt 0 ]; then
    echo $((n - 1)) > "$state/fail_syncs"
    echo "error: Failed to download (simulated interruption)"
    exit 2
  fi
  echo "Installed 49 packages"
  exit 0
fi
exit 9
"""


@pytest.fixture
def setup(tmp_path):
    state = tmp_path / "fake uv"  # A space in the path, like "Application Support".
    state.mkdir()
    uv = state / "uv"
    uv.write_text(FAKE_UV)
    uv.chmod(0o755)
    lock = tmp_path / "engine.lock"
    lock.write_text("spliceai==1.3.1 --hash=sha256:00\n")
    base = tmp_path / "Application Support" / "BioBridge"
    env_dir = base / "envs" / "spliceai-1.3.1"
    return {"state": state, "uv": uv, "lock": lock, "base": base, "env_dir": env_dir}


def install(s, *, sleeps=None, attempts_seen=None, output=None, procs=None, **kwargs):
    sleeps = [] if sleeps is None else sleeps
    return install_engine(
        s["uv"], s["lock"], s["env_dir"], s["base"], procs or ChildProcesses(),
        on_output=(output.append if output is not None else lambda line: None),
        on_attempt=lambda n, m: attempts_seen.append((n, m)) if attempts_seen is not None else None,
        sleep=kwargs.pop("sleep", sleeps.append),
        **kwargs,
    )


def test_interrupted_install_is_retried_and_then_marked_complete(setup):
    (setup["state"] / "fail_syncs").write_text("1")
    sleeps, attempts, output = [], [], []
    install(setup, sleeps=sleeps, attempts_seen=attempts, output=output)
    assert attempts == [(1, 3), (2, 3)]
    assert sleeps == [15.0]
    assert any("simulated interruption" in line for line in output)
    assert engine_ready(setup["env_dir"], setup["lock"])


def test_gives_up_after_three_attempts_without_marking_complete(setup):
    (setup["state"] / "fail_syncs").write_text("5")
    sleeps = []
    with pytest.raises(InstallError, match="after 3 attempts"):
        install(setup, sleeps=sleeps)
    assert sleeps == [15.0, 30.0]
    assert not engine_ready(setup["env_dir"], setup["lock"])


def test_failed_smoke_test_is_not_marked_complete(setup):
    (setup["state"] / "smoke_rc").write_text("1")
    with pytest.raises(InstallError, match="smoke test"):
        install(setup)
    assert not engine_ready(setup["env_dir"], setup["lock"])


def test_changed_lock_invalidates_a_finished_install(setup):
    install(setup)
    assert engine_ready(setup["env_dir"], setup["lock"])
    setup["lock"].write_text("spliceai==1.3.1 --hash=sha256:11\n")
    assert not engine_ready(setup["env_dir"], setup["lock"])


def test_reinstall_after_an_interrupted_run_starts_clean(setup):
    install(setup)
    calls = (setup["state"] / "calls.log").read_text().splitlines()
    assert calls[0].startswith("venv --python 3.11 --managed-python --clear ")
    assert "--require-hashes --no-build --compile-bytecode" in calls[1]


def test_child_environment_excludes_developer_tools(setup, monkeypatch):
    monkeypatch.setenv("PATH", "/opt/homebrew/bin:/Users/dev/.local/bin:/usr/bin:/bin")
    for leak in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "CONDA_PREFIX", "UV_INDEX_URL",
                 "UV_PYTHON", "PIP_INDEX_URL"):
        monkeypatch.setenv(leak, "/somewhere")
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.example:8080")
    install(setup)
    env = dict(line.split("=", 1) for line in
               (setup["state"] / "last_env").read_text().splitlines() if "=" in line)
    assert env["PATH"] == "/usr/bin:/bin:/usr/sbin:/sbin"
    for leak in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "CONDA_PREFIX", "UV_INDEX_URL",
                 "UV_PYTHON", "PIP_INDEX_URL"):
        assert leak not in env
    assert env["HTTPS_PROXY"] == "http://proxy.example:8080"  # Institutional proxies still work.
    assert env["UV_NO_CONFIG"] == "1"
    assert env["UV_CACHE_DIR"] == str(setup["base"] / "uv-cache")
    assert env["UV_PYTHON_INSTALL_DIR"] == str(setup["base"] / "uv-python")
    assert (env["UV_HTTP_TIMEOUT"], env["UV_HTTP_RETRIES"]) == ("120", "5")


def test_quit_during_backoff_cancels_the_install(setup):
    (setup["state"] / "fail_syncs").write_text("5")
    procs = ChildProcesses()
    threading.Timer(0.5, procs.terminate_all).start()
    with pytest.raises(Cancelled):
        install(setup, procs=procs, sleep=procs.sleep, backoff=(30.0,))
    assert not engine_ready(setup["env_dir"], setup["lock"])
