"""Compare actual compiler frame records without treating them as task-stack bounds."""
from pathlib import Path
import hashlib
import json
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
rows=[];inputs={}
for generation,tree in ((121,'engine_v43_fix'),(124,'engine_v46_ui'),(126,'engine_v47_fix')):
    frames=[]
    for path in (ROOT/'firmware'/tree/'candidate/local/product-r13/m32r-lto').glob('engine.elf.ltrans*.su'):
        inputs[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
        for line in path.read_text().splitlines():
            fields=line.split('\t')
            if len(fields)==3:
                frames.append(dict(function=fields[0],bytes=int(fields[1]),kind=fields[2]))
    assert frames and all(x['kind']=='static' for x in frames)
    init=[x for x in frames if x['function'].endswith(':ig_init')];assert len(init)==1
    rows.append(dict(generation=generation,maximum_single_frame=max(x['bytes'] for x in frames),ig_init_single_frame=init[0]['bytes'],frames=frames))
initial=json.loads((OUT/'inputs-before.json').read_text())
assert all(k not in initial or initial[k]==v for k,v in inputs.items())
(OUT/'inputs-additional.json').write_text(json.dumps(inputs,indent=2)+'\n')
(OUT/'evidence/stack-compare.json').write_text(json.dumps(dict(rows=rows,
    scope='Static single frames only. Inlining differs. These maxima cannot establish whole-call-chain or RTOS stack regression.'),indent=2)+'\n')
print([(x['generation'],x['maximum_single_frame'],x['ig_init_single_frame']) for x in rows])
