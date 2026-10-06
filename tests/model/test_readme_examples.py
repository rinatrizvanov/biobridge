"""Reproduce the example outputs published in the upstream SpliceAI README.

Runs the unmodified upstream `spliceai` CLI from the engine environment with its
defaults (-D 50, -M 0) against UCSC hg19 chromosomes (GRCh37), and requires the
SpliceAI INFO strings to match the README exactly.
"""

import subprocess

import pytest

pytestmark = pytest.mark.model

# https://github.com/Illumina/SpliceAI#examples
README_EXPECTED = {
    ("19", 38958362, "C", "T"): "T|RYR1|0.00|0.00|0.91|0.08|-28|-46|-2|-31",
    ("2", 179415988, "C", "CA"): "CA|TTN|0.07|1.00|0.00|0.00|-7|-1|35|-29",
}


def spliceai_info(vcf_path):
    """Map (chrom, pos, ref, alt) to the SpliceAI INFO value; None if the record has none."""
    observed = {}
    for line in vcf_path.read_text().splitlines():
        if line.startswith("#"):
            continue
        chrom, pos, _id, ref, alt, _qual, _filter, info = line.split("\t")[:8]
        fields = dict(f.split("=", 1) for f in info.split(";") if "=" in f)
        observed[(chrom, int(pos), ref, alt)] = fields.get("SpliceAI")
    return observed


def test_upstream_cli_reproduces_readme_examples(engine_bin, reference_set, model_data, tmp_path):
    fasta = reference_set("readme-grch37")
    out = tmp_path / "out.vcf"
    subprocess.run(
        [
            engine_bin / "spliceai",
            "-I", model_data / "readme_examples_grch37.vcf",
            "-O", out,
            "-R", fasta,
            "-A", "grch37",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert spliceai_info(out) == README_EXPECTED
