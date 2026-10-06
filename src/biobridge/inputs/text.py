"""A single variant typed or pasted by the user.

Accepted forms (GRCh38 coordinates, VCF-style alleles):

    chr17-43045712-T-G      17-43045712-T-G
    chr17:43045712 T>G      17:43045712 T>G

HGVS, rsIDs and gene names are not accepted in v0.1: turning them into genomic
alleles needs transcript-aware normalization.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from biobridge.genome import GRCH38_LENGTHS, normalize_contig

EXAMPLE = "chr17-43045712-T-G"
FORMS = (
    re.compile(r"^(?P<chrom>(?:chr)?\w{1,2})-(?P<pos>\d+)-(?P<ref>[A-Za-z]+)-(?P<alt>[A-Za-z]+)$", re.I),
    re.compile(r"^(?P<chrom>(?:chr)?\w{1,2}):(?P<pos>\d+)\s+(?P<ref>[A-Za-z]+)>(?P<alt>[A-Za-z]+)$", re.I),
)
ALLELE = re.compile(r"^[ACGTN]+$")


class InputError(ValueError):
    """Input that cannot be scored, with a message written for the user."""


@dataclass(frozen=True)
class Variant:
    chrom: str
    pos: int
    ref: str
    alt: str


def parse_variant(text: str) -> Variant:
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    if not lines:
        raise InputError(f"Enter a variant, for example {EXAMPLE}.")
    if len(lines) > 1:
        raise InputError("Enter one variant at a time. To score several, upload a VCF file.")
    match = next((m for form in FORMS if (m := form.match(lines[0]))), None)
    if not match:
        raise InputError(f"Could not read {lines[0]!r}. Use the form {EXAMPLE} or chr17:43045712 T>G "
                         "(GRCh38 position, then the reference and alternate bases).")

    chrom = normalize_contig(match["chrom"])
    if chrom is None:
        raise InputError(f"Chromosome {match['chrom']!r} is not supported. Use 1–22, X, Y or M.")
    pos = int(match["pos"])
    if not 1 <= pos <= GRCH38_LENGTHS[chrom]:
        raise InputError(f"Position {pos:,} is outside {chrom}, which has "
                         f"{GRCH38_LENGTHS[chrom]:,} bases in GRCh38.")
    ref, alt = match["ref"].upper(), match["alt"].upper()
    for name, allele in (("reference", ref), ("alternate", alt)):
        if not ALLELE.match(allele):
            raise InputError(f"The {name} allele {allele!r} may contain only A, C, G, T or N.")
    if ref == alt:
        raise InputError("The reference and alternate alleles are identical.")
    return Variant(chrom, pos, ref, alt)


def to_vcf(variant: Variant) -> str:
    """A minimal VCF for one pasted variant. It states no genome build: the build rests on
    the user's confirmation alone."""
    return (
        "##fileformat=VCFv4.2\n"
        "##source=BioBridge pasted variant\n"
        f"##contig=<ID={variant.chrom}>\n"
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
        f"{variant.chrom}\t{variant.pos}\tpasted\t{variant.ref}\t{variant.alt}\t.\t.\t.\n"
    )
