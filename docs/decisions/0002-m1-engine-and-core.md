# 0002 — M1: engine adapter and core library

Status: **local checks passed** (2026-10-06); **GitHub CI pending** (no remote yet, nothing pushed).

## Scope delivered (within the approved v0.1 scope)

- **Input validation** (`biobridge.inputs`):
  - **Pasted variant:** exactly one, in the form `chr17-43045712-T-G` or `17:43045712 T>G`. Chromosome 1–22, X, Y or M (with or without `chr`); position within the GRCh38 chromosome length; alleles only A/C/G/T/N; REF ≠ ALT.
  - **Uploads:** at most 1 MiB as uploaded and 5 MiB after decompression. Gzip is decompressed as a stream with a hard cap, so a gzip bomb is rejected while it is being read.
  - **Uploaded content:** must be UTF-8 text starting with `##fileformat=VCF`. Genotype and sample columns, and `##FORMAT` lines, are removed before anything is stored.
  - **Records** are parsed by pysam in the engine environment (runner `inspect`), never by hand.
  - **Genome build:** `##reference`/`##assembly` values and GRCh37/GRCh38 contig lengths can block a GRCh37 or conflicting file. They cannot prove GRCh38. Confirmation is always required. Provenance records `build_basis`: `user_confirmed_and_header_agrees` or `user_confirmation_only`. Pasted variants carry no build claim.
  - **Limit:** 50 alleles after splitting multi-allelic records, checked before scoring.
  - **Unsupported or invalid records:** chromosomes outside chr1–22, X, Y and M are `CONTIG_NOT_SUPPORTED`. REF with letters other than uppercase A/C/G/T/N is `INVALID_INPUT` and is never sent upstream. ALT with other letters (e.g. IUPAC `R`) is `INVALID_INPUT`: upstream would silently encode such letters as bases, so its numbers for them are dropped. Sibling ALTs are unaffected.
  - **REF mismatches** report the expected GRCh38 bases.
  - **Indels that are not left-aligned** get a warning with the left-aligned form, and are scored as entered.
  - **Duplicate alleles** are collapsed into one row with a note.
- **Reference:** UCSC hg38 chromosomes are fetched on demand with pinned md5s for chr1–22, X, Y and M.
- **Chromosome ends:** these are tested on a synthetic contig with a custom annotation, through real upstream code; the runner matches the upstream CLI. **Finding:** upstream labels the two ends differently.
  - Upstream fetches a window of 5,000 + D nt (5,050 at D=50) on each side of the variant and checks REF *before* checking the window length.
  - **Near the start:** within 5,050 nt of a chromosome's start, the window's start index is negative, and pyfaidx returns an **empty sequence**. Verified on chr17: positions 100 and 5,050 give length 0, and 5,051 gives the full 10,101 nt. Upstream's REF comparison then fails, so it reports a *REF mismatch* even when REF is correct.
  - **Near the end:** the window is truncated (e.g. 10,100 or 5,151 nt) but its centre base is correct. REF passes, and upstream reports "near chromosome end".
  - **BioBridge's correction:** BioBridge reads REF directly. If the REF matches and the position is ≤ 5,000 + D, it reports `NEAR_CONTIG_END`, noting that upstream calls this a mismatch. A position past the end is `INVALID_INPUT`. A REF that really differs stays `REF_MISMATCH`.
  - **Practical relevance:** these windows mostly cover assembly gaps (chr17's first and last 5 kb are N), so real variants there are rare. The correction is about honest labelling.
- **Runner watchdog** (`biobridge.jobs.engine`): if no event arrives for 300 s, the runner's whole process group is killed (`EngineTimeout`). A non-JSON line on stdout, an error event, a non-zero exit, or a missing `done` event each stop the job with a clear message. The packaged launcher's demo also runs under the watchdog.
- **Rows and CSV** (`biobridge.results`, `biobridge.reports.csv_report`):
  - One row per input allele × SpliceAI gene, including unscored rows.
  - Masked and raw delta scores; offsets and absolute positions; the largest masked score with its event and cutoff band (text, never a percentage).
  - Masked zeros (`AL (raw 0.24)`) and raw values below 0.005 are listed separately.
  - Missing values are `NA`, never 0.
  - Formula-like text cells are prefixed with an apostrophe; numeric cells are never altered.
  - **Provenance columns:** BioBridge version and commit (the packaged app reports `unknown` because it never calls git), engine lock sha256, sha256 of each model, annotation sha256, the chromosome's UCSC URL and md5, D=50, both score modes, build basis, license acknowledgment, start time, host, input name and sha256.
  - `provenance.json` holds the same facts plus the summary and timings.
- **Job pipeline and developer CLI:** `biobridge.jobs.job.run_job` and `python -m biobridge.dev score`.

## Masked-zero labels are verified against upstream's masking rule

`masked_to_zero` must mean that SpliceAI's masking zeroed a value, not that it rounded to 0.00. `tests/model/test_masking_labels.py` checks every score event against an independent oracle, `tests/model/masking_oracle.py`. The oracle uses upstream's public `Annotator.get_pos_data` to find the exon boundary nearest the variant. A gain is masked when its position is that boundary; a loss is masked when it is not.

The test requires three things:
- Every masked value equals either the raw value or 0.
- For raw ≥ 0.01, a masked 0.00 occurs exactly when the oracle predicts masking, and only then is it labelled `masked_zero`.
- A raw 0.00 is always labelled "below 0.005" (`rounded_zero`), whether or not masking also applied, because at two decimals that cannot be told apart.

Results:
- **Fixture:** 4 masked events in the 3 designed records. One of them is a raw 0.01 acceptor loss in the gain-at-annotated-site record.
- **Kept 50-allele benchmark results** (200 events): 4 masked zeros, 88 unmasked non-zero values, and 108 rounded zeros. For 41 of the rounded zeros the masking rule would also apply; they are correctly not called masked.

## Measured 50-allele runtime (2026-10-06)

The test runs were 50 synthetic SNVs at real GRCh38 positions near internal exon boundaries of BRCA1, NF1, TP53, NF2, CHEK2 and COMT (`tests/model/data/runtime_50_alleles_grch38.vcf`), on 2 chromosomes. Each was an end-to-end job through the developer CLI with the developer engine environment (already warmed).

The runs used an **isolated data directory on the developer's Mac**, a new `mktemp -d -t biobridge-benchmark` directory under `$TMPDIR`. Its results are kept locally for inspection and are not committed. This is not an isolated machine and not a clean-install test.

| Run | Wall time | Reference | Scoring | Engine startup (import + model) | First record | Later records, median (range) |
|---|---|---|---|---|---|---|
| 1, fresh data directory (downloads chr17 + chr22) | 75.5 s | 7.7 s | 67.7 s | 2.2 + 1.9 s | 2.36 s | 1.19 s (1.13–2.35) |
| 2, reference cached | 65.7 s | 0 s | 65.6 s | 2.0 + 1.7 s | 2.30 s | 1.21 s (1.12–1.34) |
| 3, reference cached | 65.9 s | 0 s | 65.7 s | 1.6 + 1.7 s | 2.47 s | 1.21 s (1.12–1.34) |

All 50 alleles were scored in each run. Scoring computes raw and masked scores, so each record needs two upstream calls.

Not measured:
- the packaged app's first job right after setup (setup already pays the ~20 s first-import cost),
- inputs that need more chromosomes (each first use adds that chromosome's download: 12–80 MB compressed),
- other Macs.

## Local checks (passed on this Mac, 2026-10-06)

Unit tests, model tests (real engine), and lint (`ruff --select F,E9`) pass; the counts are in the commit message. **GitHub CI is pending.**

## Remaining for M1

- GitHub CI (unit tests on Ubuntu and macOS; model tests on macOS arm64). It cannot run until the repository has a remote, and nothing will be pushed without approval.
- Still tracked: clean-machine verification and behaviour on IT-managed Macs.
