# Manual checklist: packaged app (v0.1, experimental)

Use the packaged app, not the developer tools. It takes about 10 minutes. The test files
contain **synthetic test variants at real GRCh38 positions**: they are not clinical examples.
Mark each step Pass or Fail, and note anything unexpected.

**Before you start.** Quit any running BioBridge. Open `dist/BioBridge-0.1.0.dmg` from the
project folder in Finder and drag **BioBridge** to **Applications**; choose **Replace**. A disk
image built on this Mac is not quarantined, so macOS does not ask for approval. A downloaded
copy needs the steps in `docs/install.md`. Open BioBridge from Applications. The window
should say *BioBridge is running…*, and your browser should open BioBridge.

| # | Step | Expected | Pass / Fail |
|---|---|---|---|
| 1 | **Pasted input.** Type `chr17-43057051-C-T`, tick *These coordinates are GRCh38*, then click **Run SpliceAI**. | A *Scoring…* page with a progress message, then **Results**: 1 allele scored; gene BRCA1; *The largest masked delta score is 0.99, for donor loss, at chr17:43,057,052…*; *…does not state a genome build, so BioBridge cannot verify it*; no *MOCK* banner. | |
| 2 | **Plot.** Hover over a bar, then press Tab to move between bars. | A tooltip shows the event, its masked and raw values, and its position; the same values are in the table under the plot. | |
| 3 | **VCF upload.** Click *Score more variants*. Choose `tests/model/data/runner_vs_cli_grch38.vcf`, tick the confirmation, then run. | Results: 19 alleles (13 scored, 6 not scored). Unscored rows show *Not scored* with a reason, and their scores are `NA`. *Genome build: GRCh38, as you confirmed; the file's header agrees.* Record 3 (BRCA1 chr17:43,063,331 A>G) says *Acceptor loss: set to 0.00 by SpliceAI's masking; the raw value is 0.24…*, and its plot labels that event *masked*. | |
| 4 | **CSV download.** On those results, click **Download CSV** and open the file in a text editor (Excel may turn some gene symbols into dates). | `biobridge-<job>.csv` has one row per allele and gene, `NA` for missing scores, masked and raw columns, and provenance columns (spliceai 1.3.1, model checksums, reference md5s, `build_basis`). | |
| 5 | **Progress and Cancel.** Upload `tests/model/data/runtime_50_alleles_grch38.vcf` and run it. While *Scored i of 50* is counting up, click **Cancel**. | The progress counter rises. After Cancel the page shows **Cancelled**, and no results are shown for that job. | |
| 6 | **Input errors.** Enter `chr17-43057051-C-T` and click **Run SpliceAI** without ticking the confirmation. Then replace the variant with `BRCA1 c.68_69del`, tick the confirmation, and run. | The browser first asks you to tick the confirmation. The second attempt shows an error explaining the accepted forms (HGVS is not accepted in v0.1). | |
| 7 | **Quit.** Click **Quit BioBridge** at the bottom of the page (or Quit in the window). | The page says *BioBridge is quitting*, and the BioBridge window closes. | |

**Afterwards.** Tell me which steps passed or failed. I will check your run without changing
anything: I re-score your packaged jobs' saved inputs with the development runner and require
identical results (`scripts/verify_packaged_app.py --compare-jobs`), and I read BioBridge's own
log to check that Quit left no processes behind.

**Not covered by this checklist (still pending):** GitHub CI, a clean-machine install (another
Mac or account without developer tools), and IT-managed Macs.
