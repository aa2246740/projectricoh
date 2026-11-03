"""Measure local correspondence without changing product functions."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "studio/src"), str(ROOT / "studio/tests")]
import numpy as np
from scipy import ndimage
import hdr_support as hs
from gxr_studio import audit
from gxr_studio.hdr import gain as g
from gxr_studio.raw import open_dng

audit.forbid_volumes()
audit.forbid_network(True)


def measure(name, jpeg, dng):
    raw = g.raw_luma(open_dng(dng))
    sy = g.sdr_luma_grid(g.decode_rgb(jpeg), 4)
    ry = g.to_storage(raw.y, g.jpeg_orientation(jpeg))
    al = g.align(sy, ry)
    ry = g.warp(ry, sy.shape, al.scale, al.dy, al.dx)
    a, b = g._hp(sy), g._hp(ry)
    rows = []
    for i in range(4):
        for j in range(4):
            ta = a[i*a.shape[0]//4:(i+1)*a.shape[0]//4, j*a.shape[1]//4:(j+1)*a.shape[1]//4]
            tb = b[i*b.shape[0]//4:(i+1)*b.shape[0]//4, j*b.shape[1]//4:(j+1)*b.shape[1]//4]
            rows.append([round(float(ta.std()), 3), round(float(tb.std()), 3), round(float(np.mean(g._norm(ta)*g._norm(tb))), 3)])
    rec = {"case": name, "tiles": rows, "alignment": al.to_dict()}
    print(json.dumps(rec), flush=True)


if __name__ == "__main__":
    for size, move in [(8, 48), (16, 24), (24, 40), (32, 64), (40, 80), (64, 80)]:
        first = hs.scene()
        second = first.copy()
        first[96:96+size, 420:420+size] = .035
        second[96:96+size, 420+move:420+move+size] = .035
        measure(f"object_{size}_move_{move}", hs.camera_jpeg(second), hs.camera_dng(first))
    street = ROOT / "captures/street-g137-20261031"
    for path in sorted((street / "jpg").glob("*.JPG")):
        dng = street / "dng" / (path.stem + ".DNG")
        if dng.exists():
            measure("mount_" + path.stem, path.read_bytes(), dng)
    folder = ROOT / "captures/a12-50/2026-10-24/stage2l-daily-R8051312-1473"
    paths = [p for p in sorted(folder.glob("*.JPG")) if p.with_suffix(".DNG").exists()]
    for path in paths[::10]:
        measure("50mm_" + path.stem, path.read_bytes(), path.with_suffix(".DNG"))
