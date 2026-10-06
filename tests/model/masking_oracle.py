"""Independent masking oracle, run with the engine's Python.

For each scored record and overlapping gene, print the signed distance from the
variant to the nearest annotated exon boundary in SpliceAI's annotation, using
upstream's public Annotator.get_pos_data. Upstream masks a gain whose position
equals this distance, and a loss whose position differs from it.

    <engine python> masking_oracle.py results.json reference.fa [annotation]
"""

import json
import sys

from spliceai.utils import Annotator

results = json.load(open(sys.argv[1]))
ann = Annotator(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "grch38")
distances = {}
for rec in results["records"]:
    genes, _strands, idxs = ann.get_name_and_strand(rec["chrom"], rec["pos"])
    for gene, idx in zip(genes, idxs):
        distances[f"{rec['index']}|{gene}"] = int(ann.get_pos_data(idx, rec["pos"])[2])
print(json.dumps(distances))
