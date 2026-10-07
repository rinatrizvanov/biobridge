# Limitations of BioBridge v0.1

## Scope

- **GRCh38 only.** GRCh37 is rejected, and there is no liftover.
- **Input forms:** one pasted variant, in the form `chr17-43045712-T-G` or `chr17:43045712 T>G`, or a VCF of up to 1 MB (5 MB decompressed) and 50 alleles. HGVS, rsIDs and gene names are not accepted.
- **Maximum distance** is fixed at 50 nucleotides, the SpliceAI default.
- **One job at a time.** A 50-allele job takes about a minute on an Apple M4 (measured, with the reference already downloaded).
- **No transcript-level output:** no exon or intron numbers, MANE transcripts, or HGVS.

## Model and annotation

- **Engine:** SpliceAI 1.3.1 (2020), unmodified, on a frozen TensorFlow 2.15 / Keras 2.15 stack. The upstream project is archived.
- **Annotation:** scoring uses SpliceAI's bundled GENCODE V24 canonical annotation (2016), which is gene-level. Gene symbols may be outdated. The annotation affects the scores themselves, not only the masking, so results can differ from tools that use other annotations (for example SpliceAI-lookup).
- **Masking** considers only the exon boundary nearest the variant, so it can hide a loss at another annotated boundary. Raw scores are always shown for this reason.
- **Indels** are scored as entered. BioBridge warns when an indel is not left-aligned and shows the left-aligned form, but does not change it.
- **Chromosome starts.** Within about 5 kb of a chromosome's start, upstream SpliceAI reports a reference mismatch even when REF is correct. BioBridge checks REF itself and reports these variants as too close to a chromosome end.

## Interpretation

- Delta scores are predictions. They are not measurements, confidence levels or chances of disease.
- No pathogenicity assessment, no prediction of transcript outcomes, and no ACMG criteria.
- The explanation wording has **not yet had independent expert review**.
- Not a diagnostic, and not for clinical decision-making.

## Platform and installation

- **Hardware:** Apple Silicon Macs only. Intel Macs are untested; TensorFlow 2.17 and later dropped them.
- **Notarization:** the app is not notarized, so macOS asks for an Open Anyway approval; see [install.md](install.md). On IT-managed Macs (for example with Jamf or Santa) this may be blocked. That has not been tested.
- **First setup:** needs about 330 MB of downloads and about 2 GB of disk.
- **Sleep:** BioBridge keeps the Mac awake while it sets up or scores, but closing the lid still puts the Mac to sleep and pauses the job. In one test a job paused this way finished normally after the Mac woke, with unchanged results.
- **Clean-machine installation:** tested only on the developer's Mac. A clean install has not been verified.

## Licensing

SpliceAI's models are licensed for academic and non-commercial use only. Commercial use requires a license from Illumina. See [licensing-evidence.md](licensing-evidence.md).
