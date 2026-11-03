from pathlib import Path
import json,os,subprocess,sys,time
E=Path(__file__).resolve().parent;R=E.parent
S=Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio')
rows=[]
cases=[('decode_without_exif','test_sized_export_keeps_portrait_orientation'),('stamp_floor_8','test_stamp_keeps_date_time_and_all_24_characters'),('stamp_floor_8','test_thumbnail_preview_and_export_keep_the_stamp_suffix')]
for i,(fault,test) in enumerate(cases):
 env={**os.environ,'TMPDIR':str(R),'PYTHONDONTWRITEBYTECODE':'1','PYTHONPATH':str(E)+os.pathsep+str(S/'src'),'R4_REINTRODUCE_FAULT':fault}
 env.pop('PYTEST_ADDOPTS',None)
 cmd=[sys.executable,'-B','-m','pytest','-q','-p','r4_fault_plugin',f'tests/test_finish.py::{test}',f'--basetemp={R}/sensitivity-{i}',f'--junitxml={E}/sensitivity-{i}.xml']
 start=time.monotonic()
 with (E/f'sensitivity-{i}.log').open('w') as out:p=subprocess.run(cmd,cwd=S,env=env,stdout=out,stderr=subprocess.STDOUT,timeout=1800)
 row={'fault':fault,'test':test,'exit_code':p.returncode,'expected_failure_detected':p.returncode==1,'seconds':round(time.monotonic()-start,3)}
 rows.append(row);(E/'test-sensitivity-r4.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(row),flush=True)
 if p.returncode!=1:raise SystemExit(2)
