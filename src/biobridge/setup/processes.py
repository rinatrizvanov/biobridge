"""Child processes that are always cleaned up.

Every child starts in its own session (and so its own process group), so stopping
the group also stops grandchildren, such as the Python processes uv starts.
"""

from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from pathlib import Path


class Cancelled(Exception):
    """Raised when work is abandoned because BioBridge is quitting."""


class ChildProcesses:
    def __init__(self) -> None:
        self._procs: list[subprocess.Popen] = []
        self._lock = threading.Lock()
        self._closing = threading.Event()
        self.spawn_seconds: list[tuple[str, float]] = []

    @property
    def closing(self) -> bool:
        return self._closing.is_set()

    @property
    def pids(self) -> list[int]:
        with self._lock:
            return [p.pid for p in self._procs]

    def spawn(self, args, **kwargs) -> subprocess.Popen:
        with self._lock:
            if self._closing.is_set():
                raise Cancelled("BioBridge is quitting")
            t = time.perf_counter()
            proc = subprocess.Popen([str(a) for a in args], start_new_session=True, **kwargs)
            self.spawn_seconds.append((Path(str(args[0])).name, time.perf_counter() - t))
            self._procs.append(proc)
            return proc

    def sleep(self, seconds: float) -> None:
        """Wait, but give up immediately (raising Cancelled) if BioBridge starts quitting."""
        if self._closing.wait(seconds):
            raise Cancelled("BioBridge is quitting")

    def terminate_all(self, grace: float = 3.0) -> list[int]:
        """Stop every child process group: SIGTERM, then SIGKILL after `grace` seconds.

        Returns the pids of groups that were still running when asked to stop.
        """
        with self._lock:
            self._closing.set()
            procs = list(self._procs)
        running = [p.pid for p in procs if _signal_group(p.pid, signal.SIGTERM)]
        deadline = time.monotonic() + grace
        for p in procs:
            try:
                p.wait(timeout=max(0.0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                pass
        for p in procs:
            # Also reaches grandchildren that outlived their group leader.
            _signal_group(p.pid, signal.SIGKILL)
            try:
                p.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                pass
        return running


def _signal_group(pgid: int, sig: int) -> bool:
    try:
        os.killpg(pgid, sig)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
