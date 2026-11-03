"""Reduce native call/return records to a reviewable event timeline."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "local"


def message_fields(row):
    data = bytes.fromhex(row.get("message", ""))
    if len(data) < 20 or int.from_bytes(data[:2], "big") != 24:
        return {}
    return {"message_type": int.from_bytes(data[6:8], "big"),
            "key": int.from_bytes(data[12:16], "big"),
            "phase": int.from_bytes(data[16:20], "big")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("runs", nargs="+")
    args = parser.parse_args()
    target = OUT / (args.name+".json")
    table = OUT / (args.name+".tsv")
    if target.exists() or table.exists() or target.resolve().parent != OUT:
        raise ValueError("choose a fresh timeline name")
    rows, counts, packed, messages, truncated = [], Counter(), [], [], []
    for name in args.runs:
        run = json.loads((OUT / (name+".json")).read_text())
        if run.get("flow_truncated"):
            truncated.append(name)
        for record in run["flow"]:
            kind = record["kind"]
            if kind.startswith(("control-scan-", "hid-scan-")):
                continue
            if kind == "queue-send" and record["queue"] != 1:
                continue
            fields = message_fields(record)
            if kind in ("event-next-return", "queue1-wait-return") and fields.get("message_type") != 0x700B:
                continue
            if kind == "event-submit-call" and record.get("task") == 3 and record["args"][0] == 2:
                value = record["args"][1]
                fields.update(key=value >> 24, phase=(value >> 16) & 255)
                packed.append({"run": name, "step": record["step"], **fields})
            if kind == "queue1-wait-return" and fields:
                messages.append({"run": name, "step": record["step"], **fields})
            counts[kind] += 1
            rows.append({"run": name, **record, **fields})
    fields = ("run", "step", "task", "kind", "pc", "lr", "spu", "result", "key", "phase", "args", "message")
    with table.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fields, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, separators=(",", ":")) if isinstance(v, (list, dict)) else v
                             for k, v in row.items()})
    result = {"runs": args.runs, "counts": dict(counts), "producer_events": packed,
              "Task6_key_messages": messages, "truncated_runs": truncated,
              "native_calls": rows, "tsv": str(table.relative_to(ROOT))}
    target.write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps({"records": len(rows), "producer_events": len(packed),
                      "Task6_key_messages": len(messages), "truncated_runs": truncated}))


if __name__ == "__main__":
    main()
