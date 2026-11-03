#!/usr/bin/env python3
"""Scan firmware bytes for monotone lookup tables that could be tone curves. Read-only."""
import argparse, json, struct
from pathlib import Path

def runs(values, min_len, min_span, max_flat):
    """Yield (start, length) of non-decreasing runs with enough span and limited flat steps."""
    i, n = 0, len(values)
    while i < n - 1:
        j = i
        flats = 0
        while j + 1 < n and values[j + 1] >= values[j]:
            if values[j + 1] == values[j]:
                flats += 1
            j += 1
        length = j - i + 1
        if length >= min_len and values[j] - values[i] >= min_span and flats <= max_flat * length:
            yield i, length
        i = j + 1

def scan(path, widths):
    data = Path(path).read_bytes()
    found = []
    for name, fmt, size, min_len, min_span in widths:
        for phase in range(size):
            count = (len(data) - phase) // size
            vals = struct.unpack_from(f">{count}{fmt}", data, phase)
            for start, length in runs(vals, min_len, min_span, 0.5):
                seg = vals[start:start + length]
                if len(set(seg)) < 32:
                    continue
                off = phase + start * size
                # sample the curve shape at 5 evenly spaced points
                pts = [seg[int(k * (length - 1) / 4)] for k in range(5)]
                found.append({"file": Path(path).name, "type": name, "offset": hex(off), "entries": length,
                              "first": seg[0], "last": seg[-1], "shape_5pt": pts})
    return found

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("files", nargs="+")
    ap.add_argument("--output")
    a = ap.parse_args()
    widths = [("u8", "B", 1, 256, 200), ("u16be", "H", 2, 128, 1000)]
    out = []
    for f in a.files:
        out += scan(f, widths)
    text = json.dumps(out, indent=1)
    if a.output:
        Path(a.output).write_text(text + "\n")
    print(f"{len(out)} candidates")
    for r in out[:60]:
        print(r["file"], r["type"], r["offset"], r["entries"], r["shape_5pt"])

if __name__ == "__main__":
    main()
