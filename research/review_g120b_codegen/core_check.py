"""Compare final gateway directions and the complete forwarded request."""
from pathlib import Path
import itertools
import json
import random
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
from review_scope import SOURCE,OUT,load,save,sha,record_inputs
from current_runtime import differential as d


def main():
    m=load(SOURCE/'misc_diff.py','review_core_misc')
    p=d.Pair()
    m.setup(p,'core_call')
    p.hook('view_owned',lambda b,r:p.mode['owned'])
    p.hook('eng_visible_rows',lambda b,r:8)
    rng=random.Random(0x120b30)
    rows,failures,c_cases=[],[],[]
    seen={119:set(),120:set()}
    scenarios=[]
    for sid,op,watch,owned,uncertain,row in itertools.product((2,4,6),range(1,6),range(3),range(2),range(2),(0,1,2,9)):
        scenarios.append(dict(sid=sid,op=op,watch=watch,owned=owned,uncertain=uncertain,row=row,size=0,status=0,native=0))
    for size,status,native in itertools.product((0,1,40,80,81),(-1,0),(-1,0,65535,65536)):
        scenarios.append(dict(sid=4,op=2,watch=1,owned=1,uncertain=0,row=1,size=size,status=status,native=native))
    for index,case in enumerate(scenarios):
        args,extra,_=m.prepare(p,'core_call',rng,index,True)
        p.mode.update(status=case['status'],native=case['native'],token=0x88,owned=case['owned'])
        args=(0,case['sid'],case['op'],0x1234)
        extra=(0,m.BUF,case['size'],0,m.REPLY)
        for r in p.rs:
            r.write(r.n+3713,bytes([case['watch'],0,0]))
            r.write(p.g[r.g]+2527,bytes([case['uncertain']]))
            r.write(p.g[r.g]+862,b'\1')
            r.write(p.g[r.g]+866,b'\x08')
            r.write(0x2022f726,bytes([case['row']]))
        results=[]
        for r in p.rs:
            r.reset(0x120b3000+index)
            results.append(r.call('core_call',args,extra,steps=20000))
        old,new=results
        projections=[p.projection(r,x) for r,x in zip(p.rs,results)]
        new_flag=[bytes.fromhex(data)[0] for address,data,pc in new['writes']
                  if address==p.g[120]+2537]
        if new_flag:
            restored=dict(projections[1])
            restored[0x50000000+2537]=new_flag
            projections[1]=sorted(restored.items())
        same=projections[0]==projections[1]
        intended=False
        if not same and (case['sid']==4 and case['watch']==2 and case['owned']==1
                         and case['uncertain']==0 and 1<=case['row']<=8 and case['row']!=1):
            aa,bb=map(dict,projections)
            old_flag=aa.pop(0x50000000+2537,None)
            new_flag=bb.pop(0x50000000+2537,None)
            intended=old_flag==[1] and new_flag is None and aa==bb
            if intended:
                c_cases.append(dict(index=index,case=case,old_flag=old_flag,new_flag=new_flag,
                    contract='Fn2 numeric rows do not select recipe-list slots. Only watch_view==1 compares the native row with the recipe-list cursor before the first W.'))
        ok=(old['stop']['reason']==new['stop']['reason']=='return' and
            old['result']==new['result'] and old['saved']==new['saved'] and
            old['abi_ok'] and new['abi_ok'] and (same or intended))
        rows.append(dict(index=index,case=case,ok=ok,intended_change=intended,results=[x['result'] for x in results],
            stops=[x['stop'] for x in results],edges={r.g:x['edges'] for r,x in zip(p.rs,results)}))
        for r,result in zip(p.rs,results):
            seen[r.g].update(map(tuple,result['edges']))
        if not ok:
            save('core-first-difference.json',dict(row=rows[-1],old=old,new=new,
                old_projection=projections[0],new_projection=projections[1]))
            failures.append(index)
            break
        if index%1000==0:
            print('gateway comparisons',index,'/',len(scenarios),flush=True)
    save('core-cases.json',rows)
    save('core-C-cases.json',c_cases)
    save('core-check.json',dict(status='PASS' if not failures else 'FAIL',cases=len(rows),requested=len(scenarios),
        failures=failures,intended_change_cases=len(c_cases),edges={g:sorted(e) for g,e in seen.items()},
        artifacts={r.g:dict(dat_sha256=sha(r.original),elf_sha256=sha(r.e.raw)) for r in p.rs},
        comparison='Return, r8-r15/SP/LR and complete per-byte public write histories, including the forwarded request.',
        C_projection='The existing object mapping projects n fields at offset 3712 and above. The retained helper also removes the new g.view_lost history; this script restores that history and compares it because generation 119 already writes the field.',
        contracts='The final rv_call boundary returns the specified reply; view ownership and visible rows use the specified valid values.'))
    record_inputs('core-inputs.json')
    assert not failures,failures
    print('PASS directed gateway comparisons',len(rows),flush=True)


if __name__=='__main__':
    main()
