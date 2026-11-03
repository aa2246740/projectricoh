"""Check frozen inputs, validate manifests, and remove this task's temporary data."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from support import setup,ROOT,HERE,DATA,SCRATCH,BUILD_DATA,FIT_DATA,FIT_FILES,digest,dump,protected_snapshot
setup()
import ast
from datetime import datetime,timezone
import hashlib
import json
import os
import re
import shutil
import subprocess

def manifest_check(base):
    path=base/'SHA256SUMS'
    good=0;bad=[];self_entries=[]
    for line in path.read_text().splitlines():
        if not line.strip(): continue
        h,name=line.split(None,1)
        name=name.lstrip(' *')
        p=(base/name).resolve()
        if not p.is_relative_to(base.resolve()):
            raise ValueError('Manifest path outside its directory')
        actual=digest(p)
        if p==path.resolve():
            self_entries.append({'listed':h,'actual':actual,'matches':h==actual})
        elif actual==h:
            good+=1
        else:
            bad.append({'path':name,'listed':h,'actual':actual})
    return {'path':str(path.relative_to(ROOT)),'verified_data_files':good,
            'data_mismatches':bad,'self_entries':self_entries}

def main():
    after=protected_snapshot()
    before=json.loads((HERE/'protected_before.json').read_text())
    changed=[p for p in sorted(before.keys()|after.keys()) if before.get(p)!=after.get(p)]
    core_changes=[p for p in changed if p.startswith(('studio/src/gxr_studio/engine/',
                  'studio/src/gxr_studio/lut/','studio/src/gxr_studio/raw/'))]
    dump('protected_after.json',after)
    inputs=json.loads((HERE/'input_hashes.json').read_text())
    input_bad=[r['path'] for r in inputs if digest(ROOT/r['path'])!=r['sha256']]
    manifests=[manifest_check(DATA),manifest_check(ROOT/'artifacts/downloads/panasonic-25th-luts-20261102')]
    if any(r['data_mismatches'] for r in manifests) or input_bad:
        raise ValueError('A frozen data input changed')
    dump('input_verification.json',{'input_files':len(inputs),'input_hash_mismatches':input_bad,
                                   'supplied_manifests':manifests})
    for p in HERE.glob('*.py'):
        ast.parse(p.read_text(),filename=str(p))
    if (HERE/'REPORT.md').read_text().splitlines()[0] not in ('值得接入','部分值得','不值得'):
        raise ValueError('Report first line differs')
    if list(HERE.rglob('*.cube')) or list(HERE.rglob('*.bin')) or list(HERE.rglob('*.DAT')):
        raise ValueError('Unexpected source data in research output')
    for base in (BUILD_DATA,FIT_DATA):
        (base/'SHA256SUMS').write_text(''.join(digest(p)+'  '+p.relative_to(base).as_posix()+'\n'
             for p in sorted(base.rglob('*')) if p.is_file() and p.name!='SHA256SUMS'))
    docs=manifest_check(ROOT/'artifacts/downloads/vlog-alchemy-eval-sources-20261102')
    if docs['data_mismatches']:
        raise ValueError('A saved source document changed')
    repeat=json.loads((HERE/'source_repeat_checks.json').read_text()) if (HERE/'source_repeat_checks.json').exists() else None
    snapshot=json.loads((HERE/'studio_snapshot_receipt.json').read_text()) if (HERE/'studio_snapshot_receipt.json').exists() else None
    # Only the newly created task directory is eligible for removal.
    assert str(SCRATCH)=='/Volumes/Workspace/Scratch/tmp/projectricoh/vlog-alchemy-eval-r1'
    assert not SCRATCH.is_symlink()
    members=[p for p in SCRATCH.rglob('*') if p.is_file()]
    temporary_bytes=sum(p.stat().st_size for p in members)
    temporary_files=len(members)
    os.chdir(HERE)
    shutil.rmtree(SCRATCH)
    receipt={'protected_files_before':len(before),'protected_files_after':len(after),
             'protected_content_changes':changed,'frozen_inputs_verified':len(inputs),
             'studio_core_colour_source_changes':core_changes,
             'frozen_studio_source_files':None if snapshot is None else len(snapshot['files']),
             'source_repeat_equal':None if repeat is None else repeat['all_equal_except_elapsed_seconds'],
             'scratch':str(SCRATCH),'temporary_files_removed':temporary_files,
             'temporary_bytes_removed':temporary_bytes,'scratch_exists_after':SCRATCH.exists(),
             'product_writes':'none; Python file writes restricted to research output, task Scratch and local build-data directory',
             'git_mutations':False,'third_party_scripts_executed':False,'dat_files_created':False,
             'initial_time_observed_utc':'2026-11-02T02:17:06Z',
             'resumed_utc':'2026-11-02T02:36:05Z','resumed_deadline_utc':'2026-11-02T04:16:05Z',
             'completed_utc':datetime.now(timezone.utc).isoformat(),
             'process_policy':'at most two research calculations concurrently; nice 10; BLAS threads 1',
             'input_manifest_note':'Creator supplied manifest includes a stale self-entry; seven data-file entries verify, retained unchanged.'}
    dump('cleanup.json',receipt)
    output_files=[p for p in HERE.rglob('*') if p.is_file() and p.name!='SHA256SUMS']
    output_files.extend(FIT_DATA/name for name in FIT_FILES)
    (HERE/'SHA256SUMS').write_text(''.join(digest(p)+'  '+p.relative_to(ROOT).as_posix()+'\n'
         for p in sorted(output_files)))
    # Check the newly written output manifest too.
    rows=(HERE/'SHA256SUMS').read_text().splitlines()
    for line in rows:
        h,name=line.split(None,1)
        assert digest(ROOT/name)==h
    print(json.dumps({'output_files_verified':len(rows),'source_changes':changed,
                      'inputs_verified':len(inputs),'scratch_removed':not SCRATCH.exists(),
                      'manifest_data_counts':[r['verified_data_files'] for r in manifests]}),flush=True)

if __name__=='__main__':
    main()
