"""Read actual generated JPEG bytes independently, then compare system HDR decoding."""
import importlib.util
import io
import json
import math
import struct
import subprocess
import sys
from pathlib import Path

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-hdr')/'format'
TMP.mkdir(exist_ok=True)
sys.path[:0]=[str(OUT),str(ROOT/'studio/src'),str(ROOT/'studio/tests')]
import numpy as np
from PIL import Image
import hdr_support as hs
from format_oracle import inspect,stops,linear_y,blocks,ISO
from gxr_studio import audit
from gxr_studio.hdr import gain as g
from gxr_studio.raw import open_dng

audit.forbid_network(True)
audit.forbid_volumes()
records=[]
exe=TMP/'check_imageio'
subprocess.run(['swiftc','-O','-o',str(exe),str(ROOT/'research/hdr_gainmap/check_imageio.swift')],check=True,capture_output=True,timeout=900)

def system_check(orig,hdr,info,codes,rgb):
    a=subprocess.run([str(exe),str(hdr)],check=True,capture_output=True,text=True,timeout=360)
    observed=json.loads(a.stdout.splitlines()[0])
    f=TMP/(hdr.stem+'.f32')
    a=subprocess.run([str(exe),'--compare',str(orig),str(hdr),str(f)],check=True,capture_output=True,text=True,timeout=360)
    comparison=json.loads(a.stdout)
    assert observed['isoGainMap'] is not None
    assert [observed['isoGainMap']['width'],observed['isoGainMap']['height']]==info['gain_wh']
    control={}
    if comparison['sdrMaxAbsDiff']>1:
        source=orig.read_bytes()
        version=ISO+b'\0\0\0\0'
        minimal=TMP/(hdr.stem+'_iso_only.jpg')
        minimal.write_bytes(source[:2]+b'\xff\xe2'+struct.pack('>H',len(version)+2)+version+source[2:])
        c=subprocess.run([str(exe),'--compare',str(orig),str(minimal),str(TMP/'control.f32')],check=True,capture_output=True,text=True,timeout=360)
        before=json.loads(c.stdout)
        c=subprocess.run([str(exe),'--compare',str(minimal),str(hdr),str(TMP/'control_hdr.f32')],check=True,capture_output=True,text=True,timeout=360)
        after=json.loads(c.stdout)
        control={'iso_only_sdr_max_abs_diff':before['sdrMaxAbsDiff'],'iso_only_vs_hdr_sdr_max_abs_diff':after['sdrMaxAbsDiff']}
        assert after['sdrMaxAbsDiff']==0,control
    metadata=info['iso_values']
    assert abs(comparison['hdrHeadroom']/2**metadata['HDRCapacityMax']-1)<0.001
    delta=stops(codes,metadata)
    full=np.asarray(Image.fromarray(delta.astype(np.float32)).resize((rgb.shape[1],rgb.shape[0]),Image.Resampling.BILINEAR))
    sdr=linear_y(rgb)
    hdr_y=(sdr+metadata['OffsetSDR'])*np.exp2(full)-metadata['OffsetHDR']
    predicted,base=blocks(hdr_y),blocks(sdr)
    gh,gw=predicted.shape
    arr=np.fromfile(f,np.float32)
    assert len(arr)==2*gh*gw
    sys_sdr,sys_hdr=arr[:gh*gw].reshape(gh,gw),arr[gh*gw:].reshape(gh,gw)
    valid=(sys_sdr>0.01)&(base>0.01)
    err=np.abs(np.log2(sys_hdr[valid]/sys_sdr[valid])-np.log2(predicted[valid]/base[valid]))
    p99=float(np.percentile(err,99))
    assert p99<0.15,p99
    return {'recognized':True,'sdr_max_abs_diff':comparison['sdrMaxAbsDiff'],
            'headroom':comparison['hdrHeadroom'],'boost_error_p99_stops':p99,
            'boost_error_median_stops':float(np.median(err)), 'system_pixels':int(valid.sum()),**control}

def add(jpeg,raw,label,orig=None,system=False):
    out,stats=g.hdr_from_camera_jpeg(jpeg,raw)
    info,codes,rgb=inspect(jpeg,out)
    rec={'case':label,'format':info,'algorithm':stats}
    path=TMP/(label+'_HDR.jpg')
    path.write_bytes(out)
    if system:
        if orig is None:
            orig=TMP/(label+'_orig.jpg')
            orig.write_bytes(jpeg)
        rec['imageio']=system_check(orig,path,info,codes,rgb)
    records.append(rec)
    with (OUT/'format_cases.jsonl').open('a') as f:
        f.write(json.dumps(rec,ensure_ascii=False)+'\n')
    print(json.dumps({'case':label,'ok':True,'imageio':rec.get('imageio')}),flush=True)

for orientation in range(1,9):
    jpg,dng=hs.pair(0,orientation)
    add(jpg,g.raw_luma(open_dng(dng)),'orientation_'+str(orientation),system=True)

street=ROOT/'captures/street-g137-20261031'
names=sorted(p.stem for p in (street/'dng').glob('*.DNG') if (street/'jpg'/(p.stem+'.JPG')).exists())
for name in names:
    orig=street/'jpg'/(name+'.JPG')
    add(orig.read_bytes(),g.raw_luma(open_dng(street/'dng'/(name+'.DNG'))),'mount_'+name,orig=orig,system=True)

a12=ROOT/'captures/a12-50/2026-10-24/stage2l-daily-R8051312-1473'
names=sorted(p.stem for p in a12.glob('*.JPG') if (a12/(p.stem+'.DNG')).exists())[::10]
for name in names:
    orig=a12/(name+'.JPG')
    add(orig.read_bytes(),g.raw_luma(open_dng(a12/(name+'.DNG'))),'50mm_'+name,orig=orig,system=(name in ['R8051312','R8051435','R8051465']))

proto_path=ROOT/'research/hdr_gainmap/gxr_hdr.py'
spec=importlib.util.spec_from_file_location('frozen_hdr_prototype',proto_path)
prototype=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=prototype
spec.loader.exec_module(prototype)
equivalence=[]
for name in ['R8051530','R8051532','R8051627','R8051653']:
    orig=street/'jpg'/(name+'.JPG')
    path=TMP/(name+'_prototype.jpg')
    prototype.make_hdr(orig,street/'dng'/(name+'.DNG'),path)
    original=orig.read_bytes()
    pi,pc,_=inspect(original,path.read_bytes())
    si,sc,_=inspect(original,(TMP/('mount_'+name+'_HDR.jpg')).read_bytes())
    assert pi['iso_values']==si['iso_values']
    assert np.array_equal(pc,sc)
    equivalence.append({'case':name,'gain_pixels_identical':True,'iso_values_equal':True})

summary={'format_cases':len(records),'imageio_cases':sum('imageio' in r for r in records),'prototype_equivalence':equivalence,
         'imageio_boost_error_p99_max':max(r['imageio']['boost_error_p99_stops'] for r in records if 'imageio' in r)}
assert audit.network_attempts()==[]
(OUT/'format_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary))
