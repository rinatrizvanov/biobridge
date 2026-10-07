"""Layout and accessibility of the results page in real browsers (Chromium and WebKit).

Uses the TEST-ONLY fake engine with a record whose masked and raw scores are exactly
0.00, 0.99, 1.00 and 0.50, the values most likely to collide with the plot edges.
200% zoom is emulated the way browsers lay it out: a 1280-pixel window at 200% zoom
has a 640-CSS-pixel layout viewport at device scale 2.
"""

import pytest
from playwright.sync_api import expect

from tests.web.test_browser import VCF_HEADER, start_server, upload_file  # noqa: F401
from tests.web.conftest import make_manager

pytestmark = pytest.mark.browser

EDGE_VCF = (VCF_HEADER + "chr17\t1000\tedge_values\tC\tT\t.\t.\t.\n"
            "chr17\t2000\tnot_scored:COMPLEX_DELINS\tCC\tTT\t.\t.\t.\n").encode()


@pytest.fixture
def edge_server(tmp_path):
    srv = start_server(make_manager(tmp_path / "Application Support" / "BioBridge"))
    yield srv
    srv.stop()


def results_page(browser, server, tmp_path, **context_args):
    context = browser.new_context(**context_args)
    page = context.new_page()
    page.goto(server.web.auth_url())
    page.get_by_label("VCF or VCF.gz, up to 1 MB").set_input_files(upload_file(tmp_path, "Edge_VCF.vcf", EDGE_VCF))
    page.get_by_label("These coordinates are GRCh38 (hg38).").check()
    page.get_by_role("button", name="Run SpliceAI").click()
    expect(page.get_by_role("heading", name="Results")).to_be_visible(timeout=20_000)
    return context, page


PLOT_GEOMETRY = """() => {
  const svg = document.querySelector('svg.bb-plot');
  const vb = svg.viewBox.baseVal;
  const texts = [...svg.querySelectorAll('text')].map(t => {
    const b = t.getBBox(); const r = t.getBoundingClientRect();
    return {text: t.textContent, x: b.x, y: b.y, w: b.width, h: b.height, px: r.height};
  });
  const dots = [...svg.querySelectorAll('circle')].map(c => {
    const b = c.getBBox(); return {x: b.x, y: b.y, w: b.width, h: b.height};
  });
  return {vb: {w: vb.width, h: vb.height}, texts, dots};
}"""


# Text of a table caption that runs past the visible box of its scrolling wrapper.
CLIPPED_CAPTIONS = """() => [...document.querySelectorAll('.bb-table-wrap')].flatMap(w => {
  const box = w.getBoundingClientRect();
  return [...w.querySelectorAll('caption')].filter(c => {
    const range = document.createRange(); range.selectNodeContents(c);
    return [...range.getClientRects()].some(r => r.right > box.right + 1);
  }).map(c => c.textContent.slice(0, 40));
})"""
VALUES_TABLES_SCROLLING = """() => [...document.querySelectorAll('.bb-table-wrap')]
  .filter(w => w.querySelector('table.bb-events') && w.scrollWidth > w.clientWidth + 1).length"""


def assert_plot_fits(geometry):
    vb = geometry["vb"]
    for t in geometry["texts"]:
        assert t["x"] >= 0 and t["y"] >= 0, f"{t['text']!r} clipped at top/left: {t}"
        assert t["x"] + t["w"] <= vb["w"] and t["y"] + t["h"] <= vb["h"], f"{t['text']!r} clipped: {t}"
    for d in geometry["dots"]:
        assert d["y"] - 2 >= 0 and d["y"] + d["h"] + 2 <= vb["h"]  # including the 2 px ring
    labels = [t for t in geometry["texts"]]
    for i, a in enumerate(labels):  # no two labels overlap
        for b in labels[i + 1:]:
            overlap = (a["x"] < b["x"] + b["w"] and b["x"] < a["x"] + a["w"]
                       and a["y"] < b["y"] + b["h"] and b["y"] < a["y"] + a["h"])
            assert not overlap, f"labels overlap: {a['text']!r} and {b['text']!r}"


def test_values_0_099_and_1_fit_without_clipping_or_overlap(browser, edge_server, tmp_path):
    context, page = results_page(browser, edge_server, tmp_path)
    values = page.locator("svg.bb-plot text.bb-value").all_text_contents()
    assert values == ["0.00", "0.99", "1.00", "0.50"]
    assert_plot_fits(page.evaluate(PLOT_GEOMETRY))
    expect(page.locator(".bb-lede").first).to_contain_text("Edge_VCF.vcf: 2 alleles")  # file name verbatim
    context.close()


@pytest.mark.parametrize("viewport, scale, label", [
    ({"width": 320, "height": 720}, 1, "320 px"),
    ({"width": 375, "height": 760}, 2, "375 px"),
    ({"width": 640, "height": 450}, 2, "200% zoom of a 1280 px window"),
])
def test_narrow_widths_and_200_percent_zoom(browser, edge_server, tmp_path, viewport, scale, label):
    context, page = results_page(browser, edge_server, tmp_path, viewport=viewport, device_scale_factor=scale)
    assert page.evaluate("document.documentElement.scrollWidth") <= viewport["width"], f"{label}: page scrolls sideways"
    geometry = page.evaluate(PLOT_GEOMETRY)
    assert_plot_fits(geometry)
    smallest = min(t["px"] for t in geometry["texts"])
    assert smallest >= 9, f"{label}: smallest chart text renders at {smallest:.1f} px"
    # Wide tables may scroll inside their own box, but their captions must stay readable,
    # and from phone width up the per-variant values table fits without scrolling.
    assert page.evaluate(CLIPPED_CAPTIONS) == [], f"{label}: a table caption is cut off"
    if viewport["width"] >= 375:
        assert page.evaluate(VALUES_TABLES_SCROLLING) == 0, f"{label}: a values table scrolls sideways"
    # The input page as well
    page.goto(page.url.split("/jobs/")[0] + "/")
    assert page.evaluate("document.documentElement.scrollWidth") <= viewport["width"]
    context.close()


def test_keyboard_tooltip_is_inside_the_window_and_dismissible(browser, edge_server, tmp_path):
    context, page = results_page(browser, edge_server, tmp_path, viewport={"width": 900, "height": 700})
    marks = page.locator("svg.bb-plot g.bb-mark")
    marks.first.focus()
    page.keyboard.press("Tab")  # move to the second event by keyboard
    tooltip = page.locator(".bb-tooltip")
    expect(tooltip).to_be_visible()
    expect(tooltip).to_contain_text("Acceptor loss")
    expect(tooltip).to_contain_text("0.99")
    box = tooltip.bounding_box()
    assert box["x"] >= 8 and box["y"] >= 8
    assert box["x"] + box["width"] <= 900 - 8 and box["y"] + box["height"] <= 700 - 8
    stroke = page.evaluate("getComputedStyle(document.activeElement.querySelector('.bb-hit')).stroke")
    assert stroke not in ("none", ""), "focused event has no visible focus outline"
    page.keyboard.press("Escape")
    expect(tooltip).to_be_hidden()
    context.close()


def contrast(fg, bg):
    def lum(rgb):
        c = [v / 255 for v in rgb]
        c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    a, b = sorted((lum(fg), lum(bg)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def rgb(css):
    return [int(float(v)) for v in css[css.index("(") + 1:css.index(")")].split(",")[:3]]


@pytest.mark.parametrize("scheme, surface, bar, dot", [
    ("light", (255, 255, 255), (42, 120, 214), (235, 104, 52)),
    ("dark", (22, 27, 34), (57, 135, 229), (217, 89, 38)),
])
def test_light_and_dark_modes_use_their_own_validated_colours(browser, edge_server, tmp_path,
                                                              scheme, surface, bar, dot):
    context, page = results_page(browser, edge_server, tmp_path, color_scheme=scheme)
    style = page.evaluate("""() => {
      const cs = (sel, prop) => getComputedStyle(document.querySelector(sel))[prop];
      return {svg: cs('svg.bb-plot', 'backgroundColor'), bar: cs('.bb-bar', 'fill'), dot: cs('.bb-dot', 'fill'),
              body: cs('body', 'color'), bodyBg: cs('body', 'backgroundColor'),
              muted: cs('.bb-plot .bb-tick', 'fill'), caption: cs('figcaption', 'color')};
    }""")
    assert tuple(rgb(style["svg"])) == surface
    assert tuple(rgb(style["bar"])) == bar and tuple(rgb(style["dot"])) == dot
    assert contrast(rgb(style["body"]), rgb(style["bodyBg"])) >= 4.5
    assert contrast(rgb(style["muted"]), surface) >= 4.5
    assert contrast(rgb(style["caption"]), rgb(style["bodyBg"])) >= 4.5
    context.close()


LONG_REF = "AATACAGAGTGGTGGGGTGAGATTTTTGTCAACTTGAGGGAGGGAGCTTTACCTTTCTGTCCTGGGATTCTCTTGCTCGCTTTGGACCTTGGCAGCAAACAG"


def test_long_deletions_do_not_widen_the_tables(browser, edge_server, tmp_path):
    vcf = (VCF_HEADER + "chr17\t1000\tedge_values\tC\tT\t.\t.\t.\n"
           f"chr17\t43057000\tlong_deletion\t{LONG_REF}\tA\t.\t.\t.\n").encode()
    context = browser.new_context(viewport={"width": 1280, "height": 900}, accept_downloads=True)
    page = context.new_page()
    page.goto(edge_server.web.auth_url())
    page.get_by_label("VCF or VCF.gz, up to 1 MB").set_input_files(upload_file(tmp_path, "long.vcf", vcf))
    page.get_by_label("These coordinates are GRCh38 (hg38).").check()
    page.get_by_role("button", name="Run SpliceAI").click()
    expect(page.get_by_role("heading", name="Results")).to_be_visible(timeout=20_000)
    overflowing = page.evaluate("""() => [...document.querySelectorAll('.bb-table-wrap')]
        .filter(w => w.scrollWidth > w.clientWidth + 1).length""")
    assert overflowing == 0, "a table needs sideways scrolling at 1280 px"
    assert LONG_REF not in page.locator("main").inner_text()
    expect(page.locator("table.bb-table").first).to_contain_text(f"{LONG_REF[:6]}…({len(LONG_REF)} nt)")
    with page.expect_download() as info:
        page.get_by_role("link", name="Download CSV").click()
    assert LONG_REF in open(info.value.path()).read()  # the CSV keeps the full allele
    context.close()
