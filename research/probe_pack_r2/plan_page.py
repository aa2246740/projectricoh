"""Plan spatially compensated screen greys from the frozen field RAW samples."""
import os
import sys
from pathlib import Path
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','VECLIB_MAXIMUM_THREADS'):os.environ[key]='1'
sys.dont_write_bytecode=True
import hashlib
import json
import numpy as np
from scipy import interpolate,optimize
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=HERE/'local'
PRIOR=ROOT/'research/probe_pack_r1/local/ramp_field_20261103'


def light(code):
    v=np.asarray(code)/255
    return np.where(v<=.04045,v/12.92,((v+.055)/1.055)**2.4)


def code(v):
    v=np.maximum(v,0)
    return np.where(v<=.0031308,v*12.92,1.055*v**(1/2.4)-.055)*255


def main():
    assert os.getpriority(os.PRIO_PROCESS,0)>=10
    refs=[json.loads((PRIOR/f'frames/R805{n}.json').read_text())['patches']['0.5'] for n in (1926,1933)]
    source_gray=np.array([p['screen_rgb'][0] for p in refs[0][:49]])
    measured=np.mean([[p['raw_wb'] for p in r[:49]] for r in refs],axis=0)
    model=json.loads((PRIOR/'model.json').read_text());xs=np.array(model['xs'])
    bracket=ROOT/'research/probe_pack_r1/local/bracket_20261103/frames/R8051902.json'
    noon=json.loads(bracket.read_text())['patches']['0.5'][:3]
    md=json.loads((bracket.parents[1]/'metadata.json').read_text());neutral=next(r['dng']['as_shot_neutral'] for r in md if r['frame']=='R8051902')
    noonraw=np.array([p['raw_dn_mean'] for p in noon])/neutral
    F=interpolate.PchipInterpolator([48,128,208],noonraw,axis=0)
    morning=ROOT/'research/probe_pack_r1/local/field_20261103'
    assignments=json.loads((morning/'assignments.json').read_text())['frames']
    mmeta={r['frame']:r['dng'] for r in json.loads((morning/'metadata.json').read_text())}
    mpaths=[morning/'frames'/(r['frame']+'.json') for r in assignments if r['label']=='A']
    mvalues=[]
    for path in mpaths:
        frame=json.loads(path.read_text());neutral_m=np.array(mmeta[path.stem]['as_shot_neutral'])
        assert abs(mmeta[path.stem]['exposure_s']-1/30)<1e-9
        mvalues.append(np.array([p['raw_dn_mean'] for p in frame['patches']['0.5'][:3]])/neutral_m*2)
    FM=interpolate.PchipInterpolator([48,128,208],np.median(mvalues,axis=0),axis=0)
    candidates=[]
    for highnode,maxR in [(20,1750),(19,1500)]:
        pages={}
        for phase in ('p1','p2'):
            if phase=='p1':targets=np.linspace(360,910,49)
            else:
                high=np.r_[650,720,np.linspace(760,1480,24),1600,1750] if highnode==20 else np.r_[550,620,np.linspace(660,1280,24),1400,1500]
                targets=np.r_[np.linspace(50,185,21),high]
            # Hungarian assignment keeps code changes modest and avoids clipping
            # while spreading targets across the existing physical grey cells.
            floating=code(light(source_gray)[:,None]*targets[None,:]/measured[:,0,None])
            wanted=(np.arange(49)*19)%49
            cost=np.abs(np.log(targets[None,:]/measured[:,0,None]))+.002*np.abs(np.arange(49)[None,:]-wanted[:,None])
            cost+=np.maximum(floating-252,0)*100+np.maximum(32-floating,0)*10
            ii,jj=optimize.linear_sum_assignment(cost)
            chosen=np.rint(floating[ii,jj]).astype(int)
            clipped=bool(np.any((chosen<20)|(chosen>254)))
            chosen=np.clip(chosen,20,254)
            predictions={
                'srgb':measured*(light(chosen)/light(source_gray))[:,None],
                'gamma22':measured*((chosen/source_gray)**2.2)[:,None],
                'noon_PCHIP':measured*F(chosen)/F(source_gray),
                'morning_PCHIP_projected_1_15':measured*FM(chosen)/FM(source_gray)
            }
            rows=[]
            nodes=[16] if phase=='p1' else [8,highnode]
            for transfer,values in predictions.items():
                for scale in (1.,.9,1.1):
                    for c,ch in enumerate('RGB'):
                        vv=values[:,c]*scale
                        for node in nodes:
                            l,p,r=xs[node-1:node+2];s=np.sort(vv[(vv>l)&(vv<r)])
                            row=dict(transfer=transfer,scale=scale,channel=ch,node=node,
                                left_points=int(np.sum((vv>l)&(vv<p))),right_points=int(np.sum((vv>p)&(vv<r))),
                                below_support=bool(min(vv)<l),above_support=bool(max(vv)>r),
                                nearest_peak=float(min(abs(vv-p))),max_gap=float(max(np.diff(np.r_[l,s,r]))))
                            rows.append(row)
            pages[phase]=dict(codes=chosen.tolist(),target_R=targets[jj].tolist(),clipped=clipped,predictions={k:v.tolist() for k,v in predictions.items()},coverage=rows)
        nominal_ok=all(not p['clipped'] for p in pages.values()) and all(
            r['left_points']>=3 and r['right_points']>=3 and r['below_support'] and r['above_support']
            for p in pages.values() for r in p['coverage'] if r['transfer']=='srgb' and r['scale']==1)
        robust_ok=all(r['left_points']>=2 and r['right_points']>=2 and r['below_support'] and r['above_support']
            for p in pages.values() for r in p['coverage'])
        candidates.append(dict(high_node=highnode,nominal_ok=nominal_ok,robust_ok=robust_ok,pages=pages))
    for candidate in candidates:
        print('CANDIDATE',candidate['high_node'],'nominal',candidate['nominal_ok'],'sensitivity',candidate['robust_ok'],flush=True)
        for phase,page in candidate['pages'].items():
            print(phase,'codes',min(page['codes']),max(page['codes']),'clipped',page['clipped'],flush=True)
            for r in page['coverage']:
                if r['transfer']=='srgb' and r['scale']==1:print(r,flush=True)
    result=dict(status='CANDIDATES',exposure_s=1/15,actual_f_number=5.6,P2_candidates=candidates,
        source_grays=source_gray.tolist(),source_raw_wb=measured.tolist(),node_inputs=xs.tolist(),
        method='Per-cell RAW reference times assumed display-light ratio; no new field capture yet.',
        limitations='Same window size, internal screen preset, brightness, lens, aperture, distance and angle assumed. Predictions need the new A RAW check.')
    (OUT/'page-plan-candidates.json').write_text(json.dumps(result,indent=2)+'\n')
    chosen=next(v for v in candidates if v['nominal_ok'] and v['robust_ok'])
    assert chosen['high_node']==19
    colored=np.mean([[p['raw_wb'] for p in r[49:]] for r in refs],axis=0)
    original=np.array([p['screen_rgb'] for p in refs[0][49:]])
    # Original colour order is sky / skin / leaf. Uniform linear-light scaling
    # retains the source hue while targeting the channel under measurement.
    for phase,page in chosen['pages'].items():
        target=xs[16 if phase=='p1' else 19]
        colors=[]
        for ci,(name,channel) in enumerate([('B色块',2),('肤色',0),('绿叶',1)]):
            gain=1. if phase=='p1' and ci==1 else target/colored[ci,channel]
            rgb=np.rint(code(light(original[ci])*gain)).astype(int)
            assert np.all((rgb>0)&(rgb<255))
            achieved=float(np.mean(light(rgb)/light(original[ci])))
            predicted=colored[ci]*achieved
            node=16 if phase=='p1' else 19
            assert xs[node-1]<predicted[channel]<xs[node+1]
            colors.append(dict(id=['blue','skin','leaf'][ci],label=name,rgb=rgb.tolist(),
                target_channel='RGB'[channel],predicted_raw_wb=predicted.tolist()))
        page['colors']=colors
    selected=dict(status='PASS_PREDICTION_ONLY',exposure_s=1/15,actual_f_number=5.6,P1_node=16,P2_nodes=[8,19],
        pages=chosen['pages'],nominal_ok=chosen['nominal_ok'],sensitivity_ok=chosen['robust_ok'],
        rejected_candidate=dict(nodes=[8,20],reason='R high support not bracketed under noon PCHIP transfer at -10% exposure'),
        source_files={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [
            PRIOR/'frames/R8051926.json',PRIOR/'frames/R8051933.json',PRIOR/'model.json',bracket,bracket.parents[1]/'metadata.json',
            morning/'metadata.json',morning/'assignments.json',*mpaths]},
        limitation=result['limitations'])
    (OUT/'page-plan.json').write_text(json.dumps(selected,indent=2,ensure_ascii=False)+'\n')


if __name__=='__main__':main()
