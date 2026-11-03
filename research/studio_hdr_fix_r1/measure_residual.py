"""Compare local confidence and photometric residual on fixed input pairs."""
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
    x, y = np.log2(np.maximum(ry, 1e-5)), np.log2(np.maximum(sy, 1e-5))
    valid = (sy > .01) & (sy < .95)
    cx, cy = g.fit_curve(x, y, valid)
    pred = np.minimum(np.interp(x, cx, cy), 0)
    err = np.abs(y-pred)
    a, b = g._hp(sy), g._hp(ry)
    corr = []
    for i in range(4):
        for j in range(4):
            box = (slice(i*a.shape[0]//4,(i+1)*a.shape[0]//4), slice(j*a.shape[1]//4,(j+1)*a.shape[1]//4))
            mask = valid[box]
            ta, tb = a[box][mask], b[box][mask]
            if ta.size > 32 and ta.std() > .1:
                corr.append(float(np.mean(g._norm(ta)*g._norm(tb))))
    sizes = {}
    for threshold in (.75, 1.0, 1.5, 2.0):
        labels, count = ndimage.label((err > threshold) & valid)
        sizes[threshold] = int(np.bincount(labels.ravel(), minlength=count+1)[1:].max(initial=0))
    print(json.dumps({"case":name,"masked_min_corr":min(corr,default=1),"err_p99":float(np.percentile(err[valid],99)), "residual_components":sizes}),flush=True)


if __name__ == "__main__":
    from test_hdr_review import moving_pair
    for size, move in [(8, 48), (16, 24), (24, 40), (32, 64), (40, 80), (64, 80)]:
        measure(f"object_{size}_move_{move}", *moving_pair(size, move))
    measure("quiet", *moving_pair(16,64,quiet=True))
    street = ROOT / "captures/street-g137-20261031"
    for path in sorted((street / "jpg").glob("*.JPG")):
        dng = street / "dng" / (path.stem + ".DNG")
        if dng.exists():
            measure("mount_" + path.stem, path.read_bytes(), dng)
    folder = ROOT / "captures/a12-50/2026-10-24/stage2l-daily-R8051312-1473"
    for path in [p for p in sorted(folder.glob("*.JPG")) if p.with_suffix(".DNG").exists()][::10]:
        measure("50mm_" + path.stem, path.read_bytes(), path.with_suffix(".DNG"))
