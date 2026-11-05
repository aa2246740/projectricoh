"""Stop this finite acceptance queue and preserve its remaining plan for review."""
from pathlib import Path
import argparse,datetime,json,os,signal,subprocess,sys,time
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
p=argparse.ArgumentParser()
p.add_argument('--controller',type=int,required=True)
p.add_argument('--reason',required=True)
a=p.parse_args();C.setup()
plan=C.HERE/'jobs.json'
original=json.loads(plan.read_text())
progress=json.loads((C.LOCAL/'queue-progress.json').read_text())
receipt=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),reason=a.reason,
    controller=a.controller,pending=progress['pending'],running=progress['running'],signals=[])
C.save(C.LOCAL/'queue-plan-at-stop.json',original)
def processes():
    rows=[]
    for line in subprocess.check_output(['ps','-axo','pid=,ppid=,command='],text=True).splitlines():
        cols=line.strip().split(None,2)
        if len(cols)==3:rows.append((int(cols[0]),int(cols[1]),cols[2]))
    return rows
controllers=[row for row in processes() if row[0]==a.controller]
assert len(controllers)==1 and 'research/g158/queue.py' in controllers[0][2], 'controller identity changed'
# The running controller re-reads this list every five seconds. An empty list
# prevents further admissions while its existing children are terminated.
C.save(plan,[])
try:
    for attempt in range(15):
        rows=processes()
        children=[row for row in rows if row[1]==a.controller]
        for pid,parent,command in children:
            if command.startswith('(') and command.endswith(')'):continue
            assert 'research/g158/' in command, 'unowned queue child'
            how=signal.SIGTERM if attempt<6 else signal.SIGKILL
            try:os.kill(pid,how)
            except ProcessLookupError:continue
            receipt['signals'].append(dict(pid=pid,signal=how.name))
        if not any(row[0]==a.controller for row in rows):break
        time.sleep(1)
    else:raise RuntimeError('queue controller did not exit')
finally:
    receipt['finished_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    receipt['controller_exited']=not any(row[0]==a.controller for row in processes())
    C.save(C.LOCAL/'queue-closeout.json',receipt)
    # Restore the original rerunnable plan only after the controller is gone.
    if receipt['controller_exited']:C.save(plan,original)
assert receipt['controller_exited']
print(json.dumps(dict(status='STOPPED_FOR_HANDOFF',pending=len(receipt['pending']),
    running=list(receipt['running']),signals=receipt['signals'])))
