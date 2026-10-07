# 0005 — M3: interface polish, source revision in provenance, release documentation

Status: **local checks and the user's manual retest passed** (2026-10-07). An install on a second Mac, GitHub CI and IT-managed Macs are **pending**; see [release-v0.1.0.md](../release-v0.1.0.md#outstanding-checks).

## Inputs from the manual checklist

The manual checklist passed, with two exceptions:
- The plot's **0.99 label was clipped**.
- The packaged CSV reported **`biobridge_commit=unknown`**.

## Source revision in packaged provenance

- **Why it was unknown.** The packaged app has no git checkout, and it must never call git: on a Mac without developer tools, `/usr/bin/git` opens an install dialog.
- **The fix.** `scripts/build_app.sh` now runs `scripts/write_build_info.py` before packaging. That script records three facts in `src/biobridge/_build_info.json`, which is git-ignored and included in the bundle:
  - the full commit,
  - whether packaged paths (`src/`, `pyproject.toml`, `uv.lock`) had uncommitted or untracked changes,
  - a sha256 over the packaged source.
- **No invented values.** If git cannot be read, the commit is `unknown`.
- **Run time.** The app reads this file. A source checkout asks git directly.
- **New output.** Provenance and the CSV gain `biobridge_source_sha256`.
- **Guard.** `scripts/check_app_bundle.py` fails a build whose recorded digest does not match the bundled code.
- **Result.** The rebuilt app's CSV reports `2f997da3c61759fdfb6d604971dbf92927a5b738+uncommitted changes`, which is accurate, because the M3 work is not committed yet. A build made after committing will report the clean commit.

## Design pass (Anthropic frontend-design skill)

The skill was installed project-locally at `.claude/skills/frontend-design` from `anthropics/skills`, commit `41bbe19`. Its git blob hashes match upstream, its license is Apache-2.0, and it is not committed.

- **Direction:** typeset like a methods section with journal figures.
  - **Headings:** Charter, the serif bundled with macOS.
  - **Body and numbers:** the system sans with tabular figures.
  - **Tables:** journal-style rules with right-aligned numbers, and the raw score under each masked score.
  - **Per-variant panels:** explanation beside the figure, with the value table at full width below.
- **Removed:** the skill's listed templated defaults that the page had used — middle-dot meta strings, rounded cards with soft shadows, a pill label and a tinted near-black ink.
- **Kept unchanged:**
  - the 0–1 axis;
  - masked bars and raw dots;
  - the "masked" label;
  - the table of values;
  - the scientific wording, with no explanation text changed except for ties and all-zero rows (see below);
  - the stack (Starlette, Jinja2, a vanilla script);
  - local assets only (system fonts, no downloads).
- **Colour:** the chart colours were re-validated on the new surfaces (`#ffffff` light, `#161b22` dark): all checks pass, with colour-blind separation ΔE 24.7 and 26.8. Every text colour is at least 5.3:1 (WCAG AA) in both modes.

## Problems found while verifying (each reproduced or measured before fixing)

1. **Clipped 0.99 and 1.00 labels.**
   - **Cause:** a 14-unit top margin put the label baselines at y = 5.8 and y = 4.0. A new geometry test reproduced this first.
   - **Fix:** a 30-unit top margin and explicit font sizes. Cutoff meanings moved from side labels into the figure caption, which also keeps the plot readable at narrow widths.
2. **Category names too tightly spaced.** In Chromium only, the browser test found the two-line names' line boxes touching (13-unit spacing at an 11-unit font). The spacing is now 15 units.
3. **Tooltip disappeared after scrolling.** The tooltip hid itself on scroll, so a hover that scrolled the chart into view lost it (seen in Chromium). It now follows the event when the page scrolls or resizes. Escape dismisses it.
4. **A long deletion widened the results table.**
   - **Cause:** a 102-nt deletion's full REF made the table thousands of pixels wide. This was found in the screenshots; the earlier tests did not cover it.
   - **Fix:** alleles longer than 12 bases are shortened on screen (`AATACA…(102 nt)`); the CSV keeps them in full.
   - **Also:** the per-variant value table moved to full width, so it fits at desktop width.
5. **Arbitrary event named for all-zero rows.**
   - **Cause:** "Largest masked" said `0.00 AG` when all four masked scores were 0.00. Record 8 shows why that misleads: its real signal is a raw donor gain of 0.23 that masking removed.
   - **Fix:** no event is named when the largest value is 0.00 (`none` in the CSV), and ties name every event, in the table, the CSV and the explanations.

6. **Version 0.0.0 in the app's `Info.plist`.**
   - **Cause:** `briefcase update` never rewrites `Info.plist`, so the app kept the version from when it was first created.
   - **Fix:** `scripts/build_app.sh` now recreates Briefcase's generated folder (`build/biobridge/macos/app`) on every build, and `check_app_bundle.py` fails if the versions differ. The check failed on the old build before the fix.
7. **Clipped tables and notes at phone width.** Found in the 375 px screenshot, then reproduced by a new browser test at 320 px, 375 px and 200% zoom.
   - **Cause:** cells never wrapped. Each table's note is its `<caption>`, which is as wide as the table, so it was cut off together with it.
   - **Fix:**
     - Captions are limited to the visible width of the table's scrolling box (CSS container units).
     - Below 520 px, event names and positions in the per-variant value tables may wrap, but the coordinate itself and each offset stay whole.
   - **Result:** the value tables fit from 375 px up. The All alleles table still scrolls inside its own box, which the reflow rule allows for data tables.
8. **The uploaded file's name was altered.** Jinja's `capitalize` raised the first letter and lowercased the rest, so `Edge_VCF.vcf` showed as `Edge_vcf.vcf`. A browser test reproduced it, and the name is now shown exactly.
9. **Heading spacing.** "All alleles" sat closer to the buttons above it than to its own table. The space above it is larger now.

## Verification on this Mac (isolated data directories; not a clean machine)

- **Plot geometry (unit tests).** No label or dot is clipped at values 0, 0.99, 1.00, all ones, or all zeros.
- **Browser** (Playwright, Chromium and WebKit):
  - Values 0.00, 0.99, 1.00 and 0.50: every label and dot sits inside the SVG, and no labels overlap.
  - At 320 px, at 375 px, and at 200% zoom (emulated as a 640-CSS-pixel viewport at device scale 2, which is how browsers lay out a 1280 px window at 200%): no page-level horizontal scroll, labels inside the plot, and the smallest chart text at least 9 px.
  - Keyboard: Tab shows the tooltip inside the window with the right values and a visible focus outline, and Escape hides it.
  - Light and dark mode each use their own validated colours, with measured contrast at least 4.5:1.
  - No table needs sideways scrolling at 1280 px with a 102-nt deletion present.
- Captions stay readable at every width, and the per-variant value tables fit from 375 px up.
- The final suite counts, the packaged-app verification, the screenshots and the pending checks are in [release-v0.1.0.md](../release-v0.1.0.md).
