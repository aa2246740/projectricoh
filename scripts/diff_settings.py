#!/usr/bin/env python3
"""Compare two camera-exported files; report bytes without guessing their meaning."""

import argparse
import hashlib
import json
from pathlib import Path


def read_capture(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Select a regular captured file: {path}")
    if path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError(f"Capture exceeds 8 MiB: {path}")
    return path.read_bytes()


def compare(before, after):
    spans = []
    start = None
    for offset in range(max(len(before), len(after))):
        different = offset >= min(len(before), len(after)) or before[offset] != after[offset]
        if different and start is None:
            start = offset
        if start is not None and (not different or offset + 1 == max(len(before), len(after))):
            end = offset if not different else offset + 1
            spans.append({
                "file_offset": start, "file_offset_hex": hex(start), "length": end - start,
                "before_first_32_bytes_hex": before[start:min(end, start + 32)].hex(),
                "after_first_32_bytes_hex": after[start:min(end, start + 32)].hex(),
            })
            start = None
    return spans


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    before, after = read_capture(args.before), read_capture(args.after)
    differences = compare(before, after)
    record = {
        "before": {"file": str(args.before), "bytes": len(before), "sha256": hashlib.sha256(before).hexdigest()},
        "after": {"file": str(args.after), "bytes": len(after), "sha256": hashlib.sha256(after).hexdigest()},
        "changed_byte_count": sum(span["length"] for span in differences),
        "differences": differences,
        "interpretation": "Byte differences do not identify color fields, checksums, names, timestamps or slot ownership. Use one-variable captures and repeated controls.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"changed_byte_count": record["changed_byte_count"], "span_count": len(differences), "output": str(args.output)}))


if __name__ == "__main__":
    main()
