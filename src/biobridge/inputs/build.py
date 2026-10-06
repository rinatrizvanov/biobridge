"""Evidence about which genome build a VCF uses.

A VCF header can show that a file is GRCh37 (and is then rejected; there is no
liftover) or that it is GRCh38. It cannot prove GRCh38: a header with no build
metadata leaves the user's confirmation as the only basis, and the job records that.
Matching REF bases are necessary but not proof either; frequent mismatches only
trigger a warning after scoring.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from biobridge.genome import GRCH37_LENGTHS, GRCH38_LENGTHS, normalize_contig
from biobridge.inputs.text import InputError

GRCH37_NAMES = re.compile(r"grch37|hg19|hs37d5|g1k_v37|ncbi37|(?<![a-z0-9])b37(?![a-z0-9])", re.I)
GRCH38_NAMES = re.compile(r"grch38|hg38|hs38|gca_000001405\.15|assembly38", re.I)

# A REF-mismatch warning is shown when at least this many records, and this share
# of all records, disagree with the GRCh38 reference.
MISMATCH_MIN_RECORDS = 2
MISMATCH_MIN_SHARE = 0.25


@dataclass
class BuildEvidence:
    verdict: str  # "grch38", "grch37", "conflicting" or "unknown"
    reasons: list[str] = field(default_factory=list)


def assess_header(contigs: dict[str, int | None], meta: dict[str, list[str]]) -> BuildEvidence:
    """Judge the build from ##reference/##assembly values and ##contig lengths."""
    says37, says38 = [], []
    for key in ("reference", "assembly"):
        for value in meta.get(key, []):
            if GRCH37_NAMES.search(value):
                says37.append(f"##{key}={value}")
            if GRCH38_NAMES.search(value):
                says38.append(f"##{key}={value}")
    for name, length in contigs.items():
        chrom = normalize_contig(name)
        if chrom is None or length is None or chrom == "chrM":
            continue
        if length == GRCH37_LENGTHS.get(chrom) != GRCH38_LENGTHS[chrom]:
            says37.append(f"contig {name} has the GRCh37 length {length:,}")
        elif length == GRCH38_LENGTHS[chrom]:
            says38.append(f"contig {name} has the GRCh38 length {length:,}")
    if says37 and says38:
        return BuildEvidence("conflicting", says37 + says38)
    if says37:
        return BuildEvidence("grch37", says37)
    if says38:
        return BuildEvidence("grch38", says38)
    return BuildEvidence("unknown", ["the header does not state a genome build"])


def build_basis(evidence: BuildEvidence | None, user_confirmed_grch38: bool) -> str:
    """Return the provenance value for the build, or raise InputError if the job must stop.

    `evidence` is None for a pasted variant, which has no header.
    """
    if evidence is not None and evidence.verdict == "grch37":
        raise InputError("This file appears to use GRCh37 (hg19): " + "; ".join(evidence.reasons)
                         + ". BioBridge v0.1 supports GRCh38 only and does not convert coordinates.")
    if evidence is not None and evidence.verdict == "conflicting":
        raise InputError("The file's header gives conflicting genome builds: "
                         + "; ".join(evidence.reasons) + ".")
    if not user_confirmed_grch38:
        raise InputError("Please confirm that the coordinates are GRCh38 (hg38).")
    if evidence is not None and evidence.verdict == "grch38":
        return "user_confirmed_and_header_agrees"
    return "user_confirmation_only"


def many_ref_mismatches(mismatched_records: int, total_records: int) -> bool:
    return (mismatched_records >= MISMATCH_MIN_RECORDS
            and total_records > 0 and mismatched_records / total_records >= MISMATCH_MIN_SHARE)
