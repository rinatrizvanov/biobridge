#!/usr/bin/env python3
"""Record the source revision in src/biobridge/_build_info.json before packaging.

Run by scripts/build_app.sh. The file is git-ignored and is only read by the
packaged app, which has no git checkout.
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from biobridge.buildinfo import BUILD_INFO_NAME, collect  # noqa: E402

package = REPO / "src" / "biobridge"
info = collect(REPO, package)
(package / BUILD_INFO_NAME).write_text(json.dumps(info, indent=1) + "\n")
print(json.dumps(info))
