from pathlib import Path
import os,subprocess,sys,time,json
root=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-v2-r3')
name=sys.argv[1]; cmd=sys.argv[2:]
env=os.environ.copy();env.update(TMPDIR=str(root),PYTHONDONTWRITEBYTECODE='1')
start=time.perf_counter()
try:
    with (root/'evidence'/f'{name}.log').open('w') as out:
        p=subprocess.run(cmd,stdout=out,stderr=subprocess.STDOUT,env=env,timeout=1800)
    data={'command':cmd,'exit_code':p.returncode,'seconds':round(time.perf_counter()-start,3)}
except subprocess.TimeoutExpired:
    data={'command':cmd,'exit_code':'TIMEOUT','seconds':round(time.perf_counter()-start,3)}
(root/'evidence'/f'{name}-run.json').write_text(json.dumps(data,indent=2)+'\n')
print(json.dumps(data));print((root/'evidence'/f'{name}.log').read_text()[-1800:])
sys.exit(0 if data['exit_code']==0 else 1)
