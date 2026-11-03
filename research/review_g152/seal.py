"""Summarize local runs, recheck frozen inputs, and seal review outputs."""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import os
import shutil
import time

ROOT=Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
OUT=Path(__file__).resolve().parent
TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-g152')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--seal',action='store_true')
    p.add_argument('--cleanup',action='store_true')
    a=p.parse_args()
    assert os.getpriority(os.PRIO_PROCESS,0)>=10
    processes=json.loads((OUT/'processes-final.json').read_text())
    assert 0<=time.time_ns()-processes['checked_ns']<=120*10**9,'Refresh the process receipt before sealing.'
    assert not processes['active_tests'],processes
    manifest=ROOT/'research/looks_g152/SHA256SUMS'
    before=json.loads((OUT/'input_hashes_before.json').read_text())
    assert sha(manifest)==before['manifest_sha256']
    files=[]
    for record in before['files']:
        path=ROOT/record['path']
        actual=sha(path)
        assert actual==record['actual']==record['expected'],record['path']
        files.append(dict(path=record['path'],sha256=actual))
    frozen=json.loads((ROOT/'research/looks_g152/input_receipt.json').read_text())['files']
    for name,record in frozen.items():
        path=ROOT/name
        assert path.stat().st_size==record['bytes'] and sha(path)==record['sha256'],name
    review_inputs=json.loads((ROOT/'research/looks_g152/review_input_receipt.json').read_text())
    for name,value in review_inputs.items(): assert sha(ROOT/name)==value,name
    assert sha(ROOT/'research/review_g150/previous_state_checks.py')==sha(ROOT/'research/looks_g152/legacy/previous_state_checks.py')
    checked=dict(status='PASS',manifest_sha256=sha(manifest),files=len(files),
                 implementation_frozen_files=len(frozen),g150_reproducer_identical_to_copy=True,
                 design_review_inputs=len(review_inputs),
                 checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),entries=files)
    (OUT/'input_hashes_after.json').write_text(json.dumps(checked,indent=2)+'\n')
    runs=[]
    for path in sorted((OUT/'runs').glob('*.json')):
        record=json.loads(path.read_text())
        if 'module' not in record: continue
        assert record['nice']==10
        runs.append(dict(path=str(path.relative_to(ROOT)),module=record['module'],args=record['args'],
                         status=record['status'],seconds=record['seconds'],started_ns=record['started_ns'],
                         ended_ns=record['ended_ns']))
    events=[]
    for run in runs:
        events.extend(((run['started_ns'],1),(run['ended_ns'],-1)))
    count=maximum=0
    for _,delta in sorted(events):
        count+=delta
        maximum=max(maximum,count)
        assert count>=0
    assert maximum<=2 and count==0
    witness=json.loads((OUT/'witness_check.json').read_text())
    assert witness['status']=='CONFIRMED_P1'
    initial=datetime.datetime.fromisoformat(before['utc'])
    last=max(run['ended_ns'] for run in runs)
    summary=dict(verdict='不能上卡',blocking_findings=['P1-01'],runs=len(runs),
                 passing_runs=sum(run['status']=='PASS' for run in runs),
                 failed_runs=[run for run in runs if run['status']!='PASS'],
                 cumulative_job_seconds=sum(run['seconds'] for run in runs),
                 started_utc=before['utc'],last_job_utc=datetime.datetime.fromtimestamp(last/1e9,datetime.timezone.utc).isoformat(),
                 wall_seconds_to_last_job=last/1e9-initial.timestamp(),maximum_concurrent_test_processes=maximum,
                 nice=10,active_tests_at_seal=0,manifest_items_unchanged=len(files),
                 reviewed_frozen_inputs_unchanged=len(frozen),network_policy='deny network*',
                 design_review_inputs_unchanged=len(review_inputs),
                 output_roots=[str(OUT),str(TMP)],generated_ns=time.time_ns(),jobs=runs)
    (OUT/'execution_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    lines=['本轮作业均经 offline.sb，nice=10；时间来自运行器的 monotonic 计时。',
           '', '| 模块与参数 | 结果 | 秒 | 运行回执 |','| --- | --- | ---: | --- |']
    for run in sorted(runs,key=lambda v:v['started_ns']):
        title=run['module']+' '+' '.join(run['args'])
        link=Path(run['path']).relative_to(OUT.relative_to(ROOT))
        lines.append(f"| `{title.strip()}` | {run['status']} | {run['seconds']:.3f} | [{link}]({link}) |")
    lines.extend(('',f"作业累计 {summary['cumulative_job_seconds']:.3f} 秒，最大并发 {maximum}，收尾存活测试数 0。",''))
    (OUT/'RUNS.md').write_text('\n'.join(lines))
    if a.cleanup:
        targets=[]
        if TMP.exists(): targets.append(TMP)
        local=OUT/'runtime/local/native'
        if local.exists():
            targets.extend(path for path in local.rglob('decode') if path.is_dir())
        cleanup=[]
        for target in targets:
            assert not target.is_symlink()
            assert target==TMP or target.resolve().is_relative_to(OUT.resolve())
            entries=[path for path in target.rglob('*') if path.is_file()]
            cleanup.append(dict(path=str(target),files=len(entries),bytes=sum(path.stat().st_size for path in entries)))
            shutil.rmtree(target)
        (OUT/'cleanup.json').write_text(json.dumps(dict(active_tests=0,removed=cleanup),indent=2)+'\n')
    if a.seal:
        paths=sorted(path for path in OUT.rglob('*') if path.is_file() and path.name!='SHA256SUMS')
        assert not any(path.is_symlink() for path in paths)
        (OUT/'SHA256SUMS').write_text(''.join(sha(path)+'  '+str(path.relative_to(ROOT))+'\n' for path in paths))
        for line in (OUT/'SHA256SUMS').read_text().splitlines():
            value,name=line.split(maxsplit=1)
            assert sha(ROOT/name)==value
    print(json.dumps({k:v for k,v in summary.items() if k not in ('jobs','failed_runs')}),flush=True)


if __name__=='__main__':main()
