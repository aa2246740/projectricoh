"""Audit actual admission records and the protected reference-job transition."""
from pathlib import Path
import ast,datetime,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parent));import common as C
C.setup();out=C.LOCAL/'accept-r2';transition=out/'loadgate-transition'
def read(path):return json.loads(path.read_text())
start=read(transition/'start.json');drained=read(transition/'queue-before-resume.json')
assert not start['signals_sent'] and not drained['stopped']
before=ast.parse((transition/'common-before.py').read_text());after=ast.parse((C.HERE/'common.py').read_text())
for module in (before,after):module.body=[n for n in module.body if not isinstance(n,ast.FunctionDef) or n.name!='compute_gate']
assert ast.dump(before)==ast.dump(after),'non-admission common.py code changed'
original=read(transition/'jobs-full.json');current={r['id']:r for r in read(out/'jobs.json')}
for row in original:assert current[row['id']]==row,'original job inputs or assertions changed'
admissions=[json.loads(line) for line in (out/'admissions.jsonl').read_text().splitlines()]
protected=[]
for label,pid in start['protected'].items():
    rows=[r for r in admissions if r['task']==label]
    assert len(rows)==1 and rows[0]['pid']==pid and rows[0]['nice']>=15
    assert drained['finished'][label]['returncode']==0
    result=read(C.LOCAL/'runs'/label/'result.json')
    assert result['status']=='OBSERVED' and result['actual_backend']=='reference'
    assert result['cold_start'] and not result['snapshots'] and result['manual_safety_PASS']
    assert result['compensated_to_complete04'] and len(result['fault_events'])==1
    protected.append(dict(id=label,pid=pid,admissions=1,returncode=0))
samples=[json.loads(line) for line in (out/'load.jsonl').read_text().splitlines()]
samples=[r for r in samples if r.get('admission_policy')=='tools/loadgate.py']
post=[r for r in admissions if r.get('admission_policy')=='tools/loadgate.py']
assert samples and post
for row in samples:
    info=row['info'];running=row['running']
    assert row['nice']>=15 and 0<=running<=6 and running<=info['cap']<=min(6,running+1)
    if info['admit']:
        assert info['spare']>=1 and info['mem_free']>=25 and info['load1']<=3*info['ncpu']
cursor=0;matched=[]
for row in post:
    assert row['nice']>=15 and row['info']['admit']
    index=next(i for i in range(cursor,len(samples)) if samples[i]['info']==row['info'] and samples[i]['cap']==row['cap'])
    assert row['cap']==samples[index]['running']+1<=6
    matched.append(index);cursor=index+1
final=read(out/'queue-final.json')
assert final['admission_policy']=='tools/loadgate.py'
C.save(transition/'verification.json',dict(status='PASS',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),protected_reference_jobs=protected,old_children_signalled=False,original_job_definitions_equal=True,original_jobs=len(original),common_unchanged_except_compute_gate=True,post_change_admissions=len(post),gate_samples=len(samples),unique_sample_per_admission=True,max_running_logged=max(r['running'] for r in samples),loadgate_sha256=C.sha((C.ROOT/'tools/loadgate.py').read_bytes()),timing_benchmarks_run=False,precision_changed=False))
print(json.dumps(dict(status='PASS',protected_references=2,admissions=len(post),samples=len(samples),precision_changed=False)))
