#!/usr/bin/env python3
"""Replay existing photo/scene and 128 output-quantization gates, count bytes."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import analyze as a
from analyze import ROOT,LOCAL,np,read,dump,stats,de,sha
import history as h
import physical
import refit
import itertools
import struct
import zlib


def metric(error,denom):
    value=stats(error);baseline=float(np.median(denom))
    value['similarity_percent']=None if baseline<.25 else 100*(1-value['median']/baseline)
    return value


def photo_gate(bank,before,after,model,unit):
    source=ROOT/f'research/recipe_redo_r1/local/inputs/{unit}/photos.json'
    info=read(source) if source.exists() else []
    result={};failures=[]
    for name,v in bank.items():
        if name in ('train','synthetic') or not len(v['x']):continue
        want=model.fs.lab_from_codes(v['want'])
        denominator=model.fs.delta_e00(model.fs.lab_from_codes(v['base_new']),want)
        old=model.fs.delta_e00(model.fs.lab_from_codes(before[name]),want)
        new=model.fs.delta_e00(model.fs.lab_from_codes(after[name]),want)
        photos=[];a_finite=[];b_finite=[]
        for pid in sorted(set(v['photo_id'].tolist())):
            use=v['photo_id']==pid;x=metric(old[use],denominator[use]);y=metric(new[use],denominator[use])
            absolute=all(y[k]<=x[k]+max(32*abs(float(np.spacing(x[k]))),1e-13) for k in ('median','p95'))
            if x['similarity_percent'] is None:
                if y['similarity_percent'] is not None or not absolute:failures.append(name+'/None/'+str(pid))
            else:a_finite.append(x['similarity_percent']);b_finite.append(y['similarity_percent'])
            photos.append(dict(photo_id=int(pid),current=x,candidate=y,None_absolute_pass=absolute))
        delta=None
        if a_finite:
            delta=float(np.median(b_finite)-np.median(a_finite))
            if delta<-.1-1e-12:failures.append(name+'/0.1pp')
        scenes=[]
        if name=='photo_iso200':
            scene_labels=np.array([info[int(i)]['scene_group'] for i in v['photo_id']])
            scene_masks=[(label,scene_labels==label) for label in sorted(set(scene_labels))]
        elif name=='new7_RAW_target':scene_masks=[('whole_collection',np.ones(len(old),bool))]
        else:scene_masks=[]
        for label,mask in scene_masks:
            x=metric(old[mask],denominator[mask]);y=metric(new[mask],denominator[mask])
            passed=all(y[k]<=x[k]+1e-10 for k in ('median','p95'))
            scenes.append(dict(scene=label,current=x,candidate=y,passed=passed))
            if not passed:failures.append(name+'/'+label)
        result[name]=dict(photo_median_delta_pp=delta,photos=photos,scenes=scenes,
            current=metric(old,denominator),candidate=metric(new,denominator))
    missing=[g for g in ('photo_iso200','photo_other_iso') if g not in bank]
    failures.extend('missing/'+g for g in missing)
    return dict(passes=not failures,status='UNMEASURED' if missing else 'PASS' if not failures else 'FAIL',failures=failures,groups=result,
        missing_photo_holdouts=missing,
        metric='frozen engine D65 DE00 for compatibility with the existing publication rubric')


def phase_output(rgb,phase,order,mm):
    if order=='RGB8_then_YCbCr8':rgb=np.rint(rgb)
    y,c=mm.ycbcr(rgb);ycc=np.stack([y,c.real+128,c.imag+128],axis=1)
    nearest=np.rint(ycc);ycc=np.where(abs(ycc-nearest)<1e-9,nearest,ycc)
    q=np.clip(np.floor(ycc+phase),0,255)
    return np.rint(np.clip(mm.rgb_from_ycc(q[:,0],(q[:,1]-128)+1j*(q[:,2]-128)),0,255))


def main():
    cap=a.module('blue_capacity',ROOT/'research/recipe_redo_r1/round3_mount/local/capacity.py')
    baseline={p:cap.count(p) for p in ('release','test')}
    assert all(r['net_bytes']==0 for r in baseline.values())
    hm=h.Models();result=[];replacements={};mount_replacements={}
    fmt=a.module('blue_assess_dat',ROOT/'research/v39_g153/dat_format.py')
    data=(ROOT/'firmware/package_v310_g156_test/GXRCE.DAT').read_bytes()
    for unit in ('mount-a12','a12-50','a12-28'):
      ui=('a12-50','a12-28','mount-a12').index(unit)
      model=hm.model(unit,200,read(LOCAL/'history/inventory.json')[0]['metadata']['color_raw13'])
      physical.update_model(model,unit)
      stock=fmt.expand(data,ui,4)
      for slot in (5,6):
        source=LOCAL/f'physical/guarded_fits/{unit}/{slot:02d}/exact.json';doc=read(source)
        candidate_path=LOCAL/doc['record_file'];entry=candidate_path.read_bytes();current=fmt.expand(data,ui,slot)
        assert sha(candidate_path)==doc['record_sha256']
        bank=refit.groups(unit,slot+26,True);before={};after={};scores={}
        for name,v in bank.items():
            v['base_new']=model.predict(stock,v['x'])
            before[name]=model.predict(current,v['x']);after[name]=model.predict(entry,v['x'])
            scores[name]=dict(current=stats(de(np.rint(before[name]),v['want'])),candidate=stats(de(np.rint(after[name]),v['want'])))
        gate=photo_gate(bank,{k:np.rint(v) for k,v in before.items()},{k:np.rint(v) for k,v in after.items()},model,unit)
        quant=[]
        if unit=='mount-a12':
            for order in ('YCbCr8_then_RGB8','RGB8_then_YCbCr8'):
                for phase in itertools.product((0.,.25,.5,.75),repeat=3):
                    old={k:phase_output(v,np.array(phase),order,model.mm) for k,v in before.items()}
                    new={k:phase_output(v,np.array(phase),order,model.mm) for k,v in after.items()}
                    q=photo_gate(bank,old,new,model,unit)
                    quant.append(dict(order=order,phase=phase,passes=q['passes'],failures=q['failures']))
        name='05 F-CC' if slot==5 else '06 F-CN'
        repl={(ui,name):candidate_path};replacements.update(repl)
        if ui==2:mount_replacements.update(repl)
        costs={p:cap.count(p,repl) for p in ('release','test')}
        record=dict(unit=unit,slot=slot,record_sha256=sha(candidate_path),record_file=str(candidate_path.relative_to(LOCAL)),
            standalone_bytes=len(entry),nominal_photo_gate=gate,quality=doc['quality'],scores=scores,costs=costs,
            quantization=quant,quantization_passes=sum(q['passes'] for q in quant),quantization_branches=len(quant),
            full_historical_model_error_budget_pass=False,
            historical_budget_reason='prior signed node16 response budget does not bound a global C080 and full-curve refit',
            actual_candidate_camera_exposures=0,no_DAT_built=True)
        result.append(record);dump('acceptance-progress.json',result)
        print(unit,slot,'nominal',gate['passes'],'failures',len(gate['failures']),'quant',record['quantization_passes'],'/',len(quant),
              'net bytes',costs['test']['net_bytes'],flush=True)
    dump('acceptance.json',dict(records=result,baseline_capacity=baseline,
        combined_mount={p:cap.count(p,mount_replacements) for p in ('release','test')},
        combined_all_units={p:cap.count(p,replacements) for p in ('release','test')},
        eligibility='not approved for g157 until photo, sensitivity, capacity and final package gates are closed'))


if __name__=='__main__':main()
