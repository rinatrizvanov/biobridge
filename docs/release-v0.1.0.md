# BioBridge 0.1.0: release record and pending checks

**Source release v0.1.0, 2026-10-10** (git tag `v0.1.0`, Apache-2.0).

**No disk image is published.** The candidate disk image described below is held back until the installation checks in the next section are done.

Checks on the developer's Mac (Apple M4, macOS 15.6.1) used isolated data directories created with `mktemp -d`; none of them is a clean-machine test. CI results are in [ci.md](ci.md#results).

## Pending installation and platform checks

None of these has been done.

**Installation. These block publishing a disk image.**
1. **An install on a second Apple Silicon Mac**, from a browser download, with the candidate disk image (`ef23195`, sha256 `3dadda61…`). Follow [second-mac-checklist-v0.1.md](second-mac-checklist-v0.1.md). It answers three questions:
   - Does a downloaded copy set up and run on a Mac other than the developer's, without developer tools?
   - Does macOS ask for a second Open Anyway, for the app after the disk image's?
   - Does provenance show the clean commit?

   When packaging, Briefcase warns that an ad-hoc-signed app "will run on this computer, but will not run on anyone else's computer". This test is what checks that warning.
2. **Macs managed by an institution** (for example with Jamf or Santa), where Open Anyway may be unavailable. Untested.

**Platforms:**

| Platform | Status |
|---|---|
| macOS 15, Apple Silicon | Tested by hand on one Mac (15.6.1); test suites and packaged app in CI (15.7.9) |
| macOS 26, Apple Silicon | Test suites pass in CI (26.6.2). **The packaged app has not been run.** |
| macOS 14, Apple Silicon | **Unverified.** It is the documented minimum, but nothing has been run on it. |
| Intel Macs, Windows, Linux | Not supported |

## The candidate build

**Commit IDs in this repository.** Its history was rewritten on 2026-10-09 to remove a personal email address, so every commit ID changed. All IDs in this document refer to the current history. Disk images built before that date record the earlier IDs of the same commits. The mapping between the two is kept privately by the maintainer.

**Candidate: built on 2026-10-09 from commit `ef23195`.** It was built with `scripts/build_app.sh`, with no uncommitted changes. The app's dependencies are installed at the versions in `uv.lock`. This is the disk image for the second-Mac test and for any later distribution.

| Item | Value |
|---|---|
| Commit recorded in the app and in every CSV (`biobridge_commit`) | `ef23195c912f80253f0f1ac9f78680737d64eec2` (no uncommitted changes) |
| Source sha256, recorded in the app | `1f90830a31c88fb541f126be430280839dde5e1af4adde2b6cc3dc1c2ed68a40` |
| Disk image `dist/BioBridge-0.1.0.dmg` | 49,220,411 bytes, sha256 `3dadda61f89c1aeacac62e4ed759c1f39106b2ac62f39966b705cfa1882e2d3b` |
| App | `BioBridge.app`, arm64, ad-hoc signed, 164 MB; version 0.1.0; identifier `io.github.rinatrizvanov.biobridge`; minimum macOS 14.0 |
| App runtime | Python 3.13.16 with OpenSSL 3.5.9 (BeeWare `3.13-b16`), read from the built app ([0007](decisions/0007-app-runtime-python-3.13.md)) |
| SpliceAI engine | installed at setup in a separate Python 3.11 environment |

**The packaged code is that of `3a6f738`.** `ef23195` changed only the build and check scripts, which are not in the app. The packaged paths (`src/`, `pyproject.toml`, `uv.lock`, `.python-version`) are identical, and so is the source sha256.

**Checks on this build:**
- **The bundle check** passes. It covers:
  - the signature;
  - the required files and license texts, with no `__pycache__`;
  - no embedded local paths;
  - the source digest;
  - the version, identifier and minimum macOS against `pyproject.toml`;
  - the Python license text matching the bundled runtime;
  - every bundled package's version matching `uv.lock`.
- **The disk image itself.** Mounted read-only, it contains this build: commit `ef23195` with no uncommitted changes, the identifier, minimum macOS 14.0, and a signature that verifies.
- **The checksum** identifies this candidate. Every later build gets a different one, because the build time is recorded inside the disk image.
- **CI** on this commit: see [ci.md](ci.md#results).

**Equivalent to the disk image the developer retested by hand.** That image was built on 2026-10-07 from the same packaged source, before the history was rewritten. Comparison:
- **Files:** 3,469 of the 3,475 files are byte-identical. The other six differ only where a rebuild must:
  - the build-info file: the commit ID and build time; the source sha256 is identical;
  - the code-signature files and the launcher binary's embedded signature. The launcher binaries are identical once their signatures are removed;
  - three install records (`RECORD`), in the hashes of console scripts the build generates and then removes, which depend on the build folder's path.
- **Results:** the packaged-app run gives CSVs identical to the retested image's run in every score, status and position column, and both jobs are identical to the SpliceAI runner.
- **Why a first rebuild differed.** Briefcase installed indirect dependencies at whatever versions PyPI had at build time. A rebuild picked up platformdirs 4.12.4 instead of the 4.12.3 in `uv.lock`. Builds now use the `uv.lock` versions, and the bundle check fails on any difference.

**Commits after `ef23195` are documentation only.** They are not in the app and never appear in its provenance. `git diff --stat ef23195 HEAD -- src pyproject.toml uv.lock .python-version scripts` prints nothing while that holds.

**Earlier disk images, kept read-only on the developer's Mac as historical evidence only.** They are not in the repository and are not for testing or distribution.
- **`dist/historical/BioBridge-0.1.0-3a6f738-retested-before-history-rewrite.dmg`** (49,220,279 bytes, sha256 `7fc22fed…8b3d`):
  - the image the developer retested by hand;
  - the same packaged source as `3a6f738`;
  - it records that commit's pre-rewrite ID.
- **`dist/historical/BioBridge-0.1.0-def7e9f-superseded-test-candidate.dmg`** (51,135,779 bytes, sha256 `bdbc41a934ab36fd7f769c1f6a8c96e3c6b5f11ed0054c6f941e0f2b9b974f90`):
  - built from the M3 source (`def7e9f`, source sha256 `65050cbd…`);
  - it has the placeholder identifier, a declared minimum of macOS 11, no runtime license texts, and the frozen Python 3.11.9 runtime;
  - the current bundle check rejects it;
  - the manual checklist and the first retest ran on it, or on pre-commit builds of the same source.

## Automated tests

All tests ran against the candidate's packaged source, which `3a6f738` and `ef23195` share. They ran on the developer's Mac, and in CI on macOS 15.7.9 and 26.6.2, in the private repository's earlier copy. CI on the recreated repository is recorded in [ci.md](ci.md#results). The test environment uses Python 3.13, the app's runtime; the engine tests use the Python 3.11 engine environment.

| Suite | Result |
|---|---|
| Unit and HTTP (`uv run pytest`) | 152 passed at `ef23195` (151 before its bundle-check test) |
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

`scripts/verify_packaged_app.py` launches the built app with an isolated data directory and drives the interface in Chromium. On the candidate (`ef23195`, developer's Mac), it passed.

| Check | Result |
|---|---|
| First setup, from a fresh engine install until the interface was ready | 48.8 s |
| Pasted `chr17-43057051-C-T` → results → CSV | 26.3 s, including the chr17 download |
| Upload of `runner_vs_cli_grch38.vcf` (16 records, chr17 and chr22) → results → CSV | 29.7 s, including the chr22 download |
| Progress, then Cancel (50 alleles) | "Scored 1 of 50…" was seen; Cancel left a job with no results |
| Quit from the page | 9 child processes started; none running at Quit, no survivors |
| Requests | 121, all to 127.0.0.1. The only assets were `/static/app.css` and `/static/app.js`: no CDN, no failed requests, no page errors |
| Window responsiveness | no event-loop delay over 100 ms |
| **Packaged results vs the SpliceAI runner** | both jobs were re-scored from their saved inputs with the development runner and were **identical**: upstream strings, statuses, reasons, details, warnings and CSV score columns |
| **Provenance in the CSVs** | `biobridge_commit` = `ef23195c912f80253f0f1ac9f78680737d64eec2`, with no `+uncommitted changes`; `biobridge_source_sha256` = `1f90830a…` |
| **Results vs the retested image's run** | identical CSVs in every score, status and position column |

The retested image (same packaged source) and the superseded `def7e9f` image passed the same checks earlier on 2026-10-07.

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
- **Manual retest of the current packaged source** (2026-10-08): **passed**, on the image built on 2026-10-07 from the same packaged source, before the history rewrite. The current candidate is equivalent to it, file by file and in results (see [The candidate build](#the-candidate-build)), so that retest carries over.
- **Jobs from the first manual run** were scored identically by the runner as well. Their CSVs were written by the earlier code, which still named an event (`AG`) for all-zero rows. The comparison now checks CSVs only for jobs made from the current source.

## Release record

### Source release (2026-10-10): done

1. **The personal email address is gone from the history.** Commits now use the maintainer's GitHub noreply address. The old private repository, whose history and CI records contained the address, was deleted on 2026-10-09. The replacement repository was created the same day with the cleaned history, and its CI passed ([ci.md](ci.md#results)). The complete history was scanned again before release. Recommended for the maintainer: GitHub's "Keep my email addresses private" and "Block command line pushes that expose my email" settings.
2. **CI is green on the code.** The replacement repository's first push (head `987c04d`, packaged code identical to `ef23195`) passed every job. The release commit's own CI run is listed in [ci.md](ci.md#results) once recorded.
3. **Release date and tag.** `date-released: 2026-10-10` is set in `CITATION.cff`, along with the date in `CHANGELOG.md`, and the source is tagged `v0.1.0` on the release commit.

### Before a disk image is published

1. **Pending: the installation checks** in [Pending installation and platform checks](#pending-installation-and-platform-checks).
2. **Done: a manual retest of the packaged source** (2026-10-08). It carries over to the current candidate by equivalence (see [The candidate build](#the-candidate-build)).
3. **Done: a candidate built from a clean commit** (`ef23195`) with the final identifier, minimum macOS, license texts, runtime and `uv.lock` dependency versions. The bundle check, the disk-image inspection, the packaged-app run and CI passed.
4. **Done: the bundled Python runtime is updated.** The app's own runtime is now Python 3.13.16 with OpenSSL 3.5.9, verified from the binaries. The SpliceAI engine stays on Python 3.11. See [0007](decisions/0007-app-runtime-python-3.13.md).

   **Correction.** An earlier version of this page said the bundled 3.11 runtime "gets no security fixes" because Python 3.11 had no newer macOS binaries. That was too broad:
   - Python 3.11 still receives security fixes, as source-only releases until October 2027 (3.11.16 in August 2026).
   - What did not receive them was the bundled build: python.org's last 3.11 macOS binary, 3.11.9, with OpenSSL 3.0.13.

## Other pending items (tracked, not blocking an experimental release)

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
