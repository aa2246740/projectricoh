"""Require every requested native result before collecting the final review."""
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import OUT,save,sha

expected=[]
for unit in ('50mm','28mm','mount'):
    expected += [f'native/{group}-{unit}.json' for group in ('matrix','ah','persistent','exits','latch-paths','confirm-paths')]
    expected += [f'native/concurrent_menu-other_menu-{unit}-at{at}-reopen-fn2.json' for at in (1,6,16,17,140)]
    expected += [f'native/concurrent_menu-{group}-{unit}.json' for group in ('recovery','fallback','nested')]
    expected += [f'native/ui-cutpoint-{point}-{unit}.json' for point in ('redraw','cache')]
    expected += [f'native/entry-switch-{unit}-{entry}-at1.json' for entry in ('fn2','ok','adj')]
    expected += [f'native/failure-boundary-{unit}-at{at}.json' for at in (1,6)]
expected += [f'native/baseline-entry-switch-50mm-{entry}-at1.json' for entry in ('fn2','ok','adj')]
expected += ['native/coalescing-119-50mm-at1.json','native/coalescing-119-50mm-at16.json','native/failure-boundary-50mm-at7.json']
missing=[name for name in expected if not (OUT/name).exists()]
if missing:
    print('PENDING native result records',len(missing),flush=True)
    if '--pending' in sys.argv:
        for name in missing:print(name)
        raise SystemExit(0)
    raise SystemExit('Full native matrix is incomplete.')
records={name:json.loads((OUT/name).read_text()) for name in expected}
mutations=[];rpc_commands=set()
def walk(value,path):
    if isinstance(value,dict):
        if set(value)=={'create','write','rename','delete','write_open'}:
            assert not any(value.values()),(path,value)
            mutations.append(dict(path=path,counts=value))
        if 'cmd' in value and 'result' in value:rpc_commands.add(value['cmd'])
        for k,v in value.items():walk(v,path+'/'+str(k))
    elif isinstance(value,list):
        for i,v in enumerate(value):walk(v,path+'/'+str(i))
for name,row in records.items():walk(row,name)
assert rpc_commands<={21,22,23},rpc_commands
matrix=[];entry_rows=[];early=[];handoffs=[]
for unit in ('50mm','28mm','mount'):
    x=records[f'native/matrix-{unit}.json']
    assert x['status']=='PASS' and x['cold']['state']['cursor']==4 and x['cold']['state']['W']==0
    assert len(x['fast_moves'])==41 and len(x['faults'])==3
    assert x['reboot']['state']['cursor']==4 and x['reboot']['state']['W']==0
    y=records[f'native/ah-{unit}.json'];assert y['status']=='PASS'
    assert all(k in y for k in 'abcdefgh')
    assert y['a']['generation']==119 and y['d']['after']['native_h08']==0 and y['d']['after']['mode']==1
    assert y['c']['apply01']['nine_rows'] and y['c']['apply02']['nine_rows']
    assert y['h']['next_boot']['rows']==7 and y['h']['next_boot_stock04']['slot']==4
    p=records[f'native/persistent-{unit}.json']
    assert p['status']=='PASS_NOTICE_LATCHED_MIXED_RAM' and not p['matching_complete_slots']
    assert p['latched_no_more_rpc'] and p['notice_ascii_calls'] and p['notice_native_glyph_draws']
    assert records[f'native/latch-paths-{unit}.json']['status']=='PASS'
    assert records[f'native/exits-{unit}.json']['status']=='PASS'
    confirms=records[f'native/confirm-paths-{unit}.json'];assert confirms['status']=='PASS' and len(confirms['cases'])==4
    assert all(x['extra_rpc']==0 and x['actual']['slot']==x['target'] for x in confirms['cases'])
    assert confirms['dot_checks']['rpc_observations']>0 and not confirms['dot_checks']['mismatches']
    assert set(confirms['dot_checks']['selected_rows'])==set(range(1,9))
    matrix.append(dict(unit=unit,matrix='PASS',ah='PASS',H08_and_H07='PASS',notice_after_partial_write='PASS',latch_entries='PASS',cold04='PASS'))
    for at in (1,6,16,17,140):
        name=f'native/concurrent_menu-other_menu-{unit}-at{at}-reopen-fn2.json';r=records[name]
        assert r['status']=='PASS' and r['complete_slots']==([4] if at in (1,6) else [5])
        assert r['late_ui_write_count_before_followthrough']==0 and len(r['ui_trace_scope'])==7
        handoffs.append(dict(unit=unit,point=at,complete=r['complete_slots'],late_ui_writes=0,evidence=name))
    for point in ('redraw','cache'):
        r=records[f'native/ui-cutpoint-{point}-{unit}.json'];assert r['status']=='PASS' and not r['writes_after_switch'] and len(r['ui_trace_scope'])==7
    for group in ('recovery','fallback'):
        assert records[f'native/concurrent_menu-{group}-{unit}.json']['status']=='PASS'
    nested=records[f'native/concurrent_menu-nested-{unit}.json']
    assert len(nested['cases'])==3
    for row in nested['cases']:
        assert row['outer']['ok'] and row['schedule']['native_result']['ok']
        assert row['complete_slots'] in ([4],[5]) and row['after']['root']['state']==3
        assert row['after']['list']['uncertain']==0
    for entry in ('fn2','ok','adj'):
        name=f'native/entry-switch-{unit}-{entry}-at1.json';r=records[name]
        assert r['status']=='COUNTEREXAMPLE' and not r['other_menu_ui_preserved'] and len(r['ui_trace_scope'])==7
        assert r['complete_slots']==[4] and r['after']['native_overlay']==0
        entry_rows.append(dict(unit=unit,entry=entry,late_writes=len(r['writes_after_switch']),root_state=r['after']['root']['state'],evidence=name))
    for at in (1,6):
        name=f'native/failure-boundary-{unit}-at{at}.json';r=records[name]
        assert r['status']=='NOTICE_ABSENT' and r['complete_slots']==[4]
        assert r['after']['W']==0 and r['notice']['rows']==7 and not r['notice_visible']
        early.append(dict(unit=unit,at=at,rpc=r['after']['rpc'],W=0,notice=False,evidence=name))
for entry in ('fn2','ok','adj'):
    r=records[f'native/baseline-entry-switch-50mm-{entry}-at1.json']
    assert r['generation']==117
    if entry=='adj':
        assert r['status']=='NOT_APPLICABLE_NO_RPC' and not r['schedule']['fired'] and r['schedule']['rpc_seen']==0
        assert r['complete_slots']==[4] and r['after']['W']==0
    else:assert r['status']=='COUNTEREXAMPLE'
ident=json.loads((OUT/'identity.json').read_text())['119']
for unit in ('50mm','28mm','mount'):
    assert records[f'native/matrix-{unit}.json']['dat_sha256']==ident['dat']
result=dict(status='REVIEW_COMPLETE_WITH_FINDINGS',verdict='不可以上卡。',required_records=len(records),
    evidence=[dict(path=n,sha256=sha((OUT/n).read_bytes()),status=r.get('status')) for n,r in records.items()],
    matrix=matrix,H08_switch_points=handoffs,other_entry_menu_changes=entry_rows,early_failure_no_notice=early,
    marker_before_rpc=[dict(unit=unit,**records[f'native/confirm-paths-{unit}.json']['dot_checks']) for unit in ('50mm','28mm','mount')],
    file_mutation_observations=len(mutations),file_mutations=mutations,rpc_commands=sorted(rpc_commands),
    findings=['P1-01: Fn2 and H07 can modify another native menu during the specified concurrent schedule.',
              'P1-02: Persistent communication failure before the first W has no visible error row.',
              'P1-CG01: rv_call has specific remaining A/B/C obligations, recorded per PC and direction.',
              'P2: Mixed RAM after partial W is latched and indicated; physical power/reset remains untested.'])
save('acceptance.json',result)
print('REVIEW COMPLETE',len(records),'native records; quality findings retained; file mutation observations',len(mutations),'all zero',flush=True)
