#!/usr/bin/env python3
"""Print the Python packages bundled in BioBridge.app with their declared licenses.

    python3 scripts/list_bundled_licenses.py build/biobridge/macos/app/BioBridge.app

Used to check THIRD_PARTY_LICENSES.md against what a build actually ships.
"""

import sys
from email.parser import Parser
from pathlib import Path

app = Path(sys.argv[1])
for meta in sorted((app / "Contents/Resources/app_packages").glob("*.dist-info/METADATA"),
                   key=lambda p: p.parent.name.lower()):
    m = Parser().parsestr(meta.read_text(errors="replace"))
    lic = m.get("License-Expression") or "; ".join(
        c.split("::")[-1].strip() for c in m.get_all("Classifier") or [] if c.startswith("License ::")) \
        or (m.get("License") or "unknown").splitlines()[0]
    print(f"| {m['Name']} | {m['Version']} | {lic} |")
