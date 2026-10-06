"""TEST-ONLY fake engine. Never shipped, never selectable in the app.

Speaks the runner protocol (JSON-lines events, `inspect` and `score`) with the
standard library only, and marks every result {"mock": true} so the interface
shows "MOCK — NOT MODEL OUTPUT". Behaviour is chosen by each record's ID:

    (default)              scored, with fixed made-up numbers
    masked_zero            raw acceptor loss 0.24, masked 0.00
    not_scored:<REASON>    not scored with that reason
    slow                   sleeps 60 s (for Cancel tests)
    crash                  emits an error event and exits 1
"""

import json
import sys
import time

MOCK_SCORES = {"DS_AG": 0.10, "DS_AL": 0.62, "DS_DG": 0.00, "DS_DL": 0.05,
               "DP_AG": -3, "DP_AL": 2, "DP_DG": 0, "DP_DL": 7}


def emit(event, **fields):
    print(json.dumps({"event": event, **fields}), flush=True)


def read_vcf(path):
    contigs, meta, records = {}, {}, []
    for line in open(path):
        line = line.rstrip("\n")
        if line.startswith("##contig=<"):
            fields = dict(f.split("=", 1) for f in line[10:-1].split(","))
            contigs[fields["ID"]] = int(fields["length"]) if "length" in fields else None
        elif line.startswith(("##reference=", "##assembly=")):
            key, value = line[2:].split("=", 1)
            meta.setdefault(key, []).append(value)
        elif line and not line.startswith("#"):
            chrom, pos, rid, ref, alt = line.split("\t")[:5]
            records.append({"index": len(records), "id": None if rid == "." else rid, "chrom": chrom,
                            "pos": int(pos), "ref": ref, "alts": [] if alt == "." else alt.split(",")})
    return {"contigs": contigs, "meta": meta, "samples": 0, "records": records, "error": None}


def score(request):
    records = read_vcf(request["vcf"])["records"]
    emit("start", records=len(records))
    emit("stage", stage="loading_model")
    emit("stage", stage="scoring")
    out = []
    for i, rec in enumerate(records):
        rid = rec["id"] or ""
        if rid == "slow":
            time.sleep(60)
        if rid == "crash":
            emit("error", message="RuntimeError: simulated engine crash")
            sys.exit(1)
        alleles = []
        for alt in rec["alts"]:
            if rid.startswith("not_scored:"):
                alleles.append({"alt": alt, "status": "NOT_SCORED", "reason": rid.split(":", 1)[1]})
                continue
            raw = {"alt": alt, "gene": "FAKEGENE", **MOCK_SCORES}
            masked = dict(raw, DS_AL=0.0) if rid == "masked_zero" else dict(raw)
            if rid == "masked_zero":
                raw["DS_AL"] = 0.24
            alleles.append({"alt": alt, "status": "SCORED", "genes": [{"gene": "FAKEGENE", "raw": raw, "masked": masked}]})
        out.append({**rec, "upstream": {"raw": [], "masked": []}, "warnings": [], "alleles": alleles})
        emit("progress", done=i + 1, total=len(records))
    return {"schema": "biobridge.spliceai.results/1",
            "engine": {"mock": True, "spliceai": "MOCK", "tensorflow": "MOCK", "keras": "MOCK", "python": "MOCK",
                       "models_sha256": {"models/spliceai1.h5": "MOCK"}, "annotation": "grch38",
                       "annotation_sha256": "MOCK"},
            "settings": {"distance": 50, "masks": [0, 1]},
            "timings": {"total_s": 0.0, "per_record_s": [0.0] * len(records)},
            "records": out}


def main():
    command, args = sys.argv[1], sys.argv[2:]
    opts = dict(zip(args[::2], args[1::2]))
    if command == "inspect":
        result = read_vcf(opts["--vcf"])
    else:
        result = score(json.load(open(opts["--request"])))
    json.dump(result, open(opts["--out"], "w"))
    emit("done", results=opts["--out"])


if __name__ == "__main__":
    main()
