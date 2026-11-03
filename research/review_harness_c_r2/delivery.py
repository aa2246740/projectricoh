"""Check reviewed inputs, remove only the named temporary tree, and seal outputs."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from scope_guard import HERE, ROOT, TMP, emit, enable, sha

def inputs():
    before=json.loads((HERE/'local/inputs-before.json').read_text())
    changed=[]
    for name,wanted in before.items():
        path=ROOT/name;actual=sha(path) if path.is_file() else None
        if actual!=wanted:changed.append(dict(path=name,before=wanted,after=actual))
    original=json.loads((HERE/'local/implementation-manifest.json').read_text())
    manifest=ROOT/'research/speed_hillclimb/SHA256SUMS'
    mismatches=[];count=0
    for line in manifest.read_text().splitlines():
        wanted,name=line.split(None,1);p=ROOT/name.lstrip('*');count+=1
        actual=sha(p) if p.is_file() else None
        if actual!=wanted:mismatches.append(dict(path=name,expected=wanted,actual=actual))
    result=dict(passed=not changed and not mismatches and sha(manifest)==original['sha256'],
        execution_inputs=len(before),execution_input_changes=changed,implementation_manifest_files=count,
        implementation_manifest_sha256=sha(manifest),implementation_manifest_mismatches=mismatches)
    emit(HERE/'local/inputs-after.json',result)
    print(json.dumps({k:result[k] for k in ('passed','execution_inputs','implementation_manifest_files')}),flush=True)
    assert result['passed']

def cleanup():
    process_rows=subprocess.check_output(['/bin/ps','-axo','pid=,ppid=,command='],text=True)
    active=[]
    for row in process_rows.splitlines():
        parts=row.strip().split(None,2)
        if len(parts)!=3:continue
        pid,ppid,command=int(parts[0]),int(parts[1]),parts[2]
        if str(HERE) in command or 'review_harness_c_r2/run_entry.py' in command:
            if pid!=os.getpid():active.append(dict(pid=pid,ppid=ppid,command=command))
    assert not active,active
    assert TMP==Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-harness-c-r2') and not TMP.is_symlink()
    existed=TMP.exists()
    def remove(path):
        if path.is_symlink() or not path.is_dir():
            path.unlink()
            return
        for child in path.iterdir():remove(child)
        path.rmdir()
    if existed:remove(TMP)
    result=dict(passed=not TMP.exists(),temporary_directory=str(TMP),existed=existed,
        remaining_review_processes=active,utc=datetime.now(timezone.utc).isoformat())
    emit(HERE/'local/cleanup.json',result)
    print(json.dumps(result),flush=True)
    assert result['passed']

def verify():
    rows=(HERE/'SHA256SUMS').read_text().splitlines()
    wanted_paths=set();failed=[]
    for row in rows:
        wanted,name=row.split('  ',1);p=ROOT/name;wanted_paths.add(p.resolve())
        if not p.is_file() or sha(p)!=wanted:failed.append(name)
    actual={p.resolve() for p in HERE.rglob('*') if p.is_file() and p.name!='SHA256SUMS'}
    assert actual==wanted_paths,(actual-wanted_paths,wanted_paths-actual)
    assert not failed,failed
    print(json.dumps(dict(passed=True,files=len(rows),manifest_sha256=sha(HERE/'SHA256SUMS'))),flush=True)

def seal():
    assert (HERE/'REVIEW.md').read_text().splitlines()[0] in ('可以切换','不可以切换')
    assert json.loads((HERE/'local/cleanup.json').read_text())['passed'] and not TMP.exists()
    assert json.loads((HERE/'local/inputs-after.json').read_text())['passed']
    emit(HERE/'local/delivery.json',dict(utc=datetime.now(timezone.utc).isoformat(),
         review_sha256=sha(HERE/'REVIEW.md'),temporary_directory_absent=not TMP.exists()))
    lines=[sha(p)+'  '+str(p.relative_to(ROOT)) for p in sorted(HERE.rglob('*'))
           if p.is_file() and p.name!='SHA256SUMS']
    (HERE/'SHA256SUMS').write_text('\n'.join(lines)+'\n')
    verify()

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=('inputs','cleanup','seal','verify'));args=p.parse_args()
    enable(create_tmp=False)
    globals()[args.action]()

if __name__=='__main__':main()
