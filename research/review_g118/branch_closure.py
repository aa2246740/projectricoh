"""Explain every unobserved B-body outcome; keep intentional C domains explicit."""
from pathlib import Path
import ast
import json
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from common import ROOT, OUT, save
import codegen as c

COND={'bc','bnc','beq','bne','beqz','bnez','bgtz','blez','bltz','bgez'}

def prior_rules():
    source=ROOT/'research/review_g117_codegen_r2/branches.py'
    tree=ast.parse(source.read_text())
    return next(ast.literal_eval(x.value) for x in tree.body if isinstance(x,ast.Assign)
                and any(isinstance(n,ast.Name) and n.id=='INIT_RULES' for n in x.targets))

def main():
    assert json.loads((OUT/'data-equality.json').read_text())['equal']
    init=prior_rules()
    a=[[x for x in c.atoms(g,'ig_init')[0] if x['asm'].split()[0] in COND] for g in (117,118)]
    assert len(a[0])==len(a[1])==61
    assert all(x['asm'].split()[0]==y['asm'].split()[0] for x,y in zip(*a))
    init_map={y['pc']:x['pc'] for x,y in zip(*a)}
    result={}
    for name in ('ig_init','list_bind','panel_render','ig_menu','ig_event','ig_apply'):
        d=json.loads((OUT/(name+'-results.json')).read_text())
        targeted=OUT/(name+'-targeted.json')
        extra=json.loads(targeted.read_text()) if targeted.exists() else {}
        if name=='ig_init':
            guard=json.loads((OUT/'ig_init-guard-results.json').read_text())
            extra=dict(status=guard['status'],cases=guard['cases'],edges={g:[[int(pc,16),t] for pc,t in es] for g,es in guard['coverage'].items()})
        assert not extra or extra['status']=='PASS'
        coverage={};unexplained=[]
        for generation,cov in d['coverage'].items():
            g=int(generation);edges={tuple(x) for x in extra.get('edges',{}).get(generation,[])}
            missing=[x for x in cov['uncovered'] if (int(x['pc'],16),x['taken']) not in edges]
            entries=[]
            for x in missing:
                pc=int(x['pc'],16);kind='invariant';why=None
                if name=='ig_init':
                    why=init.get(pc if g==117 else init_map[pc])
                    if why:why+='; gen117 engine identity and complete data equality rechecked for this frozen candidate'
                elif name=='panel_render' and pc in (0x4014,0x4068):
                    why='rows() clears all nine text bytes, writes seven visible characters or SaveFail plus NUL; text[8] is zero at this length-8 loop boundary'
                elif name=='ig_menu':
                    table={
                        117:{0x7c88:'install is compiled to RV_UNAVAILABLE=2, never RV_STALE=-5',
                             0x7c90:'install is compiled to RV_UNAVAILABLE=2, never RV_UNCERTAIN=-8',
                             0x7e84:'the first visible-row test succeeded; immutable record data and fresh success preserve the same row count',
                             0x7ed4:'parameter IDs 1..6 occur at offsets 0..5 in the frozen eight-ID table; lookup cannot exhaust all eight entries',
                             0x7ee0:'g.ready was true at the dominating preload check; no engine reentry mutates it before metadata copy',
                             0x7f00:'slot is guarded by visible_rows<=16 before eng_metadata; slot 17 cannot enter the copy',
                             0x7f14:'all 48 frozen records have occupied=1',
                             0x7f98:'all 48 frozen records have occupied=1'},
                        118:{0x8094:'install is compiled to RV_UNAVAILABLE=2, never RV_STALE=-5',
                             0x809c:'install is compiled to RV_UNAVAILABLE=2, never RV_UNCERTAIN=-8',
                             0x82e4:'the first visible-row test succeeded; immutable record data and fresh success preserve the same row count',
                             0x8338:'parameter IDs 1..6 occur at offsets 0..5 in the frozen eight-ID table; lookup cannot exhaust all eight entries',
                             0x8344:'g.ready was true at the dominating preload check; no engine reentry mutates it before metadata copy',
                             0x8364:'slot is guarded by visible_rows<=16 before eng_metadata; slot 17 cannot enter the copy',
                             0x8378:'all 48 frozen records have occupied=1',
                             0x83fc:'all 48 frozen records have occupied=1'}}
                    why=table[g].get(pc)
                    if g==118 and pc in (0x8294,0x829c):
                        kind='C';why='new H01 acceptance of previewing+committed live state; deliberately outside common-body differential, executed by the native half-shutter/reopen matrix'
                elif name=='ig_event':
                    if g==117 and pc in (0x8138,0x8148,0x8154,0x8170,0x8180,0x81c4,0x8284,0x8294,0x82a0):
                        kind='C';why='old raw/caller/save-versus-cancel predicates removed deliberately; B retains the exact old valid OK tuple 0x23/0x202C2D84, C native cases exercise all new owned exits'
                    if g==118 and pc in (0x8720,0x8728):
                        kind='C';why='new verified-live acceptance versus saved fallback split; B forces eng_current=STALE for the common saved path, native exits/fallback probes test the new path'
                elif name=='ig_apply':
                    if (g==117 and (pc==0x805c or 0x8080<=pc<=0x80d0)) or (g==118 and (pc==0x84d0 or 0x84f4<=pc<=0x8590)):
                        kind='C';why='entire old cursor-only recipe branch replaced by deliberate H08 preview/redraw/latest-row-drain code; retained ingress/init/Fn2 envelope is the >=10k B domain, full native matrix covers C'
                entry=dict(pc=hex(pc),taken=x['taken'],classification=kind,reason=why)
                entries.append(entry)
                if why is None:unexplained.append(dict(generation=g,**entry))
            coverage[generation]=dict(raw_random_boundary=cov['outcomes'],with_directed=cov['possible']-len(missing),
                possible=cov['possible'],unobserved=entries)
        result[name]=dict(status='ACCOUNTED' if not unexplained else 'OPEN',random=d['random'],boundary=d['boundary'],
            extra_directed=len(extra.get('cases',[])),coverage=coverage,unexplained=unexplained,
            domain='Frozen gen117/gen118 image plus native/resident contracts; direct function fixtures model listed callee boundaries. C is intentional change, not product acceptance.')
        assert not unexplained,(name,unexplained)
        print(name,'ACCOUNTED',[(g,x['with_directed'],x['possible']) for g,x in coverage.items()],flush=True)
    save('branch-closure.json',result)

if __name__=='__main__':main()
