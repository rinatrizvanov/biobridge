"""Runner validation through the real engine: inspect, allele checks, REF details,
left alignment, and chromosome ends on a synthetic contig."""

import json
import random
import subprocess

import pytest

from tests.model.test_runner_matches_cli import run_runner

pytestmark = pytest.mark.model

HEADER = "##fileformat=VCFv4.2\n##contig=<ID=chr17>\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"


def score(engine_bin, runner_script, tmp_path, vcf_text, reference, annotation="grch38", name="job"):
    vcf = tmp_path / f"{name}.vcf"
    vcf.write_text(vcf_text)
    request = {"schema": "biobridge.spliceai.request/1", "vcf": str(vcf), "annotation": annotation,
               "distance": 50, "reference": {c: str(p) for c, p in reference.items()}}
    _, _, results = run_runner(engine_bin, runner_script, request, tmp_path, name)
    return {r["id"]: r for r in results["records"]}, results


def inspect(engine_bin, runner_script, tmp_path, vcf_path):
    out = tmp_path / "inspect.json"
    proc = subprocess.run([engine_bin / "python", runner_script, "inspect", "--vcf", vcf_path, "--out", out],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert all(json.loads(line)["event"] for line in proc.stdout.splitlines())
    return json.loads(out.read_text())


@pytest.fixture(scope="module")
def chr17(reference_chromosomes):
    return {"chr17": reference_chromosomes("grch38-chr17-chr22")["chr17"]}


# --- inspect ---------------------------------------------------------------------------
def test_inspect_reports_header_and_records(engine_bin, runner_script, model_data, tmp_path):
    info = inspect(engine_bin, runner_script, tmp_path, model_data / "runner_vs_cli_grch38.vcf")
    assert info["error"] is None
    assert info["contigs"] == {"chr17": 83257441, "chr22": 50818468}
    assert any("GRCh38" in v for v in info["meta"]["reference"])
    assert info["samples"] == 0
    assert len(info["records"]) == 16
    assert info["records"][12]["alts"] == ["T", "<DEL>"]


def test_inspect_reports_unreadable_records(engine_bin, runner_script, tmp_path):
    bad = tmp_path / "bad.vcf"
    bad.write_text(HEADER + "chr17\t100\t.\tA\tG\t.\t.\t.\nchr17\tnot_a_number\t.\tA\tG\t.\t.\t.\n")
    info = inspect(engine_bin, runner_script, tmp_path, bad)
    assert len(info["records"]) == 1
    assert info["error"].startswith("data record 2 could not be read")


# --- allele checks, REF details, left alignment ------------------------------------------
@pytest.fixture(scope="module")
def checks(engine_bin, runner_script, chr17, tmp_path_factory):
    rows = [
        ("ref_mismatch", 43057055, "G", "A"),
        ("iupac_alt", 43057051, "C", "T,R"),
        ("lowercase_ref", 43057051, "c", "T"),
        ("no_alt", 43057051, "C", "."),
        ("del_right_shifted", 43057015, "GG", "G"),
        ("ins_right_shifted", 43057016, "G", "GG"),
        ("del_left_aligned", 43057012, "TG", "T"),
        ("snv_alone", 43057051, "C", "T"),
    ]
    body = "".join(f"chr17\t{pos}\t{rid}\t{ref}\t{alt}\t.\t.\t.\n" for rid, pos, ref, alt in rows)
    records, _ = score(engine_bin, runner_script, tmp_path_factory.mktemp("checks"), HEADER + body, chr17)
    return records


def alleles(record):
    return {a["alt"]: a for a in record["alleles"]}


def test_ref_mismatch_names_the_expected_bases(checks):
    (allele,) = checks["ref_mismatch"]["alleles"]
    assert (allele["status"], allele["reason"]) == ("NOT_SCORED", "REF_MISMATCH")
    assert allele["detail"] == "the GRCh38 reference has T at chr17:43057055, not G"


def test_iupac_alt_is_invalid_and_does_not_affect_its_sibling(checks):
    a = alleles(checks["iupac_alt"])
    assert (a["R"]["status"], a["R"]["reason"]) == ("NOT_SCORED", "INVALID_INPUT")
    assert "genes" not in a["R"]  # upstream's numbers for "R" are meaningless and are dropped
    assert a["T"] == alleles(checks["snv_alone"])["T"]


def test_lowercase_ref_and_missing_alt_are_invalid_input(checks):
    assert [(a["status"], a["reason"]) for a in checks["lowercase_ref"]["alleles"]] == [("NOT_SCORED", "INVALID_INPUT")]
    assert checks["lowercase_ref"]["upstream"] == {"raw": [], "masked": []}  # never sent to upstream
    (allele,) = checks["no_alt"]["alleles"]
    assert allele["reason"] == "INVALID_INPUT" and "no ALT" in allele["detail"]


def test_right_shifted_indels_get_a_left_alignment_warning_but_are_scored(checks):
    # chr17:43,057,010-19 reads G G T G G G G T G A: a GGGG run at 43,057,013-16 after a T.
    deletion = checks["del_right_shifted"]["alleles"][0]
    assert deletion["status"] == "SCORED"
    assert deletion["warnings"] == [{"code": "NOT_LEFT_ALIGNED", "pos": 43057012, "ref": "TG", "alt": "T"}]
    insertion = checks["ins_right_shifted"]["alleles"][0]
    assert insertion["warnings"] == [{"code": "NOT_LEFT_ALIGNED", "pos": 43057012, "ref": "T", "alt": "TG"}]
    assert "warnings" not in checks["del_left_aligned"]["alleles"][0]


# --- chromosome ends: synthetic contig with a custom annotation -------------------------
CONTIG_LENGTH = 20_000


@pytest.fixture(scope="module")
def synthetic(tmp_path_factory):
    """A 20 kb synthetic 'chr21' and a SpliceAI-format annotation whose one gene spans
    beyond both ends. Scores on synthetic sequence are only used to check statuses."""
    tmp = tmp_path_factory.mktemp("synthetic")
    rng = random.Random(20261006)
    seq = "".join(rng.choice("ACGT") for _ in range(CONTIG_LENGTH))
    fasta = tmp / "synthetic chr21.fa"  # a space in the path, like "Application Support"
    fasta.write_text(">chr21\n" + "\n".join(seq[i:i + 60] for i in range(0, CONTIG_LENGTH, 60)) + "\n")
    annotation = tmp / "synthetic_annotation.txt"
    annotation.write_text("#NAME\tCHROM\tSTRAND\tTX_START\tTX_END\tEXON_START\tEXON_END\n"
                          "SYNTH1\t21\t+\t0\t30000\t0,8000,15000,\t2000,8200,30000,\n")
    variants = [("near_start", 100), ("near_end", 19_950), ("middle", 10_000), ("past_end", 25_000)]
    body = "".join(f"chr21\t{pos}\t{rid}\t{seq[pos - 1] if pos <= CONTIG_LENGTH else 'A'}\t"
                   f"{'G' if pos > CONTIG_LENGTH or seq[pos - 1] != 'G' else 'A'}\t.\t.\t.\n"
                   for rid, pos in variants)
    vcf_text = "##fileformat=VCFv4.2\n##contig=<ID=chr21>\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n" + body
    return {"tmp": tmp, "fasta": fasta, "annotation": annotation, "vcf_text": vcf_text}


def test_chromosome_ends_through_real_upstream_code(engine_bin, runner_script, synthetic):
    records, results = score(engine_bin, runner_script, synthetic["tmp"], synthetic["vcf_text"],
                             {"chr21": synthetic["fasta"]}, annotation=str(synthetic["annotation"]),
                             name="ends")
    status = {rid: [(a["status"], a.get("reason")) for a in r["alleles"]] for rid, r in records.items()}
    assert status == {
        "near_start": [("NOT_SCORED", "NEAR_CONTIG_END")],
        "near_end": [("NOT_SCORED", "NEAR_CONTIG_END")],
        "middle": [("SCORED", None)],
        "past_end": [("NOT_SCORED", "INVALID_INPUT")],
    }
    # Upstream warns differently at the two ends; BioBridge reports both as NEAR_CONTIG_END.
    assert any(w.startswith("Skipping record (ref issue)") for w in records["near_start"]["warnings"])
    assert any(w.startswith("Skipping record (near chromosome end)") for w in records["near_end"]["warnings"])
    assert "start of the chromosome" in records["near_start"]["alleles"][0]["detail"]
    assert "within 5 kb of a chromosome end" in records["near_end"]["alleles"][0]["detail"]
    assert records["past_end"]["alleles"][0]["detail"] == (
        "position 25,000 is beyond the end of chr21 (20,000 bases in the reference)")
    # Provenance records the custom annotation file's digest.
    assert len(results["engine"]["annotation_sha256"]) == 64


def test_chromosome_ends_match_the_upstream_cli(engine_bin, runner_script, synthetic):
    vcf = synthetic["tmp"] / "ends_cli.vcf"
    vcf.write_text(synthetic["vcf_text"])
    records, _ = score(engine_bin, runner_script, synthetic["tmp"], synthetic["vcf_text"],
                       {"chr21": synthetic["fasta"]}, annotation=str(synthetic["annotation"]), name="ends2")
    for mask, key in ((0, "raw"), (1, "masked")):
        out = synthetic["tmp"] / f"ends_cli_m{mask}.vcf"
        subprocess.run([engine_bin / "spliceai", "-I", vcf, "-O", out, "-R", synthetic["fasta"],
                        "-A", synthetic["annotation"], "-D", "50", "-M", str(mask)],
                       check=True, capture_output=True, text=True)
        rows = []
        for line in out.read_text().splitlines():
            if not line.startswith("#"):
                cols = line.split("\t")
                info = dict(f.split("=", 1) for f in cols[7].split(";") if "=" in f)
                rows.append((cols[2], info["SpliceAI"].split(",") if "SpliceAI" in info else []))
        assert [(rid, records[rid]["upstream"][key]) for rid, _ in rows] == rows
