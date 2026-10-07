# BioBridge 0.1.0: release readiness

**Release candidate. Not released, not tagged and not published.** The source is in a private GitHub repository. Checks on the developer's Mac (Apple M4, macOS 15.6.1) used isolated data directories created with `mktemp -d`; none of them is a clean-machine test. CI results are in [ci.md](ci.md#results).

## The candidate build

Built with `scripts/build_app.sh` on 2026-10-07, with no uncommitted changes in the packaged paths (`src/`, `pyproject.toml` and `uv.lock`).

**Two commits, two roles:**
- **Packaged source commit: `def7e9f`** (M3). The candidate app was built from it and records it in every CSV as `biobridge_commit`.
- **Later commits are not in the app** and never appear in its provenance:
  - up to `d6b3433`, they changed only documentation, tests, build and check scripts, and CI configuration;
  - the public-release preparation after that changes packaged paths: the bundle identifier, the explanation text, the minimum macOS and the license texts shipped in the app.

  `git diff --stat def7e9f HEAD -- src pyproject.toml uv.lock` shows exactly what a new build would contain beyond the candidate.
- **Rebuilding from a later commit** would record that later commit and produce a different disk image. The candidate is the one below.
- **Is a new candidate needed? For distribution, yes. For the second-Mac test, no.**
  - **The current disk image stays unchanged** as the candidate for the second-Mac test. That test checks the download, approval, setup, scoring and Quit flow.
  - **It must not be distributed.** It uses the placeholder identifier `local.biobridge.biobridge`, declares macOS 11 as its minimum, and lacks the runtime license texts. `scripts/check_app_bundle.py` now rejects it for exactly those three reasons.
  - **The next distributed disk image is a new candidate.** It is built from a clean commit with the identifier `io.github.rinatrizvanov.biobridge`, the license texts and explanation text `explanations/2`, and needs its own checks (see [Release blockers](#release-blockers)).

| Item | Value |
|---|---|
| Packaged source commit, recorded in the app | `def7e9fe9bc698a1c7fac0cb282a0b35af557660` (no uncommitted changes) |
| Source sha256 recorded in the app | `65050cbda1fcfffc258cdfa122879d8fde57aca0cf5bcd7b96fe7797ee5fefa8` |
| Disk image `dist/BioBridge-0.1.0.dmg` | 51,135,779 bytes, sha256 `bdbc41a934ab36fd7f769c1f6a8c96e3c6b5f11ed0054c6f941e0f2b9b974f90` |
| App | `BioBridge.app`, arm64, ad-hoc signed, 167 MB; `Info.plist` version 0.1.0 |

**Checks on this build:**
- The bundled `biobridge` code is identical to the commit (`diff -rq`).
- Mounted read-only, the disk image contains this build: the same build info, `Info.plist` 0.1.0, and a signature that verifies.
- Every disk image built later gets a different checksum, because the build time is recorded inside it. The checksum above identifies this candidate.

**Bundle check.** `scripts/check_app_bundle.py` runs on every build. It fails unless:
- the signature verifies (`codesign --verify --deep --strict`);
- the required files are present, with no `__pycache__`;
- no builder home path or username is embedded;
- the recorded source digest matches the bundled code;
- the `Info.plist` version equals `biobridge.__version__`.

**Builds before the commit.** They recorded `2f997da…+uncommitted changes` and the same source sha256, because their bundled code was the same as the commit's. The manual retest ran on such a build.

## Automated tests

All tests ran against the final source.

| Suite | Result |
|---|---|
| Unit and HTTP (`uv run pytest`) | 144 passed |
| Real browsers, Chromium and WebKit (`-m browser`) | 32 passed, including one real-engine run per browser |
| Real engine (`-m model`) | 28 passed: upstream README examples, runner vs upstream CLI in both masking modes, validation, chromosome ends, masking labels, job pipeline, and the real-engine browser runs |
| Lint (ruff 0.16.10, rules in `ruff.toml`: E4, E7, E9, F) | clean |

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

`scripts/verify_packaged_app.py` launches the built app with an isolated data directory and drives the interface in Chromium. On the candidate build, it passed.

| Check | Result |
|---|---|
| First setup, from a fresh engine install until the interface was ready | 67.0 s (engine install 65.3 s, mostly downloading) |
| Pasted `chr17-43057051-C-T` → results → CSV | 38.2 s, including the chr17 download; the engine itself took 6.7 s |
| Upload of `runner_vs_cli_grch38.vcf` (16 records, chr17 and chr22) → results → CSV | 31.1 s, including the chr22 download; the engine took 22.3 s |
| Progress, then Cancel (50 alleles) | "Scored 1 of 50…" was seen; Cancel left a job with no results |
| Quit from the page | 9 child processes started; none running at Quit, no survivors |
| Requests | 142, all to 127.0.0.1. The only assets were `/static/app.css` and `/static/app.js`: no CDN, no failed requests, no page errors |
| Window responsiveness | no event-loop delay over 100 ms |
| **Packaged results vs the SpliceAI runner** | both jobs were re-scored from their saved inputs with the development runner and were **identical**: upstream strings, statuses, reasons, details, warnings and CSV score columns |
| **Provenance in the CSVs** | `biobridge_commit` = `def7e9fe9bc698a1c7fac0cb282a0b35af557660`, with no `+uncommitted changes`; `biobridge_source_sha256` = `65050cbd…` |

The previous run, on a pre-commit build of the same source, gave the same results. It was faster where downloads were involved: setup 56.3 s, the pasted job 18.7 s and the upload 27.6 s.

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

## Release blockers

### Before the source repository is made public

1. **Your decision: the email address in the history.** All commits carry the author address `[personal address removed]`, so making the repository public publishes it. Changing it means rewriting the history, which changes every commit SHA, including `def7e9f`, the commit the candidate app records.
2. **A green CI run on the commit to be published** (see [ci.md](ci.md#results)).
3. **At release time:**
   - set `date-released` in `CITATION.cff` and the date in `CHANGELOG.md`;
   - tag `v0.1.0`;
   - make the repository public.

   Each of these only on your approval.

### Before the next disk image is distributed

1. **The second-Mac test** with the current candidate disk image ([second-mac-checklist-v0.1.md](second-mac-checklist-v0.1.md)). It answers three questions:
   - Does a browser-downloaded copy set up and run on a Mac other than the developer's, without developer tools?
   - Does it need a second Open Anyway, for the app after the disk image's?
   - Does provenance show the clean commit?

   When packaging, Briefcase warns that an ad-hoc-signed app "will run on this computer, but will not run on anyone else's computer". This test is what checks that warning.
2. **A new candidate built from a clean commit**, checked like this one:
   - the bundle check, which now also checks the identifier, the minimum macOS and the shipped license texts;
   - the packaged-app run against the runner;
   - a short manual retest: steps 1, 7 and 8 of the [retest checklist](retest-checklist-v0.1.md), plus the app's new identifier.
3. **Your decision: the bundled Python runtime.** The app ships Python 3.11.9 with OpenSSL 3.0.13 (January 2024). python.org publishes no newer 3.11 macOS binaries, so this runtime gets no security fixes. In the app, this Python's TLS is used only to download reference chromosomes from UCSC, verified against the macOS trust store. The engine install goes through uv, which does not use this OpenSSL. The interface is served only on 127.0.0.1. The options are:
   - accept this for an experimental v0.1, and say so in the release notes;
   - move the app's own runtime to a supported Python, such as 3.12 or 3.13. The engine environment would stay on 3.11, because TensorFlow 2.15 requires it. This means a re-lock and a full re-verification.

## Explicitly pending (tracked, not blocking an experimental release)

- **macOS 14 compatibility: unverified.** No CI image and no Mac has run it. The packaged app has not run on macOS 26.
- **IT-managed Macs** (Jamf, Santa), where Open Anyway may be unavailable.
- **Independent expert review** of the explanation wording. The [wording review](wording-review-v0.1.md) checked consistency with SpliceAI's own documentation and code; it is not that review.
- **Demo inputs based on public ClinVar records.** The test inputs are synthetic variants at real GRCh38 positions.

## Optional improvements

- **Citation:** credit by name, and ORCID if wanted. `CITATION.cff` currently lists only the alias `rinatrizvanov`. A Zenodo DOI could be added at release.
- **Smaller runtime:** remove the unused Tcl/Tk and ncurses libraries from the app (Briefcase `cleanup_paths`). The app would be smaller and ship fewer components.
- **App icon:** a BioBridge icon instead of Briefcase's default.
- **Provenance:** record the explanation text version (`explanations/2`) in provenance and the CSV.
- **More CI:** run the packaged app on macOS 26 as well. It costs extra macOS minutes on a private repository.
- **Public-repository files:** `SECURITY.md`, `CONTRIBUTING.md` and issue templates.
- **Housekeeping:** a shellcheck pass; ruff's wider rules (62 style findings); replacing `httpx` in the test client, which raises a Starlette deprecation warning.
- **Licensing:** written confirmation of the model license terms from Illumina.
