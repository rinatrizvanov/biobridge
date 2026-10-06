#!/bin/sh
# Create the SpliceAI engine environment for development and model tests.
# Usage: scripts/create_engine_env.sh [ENV_DIR]   (default: .engine-venv)
set -eu
root="$(cd "$(dirname "$0")/.." && pwd)"
env_dir="${1:-$root/.engine-venv}"
uv venv --python 3.11 --managed-python --clear "$env_dir"
uv pip sync "$root/src/biobridge/adapters/spliceai/engine.lock" \
  --python "$env_dir/bin/python" --require-hashes --no-build
