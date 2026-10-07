"""Explanations (deterministic, narrow wording) and the four-score plot."""

import re
import xml.etree.ElementTree as ET

import pytest

from biobridge.explain import ABOUT, LIMITATIONS, REASONS, band_sentence, explain, position_phrase
from biobridge.results import EVENTS, Row
from biobridge.web.plot import four_score_svg

FORBIDDEN = re.compile(r"confiden|%|pathogen|benign|likely|exon skipping|upstream|downstream|"
                       r"\bexon \d|\bintron \d|probability of (the )?variant", re.I)


def scored(raw, masked=None, dp=(-20, 1, 36, 1), **kw):
    masked = masked if masked is not None else raw
    return Row(record=1, input_id="v1", chrom="chr17", pos=43057051, ref="C", alt="T", status="SCORED",
               gene="BRCA1", raw=dict(zip(EVENTS, raw)), masked=dict(zip(EVENTS, masked)),
               dp=dict(zip(EVENTS, dp)), **kw)


SCENARIOS = {
    "high": scored((0.0, 0.0, 0.02, 0.99)),
    "masked_zero": scored((0.0, 0.24, 0.01, 0.53), (0.0, 0.0, 0.01, 0.53), dp=(-50, 42, -2, 2)),
    "all_zero": scored((0.0, 0.0, 0.0, 0.0)),
    "below_cutoffs": scored((0.03, 0.0, 0.0, 0.11), dp=(0, 5, -7, 12)),
    "warnings_notes": scored((0.3, 0.0, 0.0, 0.0), warnings=["not left-aligned; left-aligned form chr17:43057012 TG>T"],
                             notes=["also input record 4"]),
}
NOT_SCORED = {code: Row(record=2, input_id=None, chrom="chr17", pos=100, ref="G", alt="A",
                        status="ERROR" if code.startswith(("ENGINE", "UNEXPECTED")) else "NOT_SCORED",
                        reason=code, detail="the GRCh38 reference has T at chr17:100, not G")
              for code in REASONS}


@pytest.mark.parametrize("name", list(SCENARIOS) + [f"genes_{n}" for n in (2,)])
def test_row_explanations_avoid_forbidden_claims(name):
    row = SCENARIOS.get(name, SCENARIOS["high"])
    text = " ".join(explain(row, genes_for_allele=2 if name.startswith("genes_") else 1))
    assert not FORBIDDEN.search(text), text


@pytest.mark.parametrize("code", list(REASONS))
def test_every_reason_has_plain_text_without_forbidden_claims(code):
    text = " ".join(explain(NOT_SCORED[code]))
    assert text.startswith(("Not scored: ", "Error: "))
    assert not FORBIDDEN.search(text), text


def test_fixed_text_carries_the_required_statements():
    about = " ".join(ABOUT)
    # The authors' interpretation is attributed to them, with BioBridge's caveat.
    assert ("The SpliceAI authors write that the largest of the four can be interpreted as the "
            "probability that the variant alters splicing") in about
    assert "not a measurement, and not a chance of disease" in about
    assert "0.2 (high recall), 0.5 (recommended) and 0.8 (high precision)" in about
    # The cutoffs predate masking in the released software (SpliceAI 1.3, October 2019).
    assert "before masking was added to the SpliceAI software (version 1.3, October 2019)" in about
    assert "recommend masked scores for variant interpretation and raw scores" in about
    for phrase in ("exon skipping", "pathogenic or benign", "RNA analysis", "not a diagnostic", "no ACMG"):
        assert phrase in LIMITATIONS


def test_largest_score_sentence_is_exact():
    assert explain(SCENARIOS["high"]) == [
        "The largest masked delta score is 0.99, for donor loss, at chr17:43,057,052, 1 nucleotide after "
        "the variant on the forward strand. This is at or above the 0.8 cutoff (high precision) "
        "characterised in the SpliceAI paper.",
        "Below 0.005 (shown as 0.00, because SpliceAI reports two decimals): acceptor gain, acceptor loss.",
    ]


def test_masked_zero_and_rounded_zero_are_worded_differently():
    text = explain(SCENARIOS["masked_zero"])
    assert ("Acceptor loss: set to 0.00 by SpliceAI's masking; the raw value is 0.24, at chr17:43,057,093, "
            "42 nucleotides after the variant on the forward strand.") in text
    assert "Below 0.005 (shown as 0.00, because SpliceAI reports two decimals): acceptor gain." in text
    assert not any("masking" in t and "acceptor gain" in t for t in text)


def test_all_zero_and_below_cutoff_rows():
    assert explain(SCENARIOS["all_zero"])[0] == "All four masked delta scores are 0.00."
    assert "below the lowest cutoff characterised in the SpliceAI paper, 0.2 (high recall)" in \
        explain(SCENARIOS["below_cutoffs"])[0]


def test_position_phrases():
    row = SCENARIOS["below_cutoffs"]
    assert position_phrase(row, "AG") == "chr17:43,057,051, the variant's own position"
    assert position_phrase(row, "DG") == "chr17:43,057,044, 7 nucleotides before the variant on the forward strand"


@pytest.mark.parametrize("value, cutoff", [(0.2, "0.2 cutoff (high recall)"), (0.5, "0.5 cutoff (recommended)"),
                                           (0.81, "0.8 cutoff (high precision)")])
def test_band_sentences(value, cutoff):
    assert cutoff in band_sentence(value)


def test_warnings_and_duplicate_notes():
    text = explain(SCENARIOS["warnings_notes"], genes_for_allele=2)
    assert "This variant overlaps 2 genes in SpliceAI's annotation; each gene is scored separately." in text
    assert "Not left-aligned; left-aligned form chr17:43057012 TG>T. It was scored as entered." in text
    assert "The same allele also appears as input record 4." in text


def test_not_scored_text_includes_the_detail():
    assert explain(NOT_SCORED["REF_MISMATCH"])[-1] == "Detail: the GRCh38 reference has T at chr17:100, not G."


# --- plot ------------------------------------------------------------------------------
def svg(row):
    out = four_score_svg(row, "p0")
    return out, ET.fromstring(out)


NS = {"s": "http://www.w3.org/2000/svg"}


def test_plot_is_well_formed_accessible_and_token_coloured():
    text, root = svg(SCENARIOS["masked_zero"])
    assert root.find("s:title", NS).text == "Delta scores for chr17:43,057,051 C>T in BRCA1"
    assert "acceptor loss masked 0.00, raw 0.24" in root.find("s:desc", NS).text
    assert not re.search(r"#[0-9a-fA-F]{3,6}\b", text)  # colours come from CSS tokens only
    marks = root.findall(".//s:g[@class='bb-mark']", NS)
    assert [m.get("tabindex") for m in marks] == ["0"] * 4
    assert marks[1].get("aria-label") == "Acceptor loss: masked 0.00, raw 0.24, at chr17:43,057,093"


def test_plot_draws_bars_only_for_positive_masked_values_and_labels_masked_zeros():
    _, root = svg(SCENARIOS["masked_zero"])
    bars = root.findall(".//s:path[@class='bb-bar']", NS)
    dots = root.findall(".//s:circle[@class='bb-dot']", NS)
    labels = [t.text for t in root.findall(".//s:text[@class='bb-value']", NS)]
    assert len(bars) == 2  # DG 0.01 and DL 0.53; AG 0.00 and masked AL have no bar
    assert len(dots) == 4
    assert labels == ["0.00", "masked", "0.01", "0.53"]


def test_reference_lines_and_fixed_axis():
    """Cutoff lines at 0.2/0.5/0.8 on a fixed 0-1 axis; their meaning is in the figure caption."""
    _, root = svg(SCENARIOS["high"])
    ref_lines = root.findall(".//s:line[@class='bb-ref-line']", NS)
    assert len(ref_lines) == 3
    ticks = [t.text for t in root.findall(".//s:text[@class='bb-tick']", NS)]
    assert ticks == ["0.0", "0.2", "0.5", "0.8", "1.0"]
    ys = {t.text: float(t.get("y")) for t in root.findall(".//s:text[@class='bb-tick']", NS)}
    assert ys["0.0"] > ys["0.2"] > ys["0.5"] > ys["0.8"] > ys["1.0"]  # 0 at the bottom, 1 at the top


def test_missing_values_are_not_drawn():
    assert four_score_svg(NOT_SCORED["COMPLEX_DELINS"], "p1") == ""
    none_row = scored((None,) * 4, dp=(None,) * 4)
    assert four_score_svg(none_row, "p2") == ""


# --- geometry: nothing may be clipped at the top or bottom of the plot ----------------
GLYPH_ASCENT = 0.8  # fraction of the font size above the baseline (Latin text)


@pytest.mark.parametrize("values", [(0.0, 0.99, 1.0, 0.5), (1.0, 1.0, 1.0, 1.0), (0.0, 0.0, 0.0, 0.0)])
def test_labels_and_dots_fit_inside_the_plot(values):
    _, root = svg(scored(values))
    width, height = (float(v) for v in root.get("viewBox").split()[2:])
    for text in root.findall(".//s:text", NS):
        size = float(text.get("font-size") or 11)
        y = float(text.get("y"))
        assert y - GLYPH_ASCENT * size >= 0, f"{text.text!r} clipped at the top (y={y})"
        assert y + 0.25 * size <= height, f"{text.text!r} clipped at the bottom (y={y})"
    for dot in root.findall(".//s:circle", NS):
        cy, r = float(dot.get("cy")), float(dot.get("r"))
        assert cy - r - 2 >= 0 and cy + r + 2 <= height  # including the 2 px ring


def test_tied_largest_scores_name_every_event():
    row = scored((0.0, 1.0, 1.0, 0.5), dp=(0, 2, -3, 5))
    first = explain(row)[0]
    assert first.startswith("The largest masked delta score, 1.00, is shared by 2 events: acceptor loss at "
                            "chr17:43,057,053, 2 nucleotides after the variant on the forward strand; donor gain at "
                            "chr17:43,057,048, 3 nucleotides before")
    assert not FORBIDDEN.search(first)
