"""The engine watchdog: hung runners are killed, failures and bad output are reported.

Fake runners are small Python scripts run with the test interpreter.
"""

import sys
import time

import pytest

from biobridge.jobs.engine import EngineError, EngineTimeout, run_engine
from biobridge.setup.processes import ChildProcesses, alive


def fake_runner(tmp_path, body):
    script = tmp_path / "runner.py"
    script.write_text("import json, os, sys, time\n"
                      "def emit(event, **kw):\n"
                      "    print(json.dumps({'event': event, **kw}), flush=True)\n" + body)
    return script


def run(tmp_path, body, timeout=1.0, procs=None):
    procs = procs or ChildProcesses()
    seen = []
    events = run_engine(sys.executable, fake_runner(tmp_path, body), [], procs, tmp_path / "runner.log",
                        env={"PATH": "/usr/bin:/bin"}, on_event=seen.append, inactivity_timeout=timeout)
    return events, seen


def test_steady_progress_completes_even_if_slower_overall_than_the_timeout(tmp_path):
    body = "for i in range(6):\n    time.sleep(0.25); emit('progress', done=i + 1)\nemit('done')\n"
    t = time.monotonic()
    events, seen = run(tmp_path, body, timeout=0.6)
    assert time.monotonic() - t > 1.2  # longer than the timeout in total, but never silent that long
    assert [e["event"] for e in events] == ["progress"] * 6 + ["done"]
    assert seen == events


def test_silent_runner_is_killed_with_its_children(tmp_path):
    pidfile = tmp_path / "grandchild.pid"
    body = ("import subprocess\n"
            "child = subprocess.Popen(['/bin/sleep', '60'])\n"
            f"open({str(pidfile)!r}, 'w').write(str(child.pid))\n"
            "emit('start')\n"
            "time.sleep(60)\n")
    t = time.monotonic()
    with pytest.raises(EngineTimeout, match="no progress for 1 s"):
        run(tmp_path, body, timeout=1.0)
    assert time.monotonic() - t < 5
    grandchild = int(pidfile.read_text())
    deadline = time.monotonic() + 3
    while alive(grandchild) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not alive(grandchild)


def test_error_event_and_exit_code_are_reported(tmp_path):
    body = "emit('error', message='ValueError: bad request'); sys.exit(1)\n"
    with pytest.raises(EngineError, match="ValueError: bad request"):
        run(tmp_path, body)


def test_crash_without_events_is_reported(tmp_path):
    body = "sys.stderr.write('Traceback: boom\\n'); os._exit(3)\n"
    with pytest.raises(EngineError, match="exit code 3"):
        run(tmp_path, body)
    assert "boom" in (tmp_path / "runner.log").read_text()


def test_non_json_output_stops_the_job(tmp_path):
    body = "print('1/1 [=====] - 0s 50ms/step', flush=True); time.sleep(30)\n"
    t = time.monotonic()
    with pytest.raises(EngineError, match="unexpected output"):
        run(tmp_path, body, timeout=10)
    assert time.monotonic() - t < 5


def test_clean_exit_without_done_event_is_not_success(tmp_path):
    with pytest.raises(EngineError, match="without finishing"):
        run(tmp_path, "emit('start')\n")
