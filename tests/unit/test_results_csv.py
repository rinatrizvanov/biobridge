"""Result rows and CSV: NA never 0, masked vs rounded zeros, duplicates, formulas, provenance."""

import csv

import pytest

from biobridge.reports.csv_report import COLUMNS, PROVENANCE_COLUMNS, write_csv
from biobridge.results import cutoff_band, rows_from_results, summarize, zero_kind


def upstream(alt, gene, ds, dp):
    return {"alt": alt, "gene": gene, **{f"DS_{e}": v for e, v in zip(("AG", "AL", "DG", "DL"), ds)},
            **{f"DP_{e}": v for e, v in zip(("AG", "AL", "DG", "DL"), dp)}}


DP = (-20, 1, 36, 1)
RESULTS = {"records": [
    {"index": 0, "id": "scored", "chrom": "chr17", "pos": 1000, "ref": "C", "alts": ["T"], "alleles": [
        {"alt": "T", "status": "SCORED", "genes": [{"gene": "GENE1",
         "raw": upstream("T", "GENE1", (0.0, 0.24, 0.02, 0.99), DP),
         "masked": upstream("T", "GENE1", (0.0, 0.0, 0.02, 0.99), DP)}]}]},
    {"index": 1, "id": "=HYPERLINK(\"http://x\")", "chrom": "chr17", "pos": 2000, "ref": "CC", "alts": ["TT"],
     "alleles": [{"alt": "TT", "status": "NOT_SCORED", "reason": "COMPLEX_DELINS", "genes": [{"gene": "GENE1",
         "raw": upstream("TT", "GENE1", (None,) * 4, (None,) * 4),
         "masked": upstream("TT", "GENE1", (None,) * 4, (None,) * 4)}]}]},
    {"index": 2, "id": None, "chrom": "chr17", "pos": 3000, "ref": "G", "alts": ["A"], "alleles": [
        {"alt": "A", "status": "NOT_SCORED", "reason": "REF_MISMATCH",
         "detail": "the GRCh38 reference has T at chr17:3000, not G"}]},
    {"index": 3, "id": "dup", "chrom": "17", "pos": 1000, "ref": "C", "alts": ["T"], "alleles": [
        {"alt": "T", "status": "SCORED", "genes": [{"gene": "GENE1",
         "raw": upstream("T", "GENE1", (0.0, 0.24, 0.02, 0.99), DP),
         "masked": upstream("T", "GENE1", (0.0, 0.0, 0.02, 0.99), DP)}]}]},
    {"index": 4, "id": "two_genes", "chrom": "chr22", "pos": 500, "ref": "A", "alts": ["G"], "alleles": [
        {"alt": "G", "status": "SCORED", "warnings": [{"code": "NOT_LEFT_ALIGNED", "pos": 498, "ref": "TA", "alt": "T"}],
         "genes": [{"gene": g, "raw": upstream("G", g, (0.1, 0.0, 0.0, 0.0), (5, 0, 0, 0)),
                    "masked": upstream("G", g, (0.1, 0.0, 0.0, 0.0), (5, 0, 0, 0))} for g in ("TXNRD2", "COMT")]}]},
]}
PROVENANCE = {k: f"value-{k}" for k in PROVENANCE_COLUMNS}
PROVENANCE.update(reference_sources={"chr17": "https://ucsc/chr17.fa.gz"}, reference_md5s={"chr17": "023ccefd"})


@pytest.mark.parametrize("raw, masked, kind", [
    (0.24, 0.0, "masked_zero"), (0.0, 0.0, "rounded_zero"), (0.01, 0.0, "masked_zero"),
    (0.5, 0.5, None), (None, None, None),
])
def test_zero_kinds(raw, masked, kind):
    assert zero_kind(raw, masked) == kind


@pytest.mark.parametrize("value, band", [(0.19, "below 0.2"), (0.2, "at or above 0.2"), (0.79, "at or above 0.5"),
                                         (0.8, "at or above 0.8"), (None, None)])
def test_cutoff_bands_are_never_percentages(value, band):
    assert cutoff_band(value) == band


@pytest.fixture
def table(tmp_path):
    rows = rows_from_results(RESULTS)
    path = write_csv(rows, PROVENANCE, tmp_path / "results.csv")
    with path.open() as fh:
        return rows, list(csv.DictReader(fh))


def test_header_and_one_row_per_allele_and_gene(table):
    rows, cells = table
    assert list(cells[0].keys()) == COLUMNS
    # scored, complex, mismatch, two_genes x2 (the duplicate is collapsed)
    assert [(c["input_record"], c["gene_spliceai_annotation"]) for c in cells] == [
        ("1", "GENE1"), ("2", "GENE1"), ("3", "NA"), ("5", "TXNRD2"), ("5", "COMT")]


def test_missing_scores_are_na_never_zero(table):
    _, cells = table
    complex_row, mismatch = cells[1], cells[2]
    for c in (complex_row, mismatch):
        assert all(c[f"DS_{e}_{m}"] == "NA" for e in ("AG", "AL", "DG", "DL") for m in ("masked", "raw"))
        assert c["max_DS_masked"] == "NA" and c["cutoff_band_masked"] == "NA"
        assert c["masked_to_zero"] == "NA" and c["raw_below_0.005"] == "NA"
    assert mismatch["reason"] == "REF_MISMATCH" and "has T" in mismatch["detail"]


def test_masked_and_rounded_zeros_are_named_separately(table):
    _, cells = table
    scored = cells[0]
    assert (scored["DS_AL_raw"], scored["DS_AL_masked"]) == ("0.24", "0.00")
    assert scored["masked_to_zero"] == "AL (raw 0.24)"
    assert scored["raw_below_0.005"] == "AG"
    assert (scored["max_DS_masked"], scored["max_DS_masked_event"], scored["cutoff_band_masked"]) == (
        "0.99", "DL", "at or above 0.8")
    assert cells[3]["masked_to_zero"] == "none"


def test_absolute_positions_and_negative_offsets_stay_numeric(table):
    _, cells = table
    assert (cells[0]["DP_AG"], cells[0]["AG_position"], cells[0]["DL_position"]) == ("-20", "980", "1001")


def test_duplicates_are_collapsed_with_a_note(table):
    rows, cells = table
    assert cells[0]["notes"] == "also input record 4"
    assert summarize(RESULTS, rows)["duplicates_collapsed"] == 1


def test_formula_like_text_is_neutralised(table):
    _, cells = table
    assert cells[1]["input_id"] == "'=HYPERLINK(\"http://x\")"


def test_left_alignment_warning_and_provenance_columns(table):
    _, cells = table
    assert cells[3]["warnings"] == "not left-aligned; left-aligned form chr22:498 TA>T"
    assert cells[0]["engine_lock_sha256"] == "value-engine_lock_sha256"
    assert (cells[0]["reference_source"], cells[0]["reference_md5"]) == ("https://ucsc/chr17.fa.gz", "023ccefd")
    assert cells[3]["reference_md5"] == "NA"  # chr22 provenance not supplied in this fixture


def test_summary_counts_alleles_not_gene_rows():
    rows = rows_from_results(RESULTS)
    summary = summarize(RESULTS, rows)
    assert summary["alleles"] == 5 and summary["rows"] == 5
    assert summary["by_status"] == {"SCORED": 3, "NOT_SCORED": 2}
    assert summary["by_reason"] == {"COMPLEX_DELINS": 1, "REF_MISMATCH": 1}
    assert summary["many_ref_mismatches"] is False
