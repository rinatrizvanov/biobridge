# 0001 — M0 feasibility spike

Status: in progress (session 1 of 4 complete)

M0 must show, before any UI work, that real SpliceAI runs locally on Apple Silicon, that its output is correct, and that a packaged app can launch it. It is time-boxed to four focused sessions.

## Session 1 — engine environment and correctness (2026-10-06): passed

Machine: Apple M4, 16 GB, macOS 15.6.1.

- `src/biobridge/adapters/spliceai/engine.lock` is compiled binary-only with hashes for `aarch64-apple-darwin` and CPython 3.11, with 49 packages. Key pins:
  - spliceai 1.3.1
  - tensorflow 2.15.1, keras 2.15.0
  - numpy 1.26.4
  - pandas 2.3.3 (<3, conservative)
  - pyfaidx 0.9.0.4, pysam 0.24.1
  - setuptools 81.0.0 (<82: spliceai imports `pkg_resources`; 81 emits a deprecation warning only)
- `scripts/create_engine_env.sh` installs it with `uv pip sync --require-hashes --no-build` in 18 s from a warm uv cache. The environment is 1.2 GB on disk; the tensorflow wheel alone is 196 MB.
  - The first attempt failed on a transient PyPI download timeout. A retry with `UV_HTTP_TIMEOUT=300` succeeded. The setup wizard needs retry handling for this.
- Smoke test:
  - `import spliceai.utils` works.
  - TensorFlow sees CPU only (no tensorflow-metal).
  - All 5 models load in 1.8 s; peak RSS is 343 MB.
  - The first import took 25 s (one-time TensorFlow startup and bytecode compilation).
- Model and annotation sha256 values, from the installed wheel:
  - spliceai1.h5 `e1fd5adcef7489d604b10e79c40078ef790d51ef048c4ce3869c9119ac5de42b`
  - spliceai2.h5 `6ab042b82ab966b6d3582cb31b96f0859ea08a864f168d69e83aa14450a3b66e`
  - spliceai3.h5 `e2e790bde53dfdf410c6dc434a86122a7d12f3f38dc2ef45d85986e9ecf22fad`
  - spliceai4.h5 `ca88ac9e58e69ba6fdeed319b72f063f164c9abf7392eaccef903e94c1d99dd6`
  - spliceai5.h5 `791cd22c62a80a08d2ca674615a93ce8159d7b55bd157cfef2983b1bd6b41391`
  - annotations/grch38.txt `565c0ea83f66b2210182364c3d626fef526229e3d02f444bab247329b6695f2c`
- **Correctness:** `tests/model/test_readme_examples.py` runs the unmodified upstream CLI (`-D 50 -M 0`, `-A grch37`) on UCSC hg19 chr2 and chr19 (md5-verified). It reproduces both README examples exactly:
  - `CA|TTN|0.07|1.00|0.00|0.00|-7|-1|35|-29`
  - `T|RYR1|0.00|0.00|0.91|0.08|-28|-46|-2|-31`

Notes for later sessions:

- Keras `predict` writes progress bars to stdout. The runner must keep upstream stdout separate from its JSON-lines event channel.
- Rough timing from the CLI log: each `predict` call takes about 0.35–0.7 s cold and about 0.07 s warm, with 10 calls per variant per mask mode. Measure properly in session 2.

## Remaining

- Session 2: runner with a per-chromosome `ann.ref_fasta` swap, mask=0 and mask=1; field-for-field equality with the CLI on a GRCh38 chr17 fixture; timing and RAM.
- Session 3: Briefcase hello-world `.dmg` → Open Anyway → uv-created engine env → one real score shown on a localhost page.
- Session 4: `docs/licensing-evidence.md`; go/no-go decision.
