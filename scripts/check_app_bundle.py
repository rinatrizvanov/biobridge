#!/usr/bin/env python3
"""Check a built BioBridge.app before it is shared.

Fails if the signature does not verify, if required files are missing, or if any
file in the bundle embeds the builder's own home directory or username (for example
in console-script shebangs). Paths from upstream build machines, such as
/Users/runner/ in third-party wheels, are not ours and are not flagged.

    python3 scripts/check_app_bundle.py build/biobridge/macos/app/BioBridge.app
"""

import getpass
import subprocess
import sys
from pathlib import Path

REQUIRED = [
    "Contents/Resources/app_packages/bin/uv",
    "Contents/Resources/app/biobridge/adapters/spliceai/engine.lock",
    "Contents/Resources/app/biobridge/adapters/spliceai/runner.py",
]
BUILDER = [str(Path.home()).encode(), getpass.getuser().encode()]


def main(app: Path) -> int:
    problems = []
    verify = subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)],
                            capture_output=True, text=True)
    if verify.returncode:
        problems.append(f"signature does not verify: {verify.stderr.strip()}")
    problems += [f"missing {rel}" for rel in REQUIRED if not (app / rel).exists()]
    problems += [f"__pycache__ in bundle: {p.relative_to(app)}" for p in app.rglob("__pycache__")]
    for path in app.rglob("*"):
        if path.is_file() and not path.is_symlink():
            data = path.read_bytes()
            if any(marker in data for marker in BUILDER):
                problems.append(f"embeds the builder's home path or username: {path.relative_to(app)}")
    for problem in problems:
        print("FAIL:", problem)
    print("OK" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
