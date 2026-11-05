"""Drain the old coordinator without signalling its reference children."""
from pathlib import Path
import datetime,json,subprocess,sys
sys.path.insert(0,str(Path(__file__).resolve().parent));import common as C
C.setup();out=C.LOCAL/'accept-r2';transition=out/'loadgate-transition'
jobs=json.loads((out/'jobs.json').read_text())
progress=json.loads((out/'progress.json').read_text())
protected={'r2-reference-P1-test-AUTO':96752,'r2-reference-P1-release-AUTO':96753}
commands={}
for label,pid in protected.items():
    command=subprocess.run(['ps','-p',str(pid),'-o','args='],capture_output=True,text=True).stdout.strip()
    if command:assert label in command,(pid,command)
    else:assert json.loads((C.LOCAL/'runs'/label/'result.json').read_text())['status']=='OBSERVED'
    commands[label]=command
assert not (transition/'jobs-full.json').exists(),'transition already prepared'
C.save(transition/'jobs-full.json',jobs)
C.save(transition/'progress-before.json',progress)
C.save(transition/'start.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),old_queue_pid=10710,protected=protected,commands=commands,policy='Owner approved CPU idle and memory gate; no check content changes.',signals_sent=[],deadline='2026-11-05T08:03:27+00:00'))
active=set(progress['running'])|set(protected)
C.save(out/'jobs.json',[j for j in jobs if j['id'] in active])
print(json.dumps(dict(status='DRAINING',protected=protected,active=sorted(active),signals_sent=[])))
