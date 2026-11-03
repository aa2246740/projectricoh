#!/usr/bin/env python3
"""Predict 03 HC BW JPEG codes on the stage 2d and stage 2e six-step greys.

Uses the u of the actual 03 frames: stage 2d `03_hcbw` and stage 2e R8051153
(both true B&W 0x03 shot on row 20). Prediction is the piecewise-linear curve
at u*4095 with implicit endpoints 0 and 4095. B&W converts to luminance before
the curve, so the curve is applied to u, not per channel.

Curve bytes come from the official image and the local candidate file; this
script prints only codes and hashes.

  python3 -I research/stage2f/predict_hc.py
"""
import hashlib
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[2]
JLAUNCH = ROOT / "artifacts/firmware/gxr-1.51/jlaunch3"
JLAUNCH_SHA = "951be1c659c85af58ae3e4ce98707c52f0b4514fc2075256854d59f822671673"
CANDIDATES = ROOT / "research/gr4_modes/local/candidates.json"
HC_KEY = ("modes", "hc_bw", "row_jpeg_domain")
MEAS_2D = ROOT / "research/stage2d_verification/measurements.json"
MEAS_2E = ROOT / "research/stage2e_verification/local/measurements.json"
ORDER = ("D6", "D5", "D4", "D3", "D2", "D1")


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def read_image(image, va, count):
    segments = [struct.unpack_from(">5I", image, 32 + i * 20) for i in range(16)]
    hits = [src + 512 + va - base for src, base, size, _, _ in segments
            if base <= va and va + count <= base + size]
    if len(hits) != 1:
        raise SystemExit(f"VMA {va:#x} is not in exactly one section")
    return image[hits[0]:hits[0] + count]


def curve(inputs, outputs):
    xs = [0, *inputs, 4095]
    ys = list(outputs)
    if len(xs) != 33 or len(ys) != 33 or any(a >= b for a, b in zip(xs, xs[1:])):
        raise SystemExit("bad curve shape")

    def apply(code):
        code = min(max(code, 0.0), 4095.0)
        for i in range(32):
            if xs[i] <= code <= xs[i + 1]:
                t = (code - xs[i]) / (xs[i + 1] - xs[i])
                return ys[i] + t * (ys[i + 1] - ys[i])
        raise RuntimeError("code outside the curve")
    return apply


def main():
    image = JLAUNCH.read_bytes()
    if sha(image) != JLAUNCH_SHA:
        raise SystemExit("jlaunch3 hash mismatch")
    row20_in = list(struct.unpack(">31H", read_image(image, 0x2012F8A6, 62)))
    row20_out = list(read_image(image, 0x201301EB, 33))
    row20_in[-1] = 4094  # as linked in stage 2e
    node = json.loads(CANDIDATES.read_text())
    for part in HC_KEY:
        node = node[part]
    new_in, new_out = node["input31_u16"], node["output33_u8"]
    row20 = curve(row20_in, row20_out)
    new = curve(new_in, new_out)

    meas_2d = json.loads(MEAS_2D.read_text())
    patches_2d = {p["label"]: p for p in meas_2d["frames"]["03_hcbw"]["patches"]}
    grey_2e = json.loads(MEAS_2E.read_text())["tone"]["R8051153"]["per_grey"]
    charts = {
        "stage2d 03_hcbw": {label: (patches_2d[label]["u"], patches_2d[label]["jpeg_y"]) for label in ORDER},
        "stage2e R8051153": {label: (grey_2e[label]["u"], grey_2e[label]["jpeg_y"]) for label in ORDER},
    }
    result = {
        "curve_sha256": sha(struct.pack(">31H", *new_in) + bytes(new_out)),
        "candidates_json_sha256": sha(CANDIDATES.read_bytes()),
        "stage2d_measurements_sha256": sha(MEAS_2D.read_bytes()),
        "stage2e_measurements_sha256": sha(MEAS_2E.read_bytes()),
        "charts": {},
    }
    for chart, greys in charts.items():
        rows = {}
        for label in ORDER:
            u, measured = greys[label]
            code = u * 4095
            rows[label] = {
                "u4095": round(code, 1),
                "row20_measured": round(measured, 1),
                "row20_pred": round(row20(code), 2),
                "new_pred": round(new(code), 2),
                "row20_round": int(round(row20(code))),
                "new_round": int(round(new(code))),
            }
        result["charts"][chart] = rows
    print(json.dumps(result, indent=2))
    for chart, rows in result["charts"].items():
        print(f"\n{chart}")
        print("patch  u*4095  row20_meas  row20_pred  new_pred  new_round")
        for label, row in rows.items():
            print(f"{label:5} {row['u4095']:7.1f} {row['row20_measured']:11.1f} "
                  f"{row['row20_pred']:11.1f} {row['new_pred']:9.1f} {row['new_round']:10d}")


if __name__ == "__main__":
    main()
