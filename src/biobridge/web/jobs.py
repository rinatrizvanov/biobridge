"""Runs one scoring job at a time in the background, with progress and Cancel."""

from __future__ import annotations

import logging
import secrets
import threading
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from biobridge import paths
from biobridge.inputs.text import InputError
from biobridge.jobs.engine import INACTIVITY_TIMEOUT, EngineError
from biobridge.jobs.job import JobRequest, JobResult, Progress, run_job
from biobridge.setup.processes import Cancelled, ChildProcesses
from biobridge.setup.reference import ensure_chromosome

log = logging.getLogger("biobridge.web")


class Busy(Exception):
    """Another job is still running."""


@dataclass
class JobState:
    id: str
    status: str = "running"  # running, done, failed or cancelled
    progress: Progress = field(default_factory=lambda: Progress("input", "Starting…"))
    error: str | None = None
    result: JobResult | None = None
    started: float = field(default_factory=time.monotonic)
    cancel: threading.Event = field(default_factory=threading.Event)
    procs: ChildProcesses = field(default_factory=ChildProcesses)


class JobManager:
    def __init__(self, base: Path, engine_env: Path, license_acknowledgment: Callable[[], str],
                 runner: Path = paths.RUNNER, python: Path | None = None,
                 reference_provider: Callable = ensure_chromosome,
                 inactivity_timeout: float = INACTIVITY_TIMEOUT,
                 on_running: Callable[[bool], None] = lambda running: None) -> None:
        self.base, self.engine_env = base, engine_env
        self.license_acknowledgment = license_acknowledgment
        self.runner, self.python, self.reference_provider = runner, python, reference_provider
        self.inactivity_timeout = inactivity_timeout
        self.on_running = on_running
        self.jobs: dict[str, JobState] = {}
        self.current: JobState | None = None
        self._lock = threading.Lock()

    def submit(self, request: JobRequest) -> JobState:
        with self._lock:
            if self.current and self.current.status == "running":
                raise Busy()
            state = JobState(id=secrets.token_hex(8))
            self.jobs[state.id] = state
            self.current = state
        threading.Thread(target=self._run, args=(state, request), name=f"job-{state.id}", daemon=True).start()
        return state

    def get(self, job_id: str) -> JobState | None:
        return self.jobs.get(job_id)

    def cancel(self, job_id: str) -> None:
        state = self.jobs.get(job_id)
        if state and state.status == "running":
            state.cancel.set()
            state.procs.terminate_all()  # stops the engine's whole process group

    def shutdown(self) -> None:
        if self.current:
            self.cancel(self.current.id)

    def _run(self, state: JobState, request: JobRequest) -> None:
        def on_status(progress: Progress) -> None:
            state.progress = progress

        self.on_running(True)
        try:
            state.result = run_job(
                request, self.base, self.engine_env, state.procs, on_status=on_status,
                license_acknowledgment=self.license_acknowledgment(), cancel=state.cancel,
                runner=self.runner, python=self.python, reference_provider=self.reference_provider,
                inactivity_timeout=self.inactivity_timeout)
            state.status = "done"
        except Cancelled:
            state.status = "cancelled"
        except (InputError, EngineError) as exc:
            state.status, state.error = ("cancelled", None) if state.cancel.is_set() else ("failed", str(exc))
        except Exception as exc:  # Never leave a job "running" forever.
            log.error("job %s failed: %s", state.id, traceback.format_exc())
            state.status = "cancelled" if state.cancel.is_set() else "failed"
            state.error = None if state.cancel.is_set() else f"Unexpected error: {type(exc).__name__}: {exc}"
        finally:
            self.on_running(False)
