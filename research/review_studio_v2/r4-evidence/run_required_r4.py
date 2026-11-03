from pathlib import Path
import json,os,subprocess,sys,time
E=Path(__file__).resolve().parent
R=E.parent
os.environ.update(TMPDIR=str(R),PYTHONDONTWRITEBYTECODE='1',XDG_CACHE_HOME=str(R/'cache'),UV_CACHE_DIR=str(R/'uv'),UV_NO_SYNC='1',RUFF_CACHE_DIR=str(R/'ruff'),MYPY_CACHE_DIR=str(R/'mypy'),PYLINTHOME=str(R/'cache/pylint'))
rows=[]
for name in ('run_checks.py','portable_check.py'):
 start=time.monotonic()
 result=subprocess.run([sys.executable,'-B',str(E/name)],env=os.environ,timeout=1800)
 row={'script':name,'exit_code':result.returncode,'seconds':round(time.monotonic()-start,3),'timeout_seconds':1800}
 rows.append(row);(E/'required-run.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(row),flush=True)
 if result.returncode:raise SystemExit(result.returncode)
