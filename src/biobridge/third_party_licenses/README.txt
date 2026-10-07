Third-party license texts shipped inside BioBridge.app
=======================================================

BioBridge is licensed under Apache-2.0. The app also contains the components
below. Each Python package bundled in the app keeps its own license files in
Contents/Resources/app_packages/<package>.dist-info/. The full list, with
versions, is THIRD_PARTY_LICENSES.md in the BioBridge source repository.

Python runtime: Python 3.13.16, the python.org macOS framework as repackaged
by BeeWare (Python-Apple-support 3.13-b16)
  python-3.13.16-license.rst
      CPython 3.13.16 Doc/license.rst (tag v3.13.16): the PSF license and the
      licenses of software incorporated in Python, including OpenSSL 3
      (Apache-2.0), expat, libmpdec and mimalloc. (libffi, zlib and bzip2
      are used from macOS itself and are not shipped.)
  OpenSSL 3.5.9 - Apache License 2.0; full text in python-3.13.16-license.rst.
  ncurses-6.5-COPYING
      ncurses 6.5 (COPYING, ThomasDickey/ncurses-snapshots tag
      v6_5_20240427, the version reported by the shipped library).
  xz-5.2.3-COPYING
      XZ Utils 5.2.3 (tukaani-project/xz, tag v5.2.3). liblzma is in the
      public domain.
  SQLite 3.50.4 - public domain; no license text is required. See
      https://sqlite.org/copyright.html

Briefcase (BeeWare), which builds the app
  briefcase-macOS-Xcode-template-LICENSE
      The app's launcher stub binary (MIT).
  briefcase-macOS-App-template-LICENSE
      The app template, including the default app icon (MIT).

The SpliceAI engine is not shipped in the app. It is installed on the user's
Mac during setup, in a separate Python 3.11 environment; see
THIRD_PARTY_LICENSES.md and docs/licensing-evidence.md.
