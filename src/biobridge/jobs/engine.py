"""Run the engine's runner as a subprocess, with a watchdog.

The runner writes one JSON event per line on stdout and logs to stderr. If no event
arrives for `inactivity_timeout` seconds, the runner's whole process group is killed
and the job fails with EngineTimeout, so a hung engine can never hang the app. A
non-JSON line on stdout also stops the job, because the event stream can no longer
be trusted.
"""

from __future__ import annotations

import json
import queue
import subprocess
import threading
from collections.abc import Callable
from pathlib import Path

from biobridge.setup.processes import Cancelled, ChildProcesses

INACTIVITY_TIMEOUT = 300.0


class EngineError(RuntimeError):
    pass


class EngineTimeout(EngineError):
    pass


def run_engine(
    python: Path,
    runner: Path,
    args: list,
    procs: ChildProcesses,
    log_path: Path,
    env: dict[str, str],
    on_event: Callable[[dict], None] = lambda event: None,
    inactivity_timeout: float = INACTIVITY_TIMEOUT,
) -> list[dict]:
    """Run `python runner *args`; return all events, or raise EngineError/EngineTimeout/Cancelled."""
    events: list[dict] = []
    with log_path.open("a") as log:
        proc = procs.spawn([python, runner, *args], env=env, stdin=subprocess.DEVNULL,
                           stdout=subprocess.PIPE, stderr=log, text=True, bufsize=1)
        lines: queue.Queue = queue.Queue()

        def pump():
            assert proc.stdout is not None
            for line in proc.stdout:
                lines.put(line)
            lines.put(None)

        threading.Thread(target=pump, name="engine-events", daemon=True).start()
        while True:
            try:
                line = lines.get(timeout=inactivity_timeout)
            except queue.Empty:
                procs.kill_group(proc)
                raise EngineTimeout(
                    f"The SpliceAI engine made no progress for {inactivity_timeout:.0f} s and was "
                    f"stopped. Details are in {log_path.name}.") from None
            if line is None:
                break
            try:
                event = json.loads(line)
                event["event"]
            except (ValueError, KeyError, TypeError):
                procs.kill_group(proc)
                raise EngineError(f"The SpliceAI engine produced unexpected output: {line[:200]!r}") from None
            events.append(event)
            on_event(event)
        rc = proc.wait()

    if procs.closing:
        raise Cancelled("BioBridge is quitting")
    errors = [e for e in events if e["event"] == "error"]
    if rc != 0 or errors:
        message = errors[-1].get("message") if errors else f"exit code {rc}"
        raise EngineError(f"The SpliceAI engine failed: {message}. Details are in {log_path.name}.")
    if not events or events[-1]["event"] != "done":
        raise EngineError("The SpliceAI engine stopped without finishing.")
    return events
