# Third-party licenses

BioBridge's own code is licensed under Apache-2.0 (see `LICENSE`). This file lists other software and data that BioBridge either **distributes inside `BioBridge.app`** or **installs on the user's Mac** at setup.

## 1. Distributed inside BioBridge.app

Each Python package's full license text is inside the app, in `Contents/Resources/app_packages/<package>.dist-info/`. To regenerate this table from a build, run `python3 scripts/list_bundled_licenses.py build/biobridge/macos/app/BioBridge.app`.

| Component | Version | License |
|---|---|---|
| Python runtime (BeeWare Python-Apple-support build) | 3.11.9 | PSF-2.0 |
| OpenSSL (inside the Python runtime) | 3.0.13 | Apache-2.0 |
| ncurses (inside the Python runtime) | 5.9 | X11-style (MIT-like) |
| Tcl/Tk (inside the Python runtime) | 8.6.13 | Tcl/Tk license (BSD-style) |
| Briefcase macOS app stub (BeeWare) | 0.4.5 | BSD-3-Clause |

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

## 5. Not distributed (development only)

pytest, Briefcase, Playwright with its test browsers, httpx and ruff are developer tools. They are not part of the app.
