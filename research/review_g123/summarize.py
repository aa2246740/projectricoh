"""Verify report counts against completed records without rerunning firmware."""
from pathlib import Path
import json
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
from support import *


def read(name):
    return json.loads((OUT/name).read_text())


def main():
    findings=[]
    for panel in ('list','panel'):
        for action in ('right','left'):
            name=f'local/nested/50mm-{panel}-before_redraw-{action}.json'
            r=read(name);n=r['nested']
            assert r['status']=='FAIL' and 'Native H08 continued' in r['error']
            assert r['dat_sha256']==PIN and n['before']['root']['inflight']==1
            assert n['before']['rows']==n['before']['cursor']==n['before']['dot_row']==1
            assert n['psw']&0x40 and n['native_H08_visits']==1 and n['extra_RPC']==0
            assert n['S_changes']==[dict(offset=0x36e,before=1,after=9)]
            assert any(x['pc']=='0x20268774' and x['offset']==0x36e for x in n['writes'])
            assert r['after']['mode']==9 and not r['native_UI']['host_ui_writes']
            findings.append(dict(file=name,kind='new_ERR_inflight_H08_S_mutation'))
    controls=[]
    for generation in (121,123):
        for panel in ('list','panel'):
            for action in ('right','left'):
                prefix='121-' if generation==121 else ''
                name=f'local/nested/{prefix}50mm-{panel}-record_failure_return-{action}.json'
                r=read(name);n=r['nested']
                if panel=='list':
                    assert r['status'].startswith('PASS') and not n['S_changes'] and not n['native_H08_visits']
                    assert n['before']['rows']==8
                else:
                    assert r['status']=='FAIL' and n['native_H08_visits']==1
                    assert n['S_changes']==[dict(offset=0x36e,before=1,after=5 if action=='right' else 4)]
                controls.append(dict(generation=generation,panel=panel,action=action,
                    inherited_panel_failure=panel=='panel',file=name))
    draw_cases=[]
    for panel in ('list','panel'):
        for kind in ('activity','state'):
            name=f'local/cutpoints-irq-enabled/50mm-{panel}-after_redraw_restore-{kind}.json'
            r=read(name)
            assert r['status']=='FAIL' and r['irq_enabled'] and r['switch']['psw']&0x40
            assert not r['late_DAT_UI'] and not r['late_native_UI']
            assert any(d['after_switch'] for d in r['draws'])
            assert len(r['painted_rows_after_switch'])==1
            assert r['painted_rows_after_switch'][0]['marker']==r['painted_rows_after_switch'][0]['cursor']==1
            draw_cases.append(dict(file=name,kind='stale_native_ERR_redraw'))
    cases=sorted((OUT/'local/cases').glob('123-*.json'))
    assert len(cases)==27 and all(json.loads(p.read_text())['status']=='PASS' for p in cases)
    locked=sorted((OUT/'local/lock-cases').glob('*.json'))
    assert len(locked)==24 and all(json.loads(p.read_text())['status']=='PASS' for p in locked)
    official=[]
    for unit in ('50mm','28mm','mount'):
        name=f'local/official-half-{unit}-with-hooks.json';r=read(name)
        assert r['status']=='PASS_NATIVE_FALLBACK_NO_UNVERIFIED_RECIPE' and r['half_RPC']==0
        official.append(name)
    idle=[]
    raw=[]
    for generation in (121,123):
        for panel in ('list','panel'):
            for keep in (0,1):
                for action in ('confirm','adj','half','release','disp_confirm'):
                    name=f'local/lock-exits/{generation}-50mm-{panel}-k{keep}-{action}.json';r=read(name)
                    assert r['status']=='PASS_NO_NATIVE_OPTION_APPLIED' and not r['S_changes']
                    assert not r['native_setters'] and r['exit_RPC']==0
                    idle.append(name)
                name=f'local/lock-exits/{generation}-50mm-{panel}-k{keep}-raw_half-recheck-final.json';r=read(name)
                assert r['status']=='PASS_NO_NATIVE_OPTION_APPLIED' and r['exit_RPC']==0 and not r['native_setters']
                raw.append(name)
    for panel in ('list','panel'):
        for keep in (0,1):
            a=read(f'local/lock-exits/121-50mm-{panel}-k{keep}-raw_half-recheck-final.json')
            b=read(f'local/lock-exits/123-50mm-{panel}-k{keep}-raw_half-recheck-final.json')
            assert a['S_sha_before']==b['S_sha_before'] and a['S_sha_after']==b['S_sha_after']
            assert a['S_changes']==b['S_changes']
    assert read('evidence/h01-compare.json')['status']=='PASS'
    assert read('evidence/machine-verify.json')['count']==889
    assert read('evidence/rpc-audit.json')['status']=='PASS'
    save('evidence/review-summary.json',dict(status='REJECTED',blocking_P1=1,P2=1,
        dat_sha256=PIN,counterexamples_PASS=27,original_lock_cases_PASS=24,
        official_half_PASS=3,compiled_read_cases_PASS=889,H01_baseline_pairs_PASS=9,
        idle_exit_nonraw_PASS=len(idle),idle_raw_half_PASS=len(raw),
        idle_exit_scope='20 nonraw cases plus 4 raw-half cases per generation. Raw shooting-task S changes are compared exactly with gen 121.',
        new_S_counterexamples=findings,baseline_controls=controls,late_draw_counterexamples=draw_cases,
        official_half_files=official,
        discarded_tool_results='Initial lock-exit fixtures missed the W fault after the native task prologue; a subsequent version expected an ok field on a compound raw-key result. An overbroad all-S-zero assertion also rejected a native shooting-task S update identical in gen 121. Original records/logs are preserved; final raw-half records compare complete S transitions.'))
    print('REJECTED: 1 P1, 1 P2; 27 prior cases and 24 original lock cases pass; 4 new S counterexamples and 4 late redraw counterexamples')


if __name__=='__main__':main()
