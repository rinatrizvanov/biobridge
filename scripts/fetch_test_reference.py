#!/usr/bin/env python3
"""Download md5-verified UCSC chromosome FASTA files used by the model tests.

Each named set is written as a single decompressed FASTA so that one `-R` path
covers every chromosome the set's test variants need:

    python scripts/fetch_test_reference.py readme-grch37

Files go to $BIOBRIDGE_TEST_REFERENCE_DIR (default: <repo>/.cache/reference).
Expected md5 values are pinned here, copied from UCSC md5sum.txt on 2026-10-05.
Standard library only, so it runs with any Python 3.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import os
import shutil
import sys
import urllib.request
from pathlib import Path

UCSC = "https://hgdownload.soe.ucsc.edu/goldenPath/{build}/chromosomes/{chrom}.fa.gz"

# (build, chromosome) -> md5 of the .fa.gz file as published by UCSC.
MD5 = {
    ("hg19", "chr2"): "1946d3b6b9cf0e8f15f014fe63c75eac",
    ("hg19", "chr19"): "173b9cc2ec39c73668480f4f25701bc3",
    ("hg38", "chr17"): "023ccefd298db339159a446e88d742ac",
}

SETS = {
    # Variants from the upstream SpliceAI README (GRCh37).
    "readme-grch37": ("hg19", ["chr2", "chr19"]),
    "chr17-grch38": ("hg38", ["chr17"]),
}


def default_dest() -> Path:
    env = os.environ.get("BIOBRIDGE_TEST_REFERENCE_DIR")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent / ".cache" / "reference"


def _md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch_chromosome(build: str, chrom: str, dest: Path) -> Path:
    """Return the path of a verified, decompressed <chrom>.fa, downloading if needed."""
    expected = MD5[(build, chrom)]
    gz_path = dest / "downloads" / build / f"{chrom}.fa.gz"
    fa_path = dest / build / f"{chrom}.fa"
    if fa_path.exists() and gz_path.exists() and _md5(gz_path) == expected:
        return fa_path

    gz_path.parent.mkdir(parents=True, exist_ok=True)
    if not (gz_path.exists() and _md5(gz_path) == expected):
        url = UCSC.format(build=build, chrom=chrom)
        part = gz_path.with_suffix(".gz.part")
        print(f"Downloading {url}", file=sys.stderr)
        with urllib.request.urlopen(url, timeout=60) as resp, part.open("wb") as out:
            shutil.copyfileobj(resp, out, 1 << 20)
        actual = _md5(part)
        if actual != expected:
            part.unlink()
            raise RuntimeError(f"md5 mismatch for {url}: expected {expected}, got {actual}")
        part.replace(gz_path)

    fa_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = fa_path.with_suffix(".fa.part")
    with gzip.open(gz_path, "rb") as src, tmp.open("wb") as out:
        shutil.copyfileobj(src, out, 1 << 20)
    tmp.replace(fa_path)
    return fa_path


def ensure_set(name: str, dest: Path | None = None) -> Path:
    """Return the path of the combined FASTA for a named set, building it if needed."""
    dest = dest or default_dest()
    build, chroms = SETS[name]
    parts = [fetch_chromosome(build, chrom, dest) for chrom in chroms]
    combined = dest / f"{name}.fa"
    stamp = dest / f"{name}.sources"
    sources = "\n".join(f"{build}/{c} md5={MD5[(build, c)]}" for c in chroms) + "\n"
    if combined.exists() and stamp.exists() and stamp.read_text() == sources:
        return combined

    tmp = combined.with_suffix(".fa.part")
    with tmp.open("wb") as out:
        for part in parts:
            with part.open("rb") as src:
                shutil.copyfileobj(src, out, 1 << 20)
    tmp.replace(combined)
    # A stale index would point at the wrong offsets.
    combined.with_suffix(".fa.fai").unlink(missing_ok=True)
    stamp.write_text(sources)
    return combined


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("sets", nargs="+", choices=sorted(SETS))
    parser.add_argument("--dest", type=Path, default=None)
    args = parser.parse_args()
    for name in args.sets:
        print(ensure_set(name, args.dest))


if __name__ == "__main__":
    main()
