"""Verify review evidence, wait receipts, unchanged inputs, and task cleanup."""
from pathlib import Path
import datetime
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'research/review_g153'
TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-g153-r1')
START=1793555544
sha=lambda b:hashlib.sha256(b).hexdigest()

def main():
    rows=[]
    for directory in (OUT/'results',OUT/'reruns/backend-audit/results'):
        for p in directory.glob('*.json'):
            d=json.loads(p.read_text())
            if 'arguments' not in d:
                continue
            assert d['status']=='PASS' and d['nice']==10
            assert d['arguments']['side']=='c' and d['arguments']['timeout']==3600
            rows.append(dict(path=str(p.relative_to(ROOT)),**d))
    assert len(rows)==16
    rows.sort(key=lambda x:x['started_ns'])
    for unit in ('50mm','mount'):
        for slot in (4,8):
            for kind,n in (('unit',505),('S',4096)):
                data=[(OUT/'results'/f'exit-{unit}-{slot}-c-{stage}-{kind}.bin').read_bytes()
                      for stage in ('before','after','reopened')]
                assert all(len(b)==n for b in data)
                assert data[0]==data[1]==data[2]
    for row in rows:
        details=row['details']
        for name in ('audit','fresh_audit'):
            if name in details:
                assert details[name]['host_UI_writes']==0
                assert details[name]['native_stats']['instructions']>0
        if row['arguments'].get('run_tag')=='backend-audit':
            assert details['audit']['native_stats']['instructions']>0
    manifest=ROOT/'tools/native_harness_c/local/ccore/build.json'
    build=json.loads(manifest.read_text())
    assert build['python']==sys.version
    assert sha(Path(build['library']).read_bytes())==build['sha256']
    for path,expected in build['sources'].items():
        assert sha(Path(path).read_bytes())==expected
    current=(OUT/'checks/runtime_spots.py').read_bytes()
    (OUT/'results/runner-source'/(sha(current)+'.txt')).write_bytes(current)
    for row in rows:
        p=OUT/'results/runner-source'/(row['script_sha256']+'.txt')
        assert sha(p.read_bytes())==row['script_sha256']
    events=[]
    for row in rows:
        events.extend([(row['started_ns'],1),(row['ended_ns'],-1)])
    count=maximum=0
    for _,change in sorted(events):
        count+=change;maximum=max(maximum,count)
    assert count==0 and maximum==3
    index=dict(status='PASS',native_jobs=len(rows),distinct_selections=13,
               native_job_seconds=sum(r['seconds'] for r in rows),native_max_concurrency=maximum,
               process_note='One short static check also overlapped the three identity jobs; the all-check process limit was exceeded once.',
               backend=dict(path='tools/native_harness_c/python_backend.py',API=5,
                            manifest_sha256=sha(manifest.read_bytes()),library_sha256=build['sha256']),
               runs=rows)
    (OUT/'results/run-index.json').write_text(json.dumps(index,indent=2)+'\n')
    spec=importlib.util.spec_from_file_location('review_final_static',OUT/'checks/static_delta.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    before=json.loads((OUT/'results/inputs-before.json').read_text());after=m.snapshot()
    changed={p:[before.get(p),after.get(p)] for p in before.keys()|after.keys() if before.get(p)!=after.get(p)}
    assert not changed,changed
    (OUT/'results/inputs-after.json').write_text(json.dumps(dict(status='PASS',files=len(after),changes={}),indent=2)+'\n')
    for name in ('port-replay.json','memory-target.json','recovery-audit.json','recovery-confirm-receipt.json','static.json'):
        assert json.loads((OUT/'results'/name).read_text())['status']=='PASS'
    # Query only this review's test entries, and do not affect any process.
    pattern='[r]esearch/review_g153/checks/(runtime_spots|recovery_spot|memory_check|port_and_recovery|static_delta)[.]py'
    proc=subprocess.run(['/usr/bin/pgrep','-f',pattern],text=True,capture_output=True,timeout=20)
    assert proc.returncode in (0,1)
    active=[int(p) for p in proc.stdout.split() if int(p)!=os.getpid()]
    assert not active,active
    scratch_files=[p for p in TMP.rglob('*') if p.is_file()]
    scratch_bytes=sum(p.stat().st_size for p in scratch_files)
    assert TMP.resolve()==TMP and TMP.name=='review-g153-r1' and str(TMP).startswith('/Volumes/Workspace/Scratch/tmp/projectricoh/')
    shutil.rmtree(TMP)
    assert not TMP.exists()
    ended=time.time()
    cleanup=dict(status='PASS',task_scratch=str(TMP),scratch_removed=True,
                 removed_files=len(scratch_files),removed_bytes=scratch_bytes,active_review_test_pids=active,
                 completed_native_jobs=16,native_max_concurrency=3,all_check_limit_deviation=True,
                 frozen_input_files=len(after),frozen_changes=0,
                 started_utc=datetime.datetime.fromtimestamp(START,datetime.timezone.utc).isoformat(),
                 ended_utc=datetime.datetime.fromtimestamp(ended,datetime.timezone.utc).isoformat(),
                 elapsed_seconds=ended-START)
    (OUT/'results/cleanup.json').write_text(json.dumps(cleanup,indent=2)+'\n')
    print(json.dumps(dict(status='PASS',native_jobs=16,native_seconds=index['native_job_seconds'],
                         frozen_files=len(after),scratch_removed=True,elapsed_seconds=cleanup['elapsed_seconds'])))

if __name__=='__main__':main()
