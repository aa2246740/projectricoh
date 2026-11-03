"""Directed final-machine cases for the changed ig_init byte/word guard."""
from pathlib import Path
import itertools
import random
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from common import save
import differential as d

p=d.Pair();d.setup_init(p);rng=random.Random(0x118b00);cases=[];seen={117:set(),118:set()}
for i,(bound,busy,committed,uncertain) in enumerate(itertools.product((0,1,255),repeat=4)):
    args,case=d.prepare_init(p,rng,0,True)
    p.mode.update(ingress=1,gate_status=0,snapshot=1,native_variant=0)
    for r in p.rs:
        r.write(r.n+2072,bytes([0,1]))
        at=d.cg.g_offset if r.g==118 else lambda x:x
        for offset,value in ((2465,bound),(2466,busy),(2467,committed),(2468,uncertain)):
            r.write(p.g[r.g]+at(offset),bytes([value]))
    results,ok,old,new=p.run(('ig_init','ig_init'),args,0x118a000+i)
    for r,x in zip(p.rs,results):seen[r.g].update(map(tuple,x['edges']))
    row=dict(index=i,bound=bound,busy=busy,committed=committed,uncertain=uncertain,ok=ok,
             result=[x['result'] for x in results],ABI=[x['abi_ok'] for x in results])
    cases.append(row)
    if not ok:
        save('ig_init-guard-failure.json',dict(row=row,old=results[0],new=results[1],old_projection=old,new_projection=new))
        raise AssertionError(row)
save('ig_init-guard-results.json',dict(status='PASS',cases=cases,coverage={g:[(hex(pc),t) for pc,t in sorted(x)] for g,x in seen.items()},
    identity='((B<<16)|(C<<8)|U)!=0 iff (B|C|U)!=0 for bytes B,C,U; bound is masked out by 0xFFFFFF',
    states='Explicit direct-function fixture, not a native menu-state replay'))
print('PASS 81 directed byte-guard combinations, including 0xFF and ignored bound byte',flush=True)
