# Continuous integration

`.github/workflows/ci.yml` runs on GitHub-hosted runners for pushes to `main`, pull requests, and manual runs. Results of actual runs are recorded under [Results](#results).

## Jobs

| Job | Runner images | What it checks |
|---|---|---|
| **Lint** | `ubuntu-24.04` | `uvx ruff@0.16.10 check .` with the rules in `ruff.toml` (E4, E7, E9, F): syntax errors, undefined names, unused imports. No project code runs. |
| **Tests** | `macos-15`, `macos-26` (Apple Silicon) | Several suites, each a separate step (listed below). |
| **Packaged app** | `macos-15` | The whole packaged app on a fresh checkout (steps listed below). |

**Tests job.** The test environment uses Python 3.13 (from `.python-version`), the app's runtime series. The real-engine suite drives the separate Python 3.11 engine environment. Each suite reports on its own:
1. **Unit and HTTP tests** (`uv run pytest`, 151 tests). They cover:
   - input validation and upload limits, and build evidence;
   - downloads (timeouts, retries, resume, checksums) and engine install retries;
   - the watchdog, and Quit cleanup of child processes;
   - results and CSV (NA never 0, masked vs rounded zeros), explanations and plot geometry;
   - build provenance, the bundle check's path rule and the release guard;
   - the HTTP security checks.
2. **Browser tests** (`pytest -m "browser and not model"`, 30 tests). They run in Chromium and WebKit with the TEST-ONLY fake engine and cover:
   - paste and upload flows, progress and Cancel, and CSV download;
   - chart values 0, 0.99 and 1.00;
   - 320 px, 375 px and 200% zoom;
   - the keyboard tooltip, and light and dark contrast.
3. **The real SpliceAI engine** (`pytest -m model`, 28 tests). The engine environment is created with `scripts/create_engine_env.sh` (hash-locked, binary-only, uv 0.11.8), and the md5-pinned UCSC chromosomes are fetched first. The tests cover:
   - the upstream README GRCh37 examples;
   - the runner matching the upstream `spliceai` CLI in raw and masked modes, with reference switching between chr17 and chr22;
   - validation and chromosome ends, and masking labels;
   - the job pipeline, and one real-engine run in each browser.

**Packaged-app job.** On a fresh checkout it:
1. builds `BioBridge.app` and its disk image with `scripts/build_app.sh`, signed ad hoc;
2. runs `scripts/check_app_bundle.py`:
   - the signature verifies;
   - the required files are present;
   - the source digest matches the recorded one;
   - the `Info.plist` version, bundle identifier and minimum macOS match `pyproject.toml`, and the identifier is not a placeholder;
   - the third-party license texts are shipped;
   - no local paths are embedded;
3. runs `scripts/verify_packaged_app.py`, which launches the built app with an isolated data folder and drives it in Chromium:
   - first setup through the app's bundled uv;
   - a pasted variant, a VCF upload, progress, Cancel and Quit;
   - every request must stay on 127.0.0.1, and no process may survive Quit;
   - both jobs are re-scored with the development runner and must be identical.

   The app and the disk image stay on the runner. **Nothing is uploaded.**

**Security:**
- The workflow's token is read-only and the workflow uses no secrets.
- Checkout doesn't keep the token on disk.
- Each action is pinned to the full commit of a release: checkout v7.0.1, setup-uv v10.2.0 and cache v6.1.0, the latest releases on 2026-10-07.

**Caches:**
- uv downloads, keyed on `uv.lock` and `engine.lock`;
- the compressed UCSC test chromosomes, keyed on `scripts/fetch_test_reference.py`;
- Playwright browsers, keyed on `uv.lock`.

A cache is saved only when its job succeeds.

## The bundle check on GitHub's runners

On GitHub's macOS runners, the builder's username is `runner` and its home is `/Users/runner`. The original check failed there for the wrong reasons:
- **The bare username.** It searched every file for the bare username, and "runner" appears in 70 files of the candidate bundle, including BioBridge's own `runner.py`.
- **Upstream home paths.** It searched every file for the home directory, and 10 upstream files name `/Users/runner/...` from their own builds on GitHub: Briefcase's stub, markupsafe, fontTools, `uv` and uv's SBOM.

The check now reports:
- the build checkout's path, anywhere in the bundle;
- the builder's home directory, only in files the build writes: BioBridge's code, `Info.plist`, install-time metadata and generated `#!` scripts.

It no longer searches for a bare username. The candidate bundle passes the new rule both as built on the developer's Mac and as if it had been built on a runner. Unit tests cover what must and must not be reported.

**A second bug.** Rehearsing the packaged-app job in a fresh local clone before the first push found one more problem. The check imports BioBridge from the bundle, and on a never-launched build Python then wrote `__pycache__`, with the checkout path, into the bundle it was checking. The check now never writes bytecode, and a test asserts that it leaves the bundle unchanged (`b110133`).

## Platform coverage

| Platform | Coverage |
|---|---|
| macOS 15, Apple Silicon | CI: lint, all test suites, and the packaged app. By hand on the developer's M4 with macOS 15.6.1, including the downloaded-app approval flow. |
| macOS 26, Apple Silicon | CI: all test suites. **The packaged app is not run on macOS 26**, by CI or by hand. |
| macOS 14, Apple Silicon | **Unverified.** It is the documented minimum, but GitHub's `macos-14` image is deprecated and no macOS 14 Mac has been used. Compatibility with macOS 14 stays explicitly unverified until a Mac running it completes the [second-Mac checklist](second-mac-checklist-v0.1.md). |
| Intel Macs | Not a target; untested. |
| Linux, Windows | Not supported. Linux runs only the lint job, which executes no project code. |

## What CI does not check

1. **macOS approval steps.** A CI build is never downloaded, so macOS never quarantines it. Gatekeeper, Open Anyway, the downloaded-copy approval and IT-managed Macs are covered only by hand, through the [second-Mac checklist](second-mac-checklist-v0.1.md). IT-managed Macs remain pending.
2. **The candidate disk image itself.** CI builds its own app from each commit. The candidate for the second-Mac test is the disk image built on the developer's Mac from `def7e9f` (see [release-v0.1.0.md](release-v0.1.0.md)).
3. **The packaged app on macOS 26.**
4. **Network dependence.** A run with empty caches downloads from PyPI, the uv Python builds, BeeWare's support packages, UCSC and Playwright's servers. Downloads retry with backoff, but an outage fails the affected step.
5. **Shell checks.** No shellcheck pass has been run on the workflow's shell lines or on the scripts.
6. **Wider lint rules.** Ruff 0.16's broader default rules report 62 style findings; only E4, E7, E9 and F are enforced.

**Cost.** In a private repository, GitHub charges macOS runner minutes at a higher rate than Linux minutes against the account's included minutes. A full run uses roughly three macOS jobs; see [Results](#results) for measured times.

## Results

### The replacement private repository

The replacement repository was created on 2026-10-09, private, with the cleaned history.

**Run 38011119744**, for the first push (head `987c04d`, a documentation commit on top of the candidate `ef23195`): **every job passed.** Every step succeeded, and the run uploaded no artifacts. The run's commit metadata carries only the noreply address.

| Job | Operating system | Result | Duration |
|---|---|---|---|
| Lint | Ubuntu 24.04.5 | passed | 8 s |
| Tests | macOS 15.7.9 (24G830) | unit and HTTP: 152 passed; browser: 30 passed; real engine: 28 passed | 8 min 7 s |
| Tests | macOS 26.6.2 (25G83) | unit and HTTP: 152 passed; browser: 30 passed; real engine: 28 passed | 7 min 46 s |
| Packaged app | macOS 15.7.9 | build and bundle check passed; packaged run passed | 3 min 22 s |

**Packaged-app job:**
- **The build:**
  - commit `987c04d`, with no uncommitted changes;
  - source sha256 `1f90830a…`, the candidate's packaged code;
  - runtime Python 3.13.16 with OpenSSL 3.5.9;
  - every bundled package at its `uv.lock` version.
- **The packaged run:**
  - first setup took 13.7 s, the pasted variant 10.8 s and the upload 36.4 s;
  - all 109 requests stayed on 127.0.0.1, with no failed requests or page errors;
  - no process survived Quit;
  - both jobs were identical to the runner.

### The earlier copy of the private repository

That copy was deleted on 2026-10-09, so that no copy of the old history, which contained a personal email address, or of its CI records stays on GitHub. The runs below are no longer viewable. They ran on the same commits before their IDs changed; the IDs given here are the current ones.

**Run for `3a6f738`** (2026-10-07), the candidate's packaged source: **every job passed.** Every step succeeded, and the run uploaded no artifacts.

| Job | Operating system | Result | Duration |
|---|---|---|---|
| Lint | Ubuntu 24.04.5 | passed | 9 s |
| Tests | macOS 15.7.9 (24G830) | unit and HTTP: 151 passed; browser: 30 passed; real engine: 28 passed | 7 min 52 s |
| Tests | macOS 26.6.2 (25G83) | unit and HTTP: 151 passed; browser: 30 passed; real engine: 28 passed | 7 min 38 s |
| Packaged app | macOS 15.7.9 | build and bundle check passed; packaged run passed | 3 min 10 s |

**Which Python ran where:**
- **Test environment:** Python 3.13.15, the runner's own copy. The tests need only the 3.13 series, matching the app's runtime.
- **Engine environment:** Python 3.11.15.
- **The packaged app's bundled runtime:** Python 3.13.16 with OpenSSL 3.5.9, as printed by the bundle check.

**Packaged-app job:**
- **The build:** commit `3a6f738`, with no uncommitted changes, and source sha256 `1f90830a…`. That is the same digest as the candidate disk image built on the developer's Mac.
- **The packaged run:**
  - first setup took 15.4 s, the pasted variant 10.5 s and the upload 37.3 s;
  - all 110 requests stayed on 127.0.0.1, with no failed requests or page errors;
  - no process survived Quit;
  - both jobs were identical to the runner.

**Run for `55316c0`** (2026-10-07): **every job passed.** Every step succeeded, and the run uploaded no artifacts.

| Job | Operating system | Result | Duration |
|---|---|---|---|
| Lint | Ubuntu 24.04.5 | passed | 7 s |
| Tests | macOS 15.7.9 (24G830) | unit and HTTP: 150 passed; browser: 30 passed; real engine: 28 passed | 7 min 26 s |
| Tests | macOS 26.6.2 (25G83) | unit and HTTP: 150 passed; browser: 30 passed; real engine: 28 passed | 8 min 9 s |
| Packaged app | macOS 15.7.9 | build and the stricter bundle check passed; the packaged run passed | 3 min 7 s |

**Packaged-app job:**
- **The build:**
  - commit `55316c0`, with no uncommitted changes;
  - identifier `io.github.rinatrizvanov.biobridge` and minimum macOS 14.0;
  - the shipped license texts present.
- **The packaged run:**
  - first setup took 14.3 s, the pasted variant 11.8 s and the upload 41.2 s;
  - all 114 requests stayed on 127.0.0.1;
  - no process survived Quit;
  - both jobs were identical to the runner.

**Run for `b110133`** (2026-10-07), the first run: **every job passed.**

| Job | Image (operating system) | Result | Duration |
|---|---|---|---|
| Lint | `ubuntu-24.04` (Ubuntu 24.04.5) | passed | 10 s |
| Tests | `macos-15-arm64` (macOS 15.7.9, 24G830) | unit and HTTP: 148 passed; browser: 30 passed; real engine: 28 passed | 8 min 27 s |
| Tests | `macos-26-arm64` (macOS 26.6.2, 25G83) | unit and HTTP: 148 passed; browser: 30 passed; real engine: 28 passed | 8 min 6 s |
| Packaged app | `macos-15-arm64` (macOS 15.7.9) | build, ad-hoc signature and bundle check passed; packaged run passed (details below) | 3 min 29 s |

**Packaged-app job:**
- **Bundle check.** The app records commit `b110133`, no uncommitted changes, and source sha256 `65050cbd…`. That is the same digest as the candidate disk image's, so CI built and ran exactly the candidate's packaged code.
- **Timings.** First setup took 14.4 s, the pasted variant 9.9 s and the 16-record upload 37.8 s.
- **Requests.** All 111 stayed on 127.0.0.1, with no failed requests or page errors.
- **Cancel and Quit.** Cancel left a job with no results. Quit started 9 child processes and left no survivors.
- **Results.** Both jobs were identical to the development runner.

**The rest of the run:**
- **Uploads:** none. The run has no artifacts, and the repository has no releases or tags.
- **Caches:** this first run started with empty caches. The downloads from PyPI, UCSC, BeeWare and Playwright all succeeded.
- **Minutes:** the job durations add up to about 20 macOS minutes and under 1 Linux minute. GitHub's run-timing API reported 0 billable minutes; the account's billing page shows actual usage.

## Running the same checks locally

```sh
uvx ruff@0.16.10 check .
uv sync --locked && uv run pytest
uv run playwright install chromium webkit && uv run pytest -m "browser and not model"
scripts/create_engine_env.sh && uv run python scripts/fetch_test_reference.py readme-grch37 grch38-chr17-chr22 \
  && uv run pytest -m model
scripts/build_app.sh   # replaces build/ and dist/BioBridge-<version>.dmg: keep a copy of a candidate first
T=$(mktemp -d -t biobridge-packaged)
uv run python scripts/verify_packaged_app.py build/biobridge/macos/app/BioBridge.app "$T"
```
