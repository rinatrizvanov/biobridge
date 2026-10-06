"""Uploaded VCF files: size limits, decompression, and dropping sample data.

Limits apply both to the file as uploaded and to its decompressed content, so a
small gzip file that expands to gigabytes is rejected while it is being read.
Genotype columns are removed before anything is stored: scoring needs only CHROM,
POS, ID, REF and ALT, and genotypes are personal data. Records are parsed later by
pysam in the engine environment.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import zlib
from dataclasses import dataclass
from pathlib import Path

from biobridge.inputs.text import InputError

MAX_UPLOAD_BYTES = 1 << 20  # 1 MiB as uploaded
MAX_VCF_BYTES = 5 << 20     # 5 MiB after decompression
CHUNK = 64 << 10


@dataclass(frozen=True)
class UploadInfo:
    sha256: str          # of the file exactly as uploaded
    uploaded_bytes: int
    vcf_bytes: int       # decompressed size before sample columns were removed
    compressed: bool
    samples_dropped: int


def _mib(n: int) -> str:
    return f"{n / (1 << 20):.1f} MB"


def _decompress(data: bytes) -> bytes:
    out = bytearray()
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(data)) as gz:
            while chunk := gz.read(CHUNK):
                out += chunk
                if len(out) > MAX_VCF_BYTES:
                    raise InputError(f"The file expands to more than {_mib(MAX_VCF_BYTES)} when "
                                     "decompressed. BioBridge v0.1 accepts small files only.")
    except (OSError, EOFError, zlib.error) as exc:
        raise InputError("The file looks gzip-compressed but could not be decompressed.") from exc
    return bytes(out)


def prepare_upload(data: bytes, dest: Path) -> UploadInfo:
    """Validate an uploaded VCF (plain or gzip) and write a sample-free copy to `dest`."""
    if len(data) > MAX_UPLOAD_BYTES:
        raise InputError(f"The file is {_mib(len(data))}; the limit is {_mib(MAX_UPLOAD_BYTES)}.")
    compressed = data[:2] == b"\x1f\x8b"
    raw = _decompress(data) if compressed else data
    if len(raw) > MAX_VCF_BYTES:
        raise InputError(f"The VCF is larger than {_mib(MAX_VCF_BYTES)}.")
    if b"\x00" in raw:
        raise InputError("This is not a text VCF file.")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InputError("The file is not valid UTF-8 text.") from exc
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if not lines[0].startswith("##fileformat=VCF"):
        raise InputError("This does not look like a VCF file: the first line must start "
                         "with ##fileformat=VCF.")

    kept, samples = [], 0
    for line in lines:
        if line.startswith("##FORMAT="):
            continue
        if line.startswith("#CHROM"):
            samples = max(0, len(line.split("\t")) - 9)
            line = "\t".join(line.split("\t")[:8])
        elif line and not line.startswith("#"):
            line = "\t".join(line.split("\t")[:8])
        kept.append(line)
    dest.write_text("\n".join(kept).rstrip("\n") + "\n")
    return UploadInfo(hashlib.sha256(data).hexdigest(), len(data), len(raw), compressed, samples)
