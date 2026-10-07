# 0004 — M3: packaged app with the interface

Status: **automated packaged-app checks passed** (2026-10-06). **The manual checklist passed** (2026-10-07) except for two findings, both fixed in [0005](0005-m3-polish-and-provenance.md): a clipped 0.99 chart label and `biobridge_commit=unknown` in the CSV. GitHub CI, clean-machine verification and IT-managed Macs are **pending**.

## Build

- Briefcase 0.4.5 builds an ad-hoc-signed arm64 `BioBridge.app` (167 MB) and `dist/BioBridge-0.0.0.dmg` (51 MB).
- `scripts/check_app_bundle.py` passes: signature valid, required files present, no `__pycache__`, and no builder home path or username.
- The bundled `biobridge` package is byte-for-byte identical to `src/biobridge` (`diff -rq`).
- `app_packages/bin` keeps only `uv`; other dependency console scripts embedded the build machine's path.

## Interface assets are local only

- **Static check:** templates reference only `/static/app.css` and `/static/app.js`. No external URL appears anywhere in the interface code; the SVG namespace identifier is never fetched. The CSS uses system fonts (no `@font-face`, `@import` or `url()`).
- **Enforced:** Content-Security-Policy `default-src 'self'`, with no inline script or style.
- **Observed in the packaged run:** 103 requests, all to `127.0.0.1:<port>`, of which the assets were `/static/app.css` and `/static/app.js`. No request failed, and the page logged no errors, including CSP violations.

## Automated packaged-app verification

Run with `scripts/verify_packaged_app.py`: the packaged app, launched with `open` against an isolated `mktemp -d` data directory on the developer's Mac (not a clean machine), driven in Chromium.

| Check | Result |
|---|---|
| Setup (fresh engine install) until the interface was ready | 45.7 s |
| Pasted `chr17-43057051-C-T` → results → CSV | 13.7 s, including the chr17 download |
| VCF upload (16 records, chr17 and chr22, unscored cases included) → results → CSV | 28.2 s, including the chr22 download |
| Progress and Cancel (50 alleles) | "Scored 1 of 50…" seen; Cancel gave **Cancelled**, and that job has no results |
| Quit from the page | the app exited; `quit_cleanup`: 9 children started, none running, **no survivors** |
| UI event-loop delays over 100 ms | none |
| **Packaged results vs runner** | both completed jobs re-scored from their saved `input.vcf` with the development runner (`.engine-venv`): **identical** upstream strings, statuses, reasons, details, warnings and model checksums; identical CSV score columns. In this build the `biobridge_commit` provenance field was `unknown`; 0005 embeds the real revision at build time. |

The automation uses `BIOBRIDGE_AUTH_URL_FILE`, which only takes effect when whoever launches the app sets it. It writes the one-time 127.0.0.1 sign-in link to a file with mode 0600 instead of opening a browser.

## Manual checklist

`docs/manual-checklist-v0.1.md` covers pasted input, the plot tooltip, VCF upload, CSV download, progress and Cancel, input errors, and Quit, with exact expected results. After the user's run, `scripts/verify_packaged_app.py --compare-jobs` checks the user's packaged jobs against the runner. It reads the data folder and writes only to a new folder.

## Pending (not verified)

- GitHub CI: no remote; nothing pushed.
- A clean-machine install: another Mac, or an account without developer tools.
- IT-managed Macs (Jamf, Santa).
- Whether a *downloaded* copy needs a second Open Anyway for the app after the disk image's.
- Remaining M3 items from the plan: demo inputs from public ClinVar IDs, and a local `v0.1.0` tag (only when asked). The README, interpreting-results and limitations pages, CITATION.cff and THIRD_PARTY_LICENSES were written in 0005.
