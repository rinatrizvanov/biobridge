"""Quit must leave no child or grandchild processes behind."""

import threading
import time

import pytest

from biobridge.setup.processes import Cancelled, ChildProcesses, alive


def wait_for(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return predicate()


def spawn_with_grandchild(procs, tmp_path, ignore_term=False):
    pidfile = tmp_path / "grandchild.pid"
    trap = "trap '' TERM; " if ignore_term else ""
    proc = procs.spawn(["/bin/sh", "-c", f"{trap}sleep 60 & echo $! > '{pidfile}'; wait"])
    assert wait_for(lambda: pidfile.exists() and pidfile.read_text().strip())
    return proc, int(pidfile.read_text())


def test_terminate_all_stops_children_and_grandchildren(tmp_path):
    procs = ChildProcesses()
    proc, grandchild = spawn_with_grandchild(procs, tmp_path)
    assert alive(proc.pid) and alive(grandchild)

    assert procs.terminate_all(grace=2.0) == [proc.pid]
    assert proc.poll() is not None
    assert wait_for(lambda: not alive(grandchild))


def test_processes_ignoring_sigterm_are_killed_after_grace(tmp_path):
    procs = ChildProcesses()
    proc, grandchild = spawn_with_grandchild(procs, tmp_path, ignore_term=True)
    t = time.monotonic()
    procs.terminate_all(grace=0.5)
    assert time.monotonic() - t < 3.0
    assert proc.poll() is not None
    assert wait_for(lambda: not alive(grandchild))


def test_no_new_children_after_quit():
    procs = ChildProcesses()
    procs.terminate_all()
    with pytest.raises(Cancelled):
        procs.spawn(["/bin/sleep", "60"])


def test_backoff_sleep_ends_when_quitting():
    procs = ChildProcesses()
    threading.Timer(0.2, procs.terminate_all).start()
    t = time.monotonic()
    with pytest.raises(Cancelled):
        procs.sleep(30)
    assert time.monotonic() - t < 2.0
