"""Measure local photometric residual relative to its observed uncertainty."""
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'studio/src'),str(ROOT/'studio/tests')]
import numpy as np
from scipy import ndimage
import hdr_support as hs
from gxr_studio import audit
from gxr_studio.hdr import gain as g
from gxr_studio.raw import open_dng

audit.forbid_volumes()
audit.forbid_network(True)


def conditional(sdr,raw):
    factor=int(np.ceil(max(sdr.shape)/192))
    sdr,raw=g.block_mean(sdr,factor),g.block_mean(raw,factor)
    a=ndimage.gaussian_filter(np.log2(np.maximum(sdr,1e-5)),.6).astype(float)
    b=ndimage.gaussian_filter(np.log2(np.maximum(raw,1e-6)),.6).astype(float)
    mask=ndimage.minimum_filter(((sdr>.01)&(sdr<.95)).astype(float),3)
    metrics={}
    for size in (8,16,32,64):
        f=lambda v:ndimage.uniform_filter(v,size,mode='reflect')
        weight=f(mask)
        w=np.maximum(weight,1e-6)
        ma,mb=f(a*mask)/w,f(b*mask)/w
        va=np.maximum(f(a*a*mask)/w-ma*ma,0)
        vb=np.maximum(f(b*b*mask)/w-mb*mb,0)
        cov=f(a*b*mask)/w-ma*mb
        slope=np.clip(cov/np.maximum(vb,1e-8),0,8)
        resid=np.abs((a-ma)-slope*(b-mb))
        sigma=np.sqrt(np.maximum(va-2*slope*cov+slope*slope*vb,0))
        bad=(resid>np.maximum(.25,5*sigma))&(weight>.5)&(mask>0)
        labels,count=ndimage.label(bad)
        largest=int(np.bincount(labels.ravel(),minlength=count+1)[1:].max(initial=0))
        blocks=int(ndimage.minimum_filter(bad.astype(int),2).sum())
        metrics[size]={'pixels':int(bad.sum()),'largest':largest,'blocks':blocks,'max':float(resid.max())}
    return metrics


def measure(name,jpeg,dng):
    raw=g.raw_luma(open_dng(dng))
    sy=g.sdr_luma_grid(g.decode_rgb(jpeg),4)
    ry=g.to_storage(raw.y,g.jpeg_orientation(jpeg))
    al=g.align(sy,ry)
    ry=g.warp(ry,sy.shape,al.scale,al.dy,al.dx)
    print(json.dumps({'case':name,'metrics':conditional(sy,ry)}),flush=True)


for seed in (0,2):
    measure('correct_'+str(seed),*hs.pair(seed))
for x in (180,300,420):
    for size in (8,16,40):
        for quiet in (False,True):
            first=hs.scene()
            if quiet:first[64:224,x-20:x+140]=.22
            second=first.copy()
            first[96:96+size,x:x+size]=.035
            second[96:96+size,x+24:x+24+size]=.035
            measure(f'object_{x}_{size}_{quiet}',hs.camera_jpeg(second),hs.camera_dng(first))
street=ROOT/'captures/street-g137-20261031'
for path in sorted((street/'dng').glob('*.DNG')):
    jpg=street/'jpg'/(path.stem+'.JPG')
    if jpg.exists():measure('mount_'+path.stem,jpg.read_bytes(),path)
folder=ROOT/'captures/a12-50/2026-10-24/stage2l-daily-R8051312-1473'
for path in [p for p in sorted(folder.glob('*.JPG')) if p.with_suffix('.DNG').exists()][::10]:
    measure('50mm_'+path.stem,path.read_bytes(),path.with_suffix('.DNG'))
