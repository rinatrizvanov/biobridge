"""Timeout, retry, resume and checksum behaviour of biobridge.setup.downloads.

A local HTTP server replays a scripted sequence of behaviours, one per request.
"""

import hashlib
import http.server
import threading
import time

import pytest

from biobridge.setup.downloads import DownloadError, download

PAYLOAD = bytes(range(256)) * 4096  # 1 MiB
MD5 = hashlib.md5(PAYLOAD).hexdigest()


class ScriptedHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        server = self.server
        server.requests.append(self.headers.get("Range"))
        behaviour = server.script.pop(0) if server.script else "ok"
        if behaviour in ("404", "503"):
            self.send_error(int(behaviour))
            return

        start = 0
        rng = self.headers.get("Range")
        if rng and behaviour != "ignore_range":
            start = int(rng.removeprefix("bytes=").rstrip("-"))
            self.send_response(206)
        else:
            self.send_response(200)
        body = PAYLOAD[start:]
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()

        if behaviour == "truncate":
            self.wfile.write(body[: len(body) // 3])
            self.wfile.flush()
            self.close_connection = True
        elif behaviour == "stall":
            self.wfile.write(body[:1000])
            self.wfile.flush()
            time.sleep(1.5)
        else:
            self.wfile.write(body)


@pytest.fixture
def server():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), ScriptedHandler)
    srv.daemon_threads = True
    srv.block_on_close = False
    srv.script, srv.requests = [], []
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    srv.url = f"http://127.0.0.1:{srv.server_address[1]}/file.bin"
    yield srv
    srv.shutdown()
    srv.server_close()


@pytest.fixture
def sleeps():
    calls = []
    return calls


def fetch(server, tmp_path, sleeps, **kwargs):
    kwargs.setdefault("md5", MD5)
    return download(server.url, tmp_path / "file.bin", sleep=sleeps.append, **kwargs)


def test_downloads_and_verifies(server, tmp_path, sleeps):
    path = fetch(server, tmp_path, sleeps)
    assert path.read_bytes() == PAYLOAD
    assert not (tmp_path / "file.bin.part").exists()
    assert sleeps == []


def test_retries_transient_http_error(server, tmp_path, sleeps):
    server.script = ["503", "ok"]
    assert fetch(server, tmp_path, sleeps).read_bytes() == PAYLOAD
    assert len(server.requests) == 2
    assert sleeps == [1.0]


def test_resumes_truncated_transfer_with_range(server, tmp_path, sleeps):
    server.script = ["truncate", "ok"]
    assert fetch(server, tmp_path, sleeps).read_bytes() == PAYLOAD
    assert server.requests[0] is None
    assert server.requests[1] == f"bytes={len(PAYLOAD) // 3}-"


def test_restarts_when_server_ignores_range(server, tmp_path, sleeps):
    server.script = ["truncate", "ignore_range"]
    assert fetch(server, tmp_path, sleeps).read_bytes() == PAYLOAD


def test_stalled_transfer_times_out_and_resumes(server, tmp_path, sleeps):
    server.script = ["stall", "ok"]
    assert fetch(server, tmp_path, sleeps, timeout=0.5).read_bytes() == PAYLOAD
    assert server.requests[1] == "bytes=1000-"


def test_checksum_mismatch_fails_and_leaves_no_file(server, tmp_path, sleeps):
    with pytest.raises(DownloadError, match="md5 mismatch"):
        fetch(server, tmp_path, sleeps, md5="0" * 32, retries=1)
    assert len(server.requests) == 2
    assert not (tmp_path / "file.bin").exists()
    assert not (tmp_path / "file.bin.part").exists()


def test_not_found_fails_immediately(server, tmp_path, sleeps):
    server.script = ["404"]
    with pytest.raises(DownloadError, match="HTTP 404"):
        fetch(server, tmp_path, sleeps)
    assert len(server.requests) == 1


def test_gives_up_after_retries_with_backoff(server, tmp_path, sleeps):
    server.script = ["503"] * 3
    with pytest.raises(DownloadError, match="failed after 3 attempts"):
        fetch(server, tmp_path, sleeps, retries=2)
    assert sleeps == [1.0, 2.0]


def test_requires_a_checksum(tmp_path):
    with pytest.raises(ValueError):
        download("http://127.0.0.1/x", tmp_path / "x")


def test_tls_uses_the_macos_trust_store_and_verifies_certificates():
    import ssl

    import truststore

    from biobridge.setup.downloads import tls_context

    ctx = tls_context()
    assert isinstance(ctx, truststore.SSLContext)
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert ctx.check_hostname
