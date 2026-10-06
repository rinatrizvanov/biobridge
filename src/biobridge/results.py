"""Runner results as rows: one per input allele and SpliceAI gene.

Missing scores stay None (exported as NA): they are never turned into 0, plotted,
or averaged. Two kinds of zero are kept apart:

- masked zero: raw delta score >= 0.01 but the masked score is 0.00. SpliceAI's
  masking zeroed it, by comparing the predicted position with the single annotated
  exon boundary nearest the variant.
- rounded zero: the raw delta score itself is 0.00, i.e. below 0.005, since SpliceAI
  reports two decimals. The masked score is then 0.00 too.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from biobridge.genome import normalize_contig
from biobridge.inputs.build import many_ref_mismatches

EVENTS = ("AG", "AL", "DG", "DL")
EVENT_NAMES = {"AG": "acceptor gain", "AL": "acceptor loss", "DG": "donor gain", "DL": "donor loss"}


def zero_kind(raw: float | None, masked: float | None) -> str | None:
    if raw is None or masked is None:
        return None
    if masked == 0.0 and raw >= 0.01:
        return "masked_zero"
    if raw == 0.0:
        return "rounded_zero"
    return None


def cutoff_band(value: float | None) -> str | None:
    """Position relative to the cutoffs characterised in the SpliceAI paper; never a percentage."""
    if value is None:
        return None
    for cutoff in (0.8, 0.5, 0.2):
        if value >= cutoff:
            return f"at or above {cutoff}"
    return "below 0.2"


@dataclass
class Row:
    record: int
    input_id: str | None
    chrom: str
    pos: int
    ref: str
    alt: str | None
    status: str
    reason: str | None = None
    detail: str | None = None
    gene: str | None = None
    masked: dict[str, float | None] = field(default_factory=dict)
    raw: dict[str, float | None] = field(default_factory=dict)
    dp: dict[str, int | None] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def position(self, event: str) -> int | None:
        dp = self.dp.get(event)
        return None if dp is None else self.pos + dp

    def max_masked(self) -> tuple[float, str] | None:
        values = [(v, e) for e, v in self.masked.items() if v is not None]
        return max(values, key=lambda ve: ve[0]) if values else None

    def zeros(self, kind: str) -> list[str]:
        return [e for e in EVENTS if zero_kind(self.raw.get(e), self.masked.get(e)) == kind]


def _scores(upstream: dict, key: str) -> dict:
    return {e: upstream.get(f"{key}_{e}") for e in EVENTS}


def rows_from_results(results: dict) -> list[Row]:
    rows: list[Row] = []
    first_seen: dict[tuple, Row] = {}
    for rec in results["records"]:
        for allele in rec["alleles"]:
            key = (normalize_contig(rec["chrom"]) or rec["chrom"], rec["pos"], rec["ref"], allele["alt"])
            if allele["alt"] is not None and key in first_seen:
                first_seen[key].notes.append(f"also input record {rec['index'] + 1}")
                continue
            base = dict(record=rec["index"] + 1, input_id=rec.get("id"), chrom=rec["chrom"], pos=rec["pos"],
                        ref=rec["ref"], alt=allele["alt"], status=allele["status"],
                        reason=allele.get("reason"), detail=allele.get("detail"))
            warnings = [f"not left-aligned; left-aligned form {rec['chrom']}:{w['pos']} {w['ref']}>{w['alt']}"
                        for w in allele.get("warnings", []) if w["code"] == "NOT_LEFT_ALIGNED"]
            genes = allele.get("genes") or [None]
            for gene in genes:
                row = Row(**base, warnings=list(warnings))
                if gene is not None:
                    row.gene = gene["gene"]
                    row.raw, row.masked = _scores(gene["raw"], "DS"), _scores(gene["masked"], "DS")
                    raw_dp, masked_dp = _scores(gene["raw"], "DP"), _scores(gene["masked"], "DP")
                    if raw_dp != masked_dp:  # Masking zeroes scores but never moves positions.
                        raise ValueError(f"raw and masked positions differ for record {rec['index'] + 1}")
                    row.dp = raw_dp
                rows.append(row)
                if allele["alt"] is not None:
                    first_seen.setdefault(key, row)
    return rows


def summarize(results: dict, rows: list[Row]) -> dict:
    """Counts per input allele (not per gene row), plus the REF-mismatch warning."""
    alleles = [a for r in results["records"] for a in r["alleles"]]
    by_status = Counter(a["status"] for a in alleles)
    by_reason = Counter(a["reason"] for a in alleles if a.get("reason"))
    mismatched = sum(1 for r in results["records"]
                     if any(a.get("reason") == "REF_MISMATCH" for a in r["alleles"]))
    total = len(results["records"])
    return {
        "records": total,
        "alleles": len(alleles),
        "by_status": dict(by_status),
        "by_reason": dict(by_reason),
        "rows": len(rows),
        "duplicates_collapsed": sum(len([n for n in r.notes if n.startswith("also input")]) for r in rows),
        "many_ref_mismatches": many_ref_mismatches(mismatched, total),
    }
