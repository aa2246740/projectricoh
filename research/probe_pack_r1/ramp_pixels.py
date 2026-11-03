#!/usr/bin/env python3
"""Check rendered sample pixels and independently locate/decode corner markers."""
import hashlib
import json
import os
from pathlib import Path

for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[name] = "1"
import numpy as np
from PIL import Image
from scipy.ndimage import find_objects, label

HERE = Path(__file__).resolve().parent
OUT = HERE / "local/ramp/browser"


def marker_bits(image, rect):
    x, y, w, h = rect
    cells = np.array([[image[int(y+(r+.5)*h/9), int(x+(c+.5)*w/9)]
                       for c in range(9)] for r in range(9)])
    return np.min(cells, axis=-1) >= 220


def main():
    summary = json.loads((OUT / "check.json").read_text())
    page_hash = hashlib.sha256((HERE / "ramp.html").read_bytes()).hexdigest()
    assert summary["status"] == "PASS" and summary["htmlSha256"] == page_hash
    layout = json.loads((OUT / "layout.json").read_text())
    candidates = []
    for marker in layout["markers"]:
        matrix = np.zeros((9, 9), bool)
        matrix[[0, -1], :] = True
        matrix[:, [0, -1]] = True
        matrix[2:7, 2:7] = np.array([[bit == '1' for bit in row] for row in marker["bits"]])
        for rotation in range(4):
            candidates.append((marker["corner"], rotation, np.rot90(matrix, rotation)))
    hamming_min = min(int(np.sum(a[2] != b[2]))
        for i, a in enumerate(candidates) for b in candidates[i+1:])
    assert hamming_min >= 4
    receipts = []
    for case in summary["cases"]:
        name = case["name"]
        data = json.loads((OUT / f"{name}.json").read_text())
        pixels = np.array(Image.open(OUT / f"{name}.png").convert("RGB"))
        for patch in data["patches"]:
            sample = patch["sample"]
            x1, y1 = int(np.ceil(sample["x"])), int(np.ceil(sample["y"]))
            x2, y2 = int(sample["x"] + sample["w"]), int(sample["y"] + sample["h"])
            roi = pixels[y1:y2, x1:x2].astype(int)
            expected = np.array([int(x) for x in patch["rgb"].split(',')])
            assert roi.size and np.max(abs(roi - expected)) == 0, (name, patch["id"])
        # Find white connected components without using DOM marker coordinates.
        components, count = label(np.min(pixels, axis=-1) > 245)
        found = []
        for component in find_objects(components):
            yy, xx = component
            w, h = xx.stop - xx.start, yy.stop - yy.start
            if min(w, h) < 14 or abs(w - h) > 2:
                continue
            bits = marker_bits(pixels, (xx.start, yy.start, w, h))
            matches = sorted((int(np.sum(bits != expected)), corner, rotation)
                             for corner, rotation, expected in candidates)
            distance, corner, rotation = matches[0]
            if distance > 2 or matches[1][0] - distance < 3:
                continue
            found.append(dict(corner=corner, rotation=rotation, bit_errors=distance,
                              bbox=[xx.start, yy.start, w, h]))
        assert len(found) == 4 and set(m["corner"] for m in found) == {"TL", "TR", "BL", "BR"}, (name, found)
        for marker in found:
            expected = next(m["box"] for m in data["markers"] if m["corner"] == marker["corner"])
            assert abs(marker["bbox"][0] - expected["x"]) < 2
            assert abs(marker["bbox"][1] - expected["y"]) < 2
        receipts.append(dict(case=name, uniform_samples=52, located_markers=found))
    output = dict(status="PASS", htmlSha256=page_hash, marker_minimum_hamming_distance=hamming_min,
                  cases=receipts, limitation="Synthetic browser screenshots only; camera perspective, blur and moire remain to be checked.")
    (OUT.parent / "pixels.json").write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps(dict(status="PASS", cases=len(receipts), exact_color_sample_regions=len(receipts)*52,
                         markers_decoded=len(receipts)*4, minimum_hamming_distance=hamming_min)))


if __name__ == "__main__":
    main()
