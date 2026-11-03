import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

WT=Path('/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview')
HERE=Path(__file__).resolve().parent
TEMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-gpu-preview-r2/prefetch-generation')
sys.path.insert(0,str(WT/'tests'))
from test_gpu_state import ENGINE_STUB
rows=[]
for scenario in ('late-success','late-failure'):
    root=TEMP/scenario;(root/'gpu').mkdir(parents=True)
    for name in ('gpu_stage.js','state.js'):shutil.copyfile(WT/'web/assets'/name,root/name)
    (root/'package.json').write_text('{"type":"module"}\n')
    (root/'api.js').write_text('export const api=(...a)=>globalThis.apiStub(...a);\n')
    (root/'gpu/engine.js').write_text(ENGINE_STUB)
    run=subprocess.run(['node',str(HERE/'prefetch_generation.mjs'),str(root),scenario],capture_output=True,text=True,timeout=30)
    assert run.returncode==0,run.stdout+run.stderr
    rows.append(json.loads(run.stdout))
out={'gpu_stage_sha256':hashlib.sha256((WT/'web/assets/gpu_stage.js').read_bytes()).hexdigest(),'rows':rows}
(HERE/'prefetch-generation.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
