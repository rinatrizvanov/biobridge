# 0001 — M0 feasibility spike

Status: **GO**. M0 completed 2026-10-06; clean-machine verification pending.

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

## Session 2 — runner and CLI equivalence (2026-10-06): passed

### What was built

- `src/biobridge/adapters/spliceai/runner.py` runs as a subprocess in the engine environment.
  - It builds one upstream `Annotator` and points `ann.ref_fasta` at the right per-chromosome FASTA before each record.
  - It calls the unmodified `get_delta_scores` with mask=0 and with mask=1, and maps upstream warnings to reason codes.
  - It writes JSON-lines events to the original stdout. File descriptor 1 is redirected to stderr, so Keras/TensorFlow output can never enter the event stream.
- `src/biobridge/setup/downloads.py` provides checksum-verified downloads with a stall timeout, retries with backoff, and HTTP Range resume. `scripts/fetch_test_reference.py` now uses it.
- `scripts/create_engine_env.sh`:
  - `UV_HTTP_TIMEOUT=120`, `UV_HTTP_RETRIES=5`.
  - Up to 3 whole-install attempts with 15/30 s backoff.
  - Bytecode precompiled during install.
  - A smoke test that doubles as warm-up.
- `tests/model/data/runner_vs_cli_grch38.vcf` holds 16 synthetic records at real GRCh38 positions, with REF bases from UCSC hg38 (one deliberately wrong). chr17 and chr22 are interleaved, giving 6 reference switches.

### Results

- **Equivalence.** The runner equals the upstream CLI field for field for `-M 0` and `-M 1` on all 16 records. The CLI used one combined chr17+chr22 FASTA; the runner switched between per-chromosome files.
- **Statuses** are pinned for every case:
  - Minus-strand SNV, deletion and insertion (BRCA1); plus-strand SNVs (NF1, COMT).
  - A TXNRD2/COMT two-gene overlap reported per gene.
  - Intergenic → `NOT_IN_SPLICEAI_GENE`; complex delins → `COMPLEX_DELINS` (scores `None`, never 0); wrong REF → `REF_MISMATCH`; `<DEL>` and `*` → `UNSUPPORTED_ALLELE`, with the record's other allele scored; multi-allelic; a 102-nt deletion → `DELETION_TOO_LONG`.
  - A chromosome missing from the request → `CONTIG_NOT_SUPPORTED`, with other records unchanged. With no usable chromosome at all, TensorFlow is never loaded.
- **Multi-allelic records:** each ALT is scored on its own. A regression test splits every multi-allelic record into one-ALT records and requires identical status and scores per ALT. Supported ALTs are scored even beside an unsupported `<DEL>` or `*`.
- **Event stream:** every stdout line is a JSON event. Keras progress bars (600 lines in a 30-record run) all went to stderr.
- **Tests:** 9 unit tests (downloads) and 12 model tests pass.

### Findings

1. **The upstream CLI crashes on symbolic ALT alleles.** With pysam 0.24.1, writing a record whose ALT includes `<DEL>` aborts the whole run ("Invalid BCF, the INFO tag id=2 is too large"), so all output is lost. Neither the `##ALT` header nor `*` triggers it. The runner is unaffected because it never writes VCF through upstream code. Two consequences: the comparison test gives the CLI a copy without symbolic ALTs (upstream drops them before scoring anyway), and Stage 2's VCF export must be tested with symbolic alleles.
2. **The masking quirk is confirmed on real data.**
   - BRCA1 chr17:43063331 A>G: raw acceptor loss 0.24 at chr17:43063373, which *is* an annotated V24 exon boundary. The nearest boundary to the variant is chr17:43063333, so masked mode reports 0.00 and hides a predicted loss at an annotated acceptor.
   - The intended masking cases also occur: chr17:43067603 T>C has a donor gain of 0.23 at the nearest annotated boundary (masked to 0), and NF1 chr17:31181426 A>G has an acceptor loss of 0.17 at an unannotated position (masked to 0).
   - Conclusion: raw must always be shown next to masked.
3. **Strand sanity.** BRCA1 (minus strand) SNVs just below exon 5's lower genomic boundary give donor loss 0.82–0.99, and SNVs above its upper boundary give acceptor loss 1.00. NF1 and COMT (plus strand) show the mirror pattern. This is consistent with DP being a forward-strand genomic offset.
4. **Disk.** The environment is 1.3 GB as `du` counts it. When installed from uv's cache it consumes only about 8 MB extra on disk, because uv clones files on APFS. The uv cache is 1.2 GB and the managed Python 62 MB, so the real total is about 1.3 GB.
5. **The cold first import is not bytecode compilation.** The first `import spliceai.utils` in a new environment takes 23.1 s, or 19.3 s with precompiled bytecode. The rest is first load of newly written native libraries, likely macOS security scanning (not verified). Setup must warm the engine once; the install script's smoke test does this.

### Timings

Apple M4, 16 GB, macOS 15.6.1, measured sequentially with nothing else running. Single measurements on a home connection, so network figures vary.

| What | Uncached / cold | Cached / warm |
|---|---|---|
| Engine install (Python 3.11 plus 49 packages, about 330 MB download) | 21.4 s (Python 1.9 s, packages 19.6 s). An earlier run at a slower moment took 52 s; the very first attempt failed with a PyPI timeout. | 0.4 s from the uv cache (1.8 s with bytecode precompile) |
| `import spliceai.utils` | 23.1 s, first in a new environment (19.3 s with precompiled bytecode) | 1.5–1.8 s |
| Runner, 16-record fixture, raw and masked, D=50 | 45.4 s wall (import 22.2 s), first run in a fresh environment | 24.1 s wall |
| Model load (5 models) | 1.8 s | 1.8 s |
| First record (TensorFlow warm-up) | 2.39 s | 2.33 s |
| Each later record (raw and masked) | median 1.12 s | median 1.18 s; median 1.21 s over a 112-record scan |
| Peak memory (RSS) | 698 MB | 673 MB |
| Reference hg38 chr17+chr22 (38 MB gz → 135 MB) | 8.0 s (download, md5, decompress) | 0.1 s (md5 re-check) |

TensorFlow uses about 5 CPU cores while scoring. **Estimate, not measured:** a job at the v0.1 limit of 50 alleles should take about 1–1.2 minutes warm (about 4 s startup plus about 1.2 s per allele). M1 must measure it.

### Blockers and open items

- **No blockers for M0.**
- Open, carried to M1:
  - `NEAR_CONTIG_END` and the upstream "fasta issue" path (a position past the chromosome end) still need tests, with a synthetic contig and annotation.
  - Raw and masked scores need two upstream calls per record, doubling scoring time. This is acceptable at ≤50 alleles.
  - The runner watchdog (no event for 300 s → kill) is specified in the plan but not yet implemented; it belongs to the core job manager.

## Session 3 — packaged app (2026-10-06): passed

### What was built

- **App:** Briefcase 0.4.5 builds an ad-hoc-signed, arm64-only `BioBridge.app` (163 MB) and `.dmg` (50 MB), bundle ID `local.biobridge.biobridge` (a placeholder). It contains a Toga window: license acknowledgment, setup progress, Retry, Quit.
- **Engine install** (`biobridge.setup.envs`):
  - Uses the bundled uv 0.11.8 and a Python that uv downloads into BioBridge's own folder.
  - Child processes get only the system PATH plus proxy and certificate variables, `UV_NO_CONFIG=1`, and uv's own cache and Python folders.
  - Up to 3 attempts with 15/30 s backoff. A completion marker records the lock digest.
- **Process cleanup:** every child starts in its own process group (`biobridge.setup.processes`). Quit, or SIGTERM, terminates the groups and then kills them after 3 s.
- **Demo:** one real prediction on a synthetic variant, shown on a 127.0.0.1 page protected by a token and a Host check.
- **Bundle check:** `scripts/check_app_bundle.py` verifies the signature and required files, and that no `__pycache__` or builder home path/username is in the bundle.

### Problems found and fixed (each diagnosed before changing anything)

1. **Build-machine path in the app.** Four fontTools console scripts in the bundle had shebangs naming the builder's home folder. They are removed via `cleanup_paths`. The bundle check also confirmed that the other `/Users/...` strings come from upstream build machines (`runner`, `sysadmin`) or CPython test data.
2. **TLS failed inside the app.** The bundled Python's OpenSSL looks for certificates in the python.org installer's folder, which a typical Mac lacks, so the chr17 download failed with `CERTIFICATE_VERIFY_FAILED`. It would have worked on a developer Mac that has python.org Python installed. BioBridge's own downloads now use `truststore`, which reads the macOS trust store and honours institutional root certificates in the Keychain. uv already used the system store (`UV_SYSTEM_CERTS=1`).
3. **App Nap and idle sleep.** While setup runs, the app holds `NSActivityUserInitiated`, so macOS neither naps it nor idle-sleeps the Mac mid-download.
4. **Harness bugs, not app bugs.** `ps` truncated command lines; a stale app instance from an aborted run was signalled; and the path's spaces broke command-line matching. The final harness tracks processes by parent PID.

### Preflight evidence

The packaged app was launched with `open`, which gives it launchd's environment rather than the developer shell's, against scratch folders whose paths contain spaces.

- **Real prediction from the packaged app:** `T|BRCA1|0.00|0.00|0.02|0.99|-20|1|36|1` (raw = masked), identical to the development runner. The engine's Python is BioBridge's own uv-managed CPython 3.11.15, not a developer installation.
- **Interrupted install, automatic retry:** uv was killed mid-download (SIGKILL). The app logged "Attempt 1 failed (exit code -9); retrying in 15 s", attempt 2 of 3 completed (68 s including backoff), and the prediction followed.
- **Quit mid-install, then relaunch:** the app exited in 1.3 s, killing uv's process group with no survivors and no completion marker. The relaunch completed the install from the partially filled cache, produced the prediction (53 s), and wrote the marker.
- **Quit cleanup:** every run ended with `survivors: []`, the app exiting 0.9–2.0 s after SIGTERM, and no stray instances.
- **Bundle integrity:** after running, the signature still verifies and the bundle contains no `__pycache__`.
- **Timings**, for a fresh install in the packaged app on a home connection: engine install 44–45 s (includes the ~20 s warm-up); launch to result 58–64 s. With the engine already installed, the demo completes in seconds.
- **UI responsiveness:**
  - Worst event-loop delays during install were 291–557 ms, once or twice per install, all well below the ~2 s at which macOS shows a spinning cursor. There were none during the chromosome download, and none in three cached runs.
  - Spawning a child process takes 2–3 ms, so the delays are not caused by spawning.
  - An independent heartbeat process showed no delays at the same moments, so the cause is not system-wide.
  - The cause is not identified. It occurs only in background launches while uv unpacks wheels, and is likely timer handling in a background app under load (unverified). It will be re-measured with the window in the foreground during the Gatekeeper run.

### Gatekeeper run under the real account (2026-10-06): passed

Verified only from BioBridge's own log (`~/Library/Logs/BioBridge/launcher.log`), its data folder, and unprivileged file checks. No Gatekeeper queries or settings changes were made.

- **Install path:**
  - The `.dmg` was downloaded in Chrome; the installed app carries Chrome's quarantine attribute.
  - *User-reported:* macOS blocked the disk image itself before mounting it, and it needed an Open Anyway approval. This is now in `docs/install.md`.
  - The first attempt left no BioBridge log or data folder, so the app's code had not started. A second attempt by the developer ran.
- **Run, according to the log:**
  - The app launched from `/Applications/BioBridge.app`, not a translocated copy. It inherited only `PATH=/usr/bin:/bin:/usr/sbin:/sbin`.
  - It used the bundled uv. The engine's Python is BioBridge's own uv-managed CPython 3.11.15 in `~/Library/Application Support/BioBridge/uv-python`.
  - The license acknowledgment was recorded at 04:41:54. The engine installed in 44.5 s on the first attempt, chr17 downloaded and was verified in 4 s, and the prediction took 7 s. The result was ready 56 s after the click.
  - Real prediction: `T|BRCA1|0.00|0.00|0.02|0.99|-20|1|36|1`, raw = masked, identical to the development runner. Engine: spliceai 1.3.1, TensorFlow 2.15.1.
- **Foreground responsiveness:** the worst UI event-loop delay per stage was 6.7 ms before the click, 3.7 ms during install, 4.6 ms during the chromosome download, and 1.6 ms while running the prediction. There were no stalls over 100 ms. The 291–557 ms delays seen in preflight therefore occurred only in background launches.
- **Child process launch times:** 3–12 ms each.
- **Quit:** `quit_cleanup` records 4 children started, none running at Quit, and no survivors. No BioBridge processes remained afterwards.
- **Installed bundle afterwards:** the signature verifies and the bundle contains no `__pycache__`.
- **Disk:** `du` counts 2.7 GB in Application Support. Files uv clones from its cache are counted twice, and the earlier APFS measurement suggests real usage near 1.4 GB, but this install's real usage was not measured.

### Still unverified

- Whether the app needed its own Open Anyway approval after the disk image's (not reported).
- Clean-machine verification on a Mac without developer tools: **pending**.
- Behaviour on IT-managed Macs.

## Session 4 — licensing evidence and decision (2026-10-06)

`docs/licensing-evidence.md` records each license statement with its commit, date and Software Heritage ID. It also records BioBridge's policy: no copying, modification or redistribution; models treated as CC BY-NC 4.0; acknowledgment required before installing the engine.

## Decision: GO for Stage 1 (v0.1) with SpliceAI 1.3.1

All M0 exit criteria were met on this Mac:

- **Real model execution.** The pinned engine (TensorFlow 2.15.1, Keras 2.15, numpy 1.26, `setuptools<82`) installs binary-only on Apple Silicon.
- **Correct output.**
  - Both upstream README examples reproduce exactly.
  - The runner equals the upstream CLI field for field in raw and masked modes on a 16-record GRCh38 fixture that switches chromosomes.
  - Each ALT of a multi-allelic record is scored independently.
- **Minimal packaged launch.** An ad-hoc-signed app, installed through the Gatekeeper flow, ran entirely on bundled tools. It produced a real prediction under the real account, recovered from interrupted installs, kept foreground UI delays at or below 7 ms, and left no processes behind on Quit.

Conditions carried forward:

- **Academic and non-commercial use only** (model license).
- **Clean-machine verification is pending.** It must be done before any announcement, by an outside tester or a macOS VM.
- **Distribution friction.** Without notarization, the `.dmg` itself needs an Open Anyway approval. M3 should evaluate a `.zip` download, which may need only one approval (untested). Whether the app needs a second approval after the disk image's is unverified.
- **Carried to M1:** input validation; chromosome-end tests; the runner watchdog; CSV and provenance; measuring the 50-allele runtime (until then an estimate).
