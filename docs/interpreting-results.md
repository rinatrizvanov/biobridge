# Reading BioBridge results

BioBridge reports SpliceAI's predictions. It does not interpret them clinically.

## Delta scores

For each position within 50 nucleotides of a variant, SpliceAI predicts the probability that the position is used as a splice acceptor or donor. It does this twice: once for the reference sequence and once with the variant. A **delta score** is the largest change in that probability, reported separately for four events:

| Code | Event | Meaning |
|---|---|---|
| AG | acceptor gain | largest increase in acceptor probability |
| AL | acceptor loss | largest decrease in acceptor probability |
| DG | donor gain | largest increase in donor probability |
| DL | donor loss | largest decrease in donor probability |

Scores range from 0 to 1 and are reported with two decimals. A delta score is a model prediction. It is **not a confidence level and not a chance of disease**, and BioBridge never shows it as a percentage.

The SpliceAI paper characterised cutoffs of **0.2** (high recall), **0.5** (recommended) and **0.8** (high precision). BioBridge says which of these the largest masked score reaches. The cutoffs come from the paper; they are not BioBridge's thresholds.

## Masked and raw scores

The SpliceAI authors recommend **masked** scores for variant interpretation and **raw** scores for studying alternative splicing. BioBridge always shows both.

Masking compares each predicted position with **the single annotated exon boundary nearest the variant** in SpliceAI's GENCODE V24 annotation. It sets to 0:
- a gain at that boundary, and
- a loss anywhere else.

So masking can hide a predicted loss at *another* annotated boundary. One test case does exactly that: raw acceptor loss 0.24 at an annotated acceptor that is not the nearest boundary, shown as masked 0.00.

## Two kinds of 0.00

- **Set to 0.00 by masking.** The raw score is 0.01 or more, but masking set the masked score to 0. The explanation says so and gives the raw value. The chart labels the event "masked", and the CSV lists it in `masked_to_zero`.
- **Below 0.005.** The raw score itself is 0.00 after rounding to two decimals. The CSV lists the event in `raw_below_0.005`.

**`NA` means not available.** Missing scores are never shown as 0.

## Positions

Positions are GRCh38 coordinates on the forward strand of the genome. The **offset** counts nucleotides from the variant along that strand: positive means a higher coordinate. It does not say upstream or downstream in the gene, because that depends on the gene's strand. BioBridge v0.1 does not number exons.

## The chart

- One chart per scored variant, on a fixed 0–1 axis.
- Bars show masked scores; dots show raw scores.
- Hairlines mark the 0.2, 0.5 and 0.8 cutoffs.
- Hover over an event, or move to it with Tab, to see its values. Escape hides them. The same values are in the table under the chart.

## Not scored

| Reason | What it means |
|---|---|
| Outside SpliceAI's genes | SpliceAI only scores variants inside genes of its annotation (GENCODE V24). |
| Reference mismatch | The REF allele differs from GRCh38 at that position. The detail gives the reference bases. Check the build, and that the alleles were not copied from the minus strand or from an HGVS description. |
| Near a chromosome end | SpliceAI needs about 5 kb of sequence on each side of the variant. |
| Deletion too long | Deletions longer than 100 nt are not scored at the maximum distance used (50). |
| Complex substitution | SpliceAI does not score variants in which both REF and ALT are longer than one base. |
| Unsupported allele | Symbolic or placeholder alleles such as `<DEL>` or `*`. |
| Unsupported chromosome | Only chr1–22, X, Y and M are supported. |
| Invalid input | For example, letters other than A, C, G, T or N. |

A variant that overlaps two genes is scored once for each gene.

## Genome build

BioBridge rejects inputs whose header indicates GRCh37, or gives conflicting builds. It cannot verify the build of an input that does not state one. The results then say so, and the CSV's `build_basis` is `user_confirmation_only`.

## What a score does not tell you

SpliceAI does not predict the resulting transcript (exon skipping, intron retention or use of a cryptic site), and a score alone does not establish that a variant is pathogenic or benign. Confirming an effect on splicing needs RNA evidence. BioBridge assigns no ACMG criteria.

## The CSV

Each row is one input allele in one SpliceAI gene, unscored alleles included. The main columns are:
- **Status:** `status`, `reason` and `detail`.
- **Scores:** `DS_<event>_masked` and `DS_<event>_raw`.
- **Positions:** `DP_<event>` (the offset) and `<event>_position`.
- **Largest masked score:** `max_DS_masked` and `max_DS_masked_event`. The event column is `none` when all four masked scores are 0.00, and lists every event when they tie.
- **Zeros:** `masked_to_zero` and `raw_below_0.005`.
- **Provenance:** one column per item.

Long alleles are written in full in the CSV; on screen they are shortened (for example `AATACA…(102 nt)`). Spreadsheet programs may turn some gene symbols into dates, so open the file as text, or import gene columns as text.
