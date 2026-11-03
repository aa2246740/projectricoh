"""Run one foreground command and retain stdout, stderr, argv and exit status."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
label=sys.argv[1];argv=sys.argv[2:]
assert label.replace('-','').replace('_','').isalnum() and argv
out=HERE/'local/commands'/label
out.mkdir(parents=True,exist_ok=False)
start=time.monotonic()
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',GIT_OPTIONAL_LOCKS='0')
(out/'native_ux.py').write_bytes((HERE/'native_ux.py').read_bytes())
with (out/'stdout.txt').open('w') as stdout, (out/'stderr.txt').open('w') as stderr:
    p=subprocess.Popen(argv,cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=stderr,text=True)
    for line in p.stdout:
        stdout.write(line);stdout.flush();print(line,end='',flush=True)
    rc=p.wait()
result=dict(argv=argv,cwd=str(ROOT),returncode=rc,host_wall_seconds=time.monotonic()-start)
(out/'command.json').write_text(json.dumps(result,indent=2)+'\n')
if rc:print((out/'stderr.txt').read_text(),file=sys.stderr)
raise SystemExit(rc)
