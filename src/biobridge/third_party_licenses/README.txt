Third-party license texts shipped inside BioBridge.app
=======================================================

BioBridge is licensed under Apache-2.0. The app also contains the components
below. Each Python package bundled in the app keeps its own license files in
Contents/Resources/app_packages/<package>.dist-info/. The full list, with
versions, is THIRD_PARTY_LICENSES.md in the BioBridge source repository.

Python runtime (BeeWare's repackaging of the python.org macOS framework 3.11.9)
  python-3.11.9-license.rst
      CPython 3.11.9 Doc/license.rst (tag v3.11.9): the PSF license and the
      licenses of software incorporated in Python, including OpenSSL 3.0
      (Apache-2.0), expat and libmpdec. (libffi and zlib are used from macOS
      itself and are not shipped.)
  OpenSSL 3.0.13 - Apache License 2.0; full text in python-3.11.9-license.rst.
  tcl-8.6.13-license.terms, tk-8.6.13-license.terms
      Tcl/Tk 8.6.13 (tcltk/tcl and tcltk/tk, tag core-8-6-13). The libraries
      are present in the runtime; BioBridge does not use them.
  ncurses-5.9-license.txt
      ncurses 5.9 (license header of include/curses.h.in, tag v5.9).
  xz-5.2.3-COPYING
      XZ Utils 5.2.3 (tukaani-project/xz, tag v5.2.3). liblzma is in the
      public domain.
  SQLite 3.45.1 - public domain; no license text is required. See
      https://sqlite.org/copyright.html

Briefcase (BeeWare), which builds the app
  briefcase-macOS-Xcode-template-LICENSE
      The app's launcher stub binary (MIT).
  briefcase-macOS-App-template-LICENSE
      The app template, including the default app icon (MIT).

The SpliceAI engine is not shipped in the app. It is installed on the user's
Mac during setup; see THIRD_PARTY_LICENSES.md and docs/licensing-evidence.md.
