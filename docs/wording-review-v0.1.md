# Wording review: SpliceAI statements in BioBridge v0.1

**What this is.** A check, made on 2026-10-07, that every statement BioBridge makes about SpliceAI agrees with SpliceAI's own documentation and code. **It is not the independent expert review**, which is still pending. That review should judge whether the wording serves bench scientists and whether anything clinically relevant is missing.

**Scope:**
- the fixed text (`ABOUT`, `LIMITATIONS`) and the reasons for unscored alleles in `src/biobridge/explain.py`;
- the per-variant sentences;
- the chart caption;
- `docs/interpreting-results.md`, `docs/limitations.md` and the README.

## Sources

| Source | What it settles |
|---|---|
| Upstream README at tag `v1.3.1`, the version BioBridge runs | The meaning of DS and DP, the cutoffs, the `-M` description, and which variants are scored |
| Upstream README history (`Illumina/SpliceAI`, commits touching `README.md`) | When statements first appeared |
| `spliceai/utils.py` in the installed `spliceai==1.3.1` wheel | Masking and rounding as actually implemented |
| Jaganathan et al., *Cell* 2019, doi:10.1016/j.cell.2018.12.015 | The paper's publication date (January 2019) |

**Dates from the history:**
- The `-M` (masking) option first appears in the "Version 1.3" commits of 2019-10-11/12, for example `dd88e48`. It is absent at `92378c4` (2019-02-21).
- The sentence "can be interpreted as the probability of the variant being splice-altering" is present at `92378c4` and unchanged at `v1.3.1`.
- The FAQ entry on raw and masked files was added in `76ef672` (2020-05-15). It is unchanged at `fc33369` (2025-07-18), the relicensing commit.

## Findings

| # | BioBridge statement | Upstream | Verdict | Change |
|---|---|---|---|---|
| 1 | A delta score is the largest change, within ±50 nt, in the predicted probability that a position is used as an acceptor or donor, for AG, AL, DG and DL. | The README's worked examples ("The probability that the position … is used as a splice donor increases by 0.91"); `-D` defaults to 50. | Consistent | None |
| 2 | "It is a model prediction: not a confidence level, and not a chance of disease." | README: the delta score of a variant, the maximum of the four, "can be interpreted as the probability of the variant being splice-altering". | **Contradicted the authors without attribution.** | The authors' interpretation is now quoted and attributed. BioBridge keeps its own caveat: a model prediction, not a measurement, and not a chance of disease. |
| 3 | Cutoffs of 0.2 (high recall), 0.5 (recommended) and 0.8 (high precision) were characterised in the paper. | README v1.3.1, same wording. | Consistent, but incomplete | BioBridge compares the **largest masked** score with them, while the paper (January 2019) predates masking in the software (version 1.3, October 2019). This is now stated in the app and the docs. |
| 4 | "Masked scores follow the SpliceAI authors' recommendation for variant interpretation." | Not in README v1.3.1. The FAQ added in May 2020 says: "We recommend using raw files for alternative splicing analysis and masked files for variant interpretation" (about precomputed files). | Supported, but cited imprecisely | Reworded as the authors' recommendation of masked scores for interpretation and raw scores for alternative splicing. The docs name the FAQ and its date. |
| 5 | Masking sets to 0 a gain at, or a loss away from, the annotated exon boundary nearest the variant. | README: "Mask scores representing annotated acceptor/donor gain and unannotated acceptor/donor loss". `utils.py` lines 186–197 compare each event's position with the distance to the nearest exon boundary. | Consistent with the code, and more precise than the README | Added "canonical" to "GENCODE V24 annotation", matching the README's `-A` description. |
| 6 | A masked value is either the raw maximum or 0. Raw values are always shown. | `utils.py`: the score is multiplied by `(1 - mask)` at the raw maximum's position. | Consistent | None |
| 7 | Positions are forward-strand GRCh38 coordinates; offsets read "after" or "before the variant on the forward strand". | README: "positive values are downstream of the variant, negative values are upstream". | Consistent. BioBridge avoids "upstream" and "downstream", which readers may take relative to the gene. | None |
| 8 | 0.00 means "below 0.005" because SpliceAI reports two decimals. | `utils.py` formats scores with `{:.2f}`. | Consistent | None |
| 9 | Not scored: outside annotated genes; within about 5 kb of a chromosome end; deletions longer than 100 nt at D = 50; REF mismatch; both REF and ALT longer than one base. | README FAQ 1 ("close to chromosome ends (5kb on either side), deletions of length greater than twice the input parameter -D, or inconsistent with the reference fasta file"); README `-O` ("Only SNVs and simple INDELs (REF or ALT is a single base) within genes"). | Consistent | None |
| 10 | A variant in two genes is scored once per gene. | README `-O`: "Variants in multiple genes have separate predictions for each gene." | Consistent | None |
| 11 | "Confirming an effect on splicing needs RNA evidence." | Not an upstream statement; this is BioBridge's own caution. | Too narrow | Now: "requires experimental evidence, such as RNA analysis." |

**Version.** The explanation text version is now `explanations/2`.

## Left for the independent expert review

- Whether showing the largest masked score as the headline, with the paper's cutoffs, is the right default for bench scientists. Some may expect raw scores, or both together.
- Whether the authors' "probability of the variant being splice-altering" interpretation should appear at all in a tool for non-specialists, and with what caveats.
- Whether the fixed limitations sentence is enough, or should point to published guidance on using SpliceAI in variant classification.
