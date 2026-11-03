"""Narrow cleanup and SHA256 sealing. Run after the Chinese report has been written."""
import json
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from run_review import ROOT,REVIEW,LOCAL,TMP,PACKAGE,SOURCE,digest,save,setup

def main():
    setup()
    accepted=json.loads((LOCAL/'acceptance-review.json').read_text())
    stable=json.loads((LOCAL/'input-stability.json').read_text())
    assert accepted['status']=='PASS_WITH_DEVICE_BOUNDARIES' and stable['status']=='PASS'
    assert (REVIEW/'REVIEW.md').read_text().splitlines()[0]=='可以上卡'
    process_list=(LOCAL/'processes-before-cleanup.txt').read_text()
    active=[]
    for line in process_list.splitlines():
        if 'review_probe3_r1/' not in line:continue
        parts=line.split()
        if len(parts)<3 or int(parts[0])==os.getpid():continue
        command=parts[2:]
        if ' -c ' in ' '+ ' '.join(command)+' ':continue
        if any(value.endswith(('/run_review.py','/c_suite.py','/page_review.mjs','/boundary_replay.py')) for value in command) or ('chromium_headless_shell-1228' in line and 'review_probe3_r1/local/' in line):
            active.append(line)
    assert not active,active
    assert TMP.resolve()==LOCAL.resolve()/'tmp' and not TMP.is_symlink()
    paths=list(TMP.rglob('*'));files=[p for p in paths if p.is_file()]
    removed_bytes=sum(p.stat().st_size for p in files);removed_files=len(files)
    for path in sorted(paths,key=lambda p:len(p.parts),reverse=True):
        if path.is_dir() and not path.is_symlink():path.rmdir()
        else:path.unlink()
    TMP.rmdir()
    save(LOCAL/'cleanup.json',dict(status='PASS',removed_directory=str(TMP),files=removed_files,
        apparent_bytes=removed_bytes,remaining_review_compute_processes=active,
        write_scope=str(REVIEW),nice=os.getpriority(os.PRIO_PROCESS,0),
        no_card_camera_network_or_Git_writes=True))
    inputs=json.loads((LOCAL/'inputs-after.json').read_text())
    names=set(inputs)
    manifest=REVIEW/'SHA256SUMS'
    for path in REVIEW.rglob('*'):
        if path.is_file() and path!=manifest and path.name not in ('sha256-verify.log','finalize.log'):
            names.add(str(path.relative_to(ROOT)))
    values={name:digest(ROOT/name) for name in sorted(names)}
    for name,wanted in inputs.items():assert values[name]==wanted,name
    manifest.write_text(''.join(value+'  '+name+'\n' for name,value in values.items()))
    print(json.dumps(dict(status='PASS',manifest_files=len(values),removed_files=removed_files,
        removed_bytes=removed_bytes,input_files=stable['files'])))

if __name__=='__main__':main()
