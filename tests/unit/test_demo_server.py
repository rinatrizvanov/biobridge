"""The spike's result page: token and Host checks, NA for missing values, Quit."""

import http.client
import threading

import pytest

from biobridge.demo_server import ResultServer

SCORES = {"DS_AG": 0.0, "DS_AL": 0.0, "DS_DG": 0.02, "DS_DL": 0.99,
          "DP_AG": -20, "DP_AL": 1, "DP_DG": 36, "DP_DL": 1}
RESULTS = {
    "records": [
        {"chrom": "chr17", "pos": 100, "ref": "C", "alleles": [
            {"alt": "T", "status": "SCORED", "genes": [
                {"gene": "GENE1", "raw": dict(SCORES), "masked": dict(SCORES, DS_DG=None)}]},
            {"alt": "<DEL>", "status": "NOT_SCORED", "reason": "UNSUPPORTED_ALLELE", "genes": []},
        ]},
    ],
    "engine": {"spliceai": "1.3.1", "tensorflow": "2.15.1", "keras": "2.15.0", "python": "3.11",
               "annotation": "grch38", "annotation_sha256": "ab" * 32,
               "models_sha256": {"models/spliceai1.h5": "cd" * 32}},
    "settings": {"distance": 50},
    "reference_md5": {"chr17": "023ccefd298db339159a446e88d742ac"},
}


@pytest.fixture
def server():
    quit_called = threading.Event()
    srv = ResultServer(RESULTS, on_quit=quit_called.set)
    srv.quit_called = quit_called
    yield srv
    srv.close()


def request(srv, method, path, host=None):
    conn = http.client.HTTPConnection("127.0.0.1", srv.port, timeout=5)
    conn.putrequest(method, path, skip_host=True)
    conn.putheader("Host", host or f"127.0.0.1:{srv.port}")
    conn.putheader("Content-Length", "0")
    conn.endheaders()
    resp = conn.getresponse()
    return resp.status, resp.read().decode()


def test_page_requires_token_and_local_host(server):
    assert request(server, "GET", "/")[0] == 403
    assert request(server, "GET", "/?t=wrong")[0] == 403
    assert request(server, "GET", f"/?t={server.token}", host="evil.example:80")[0] == 403
    status, body = request(server, "GET", f"/?t={server.token}")
    assert status == 200
    assert "Not a diagnostic" in body


def test_page_shows_masked_and_raw_and_never_turns_missing_into_zero(server):
    _, body = request(server, "GET", f"/?t={server.token}")
    assert "<td>masked</td>" in body and "<td>raw</td>" in body
    assert "<td>NA</td>" in body  # masked DS_DG is None
    assert "Not scored: UNSUPPORTED_ALLELE" in body
    assert "chr17:101" in body  # DL position = POS + DP


def test_quit_requires_token(server):
    assert request(server, "POST", "/quit")[0] == 403
    assert not server.quit_called.is_set()
    assert request(server, "POST", f"/quit?t={server.token}")[0] == 200
    assert server.quit_called.wait(2)
