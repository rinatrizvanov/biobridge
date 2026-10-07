# BioBridge 0.1.0: release readiness

**Release candidate. Not released, not tagged, nothing pushed or published.** Everything below was checked on the developer's Mac (Apple M4, macOS 15.6.1), using isolated data directories created with `mktemp -d`. None of it is a clean-machine test.

## The candidate build

The candidate is built with `scripts/build_app.sh` from the M3 commit, with no uncommitted changes in the packaged paths (`src/`, `pyproject.toml`, `uv.lock`).

| Item | Value |
|---|---|
| Source revision recorded in the app | *recorded after building from the M3 commit* |
| Source sha256 recorded in the app | *recorded after building from the M3 commit* |
| Disk image `dist/BioBridge-0.1.0.dmg` | *size and sha256 recorded after building from the M3 commit* |
| App | `BioBridge.app`, arm64, ad-hoc signed, about 167 MB; `Info.plist` version 0.1.0 |

**Bundle check.** `scripts/check_app_bundle.py` runs on every build. It fails unless:
- the signature verifies (`codesign --verify --deep --strict`);
- the required files are present, with no `__pycache__`;
- no builder home path or username is embedded;
- the recorded source digest matches the bundled code;
- the `Info.plist` version equals `biobridge.__version__`.

**Builds before the commit.** They recorded `2f997da…+uncommitted changes`, with source sha256 `65050cbda1fcfffc258cdfa122879d8fde57aca0cf5bcd7b96fe7797ee5fefa8`. The checks below ran on such a build. The bundled code was the same as in the M3 commit, so the source digest is the same.

## Automated tests

All tests ran against the final source.

| Suite | Result |
|---|---|
| Unit and HTTP (`uv run pytest`) | 144 passed |
| Real browsers, Chromium and WebKit (`-m browser`) | 32 passed, including one real-engine run per browser |
| Real engine (`-m model`) | 28 passed: upstream README examples, runner vs upstream CLI in both masking modes, validation, chromosome ends, masking labels, job pipeline, and the real-engine browser runs |
| Lint (ruff, rules E4, E7, E9, F) | clean |

The browser layout tests cover:
- chart values of 0, 0.99 and 1.00 inside the plot, with no labels overlapping;
- 320 px, 375 px and 200% zoom, with no sideways page scroll;
- table captions that stay readable when a wide table scrolls inside its own box;
- per-variant value tables that fit from 375 px up;
- a keyboard tooltip that stays inside the window and closes with Escape;
- light-mode and dark-mode contrast;
- a 102-nt deletion that does not widen the tables;
- an uploaded file's name shown exactly as on disk.

## Packaged app, driven end to end

`scripts/verify_packaged_app.py` launches the built app with an isolated data directory and drives the interface in Chromium. On the pre-commit build of the same source, it passed.

| Check | Result |
|---|---|
| First setup, from a fresh engine install until the interface was ready | 56.3 s |
| Pasted `chr17-43057051-C-T` → results → CSV | 18.7 s, including the chr17 download |
| Upload of `runner_vs_cli_grch38.vcf` (16 records, chr17 and chr22) → results → CSV | 27.6 s, including the chr22 download |
| Progress, then Cancel (50 alleles) | "Scored 1 of 50…" was seen; Cancel left a job with no results |
| Quit from the page | 9 child processes started; none running at Quit, no survivors |
| Requests | 109, all to 127.0.0.1. The only assets were `/static/app.css` and `/static/app.js`: no CDN, no failed requests, no page errors |
| Window responsiveness | no event-loop delay over 100 ms |
| **Packaged results vs the SpliceAI runner** | both jobs were re-scored from their saved inputs with the development runner and were **identical**: upstream strings, statuses, reasons, details, warnings and CSV score columns |

**Earlier runs of the same checks** gave the same results with minor differences:
- The 0.5 s delay during engine install. Two earlier runs each logged one window delay of about 0.5 s while the engine was installing.
- Closing the lid. In one earlier run the lid was closed mid-job, and macOS slept for about 6 minutes. The power log shows clamshell sleep at 09:05:49 and a lid wake at 09:12:13. Both jobs carried on after wake and matched the runner. The watchdog did not fire, because its clock does not count time asleep. BioBridge asks macOS to stay awake while it works, but that cannot prevent sleep when the lid is closed. This is now in [limitations.md](limitations.md).

## Screenshots

`scripts/screenshots.py` takes 23 screenshots of the packaged app running the real engine:
- input and results pages, light and dark;
- the All alleles table;
- the 0.99, 1.00 and masked-zero charts;
- the keyboard tooltip;
- 375 px width and 200% zoom;
- WebKit, light and dark;
- progress and Cancel.

They are kept in a `mktemp -d` folder on the developer's Mac and are not committed, because they come from a specific run. Rerun the script to regenerate them.

## Manual checks on the developer's Mac

- **[Manual checklist](manual-checklist-v0.1.md)** (2026-10-07): **passed**, except for two findings, both since fixed and tested:
  - the 0.99 chart label was clipped;
  - the CSV reported `biobridge_commit=unknown`.
- **[Retest checklist](retest-checklist-v0.1.md)** (2026-10-07): **passed**, on the pre-commit build (source sha256 `65050cbd…`). BioBridge's own log for that session shows:
  - two jobs: a pasted variant and the 16-record VCF;
  - both identical to the SpliceAI runner, including the CSV score columns (`verify_packaged_app.py --compare-jobs`);
  - Quit cleanup: 4 child processes started, none running at Quit, no survivors.
- **Jobs from the first manual run** were scored identically by the runner as well. Their CSVs were written by the earlier code, which still named an event (`AG`) for all-zero rows. The comparison now checks CSVs only for jobs made from the current source.

## Outstanding checks

Nothing below has been done or verified.

1. **A second Apple Silicon Mac**, following [second-mac-checklist-v0.1.md](second-mac-checklist-v0.1.md). It answers three questions:
   - Does a browser-downloaded copy set up and run on a Mac other than the developer's, without developer tools?
   - Does it need a second Open Anyway, for the app after the disk image's?
   - Does provenance show the clean commit?

   When packaging, Briefcase warns that an ad-hoc-signed app "will run on this computer, but will not run on anyone else's computer". This step is what tests that warning.
2. **GitHub CI.** No workflow exists yet (`.github/workflows` is absent), and there is no GitHub remote. Writing the workflow, running it on macOS arm64 and building the disk image as a CI artifact all need a push, which needs your approval.
3. **IT-managed Macs** (Jamf, Santa), where Open Anyway may be unavailable.
4. **Independent expert review** of the explanation wording.
5. **Demo inputs based on public ClinVar records.** The current test inputs are synthetic variants at real GRCh38 positions.
6. **A real bundle identifier.** `local.biobridge` in `pyproject.toml` is a placeholder and must be replaced before any public release, followed by a rebuild and a retest.
7. **Release steps, each only on your approval:** tag `v0.1.0` locally, push, publish the disk image.
8. **Optional:** confirmation of the model license terms from Illumina.

**Known minor items:**
- ruff 0.16's wider default rule set reports 62 style findings, none in the E4/E7/E9/F rules.
- The test client emits a Starlette deprecation warning about `httpx`.
