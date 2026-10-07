"""CSV export: every row (unscored ones included), masked and raw scores, provenance.

Missing values are written as NA. Text cells that a spreadsheet would treat as a
formula (starting with = + - @ or a tab/return) are prefixed with an apostrophe;
numeric cells are written as plain numbers and are never altered.
"""

from __future__ import annotations

import csv
from pathlib import Path

from biobridge.results import EVENTS, Row, cutoff_band

NA = "NA"
PROVENANCE_COLUMNS = [
    "biobridge_version", "biobridge_commit", "biobridge_source_sha256", "adapter", "spliceai_version", "tensorflow_version",
    "keras_version", "engine_lock_sha256", "models_sha256", "annotation", "annotation_sha256",
    "reference_build", "reference_source", "reference_md5", "max_distance", "score_modes",
    "build_basis", "license_acknowledgment", "job_started", "host", "input_name", "input_sha256",
]
COLUMNS = (
    ["input_record", "input_id", "chrom", "pos", "ref", "alt", "status", "reason", "detail",
     "gene_spliceai_annotation"]
    + [f"DS_{e}_masked" for e in EVENTS] + [f"DS_{e}_raw" for e in EVENTS]
    + [f"DP_{e}" for e in EVENTS] + [f"{e}_position" for e in EVENTS]
    + ["max_DS_masked", "max_DS_masked_event", "cutoff_band_masked",
       "masked_to_zero", "raw_below_0.005", "warnings", "notes"]
    + PROVENANCE_COLUMNS
)
NUMERIC = ({"input_record", "pos", "max_DS_masked"} | {f"DS_{e}_{m}" for e in EVENTS for m in ("masked", "raw")}
           | {f"DP_{e}" for e in EVENTS} | {f"{e}_position" for e in EVENTS})
FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def _number(value) -> str:
    if value is None:
        return NA
    return f"{value:.2f}" if isinstance(value, float) else str(value)


def _text(value) -> str:
    if value is None:
        return NA
    text = str(value)
    return "'" + text if text.startswith(FORMULA_START) else text


def row_cells(row: Row, provenance: dict) -> dict[str, str]:
    top = row.top_masked()
    has_scores = any(v is not None for v in row.raw.values())
    masked_zero = [f"{e} (raw {row.raw[e]:.2f})" for e in row.zeros("masked_zero")]
    cells = {
        "input_record": row.record, "input_id": row.input_id, "chrom": row.chrom, "pos": row.pos,
        "ref": row.ref, "alt": row.alt, "status": row.status, "reason": row.reason,
        "detail": row.detail, "gene_spliceai_annotation": row.gene,
        **{f"DS_{e}_masked": row.masked.get(e) for e in EVENTS},
        **{f"DS_{e}_raw": row.raw.get(e) for e in EVENTS},
        **{f"DP_{e}": row.dp.get(e) for e in EVENTS},
        **{f"{e}_position": row.position(e) for e in EVENTS},
        "max_DS_masked": top[0] if top else None,
        # "none" when all four masked scores are 0.00; ties list every event.
        "max_DS_masked_event": ("; ".join(top[1]) or "none") if top else None,
        "cutoff_band_masked": cutoff_band(top[0]) if top else None,
        # For unscored rows these are NA (not applicable); for scored rows "none" if empty.
        "masked_to_zero": ("; ".join(masked_zero) or "none") if has_scores else None,
        "raw_below_0.005": ("; ".join(row.zeros("rounded_zero")) or "none") if has_scores else None,
        "warnings": "; ".join(row.warnings),
        "notes": "; ".join(row.notes),
        **{k: provenance.get(k) for k in PROVENANCE_COLUMNS},
    }
    cells["reference_source"] = provenance.get("reference_sources", {}).get(row.chrom, NA)
    cells["reference_md5"] = provenance.get("reference_md5s", {}).get(row.chrom, NA)
    return {k: (_number(v) if k in NUMERIC else _text(v)) for k, v in cells.items()}


def write_csv(rows: list[Row], provenance: dict, path: Path) -> Path:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row_cells(row, provenance))
    return path
