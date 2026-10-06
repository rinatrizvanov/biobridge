# Licensing evidence: SpliceAI

Recorded 2026-10-06 from the upstream repository (`github.com/Illumina/SpliceAI`), PyPI,
and the Software Heritage archive. This is a record of what the sources say, not legal advice.

## Sources

Every revision below is preserved in Software Heritage (`swh:1:rev:<commit>`). The
archive's latest visit of the repository, on 2026-10-05, is snapshot
`swh:1:snp:43ccdaa47cb097a96ae19ca01c7476a8b750b401`.

| Date | Source | What it says (quoted) |
|---|---|---|
| 2020-03-07 | Tag `v1.3.1`, commit `b3c7f17b4137cb32b30c56c064f8b90b9b8f38d0`, `LICENSE` | "SpliceAI source code is provided under the GPLv3 license. SpliceAI includes several third party packages provided under other open source licenses, please see COPYRIGHT for additional details." There is **no statement about the trained models**. `setup.py`: `license='GPLv3'`. `COPYRIGHT`: GPL version 3 "or at your option, any later version". |
| 2020-03-07 | PyPI `spliceai-1.3.1-py2.py3-none-any.whl`, sha256 `63c633b8de6803d4ffb613e6ef62f1a896fec9fc13245c0f000ff7adea279776` | Wheel metadata `License: GPLv3`. The wheel contains no LICENSE file. It bundles the five models `spliceai/models/spliceai1–5.h5` and the GENCODE V24 annotations. |
| 2021-09-06 | Commit `b083eb5f8f0d773c7c977aac0c45880d47ca18b7`, `LICENSE` | "SpliceAI source code is provided under the GPLv3 license. SpliceAI models are provided under CC BY NC 4.0 license for academic and non-commercial use. …" |
| 2024-03-19 | Commit `f364513182291e7df973c4db1b301505a03279f9`, `LICENSE` | Same statement as 2021-09-06. |
| 2025-07-18 | Commit `fef2d058c46847a170c39813fc1637cfd2a91a47` ("Update LICENSE to polyform strict"), `LICENSE`; commit `c0cee4a45ec197f9afeaec78300f4b825005c846` (COPYRIGHT) | "SpliceAI source code is provided under the PolyForm Strict License 1.0.0. SpliceAI models are provided under CC BY NC 4.0 license for academic and non-commercial use. …", followed by the PolyForm Strict License 1.0.0 text. |
| current | `README.md`, section "License" | "SpliceAI source code is provided under the PolyForm Strict License 1.0.0. … The trained models used by SpliceAI (located in this package at spliceai/models) are provided under the CC BY NC 4.0 license for academic and non-commercial use; other use requires a commercial license from Illumina, Inc." It also says: "Purchase of AI scores and models for commercial use is available at AI_licensing@illumina.com." |
| current | `README.md`, precomputed scores | "These annotations are free for academic and not-for-profit use; other use requires a commercial license from Illumina, Inc." |
| 2026 | GitHub repository state | Archived (read-only). The GitHub page dates the archiving to 2026-04-20; the API reports `archived: true`. |

## How the sources differ

- **Code.** Release 1.3.1 was published under GPLv3 in its tagged LICENSE, `setup.py`, and PyPI metadata. The 2025 PolyForm Strict relicensing applies to the repository as it stands now. Whether it can affect copies of 1.3.1 already distributed under GPLv3 is a legal question these sources do not settle.
- **Trained models.** When 1.3.1 was released, no separate license was stated for the models. Since 2021, Illumina has stated CC BY-NC 4.0 (academic and non-commercial use only).

## BioBridge's policy

1. **No copying, no modification, no redistribution.** BioBridge contains no SpliceAI code or models and never patches them. On the user's Mac, the engine environment installs the unmodified `spliceai==1.3.1` wheel from PyPI, pinned by the hash above. BioBridge's runner calls upstream's public functions, and its tests run the upstream CLI. No code is taken from repository states after 2025-07-18.
2. **The models are treated as CC BY-NC 4.0**, the most restrictive statement. Before installing the engine, the user must confirm academic or non-commercial use. The confirmation and its time are stored. The notice says that commercial use, including research at companies, requires a license from Illumina.
3. **Precomputed SpliceAI scores** (BaseSpace) are not used or redistributed.
4. **Attribution:** the SpliceAI paper (Jaganathan et al., *Cell* 2019, doi:10.1016/j.cell.2018.12.015) is cited in the README and the app.
5. **BioBridge's own code** is Apache-2.0, which can be combined with GPLv3 code.
6. **Test fixtures** quote the two example output lines from the upstream README (factual score values, cited at the point of use). They do not copy upstream files.

## Open, non-blocking

- Optionally ask Illumina (AI_licensing@illumina.com) to confirm that an open-source GUI which installs the unmodified PyPI release on the user's machine, for non-commercial use, is acceptable.
