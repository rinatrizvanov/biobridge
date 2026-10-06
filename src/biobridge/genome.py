"""GRCh38 facts used for validation and on-demand reference downloads.

Values come from UCSC (hg38 chromosomes/md5sum.txt, hg38.chrom.sizes and hg19.chrom.sizes),
checked 2026-10-06. GRCh37 lengths are used only to recognise GRCh37 input, which v0.1
rejects; there is no liftover.
"""

from __future__ import annotations

SUPPORTED = ("chr1", "chr2", "chr3", "chr4", "chr5", "chr6", "chr7", "chr8", "chr9", "chr10", "chr11", "chr12", "chr13", "chr14", "chr15", "chr16", "chr17", "chr18", "chr19", "chr20", "chr21", "chr22", "chrX", "chrY", "chrM")

# md5 of each UCSC hg38 chromosomes/<chrom>.fa.gz
HG38_MD5 = {
    "chr1": "f069c41e7cc8c2d3a7655cbb2d4186b8",
    "chr2": "609cc41e8a44eb99f87839456c6ed333",
    "chr3": "410294b87e71dbd40cf1b98fbadb443b",
    "chr4": "2a54872d6f884b8a993a7aa16db288df",
    "chr5": "69ee0b7e266a45d1b21fd665f917b009",
    "chr6": "fe629afc52a1a06468b60fde0109e32a",
    "chr7": "9c1df22d2a5ce712a410c65fb6e4aeb6",
    "chr8": "44c1556e73628c8ccbaa62ec39bae86a",
    "chr9": "f7e98217b35f5a7451f1166196b4b33c",
    "chr10": "b7d478cb06a84400f74a8932cd5fad0d",
    "chr11": "76542ddafa00440fb67606649e387d7a",
    "chr12": "ea464740f7571bd35d8bc4776be874fa",
    "chr13": "faddb3ad7e9c468ade70b1c88171f1eb",
    "chr14": "c970b8826b6434daa4292d95a300bfd9",
    "chr15": "fd152c2f9d14aaa1b9267e8a1d7561ff",
    "chr16": "6add68e486a69be4ae8cbbc9453cc173",
    "chr17": "023ccefd298db339159a446e88d742ac",
    "chr18": "f3c68bdafea015e6f724c3d646fa2282",
    "chr19": "5668c1a7edca32cc5d68bbeb26061d81",
    "chr20": "1d42fbb5014b165373aca053f4f24061",
    "chr21": "184df2bd9b812b6e6b6da16c6021369e",
    "chr22": "41b47ce1cc21b558409c19b892e1c0d1",
    "chrX": "58259f5bd35fe7e16aeec4c24ee02206",
    "chrY": "d26954bb71ff5e3b8f794fa4c61bfb15",
    "chrM": "62130ce4e873ce2bd6359d1ed9a64906",
}

GRCH38_LENGTHS = {
    "chr1": 248956422,
    "chr2": 242193529,
    "chr3": 198295559,
    "chr4": 190214555,
    "chr5": 181538259,
    "chr6": 170805979,
    "chr7": 159345973,
    "chr8": 145138636,
    "chr9": 138394717,
    "chr10": 133797422,
    "chr11": 135086622,
    "chr12": 133275309,
    "chr13": 114364328,
    "chr14": 107043718,
    "chr15": 101991189,
    "chr16": 90338345,
    "chr17": 83257441,
    "chr18": 80373285,
    "chr19": 58617616,
    "chr20": 64444167,
    "chr21": 46709983,
    "chr22": 50818468,
    "chrX": 156040895,
    "chrY": 57227415,
    "chrM": 16569,
}

# hg19 primary chromosomes (chrM omitted: its length does not separate the builds).
GRCH37_LENGTHS = {
    "chr1": 249250621,
    "chr2": 243199373,
    "chr3": 198022430,
    "chr4": 191154276,
    "chr5": 180915260,
    "chr6": 171115067,
    "chr7": 159138663,
    "chr8": 146364022,
    "chr9": 141213431,
    "chr10": 135534747,
    "chr11": 135006516,
    "chr12": 133851895,
    "chr13": 115169878,
    "chr14": 107349540,
    "chr15": 102531392,
    "chr16": 90354753,
    "chr17": 81195210,
    "chr18": 78077248,
    "chr19": 59128983,
    "chr20": 63025520,
    "chr21": 48129895,
    "chr22": 51304566,
    "chrX": 155270560,
    "chrY": 59373566,
}


def normalize_contig(name: str) -> str | None:
    """Map "17", "chr17", "Chr17", "MT" or "chrM" to the UCSC name; None if not a supported chromosome."""
    core = name[3:] if name[:3].lower() == "chr" else name
    core = core.upper()
    if core == "MT":
        core = "M"
    candidate = f"chr{core}"
    return candidate if candidate in SUPPORTED else None
