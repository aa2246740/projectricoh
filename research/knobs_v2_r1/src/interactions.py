"""Adjacent visibility inside the requested extreme contexts, including Amount."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import support as s
s.dependencies()
import csv
import hashlib
import json
import time
import numpy as np
import knobs as k
from bridge import C,compare
from checks import inspect,changed
from model_adapter import Model,masks


def main():
    s.guard();s.verify_inputs();modules=s.parse();model=Model();c=C(build=False);start=time.monotonic()
    cal=json.loads((s.LOCAL/'calibration.json').read_text());alts=json.loads((s.LOCAL/'alternatives.json').read_text())
    assert cal['code_inputs']=={name:s.sha(s.HERE/'src'/name) for name in cal['code_inputs']}
    gi={(g['unit'],g['slot'],g['param'],g.get('wb_method',0)):g for g in cal['groups']+alts if not g.get('tone_method',0)}
    pair_count=state_count=0;failures=dead=incomplete=0;group_results=[];limit_rows=[];events=[]
    fields=('unit','slot','param','wb_method','context','context_level','from_level','to_level','byte_dead',
            'entry_byte_diff','region0_n','region0_median','region1_n','region1_median','min_median_de00','visible','complete')
    target=s.LOCAL/'interaction_adjacent.csv'
    with target.open('w',newline='') as file:
        writer=csv.DictWriter(file,fieldnames=fields);writer.writeheader()
        for m in modules:
            for slot in range(1,9):
                unit=m['name'];base=m['entries'][slot];stock=m['entries'][4]
                with np.load(s.LOCAL/f'chart-{unit}-{slot:02d}.npz',allow_pickle=False) as z:x=z['x'].copy()
                cache={}
                contexts=[]
                for param,context in (('contrast','highlight'),('highlight','contrast'),('fade','shadow'),('shadow','fade')):
                    contexts.extend((param,context,level,0) for level in (-9,9))
                if slot!=3:
                    for param,context in (('saturation','split'),('split','saturation')):
                        contexts.extend((param,context,level,0) for level in (-9,9))
                    for param in ('contrast','highlight','shadow','fade','saturation','warmth','tint','split'):
                        contexts.extend((param,'amount',a,0) for a in range(0,151,10))
                    for param in ('warmth','tint'):
                        contexts.extend((param,'amount',a,1) for a in range(0,151,10))
                for param,context,context_level,wm in contexts:
                    g=gi[unit,slot,param,wm];regions=masks(model,base,x,param,chart=True);prev=None
                    nfail=ndead=ninc=0;minimum=1000.0
                    for level in range(-9,10):
                        ds=[0]*10;ds[k.PARAMS.index(param)]=g['doses'][str(level)]
                        if context=='amount':amount=context_level
                        else:
                            amount=100;cg=gi[unit,slot,context,0]
                            ds[k.PARAMS.index(context)]=cg['doses'][str(context_level)]
                        b,st=compare(c,stock,base,k.Request(amount,tuple(ds),wm));state_count+=1
                        info=inspect(b)
                        if info['errors']:raise AssertionError((unit,slot,param,context,context_level,level,info['errors']))
                        tag=dict(unit=unit,slot=slot,param=param,wb_method=wm,context=context,context_level=context_level,level=level)
                        for lim in info['limits']:limit_rows.append(dict(**tag,**lim))
                        if any(st.values()):events.append(dict(**tag,**st))
                        if b not in cache:cache[b]=model.lab(model.predict(b,x,quantize=True))
                        lab=cache[b]
                        if prev is not None:
                            de=model.de(prev[2],lab)
                            med=[float(np.median(de[r])) if r.sum()>=16 else None for r in regions]
                            complete=all(v is not None for v in med)
                            score=min(med) if complete else None
                            visible=bool(complete and score>=1.0);same=prev[1]==b
                            row=dict(unit=unit,slot=slot,param=param,wb_method=wm,context=context,context_level=context_level,
                                     from_level=prev[0],to_level=level,byte_dead=same,
                                     entry_byte_diff=sum(a!=z for a,z in zip(prev[1],b)),
                                     region0_n=int(regions[0].sum()),region0_median=med[0],
                                     region1_n=int(regions[1].sum()) if len(regions)==2 else '',
                                     region1_median=med[1] if len(regions)==2 else '',
                                     min_median_de00=score,visible=visible,complete=complete)
                            writer.writerow(row);pair_count+=1;failures+=not visible;dead+=same;incomplete+=not complete
                            nfail+=not visible;ndead+=same;ninc+=not complete
                            if score is not None:minimum=min(minimum,score)
                        prev=(level,b,lab)
                    group_results.append(dict(unit=unit,slot=slot,param=param,wb_method=wm,context=context,context_level=context_level,
                                               pairs=18,below_threshold=nfail,byte_dead=ndead,incomplete=ninc,min_de00=minimum))
                print('interaction contexts',unit,f'{slot:02d}',state_count,'states',f'{time.monotonic()-start:.1f}s',flush=True)
    for name,rows in (('interaction_limits.csv',limit_rows),('interaction_events.csv',events)):
        with (s.LOCAL/name).open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    s.dump(s.LOCAL/'interaction_groups.json',group_results)
    summary=dict(status='PASS_HOST_STRUCTURE_VISIBILITY_FAIL' if failures else 'PASS_HOST_CHART',
                 states=state_count,pairs=pair_count,groups=len(group_results),below_threshold=failures,byte_dead=dead,
                 incomplete=incomplete,limit_records=len(limit_rows),limit_event_states=len(events),max_curve_jump_bound=1,
                 threshold=1.0,transfer_units=['qlaunch','l08firm'],elapsed_seconds=time.monotonic()-start)
    s.dump(s.LOCAL/'interaction_verification.json',summary)
    s.dump(s.LOCAL/'model_inputs_interactions.json',model.provenance());s.verify_inputs()
    print(json.dumps(summary,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
