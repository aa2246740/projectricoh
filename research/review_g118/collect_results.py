"""Validate the actual evidence artifacts and produce a compact acceptance ledger."""
from pathlib import Path
import json
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from common import OUT, save, file_sha

def get(name):return json.loads((OUT/name).read_text())

def file_counters(x,where='root'):
    found=[]
    if isinstance(x,dict):
        if {'create','write','rename','delete','write_open'}<=x.keys():
            counts={k:x[k] for k in ('create','write','rename','delete','write_open')}
            assert not any(counts.values()),(where,counts)
            found.append(where)
        for k,v in x.items():found.extend(file_counters(v,where+'.'+k))
    elif isinstance(x,list):
        for i,v in enumerate(x):found.extend(file_counters(v,where+'['+str(i)+']'))
    return found

def main():
    ledger=[];counters=[]
    for unit in ('50mm','28mm','mount'):
        for group in ('matrix','ah','perf'):
            f=f'native/{group}-{unit}.json';d=get(f)
            assert d['status']=='PASS',f
            assert d['dat_sha256']=='e557c7266c05ea5b997bd369b505ea364c660e87aef07180c784207ffd0f3f2d'
            assert d['elf_sha256']=='108bdd2b6546df7ebb0f58cf165e5c86864f293e17aa49b76fef06ac5c067383'
            assert d['getter_fixed_return_stub_removed'] and not d['native_ui_hand_seeded']
            counters.extend((f,x) for x in file_counters(d))
            if group=='matrix':
                assert len(d['fast_moves'])==41 and len(d['faults'])==3
                assert d['cold']['state']['cursor']==d['cold']['state']['dot_row']==4
                assert d['cold']['state']['rpc']==d['cold']['state']['W']==0
                assert d['cold']['actual']['slot']==d['reboot']['actual']['slot']==4
            elif group=='ah':
                assert all(k in d for k in 'abcdefgh')
                assert not d['g']['old_preferences_opened']
                assert d['g']['stale_files_unchanged']
            else:assert len(d['moves'])==32 and all(x['crc_accelerated_calls']==x['rpc_errors']==0 for x in d['moves'])
            ledger.append(dict(file=f,status=d['status'],sha256=file_sha(OUT/f),wall_seconds=d['wall_seconds']))
        f=f'native/adversarial-recovery-{unit}.json';d=get(f)
        assert d['status']=='PASS' and len(d['rows'])==9
        assert sum(x['W'] for x in d['rows'])==sum(x['V'] for x in d['rows'])==253
        assert len(d['settings_tokens'])==2
        counters.extend((f,x) for x in file_counters(d));ledger.append(dict(file=f,status=d['status'],sha256=file_sha(OUT/f)))
    x=get('native/adversarial-recovery-50mm.json')['page_crossings']
    assert len(x)==1 and x[0]['previous']=='0x2012fffe' and x[0]['next']=='0x20130000'
    assert x[0]['X']['cmd']==23 and x[0]['X']['value']==0x2013 and x[0]['V']['cmd']==21 and x[0]['V']['value']==0
    foreign=get('native/adversarial-foreign-50mm.json');persistent=get('native/persistent-50mm.json');baseline=get('native/baseline-delta.json')
    assert foreign['schedule']['resident_inflight']==1
    assert foreign['schedule']['after_native']['native_activity']==foreign['after']['native_activity']==7
    assert foreign['after']['native_overlay']==21 and foreign['after']['root']['state']==3
    assert foreign['complete_slots']==[7]
    late=foreign['writes'][foreign['schedule']['write_mark_after_native']:]
    assert all(any(w['address']==a and w['data']=='07' for w in late) for a in ('0x2022f725','0x2022f726','0x205a2944'))
    assert not persistent['matching_complete_slots'] and persistent['after']['list']['uncertain']==1
    assert persistent['after']['root']['state']==6 and persistent['after']['W']==10 and persistent['after']['rpc']==18
    assert baseline['after_H08']['rpc']==0 and baseline['after_H08_actual']['slot']==4
    assert not baseline['complete_slots_after_H07']
    assert baseline['after_H07']['deep_sha256']==persistent['after']['deep_sha256']
    for f in ('native/adversarial-foreign-50mm.json','native/persistent-50mm.json','native/baseline-delta.json',
              'native/adversarial-exits-50mm.json','native/adversarial-nested-50mm.json','native/adversarial-fallback-50mm.json'):
        d=get(f);assert d['status'] not in ('FAIL','PARTIAL_NATIVE_BLOCK')
        counters.extend((f,x) for x in file_counters(d));ledger.append(dict(file=f,status=d['status'],sha256=file_sha(OUT/f)))
    for n in ('ig_init','list_bind','panel_render','ig_menu','ig_event','ig_apply'):
        d=get(n+'-results.json');assert d['random']==10000 and d['boundary']==64 and not d['failures']
    branches=get('branch-closure.json');assert all(x['status']=='ACCOUNTED' for x in branches.values())
    closure=get('codegen-closure.json');assert closure['all_changed_accounted'] and not closure['unresolved']
    assert closure['changed_shared']==92 and len(closure['symbol_obligations'])==130
    assert get('measurements.json')['status']=='PASS_COUNTS_ONLY'
    assert get('machine-gates.json')['zero_file_mutations']
    assert get('package.json')['card_checksums']=='30/30 OK'
    result=dict(verdict='不可以上卡。',status='REVIEW_COMPLETED_WITH_BLOCKING_FINDINGS',
        runs=ledger,zero_file_counter_observations=len(counters),counter_locations=counters,
        shared_changed=92,symbol_obligations=130,differential_pairs=60384,
        extra_directed_pairs=sum(x['extra_directed'] for x in branches.values()),
        no_independent_compile=True,no_camera=True,no_storage_card_access=True,
        findings=[dict(id='P1-01',kind='new foreign-native-list ownership failure',evidence='native/adversarial-foreign-50mm.json'),
                  dict(id='P1-02',kind='inherited partial-write failure with new H08 exposure',evidence='native/persistent-50mm.json'),
                  dict(id='P2-01',kind='conditional latency and unobserved LCD intermediate frame',evidence='measurements.json')])
    save('acceptance.json',result)
    print('PASS evidence ledger:',len(ledger),'runs,',len(counters),'zero-file counter observations;',60384,'random+boundary pairs;',result['extra_directed_pairs'],'extra directed pairs',flush=True)

if __name__=='__main__':main()
