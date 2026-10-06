#!/bin/sh
# Re-compile the SpliceAI engine lockfile (binary wheels only, with hashes).
set -eu
cd "$(dirname "$0")/../src/biobridge/adapters/spliceai"
uv pip compile requirements.in -o engine.lock \
  --python-version 3.11 --python-platform aarch64-apple-darwin \
  --generate-hashes --no-build --emit-index-url
