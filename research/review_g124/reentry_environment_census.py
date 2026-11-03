"""Separate actor-local interpreter gaps from firmware assertion failures."""
from pathlib import Path
from collections import Counter
import json
OUT=Path(__file__).resolve().parent
counts=Counter();failures=[]
for folder in sorted((OUT/'local').glob('reentry-all-keys*')):
    if not folder.is_dir():continue
    for p in sorted(folder.glob('*.json')):
        r=json.loads(p.read_text());actor=r.get('key','?');counts[(folder.name,actor,r.get('status','?'))]+=1
        if r.get('status')=='FAIL':
            failures.append(dict(file=str(p.relative_to(OUT)),key=actor,interpreter_trap='unsupported exception instruction trap' in r.get('error',''),
                                 error_tail=r.get('error','')[-180:]))
value=dict(premise='The pre-existing non-IRQ shooting fixture also models the IRQ-enabled RTOS calls.',
    actors=[dict(folder=k[0],key=k[1],status=k[2],count=v) for k,v in sorted(counts.items())],failures=failures,
    result='The failed actor is HALF. Services 400/380 query normal task context and task ID; native 0x2005e034 submits an RTOS message. Model these OS boundaries, retain native handlers and require H07 evidence.')
(OUT/'evidence/reentry-environment-census.json').write_text(json.dumps(value,indent=2)+'\n')
print(json.dumps(value['actors']));print('Failure keys:',sorted({r['key'] for r in failures}))
