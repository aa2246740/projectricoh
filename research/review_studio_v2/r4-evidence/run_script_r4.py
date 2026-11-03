from pathlib import Path
import json,os,subprocess,sys,time
E=Path(__file__).resolve().parent;R=E.parent
os.environ.update(TMPDIR=str(R),PYTHONDONTWRITEBYTECODE='1',XDG_CACHE_HOME=str(R/'cache'),UV_CACHE_DIR=str(R/'uv'),UV_NO_SYNC='1',RUFF_CACHE_DIR=str(R/'ruff'),MYPY_CACHE_DIR=str(R/'mypy'),PYLINTHOME=str(R/'cache/pylint'))
for name in sys.argv[1:]:
 cmd=([sys.executable,'-B'] if name.endswith('.py') else ['node'])+[str(E/name)]
 start=time.monotonic()
 with (E/(name+'.log')).open('w') as out:
  result=subprocess.run(cmd,cwd='/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio',env=os.environ,stdout=out,stderr=subprocess.STDOUT,timeout=1800)
 row={'script':name,'command':cmd,'exit_code':result.returncode,'seconds':round(time.monotonic()-start,3),'timeout_seconds':1800}
 (E/(name+'.run.json')).write_text(json.dumps(row,indent=2)+'\n');print(json.dumps(row),flush=True)
 if result.returncode:
  print((E/(name+'.log')).read_text()[-3000:],flush=True);raise SystemExit(result.returncode)
