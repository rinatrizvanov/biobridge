# Third-party licenses

BioBridge's own code is licensed under Apache-2.0 (see `LICENSE`). This file lists other software and data that BioBridge either **distributes inside `BioBridge.app`** or **installs on the user's Mac** at setup, and the third-party material in the source repository.

## 1. Distributed inside BioBridge.app

**Where the full license texts are:**
- **Python packages:** each package's full license text is inside the app, in `Contents/Resources/app_packages/<package>.dist-info/`. To regenerate the package table below from a build, run `python3 scripts/list_bundled_licenses.py build/biobridge/macos/app/BioBridge.app`.
- **The Python runtime and the Briefcase stub:**
  - their license texts are in `src/biobridge/third_party_licenses/` and ship inside the app;
  - `scripts/check_app_bundle.py` fails a build that lacks them, or whose Python license text does not match the bundled runtime's version.

The app's own runtime runs the launcher and the local web interface. It is Python 3.13. The SpliceAI engine runs in a separate Python 3.11 environment, installed at setup (section 2).

| Component | Version | License | Text |
|---|---|---|---|
| Python runtime: the python.org macOS framework, repackaged by BeeWare (Python-Apple-support `3.13-b16`) | 3.13.16 | PSF-2.0 | `python-3.13.16-license.rst` (CPython's `Doc/license.rst` at `v3.13.16`) |
| OpenSSL, inside the runtime | 3.5.9 | Apache-2.0 | in `python-3.13.16-license.rst` |
| expat (2.8.5), libmpdec (4.0.1) and mimalloc, compiled into CPython | as in CPython 3.13.16 | MIT, BSD-2-Clause and MIT | in `python-3.13.16-license.rst` |
| libffi, zlib and bzip2 | macOS system libraries | not distributed (the runtime links `/usr/lib`) | — |
| SQLite, inside the runtime | 3.50.4 | Public domain | none required |
| XZ Utils (liblzma), inside the runtime | 5.2.3 | Public domain (liblzma) | `xz-5.2.3-COPYING` |
| ncurses, inside the runtime | 6.5 (20240427) | X11-style (MIT-like) | `ncurses-6.5-COPYING` |
| Briefcase macOS launcher stub (BeeWare) | Briefcase 0.4.5 | MIT | `briefcase-macOS-Xcode-template-LICENSE` |
| Briefcase macOS app template, including the default app icon (BeeWare) | Briefcase 0.4.5 | MIT | `briefcase-macOS-App-template-LICENSE` |

**How the runtime was identified:**
- **Python version:** from the runtime's own `Info.plist` and binary in the built app.
- **OpenSSL, SQLite and ncurses:** from version strings in the app's libraries.
- **The full component list:** from CPython 3.13.16's macOS installer build script (`Mac/BuildScript/build-installer.py`). BeeWare removes that build's Tcl/Tk.
- **Release notes are not evidence.** BeeWare's release notes describe the packages BeeWare builds itself. The macOS framework is python.org's build, so the shipped versions can differ: for `3.13-b15` the notes say OpenSSL 3.0.22, while the macOS library is 3.0.21.

**Support status:**
- **Python 3.13.16** (30 September 2026) was the newest 3.13 release when this runtime was chosen.
- **OpenSSL 3.5** is a long-term-support release. Briefcase 0.4.5's default for 3.13, package `b15`, would have shipped OpenSSL 3.0.21, and OpenSSL 3.0's support ended in September 2026. `pyproject.toml` pins `b16` by revision and checksum.
- **Earlier builds** bundled Python 3.11.9 with OpenSSL 3.0.13. Python 3.11 itself still receives security fixes, as source-only releases until October 2027 (3.11.16 in August 2026). But python.org's last 3.11 macOS binary was 3.11.9, and BeeWare's macOS package repackages that binary. So the bundled 3.11 runtime could not receive those fixes.

| Python package | Version | License (as declared by the package) |
|---|---|---|
| anyio | 4.15.1 | MIT |
| click | 8.5.0 | BSD-3-Clause |
| fonttools | 4.66.1 | MIT |
| h11 | 0.16.0 | MIT License |
| idna | 3.20 | BSD-3-Clause |
| Jinja2 | 3.1.6 | BSD License |
| MarkupSafe | 3.0.4 | BSD-3-Clause |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause |
| platformdirs | 4.12.3 | MIT |
| python-multipart | 0.0.32 | Apache-2.0 |
| rubicon-objc | 0.5.7 | BSD-3-Clause |
| starlette | 1.7.0 | BSD-3-Clause |
| toga | 0.5.7 | BSD-3-Clause |
| toga-cocoa | 0.5.7 | BSD-3-Clause |
| toga-core | 0.5.7 | BSD-3-Clause |
| travertino | 0.5.7 | BSD-3-Clause |
| truststore | 0.10.4 | MIT |
| typing_extensions | 4.16.0 | PSF-2.0 |
| uv | 0.11.8 | MIT OR Apache-2.0 |
| uvicorn | 0.54.0 | BSD-3-Clause |

## 2. Installed on the user's Mac during setup (not distributed by BioBridge)

The engine environment is created on the user's Mac from the hash-locked `src/biobridge/adapters/spliceai/engine.lock`. Its packages are downloaded from PyPI, and the Python interpreter by uv.

| Component | Version | License |
|---|---|---|
| spliceai | 1.3.1 | Code: GPLv3, as released on PyPI (the upstream repository was later relicensed to PolyForm Strict 1.0.0). **Trained models: CC BY-NC 4.0, academic and non-commercial use only**. See `docs/licensing-evidence.md`. |
| TensorFlow | 2.15.1 | Apache-2.0 |
| Keras | 2.15.0 | Apache-2.0 |
| NumPy | 1.26.4 | BSD-3-Clause |
| pandas | 2.3.3 | BSD-3-Clause |
| pysam (includes htslib) | 0.24.1 | MIT (htslib: MIT/Expat and BSD) |
| pyfaidx | 0.9.0.4 | BSD-3-Clause |
| h5py | 3.16.0 | BSD-3-Clause |
| CPython (python-build-standalone, installed by uv) | 3.11.15 | PSF-2.0 |
| Other dependencies (absl-py, grpcio, protobuf, tensorboard, setuptools and others) | see `engine.lock` | Permissive (Apache-2.0, BSD, MIT) as declared by each package |

## 3. Data downloaded when first needed

- **GRCh38 chromosome sequences** from the UCSC Genome Browser (`hgdownload.soe.ucsc.edu/goldenPath/hg38/chromosomes/`). They are checked against pinned md5 checksums, and their use is subject to UCSC's conditions of use. BioBridge does not redistribute them.
- **SpliceAI's GENCODE V24 annotation** is part of the `spliceai` package (see section 2).

## 4. Fonts

The interface uses fonts already on every Mac (Charter and the system sans-serif). No font files are distributed or downloaded.

## 5. In the source repository

The repository contains no third-party code. It does contain:
- the license texts listed in section 1, in `src/biobridge/third_party_licenses/`;
- `tests/model/data/readme_examples_grch37.vcf`: the two example variants from the upstream SpliceAI README, used to reproduce its published outputs;
- the other test inputs, which are synthetic variants at real GRCh38 positions;
- `engine.lock` and `uv.lock`, which list package names, versions and hashes, not package code.

## 6. Not distributed (development only)

pytest, Briefcase, Playwright with its test browsers, httpx and ruff are developer tools. They are not part of the app.
