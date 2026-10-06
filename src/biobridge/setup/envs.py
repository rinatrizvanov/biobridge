"""Create the SpliceAI engine environment with the uv binary bundled in BioBridge.

The environment is built only from the hash-locked requirements, from binary wheels,
with a Python that uv downloads into BioBridge's own folder. Child processes get a
minimal environment (system PATH plus proxy and certificate settings), so Homebrew,
conda, pyenv or a developer's uv configuration cannot leak in.

Network handling: uv retries each request (UV_HTTP_RETRIES) and abandons a stalled
connection after UV_HTTP_TIMEOUT seconds. The whole install is retried with backoff;
wheels finished by an earlier attempt stay in uv's cache, so a retry only fetches
what is still missing. A completion marker records the lock's digest, so an
interrupted install is never mistaken for a finished one.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

from biobridge.setup.processes import Cancelled, ChildProcesses

PYTHON_VERSION = "3.11"
MARKER = ".biobridge-complete"
KEEP_ENV = (
    "HOME", "USER", "LOGNAME", "TMPDIR", "LANG", "LC_ALL", "LC_CTYPE",
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
    "http_proxy", "https_proxy", "all_proxy", "no_proxy",
    "SSL_CERT_FILE", "SSL_CERT_DIR",
)
SMOKE_TEST = (
    "import spliceai.utils, tensorflow as tf; "
    "assert not tf.config.list_physical_devices('GPU'), 'unexpected GPU plugin'"
)


class InstallError(RuntimeError):
    pass


def sanitized_env(base: Path) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k in KEEP_ENV}
    env.update(
        PATH="/usr/bin:/bin:/usr/sbin:/sbin",
        UV_NO_CONFIG="1",
        UV_CACHE_DIR=str(base / "uv-cache"),
        UV_PYTHON_INSTALL_DIR=str(base / "uv-python"),
        UV_HTTP_TIMEOUT="120",
        UV_HTTP_RETRIES="5",
        UV_SYSTEM_CERTS="1",
        UV_NO_PROGRESS="1",
        TF_CPP_MIN_LOG_LEVEL="2",
    )
    return env


def lock_digest(lock: Path) -> str:
    return hashlib.sha256(lock.read_bytes()).hexdigest()


def engine_ready(env_dir: Path, lock: Path) -> bool:
    marker = env_dir / MARKER
    if not (marker.exists() and (env_dir / "bin" / "python").exists()):
        return False
    try:
        return json.loads(marker.read_text()).get("lock_sha256") == lock_digest(lock)
    except (OSError, ValueError):
        return False


def run_streaming(procs: ChildProcesses, args, env: dict[str, str],
                  on_output: Callable[[str], None]) -> int:
    proc = procs.spawn(args, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, text=True, bufsize=1)
    assert proc.stdout is not None
    for line in proc.stdout:
        on_output(line.rstrip())
    return proc.wait()


def install_engine(
    uv: Path,
    lock: Path,
    env_dir: Path,
    base: Path,
    procs: ChildProcesses,
    on_output: Callable[[str], None],
    on_attempt: Callable[[int, int], None],
    attempts: int = 3,
    backoff: tuple[float, ...] = (15.0, 30.0),
    sleep: Callable[[float], None] | None = None,
) -> None:
    """Build the engine environment; raise InstallError after `attempts` failures."""
    sleep = sleep or procs.sleep
    env = sanitized_env(base)
    python = env_dir / "bin" / "python"
    (env_dir / MARKER).unlink(missing_ok=True)

    for attempt in range(1, attempts + 1):
        on_attempt(attempt, attempts)
        rc = run_streaming(procs, [uv, "venv", "--python", PYTHON_VERSION, "--managed-python",
                                   "--clear", env_dir], env, on_output)
        if rc == 0:
            rc = run_streaming(procs, [uv, "pip", "sync", lock, "--python", python,
                                       "--require-hashes", "--no-build", "--compile-bytecode"],
                               env, on_output)
        if procs.closing:
            raise Cancelled("BioBridge is quitting")
        if rc == 0:
            break
        if attempt == attempts:
            raise InstallError(f"engine install failed after {attempts} attempts (exit code {rc})")
        delay = backoff[min(attempt - 1, len(backoff) - 1)]
        on_output(f"Attempt {attempt} failed (exit code {rc}); retrying in {delay:.0f} s")
        sleep(delay)

    # Smoke test and warm-up: the first import in a new environment takes ~20 s
    # (measured in M0), so it is paid here rather than in the user's first job.
    rc = run_streaming(procs, [python, "-W", "ignore", "-c", SMOKE_TEST], env, on_output)
    if procs.closing:
        raise Cancelled("BioBridge is quitting")
    if rc != 0:
        raise InstallError(f"engine smoke test failed (exit code {rc})")
    (env_dir / MARKER).write_text(json.dumps(
        {"lock_sha256": lock_digest(lock), "completed": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    ))
