"""Input validation: pasted variants, upload limits, sample removal, build evidence."""

import gzip

import pytest

from biobridge.inputs.build import BuildEvidence, assess_header, build_basis, many_ref_mismatches
from biobridge.inputs.text import InputError, Variant, parse_variant, to_vcf
from biobridge.inputs.upload import MAX_UPLOAD_BYTES, MAX_VCF_BYTES, prepare_upload

HEADER = "##fileformat=VCFv4.2\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"


# --- pasted variants -------------------------------------------------------------------
@pytest.mark.parametrize("text", [
    "chr17-43045712-T-G", "17-43045712-T-G", "chr17:43045712 T>G", "17:43045712 t>g",
    "  chr17-43045712-T-G  \n", "Chr17-43045712-T-G",
])
def test_accepted_forms(text):
    assert parse_variant(text) == Variant("chr17", 43045712, "T", "G")


def test_mitochondrial_and_sex_chromosomes_normalize():
    assert parse_variant("MT-100-A-G").chrom == "chrM"
    assert parse_variant("x:100 A>G").chrom == "chrX"


@pytest.mark.parametrize("text, message", [
    ("", "Enter a variant"),
    ("chr17-1-A-G\nchr17-2-A-G", "one variant at a time"),
    ("NM_007294.4:c.5266dupC", "Could not read"),
    ("rs80357906", "Could not read"),
    ("chr17_KI270729v1_random-10-A-G", "Could not read"),
    ("chr23-100-A-G", "not supported"),
    ("chr17-0-A-G", "outside chr17"),
    ("chr17-83257442-A-G", "outside chr17"),
    ("chr17-100-R-G", "may contain only A, C, G, T or N"),
    ("chr17-100-A-A", "identical"),
])
def test_rejected_forms_explain_why(text, message):
    with pytest.raises(InputError, match=message):
        parse_variant(text)


def test_pasted_vcf_states_no_build():
    vcf = to_vcf(Variant("chr17", 43045712, "T", "G"))
    assert "##contig=<ID=chr17>" in vcf  # no length, so no claimed build
    assert "chr17\t43045712\tpasted\tT\tG" in vcf


# --- uploads ---------------------------------------------------------------------------
def test_plain_upload_drops_sample_columns(tmp_path):
    vcf = ("##fileformat=VCFv4.2\n##FORMAT=<ID=GT,Number=1,Type=String,Description=\"GT\">\n"
           "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tPATIENT_1\tPATIENT_2\r\n"
           "chr17\t100\t.\tA\tG\t.\t.\t.\tGT\t0/1\t1/1\r\n")
    info = prepare_upload(vcf.encode(), tmp_path / "in.vcf")
    written = (tmp_path / "in.vcf").read_text()
    assert info.samples_dropped == 2 and not info.compressed
    assert "PATIENT" not in written and "0/1" not in written and "##FORMAT" not in written
    assert "chr17\t100\t.\tA\tG\t.\t.\t." in written and "\r" not in written


def test_gzip_upload_is_decompressed(tmp_path):
    vcf = (HEADER + "chr17\t100\t.\tA\tG\t.\t.\t.\n").encode()
    info = prepare_upload(gzip.compress(vcf), tmp_path / "in.vcf")
    assert info.compressed and info.vcf_bytes == len(vcf)
    assert (tmp_path / "in.vcf").read_bytes() == vcf


def test_upload_size_limit_applies_to_the_file_as_uploaded(tmp_path):
    big = (HEADER + "x" * MAX_UPLOAD_BYTES).encode()
    with pytest.raises(InputError, match="the limit is 1.0 MB"):
        prepare_upload(big, tmp_path / "in.vcf")


def test_gzip_bomb_is_rejected_while_decompressing(tmp_path):
    bomb = gzip.compress((HEADER + "#" * (MAX_VCF_BYTES * 4)).encode())
    assert len(bomb) < MAX_UPLOAD_BYTES  # small enough to pass the upload limit
    with pytest.raises(InputError, match="expands to more than 5.0 MB"):
        prepare_upload(bomb, tmp_path / "in.vcf")
    assert not (tmp_path / "in.vcf").exists()


@pytest.mark.parametrize("data, message", [
    (b"\x1f\x8b\x08\x00garbage", "could not be decompressed"),
    (b"##fileformat=VCFv4.2\n\x00\x01", "not a text VCF"),
    (b"\xff\xfe\xfa", "not valid UTF-8"),
    (b"CHROM,POS,REF,ALT\n17,100,A,G\n", "does not look like a VCF"),
])
def test_unreadable_uploads_explain_why(tmp_path, data, message):
    with pytest.raises(InputError, match=message):
        prepare_upload(data, tmp_path / "in.vcf")


# --- genome build ----------------------------------------------------------------------
def test_grch37_reference_line_blocks_the_job():
    evidence = assess_header({}, {"reference": ["file:///data/human_g1k_v37.fasta"]})
    assert evidence.verdict == "grch37"
    with pytest.raises(InputError, match="GRCh37"):
        build_basis(evidence, user_confirmed_grch38=True)


def test_grch37_contig_lengths_block_the_job():
    evidence = assess_header({"1": 249250621, "17": 81195210}, {})
    assert evidence.verdict == "grch37"
    assert "contig 1 has the GRCh37 length 249,250,621" in evidence.reasons


def test_grch38_header_agrees_but_confirmation_is_still_required():
    evidence = assess_header({"chr17": 83257441}, {"reference": ["GRCh38"]})
    assert evidence.verdict == "grch38"
    with pytest.raises(InputError, match="confirm"):
        build_basis(evidence, user_confirmed_grch38=False)
    assert build_basis(evidence, user_confirmed_grch38=True) == "user_confirmed_and_header_agrees"


def test_missing_metadata_cannot_establish_grch38():
    evidence = assess_header({"chr17": None}, {})
    assert evidence.verdict == "unknown"
    assert build_basis(evidence, user_confirmed_grch38=True) == "user_confirmation_only"
    assert build_basis(None, user_confirmed_grch38=True) == "user_confirmation_only"  # pasted


def test_conflicting_header_blocks_the_job():
    evidence = assess_header({"chr1": 249250621}, {"assembly": ["hg38"]})
    assert evidence.verdict == "conflicting"
    with pytest.raises(InputError, match="conflicting"):
        build_basis(evidence, user_confirmed_grch38=True)


def test_mitochondrial_length_is_not_used_as_evidence():
    assert assess_header({"chrM": 16569, "MT": 16571}, {}).verdict == "unknown"


def test_words_containing_b37_are_not_mistaken_for_grch37():
    assert assess_header({}, {"reference": ["genome_lab37b.fa"]}).verdict == "unknown"
    assert assess_header({}, {"reference": ["b37"]}).verdict == "grch37"


@pytest.mark.parametrize("mismatched, total, warn", [(1, 1, False), (2, 4, True), (2, 10, False), (5, 20, True)])
def test_ref_mismatch_warning_threshold(mismatched, total, warn):
    assert many_ref_mismatches(mismatched, total) is warn


def test_build_evidence_reasons_are_reported():
    assert BuildEvidence("unknown").reasons == []
