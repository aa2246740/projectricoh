"""Run the native harness copies, keeping every self-written file in this tree."""
from pathlib import Path
import subprocess,os,json,sys,time
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OUT=HERE/'local'
commands=[('native-scenarios',['/usr/bin/python3','-I','-B',HERE/'native_harness/scenarios.py']),('native-v35-g117',['/usr/bin/python3','-I','-B',HERE/'run_v35_g117.py'])]
rows=[]
for name,argv in commands:
 start=time.monotonic()
 p=subprocess.run([str(x) for x in argv],cwd=ROOT,env=dict(os.environ,TMPDIR=str(HERE/'candidate/local/tmp'),PYTHONDONTWRITEBYTECODE='1'),capture_output=True,text=True,timeout=1500)
 (OUT/(name+'.stdout')).write_text(p.stdout);(OUT/(name+'.stderr')).write_text(p.stderr)
 rows.append(dict(name=name,argv=[str(x) for x in argv],returncode=p.returncode,seconds=round(time.monotonic()-start,3)))
 (OUT/'native-runs.json').write_text(json.dumps(rows,indent=2)+'\n')
 print(name,'returncode',p.returncode,p.stdout,p.stderr,flush=True)
sys.exit(any(row['returncode'] for row in rows))
