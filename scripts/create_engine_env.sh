#!/bin/sh
# Create the SpliceAI engine environment for development and model tests.
# Usage: scripts/create_engine_env.sh [ENV_DIR]   (default: .engine-venv)
#
# Network handling: uv retries each request (UV_HTTP_RETRIES) and gives up on a
# stalled connection after UV_HTTP_TIMEOUT seconds. The whole install is retried up
# to BIOBRIDGE_INSTALL_ATTEMPTS times with backoff; wheels finished by an earlier
# attempt stay in uv's cache, so each retry only fetches what is still missing.
set -eu
root="$(cd "$(dirname "$0")/.." && pwd)"
env_dir="${1:-$root/.engine-venv}"
lock="$root/src/biobridge/adapters/spliceai/engine.lock"

export UV_HTTP_TIMEOUT="${UV_HTTP_TIMEOUT:-120}"
export UV_HTTP_RETRIES="${UV_HTTP_RETRIES:-5}"
attempts="${BIOBRIDGE_INSTALL_ATTEMPTS:-3}"

uv venv --python 3.11 --managed-python --clear "$env_dir"

n=1
until uv pip sync "$lock" --python "$env_dir/bin/python" --require-hashes --no-build --compile-bytecode; do
  if [ "$n" -ge "$attempts" ]; then
    echo "Engine install failed after $attempts attempts." >&2
    exit 1
  fi
  delay=$((n * 15))
  echo "Engine install attempt $n failed; retrying in ${delay}s." >&2
  sleep "$delay"
  n=$((n + 1))
done

# Smoke test and warm-up: spliceai imports (needs pkg_resources) and TensorFlow sees no
# GPU plugin. The first import in a new environment takes ~20 s (measured in M0), so
# paying it here keeps it out of the user's first job.
"$env_dir/bin/python" -W ignore -c 'import spliceai.utils, tensorflow as tf; assert not tf.config.list_physical_devices("GPU")'
