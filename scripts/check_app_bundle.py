#!/usr/bin/env python3
"""Check a built BioBridge.app before it is shared.

Fails if the signature does not verify, if required files are missing, if the
Info.plist version differs from biobridge.__version__, if the bundle identifier is
not the one in pyproject.toml or is a placeholder, or if the bundle embeds a local
path from this build:

- the path of the source checkout the app was built from, anywhere in the bundle
  (console-script shebangs once pointed into the build tree);
- the builder's home directory, in files this build writes: BioBridge's own code,
  Info.plist, install-time metadata and generated scripts.

Upstream files are copied in as built elsewhere and may name their own build
machines; several wheels and Briefcase's stub contain /Users/runner/..., which on
GitHub's macOS runners is also the builder's home, so the home-directory check does
not apply to them. A bare username is not searched for: "runner", for example, is
also ordinary text in BioBridge's own code (runner.py).

    uv run python scripts/check_app_bundle.py build/biobridge/macos/app/BioBridge.app
"""

import json
import plistlib
import tomllib
import subprocess
import sys
from pathlib import Path

REQUIRED = [
    "Contents/Resources/app_packages/bin/uv",
    "Contents/Resources/app/biobridge/adapters/spliceai/engine.lock",
    "Contents/Resources/app/biobridge/adapters/spliceai/runner.py",
    # License texts for components of the Python runtime and the Briefcase stub.
    *(f"Contents/Resources/app/biobridge/third_party_licenses/{name}" for name in (
        "README.txt", "python-3.11.9-license.rst", "tcl-8.6.13-license.terms", "tk-8.6.13-license.terms",
        "ncurses-5.9-license.txt", "xz-5.2.3-COPYING", "briefcase-macOS-Xcode-template-LICENSE",
        "briefcase-macOS-App-template-LICENSE")),
]
REPO = Path(__file__).resolve().parent.parent
# Reverse-DNS prefixes that no released build may use.
PLACEHOLDER_PREFIXES = ("local.", "com.example.", "org.example.", "org.beeware.")
# Written at install time rather than copied from a wheel.
INSTALL_METADATA = {"direct_url.json", "INSTALLER", "REQUESTED", "RECORD"}


def bundle_identifier(pyproject: Path) -> str:
    """The identifier Briefcase gives the app: bundle prefix + "." + app name."""
    briefcase = tomllib.loads(pyproject.read_text())["tool"]["briefcase"]
    (app_name,) = briefcase["app"]
    return f"{briefcase['bundle']}.{app_name}"


def own_file(rel: Path, data: bytes) -> bool:
    """Files this build writes or generates, as opposed to upstream files copied in."""
    return (rel.parts[:3] == ("Contents", "Resources", "app") or rel == Path("Contents/Info.plist")
            or rel.name in INSTALL_METADATA or rel.suffix == ".pth" or data.startswith(b"#!"))


def local_paths(app: Path, checkout: Path, home: Path) -> list[str]:
    """Files in the bundle that embed the build checkout's path or the builder's home."""
    anywhere = {str(checkout).encode(), str(checkout.resolve()).encode()}
    own_only = {str(home).encode(), str(home.resolve()).encode()}
    found = []
    for path in sorted(app.rglob("*")):
        if path.is_file() and not path.is_symlink():
            data, rel = path.read_bytes(), path.relative_to(app)
            if any(marker in data for marker in anywhere):
                found.append(f"embeds the build checkout's path: {rel}")
            elif own_file(rel, data) and any(marker in data for marker in own_only):
                found.append(f"embeds the builder's home directory: {rel}")
    return found


def main(app: Path) -> int:
    problems = []
    verify = subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)],
                            capture_output=True, text=True)
    if verify.returncode:
        problems.append(f"signature does not verify: {verify.stderr.strip()}")
    problems += [f"missing {rel}" for rel in REQUIRED if not (app / rel).exists()]
    problems += [f"__pycache__ in bundle: {p.relative_to(app)}" for p in app.rglob("__pycache__")]
    package = app / "Contents/Resources/app/biobridge"
    # Importing from the bundle must not write __pycache__ (with local paths) into it.
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(package.parent))
    from biobridge import __version__
    from biobridge.buildinfo import BUILD_INFO_NAME, source_digest
    with open(app / "Contents/Info.plist", "rb") as f:
        plist = plistlib.load(f)
    expected_id = bundle_identifier(REPO / "pyproject.toml")
    if plist.get("CFBundleIdentifier") != expected_id:
        problems.append(f"bundle identifier {plist.get('CFBundleIdentifier')} differs from {expected_id}")
    min_os = tomllib.loads((REPO / "pyproject.toml").read_text())["tool"]["briefcase"]["app"]["biobridge"]["macOS"]["min_os_version"]
    if plist.get("LSMinimumSystemVersion") != min_os:
        problems.append(f"minimum macOS {plist.get('LSMinimumSystemVersion')} differs from {min_os}")
    if expected_id.startswith(PLACEHOLDER_PREFIXES):
        problems.append(f"bundle identifier {expected_id} is a placeholder")
    if plist.get("CFBundleShortVersionString") != __version__:
        problems.append(f"Info.plist version {plist.get('CFBundleShortVersionString')} "
                        f"differs from biobridge {__version__}")
    try:
        info = json.loads((package / BUILD_INFO_NAME).read_text())
    except (OSError, ValueError):
        problems.append(f"missing or unreadable {BUILD_INFO_NAME} (build with scripts/build_app.sh)")
    else:
        if info.get("source_sha256") != source_digest(package):
            problems.append("recorded source digest does not match the bundled code")
        print(f"build info: commit {info.get('commit')}, uncommitted changes {info.get('uncommitted_changes')}, "
              f"source sha256 {str(info.get('source_sha256'))[:16]}…")
    problems += local_paths(app, REPO, Path.home())
    for problem in problems:
        print("FAIL:", problem)
    print("OK" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
