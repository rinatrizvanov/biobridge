"""Deterministic explanations: fixed text plus sentences built from each result row.

Rules (v0.1):
- A delta score is a change in SpliceAI's predicted splice-site probability, not a
  confidence level or a chance of disease. Values are never shown as percentages.
- Positions are absolute GRCh38 coordinates with a forward-strand offset; there is
  no upstream/downstream, exon-number or transcript wording.
- No statement about the resulting transcript, pathogenicity or ACMG criteria. That
  is said once, in the fixed limitations, and nowhere else.
- A masked zero (masking set a raw value >= 0.01 to 0) and a raw value below 0.005
  (shown as 0.00) are described differently.
"""

from __future__ import annotations

from biobridge.results import EVENT_NAMES, EVENTS, Row

VERSION = "explanations/1"

ABOUT = [
    "SpliceAI predicts, for each position near a variant, the probability that the position is "
    "used as a splice acceptor or donor, once for the reference sequence and once with the variant. "
    "A delta score is the largest change in that probability within ±50 nucleotides of the variant, "
    "separately for acceptor gain (AG), acceptor loss (AL), donor gain (DG) and donor loss (DL). "
    "It is a model prediction: not a confidence level, and not a chance of disease.",
    "The SpliceAI paper (Jaganathan et al., Cell 2019) characterised cutoffs of 0.2 (high recall), "
    "0.5 (recommended) and 0.8 (high precision).",
    "Masked scores follow the SpliceAI authors' recommendation for variant interpretation. Masking "
    "sets to 0 a gain at, or a loss away from, the annotated exon boundary nearest the variant in "
    "SpliceAI's GENCODE V24 annotation. Raw scores are shown alongside because masking can also hide "
    "a change at another annotated boundary.",
    "Positions are GRCh38 coordinates on the genome's forward strand; offsets count nucleotides from "
    "the variant along that strand.",
]
LIMITATIONS = (
    "SpliceAI does not predict the resulting transcript (for example exon skipping, intron retention "
    "or use of a cryptic splice site), and a score alone does not establish that a variant is "
    "pathogenic or benign. Confirming an effect on splicing needs RNA evidence. BioBridge is "
    "experimental research software, not a diagnostic, and assigns no ACMG criteria."
)

REASONS = {
    "NOT_IN_SPLICEAI_GENE": "The variant is outside the genes in SpliceAI's annotation (GENCODE V24), "
                            "so SpliceAI does not score it.",
    "REF_MISMATCH": "The reference allele does not match GRCh38 at this position. Check the genome build, "
                    "and that the alleles were not copied from the minus strand or from an HGVS description.",
    "NEAR_CONTIG_END": "The variant is too close to a chromosome end for SpliceAI's sequence window.",
    "DELETION_TOO_LONG": "SpliceAI does not score deletions longer than 100 nucleotides at the maximum "
                         "distance used here (50).",
    "COMPLEX_DELINS": "SpliceAI does not score variants in which both the reference and the alternate "
                      "allele are longer than one base.",
    "UNSUPPORTED_ALLELE": "Symbolic or placeholder alleles (such as <DEL> or *) are not supported.",
    "CONTIG_NOT_SUPPORTED": "Only chromosomes 1–22, X, Y and M of GRCh38 are supported.",
    "INVALID_INPUT": "The record is not valid input.",
    "ENGINE_ERROR": "The SpliceAI engine failed on this record.",
    "UNEXPECTED_ENGINE_OUTPUT": "The SpliceAI engine returned output BioBridge could not match to this allele.",
}


def band_sentence(value: float) -> str:
    for cutoff, name in ((0.8, "high precision"), (0.5, "recommended"), (0.2, "high recall")):
        if value >= cutoff:
            return f"This is at or above the {cutoff} cutoff ({name}) characterised in the SpliceAI paper."
    return "This is below the lowest cutoff characterised in the SpliceAI paper, 0.2 (high recall)."


def position_phrase(row: Row, event: str) -> str:
    dp = row.dp[event]
    where = f"{row.chrom}:{row.position(event):,}"
    if dp == 0:
        return f"{where}, the variant's own position"
    return f"{where}, {abs(dp)} nucleotide{'s' if abs(dp) != 1 else ''} {'after' if dp > 0 else 'before'} " \
           f"the variant on the forward strand"


def explain(row: Row, genes_for_allele: int = 1) -> list[str]:
    """Sentences for one row. Not-scored rows get the reason (and BioBridge's detail)."""
    if row.status != "SCORED":
        lead = "Error: " if row.status == "ERROR" else "Not scored: "
        text = [lead + REASONS.get(row.reason or "", "No reason was recorded.")]
        if row.detail:
            text.append(f"Detail: {row.detail}.")
        return text

    text = []
    best = row.max_masked()
    if best is None or best[0] == 0.0:
        text.append("All four masked delta scores are 0.00.")
    else:
        value, event = best
        text.append(f"The largest masked delta score is {value:.2f}, for {EVENT_NAMES[event]}, at "
                    f"{position_phrase(row, event)}. {band_sentence(value)}")
    for event in row.zeros("masked_zero"):
        text.append(f"{EVENT_NAMES[event].capitalize()}: set to 0.00 by SpliceAI's masking; the raw value "
                    f"is {row.raw[event]:.2f}, at {position_phrase(row, event)}.")
    rounded = row.zeros("rounded_zero")
    if rounded:
        names = ", ".join(EVENT_NAMES[e] for e in rounded)
        text.append(f"Below 0.005 (shown as 0.00, because SpliceAI reports two decimals): {names}.")
    if genes_for_allele > 1:
        text.append(f"This variant overlaps {genes_for_allele} genes in SpliceAI's annotation; each gene "
                    "is scored separately.")
    text += [w[0].upper() + w[1:] + ". It was scored as entered." for w in row.warnings]
    if row.notes:
        text.append("The same allele " + "; ".join(row.notes).replace("also input", "also appears as input") + ".")
    return text


def event_table(row: Row) -> list[dict]:
    """The table twin of the plot: every value, reachable without the chart."""
    return [{"event": e, "name": EVENT_NAMES[e], "masked": row.masked.get(e), "raw": row.raw.get(e),
             "offset": row.dp.get(e), "position": row.position(e)} for e in EVENTS]
