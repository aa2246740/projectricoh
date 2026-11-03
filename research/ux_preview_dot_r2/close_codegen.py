"""Account for every typed symbol, with final-image A/B/C evidence and dependencies."""
from pathlib import Path
import collections
import difflib
import json
import re
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import codegen as c
from common import OUT,ROOT,save,sha

B={
 'es_range.constprop.0','identity.constprop.0','same.constprop.0','ui_prepare.constprop.0','ingress',
 'core_call','finish','ui_finish','write_word','preview_cached','ig_panel_open','ig_panel_event','rv_call',
 'list_bind','panel_render.constprop.0','ig_menu','ig_event','ig_apply',
}
PURE_B={'es_range.constprop.0','identity.constprop.0','same.constprop.0','ui_prepare.constprop.0','ingress'}
C={
 'core_call':'RPC return ownership checks and pre-W supersession are intentional. Existing request/reply, scratch copy, RPC token and receipt body are B with watch_view=0.',
 'finish':'Uncertain failure latches application off while retaining the checked menu entry; watch flag cleanup is new. Other status mapping, workspace cleanup and stop behavior are B.',
 'ui_finish':'Same uncertain-failure latch and watch cleanup; retained UI status/close/stop behavior is B.',
 'write_word':'New no-first-W guard uses the tail-padding view_lost flag. Existing sticky uncertainty, W result validation and saturated witness counter are B with the guard clear.',
 'preview_cached':'New cancellation without compensation before any W after lost/superseded view. Existing slot/metadata/preview/recovery body is B with the cancellation flag clear.',
 'ig_panel_open':'New failed latch consumes Fn2. Existing numeric-page construction and preview paths are B in the common unfailed domain, and native Fn2 paths execute on all units.',
 'ig_panel_event':'New failed latch consumes numeric events. Existing ingress/init/a4_move/ui_finish envelope is B.',
 'rv_call':'Only UI_LIST op3 adds the ownership predicate under the existing IRQ critical section. B executes the dispatcher with that predicate true; native foreign cases exercise rejection. Session helper specialization changes have their own B.',
 'list_bind':'New one-row fault list, guarded op3 and guarded cache call. B executes the original recipe-list publication with failed=0 and declared cursor boundary.',
 'panel_render.constprop.0':'Only the cursor-cache call gains the published list and construction phase arguments. Full retained render body is B at the same cursor-cache boundary.',
 'ig_menu':'New failed latch publishes the error row; original H01 body is B with failed=0. Actual error publication and reopening are native tested.',
 'ig_event':'New failed latch blocks application while allowing close. Common ordinary/Fn2/verified-preview event behavior is B, with additional verified-current cases.',
 'ig_apply':'Ownership, pre-W coalescing, loss handoff and error latch are intentional H08 changes. Existing ingress/init/Fn2 envelope is B; full preview/drain behavior executes through native navigation.',
 'cursor_cache':'The original fixed-byte write now runs only under IRQ and a complete view-ownership predicate. Its address and state-pointer check remain explicit in source and native write traces.',
 'rv_view_owned':'New owner predicate reads native Image activity, list pointer/count, overlay, view stack, view epoch, resident session, lease and publication relationship.',
 'view_owned':'New adapter binding to its own currently published recipe or numeric list.',
 'release_view':'Clear the per-call cancellation flag, close only engine-private list state, and consume the old H08 continuation. Returning PASS would make the unchanged resident restore/hide the foreign UI.',
}

def main():
    inv=json.loads((OUT/'codegen-inventory.json').read_text());final=json.loads((OUT/'identity.json').read_text())
    evidence={};obligations=[];nodes={};lines=['function\tstatus\t118_bytes\t119_bytes\tclass\tevidence']
    for name in sorted(B|{'es_session'}):
        key='panel_render' if name=='panel_render.constprop.0' else name
        p=OUT/(key+'-results.json');data=json.loads(p.read_text())
        assert data['random']>=10000 and data['boundary']>=64 and not data['failures'],(name,'B incomplete')
        for gen in ('118','119'):
            assert data['artifacts'][gen]['dat']==final[gen]['dat'] and data['artifacts'][gen]['elf']==final[gen]['elf'],(name,'stale B artifact')
        evidence[name]=dict(file=p.name,random=data['random'],boundary=data['boundary'],coverage=data['coverage'])
    objects=json.loads((OUT/'object-map.json').read_text())
    assert all(x['bytes_equal'] for x in objects['pairs'])
    indirect={'core_call':['rv_call'],'pn_call':['rv_call'],'pn_address':['address'],
              'svc.constprop.0':['core_call'],'panel_render.constprop.0':['pn_native_from_seed'],
              'disarm':['grain_snapshot'],'apply_impl':['grain_snapshot']}
    for row in inv:
        name=row['name'];ev=[];reason='';category=None
        if row.get('local_A'):
            category='identity+A' if row['status']=='identical' else 'A';ev=['codegen/'+name+'.json']
            reason='All non-address instruction bytes, control-flow destinations, packets, stack and complete referenced data objects translated.'
        elif name in B:
            category='B' if name in PURE_B else 'C+B';key='panel_render' if name=='panel_render.constprop.0' else name
            ev=[key+'-results.json','source.patch'];reason=C.get(name,'Same source; root-parameter specialization changes are checked on the real retained body.')
            if (OUT/(key+'-targeted.json')).exists():ev.append(key+'-targeted.json')
        elif name=='es_session':
            category='B';ev=['es_session-results.json','es_session-targeted.json'];reason='Same resident-session validation body, now taking the known resident root explicitly. B pairs old implicit-root specialization with new explicit-root body.'
        elif name=='es_session.constprop.0' and row['status']=='removed':
            category='B paired removal';ev=['es_session-results.json','es_session-targeted.json'];reason='Old specialization paired with the added generic es_session body.'
        elif name in C:
            category='C';ev=['source.patch','native/adversarial-foreign-50mm-at1-reopen-fn2.json','native/persistent-50mm.json'];reason=C[name]
        assert category,(name,'unclassified')
        deps=set()
        if row['status']!='removed':
            aa=c.atoms(119,name)[0];_,branches,_=c.symbolic(119,name,aa)
            deps={b['logical'] for b in branches if not b['logical'].startswith('self@')}
            for address in c.data_targets(119,name,aa).values():
                obj=c.object_info(119,address)
                if obj and obj['type']==2 and obj['offset']==0:deps.add(c.canon(119,obj['name']))
            deps.update(indirect.get(name,[]));nodes[name]=sorted(deps)
        result=dict(function=name,status=row['status'],category=category,evidence=ev,reason=reason,dependencies=sorted(deps),
                    old_bytes=row['old_size'],new_bytes=row['new_size'])
        obligations.append(result);lines.append('\t'.join(map(str,(name,row['status'],row['old_size'],row['new_size'],category,','.join(ev)))))
    leaves=json.loads((OUT/'assembly-leaves.json').read_text())
    for row in leaves:nodes[row['name']]=[]
    unresolved=[dict(function=n,target=x) for n,dd in nodes.items() for x in dd if x not in nodes]
    assert not unresolved,unresolved
    # The local evidence for each dependency is explicit above. Return-only
    # function-address edges are retained rather than silently discarded.
    save('codegen-dependencies.json',nodes)
    save('codegen-closure.json',dict(status='ACCOUNTED_A_B_C',obligations=obligations,
        counts=dict(collections.Counter(x['category'] for x in obligations)),
        changed_shared_categories=dict(collections.Counter(x['category'] for x in obligations if x['status']=='changed')),
        B=evidence,B_pairs=sum(x['random']+x['boundary'] for x in evidence.values()),
        unresolved=unresolved,dependency_nodes=len(nodes),
        scope='B is bounded final-machine differential evidence at declared common callee boundaries. It is not an exhaustive proof over arbitrary corrupt private data or hardware scheduling. C identifies intentional changes, not a safety approval.',
        branch_coverage='Raw B branch coverage and directed edge records are preserved. Native tests cover the new C owner-loss, coalescing, error-notice, preview and exit states.'))
    (OUT/'codegen-closure.tsv').write_text('\n'.join(lines)+'\n')
    print('PASS A/B/C inventory',len(obligations),'typed symbols; changed',sum(x['status']=='changed' for x in obligations),'B pairs',sum(x['random']+x['boundary'] for x in evidence.values()),'unresolved',len(unresolved),flush=True)

if __name__=='__main__':main()
