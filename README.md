# BioBridge

> **Status: pre-alpha feasibility spike.** Nothing here is usable by end users yet, and there is no release.

BioBridge aims to let bench scientists run selected scientific tools on their own computer through a simple graphical interface, without a terminal, scripting or managing software environments. The first planned workflow scores small sets of GRCh38 variants with [SpliceAI](https://github.com/Illumina/SpliceAI) (Jaganathan et al., *Cell* 2019, [doi:10.1016/j.cell.2018.12.015](https://doi.org/10.1016/j.cell.2018.12.015)), entirely on the user's Mac.

## Licensing

- BioBridge's own code is licensed under Apache-2.0 (see `LICENSE`).
- BioBridge does not include, modify or redistribute SpliceAI. Its engine environment installs the unmodified `spliceai==1.3.1` package from PyPI on the user's machine.
- Illumina states that the SpliceAI trained models are provided under CC BY-NC 4.0, for academic and non-commercial use only; other use requires a commercial license from Illumina. BioBridge applies these terms to the models.
- The SpliceAI source code was released under GPLv3 up to 1.3.1. The upstream repository was relicensed to PolyForm Strict 1.0.0 in July 2025 and archived in April 2026.

Licensing evidence, with commit references, will be recorded in `docs/licensing-evidence.md`. This is not legal advice.

## Development

Requires macOS on Apple Silicon and [uv](https://docs.astral.sh/uv/).

```sh
scripts/create_engine_env.sh   # SpliceAI engine environment in .engine-venv (about 1.3 GB)
uv run pytest                  # unit tests
uv run pytest -m model         # real-model tests: upstream README examples, runner-vs-CLI comparison,
                               # validation, chromosome ends, masking labels, and the job pipeline
                               # (first run downloads about 140 MB of UCSC hg19/hg38 chromosomes)
uv run playwright install chromium webkit   # once: test browsers (~850 MB in ~/Library/Caches)
uv run pytest -m browser       # the web interface in real browsers (fake engine + one real-engine run)

# Score a variant or a small GRCh38 VCF without the app (developer use only):
uv run python -m biobridge.dev score --variant chr17-43057051-C-T --confirm-grch38 \
    --engine-env .engine-venv --home "$(mktemp -d)"
```

Results (`results.csv`, `provenance.json`) are written to a job folder under `--home`.
