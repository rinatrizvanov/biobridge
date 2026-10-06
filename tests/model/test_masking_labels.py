"""Masked-zero labels must mean that SpliceAI's masking zeroed the value, not rounding.

Checked against an independent oracle (masking_oracle.py) that applies upstream's
masking rule from the annotation: a gain is masked when its position is the exon
boundary nearest the variant; a loss is masked when it is not.
"""

import json
import subprocess
from pathlib import Path

import pytest

from biobridge.results import EVENTS, rows_from_results, zero_kind
from tests.model.test_runner_matches_cli import run_runner

pytestmark = pytest.mark.model
ORACLE = Path(__file__).with_name("masking_oracle.py")


def check_labels(results: dict, distances: dict) -> dict:
    """Assert every label against the oracle; return counts of each kind."""
    counts = {"masked_zero": 0, "rounded_zero": 0, "unmasked_nonzero": 0, "masked_but_rounded": 0,
              "records_with_masked_zero": set()}
    for row in rows_from_results(results):
        if not row.gene or all(v is None for v in row.raw.values()):
            continue
        dist = distances[f"{row.record - 1}|{row.gene}"]
        for event in EVENTS:
            raw, masked, dp = row.raw[event], row.masked[event], row.dp[event]
            predicted = (dp == dist) if event in ("AG", "DG") else (dp != dist)
            assert masked in (raw, 0.0), f"{row.input_id} {event}: masked {masked} is neither raw {raw} nor 0"
            kind = zero_kind(raw, masked)
            if raw >= 0.01:
                assert (masked == 0.0) == predicted, f"{row.input_id} {event}: masking disagrees with the oracle"
                assert (kind == "masked_zero") == predicted
                counts["masked_zero" if predicted else "unmasked_nonzero"] += 1
                if predicted:
                    counts["records_with_masked_zero"].add(row.input_id)
            else:  # raw prints as 0.00: below 0.005, whether or not masking also applied
                assert kind == "rounded_zero"
                counts["rounded_zero"] += 1
                counts["masked_but_rounded"] += predicted
    return counts


def test_masked_zero_labels_match_upstream_masking(engine_bin, runner_script, reference_chromosomes,
                                                   model_data, tmp_path):
    chroms = reference_chromosomes("grch38-chr17-chr22")
    request = {"schema": "biobridge.spliceai.request/1",
               "vcf": str(model_data / "runner_vs_cli_grch38.vcf"), "annotation": "grch38",
               "distance": 50, "reference": {c: str(p) for c, p in chroms.items()}}
    _, _, results = run_runner(engine_bin, runner_script, request, tmp_path, "masking")
    (tmp_path / "results.json").write_text(json.dumps(results))
    oracle = subprocess.run([engine_bin / "python", ORACLE, tmp_path / "results.json", chroms["chr17"]],
                            capture_output=True, text=True, check=True)
    counts = check_labels(results, json.loads(oracle.stdout))
    # The fixture's three designed records: a loss at a non-nearest annotated boundary, a gain at the
    # nearest boundary (whose record also has a raw 0.01 acceptor loss that is masked), and a loss
    # at an unannotated position: four masked events in three records.
    assert counts["records_with_masked_zero"] == {
        "brca1_masked_hides_annotated_loss", "brca1_masked_gain_at_annotated_site", "nf1_masked_unannotated_loss"}
    assert counts["masked_zero"] == 4
    assert counts["unmasked_nonzero"] > 10 and counts["rounded_zero"] > 10
