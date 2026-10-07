"""Real-browser tests (Playwright, Chromium and WebKit) of the web interface.

The fast suite uses the TEST-ONLY fake engine, whose results must show the MOCK
watermark. One test drives the real SpliceAI engine (also marked `model`).
"""

import csv
import gzip
import os
import socket
import time
from pathlib import Path

import pytest
from playwright.sync_api import expect

from biobridge.genome import HG38_MD5
from biobridge.inputs.upload import MAX_VCF_BYTES
from biobridge.setup.processes import alive
from biobridge.web.app import BioBridgeWeb
from biobridge.web.jobs import JobManager
from biobridge.web.server import WebServer
from tests.web.conftest import make_manager, wait_for

pytestmark = pytest.mark.browser
VCF_HEADER = "##fileformat=VCFv4.2\n##contig=<ID=chr17>\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"


def start_server(manager: JobManager) -> WebServer:
    server = WebServer(lambda host: BioBridgeWeb(manager, host)).start()
    assert wait_for(lambda: socket.socket().connect_ex(("127.0.0.1", server.port)) == 0, timeout=10)
    return server


@pytest.fixture
def server(tmp_path):
    srv = start_server(make_manager(tmp_path / "Application Support" / "BioBridge"))
    yield srv
    srv.stop()


@pytest.fixture
def page(browser, server):
    context = browser.new_context(accept_downloads=True)
    pg = context.new_page()
    pg.goto(server.web.auth_url())
    expect(pg.get_by_role("heading", name="Score variants with SpliceAI")).to_be_visible()
    yield pg
    context.close()


def upload_file(tmp_path, name, content: bytes) -> Path:
    path = tmp_path / name
    path.write_bytes(content)
    return path


def test_confirmation_is_required_before_running(page):
    page.get_by_label("GRCh38 position and alleles").fill("chr17-43057051-C-T")
    page.get_by_role("button", name="Run SpliceAI").click()
    expect(page).to_have_url(page.url)  # the browser blocks submission of the form
    assert page.locator("#confirm").evaluate("el => !el.checkValidity()")
    assert "/jobs/" not in page.url


def test_pasted_variant_shows_progress_then_results_plot_and_tooltip(page):
    page.get_by_label("GRCh38 position and alleles").fill("chr17-43057051-C-T")
    page.get_by_label("These coordinates are GRCh38 (hg38).").check()
    page.get_by_role("button", name="Run SpliceAI").click()
    expect(page.get_by_role("heading", name="Results")).to_be_visible(timeout=20_000)
    expect(page.get_by_text("MOCK — NOT MODEL OUTPUT")).to_be_visible()
    expect(page.get_by_text("cannot verify it")).to_be_visible()

    plot = page.locator("svg.bb-plot").first
    expect(plot).to_be_visible()
    expect(plot.locator("g.bb-mark")).to_have_count(4)
    expect(page.get_by_text("Masked delta score (bar)")).to_be_visible()
    plot.locator("g.bb-mark").nth(1).hover()
    tooltip = page.locator(".bb-tooltip")
    expect(tooltip).to_be_visible()
    expect(tooltip).to_contain_text("Acceptor loss")
    expect(tooltip).to_contain_text("0.62")
    # Keyboard focus shows the same tooltip.
    page.mouse.move(0, 0)
    plot.locator("g.bb-mark").nth(3).focus()
    expect(tooltip).to_contain_text("Donor loss")


def test_uploaded_vcf_shows_reasons_na_and_masked_zero(page, tmp_path):
    vcf = upload_file(tmp_path, "variants.vcf", (VCF_HEADER + "chr17\t100\tmasked_zero\tC\tT\t.\t.\t.\n"
                                                 "chr17\t200\tnot_scored:REF_MISMATCH\tG\tA\t.\t.\t.\n").encode())
    page.get_by_label("VCF or VCF.gz, up to 1 MB").set_input_files(vcf)
    page.get_by_label("These coordinates are GRCh38 (hg38).").check()
    page.get_by_role("button", name="Run SpliceAI").click()
    expect(page.get_by_role("heading", name="Results")).to_be_visible(timeout=20_000)
    table = page.locator("table.bb-table").first
    expect(table.locator("tbody tr")).to_have_count(2)
    expect(table.locator("tbody tr").nth(1)).to_contain_text("Not scored")
    expect(table.locator("tbody tr").nth(1)).to_contain_text("NA")
    expect(page.get_by_text("The reference allele does not match GRCh38")).to_be_visible()
    expect(page.get_by_text("Acceptor loss: set to 0.00 by SpliceAI's masking; the raw value is 0.24",
                            exact=False)).to_be_visible()
    expect(page.locator("svg.bb-plot text.bb-value", has_text="masked")).to_have_count(1)


def test_csv_download_content(page):
    page.get_by_label("GRCh38 position and alleles").fill("chr17:43057051 C>T")
    page.get_by_label("These coordinates are GRCh38 (hg38).").check()
    page.get_by_role("button", name="Run SpliceAI").click()
    expect(page.get_by_role("heading", name="Results")).to_be_visible(timeout=20_000)
    with page.expect_download() as info:
        page.get_by_role("link", name="Download CSV").click()
    download = info.value
    assert download.suggested_filename.startswith("biobridge-") and download.suggested_filename.endswith(".csv")
    rows = list(csv.DictReader(open(download.path())))
    assert len(rows) == 1 and rows[0]["build_basis"] == "user_confirmation_only"
    assert rows[0]["spliceai_version"] == "MOCK"


def test_decompressed_size_limit_message(page, tmp_path):
    bomb = upload_file(tmp_path, "bomb.vcf.gz", gzip.compress((VCF_HEADER + "#" * (MAX_VCF_BYTES * 3)).encode()))
    page.get_by_label("VCF or VCF.gz, up to 1 MB").set_input_files(bomb)
    page.get_by_label("These coordinates are GRCh38 (hg38).").check()
    page.get_by_role("button", name="Run SpliceAI").click()
    expect(page.get_by_role("alert")).to_contain_text("expands to more than 5.0 MB")


def test_cancel_stops_the_engine(page, server, tmp_path):
    vcf = upload_file(tmp_path, "slow.vcf", (VCF_HEADER + "chr17\t100\tslow\tC\tT\t.\t.\t.\n").encode())
    page.get_by_label("VCF or VCF.gz, up to 1 MB").set_input_files(vcf)
    page.get_by_label("These coordinates are GRCh38 (hg38).").check()
    page.get_by_role("button", name="Run SpliceAI").click()
    expect(page.get_by_role("heading", name="Scoring…")).to_be_visible()
    expect(page.locator("#bb-progress-text")).to_contain_text("Scored 0 of 1", timeout=10_000)
    state = server.web.manager.current
    pids = state.procs.pids
    assert pids
    page.get_by_role("button", name="Cancel").click()
    expect(page.get_by_role("heading", name="Cancelled")).to_be_visible(timeout=10_000)
    assert wait_for(lambda: not any(alive(p) for p in pids), timeout=5)


def test_no_page_level_horizontal_scroll_at_phone_width(browser, server):
    context = browser.new_context(viewport={"width": 375, "height": 800})
    pg = context.new_page()
    pg.goto(server.web.auth_url())
    width = pg.evaluate("document.documentElement.scrollWidth")
    assert width <= 375
    pg.get_by_label("GRCh38 position and alleles").fill("chr17-43057051-C-T")
    pg.get_by_label("These coordinates are GRCh38 (hg38).").check()
    pg.get_by_role("button", name="Run SpliceAI").click()
    expect(pg.get_by_role("heading", name="Results")).to_be_visible(timeout=20_000)
    assert pg.evaluate("document.documentElement.scrollWidth") <= 375  # the wide table scrolls inside its box
    context.close()


# --- one run with the real SpliceAI engine ---------------------------------------------
@pytest.mark.model
def test_real_engine_end_to_end_in_the_browser(browser, tmp_path, engine_bin, reference_chromosomes):
    base = tmp_path / "Application Support" / "BioBridge"
    ref = base / "data" / "reference" / "hg38"
    ref.mkdir(parents=True)
    os.symlink(reference_chromosomes("grch38-chr17-chr22")["chr17"], ref / "chr17.fa")
    (ref / "chr17.fa.md5").write_text(HG38_MD5["chr17"])
    manager = JobManager(base, engine_env=engine_bin.parent, license_acknowledgment=lambda: "test run")
    server = start_server(manager)
    context = browser.new_context(accept_downloads=True)
    try:
        pg = context.new_page()
        pg.goto(server.web.auth_url())
        pg.get_by_label("GRCh38 position and alleles").fill("chr17-43057051-C-T")
        pg.get_by_label("These coordinates are GRCh38 (hg38).").check()
        t = time.monotonic()
        pg.get_by_role("button", name="Run SpliceAI").click()
        expect(pg.get_by_role("heading", name="Results")).to_be_visible(timeout=120_000)
        expect(pg.get_by_text("MOCK")).to_have_count(0)
        expect(pg.get_by_text("The largest masked delta score is 0.99, for donor loss", exact=False)).to_be_visible()
        with pg.expect_download() as info:
            pg.get_by_role("link", name="Download CSV").click()
        (row,) = list(csv.DictReader(open(info.value.path())))
        assert (row["spliceai_version"], row["DS_DL_masked"], row["gene_spliceai_annotation"]) == ("1.3.1", "0.99", "BRCA1")
        print(f"real-engine browser run ({browser.browser_type.name}): {time.monotonic() - t:.1f} s from click to results")
    finally:
        context.close()
        server.stop()
