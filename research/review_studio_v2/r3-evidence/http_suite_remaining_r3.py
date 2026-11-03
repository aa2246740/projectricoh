from pathlib import Path
import json,os,subprocess,sys,time
E=Path(__file__).resolve().parent;root=E.parent
rows=[]
for script in ('ui_extra_r3.mjs','visual_check.mjs','focused_checks.py'):
 cmd=([sys.executable,'-B'] if script.endswith('.py') else ['node'])+[str(E/script)]
 start=time.perf_counter()
 with (E/f'{script}.log').open('w') as out:
  result=subprocess.run(cmd,env={**os.environ,'TMPDIR':str(root),'PYTHONDONTWRITEBYTECODE':'1'},stdout=out,stderr=subprocess.STDOUT,timeout=1800)
 row={'script':script,'exit_code':result.returncode,'seconds':round(time.perf_counter()-start,3)};rows.append(row)
 (E/'http-suite-remaining-r3.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(row),flush=True)
 if result.returncode:
  print((E/f'{script}.log').read_text()[-2800:],flush=True)
  raise SystemExit(result.returncode)
