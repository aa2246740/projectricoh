"""Retain the synthetic API result and measure the local gain error."""
import io
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-hdr')
sys.path[:0]=[str(OUT),str(ROOT/'studio/src'),str(ROOT/'studio/tests')]
import numpy as np
from PIL import Image
import hdr_support as hs
from format_oracle import inspect,stops,digest
from gxr_studio import audit
from gxr_studio.hdr import gain as g
from gxr_studio.raw import open_dng

audit.forbid_network(True)
audit.forbid_volumes()
evidence=OUT/'evidence'
evidence.mkdir(exist_ok=True)
folder=TMP/'edits/volumes/NO NAME/DCIM/100RICOH'
jpeg=(folder/'MOTION.JPG').read_bytes()
raw=g.raw_luma(open_dng(folder/'MOTION.DNG'))
al=g.align(g.sdr_luma_grid(g.decode_rgb(jpeg),4),raw.y)
g.check_alignment(al)
records=[json.loads(s) for s in (OUT/'edit_cases.jsonl').read_text().splitlines()]
api=next(r for r in records if r.get('case')=='MOTION')
paths=list((TMP/'edits/library/.studio/hdr').rglob('*.jpg'))
matched=[p for p in paths if digest(p.read_bytes())==api['format']['hdr_sha256']]
assert len(matched)==1
wrong=matched[0].read_bytes()
info,codes,_=inspect(jpeg,wrong)
second=hs.scene(seed=0)
second[96:136,500:540]=0.035
correct,_=g.hdr_from_camera_jpeg(jpeg,g.raw_luma(open_dng(hs.camera_dng(second))))
ci,cc,_=inspect(jpeg,correct)
gain_wrong,gain_correct=stops(codes,info['iso_values']),stops(cc,ci['iso_values'])
roi=(slice(25,33),slice(106,114))
delta=gain_correct-gain_wrong
effect={'max_abs_gain_difference_stops':float(np.abs(delta).max()),
        'old_object_region_median_gain_deficit_stops':float(np.median(delta[roi])),
        'fraction_difference_gt_0p25':float((np.abs(delta)>0.25).mean())}
assert effect['max_abs_gain_difference_stops']>0.75
assert effect['old_object_region_median_gain_deficit_stops']>0.25
files={
    'motion_input.JPG':folder/'MOTION.JPG',
    'motion_wrong_input.DNG':folder/'MOTION.DNG',
    'motion_import_HDR.jpg':matched[0],
    'motion_export_HDR.jpg':next((TMP/'edits/exports').glob('MOTION_gxr*.jpg')),
}
hashes={}
for name,source in files.items():
    target=evidence/name
    shutil.copy2(source,target)
    hashes[name]={'sha256':digest(target.read_bytes()),'bytes':target.stat().st_size}
target=evidence/'motion_correct_reference_HDR.jpg'
target.write_bytes(correct)
hashes[target.name]={'sha256':digest(correct),'bytes':len(correct)}

a=g._hp(g.sdr_luma_grid(g.decode_rgb(jpeg),4))
b=g._hp(g.warp(raw.y,a.shape,al.scale,al.dy,al.dx))
tiles=[]
def normalized(v):
    return (v-v.mean())/(v.std()+1e-6)
for i in range(4):
    for j in range(4):
        y0,y1=max(3,i*a.shape[0]//4),min(a.shape[0]-3,(i+1)*a.shape[0]//4)
        x0,x1=max(3,j*a.shape[1]//4),min(a.shape[1]-3,(j+1)*a.shape[1]//4)
        tile=a[y0:y1,x0:x1]
        texture=float(tile.std())
        if tile.size<64 or texture<0.1:
            tiles.append({'row':i,'column':j,'checked':False,'texture':texture})
            continue
        norm=normalized(tile)
        candidates=[]
        for dy in range(-3,4):
            for dx in range(-3,4):
                corr=float(np.mean(norm*normalized(b[y0+dy:y1+dy,x0+dx:x1+dx])))
                candidates.append((corr,dy,dx))
        here=next(c for c,y,x in candidates if y==x==0)
        best=max(candidates)
        tiles.append({'row':i,'column':j,'checked':True,'texture':texture,'here':here,'best':best[0],
                      'best_shift':[best[1],best[2]],'improvement':best[0]-here})

result={'known_motion_pixels':80,'object_wh':[40,40],'gain_grid_known_motion_pixels':20,
        'gain_grid_search_reach':3,'alignment':al.to_dict(),'correlation_full':al.correlation,
        'import_status':api['status'],'export_hdr':True,'export_note':None,
        'effect':effect,'evidence_files':hashes,'tiles':tiles,'all_evidence_synthetic':True}
system=[]
for name in ['motion_import_HDR.jpg','motion_correct_reference_HDR.jpg']:
    f=TMP/('system_'+name+'.f32')
    process=subprocess.run([str(TMP/'format/check_imageio'),'--compare',str(evidence/'motion_input.JPG'),str(evidence/name),str(f)],
                           check=True,capture_output=True,text=True,timeout=360)
    fields=json.loads(process.stdout)
    values=np.fromfile(f,np.float32)
    count=gain_wrong.size
    assert values.size==2*count
    base,rendered=values[:count].reshape(gain_wrong.shape),values[count:].reshape(gain_wrong.shape)
    system.append(np.log2(np.maximum(rendered,1e-6)/np.maximum(base,1e-6)))
    result.setdefault('system_decode',{})[name]=fields
system_delta=system[1]-system[0]
result['system_effect']={'old_object_region_median_gain_deficit_stops':float(np.median(system_delta[roi])),
                         'max_abs_gain_difference_stops':float(np.abs(system_delta).max())}
assert result['system_effect']['old_object_region_median_gain_deficit_stops']>0.2
assert result['system_effect']['max_abs_gain_difference_stops']>0.5
assert audit.network_attempts()==[]
(OUT/'alignment_detail.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['alignment','import_status','export_hdr','effect','system_effect','evidence_files']}))
