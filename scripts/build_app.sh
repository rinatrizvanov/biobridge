#!/bin/sh
# Build, package and check BioBridge.app with its source revision embedded.
#   scripts/build_app.sh
# Produces build/biobridge/macos/app/BioBridge.app and dist/BioBridge-<version>.dmg
# (ad-hoc signed; nothing is published).
set -eu
cd "$(dirname "$0")/.."
python3 scripts/write_build_info.py
find src -name __pycache__ -type d -prune -exec rm -rf {} +
# Recreate the generated app template so Info.plist carries the current version
# (briefcase update does not rewrite it). Only build/biobridge/macos/app is replaced.
printf 'y\n' | uv run briefcase create macOS app
uv run briefcase build macOS app --no-input
uv run briefcase package macOS app --adhoc-sign --no-input
python3 scripts/check_app_bundle.py build/biobridge/macos/app/BioBridge.app
