"""Per-unit/recipe integer dose tables, chosen and measured in display codes."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import support as s
s.dependencies()
import csv
import hashlib
import time
import numpy as np
import knobs as k
from bridge import C,compare
from model_adapter import Model,synthetic,masks,recipe_chart

THRESHOLD=1.0
CODE_INPUTS=('knobs.c','knobs.h','knobs.py','support.py','bridge.py','model_adapter.py','calibrate.py')
COLOUR=('amount','contrast','highlight','shadow','fade','saturation','warmth','tint','split')
BW=('contrast','highlight','shadow','fade','filter','tone')


def controls(slot):return BW if slot==3 else COLOUR


def score(model,la,lb,regions):
    de=model.de(la,lb)
    med=[float(np.median(de[m])) if m.sum()>=16 else None for m in regions]
    return min(v for v in med if v is not None) if any(v is not None for v in med) else 0.0,med


def tune(model,c,stock,base,param,x,wb_method=0,tone_method=0):
    regions=masks(model,base,x,param,chart=True)
    cache={}
    def output(dose):
        if dose not in cache:
            rq=k.request_for(param,dose,wb_method=wb_method,tone_method=tone_method)
            b,_=c.apply(stock,base,rq)
            rgb=model.predict(b,x,quantize=True)
            cache[dose]=(b,model.lab(rgb))
        return cache[dose]
    output(0)
    levels={0:0};pairs=[]
    for sign in (-1,1):
        prev=0;increment=0;previous_score=0
        for i in range(1,10):
            rem=10-i
            maxinc=(k.Q-prev-rem*(rem-1)//2)//rem
            lo=prev+increment+1;hi=prev+maxinc
            if lo>hi:raise AssertionError('convex dose budget')
            target=max(THRESHOLD+0.06*(i-1),previous_score+0.06)
            prev_bytes,prev_lab=output(sign*prev)
            def metric(d):return score(model,prev_lab,output(sign*d)[1],regions)[0]
            if metric(hi)<target:chosen=hi
            else:
                left,right=lo,hi
                while left<right:
                    mid=(left+right)//2
                    if metric(mid)>=target:right=mid
                    else:left=mid+1
                chosen=left
            b,lab=output(sign*chosen);sc,med=score(model,prev_lab,lab,regions)
            levels[sign*i]=sign*chosen
            pairs.append(dict(from_level=sign*(i-1),to_level=sign*i,dose_from=sign*prev,dose_to=sign*chosen,
                              target_de00=target,region_medians=med,region_counts=[int(m.sum()) for m in regions],
                              min_median_de00=sc,byte_dead=b==prev_bytes,visible=sc>=THRESHOLD,
                              target_met=sc>=target))
            increment=chosen-prev;prev=chosen;previous_score=sc
    if param=='filter':
        # Green and red are fixed semantic endpoints; distribute the tuned
        # interior doses over the full path instead of stopping at yellow.
        for sign in (-1,1):
            endpoint=abs(levels[9*sign])
            for i in range(1,10):levels[i*sign]=sign*k.rd(abs(levels[i*sign])*k.Q,endpoint)
        for p in pairs:
            a,b=levels[p['from_level']],levels[p['to_level']]
            aa,la=output(a);bb,lb=output(b);sc,med=score(model,la,lb,regions)
            p.update(dose_from=a,dose_to=b,region_medians=med,min_median_de00=sc,
                     byte_dead=aa==bb,visible=sc>=THRESHOLD,target_met=sc>=p['target_de00'])
    return levels,pairs


def main():
    s.guard();s.freeze_inputs();code_hashes={name:s.sha(s.HERE/'src'/name) for name in CODE_INPUTS}
    modules=s.parse();c=C();model=Model();x=synthetic()
    assert abs(float(model.de(np.array([[50,2.6772,-79.7751]]),np.array([[50,0,-82.7485]]))[0])-2.0425)<0.00005
    outdir=s.HERE/'tables';outdir.mkdir(exist_ok=True)
    groups=[];rows=[];variants=[];binary=bytearray();start=time.monotonic()
    for m in modules:
        stock=m['entries'][4]
        for slot in range(1,9):
            base=m['entries'][slot];unit=m['name'];x=recipe_chart(model,base)
            np.savez_compressed(s.LOCAL/f'chart-{unit}-{slot:02d}.npz',x=x)
            for param in controls(slot):
                if param=='amount':
                    dose_map={a:a for a in range(0,151,10)};pairs=[];prev=None
                    regions=masks(model,base,x,param,chart=True)
                    for a in dose_map:
                        b,_=compare(c,stock,base,k.Request(a));lab=model.lab(model.predict(b,x,quantize=True))
                        if prev is not None:
                            sc,med=score(model,prev[2],lab,regions)
                            pairs.append(dict(from_level=prev[0],to_level=a,dose_from=prev[0],dose_to=a,
                                              target_de00=THRESHOLD,region_medians=med,region_counts=[int(z.sum()) for z in regions],
                                              min_median_de00=sc,byte_dead=b==prev[1],visible=sc>=THRESHOLD,target_met=sc>=THRESHOLD))
                        prev=(a,b,lab)
                else:dose_map,pairs=tune(model,c,stock,base,param,x)
                group=dict(unit=unit,slot=slot,param=param,wb_method=0,tone_method=0,
                           doses={str(a):d for a,d in sorted(dose_map.items())},pairs=pairs)
                groups.append(group)
                for level,dose in sorted(dose_map.items()):
                    rq=k.Request(level) if param=='amount' else k.request_for(param,dose)
                    b,stats=compare(c,stock,base,rq);offset=len(binary);binary+=b
                    variants.append(dict(unit=unit,slot=slot,param=param,level=level,dose=dose,offset=offset,
                                         sha256=hashlib.sha256(b).hexdigest(),stats=stats))
                    rows.append(dict(unit=unit,slot=slot,param=param,level=level,dose=dose,
                                     q=4096,domain='percent' if param=='amount' else 'Q12',
                                     adjacent_min_median_de00=next((p['min_median_de00'] for p in pairs if p['to_level']==level),'')))
            print(f'calibrated {unit} {slot:02d}: {time.monotonic()-start:.1f}s',flush=True)
    with (outdir/'steps.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    for m in modules:
        for slot in range(1,9):
            selected=[r for r in rows if r['unit']==m['name'] and r['slot']==slot]
            with (outdir/f'{m["name"]}-{slot:02d}.csv').open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(selected)
    (s.LOCAL/'variants.bin').write_bytes(binary)
    s.dump(s.LOCAL/'variants.json',variants)
    s.dump(s.LOCAL/'calibration.json',dict(schema='knobs-v2-r1/calibration/1',threshold=THRESHOLD,
             evaluation='clipped and rounded 8-bit RGB, sRGB D65 Lab, CIEDE2000',
             samples=len(x),sample_kind='257 neutral patches uniform in recipe baseline output Y + fixed 9^3 log RGB cube',groups=groups,
             groups_count=len(groups),variants_count=len(variants),code_inputs=code_hashes,
             conditional_controls=['03 Tone'],transfer_units=['qlaunch','l08firm'],
             elapsed_seconds=time.monotonic()-start))
    # Alternatives use the same criterion; never imply equal doses have equal visual strength.
    alternatives=[]
    for m in modules:
        for slot in range(1,9):
            x=recipe_chart(model,m['entries'][slot])
            params=('tone',) if slot==3 else ('warmth','tint')
            for param in params:
                wm,tm=(0,1) if param=='tone' else (1,0)
                levels,pairs=tune(model,c,m['entries'][4],m['entries'][slot],param,x,wm,tm)
                alternatives.append(dict(unit=m['name'],slot=slot,param=param,wb_method=wm,tone_method=tm,
                                         doses={str(a):d for a,d in sorted(levels.items())},pairs=pairs))
                for dose in levels.values():compare(c,m['entries'][4],m['entries'][slot],k.request_for(param,dose,wb_method=wm,tone_method=tm))
        print('alternatives',m['name'],flush=True)
    s.dump(s.LOCAL/'alternatives.json',alternatives)
    with (outdir/'alternatives.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=('unit','slot','param','wb_method','tone_method','level','dose'))
        writer.writeheader()
        for g in alternatives:
            for level,dose in g['doses'].items():
                writer.writerow({**{key:g[key] for key in ('unit','slot','param','wb_method','tone_method')},'level':level,'dose':dose})
    s.dump(s.LOCAL/'model_inputs_calibration.json',model.provenance());s.verify_inputs()
    if code_hashes!={name:s.sha(s.HERE/'src'/name) for name in CODE_INPUTS}:raise ValueError('calibration source changed during run')
    failures=[dict(unit=g['unit'],slot=g['slot'],param=g['param'],**p) for g in groups for p in g['pairs'] if not p['visible'] or p['byte_dead']]
    s.dump(s.LOCAL/'calibration_failures.json',failures)
    print('DONE',len(variants),'variants;',len(failures),'failed pairs;',time.monotonic()-start,'seconds',flush=True)

if __name__=='__main__':main()
