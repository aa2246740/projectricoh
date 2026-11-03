from pathlib import Path
import json,os,shutil,subprocess,sys,time
ROOT=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-v2-r2');E=ROOT/'evidence'
STUDIO=Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio')
env=os.environ.copy();env.update(TMPDIR=str(ROOT),PYTHONDONTWRITEBYTECODE='1',XDG_CACHE_HOME=str(ROOT/'cache'),PYLINTHOME=str(ROOT/'pylint'),GIT_OPTIONAL_LOCKS='0')
records=[]
for script in ('baseline_fixture.py','acceptance.py','geometry_r2.py','text_r2.py','copy_audit.py','copy_r2.py'):
 start=time.monotonic()
 with (E/(script+'.log')).open('w') as out:
  proc=subprocess.run([sys.executable,'-B',str(E/script)],cwd=STUDIO,env=env,stdout=out,stderr=subprocess.STDOUT,timeout=1800)
 if script=='copy_audit.py' and (E/'COPY_VIOLATIONS.tsv').exists():shutil.copyfile(E/'COPY_VIOLATIONS.tsv',E/'copy-legacy-candidates.tsv')
 row={'script':script,'exit_code':proc.returncode,'seconds':round(time.monotonic()-start,2)};records.append(row)
 (E/'serial-checks-r2.json').write_text(json.dumps(records,indent=2)+'\n')
 print(json.dumps(row),flush=True)
 if proc.returncode and script not in ('copy_audit.py',):raise SystemExit(proc.returncode)
