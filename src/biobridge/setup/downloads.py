"""Checksum-verified downloads with timeouts, retries and resume.

Standard library only, so the same code serves the app's setup wizard and the
developer scripts. Transient failures (connection errors, stalls, HTTP 408/429/5xx,
truncated transfers, checksum mismatches) are retried with exponential backoff, and
an interrupted transfer resumes from its `.part` file when the server honours HTTP
Range requests. Other HTTP errors (e.g. 404) fail immediately.

TLS certificates are checked against the macOS system trust store via `truststore`,
which also honours institutional root certificates installed in the Keychain. The
Python bundled in the app has no usable default CA file: its OpenSSL looks in the
python.org installer's folder, which most Macs do not have. Without truststore (e.g.
when a developer script runs under the system Python), the default context is used.
"""

from __future__ import annotations

import hashlib
import http.client
import socket
import ssl
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

CHUNK = 1 << 20
RETRYABLE_HTTP = {408, 429, 500, 502, 503, 504}


def tls_context() -> ssl.SSLContext:
    try:
        import truststore
    except ImportError:
        return ssl.create_default_context()
    return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)


class DownloadError(RuntimeError):
    """Raised when a download fails permanently or exhausts its retries."""


def file_digest(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(
    url: str,
    dest: Path,
    *,
    md5: str | None = None,
    sha256: str | None = None,
    timeout: float = 60.0,
    retries: int = 4,
    backoff: float = 2.0,
    progress: Callable[[int, int | None], None] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> Path:
    """Download `url` to `dest` atomically and verify its checksum.

    `timeout` bounds each connect and each read (a stall, not the whole transfer).
    `retries` is the number of additional attempts after the first one.
    `progress(done_bytes, total_bytes_or_None)` is called after every chunk.
    """
    if md5 is None and sha256 is None:
        raise ValueError("a checksum (md5 or sha256) is required")
    algorithm, expected = ("sha256", sha256) if sha256 else ("md5", md5)
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")

    last_error: Exception | None = None
    for attempt in range(retries + 1):
        if attempt:
            sleep(backoff ** (attempt - 1))
        try:
            _transfer(url, part, timeout, progress)
        except urllib.error.HTTPError as exc:
            if exc.code == 416:  # Range not satisfiable: the .part is already complete or stale.
                pass
            elif exc.code in RETRYABLE_HTTP:
                last_error = exc
                continue
            else:
                raise DownloadError(f"{url}: HTTP {exc.code} {exc.reason}") from exc
        except (urllib.error.URLError, http.client.HTTPException, socket.timeout,
                TimeoutError, ConnectionError) as exc:
            last_error = exc
            continue

        actual = file_digest(part, algorithm)
        if actual == expected:
            part.replace(dest)
            return dest
        part.unlink()
        last_error = DownloadError(f"{url}: {algorithm} mismatch, expected {expected}, got {actual}")

    raise DownloadError(f"{url}: failed after {retries + 1} attempts: {last_error}") from last_error


def _transfer(url: str, part: Path, timeout: float,
              progress: Callable[[int, int | None], None] | None) -> None:
    have = part.stat().st_size if part.exists() else 0
    request = urllib.request.Request(url, headers={"Range": f"bytes={have}-"} if have else {})
    with urllib.request.urlopen(request, timeout=timeout, context=tls_context()) as resp:
        if have and resp.status != 206:
            have = 0  # Server ignored the Range header; start over.
        length = resp.headers.get("Content-Length")
        total = have + int(length) if length is not None else None
        done = have
        with part.open("ab" if have else "wb") as out:
            # read1 returns whatever has arrived, so bytes received before a stall
            # reach the .part file and the next attempt can resume from them.
            while chunk := resp.read1(CHUNK):
                out.write(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
    if total is not None and done < total:
        raise http.client.IncompleteRead(b"", total - done)
