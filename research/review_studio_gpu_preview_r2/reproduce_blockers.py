"""Rerun synthetic blocker probes into a fresh Scratch root, preserving this delivery."""
import json
import plistlib
import shutil
import subprocess
from pathlib import Path

HERE=Path(__file__).resolve().parent
TEMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-gpu-preview-r2')
WT=Path('/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview')
PY=WT/'.venv/bin/python'
subprocess.run(['df','-h','/Volumes/Workspace'],check=True)
volume=plistlib.loads(subprocess.check_output(['diskutil','info','-plist','/Volumes/Workspace']))
assert volume['VolumeUUID']=='14BE04EB-AF49-497E-B36A-B078B2F7C5E8' and volume['FilesystemType']=='apfs' and volume['Writable']
assert not TEMP.exists(),'An existing run is present. Preserve it and resolve ownership before running again.'
out=TEMP/'repro-evidence';out.mkdir(parents=True)
shutil.copyfile(HERE/'run_gate.py',out/'run_gate.py')
head=subprocess.check_output(['git','--no-optional-locks','-C',str(WT),'rev-parse','HEAD']).decode().strip()
results=[]
for name in ['media_root_race.py','http_boundary_extra.py','lut_reimport_probe.py','path_delete_race.py','card_reader_retarget.py']:
    shutil.copyfile(HERE/name,out/name)
    cmd=['nice','-n','10','/usr/bin/python3','-I','-B',str(out/'run_gate.py'),'--timeout','180',Path(name).stem,'--',str(PY),'-I','-B',str(out/name)]
    result=subprocess.run(cmd,check=False)
    results.append({'script':name,'exit_code':result.returncode})
(out/'repro-run.json').write_text(json.dumps({'head':head,'scope':'synthetic observations, not an automatic merge verdict','results':results},indent=2)+'\n')
print('Evidence retained at '+str(out))
raise SystemExit(0 if all(r['exit_code']==0 for r in results) else 1)
