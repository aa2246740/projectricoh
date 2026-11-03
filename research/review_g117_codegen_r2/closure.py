"""Check switch destinations, unchanged leaves, and SCC dependency closure."""
from pathlib import Path
import bisect, collections, json, re, struct, sys
OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(OUT))
import translation as t


def save(n,x):t.save(n,x)


def main():
    rows=json.loads((OUT/'translation-local.json').read_text())
    names={r['name']:r for r in rows}
    lookup={t.previous.fname(n):n for n in names}
    for n in names:lookup.setdefault(t.canonical(n),n)
    leaves=[]
    for row in rows:
        if row['category']!='identity':continue
        old=next(x['old_name'] for x in t.INV if x['name']==row['name'])
        aa=t.atoms(116,old);bb=t.atoms(117,row['name'])
        a,ab=t.symbolic(116,old,aa);b,bc=t.symbolic(117,row['name'],bb)
        good=a==b and all(x['logical'].startswith('self@') for x in bc) and not any(x['relocation'] for x in aa+bb)
        leaves.append(dict(name=row['name'],kind='typed-identical-leaf',ok=good,non_nop_atoms=len(a)))
        assert good,row
    untyped=json.loads((t.R1/'untyped-assembly-functions.json').read_text())
    for r in untyped:
        a=t.ES[116].bytes(r['old_address'],r['size116'])
        b=t.ES[117].bytes(r['new_address'],r['size117'])
        good=a==b
        leaves.append(dict(name=r['name'],kind='native-or-IRQ-byte-identical-leaf',ok=good,hex=a.hex()))
        assert good,r
    switches=[]
    for i in range(2):
        pair=[]
        for g in t.G:
            base,z=t.table_ranges(g,'rv_call')[i]
            aa=t.atoms(g,'rv_call');pcs=[x['pc'] for x in aa]
            rel=struct.unpack('>'+str(z//4)+'i',t.ES[g].bytes(base,z))
            targets=[base+x for x in rel]
            assert all(pc in pcs for pc in targets)
            pair.append(dict(generation=g,base=base,bytes=z,relative_offsets=rel,
                             targets=targets,atoms=[bisect.bisect_left(pcs,pc) for pc in targets]))
        assert pair[0]['relative_offsets']==pair[1]['relative_offsets']
        assert pair[0]['atoms']==pair[1]['atoms']
        switches.append(dict(index=i,old=pair[0],new=pair[1],ok=True))
    indirect={
        'core_call': ['rv_call'], 'disarm':['grain_snapshot'],
        'pn_address':['address'], 'pn_call':['rv_call'],
        'pn_ui_render.constprop.0':['pn_native_from_seed'],
        'svc.constprop.0':['core_call'], 'eng_apply':['grain_snapshot']}
    graph={};unresolved=[]
    native={x['name'] for x in leaves}
    for row in rows:
        n=row['name'];deps=set(row.get('dependencies',[]))|set(indirect.get(n,[]))
        resolved=set()
        for d in deps:
            if d in names:resolved.add(d)
            elif d in lookup:resolved.add(lookup[d])
            elif d in native:resolved.add(d)
            else:unresolved.append(dict(function=n,target=d))
        graph[n]=sorted(resolved)
    for n in native:graph.setdefault(n,[])
    # Tarjan's components give simultaneous induction for recursive callbacks.
    index={};low={};stack=[];active=set();components=[]
    def visit(n):
        index[n]=low[n]=len(index);stack.append(n);active.add(n)
        for d in graph[n]:
            if d not in index:visit(d);low[n]=min(low[n],low[d])
            elif d in active:low[n]=min(low[n],index[d])
        if low[n]==index[n]:
            c=[]
            while True:
                d=stack.pop();active.remove(d);c.append(d)
                if d==n:break
            components.append(sorted(c))
    for n in graph:
        if n not in index:visit(n)
    obligations=[]
    for r in rows:
        n=r['name'];category=r['category']
        if n=='path':category='B-r2'
        if n=='ig_init':category='C+B'
        ok=r['local_ok'] is True if category=='A' else True
        proof=[]
        if category in ('B-r2','C+B'):
            file=OUT/(n+'-results.json')
            d=json.loads(file.read_text()) if file.exists() else {}
            ok=d.get('random',0)>=10000 and not d.get('failures',[True])
            proof=[n+'-results.json']
            # Coverage closure is a separate explicit obligation.
            coverage=OUT/'branch-closure.json'
            if category=='C+B' and n in ('ig_init','ig_menu','ig_event'):
                cc=json.loads(coverage.read_text()) if coverage.exists() else {}
                ok=ok and cc.get(n,{}).get('closed',False)
                proof.append('branch-closure.json')
        obligations.append(dict(function=n,category=category,local_closed=ok,evidence=proof,dependencies=graph[n]))
    good={r['function'] for r in obligations if r['local_closed']}
    good.update(x['name'] for x in leaves if x['ok'])
    component_rows=[];closed=set()
    for c in components:
        external={x for n in c for x in graph[n] if x not in c}
        ok=set(c)<=good and external<=closed
        if ok:closed.update(c)
        component_rows.append(dict(functions=c,dependencies=sorted(external),closed=ok))
    for r in obligations:r['closed']=r['local_closed'] and r['function'] in closed
    save('identity-leaves.json',leaves);save('switch-tables.json',switches)
    save('dependency-graph.json',dict(graph=graph,indirect=indirect,unresolved=unresolved,components=component_rows))
    save('function-closure.json',obligations)
    print('unresolved targets',unresolved)
    print('categories',dict(collections.Counter(r['category'] for r in obligations if r['category']!='identity')))
    print('open local',[(r['function'],r['category']) for r in obligations if not r['local_closed']])
    print('open including dependencies',[r['function'] for r in obligations if not r['closed']])
    print('SCCs',len(components),'nontrivial',[c for c in components if len(c)>1])


if __name__=='__main__':main()
