"""Freeze verification, owned temporary cleanup, and final checksum sealing."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

HERE=Path(__file__).resolve().parent
OUT=HERE.parent
ROOT=HERE.parents[2]
RUNS=HERE/'runs'
TEMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-emulator-fast-r1')
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(2**20),b''):h.update(block)
    return h.hexdigest()
p=argparse.ArgumentParser()
p.add_argument('action',choices=('freeze','cleanup','seal'))
a=p.parse_args()
assert os.getpriority(os.PRIO_PROCESS,0)>=10
if a.action=='freeze':
    initial=json.loads((RUNS/'frozen-inputs.json').read_text())
    rows={}
    differences=[]
    for name,expected in initial['files'].items():
        path=ROOT/name
        actual={'sha256':sha(path),'bytes':path.stat().st_size}
        rows[name]=actual
        if actual!=expected:
            differences.append({'path':name,'before':expected,'after':actual})
    record={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'files':rows,
            'count':len(rows),'differences':differences}
    (RUNS/'frozen-inputs-final.json').write_text(json.dumps(record,indent=2)+'\n')
    assert not differences,differences
    print(json.dumps({'unchanged_files':len(rows)}))
elif a.action=='cleanup':
    lines=subprocess.check_output(['ps','-Ao','pid,ppid,ni,etime,args'],text=True).splitlines()
    remaining=[line for line in lines if 'review_emulator_fast_r1/local/' in line and
               'python' in line.lower() and 'finalize.py' not in line]
    assert not remaining,remaining
    assert TEMP==Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-emulator-fast-r1')
    before=[]
    if TEMP.exists():
        assert TEMP.is_dir() and not TEMP.is_symlink()
        before=[str(path.relative_to(TEMP)) for path in TEMP.rglob('*')]
        shutil.rmtree(TEMP)
    rec={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
         'temporary_path':str(TEMP),'temporary_contents_before':before,
         'temporary_removed':not TEMP.exists(),'remaining_review_processes':remaining,
         'nice':os.getpriority(os.PRIO_PROCESS,0)}
    (RUNS/'cleanup.json').write_text(json.dumps(rec,indent=2)+'\n')
    print(json.dumps(rec))
else:
    target=OUT/'SHA256SUMS'
    paths=sorted(path for path in OUT.rglob('*') if path.is_file() and path!=target)
    for path in paths:
        assert not path.is_symlink()
    rows=[(sha(path),str(path.relative_to(ROOT))) for path in paths]
    target.write_text(''.join(digest+'  '+name+'\n' for digest,name in rows))
    errors=[name for digest,name in rows if sha(ROOT/name)!=digest]
    assert not errors,errors
    print(json.dumps({'verified_entries':len(rows),'manifest_sha256':sha(target),
                      'total_bytes':sum(path.stat().st_size for path in paths)}))
