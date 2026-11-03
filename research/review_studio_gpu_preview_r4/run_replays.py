"""Replay frozen r2/r3 probes sequentially; every command is bounded."""
import json,os,subprocess,sys,time
from pathlib import Path
r=Path(__file__).resolve().parent
python=Path('/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview/.venv/bin/python')
cases=[('original-extra',['run_original.py','extra_boundaries.py']),('r3-extra',['extra_boundaries.py']),('r3-loop',['windows_loop_guard.py']),('r3-contracts',['windows_contracts.py'])]+[('r2-'+name,['replay_r2.py',name]) for name in ['media_root_race','path_delete_race','card_reader_retarget','lut_reimport_probe','http_boundary_extra']]
receipts=[]
for label,parts in cases:
 env=dict(os.environ)
 folder=Path(env['REVIEW_TMP'])/label
 folder.mkdir()
 env['REVIEW_TMP']=str(folder)
 start=time.monotonic()
 command=[str(python),'-I','-B',str(r/parts[0]),*parts[1:]]
 with (r/(label+'.log')).open('wb') as log:
  completed=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=300)
 result={'case':label,'command':command,'exit':completed.returncode,'seconds':time.monotonic()-start,'head':'fb6bacc51a35ee56736f9af4de5aa624cfd4ac14'}
 receipts.append(result)
 (r/'replay-receipts.json').write_text(json.dumps(receipts,indent=2)+'\n')
 print(json.dumps(result),flush=True)
