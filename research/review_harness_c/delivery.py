"""Recheck read-only inputs, clean the task temp directory, and seal delivery."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from scope_guard import HERE, ROOT, TMP, emit, enable, sha

parser=argparse.ArgumentParser()
parser.add_argument('mode',choices=('inputs','cleanup','seal','verify'))
args=parser.parse_args()
enable(create_tmp=args.mode=='inputs')
if args.mode=='inputs':
    before=json.loads((HERE/'local/inputs-before.json').read_text())
    changed=[dict(path=name,expected=value,actual=sha(ROOT/name) if (ROOT/name).is_file() else None)
             for name,value in before.items() if not (ROOT/name).is_file() or sha(ROOT/name)!=value]
    membership=[]
    for name in ('tools/native_harness','tools/native_harness_c','tools/speedlab','tools/gxr_emulator_batch'):
        old={path for path in before if path.startswith(name+'/')}
        current={str(path.relative_to(ROOT)) for path in (ROOT/name).rglob('*') if path.is_file()}
        membership.append(dict(directory=name,added=sorted(current-old),removed=sorted(old-current)))
    passed=not changed and all(not row['added'] and not row['removed'] for row in membership)
    emit(HERE/'local/inputs-after.json',dict(count=len(before),passed=passed,changed=changed,membership=membership))
    print(json.dumps(dict(count=len(before),passed=passed)),flush=True)
    assert passed
elif args.mode=='cleanup':
    text=subprocess.check_output(['/bin/ps','-axo','pid=,comm=,args='],text=True)
    remaining=[]
    for row in text.splitlines():
        fields=row.strip().split(None,2)
        if (len(fields)==3 and int(fields[0])!=os.getpid() and 'python' in fields[1].lower()
                and (str(HERE) in fields[2] or 'research/review_harness_c/' in fields[2])):
            remaining.append(row)
    if remaining:raise RuntimeError('review processes remain: '+str(remaining))
    files=[str(path.relative_to(TMP)) for path in TMP.rglob('*') if path.is_file()]
    shutil.rmtree(TMP)
    emit(HERE/'local/cleanup.json',dict(tmpdir=str(TMP),files_removed=files,tmpdir_removed=not TMP.exists(),
           remaining_review_python_processes=remaining,passed=not TMP.exists() and not remaining))
    print('Task temporary directory removed; no remaining review Python processes',flush=True)
elif args.mode=='seal':
    target=HERE/'SHA256SUMS'
    rows=[sha(path)+'  '+str(path.relative_to(ROOT)) for path in sorted(HERE.rglob('*')) if path.is_file() and path!=target]
    target.write_text('\n'.join(rows)+'\n')
    print('Sealed',len(rows),'files',flush=True)
else:
    failed=[];count=0
    for row in (HERE/'SHA256SUMS').read_text().splitlines():
        expected,name=row.split(None,1);count+=1
        if sha(ROOT/name)!=expected:failed.append(name)
    print(json.dumps(dict(files=count,passed=not failed,mismatches=failed)),flush=True)
    assert not failed
