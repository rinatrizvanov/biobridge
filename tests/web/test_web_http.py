"""HTTP-level tests of the web interface (security, form handling, jobs, CSV).

Real-browser behaviour is covered separately by the Playwright tests.
"""

import csv
import gzip
import io

import pytest
from starlette.testclient import TestClient

from biobridge.inputs.upload import MAX_UPLOAD_BYTES, MAX_VCF_BYTES
from biobridge.setup.processes import alive
from tests.web.conftest import wait_for

ORIGIN = {"origin": "http://testserver"}
VCF_HEADER = "##fileformat=VCFv4.2\n##contig=<ID=chr17>\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"


@pytest.fixture
def web(web_factory):
    return web_factory()


@pytest.fixture
def client(web):
    with TestClient(web.app, base_url="http://testserver", follow_redirects=False) as c:
        r = c.get(f"/auth?t={web.mint_token()}")
        assert r.status_code == 303
        yield c


def submit(client, web, *, variant=None, vcf=None, confirm=True):
    data = {"csrf": web.csrf, "variant": variant or ""}
    if confirm:
        data["confirm_grch38"] = "yes"
    files = {"vcf": ("input.vcf", vcf, "text/plain")} if vcf is not None else None
    return client.post("/jobs", data=data, files=files, headers=ORIGIN)


def finished(client, job_url):
    assert wait_for(lambda: client.get(job_url + "/status").json()["status"] != "running")
    return client.get(job_url + "/status").json()


# --- security ------------------------------------------------------------------------
def test_pages_need_the_session_cookie(web):
    with TestClient(web.app, base_url="http://testserver") as c:
        assert c.get("/").status_code == 403
        assert c.get("/static/app.css").status_code == 403


def test_token_is_one_time_and_sets_a_strict_http_only_cookie(web):
    token = web.mint_token()
    with TestClient(web.app, base_url="http://testserver", follow_redirects=False) as c:
        assert c.get("/auth?t=wrong").status_code == 403
        r = c.get(f"/auth?t={token}")
        assert r.status_code == 303 and r.headers["location"] == "/"
        cookie = r.headers["set-cookie"].lower()
        assert "httponly" in cookie and "samesite=strict" in cookie
        assert c.get("/").status_code == 200
    with TestClient(web.app, base_url="http://testserver") as other:
        assert other.get(f"/auth?t={token}").status_code == 403  # already used


def test_wrong_host_is_rejected(web):
    with TestClient(web.app, base_url="http://evil.example") as c:
        assert c.get(f"/auth?t={web.mint_token()}").status_code == 400


def test_posts_need_matching_origin_and_csrf(client, web):
    data = {"csrf": web.csrf, "variant": "chr17-43057051-C-T", "confirm_grch38": "yes"}
    assert client.post("/jobs", data=data).status_code == 403  # no Origin
    assert client.post("/jobs", data=data, headers={"origin": "http://evil.example"}).status_code == 403
    assert client.post("/jobs", data=dict(data, csrf="nope"), headers=ORIGIN).status_code == 403


def test_security_headers(client):
    r = client.get("/")
    assert "script-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["x-frame-options"] == "DENY"
    # same-origin keeps a real Origin on our own form POSTs; other sites still get no referrer.
    assert r.headers["referrer-policy"] == "same-origin"
    assert "access-control-allow-origin" not in r.headers


# --- form validation -------------------------------------------------------------------
@pytest.mark.parametrize("kwargs, message", [
    ({"variant": "chr17-43057051-C-T", "confirm": False}, "confirm that the coordinates are GRCh38"),
    ({"variant": "chr17-43057051-C-T", "vcf": VCF_HEADER.encode()}, "not both"),
    ({}, "Enter one variant or choose one VCF file"),
    ({"variant": "BRCA1 c.68_69del"}, "Could not read"),
    ({"vcf": b"not a vcf"}, "does not look like a VCF"),
])
def test_input_errors_are_shown_on_the_form(client, web, kwargs, message):
    r = submit(client, web, **kwargs)
    assert r.status_code == 400
    assert message in r.text.replace("&#39;", "'")


def test_oversized_and_bomb_uploads_are_rejected(client, web):
    r = submit(client, web, vcf=b"#" * (MAX_UPLOAD_BYTES + 300_000))
    assert r.status_code == 413
    bomb = gzip.compress((VCF_HEADER + "#" * (MAX_VCF_BYTES * 3)).encode())
    r = submit(client, web, vcf=bomb)
    assert r.status_code == 400 and "expands to more than 5.0 MB" in r.text


# --- jobs ------------------------------------------------------------------------------
def test_pasted_variant_runs_to_results_and_csv(client, web):
    r = submit(client, web, variant="chr17-43057051-C-T")
    assert r.status_code == 303
    job_url = r.headers["location"]
    assert finished(client, job_url)["status"] == "done"
    page = client.get(job_url).text
    assert "MOCK — NOT MODEL OUTPUT" in page
    assert "user_confirmation_only" in page and "cannot verify it" in page
    assert "bb-plot" in page and "Masked delta score (bar)" in page
    csv_response = client.get(job_url + "/results.csv")
    assert csv_response.headers["content-type"].startswith("text/csv")
    assert "attachment" in csv_response.headers["content-disposition"]
    (row,) = list(csv.DictReader(io.StringIO(csv_response.text)))
    assert (row["status"], row["DS_AL_masked"], row["spliceai_version"]) == ("SCORED", "0.62", "MOCK")


def test_uploaded_vcf_shows_unscored_rows_with_reasons_and_masked_zero(client, web):
    vcf = (VCF_HEADER + "chr17\t100\tmasked_zero\tC\tT\t.\t.\t.\n"
           "chr17\t200\tnot_scored:REF_MISMATCH\tG\tA\t.\t.\t.\n").encode()
    job_url = submit(client, web, vcf=vcf).headers["location"]
    assert finished(client, job_url)["status"] == "done"
    page = client.get(job_url).text
    assert "Acceptor loss: set to 0.00 by SpliceAI&#39;s masking; the raw value is 0.24" in page
    assert "Not scored: The reference allele does not match GRCh38" in page
    assert page.count("<td>NA</td>") >= 1


def test_only_one_job_at_a_time_and_cancel_stops_the_engine(client, web):
    vcf = (VCF_HEADER + "chr17\t100\tslow\tC\tT\t.\t.\t.\n").encode()
    job_url = submit(client, web, vcf=vcf).headers["location"]
    job_id = job_url.rsplit("/", 1)[1]
    state = web.manager.get(job_id)
    assert wait_for(lambda: state.procs.pids and state.progress.stage in ("loading_model", "scoring"))
    busy = submit(client, web, variant="chr17-43057051-C-T")
    assert busy.status_code == 409 and "already running" in busy.text
    pids = state.procs.pids
    r = client.post(job_url + "/cancel", data={"csrf": web.csrf}, headers=ORIGIN)
    assert r.status_code == 303
    assert finished(client, job_url)["status"] == "cancelled"
    assert wait_for(lambda: not any(alive(p) for p in pids), timeout=5)
    assert "Cancelled" in client.get(job_url).text


def test_engine_failure_is_reported_not_hidden(client, web):
    vcf = (VCF_HEADER + "chr17\t100\tcrash\tC\tT\t.\t.\t.\n").encode()
    job_url = submit(client, web, vcf=vcf).headers["location"]
    status = finished(client, job_url)
    assert status["status"] == "failed" and "simulated engine crash" in status["error"]
    assert "Could not score this input" in client.get(job_url).text
