"""The BioBridge runner must reproduce the upstream spliceai CLI exactly.

The CLI runs twice (-M 0 and -M 1) against one combined chr17+chr22 FASTA. The
runner runs once against separate per-chromosome FASTA files, switching the
reference as records alternate between chromosomes. For every record, the runner's
raw and masked upstream strings must equal the CLI's INFO values field for field.
The fixture also pins the status each case must get, so it cannot silently lose
its edge cases.

The upstream CLI cannot process the fixture's symbolic <DEL> allele: with pysam
0.24.1 its VCF writer aborts the whole run ("Invalid BCF, the INFO tag id=2 is too
large"). Upstream drops symbolic alleles before scoring anyway, so the CLI gets a
copy of the input with symbolic ALTs removed, and the runner's result for
`T,<DEL>` must equal the CLI's result for `T`. The runner never writes VCF through
upstream code, so it is not affected.
"""

import json
import subprocess

import pytest

pytestmark = pytest.mark.model

FIXTURE = "runner_vs_cli_grch38.vcf"
SET = "grch38-chr17-chr22"

# Record ID -> {alt: (status, reason)}; reason None for SCORED.
EXPECTED_STATUS = {
    "brca1_minus_snv": {"T": ("SCORED", None)},
    "comt_plus_snv": {"A": ("SCORED", None)},
    "brca1_masked_hides_annotated_loss": {"G": ("SCORED", None)},
    "brca1_minus_del2": {"A": ("SCORED", None)},
    "txnrd2_comt_two_genes": {"T": ("SCORED", None)},
    "brca1_minus_ins1": {"GT": ("SCORED", None)},
    "nf1_plus_snv": {"A": ("SCORED", None)},
    "brca1_masked_gain_at_annotated_site": {"C": ("SCORED", None)},
    "nf1_masked_unannotated_loss": {"G": ("SCORED", None)},
    "intergenic": {"T": ("NOT_SCORED", "NOT_IN_SPLICEAI_GENE")},
    "brca1_complex_delins": {"TT": ("NOT_SCORED", "COMPLEX_DELINS")},
    "brca1_ref_mismatch": {"A": ("NOT_SCORED", "REF_MISMATCH")},
    "brca1_symbolic_allele": {"T": ("SCORED", None), "<DEL>": ("NOT_SCORED", "UNSUPPORTED_ALLELE")},
    "comt_multiallelic": {"A": ("SCORED", None), "C": ("SCORED", None)},
    "brca1_star_allele": {"C": ("SCORED", None), "*": ("NOT_SCORED", "UNSUPPORTED_ALLELE")},
    "brca1_deletion_too_long": {"A": ("NOT_SCORED", "DELETION_TOO_LONG")},
}
MASK_CHANGES = {
    "brca1_masked_hides_annotated_loss",
    "brca1_masked_gain_at_annotated_site",
    "nf1_masked_unannotated_loss",
}
DS = ["DS_AG", "DS_AL", "DS_DG", "DS_DL"]


def without_symbolic_alts(src, dest):
    """Copy a VCF, removing symbolic ALT alleles (those the CLI's writer cannot handle)."""
    lines = []
    for line in src.read_text().splitlines():
        if not line.startswith("#"):
            cols = line.split("\t")
            cols[4] = ",".join(a for a in cols[4].split(",") if not a.startswith("<"))
            line = "\t".join(cols)
        lines.append(line)
    dest.write_text("\n".join(lines) + "\n")
    return dest


def cli_info(engine_bin, vcf, fasta, mask, out):
    subprocess.run(
        [engine_bin / "spliceai", "-I", vcf, "-O", out, "-R", fasta, "-A", "grch38",
         "-D", "50", "-M", str(mask)],
        check=True, capture_output=True, text=True,
    )
    rows = []
    for line in out.read_text().splitlines():
        if line.startswith("#"):
            continue
        cols = line.split("\t")
        info = dict(f.split("=", 1) for f in cols[7].split(";") if "=" in f)
        rows.append((cols[2], info["SpliceAI"].split(",") if "SpliceAI" in info else []))
    return rows


def run_runner(engine_bin, runner_script, request, tmp_path, name):
    req_path, out_path = tmp_path / f"{name}.request.json", tmp_path / f"{name}.results.json"
    req_path.write_text(json.dumps(request))
    proc = subprocess.run(
        [engine_bin / "python", runner_script, "score", "--request", req_path, "--out", out_path],
        capture_output=True, text=True,
    )
    events = [json.loads(line) for line in proc.stdout.splitlines()]  # Fails on any non-JSON line.
    assert proc.returncode == 0, proc.stderr[-3000:]
    return events, proc.stderr, json.loads(out_path.read_text())


@pytest.fixture(scope="module")
def comparison(engine_bin, runner_script, reference_set, reference_chromosomes, model_data,
               tmp_path_factory):
    tmp = tmp_path_factory.mktemp("runner_vs_cli")
    vcf = model_data / FIXTURE
    combined = reference_set(SET)
    chroms = reference_chromosomes(SET)
    cli_vcf = without_symbolic_alts(vcf, tmp / "cli_input.vcf")
    cli = {m: cli_info(engine_bin, cli_vcf, combined, m, tmp / f"cli_m{m}.vcf") for m in (0, 1)}
    request = {
        "schema": "biobridge.spliceai.request/1",
        "vcf": str(vcf),
        "annotation": "grch38",
        "distance": 50,
        "reference": {c: str(p) for c, p in chroms.items()},
    }
    events, stderr, results = run_runner(engine_bin, runner_script, request, tmp, "full")
    return {"cli": cli, "events": events, "stderr": stderr, "results": results,
            "request": request, "tmp": tmp}


def test_fixture_switches_chromosomes(comparison):
    chroms = [r["chrom"] for r in comparison["results"]["records"]]
    switches = sum(a != b for a, b in zip(chroms, chroms[1:]))
    assert set(chroms) == {"chr17", "chr22"}
    assert switches >= 4


def test_runner_equals_cli_in_both_mask_modes(comparison):
    records = comparison["results"]["records"]
    for mask, key in ((0, "raw"), (1, "masked")):
        cli_rows = comparison["cli"][mask]
        assert len(cli_rows) == len(records)
        for (cli_id, cli_values), rec in zip(cli_rows, records):
            assert rec["id"] == cli_id
            assert rec["upstream"][key] == cli_values, f"{cli_id} (-M {mask})"


def test_statuses_and_reasons(comparison):
    observed = {}
    for rec in comparison["results"]["records"]:
        observed[rec["id"]] = {a["alt"]: (a["status"], a.get("reason")) for a in rec["alleles"]}
    assert observed == EXPECTED_STATUS


def test_missing_scores_are_none_never_zero(comparison):
    rec = next(r for r in comparison["results"]["records"] if r["id"] == "brca1_complex_delins")
    (allele,) = rec["alleles"]
    assert allele["genes"], "complex delins should still name the overlapping gene"
    for row in allele["genes"]:
        for mode in ("raw", "masked"):
            assert all(row[mode][k] is None for k in DS)


def test_two_gene_overlap_reports_each_gene(comparison):
    rec = next(r for r in comparison["results"]["records"] if r["id"] == "txnrd2_comt_two_genes")
    (allele,) = rec["alleles"]
    assert sorted(g["gene"] for g in allele["genes"]) == ["COMT", "TXNRD2"]


def test_fixture_contains_masked_and_raw_differences(comparison):
    changed = set()
    for rec in comparison["results"]["records"]:
        for allele in rec["alleles"]:
            for row in allele.get("genes", []):
                if any(row["raw"][k] != row["masked"][k] for k in DS):
                    changed.add(rec["id"])
    assert changed == MASK_CHANGES


def test_event_stream_is_structured_and_keras_output_is_in_the_log(comparison):
    events = comparison["events"]
    n = len(comparison["results"]["records"])
    assert events[0] == {"event": "start", "records": n}
    assert [e["done"] for e in events if e["event"] == "progress"] == list(range(1, n + 1))
    assert events[-1]["event"] == "done"
    # Keras predict progress bars were printed, and went to stderr, not the event stream.
    assert "/step" in comparison["stderr"]


def test_missing_reference_chromosome_is_not_scored(comparison, engine_bin, runner_script):
    request = dict(comparison["request"])
    request["reference"] = {"chr17": comparison["request"]["reference"]["chr17"]}
    _, _, results = run_runner(engine_bin, runner_script, request, comparison["tmp"], "chr17_only")
    full = {r["index"]: r for r in comparison["results"]["records"]}
    for rec in results["records"]:
        if rec["chrom"] == "chr22":
            assert {a["status"] for a in rec["alleles"]} == {"NOT_SCORED"}
            assert {a["reason"] for a in rec["alleles"]} == {"CONTIG_NOT_SUPPORTED"}
            assert rec["upstream"] == {"raw": [], "masked": []}
        else:
            assert rec["upstream"] == full[rec["index"]]["upstream"]
            assert rec["alleles"] == full[rec["index"]]["alleles"]


def test_results_record_engine_provenance(comparison):
    engine = comparison["results"]["engine"]
    assert engine["spliceai"] == "1.3.1"
    assert engine["tensorflow"] == "2.15.1"
    assert engine["annotation"] == "grch38"
    assert engine["annotation_sha256"] == (
        "565c0ea83f66b2210182364c3d626fef526229e3d02f444bab247329b6695f2c"
    )
    assert len(engine["models_sha256"]) == 5


def test_no_usable_chromosome_skips_model_and_reports_each_record(
        engine_bin, runner_script, model_data, tmp_path):
    request = {
        "schema": "biobridge.spliceai.request/1",
        "vcf": str(model_data / FIXTURE),
        "distance": 50,
        "reference": {"chr21": str(tmp_path / "unused.fa")},
    }
    events, _, results = run_runner(engine_bin, runner_script, request, tmp_path, "none")
    assert "loading_model" not in [e.get("stage") for e in events]
    assert "model_load_s" not in results["timings"]
    reasons = {a["reason"] for rec in results["records"] for a in rec["alleles"]}
    assert reasons == {"CONTIG_NOT_SUPPORTED"}
    assert len(results["records"]) == len(EXPECTED_STATUS)


MULTI_ALLELIC = {"brca1_symbolic_allele", "comt_multiallelic", "brca1_star_allele"}


def test_multiallelic_alts_are_scored_independently(comparison, engine_bin, runner_script,
                                                    model_data, tmp_path):
    """Each ALT of a multi-allelic record is scored on its own.

    Every ALT must get exactly the status and scores it gets when it is the only ALT,
    so a supported ALT is never blocked or altered by an unsupported sibling
    (symbolic <DEL> or *) or by another supported ALT.
    """
    records = [r for r in comparison["results"]["records"] if r["id"] in MULTI_ALLELIC]
    assert {r["id"] for r in records} == MULTI_ALLELIC
    # The fixture must keep at least one record mixing supported and unsupported ALTs.
    assert any({a["status"] for a in r["alleles"]} == {"SCORED", "NOT_SCORED"} for r in records)

    header = [ln for ln in (model_data / FIXTURE).read_text().splitlines() if ln.startswith("#")]
    body = [f"{r['chrom']}\t{r['pos']}\t{r['id']}:{alt}\t{r['ref']}\t{alt}\t.\t.\t."
            for r in records for alt in r["alts"]]
    split_vcf = tmp_path / "split.vcf"
    split_vcf.write_text("\n".join(header + body) + "\n")
    request = dict(comparison["request"], vcf=str(split_vcf))
    _, _, split = run_runner(engine_bin, runner_script, request, tmp_path, "split")

    alone = {}
    for rec in split["records"]:
        (allele,) = rec["alleles"]
        alone[rec["id"]] = allele
    for rec in records:
        for allele in rec["alleles"]:
            assert alone[f"{rec['id']}:{allele['alt']}"] == allele, f"{rec['id']} ALT {allele['alt']}"
