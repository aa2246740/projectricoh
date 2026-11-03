"""Compare g145 replay results: everything except timing fields, plus the final card bytes.

Usage: /usr/bin/python3 -I -B research/emulator_batch/g145_compare.py A_DIR B_DIR [OUTPUT.json]
Timing fields: top-level 'seconds' and 'seconds' inside boot records.
"""
import hashlib
import json
from pathlib import Path
import sys


def strip(value):
    if isinstance(value, dict):
        return {k: strip(v) for k, v in value.items() if k != "seconds"}
    if isinstance(value, list):
        return [strip(v) for v in value]
    return value


def differences(a, b, path="", out=None):
    out = [] if out is None else out
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            differences(a.get(k), b.get(k), path + "/" + str(k), out)
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            differences(x, y, path + "/" + str(i), out)
    elif a != b:
        out.append(path)
    return out


def main():
    a, b = Path(sys.argv[1]), Path(sys.argv[2])
    ra, rb = (json.loads((d / "result.json").read_text()) for d in (a, b))
    diff = differences(strip(ra), strip(rb))
    cards = [hashlib.sha256((d / "card.img").read_bytes()).hexdigest() for d in (a, b)]
    keys = ["placement", "after_placement", "boot1_vs_placed", "boot1_load", "boot1_flushes",
            "boot1_total_vs_boot1_mount", "boot2_mount_vs_boot1_end", "boot2_load",
            "boot2_end_vs_boot1_end", "final_entry", "final_inspect", "calls", "status"]
    result = {"a": str(a), "b": str(b), "status": [ra.get("status"), rb.get("status")],
              "non_timing_differences": diff, "card_sha256": cards, "card_equal": cards[0] == cards[1],
              "sections_equal": {k: strip(ra.get(k)) == strip(rb.get(k)) for k in keys},
              "seconds": [ra.get("seconds"), rb.get("seconds")],
              "boot_seconds": [[c["boot"]["seconds"] for c in r["calls"] if "boot" in c] for r in (ra, rb)]}
    result["equal"] = not diff and result["card_equal"]
    text = json.dumps(result, indent=2)
    if len(sys.argv) > 3:
        Path(sys.argv[3]).write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
