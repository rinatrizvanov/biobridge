"""The whole job pipeline with the real engine: input -> inspect -> build check -> limit ->
reference -> scoring -> rows -> CSV and provenance."""

import csv
import gzip
import json
import os

import pytest

from biobridge.inputs.text import InputError
from biobridge.jobs.job import MAX_ALLELES, JobRequest, run_job
from biobridge.setup.processes import ChildProcesses
from biobridge.genome import HG38_MD5
from tests.model.test_runner_matches_cli import EXPECTED_STATUS

pytestmark = pytest.mark.model


@pytest.fixture(scope="module")
def home(tmp_path_factory, reference_chromosomes):
    """A BioBridge data folder pre-seeded with the cached, md5-verified chr17 and chr22."""
    base = tmp_path_factory.mktemp("home") / "Application Support" / "BioBridge"
    ref = base / "data" / "reference" / "hg38"
    ref.mkdir(parents=True)
    for chrom, path in reference_chromosomes("grch38-chr17-chr22").items():
        os.symlink(path, ref / f"{chrom}.fa")
        (ref / f"{chrom}.fa.md5").write_text(HG38_MD5[chrom])
    return base


def job(home, engine_bin, **kwargs):
    return run_job(JobRequest(**kwargs), home, engine_bin.parent, ChildProcesses())


def read_csv(path):
    with path.open() as fh:
        return list(csv.DictReader(fh))


def test_pasted_variant_end_to_end(home, engine_bin):
    result = job(home, engine_bin, paste="chr17-43057051-C-T", confirm_grch38=True)
    (row,) = read_csv(result.csv_path)
    assert (row["status"], row["gene_spliceai_annotation"], row["DS_DL_masked"], row["DL_position"]) == (
        "SCORED", "BRCA1", "0.99", "43057052")
    assert row["build_basis"] == "user_confirmation_only"
    assert row["spliceai_version"] == "1.3.1"
    assert row["reference_md5"] == HG38_MD5["chr17"]
    provenance = json.loads((result.job_dir / "provenance.json").read_text())
    assert provenance["input_name"] == "pasted variant" and provenance["build_evidence"] is None


def test_uploaded_vcf_with_genotypes_end_to_end(home, engine_bin, model_data):
    lines = (model_data / "runner_vs_cli_grch38.vcf").read_text().splitlines()
    with_samples = [ln + "\tFORMAT\tPATIENT" if ln.startswith("#CHROM") else
                    ln if ln.startswith("#") else ln + "\tGT\t0/1" for ln in lines]
    data = gzip.compress(("\n".join(with_samples) + "\n").encode())
    result = job(home, engine_bin, vcf_bytes=data, vcf_name="fixture.vcf.gz", confirm_grch38=True)

    assert "PATIENT" not in (result.job_dir / "input.vcf").read_text()
    rows = read_csv(result.csv_path)
    observed = {}
    for row in rows:
        observed.setdefault(row["input_id"], {})[row["alt"]] = (row["status"], None if row["reason"] == "NA" else row["reason"])
    assert observed == EXPECTED_STATUS
    assert rows[0]["build_basis"] == "user_confirmed_and_header_agrees"
    expected_counts = {}
    for statuses in EXPECTED_STATUS.values():
        for status, _ in statuses.values():
            expected_counts[status] = expected_counts.get(status, 0) + 1
    assert result.summary["by_status"] == expected_counts  # 13 scored, 6 not scored
    two_genes = [r["gene_spliceai_annotation"] for r in rows if r["input_id"] == "txnrd2_comt_two_genes"]
    assert sorted(two_genes) == ["COMT", "TXNRD2"]
    hidden = next(r for r in rows if r["input_id"] == "brca1_masked_hides_annotated_loss")
    assert hidden["masked_to_zero"].startswith("AL (raw 0.2")


def test_grch37_file_is_blocked_before_scoring(home, engine_bin, model_data):
    data = (model_data / "readme_examples_grch37.vcf").read_bytes()
    with pytest.raises(InputError, match="GRCh37"):
        job(home, engine_bin, vcf_bytes=data, confirm_grch38=True)
    newest = sorted((home / "jobs").iterdir())[-1]
    assert not (newest / "results.json").exists()


def test_confirmation_is_required(home, engine_bin):
    with pytest.raises(InputError, match="confirm"):
        job(home, engine_bin, paste="chr17-43057051-C-T", confirm_grch38=False)


def test_allele_limit_is_checked_before_scoring(home, engine_bin):
    body = "".join(f"chr17\t{43057000 + i}\t.\tN\tA\t.\t.\t.\n" for i in range(MAX_ALLELES + 1))
    data = ("##fileformat=VCFv4.2\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n" + body).encode()
    with pytest.raises(InputError, match=f"51 alleles; BioBridge v0.1 scores up to {MAX_ALLELES}"):
        job(home, engine_bin, vcf_bytes=data, confirm_grch38=True)
