#!/usr/bin/python3
"""Reproduce the review workloads serially inside the existing write fence."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-body-reclaim')
assert HERE==ROOT/'research/review_body_reclaim'
assert not TMP.is_symlink()
TMP.mkdir(parents=True,exist_ok=True)
os.environ.update(TMPDIR=str(TMP),PYTHONDONTWRITEBYTECODE='1',CLANG_MODULE_CACHE_PATH=str(TMP/'clang-cache'))
records=[]

def run(name,args,timeout=900):
    log=HERE/f'local/reproduce-{name}.log'
    start=time.monotonic()
    with log.open('w') as stream:
        result=subprocess.run(['/usr/bin/nice','-n','10',*map(str,args)],cwd=ROOT,
                              stdout=stream,stderr=subprocess.STDOUT,timeout=timeout,env=os.environ.copy())
    row={'name':name,'arguments':list(map(str,args)),'returncode':result.returncode,
         'elapsed_seconds':round(time.monotonic()-start,3),'timeout_seconds':timeout,
         'log':str(log.relative_to(HERE))}
    records.append(row)
    if result.returncode:
        print(log.read_text()[-6000:]);raise RuntimeError(row)

def frozen():
    snapshot=json.loads((HERE/'inputs-before.json').read_text())['files']
    bad=[name for name,digest in snapshot.items() if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest]
    assert not bad,bad
    return len(snapshot)

def main():
    start=time.monotonic();input_count=frozen()
    run('rebuild',['/bin/zsh',HERE/'rebuild_review.sh',HERE/'local/sizes.json'],1800)
    assert json.loads((HERE/'local/sizes.json').read_text())==json.loads((ROOT/'research/body_next_steps/prototype/sizes.json').read_text())
    reference=HERE/'local/observer-reference'
    assert reference.parent==HERE/'local' and not reference.is_symlink()
    if reference.exists():shutil.rmtree(reference)
    reference.mkdir()
    for source in (HERE/'local/rebuild/v/r3').iterdir():
        if source.is_file():shutil.copy2(source,reference/source.name)
    source=(reference/'hooks.c').read_text();attribute='__attribute__((optimize("no-jump-tables")))\n'
    assert source.count(attribute)==1
    (reference/'hooks.c').write_text(source.replace(attribute,''))
    run('observer-reference',['/usr/bin/python3','-I','-B',HERE/'proto_strict_review.py',reference,'rv_resume_10=0x202b1210'])
    run('layout-compile',['/usr/bin/clang','-std=c11','-I'+str(reference),HERE/'local/layout.c','-o',HERE/'local/layout'])
    run('layout',[HERE/'local/layout'])
    layout=json.loads((HERE/'local/reproduce-layout.log').read_text())
    (HERE/'local/layout.json').write_text(json.dumps(layout,indent=2)+'\n')
    for name,script in [('host','run_host_review.py'),('header','run_header_review.py'),
                        ('native','native_replay.py'),('observer','observer_replay.py'),
                        ('restore','run_restore_review.py'),('stack','stack_review.py'),
                        ('static','static_recheck.py')]:
        run(name,['/usr/bin/python3','-I','-B',HERE/script])
    source=HERE/'local/rebuild/v/r3';out=HERE/'local'
    flags=['-std=c11','-O1','-g','-Wall','-Wextra','-Wno-unknown-attributes','-fno-builtin',
           '-fsanitize=address,undefined','-fno-omit-frame-pointer','-DRV_HOST','-DREVIEW_C5=1',
           '-I'+str(source),'-I'+str(out/'host')]
    units=[HERE/'handshake_permissions.c',*[source/name for name in ['resident.c','shared.c','hooks.c','loader.c','validate_envelope.inc.c']],
           out/'host/services.c',out/'host/api.c']
    run('handshake-compile',['/usr/bin/clang',*flags,*units,'-o',out/'handshake-permissions'])
    run('handshake',[out/'handshake-permissions'])
    permissions=json.loads((out/'reproduce-handshake.log').read_text())
    (out/'handshake-result.json').write_text(json.dumps({'result':permissions},indent=2)+'\n')
    assert frozen()==input_count
    result={'classification':'serial reproduction of scoped review evidence',
            'input_files_unchanged':input_count,'size_table_exact_match':True,
            'elapsed_seconds':round(time.monotonic()-start,3),'records':records,
            'scope':'read-only inputs, no network, camera, storage card, Git writes, or subagents'}
    (out/'reproduction-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='records'},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
