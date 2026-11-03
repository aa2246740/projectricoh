"""Independent source snapshots and separate, cold application fixtures."""
import hashlib
import io
import json
import shutil
import subprocess
import tarfile
from pathlib import Path

HERE=Path(__file__).resolve().parent
TEMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-gpu-preview-r2')
WT=Path('/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview')
snap=TEMP/'main-snapshot';snap.mkdir()
archive=subprocess.check_output(['git','--no-optional-locks','-C',str(WT),'archive','edf01457cb8d941cda877cf6f5a1f84cd5c38324'])
with tarfile.open(fileobj=io.BytesIO(archive)) as t:t.extractall(snap,filter='data')
rows=[]
for mode in ('main','head'):
    root=TEMP/('baseline-'+mode)
    root.mkdir()
    for name in ('library','app-home'):shutil.copytree(TEMP/'studio'/name,root/name)
    (root/'app-home/flags.json').write_text('{"gpu_preview":false,"hdr_on_import":false}\n')
    rows.append({'mode':mode,'root':str(root),'flags':json.loads((root/'app-home/flags.json').read_text()),'library_index_sha256':hashlib.sha256((root/'library/.studio/index.sqlite').read_bytes()).hexdigest()})
(HERE/'baseline-fixtures.json').write_text(json.dumps({'source_commit':'edf01457cb8d941cda877cf6f5a1f84cd5c38324','archive_sha256':hashlib.sha256(archive).hexdigest(),'separate_processes_and_fixtures':True,'rows':rows},indent=2)+'\n')
print('Prepared separate baseline and head source/runtime fixtures')
