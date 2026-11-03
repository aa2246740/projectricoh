"""Measure small-window correspondence and residuals before setting a gate."""
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


def measure(name,jpeg,dng):
    raw=g.raw_luma(open_dng(dng))
    sy=g.sdr_luma_grid(g.decode_rgb(jpeg),4)
    ry=g.to_storage(raw.y,g.jpeg_orientation(jpeg))
    al=g.align(sy,ry)
    ry=g.warp(ry,sy.shape,al.scale,al.dy,al.dx)
    x,y=np.log2(np.maximum(ry,1e-6)),np.log2(np.maximum(sy,1e-5))
    cx,cy=g.fit_curve(x,y,(sy>.003)&(sy<.97))
    pred=np.interp(x,cx,cy)
    a,b=g._hp(sy),g._hp(np.exp2(pred))
    if len(sys.argv)>1 and sys.argv[1]=="direct":
        a,b=ndimage.gaussian_filter(y,.6),ndimage.gaussian_filter(x,.6)
    mask=((sy>.01)&(sy<.95)).astype(float)
    err=np.abs(y-pred)
    metrics={}
    for size in (8,16,32):
        f=lambda v:ndimage.uniform_filter(v,size,mode="reflect")
        weight=f(mask)
        ma,mb=f(a*mask)/np.maximum(weight,1e-6),f(b*mask)/np.maximum(weight,1e-6)
        va=np.maximum(f(a*a*mask)/np.maximum(weight,1e-6)-ma*ma,0)
        vb=np.maximum(f(b*b*mask)/np.maximum(weight,1e-6)-mb*mb,0)
        cov=f(a*b*mask)/np.maximum(weight,1e-6)-ma*mb
        corr=cov/np.sqrt(va*vb+1e-12)
        for dy in (-1,0,1):
            for dx in (-1,0,1):
                shifted=ndimage.shift(b,(dy,dx),order=0,mode="nearest")
                ms=f(shifted*mask)/np.maximum(weight,1e-6)
                vs=np.maximum(f(shifted*shifted*mask)/np.maximum(weight,1e-6)-ms*ms,0)
                cs=(f(a*shifted*mask)/np.maximum(weight,1e-6)-ma*ms)/np.sqrt(va*vs+1e-12)
                corr=np.maximum(corr,cs)
        bad=(corr<.5)&(va>.1**2)&(weight>.5)&(mask>0)
        counts={str(t):int((bad&(err>t)).sum()) for t in (.25,.5,1.,1.5)}
        focus={str(t):int((bad&(err>.5)&((sy>t)|(np.exp2(pred)>t))).sum()) for t in (.1,.3,.5)}
        metrics[size]={"bad":int(bad.sum()),"residual":counts,"focus":focus,"min":float(corr[(va>.1**2)&(weight>.5)].min(initial=1))}
    print(json.dumps({"case":name,"windows":metrics}),flush=True)


for x in (180,300,420):
    for quiet in (False,True):
        first=hs.scene()
        if quiet:first[64:224,x-20:x+140]=.22
        second=first.copy()
        first[96:104,x:x+8]=.035
        second[96:104,x+24:x+32]=.035
        measure(f"small_{x}_{quiet}",hs.camera_jpeg(second),hs.camera_dng(first))
street=ROOT/"captures/street-g137-20261031"
for path in sorted((street/"jpg").glob("*.JPG")):
    dng=street/"dng"/(path.stem+".DNG")
    if dng.exists():measure("mount_"+path.stem,path.read_bytes(),dng)
folder=ROOT/"captures/a12-50/2026-10-24/stage2l-daily-R8051312-1473"
for path in [p for p in sorted(folder.glob("*.JPG")) if p.with_suffix(".DNG").exists()][::10]:
    measure("50mm_"+path.stem,path.read_bytes(),path.with_suffix(".DNG"))
