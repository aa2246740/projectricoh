"""Record each foreground command, including failures, under the write fence."""
from pathlib import Path
import json
import os
import subprocess
import sys
import time
import signal
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import OUT,ROOT,save,file_sha

label=sys.argv[1];args=sys.argv[2:]
assert label.replace('-','').replace('_','').isalnum() and args
destination=OUT/'commands'/label
destination.mkdir(parents=True,exist_ok=False)
start=time.monotonic()
review_sources={q.name:file_sha(q) for q in sorted(OUT.glob("*.py"))}
with (destination/'stdout.txt').open('w') as stdout,(destination/'stderr.txt').open('w') as stderr:
    p=subprocess.Popen(args,cwd=ROOT,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',GIT_OPTIONAL_LOCKS='0'),stdout=subprocess.PIPE,stderr=stderr,text=True,start_new_session=True)
    save('commands/'+label+'/owner.json',dict(pid=p.pid,process_group=p.pid,started_utc=datetime.now(timezone.utc).isoformat(),argv=args,review_sources=review_sources))
    def end_window(signum,frame):
        os.killpg(p.pid,signal.SIGTERM)
    signal.signal(signal.SIGALRM,end_window)
    limit=datetime(2026,10,27,15,20,30,tzinfo=timezone.utc)
    signal.setitimer(signal.ITIMER_REAL,max(1,(limit-datetime.now(timezone.utc)).total_seconds()))
    for line in p.stdout:
        stdout.write(line);stdout.flush();print(line,end='',flush=True)
    result=p.wait()
    signal.setitimer(signal.ITIMER_REAL,0)
save('commands/'+label+'/command.json',dict(argv=args,cwd=str(ROOT),returncode=result,wall_seconds=time.monotonic()-start,review_sources=review_sources))
if result:print((destination/'stderr.txt').read_text(),file=sys.stderr)
raise SystemExit(result)
