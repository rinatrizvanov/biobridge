# 0003 — M2: local web interface

Status: **local checks passed** (2026-10-06); GitHub CI pending; the packaged app's interface still needs a manual job run.

## Delivered (approved v0.1 scope)

- **Input:**
  - Pasting one variant, or uploading a VCF/VCF.gz.
  - A GRCh38 confirmation, required by the browser and checked again on the server.
  - Fast checks before a job is queued: one input source, confirmation, variant format, upload size, and size after decompression. Input errors are shown on the form.
- **Jobs:**
  - One job at a time on a background thread, with live progress: checking input → downloading or preparing chromosomes → loading the model → "Scored i of N".
  - **Cancel** stops the job's whole engine process group.
  - Failures and cancellations are shown as such; partial results are never shown as complete.
  - Every job runs under the M1 watchdog.
- **Results:**
  - A build-basis sentence ("…the input does not state a genome build, so BioBridge cannot verify it" when that is the case) and the frequent-REF-mismatch warning.
  - A summary table with masked scores and raw values in brackets, where `NA` means not available.
  - For each variant: deterministic explanations (`biobridge.explain`, `explanations/1`), the four-score plot, and a table with the same values.
  - Fixed "About these scores" text and limitations, provenance, and CSV download.
- **Plot** (`biobridge.web.plot`): masked bars and raw dots on a fixed 0–1 axis, with solid hairline reference lines labelled 0.2 high recall, 0.5 recommended and 0.8 high precision.
  - **Data marks:** bars at most 24 px wide with 4 px rounded tops; dots with a 2 px ring in the surface colour.
  - **Labels:** a masked zero is labelled "masked"; missing values are never drawn.
  - **Legend and tooltip:** a legend, and a tooltip on hover and keyboard focus.
  - **Accessibility:** SVG title and description.
  - **Colours:** CSS tokens only. The palette was validated with the dataviz validator: masked `#2a78d6`/`#3987e5` and raw `#eb6834`/`#d95926`, with colour-blind separation ΔE 24.7 (light) and 26.8 (dark), and ≥ 3:1 contrast in both modes.
- **Explanation wording:**
  - The fixed text says what a delta score is: not a confidence level, not a chance of disease.
  - The fixed text gives the cutoffs as characterised in the paper, and the limitations: no transcript outcome, no pathogenicity, RNA evidence needed, not a diagnostic, no ACMG criteria.
  - Per-row text gives absolute positions and forward-strand offsets.
  - "Set to 0.00 by SpliceAI's masking; the raw value is …" is kept apart from "Below 0.005 (shown as 0.00…)".
  - A test scans all generated text for "confidence", "%", "pathogenic", "benign", "likely", "exon skipping", upstream/downstream, and exon or intron numbers.
- **Security:**
  - Listens on 127.0.0.1 only and checks the Host header.
  - A one-time `/auth?t=` link becomes an HttpOnly, SameSite=Strict cookie.
  - POSTs need the right Origin and a CSRF field.
  - Content-Security-Policy with no inline script or style, and no CORS.
  - Upload size is checked from Content-Length before parsing.
- **Launcher:** after setup it serves the interface and opens it through a one-time link; "Open in browser" mints a fresh link. An activity assertion is held during setup **and during every job**, so App Nap cannot throttle work while the browser is in front. Quit (window, page, or SIGTERM) cancels the job and stops all processes.
- **Release guard:** the fake test engine and its `mock` flag exist only under `tests/`. Tests check that the app's job manager defaults to the real runner and that the packaged sources exclude `tests/`. Results from the test engine show "MOCK — NOT MODEL OUTPUT".

## Deviations from the plan's library choices (same scope)

- **Starlette instead of FastAPI:** only Starlette's routing and templating are used, so the pydantic dependency is avoided.
- **A small vanilla script instead of vendored htmx:** progress polling and tooltips are about 80 lines with no third-party code, which keeps the CSP strict.
- **Hand-built SVG instead of matplotlib:** a four-bar chart needs neither numpy nor matplotlib in the app bundle, and gets exact control of the marks and accessibility.

## Problems found by real-browser and bundle checks (each diagnosed before changing anything)

1. **Every form POST was blocked in both browsers.** `Referrer-Policy: no-referrer` makes browsers send `Origin: null` on form POSTs, as the Fetch spec requires; this was captured in Chromium and WebKit. The policy is now `same-origin`: BioBridge's own POSTs carry the real Origin, the Origin check stays strict, and other sites still get no referrer. The HTTP-level tests had passed, because they set the header themselves.
2. **No progress shown during the first variant.** The engine announces scoring before the first variant finishes, and the pipeline ignored that event, so the page said "Loading the SpliceAI model…" while it was scoring. It now shows "Scored 0 of N" as soon as scoring starts.
3. **The results page was 521 px wide at a 375 px phone width.** The per-variant value table was not inside a scroll container; now it is.
4. **New build-machine path leaks.** The `idna` and `uvicorn` console scripts embedded the build machine's home path, and the bundle check failed the build. The cleanup rule is now structural: everything in `app_packages/bin` except `uv` is removed.

## Local checks (passed on this Mac, 2026-10-06)

- **Unit, model and lint:** 131 unit tests (including 15 HTTP-level interface tests and 30 explanation and plot tests), 26 model tests (real engine), and `ruff --select F,E9`.
- **Browser** (Playwright, Chromium and WebKit; 16 tests):
  - Paste and upload flows; the required confirmation; the decompressed-size error.
  - Progress then results; the MOCK watermark; unscored rows with `NA` and their reason; the masked-zero sentence and plot label.
  - Plot tooltips on hover and keyboard focus; the actual CSV download; Cancel stopping the engine; no page-level horizontal scroll at 375 px.
  - One **real-engine** run per browser: 8.0 s (Chromium) and 6.9 s (WebKit) from click to results, with no MOCK banner, donor loss 0.99, and a CSV from spliceai 1.3.1.
- **Packaged-app smoke test:** the build-folder app, launched with `open` against an isolated `mktemp -d` data directory on this Mac (not a clean machine).
  - Setup and engine install took 49.5 s, and then the web server was ready.
  - The server listens on 127.0.0.1 only. Without a session it returns 403; with a bad token, 403; with a foreign Host, 400.
  - SIGTERM: the app exits with no survivors, and the port closes.

## Remaining

- **The packaged app's interface has not yet run a job.** The smoke test checked setup, the guard and Quit from outside. The interface code is identical to what the real-engine browser tests ran from source. It is a manual step for M3.
- **GitHub CI** is pending.
- **Clean-machine verification** and **IT-managed Macs** remain unverified.
- **Test-only dependency warning:** Starlette's TestClient warns that `httpx` support is deprecated in favour of `httpx2`. This affects tests only.
