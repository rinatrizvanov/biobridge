#!/bin/sh
# Build, package and check BioBridge.app with its source revision embedded.
#   scripts/build_app.sh
# Produces build/biobridge/macos/app/BioBridge.app and dist/BioBridge-<version>.dmg
# (ad-hoc signed; nothing is published).
set -eu
cd "$(dirname "$0")/.."
uv run python scripts/write_build_info.py
find src -name __pycache__ -type d -prune -exec rm -rf {} +
# Recreate the generated app template so Info.plist carries the current version
# (briefcase update does not rewrite it). Only build/biobridge/macos/app is replaced;
# on a fresh checkout (CI) there is nothing to replace.
if [ -d build/biobridge/macos/app ]; then
  printf 'y\n' | uv run briefcase create macOS app
else
  uv run briefcase create macOS app --no-input
fi
uv run briefcase build macOS app --no-input
uv run briefcase package macOS app --adhoc-sign --no-input
uv run python scripts/check_app_bundle.py build/biobridge/macos/app/BioBridge.app
