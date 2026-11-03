"""Check actual paired files, nearby exposures, local motion and radial correction."""
import io
import json
import math
import sys
import time
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
TMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-hdr')/'alignment'
TMP.mkdir(exist_ok=True)
sys.path[:0] = [str(OUT),str(ROOT/'studio/src'),str(ROOT/'studio/tests')]
import numpy as np
from PIL import Image
from scipy import ndimage
import hdr_support as hs
from gxr_studio import audit
from gxr_studio.hdr import gain as g
from gxr_studio.raw import open_dng
from format_oracle import inspect, stops

audit.forbid_volumes()
audit.forbid_network(True)
records=[]
def emit(rec):
    records.append(rec)
    with (OUT/'alignment_cases.jsonl').open('a') as f:
        f.write(json.dumps(rec,ensure_ascii=False)+'\n')
    print(json.dumps(rec,ensure_ascii=False),flush=True)

def trial(jpeg,raw,label,kind,**extras):
    started=time.monotonic()
    grid=g.sdr_luma_grid(g.decode_rgb(jpeg),4)
    orientation=g.jpeg_orientation(jpeg)
    stored=g.RawLuma(g.to_storage(raw.y,orientation),g.to_storage(raw.clip,orientation))
    al=g.align(grid,stored.y)
    rec={'kind':kind,'case':label,'alignment':al.to_dict(),'shift_fraction':al.shift_frac,**extras}
    try:
        g.check_alignment(al)
    except g.HdrUnsupported as exc:
        rec.update(accepted=False,reason=exc.reason,detail=exc.detail)
        emit({**rec,'seconds':round(time.monotonic()-started,3)})
        return None,rec
    try:
        raw_y,clip=g.register(stored,grid.shape,al,grid.shape)
        result=g.compute_gain(grid,raw_y,clip,g.Params())
        data=g.package(jpeg,result,g.Params())
        check,codes,_=inspect(jpeg,data)
        rec.update(accepted=True,hdr_sha256=check['hdr_sha256'],gain_max=check['iso_values']['GainMapMax'])
        emit({**rec,'seconds':round(time.monotonic()-started,3)})
        return (data,stops(codes,check['iso_values'])),rec
    except g.HdrUnsupported as exc:
        rec.update(accepted=False,reason=exc.reason,detail=exc.detail)
        emit({**rec,'seconds':round(time.monotonic()-started,3)})
        return None,rec

def synthetic_motion():
    for size,shift in [(16,24),(24,40),(32,64),(40,80),(64,80)]:
        first=hs.scene(seed=0)
        second=first.copy()
        y,x=96,420
        first[y:y+size,x:x+size]=0.035
        second[y:y+size,x+shift:x+shift+size]=0.035
        jpeg=hs.camera_jpeg(second)
        raw=g.raw_luma(open_dng(hs.camera_dng(first)))
        made,rec=trial(jpeg,raw,f'object_{size}_move_{shift}','local_motion',known_motion_pixels=shift,object_wh=[size,size])
        if made:
            correct,_=g.hdr_from_camera_jpeg(jpeg,g.raw_luma(open_dng(hs.camera_dng(second))))
            _,cc,_=inspect(jpeg,correct)
            _,wc,_=inspect(jpeg,made[0])
            from format_oracle import inspect as oracle
            cm=oracle(jpeg,correct)[0]['iso_values']
            wm=oracle(jpeg,made[0])[0]['iso_values']
            true_gain,wrong_gain=stops(cc,cm),stops(wc,wm)
            roi=(slice(y//4+1,(y+size)//4-1),slice(x//4+1,(x+size)//4-1))
            error=true_gain[roi]-wrong_gain[roi]
            emit({'kind':'local_motion_effect','case':rec['case'],'median_gain_deficit_stops':float(np.median(error)),
                  'max_gain_difference_stops':float(np.abs(true_gain-wrong_gain).max()),
                  'fraction_difference_gt_0p25':float((np.abs(true_gain-wrong_gain)>0.25).mean())})
            Image.fromarray(hs.srgb_bytes(first*hs.EXPOSURE)).save(TMP/(rec['case']+'_raw_scene.png'))
            Image.fromarray(hs.srgb_bytes(second*hs.EXPOSURE)).save(TMP/(rec['case']+'_jpeg_scene.png'))
            (TMP/(rec['case']+'_wrong.jpg')).write_bytes(made[0])
            (TMP/(rec['case']+'_correct.jpg')).write_bytes(correct)

def real_pairs():
    street=ROOT/'captures/street-g137-20261031'
    names=sorted(p.stem for p in (street/'dng').glob('*.DNG') if (street/'jpg'/(p.stem+'.JPG')).exists())
    for name in names:
        trial((street/'jpg'/(name+'.JPG')).read_bytes(),g.raw_luma(open_dng(street/'dng'/(name+'.DNG'))),name,'mount_correct')
    a12=ROOT/'captures/a12-50/2026-10-24/stage2l-daily-R8051312-1473'
    names=sorted(p.stem for p in a12.glob('*.JPG') if (a12/(p.stem+'.DNG')).exists())
    for i in range(0,len(names),10):
        name=names[i]
        trial((a12/(name+'.JPG')).read_bytes(),g.raw_luma(open_dng(a12/(name+'.DNG'))),name,'50mm_correct')
        if i+1 < len(names):
            other=names[i+1]
            trial((a12/(name+'.JPG')).read_bytes(),g.raw_luma(open_dng(a12/(other+'.DNG'))),name+'+'+other,'50mm_adjacent')
    for name,other in [('R8051530','R8051531'),('R8051532','R8051533'),('R8051627','R8051644'),('R8051680','R8051685')]:
        trial((street/'jpg'/(name+'.JPG')).read_bytes(),g.raw_luma(open_dng(street/'dng'/(other+'.DNG'))),name+'+'+other,'mount_other')

def radial():
    street=ROOT/'captures/street-g137-20261031'
    jpeg=(street/'jpg/R8051530.JPG').read_bytes()
    raw=g.raw_luma(open_dng(street/'dng/R8051530.DNG'))
    rgb=g.decode_rgb(jpeg)
    h,w=rgb.shape[:2]
    yy,xx=np.mgrid[0:h,0:w].astype(np.float32)
    nx,ny=(xx-(w-1)/2)/(w/2),(yy-(h-1)/2)/(h/2)
    rr=nx*nx+ny*ny
    for k in [0.002,0.006,0.012,0.03,-0.012]:
        sx=(xx-(w-1)/2)*(1+k*rr)+(w-1)/2
        sy=(yy-(h-1)/2)*(1+k*rr)+(h-1)/2
        arr=np.stack([ndimage.map_coordinates(rgb[...,c],[sy,sx],order=1,mode='nearest') for c in range(3)],axis=-1)
        b=io.BytesIO()
        Image.fromarray(arr).save(b,'JPEG',quality=95)
        trial(b.getvalue(),raw,f'radial_{k}','radial_correction',coefficient=k,
              max_displacement_pixels=float(np.sqrt((sx-xx)**2+(sy-yy)**2).max()))

synthetic_motion()
real_pairs()
radial()
summary={}
for kind in sorted(set(r['kind'] for r in records)):
    group=[r for r in records if r['kind']==kind]
    summary[kind]={'count':len(group),'accepted':sum(bool(r.get('accepted')) for r in group)}
assert audit.network_attempts()==[]
(OUT/'alignment_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary))
