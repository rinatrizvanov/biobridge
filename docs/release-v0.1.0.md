# BioBridge 0.1.0: release readiness

**Release candidate. Not released, not tagged and not published.** The source is in a private GitHub repository. Checks on the developer's Mac (Apple M4, macOS 15.6.1) used isolated data directories created with `mktemp -d`; none of them is a clean-machine test. CI results are in [ci.md](ci.md#results).

## The candidate build

**Candidate: built on 2026-10-07 from packaged source commit `3a6f738`.** It was built with `scripts/build_app.sh`, with no uncommitted changes in the packaged paths (`src/`, `pyproject.toml` and `uv.lock`). This is the disk image for the second-Mac test and for any later distribution.

| Item | Value |
|---|---|
| Packaged source commit, recorded in the app and in every CSV (`biobridge_commit`) | `3a6f738bf74a7551327f7cc007c86339dcabf110` (no uncommitted changes) |
| Source sha256, recorded in the app | `1f90830a31c88fb541f126be430280839dde5e1af4adde2b6cc3dc1c2ed68a40` |
| Disk image `dist/BioBridge-0.1.0.dmg` | 49,220,279 bytes, sha256 `7fc22fedd200bda9347e829bc4e15230298c950d6961de0516d945d50f488b3d` |
| App | `BioBridge.app`, arm64, ad-hoc signed, 164 MB; version 0.1.0; identifier `io.github.rinatrizvanov.biobridge`; minimum macOS 14.0 |
| App runtime | Python 3.13.16 with OpenSSL 3.5.9 (BeeWare `3.13-b16`), read from the built app ([0007](decisions/0007-app-runtime-python-3.13.md)) |
| SpliceAI engine | installed at setup in a separate Python 3.11 environment |

**Checks on this build:**
- **The bundle check** passes. It covers:
  - the signature;
  - the required files and license texts, with no `__pycache__`;
  - no embedded local paths;
  - the source digest;
  - the version, identifier and minimum macOS against `pyproject.toml`;
  - the Python license text matching the bundled runtime.
- **The bundled `biobridge` code** is identical to the commit (`diff -rq`).
- **The disk image itself.** Mounted read-only, it contains this build:
  - commit `3a6f738`, with no uncommitted changes;
  - identifier `io.github.rinatrizvanov.biobridge` and minimum macOS 14.0;
  - runtime 3.13.16;
  - the six license files;
  - a signature that verifies.
- **The checksum** identifies this candidate. Every later build gets a different one, because the build time is recorded inside the disk image.
- **CI.** CI built the same packaged source from `3a6f738`, with source sha256 `1f90830a…`, and passed every job ([ci.md](ci.md#results)).

**Commits after `3a6f738` are documentation only.** They are not in the app and never appear in its provenance. `git diff --stat 3a6f738 HEAD -- src pyproject.toml uv.lock .python-version` prints nothing while that holds.

**Superseded candidate, kept only as historical evidence:**
- **The disk image:** built from `def7e9f` (M3) on 2026-10-07; source sha256 `65050cbd…`; 51,135,779 bytes; sha256 `bdbc41a934ab36fd7f769c1f6a8c96e3c6b5f11ed0054c6f941e0f2b9b974f90`.
- **Where it is kept:** read-only on the developer's Mac as `dist/historical/BioBridge-0.1.0-def7e9f-superseded-test-candidate.dmg`. It is not in the repository.
- **Not for testing or distribution.** It has the placeholder identifier `local.biobridge.biobridge`, a declared minimum of macOS 11, no runtime license texts, and the frozen Python 3.11.9 runtime with OpenSSL 3.0.13. The current bundle check rejects it.
- **What it was used for:** the manual checklist and the retest earlier on 2026-10-07 ran on it, or on pre-commit builds of the same source.

## Automated tests

All tests ran against the candidate's source (`3a6f738`). They ran on the developer's Mac and in CI on macOS 15.7.9 and 26.6.2. The test environment uses Python 3.13, the app's runtime; the engine tests use the Python 3.11 engine environment.

| Suite | Result |
|---|---|
| Unit and HTTP (`uv run pytest`) | 151 passed |
| Real browsers, Chromium and WebKit (`-m "browser and not model"`) | 30 passed |
| Real engine (`-m model`) | 28 passed: upstream README examples, runner vs upstream CLI in both masking modes, validation, chromosome ends, masking labels, job pipeline, and one real-engine run per browser |
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

`scripts/verify_packaged_app.py` launches the built app with an isolated data directory and drives the interface in Chromium. On the candidate (`3a6f738`, developer's Mac), it passed. The CI packaged-app job passed as well, on its own build of the same source.

| Check | Result |
|---|---|
| First setup, from a fresh engine install until the interface was ready | 46.2 s |
| Pasted `chr17-43057051-C-T` → results → CSV | 24.8 s, including the chr17 download |
| Upload of `runner_vs_cli_grch38.vcf` (16 records, chr17 and chr22) → results → CSV | 29.7 s, including the chr22 download |
| Progress, then Cancel (50 alleles) | "Scored 1 of 50…" was seen; Cancel left a job with no results |
| Quit from the page | 9 child processes started; none running at Quit, no survivors |
| Requests | 121, all to 127.0.0.1. The only assets were `/static/app.css` and `/static/app.js`: no CDN, no failed requests, no page errors |
| Window responsiveness | no event-loop delay over 100 ms |
| **Packaged results vs the SpliceAI runner** | both jobs were re-scored from their saved inputs with the development runner and were **identical**: upstream strings, statuses, reasons, details, warnings and CSV score columns |
| **Provenance in the CSVs** | `biobridge_commit` = `3a6f738bf74a7551327f7cc007c86339dcabf110`, with no `+uncommitted changes`; `biobridge_source_sha256` = `1f90830a…` |

The superseded `def7e9f` candidate, with its Python 3.11.9 runtime, passed the same checks earlier on 2026-10-07.

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
- **[Retest checklist](retest-checklist-v0.1.md)** (2026-10-07): **passed**, on a pre-commit build of the superseded `def7e9f` source (source sha256 `65050cbd…`, Python 3.11.9 runtime). BioBridge's own log for that session shows:
  - two jobs: a pasted variant and the 16-record VCF;
  - both identical to the SpliceAI runner, including the CSV score columns (`verify_packaged_app.py --compare-jobs`);
  - Quit cleanup: 4 child processes started, none running at Quit, no survivors.
- **The current candidate (`3a6f738`) has had no manual run yet**; see [Release blockers](#release-blockers).
- **Jobs from the first manual run** were scored identically by the runner as well. Their CSVs were written by the earlier code, which still named an event (`AG`) for all-zero rows. The comparison now checks CSVs only for jobs made from the current source.

## Release blockers

### Before the source repository is made public

1. **Your decision: the email address in the history.** All commits carry the author address `[personal address removed]`, so making the repository public publishes it. Changing it means rewriting the history, which changes every commit SHA, including `3a6f738`, the commit the candidate app records.
2. **A green CI run on the last code commit before publishing.** `3a6f738` is green ([ci.md](ci.md#results)). Documentation-only commits after it skip CI.
3. **At release time:**
   - set `date-released` in `CITATION.cff` and the date in `CHANGELOG.md`;
   - tag `v0.1.0`;
   - make the repository public.

   Each of these only on your approval.

### Before the next disk image is distributed

1. **The second-Mac test** with the candidate disk image from `3a6f738`, sha256 `7fc22fed…` ([second-mac-checklist-v0.1.md](second-mac-checklist-v0.1.md)). It answers three questions:
   - Does a browser-downloaded copy set up and run on a Mac other than the developer's, without developer tools?
   - Does it need a second Open Anyway, for the app after the disk image's?
   - Does provenance show the clean commit?

   When packaging, Briefcase warns that an ad-hoc-signed app "will run on this computer, but will not run on anyone else's computer". This test is what checks that warning.
2. **A short manual retest of the candidate on the developer's Mac:** steps 1, 7 and 8 of the [retest checklist](retest-checklist-v0.1.md). The automated checks have passed; no person has used this build yet.
3. **Done: a new candidate built from a clean commit.** It is built from `3a6f738` with the final identifier, minimum macOS, license texts and runtime. The bundle check, the disk-image inspection, the packaged-app run and CI all passed (see [The candidate build](#the-candidate-build)).
4. **Done: the bundled Python runtime is updated.** The app's own runtime is now Python 3.13.16 with OpenSSL 3.5.9, verified from the binaries. The SpliceAI engine stays on Python 3.11. See [0007](decisions/0007-app-runtime-python-3.13.md).

   **Correction.** An earlier version of this page said the bundled 3.11 runtime "gets no security fixes" because Python 3.11 had no newer macOS binaries. That was too broad:
   - Python 3.11 still receives security fixes, as source-only releases until October 2027 (3.11.16 in August 2026).
   - What did not receive them was the bundled build: python.org's last 3.11 macOS binary, 3.11.9, with OpenSSL 3.0.13.

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
