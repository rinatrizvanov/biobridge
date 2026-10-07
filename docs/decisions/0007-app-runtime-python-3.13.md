# 0007: The app's runtime moves to Python 3.13; the engine stays on 3.11

Status: **done** (2026-10-07). The repository is private, with no tag and nothing published.

## Two Pythons, two jobs

| | Runs | Python | Source |
|---|---|---|---|
| **App runtime**, bundled in `BioBridge.app` | the launcher window, setup and the local web interface | **3.13.16** | BeeWare Python-Apple-support `3.13-b16`, which repackages python.org's macOS framework |
| **Engine**, installed on the user's Mac at setup | SpliceAI and TensorFlow (`runner.py`) | **3.11** | uv-managed CPython, `setup/envs.py` (`PYTHON_VERSION = "3.11"`), from the hash-locked `engine.lock` |

The engine must stay on 3.11, because TensorFlow 2.15 supports Python only up to 3.11. The app runtime has no such constraint.

## Why the app runtime changed

- **The old runtime was frozen.** Earlier builds bundled Python 3.11.9 with OpenSSL 3.0.13 from January 2024: python.org's last 3.11 macOS binary, repackaged by BeeWare.
- **Python 3.11 itself is still maintained.** It receives source-only security releases until October 2027 (3.11.16 in August 2026). The bundled binary could not receive them.
- **A correction.** Earlier documents said the 3.11 runtime "gets no security fixes" because Python 3.11 had no newer macOS binaries. That overstated it: the bundled *build* got no fixes, not Python 3.11.

## Choosing the 3.13 package

Briefcase 0.4.5's template defaults to package `3.13-b15`. Both candidates were downloaded and their binaries read directly; nothing was run.

| Package | Python (from `Info.plist` and the binary) | OpenSSL (from `libcrypto`) | Note |
|---|---|---|---|
| `3.13-b15`, Briefcase's default (hash matches the template's) | 3.13.15 | 3.0.21 | OpenSSL 3.0's support ended in September 2026. The release notes say 3.0.22, but the macOS library is 3.0.21. |
| **`3.13-b16`**, chosen (published 2026-10-06) | **3.13.16**, the newest 3.13 release (2026-09-30) | **3.5.9**, a long-term-support line | Matches CPython 3.13.16's macOS build script |

**How it is pinned.** `pyproject.toml` sets `support_revision = "16"` and the package's sha256 (`29334305…f737`). `.python-version` is `3.13`, because Briefcase bundles the Python minor version it runs under. The development and CI test environments therefore also run on 3.13, the app's runtime, while the engine tests still use the 3.11 engine environment.

## What the runtime contains

- **From CPython 3.13.16's macOS build script, checked against the shipped binaries:**
  - OpenSSL 3.5.9;
  - SQLite 3.50.4;
  - XZ 5.2.3;
  - ncurses 6.5 (20240427);
  - libmpdec 4.0.1, expat 2.8.5 and mimalloc, compiled in.
- **From macOS itself:** libffi, zlib and bzip2.
- **Removed:** BeeWare removes the build's Tcl/Tk, so the 3.11-era Tcl/Tk license texts are no longer shipped.
- **License texts.** `src/biobridge/third_party_licenses/` now holds CPython 3.13.16's `Doc/license.rst` and ncurses 6.5's `COPYING`, alongside the XZ and BeeWare texts.
- **The bundle check:**
  - it prints the bundled Python and OpenSSL versions;
  - it fails if the Python license text for the bundled runtime's exact version is missing.

## Compatibility checks

- **Code:** no module removed in Python 3.13 is used.
- **The lock:** `uv.lock` installs unchanged on 3.13.
- **Unit and browser tests** pass on 3.13: 151 and 30.
- **The real-engine suite** passes with the 3.13 test environment driving the 3.11 engine.
- **The packaged app** was built, checked and run end to end with the 3.13.16 runtime; see the [release page](../release-v0.1.0.md).
