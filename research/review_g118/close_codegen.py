"""Close every changed symbol by A, >=10k B, or an explicit source C change."""
from pathlib import Path
import collections
import json
import re
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from common import ROOT, OUT, save
import codegen as c

def selective(n,drop=(),calls=None):
    calls=calls or {};aa=c.atoms(117,n)[0];bb=c.atoms(118,n)[0]
    na,ba,_=c.symbolic(117,n,aa);nb,br,_=c.symbolic(118,n,bb)
    kept=[j for j in range(len(bb)) if j not in drop];assert len(kept)==len(aa)
    reverse={j:i for i,j in enumerate(kept)};sa=c.pointer_states(117,n,aa,ba);sb=c.pointer_states(118,n,bb,br)
    dataa=c.data_targets(117,n,aa);datab=c.data_targets(118,n,bb)
    rows=[];target_proofs=[];changes=[]
    for i,j in enumerate(kept):
        old,new=na[i],nb[j]
        new=re.sub(r'self@(\d+)',lambda m:'self@'+str(reverse[int(m[1])]),new)
        permitted=None
        if (old,new) in calls:
            permitted=dict(kind='intentional-callee-substitution',old=old,new=new);new=old
        if old!=new:
            proof=c.layout_change(old,new,sa.get(i,{}),sb.get(j,{}))
            assert proof,(n,i,j,old,new)
            permitted=proof;new=old
        assert old==new
        ra,rb=bytes.fromhex(aa[i]['raw']),bytes.fromhex(bb[j]['raw'])
        if len(ra)==2:ra=(int.from_bytes(ra,'big')&0x7fff).to_bytes(2,'big')
        if len(rb)==2:rb=(int.from_bytes(rb,'big')&0x7fff).to_bytes(2,'big')
        rel=aa[i]['relocation']
        if rel and rel[0] in {'R_M32R_GOTOFF_HI_SLO','R_M32R_GOTOFF_LO','R_M32R_GOTPC_HI_SLO','R_M32R_GOTPC_LO'}:
            assert bb[j]['relocation'][0]==rel[0];ra,rb=ra[:2],rb[:2]
        elif aa[i]['asm'].split(' ')[0] in c.BRANCH:ra=rb=b''
        elif permitted:ra,rb=ra[:2],rb[:2]
        assert ra==rb,(n,i,j,aa[i],bb[j])
        if i in dataa:
            assert j in datab
            p=c.check_data(dataa[i],datab[j]);assert p['equal'],(n,i,j,p)
            target_proofs.append(dict(old_atom=i,new_atom=j,**p))
        if permitted:changes.append(dict(old_atom=i,new_atom=j,**permitted))
        rows.append([i,j])
    if n=='end':
        assert [nb[j] for j in drop]==['addi r0,#8','beqz r0,self@28']
        assert nb[28]=='ldi r0,#0' and nb[27]=='stb r8,@(2524,r4)'
    p=dict(function=n,status='C+A',old_atoms=len(aa),new_atoms=len(bb),mapping=rows,
           explicit_C_atoms=[bb[j] for j in drop],declared_C_calls=list(calls),changes=changes,
           all_remaining_non_address_bytes_equal=True,branch_destinations_mapped=True,data_targets=target_proofs)
    save('proof-C/'+n+'.json',p);return p

def main():
    inventory=json.loads((OUT/'codegen-inventory.json').read_text())
    selective('a4_move',calls={('bl pn_ui_render.constprop.0','bl panel_render.constprop.0'):True})
    selective('ig_panel_open',calls={('bl pn_ui_render.constprop.0','bl panel_render.constprop.0'):True,
                                    ('bl select_cached','bl preview_cached'):True})
    selective('end',drop=(22,23))
    B={}
    for n in ('ig_init','list_bind','panel_render','ig_menu','ig_event','ig_apply'):
        d=json.loads((OUT/(n+'-results.json')).read_text())
        assert d['random']>=10000 and d['boundary']>=64 and not d['failures'],(n,d)
        B[n]=dict(random=d['random'],boundary=d['boundary'],coverage=d['coverage'],evidence=n+'-results.json')
    assert json.loads((OUT/'ig_init-guard-results.json').read_text())['status']=='PASS'
    branches=json.loads((OUT/'branch-closure.json').read_text())
    assert set(branches)==set(B) and all(x['status']=='ACCOUNTED' and not x['unexplained'] for x in branches.values())
    C={
        'a4_move':('C+A','Only the render callee changes; every remaining instruction/data target is translated exactly.'),
        'end':('C+A','RV_UNCERTAIN cleanup retains bound; remaining instructions and branch targets match under g field layout.'),
        'ig_panel_open':('C+A','Select becomes preview and render gains cache sync; every other instruction is translated exactly.'),
        'eng_apply':('C','Full intentional refactor into apply_impl, verified-live fast acceptance, confirmed snapshot, finite recovery.'),
        'ig_apply':('C+B','H08 redraw + preview + latest-row drain is C; >=10k differential of the retained ingress/init/Fn2 routing envelope.'),
        'ig_event':('C+B','Owned H07 acceptance and verified-live fast path are C; >=10k differential of the old valid-confirmation domain, including Fn2 RAM commit.'),
        'ig_menu':('C+B','H01 clears numeric panel state and accepts pending live preview; >=10k projected differential for other paths.'),
        'list_bind':('C+B','Operation argument 1/3 and successful cursor sync are intentional; >=10k old/op1 common-body differential.'),
        'cursor_cache':('C','New fixed-byte cache synchronization guarded by native state pointer; direct guard and native paths checked.'),
        'apply_impl':('C','New helper owns deliberate recovery/confirm distinction, forced nine-row verification and settings/preview ordering.'),
        'recover_confirmed':('C','New finite confirmed -> stock04 fallback sequence; persistent transport failure is not hidden by closure.'),
        'preview_cached':('C','New saved-RAM preview entry; output/data correctness checked by native matrix.'),
        'panel_render.constprop.0':('C+B','Old pn_ui_render body plus successful cursor sync; >=10k differential after that explicit C callback.'),
        'pn_ui_render.constprop.0':('C+B','Old name subsumed by panel_render.constprop.0, whose retained body has >=10k differential.'),
        'select_cached':('C','Replaced intentionally by preview_cached and accept_preview, the latter inlined into ig_event.'),
    }
    nodes={};obligations=[]
    indirect={'core_call':['rv_call'],'disarm':['grain_snapshot'],'pn_address':['address'],'pn_call':['rv_call'],
              'svc.constprop.0':['core_call'],'apply_impl':['grain_snapshot'],'panel_render.constprop.0':['pn_native_from_seed']}
    for row in inventory:
        n=row['name'];category=None;evidence=[]
        if row.get('local_A'):
            category='identity+A' if row['status']=='identical' else 'A';evidence=['codegen/'+n+'.json']
        elif n=='ig_init':category='B';evidence=['ig_init-results.json','ig_init-guard-results.json']
        elif n in C:
            category=C[n][0]
            if category=='C+A':evidence=['proof-C/'+n+'.json']
            elif n in ('list_bind','ig_menu','ig_apply','ig_event'):evidence=[n+'-results.json','source.patch']
            elif 'panel_render' in n or 'pn_ui_render' in n:evidence=['panel_render-results.json','source.patch']
            else:evidence=['source.patch']
        assert category,(n,'unclosed changed symbol')
        bn='panel_render' if n in ('panel_render.constprop.0','pn_ui_render.constprop.0') else n
        if bn in B:
            evidence.append('branch-closure.json')
            if (OUT/(bn+'-targeted.json')).exists():evidence.append(bn+'-targeted.json')
        deps=set()
        if row['status']!='removed':
            aa=c.atoms(118,n)[0];_,branches,_=c.symbolic(118,n,aa)
            deps={x['logical'] for x in branches if not x['logical'].startswith('self@')}
            for address in c.data_targets(118,n,aa).values():
                obj=c.object_info(118,address)
                if obj and obj['type']==2 and obj['offset']==0:deps.add(c.canon(118,obj['name']))
            deps.update(indirect.get(n,[]));nodes[n]=sorted(deps)
        obligations.append(dict(function=n,status=row['status'],old_size=row['old_size'],new_size=row['new_size'],category=category,
            local_closed=True,evidence=evidence,reason=C[n][1] if n in C else 'Complete literal instruction/data translation' if category!='B' else '10k final-body differential plus directed guard cases',dependencies=sorted(deps)))
    leaves=json.loads((OUT/'assembly-leaves.json').read_text())
    for row in leaves:nodes[row['name']]=[]
    unresolved=[dict(function=n,target=d) for n,dd in nodes.items() for d in dd if d not in nodes]
    assert not unresolved,unresolved
    closed=set();remaining=set(nodes)
    while remaining:
        ready={n for n in remaining if set(nodes[n])<=closed}
        assert ready,('unclosed dependency component',remaining)
        remaining-=ready;closed|=ready
    for o in obligations:o['closed_with_dependencies']=o['status']=='removed' or o['function'] in closed
    save('codegen-closure.json',dict(status='ACCOUNTED',symbol_obligations=obligations,
        changed_shared=sum(x['status']=='changed' for x in obligations),
        changed_shared_categories=dict(collections.Counter(x['category'] for x in obligations if x['status']=='changed')),
        all_changed_accounted=True,unresolved=unresolved,dependency_nodes=len(nodes),
        note='C accounts for an intentional change, not a safety approval. Adversarial findings remain blocking.'))
    save('codegen-dependencies.json',nodes)
    lines=['function\tstatus\t117_bytes\t118_bytes\tclass\tclosed\tevidence']
    for o in obligations:lines.append('\t'.join(map(str,(o['function'],o['status'],o['old_size'],o['new_size'],o['category'],o['closed_with_dependencies'],','.join(o['evidence'])))))
    (OUT/'codegen-closure.tsv').write_text('\n'.join(lines)+'\n')
    print('PASS all',len(obligations),'symbol obligations accounted; dependency nodes',len(nodes),'unresolved=0',flush=True)
    print('CHANGED_SHARED',dict(collections.Counter(x['category'] for x in obligations if x['status']=='changed')),flush=True)

if __name__=='__main__':main()
