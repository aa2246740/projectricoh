"""Clean only the synthetic strict-scan follow-up, without touching other runs."""
import datetime
import json
import plistlib
import shutil
import subprocess
from pathlib import Path

HERE=Path(__file__).resolve().parent
TEMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-gpu-preview-r2')
v=plistlib.loads(subprocess.check_output(['diskutil','info','-plist','/Volumes/Workspace']))
assert v['VolumeUUID']=='14BE04EB-AF49-497E-B36A-B078B2F7C5E8' and v['Writable']
assert TEMP.is_dir() and not TEMP.is_symlink() and TEMP.resolve()==TEMP
scan_only={p.name for p in TEMP.iterdir()}=={'card-reader-retarget'}
repro_marker=TEMP/'repro-evidence/repro-run.json'
repro=json.loads(repro_marker.read_text()) if repro_marker.is_file() else None
assert scan_only or (repro is not None and len(repro['results'])==5 and all(r['exit_code']==0 for r in repro['results']))
files=[p for p in TEMP.rglob('*') if p.is_file() and not p.is_symlink()]
entry={'scope':'synthetic production strict-scan follow-up' if scan_only else 'end-to-end validation of the delivered synthetic reproduction entry','files':len(files),'bytes':sum(p.stat().st_size for p in files),'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
cleanup=json.loads((HERE/'cleanup.json').read_text())
if not (HERE/'cleanup-primary.json').exists():shutil.copyfile(HERE/'cleanup.json',HERE/'cleanup-primary.json')
shutil.rmtree(TEMP);assert not TEMP.exists()
cleanup.setdefault('followup_cleanups',[]).append(entry)
cleanup['removed_regular_files']+=entry['files'];cleanup['removed_bytes']+=entry['bytes'];cleanup['utc']=entry['utc']
(HERE/'cleanup.json').write_text(json.dumps(cleanup,indent=2)+'\n')
print(json.dumps(entry))
