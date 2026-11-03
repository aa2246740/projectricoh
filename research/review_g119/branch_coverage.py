"""Combine observed B branch edges and directed cases for the exact final images."""
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import codegen as c
from common import OUT,save

COND={'bc','bnc','beq','bne','beqz','bnez','bgtz','blez','bltz','bgez'}

def main():
    identity=json.loads((OUT/'identity.json').read_text());rows={}
    for p in sorted(OUT.glob('*-results.json')):
        data=json.loads(p.read_text())
        if 'artifacts' not in data:continue
        for gen in ('118','119'):
            assert data['artifacts'][gen]['dat']==identity[gen]['dat'],(p.name,'stale DAT')
            assert data['artifacts'][gen]['elf']==identity[gen]['elf'],(p.name,'stale ELF')
        assert data['random']>=10000 and data['boundary']>=64 and not data['failures'],p.name
        name=data['function'];func='panel_render.constprop.0' if name=='panel_render' else name;pair={}
        for gen in (118,119):
            f='es_session.constprop.0' if name=='es_session' and gen==118 else func
            atoms=c.atoms(gen,f)[0];pcs={a['pc'] for a in atoms if a['asm'].split(' ')[0] in COND}
            original=data['coverage'][str(gen)];missing=original['uncovered']
            covered={(pc,b) for pc in pcs for b in (False,True) if dict(pc=hex(pc),taken=b) not in missing}
            targeted=OUT/(name+'-targeted.json')
            if targeted.exists():
                extra=json.loads(targeted.read_text())
                for case in extra['cases']:
                    for pc,b in case.get('edges',{}).get(str(gen),[]):
                        if pc in pcs:covered.add((pc,b))
                for pc,b in extra.get('edges',{}).get(str(gen),[]):
                    if pc in pcs:covered.add((pc,b))
            pair[gen]=dict(raw=original,after_directed_outcomes=len(covered),possible=2*len(pcs),
                uncovered=[dict(pc=hex(pc),taken=b) for pc in sorted(pcs) for b in (False,True) if (pc,b) not in covered])
        rows[name]=pair
    assert len(rows)==19,len(rows)
    save('branch-coverage.json',dict(artifacts=identity,functions=rows,
        scope='Observed branch outcomes only. No unexecuted branch is counted as executed; intentional C paths and bounded common-callee domains are described in codegen-closure.json.'))
    print('PASS final-image branch records',len(rows),'functions',flush=True)
    for name,pair in sorted(rows.items()):print(name,[(g,x['after_directed_outcomes'],x['possible']) for g,x in pair.items()],flush=True)

if __name__=='__main__':main()
