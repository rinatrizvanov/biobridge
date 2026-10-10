# Changelog

## 0.1.0 — 2026-10-10

**Source release.** No macOS disk image is published for 0.1.0. The candidate image is waiting for an installation test on a second Mac; see `docs/release-v0.1.0.md`.

First usable version. Experimental research software, not a diagnostic; SpliceAI's models are licensed for academic and non-commercial use only.

### Added
- A macOS app (Apple Silicon) that sets up the SpliceAI engine on the user's Mac without a terminal. It uses its bundled uv, binary-only hash-locked packages and a uv-managed Python, with retries for interrupted downloads.
- A local browser interface (127.0.0.1 only):
  - one pasted GRCh38 variant, or a VCF upload (up to 1 MB, 5 MB decompressed, 50 alleles);
  - a required GRCh38 confirmation;
  - live progress and Cancel;
  - results with masked and raw delta scores, a chart and a table of values per variant, deterministic explanations, and reasons for unscored alleles;
  - CSV download.
- The unmodified SpliceAI 1.3.1 runs under a watchdog. Its results match the upstream CLI field for field in raw and masked modes, including reference switching between chromosomes.
- Provenance with every result: BioBridge version, source revision and source digest (embedded at build time in the packaged app), engine lock, model and annotation checksums, reference checksums, settings, genome-build basis and license acknowledgment.

### Found and fixed during verification
- Downloads inside the app failed TLS verification: the bundled Python had no usable CA file. Downloads now use the macOS trust store.
- In real browsers, form posts were blocked: the `no-referrer` policy made them send `Origin: null`. The policy is now `same-origin`.
- Chart value labels at 0.99 and 1.00 were clipped at the top. The plot geometry is now tested at 0, 0.99 and 1.00, at narrow widths and at 200% zoom.
- A 102-nt deletion's full allele made the results table thousands of pixels wide. Long alleles are now shortened on screen; the CSV keeps them in full.
- "Largest masked" named an arbitrary event when all four masked scores were 0.00. It now names no event in that case, and every event in a tie.
- Upstream reports a reference mismatch near chromosome starts. BioBridge now checks REF itself.
- Console scripts in the app embedded the build machine's home path. They are removed, and a bundle check guards against it.
- The packaged app reported its source revision as `unknown`. It now records the real commit and whether the build had uncommitted changes.
- The app's `Info.plist` kept version 0.0.0, because Briefcase does not rewrite it on update. The build now recreates the generated app folder, and the bundle check compares the versions.
- The results summary capitalised the uploaded file's name (`MyVariants.VCF` became `Myvariants.vcf`). It now shows the name exactly.
- At phone width, the per-variant value tables and the table notes were cut off at the screen edge. Value tables now wrap to fit, and notes under a table that scrolls sideways wrap to the visible width.

### Changed in preparation for a public release
- **Bundle identifier:** now `io.github.rinatrizvanov.biobridge`, replacing the placeholder `local.biobridge.biobridge`. Data and log folders are unchanged.
- **Minimum macOS:** the app now declares macOS 14, the documented minimum, instead of macOS 11.
- **License texts:** the app now ships the texts for its Python runtime components (OpenSSL, Tcl/Tk, ncurses, XZ) and for Briefcase's stub and template. The notices also correct the stub's license: MIT, not BSD-3-Clause.
- **Explanation wording** (`explanations/2`), checked against SpliceAI's README history and code (`docs/wording-review-v0.1.md`):
  - the authors' interpretation of the delta score is quoted with attribution;
  - the paper's cutoffs are noted as predating masking;
  - the masked-score recommendation is cited to its source;
  - the limitations sentence is less narrow.
- **Bundle check:** it now fails on a placeholder identifier, a mismatched minimum macOS, or missing license texts.
- **Docs:** the README and install guide separate tested platforms from unverified ones.
- **App runtime:** now Python 3.13.16 with OpenSSL 3.5.9 (BeeWare `3.13-b16`, pinned by revision and checksum), replacing Python 3.11.9 with OpenSSL 3.0.13. The SpliceAI engine stays in its own Python 3.11 environment. Earlier docs wrongly said the 3.11 runtime "gets no security fixes": Python 3.11 still receives source-only security releases until October 2027, but the bundled 3.11.9 build could not receive them.
- **Candidate:** a new disk image, built from `ef23195` with the Python 3.13.16 runtime, replaces the `def7e9f` test candidate. The old candidate is kept only as historical evidence.
- **Reproducible app builds:** the app's dependencies, including indirect ones, are installed at the versions in `uv.lock`, and the bundle check fails on any difference. Before this, a rebuild picked up a newer platformdirs from PyPI.
- **History rewritten** (2026-10-09) to remove a personal email address. Commits now use the maintainer's GitHub noreply address, and every commit ID changed. Commit IDs quoted in documents and messages were updated to the new ones.

### Known limitations and pending checks
See `docs/limitations.md` and `docs/release-v0.1.0.md`. Pending:
- an install on a second Mac, including whether a downloaded copy needs a second approval;
- macOS 14 compatibility (unverified), and the packaged app on macOS 26;
- IT-managed Macs;
- independent expert review of the explanations;
- ClinVar-based demo inputs;
