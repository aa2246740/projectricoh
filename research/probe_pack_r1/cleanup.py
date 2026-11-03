"""Remove this task's scratch directory after retaining replay inputs."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zlib
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *


def main():
    guard(create_tmp=False)
    receipt = json.loads((HERE/'evidence/acceptance.json').read_text())
    assert receipt['status']=='PASS'
    assert receipt['dat_sha256']==sha((PACKAGE/'local/SD_ROOT/GXRCE.DAT').read_bytes())
    assert freeze()==json.loads((HERE/'local/frozen-inputs.json').read_text())
    media = json.loads((HERE/'evidence/media-retention.json').read_text())
    assert media['status']=='PASS'
    for item in media['evidence_media']:
        assert sha(zlib.decompress((HERE/item['compressed']).read_bytes()))==item['medium_sha256']
    correction=json.loads((HERE/'local/cache-path-correction.json').read_text())
    moved=correction['moved_to_task_scratch']
    assert correction['files']==len(moved)==130
    assert all(not (ROOT/item['path']).exists() for item in moved), 'old cache path regenerated'
    rows={}
    for line in subprocess.check_output(['/bin/ps','-axo','pid=,ppid=,command='],text=True).splitlines():
        parts=line.split(None,2)
        if len(parts)==3: rows[int(parts[0])]=(int(parts[1]),parts[2])
    ancestors={os.getpid()}
    pid=os.getpid()
    while pid in rows and rows[pid][0] and rows[pid][0] not in ancestors:
        pid=rows[pid][0];ancestors.add(pid)
    active=[dict(pid=pid,command=command) for pid,(_,command) in rows.items()
            if pid not in ancestors and ('research/probe_pack_r1/' in command or 'probe-pack-r1/' in command)]
    assert not active, active
    assert TMP==Path('/Volumes/Workspace/Scratch/tmp/projectricoh/probe-pack-r1')
    assert not TMP.is_symlink() and TMP.resolve()==TMP
    files=list(TMP.rglob('*')) if TMP.exists() else []
    assert not [p for p in files if p.is_symlink()]
    count=sum(p.is_file() for p in files)
    size=sum(p.stat().st_size for p in files if p.is_file())
    if TMP.exists():shutil.rmtree(TMP)
    assert not TMP.exists()
    result=dict(status='PASS',temporary_directory=str(TMP),temporary_directory_removed=True,
                removed_files=count,removed_bytes=size,active_task_jobs=active,
                corrected_cache_files_absent=len(moved),protected_inputs_unchanged=len(freeze()),
                replay_media_retained=len(media['evidence_media']))
    save(HERE/'evidence/cleanup.json',result)
    print(json.dumps(result))


if __name__=='__main__':main()
