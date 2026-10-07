# BioBridge

BioBridge runs [SpliceAI](https://github.com/Illumina/SpliceAI) on your own Mac through a simple browser interface. You don't need a terminal, an account or a server, and your variants never leave the computer.

> **Version 0.1.0, release candidate; not yet released.** Experimental research software, not a diagnostic. SpliceAI's trained models are licensed for **academic and non-commercial use only** (CC BY-NC 4.0); commercial use, including research at companies, requires a license from Illumina.

## What it does

- Scores one GRCh38 variant, or a small VCF file (up to 50 alleles), with the unmodified SpliceAI 1.3.1 model, on your Mac.
- Shows masked and raw delta scores side by side, a chart and a table of values for each variant, short deterministic explanations, and the reason for anything that could not be scored.
- Exports a CSV with full provenance: the BioBridge source revision, engine and model checksums, reference checksums, settings, and the basis for the genome build.

## What it does not do in v0.1

- Accept GRCh37 (hg19) input, HGVS descriptions, rsIDs or gene names.
- Number exons or introns, or name transcripts.
- Predict the resulting transcript (for example exon skipping), assess pathogenicity, or assign ACMG criteria.

See [docs/limitations.md](docs/limitations.md).

## Requirements

- A Mac with Apple Silicon (M1 or later) running macOS 14 or later. Tested on an M4 with macOS 15.6.1.
- An internet connection for the first setup (about 330 MB), and the first time each chromosome is needed (12–80 MB each).
- About 2 GB of free disk space.

## Install and use

1. **Install.** Follow [docs/install.md](docs/install.md). BioBridge is not notarized by Apple, so macOS asks you to approve it once.
2. **Set up.** Open BioBridge, confirm non-commercial use, and click **Start BioBridge**. The first setup takes about a minute.
3. **Score.** Your browser opens BioBridge. Enter a variant such as `chr17-43045712-T-G`, or choose a VCF file. Confirm that the coordinates are GRCh38, then click **Run SpliceAI**.
4. **Read the results.** [docs/interpreting-results.md](docs/interpreting-results.md) explains what the scores mean. Click **Download CSV** to keep them.
5. **Quit** from the page or from the BioBridge window.

## Privacy

- Variants are scored on your Mac.
- The first time a chromosome is needed, BioBridge downloads it from UCSC. This tells UCSC only which chromosome was needed.
- There is no telemetry.
- Jobs are stored in `~/Library/Application Support/BioBridge/jobs`: the input without genotype columns, the results, the CSV and the provenance.

## Licensing

- **BioBridge's own code:** Apache-2.0 ([LICENSE](LICENSE)).
- **SpliceAI:** BioBridge does not include, modify or redistribute SpliceAI. During setup, your Mac installs the unmodified `spliceai==1.3.1` package from PyPI. That release's code was published under GPLv3. Illumina states that the trained models are CC BY-NC 4.0, and BioBridge applies those terms. The upstream repository was relicensed to PolyForm Strict 1.0.0 in July 2025 and archived in April 2026. Evidence, with commit references: [docs/licensing-evidence.md](docs/licensing-evidence.md). This is not legal advice.
- **Components bundled in the app:** [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).

## Citing

If you use BioBridge in research, cite SpliceAI: Jaganathan K. et al., *Predicting splicing from primary sequence with deep learning*, Cell 2019, [doi:10.1016/j.cell.2018.12.015](https://doi.org/10.1016/j.cell.2018.12.015). To cite BioBridge itself, see [CITATION.cff](CITATION.cff), and give the source revision recorded in your CSV.

## Verification status

Details are in [docs/release-v0.1.0.md](docs/release-v0.1.0.md).

**Passed on the developer's Mac:**
- Unit, real-engine and real-browser (Chromium and WebKit) tests.
- An automated run of the packaged app, in which its results were identical to the SpliceAI runner.
- A manual checklist run. Its two findings, a clipped chart label and an unknown source revision in the CSV, are fixed,
  and a manual retest passed.

**Still pending:**
- An install on a second Mac ([checklist](docs/second-mac-checklist-v0.1.md)). This includes whether a downloaded copy needs a second approval.
- Green GitHub CI runs. The workflow and its recorded results are in [docs/ci.md](docs/ci.md).
- macOS 14, the documented minimum, is unverified.
- IT-managed Macs.
- Independent expert review of the explanations.
- Demo inputs based on public ClinVar records.
- A real bundle identifier in place of the placeholder.

## Development

You need macOS on Apple Silicon and [uv](https://docs.astral.sh/uv/).

```sh
uvx ruff@0.16.10 check .       # lint (rules in ruff.toml); CI jobs and coverage: docs/ci.md
scripts/create_engine_env.sh   # SpliceAI engine environment in .engine-venv (about 1.3 GB)
uv run pytest                  # unit and HTTP-level tests
uv run pytest -m model         # real-engine tests: upstream README examples, runner vs CLI, validation,
                               # chromosome ends, masking labels, job pipeline (downloads ~140 MB once)
uv run playwright install chromium webkit   # once: test browsers (~850 MB in ~/Library/Caches)
uv run pytest -m browser       # the interface in Chromium and WebKit (fake engine + one real-engine run)

scripts/build_app.sh           # build BioBridge.app and the .dmg, with the source revision embedded
T=$(mktemp -d -t biobridge-packaged)
uv run python scripts/verify_packaged_app.py build/biobridge/macos/app/BioBridge.app "$T"
uv run python scripts/screenshots.py build/biobridge/macos/app/BioBridge.app "$(mktemp -d)"

# Score without the app (developer use only):
uv run python -m biobridge.dev score --variant chr17-43057051-C-T --confirm-grch38 \
    --engine-env .engine-venv --home "$(mktemp -d)"
```

Design decisions and measurements are recorded in [docs/decisions](docs/decisions).

## Acknowledgments

- SpliceAI was developed at Illumina (Jaganathan et al., 2019).
- Reference sequences come from the UCSC Genome Browser.
- BioBridge is built with BeeWare (Briefcase, Toga), uv, Starlette and Uvicorn.
