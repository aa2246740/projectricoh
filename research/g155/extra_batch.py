"""最后的独立用例；每组前台结束，非 PASS 用 Python 确认。"""
from pathlib import Path
import json
import os
import subprocess
import time
import sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
JOBS=[
    ('retire-live-50mm','retire_live_tests.py',['--unit','50mm']),
    ('retire-live-mount','retire_live_tests.py',['--unit','mount']),
    ('builtin6-50mm','boot_tests.py',['--case','success','--kind','builtin','--number','6','--unit','50mm']),
    ('builtin6-28mm','boot_tests.py',['--case','success','--kind','builtin','--number','6','--unit','28mm']),
    ('t1-mount','t1_tests.py',[]),('repeat','repeat_tests.py',[]),('release-ui','release_ui_tests.py',[])]

def main():
    rows=[]
    for name,entry,args in JOBS:
        command=['/usr/bin/python3','-I','-B',HERE/'run.py','--name','extra-'+name,'research/g155/'+entry,*args]
        env=dict(os.environ,GXR_HARNESS_BACKEND='c');start=time.monotonic()
        p=subprocess.run(list(map(str,command)),cwd=ROOT,env=env,timeout=10800)
        row=dict(name=name,returncode=p.returncode,seconds=time.monotonic()-start);rows.append(row)
        if p.returncode:
            command[5]+='-python';env['GXR_HARNESS_BACKEND']='python'
            confirm=subprocess.run(list(map(str,command)),cwd=ROOT,env=env,timeout=10800)
            row['python_returncode']=confirm.returncode
        (HERE/'evidence/extra-batch.json').write_text(json.dumps(dict(jobs=rows,
            status='FAIL' if p.returncode else 'PASS' if len(rows)==len(JOBS) else 'RUNNING'),indent=2)+'\n')
        if p.returncode:return p.returncode
    return 0

if __name__=='__main__':sys.exit(main())
