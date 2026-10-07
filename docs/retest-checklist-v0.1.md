# Retest checklist: interface polish (v0.1.0 release candidate)

This checklist takes about 10 minutes. Install `dist/BioBridge-0.1.0.dmg` over the previous version: quit BioBridge, open the `.dmg` from the project's `dist/` folder in Finder, drag BioBridge to Applications, and choose **Replace**. A disk image built on this Mac does not ask for approval. Your existing setup is reused. The test files are synthetic variants at real GRCh38 positions, not clinical examples.

| # | Check | Expected | Pass / Fail |
|---|---|---|---|
| 1 | Paste `chr17-43057051-C-T`, tick the GRCh38 confirmation, and run. | In the chart, the **0.99** label above *DL* is fully visible. The *Largest masked* column reads `0.99 DL`. | |
| 2 | Upload `tests/model/data/runner_vs_cli_grch38.vcf` and run. | The summary starts `runner_vs_cli_grch38.vcf:`, the file name exactly as on disk. Record 4's **1.00** label is fully visible. In the *All alleles* table every column fits without scrolling sideways. Record 16 reads `AATACA…(102 nt)>A`. Rows whose masked scores are all 0.00 (records 5, 6, 8 and 9) show `0.00` with no event name. | |
| 3 | Make the browser window as narrow as it goes, then wide again. | The page never scrolls sideways. The *All alleles* table may scroll inside its own box, but the note under it stays readable. Each record's value table fits without scrolling; positions may wrap onto two lines. Chart labels stay inside the chart and readable. | |
| 4 | Zoom to 200% (press ⌘+ until the browser shows 200%). Then press ⌘0. | Text and charts grow without clipping or overlapping labels, and the page does not scroll sideways. | |
| 5 | Click once inside a chart, then press Tab to move between its events. Press Escape. | Each focused event gets a visible outline. A tooltip inside the window shows the event, its masked and raw values and its position. Escape hides it. | |
| 6 | Switch macOS between Light and Dark (System Settings › Appearance) with a results page open. | Both modes are easy to read. Masked bars are blue and raw dots orange in both modes. | |
| 7 | Download the CSV and open it in a text editor. | `biobridge_commit` is a 40-character commit, followed by `+uncommitted changes` if the build had uncommitted changes, instead of `unknown`. `biobridge_source_sha256` is filled. A row with all masked scores at 0.00 has `max_DS_masked_event` = `none`. | |
| 8 | Quick regression: upload `tests/model/data/runtime_50_alleles_grch38.vcf`, click **Cancel** while it counts, then click **Quit BioBridge**. | Progress counts up; Cancel shows *Cancelled*; Quit closes BioBridge. | |

Tell me which steps passed or failed. I will check your jobs against the SpliceAI runner, and Quit cleanup from BioBridge's own log, without changing anything.

**Still pending, not covered here:** GitHub CI, a clean-machine install, IT-managed Macs, and whether a downloaded copy needs a second approval.
