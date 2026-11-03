"""Union fresh B and directed edges. Never infer execution from classification."""
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import codegen as c
from common import OUT,save

COND={'bc','bnc','beq','bne','beqz','bnez','bgtz','blez','bltz','bgez'}
identity=json.loads((OUT/'identity.json').read_text())
all_results=sorted(OUT.glob('*-results.json'))
functions={}
for p in all_results:
    data=json.loads(p.read_text())
    if 'function' not in data or 'coverage' not in data:continue
    name=data['function'];func='panel_render.constprop.0' if name=='panel_render' else name
    assert not data['failures'] and data['random']>=10000 and data['boundary']>=64
    extra=[]
    for q in (OUT/(name+'-targeted.json'),OUT/(name+'-review-targeted.json'),OUT/(name+'-current-targeted.json')):
        if q.exists():extra.append((q.name,json.loads(q.read_text())))
    if name=='rv_call' and (OUT/'service-targets.json').exists():
        extra.append(('service-targets.json',json.loads((OUT/'service-targets.json').read_text())))
    if name=='rv_call' and (OUT/'service-targets-early.json').exists():
        extra.append(('service-targets-early.json',json.loads((OUT/'service-targets-early.json').read_text())))
    if name=='rv_call' and (OUT/'service-more.json').exists():
        extra.append(('service-more.json',json.loads((OUT/'service-more.json').read_text())))
    pair={}
    for gen in (118,119):
        assert data['artifacts'][str(gen)]['dat']==identity[str(gen)]['dat']
        actual='es_session.constprop.0' if name=='es_session' and gen==118 else func
        atoms=c.atoms(gen,actual)[0];pcs={x['pc'] for x in atoms if x['asm'].split(' ')[0] in COND}
        missing={(int(x['pc'],16),x['taken']) for x in data['coverage'][str(gen)]['uncovered']}
        observed={(pc,b) for pc in pcs for b in (False,True)}-missing
        for _,record in extra:
            for case in record.get('cases',[]):
                observed.update((pc,b) for pc,b in case.get('edges',{}).get(str(gen),[]) if pc in pcs)
            observed.update((pc,b) for pc,b in record.get('edges',{}).get(str(gen),[]) if pc in pcs)
        contexts=[]
        for pc in sorted(pcs):
            for b in (False,True):
                if (pc,b) in observed:continue
                i=next(i for i,x in enumerate(atoms) if x['pc']==pc)
                contexts.append(dict(pc=hex(pc),taken=b,context=[dict(pc=hex(x['pc']),asm=x['asm']) for x in atoms[max(0,i-4):i+3]]))
        pair[gen]=dict(observed=len(observed),possible=2*len(pcs),uncovered=contexts)
    functions[name]=dict(evidence=[p.name]+[q for q,_ in extra],pair=pair)
save('coverage-union.json',dict(functions=functions,count=len(functions),artifacts=identity))
print('Fresh branch union',len(functions),'functions')
for n,x in functions.items():print(n,[(g,v['observed'],v['possible'],len(v['uncovered'])) for g,v in x['pair'].items()])
