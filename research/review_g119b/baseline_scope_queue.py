"""Recheck baseline entry schedules with the expanded UI write range."""
from pathlib import Path
import subprocess,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import OUT,ROOT,save
rows=[]
for entry in ('fn2','ok','adj'):
    rc=subprocess.call(['/usr/bin/python3','-I','-B',str(OUT/'run_recorded.py'),'baseline-entry-'+entry+'-u2','/usr/bin/python3','-I','-B',str(OUT/'entry_switch.py'),'50mm',entry,'--baseline'],cwd=ROOT)
    rows.append(dict(entry=entry,returncode=rc));save('baseline-scope-queue.json',rows)
    print('BASELINE',entry,'exit',rc,flush=True)
raise SystemExit(any(x['returncode'] for x in rows))
