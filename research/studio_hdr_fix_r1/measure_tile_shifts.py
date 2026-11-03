"""Measure the displacement evidence independently of the existing gain cutoff."""
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "studio/src"), str(ROOT / "studio/tests")]
import numpy as np
from PIL import Image
from scipy import ndimage
from gxr_studio import audit
from gxr_studio.hdr import gain as g
from gxr_studio.raw import open_dng

audit.forbid_volumes()
audit.forbid_network(True)


def measure(name, jpeg, dng):
    raw = g.raw_luma(open_dng(dng))
    sdr = g.sdr_luma_grid(g.decode_rgb(jpeg), 4)
    ry = g.to_storage(raw.y, g.jpeg_orientation(jpeg))
    al = g.align(sdr, ry)
    a, b = g._hp(sdr), g._hp(g.warp(ry, sdr.shape, al.scale, al.dy, al.dx))
    h, w = a.shape
    far = []
    for i in range(4):
        for j in range(4):
            y0, y1 = max(3,i*h//4), min(h-3,(i+1)*h//4)
            x0, x1 = max(3,j*w//4), min(w-3,(j+1)*w//4)
            ta = a[y0:y1,x0:x1]
            if ta.size < 64 or ta.std() < .1:
                continue
            tn = g._norm(ta)
            here = float(np.mean(tn*g._norm(b[y0:y1,x0:x1])))
            best = (here,0,0)
            for dy in range(-3,4):
                for dx in range(-3,4):
                    corr = float(np.mean(tn*g._norm(b[y0+dy:y1+dy,x0+dx:x1+dx])))
                    if corr > best[0]:
                        best = (corr,dy,dx)
            if max(abs(best[1]),abs(best[2])) >= 1:
                far.append({"tile":[i,j],"delta":best[0]-here,"here":here,"shift":best[1:]})
    print(json.dumps({"case":name,"far":far}),flush=True)


street = ROOT / "captures/street-g137-20261031"
for path in sorted((street / "jpg").glob("*.JPG")):
    dng = street / "dng" / (path.stem + ".DNG")
    if dng.exists():
        measure("mount_"+path.stem,path.read_bytes(),dng)
folder = ROOT / "captures/a12-50/2026-10-24/stage2l-daily-R8051312-1473"
for path in [p for p in sorted(folder.glob("*.JPG")) if p.with_suffix(".DNG").exists()][::10]:
    measure("50mm_"+path.stem,path.read_bytes(),path.with_suffix(".DNG"))
jpeg = (street / "jpg/R8051530.JPG").read_bytes()
rgb = g.decode_rgb(jpeg)
h,w = rgb.shape[:2]
yy,xx = np.mgrid[:h,:w].astype(np.float32)
rr = ((xx-(w-1)/2)/(w/2))**2+((yy-(h-1)/2)/(h/2))**2
for k in [.002,.006]:
    sx=(xx-(w-1)/2)*(1+k*rr)+(w-1)/2
    sy=(yy-(h-1)/2)*(1+k*rr)+(h-1)/2
    arr=np.stack([ndimage.map_coordinates(rgb[...,c],[sy,sx],order=1,mode="nearest") for c in range(3)],axis=-1)
    buf=io.BytesIO()
    Image.fromarray(arr).save(buf,"JPEG",quality=95)
    measure("radial_"+str(k),buf.getvalue(),street / "dng/R8051530.DNG")
