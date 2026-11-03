#!/usr/bin/env python3
"""Predict stage 2d neutral patches for both stage 2g table files.

Reads the curves straight from the gitignored DEEPTBL files, i.e. the bytes
the camera would load, and the 04_std and 03 frames' sensor codes from
research/stage2d_verification/measurements.json. Prints codes only.

  python3 -I research/stage2g/predict_neutrals.py
"""
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[2]
TABLES = ROOT / "firmware/stage2g/examples/tables"
MEAS = ROOT / "research/stage2d_verification/measurements.json"
JLAUNCH = ROOT / "artifacts/firmware/gxr-1.51/jlaunch3"
ORDER = ("D6", "D5", "D4", "D3", "D2", "D1")
SLOTS = ("01 Posi", "02 Nega", "03 HC BW", "05Chrome", "06ClsNeg", "07 PrbA", "08 PrbB")


def curve(inputs, outputs):
    xs = [0, *inputs, 4095]
    def apply(code):
        code = min(max(code, 0), 4095)
        for i in range(len(xs) - 1):
            if xs[i] <= code <= xs[i + 1]:
                t = (code - xs[i]) / (xs[i + 1] - xs[i])
                return outputs[i] + t * (outputs[i + 1] - outputs[i])
        raise RuntimeError("code outside the curve")
    return apply


def from_table(blob, index):
    entry = blob[16 + index * 212:16 + (index + 1) * 212]
    return curve(list(struct.unpack(">31H", entry[20:82])), list(entry[82:115]))


def stock():
    image = JLAUNCH.read_bytes()
    segments = [struct.unpack_from(">5I", image, 32 + i * 20) for i in range(16)]
    def read(va, count):
        hit = [src + 512 + va - base for src, base, size, _, _ in segments if base <= va and va + count <= base + size][0]
        return image[hit:hit + count]
    return curve(list(struct.unpack(">31H", read(0x2012F504, 62))), list(read(0x2012FFFC, 33)))


def main():
    meas = json.loads(MEAS.read_text())
    frames = {name: {p["label"]: p for p in meas["frames"][name]["patches"]} for name in ("04_std", "03_hcbw")
              if name in meas["frames"]}
    sets = {name: (TABLES / name / "DEEPTBL0.DAT").read_bytes() for name in ("equal-2e", "new")}
    std = stock()
    for frame, patches in frames.items():
        print(f"u_source frame {frame}")
        print("set        label    u  " + " ".join(f"{name:>8}" for name in (*SLOTS[:3], "04 Std", *SLOTS[3:])))
        for set_name, blob in sets.items():
            rows = [from_table(blob, i) for i in range(len(SLOTS))]
            for label in ORDER:
                code = patches[label]["u"] * 4095
                values = [rows[0](code), rows[1](code), rows[2](code), std(code)] + [row(code) for row in rows[3:]]
                print(f"{set_name:<10} {label} {code:6.1f} " + " ".join(f"{int(round(v)):8d}" for v in values))


if __name__ == "__main__":
    main()
