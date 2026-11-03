"""Assert the observed review results without converting counterexamples to passes."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from scope_guard import HERE, ROOT, emit, enable, sha
from independent_cases import differences
from suite_compare import leaves

def read(name):return json.loads((HERE/'local'/name).read_text())

def main():
    enable()
    initial=read('independent-summary.json');extended=read('extended-summary.json')
    assert initial['cases']==15 and initial['equal']==15 and initial['mismatches']==0
    assert extended['cases']==4 and extended['mismatches']==0
    for summary in ('new-summary.json','b-binding/local/new-summary.json'):
        cases=read(summary)
        assert cases['cases']==6 and cases['equal']==4 and cases['mismatches']==2
        actual={row['case'] for row in cases['checks'] if not row['equal']}
        assert actual=={'parent-class-op-replacement','write-parent-class-op-replacement'}
        folder='new-cases' if summary=='new-summary.json' else 'b-binding/local/new-cases'
        for name,value,event_count in [('parent-class-op-replacement',44,4),('write-parent-class-op-replacement',39,3)]:
            row=read(folder+'/'+name+'.json')
            assert row['values'][0]['state']['r'][9]==value and row['values'][1]['state']['r'][9]==0
            assert len(row['values'][0]['events'])==event_count and not row['values'][1]['events']
            assert row['diagnostics'][1]['compatible'] and row['diagnostics'][1]['stats']['fallback_calls']==0
    trace=read('trace-summary.json');assert trace['passed'] and trace['cases']==6
    cache=read('cache-summary.json');assert cache['concurrency']['passed']
    assert cache['environment']==dict(first=140000,cached=150000,uncached=150000,same_key=False,equivalent=True)
    assert read('cache-fork-summary.json')['passed']
    assert read('api-summary.json')['passed'] and read('api-summary.json')['old_rejection']=='C core API differs'
    assert read('default-summary.json')['passed']
    assert read('boundary-summary.json')['passed'] and read('boundary-summary.json')['cases']==38
    source_copies=[]
    for name in ('independent_cases.py','extended_cases.py','trace_cases.py','cache_cases.py','default_cases.py'):
        a=ROOT/'research/review_harness_c'/name;b=HERE/name
        assert a.read_bytes()==b.read_bytes()
        source_copies.append(dict(name=name,sha256=sha(b),byte_identical=True))
    assert (ROOT/'tools/speedlab/content_cache.py').read_bytes()==(HERE/'content_cache.py').read_bytes()
    a=read('fixed-python-50mm/result.json');b=read('fixed-c-50mm/result.json')
    assert not differences(a,b)
    ma=read('fixed-python-50mm/metrics.json');mb=read('fixed-c-50mm/metrics.json')
    assert ma['instruction_count']==mb['instruction_count']==27322942
    assert ma['opcode_count']==mb['opcode_count']==42299447
    raw=[HERE/'local'/('fixed-'+side+'-50mm/local/accept-50mm.json') for side in ('python','c')]
    assert raw[0].read_bytes()==raw[1].read_bytes()
    fixed=dict(equal=True,compared_values=leaves(a),instruction_count=ma['instruction_count'],opcode_count=ma['opcode_count'],
        raw_sha256=sha(raw[0]),left=ma,right=mb)
    emit(HERE/'local/fixed-comparison.json',fixed)
    view_a=read('view-a-comparison.json');view_b=read('view-b-comparison.json')
    assert view_a['equal'] and view_b['equal']
    assert read('view-b-on/summary.json')['ui_audit_option']=='1'
    assert read('view-b/summary.json')['ui_audit_option']=='0'
    assert read('view-b-off-comparison.json')['equal']
    assert view_a['right']['native_stats']['instructions']==view_a['right']['instruction_count']
    assert view_b['right']['native_stats']['instructions']==view_b['right']['instruction_count']
    assert view_b['right']['native_stats']['ui_guard_calls']>0 and view_b['right']['native_stats']['fast_writes']>0
    stored=read('stored-audit-comparison.json')
    assert stored['equal'] and stored['files']==71 and stored['records']==994 and stored['mutation_rejected']
    result=dict(a_verdict='不可以切换',b_verdict='B 暂不合并',new_blocker='P1-03',original_cases_equal=19,
        new_cases_equal=4,new_cases_different=2,b_new_cases_different=2,trace_cases_equal=6,cache_environment_equal=True,
        fork_environment_equal_with_recorded_tools=True,real_old_api_rejected=True,b_boundary_cases_equal=38,
        fixed=fixed,view_a=view_a,view_b=view_b,retained_audit_tapes={k:stored[k] for k in ('equal','files','records','bytes','mutation_rejected','mutant_records')},
        copied_case_sources=source_copies)
    emit(HERE/'local/final-summary.json',result)
    print(json.dumps(dict(a=result['a_verdict'],b=result['b_verdict'],fixed_values=fixed['compared_values'],
          view_values=view_a['compared_values'],fresh_audit_events=view_b['audit_tapes']['records'])),flush=True)

if __name__=='__main__':main()
