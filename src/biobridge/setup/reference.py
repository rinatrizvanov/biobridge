"""GRCh38 reference chromosomes, downloaded from UCSC only when a job needs them."""

from __future__ import annotations

import gzip
import shutil
from collections.abc import Callable
from pathlib import Path

from biobridge.setup.downloads import download

UCSC_HG38 = "https://hgdownload.soe.ucsc.edu/goldenPath/hg38/chromosomes/{chrom}.fa.gz"

# md5 of each .fa.gz as published in UCSC md5sum.txt (checked 2026-10-05).
# M1 extends this to chr1-22, X, Y and M.
HG38_MD5 = {
    "chr17": "023ccefd298db339159a446e88d742ac",
    "chr22": "41b47ce1cc21b558409c19b892e1c0d1",
}


def ensure_chromosome(chrom: str, base: Path,
                      progress: Callable[[int, int | None], None] | None = None) -> Path:
    """Return a verified, decompressed GRCh38 FASTA for `chrom`, downloading it if needed."""
    md5 = HG38_MD5[chrom]
    fasta = base / "data" / "reference" / "hg38" / f"{chrom}.fa"
    stamp = fasta.with_name(fasta.name + ".md5")
    if fasta.exists() and stamp.exists() and stamp.read_text() == md5:
        return fasta

    gz = download(UCSC_HG38.format(chrom=chrom),
                  base / "data" / "downloads" / "hg38" / f"{chrom}.fa.gz",
                  md5=md5, progress=progress)
    fasta.parent.mkdir(parents=True, exist_ok=True)
    part = fasta.with_name(fasta.name + ".part")
    with gzip.open(gz, "rb") as src, part.open("wb") as out:
        shutil.copyfileobj(src, out, 1 << 20)
    part.replace(fasta)
    fasta.with_name(fasta.name + ".fai").unlink(missing_ok=True)  # never trust a stale index
    stamp.write_text(md5)
    gz.unlink()
    return fasta
