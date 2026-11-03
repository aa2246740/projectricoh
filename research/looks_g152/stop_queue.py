"""Stop only this task's named controller and its current test sessions."""
from pathlib import Path
import json,os,signal,subprocess,time
HERE=Path(__file__).resolve().parent
def census():
    result=[]
    for line in subprocess.check_output(['/bin/ps','-axo','pid=,ppid=,ni=,command='],text=True).splitlines():
        parts=line.strip().split(None,3)
        if len(parts)==4:result.append((int(parts[0]),int(parts[1]),int(parts[2]),parts[3]))
    return result
def main():
    rows=census();matches=[r for r in rows if 'Python.app/Contents/MacOS/Python' in r[3] and r[3].endswith('run_jobs.py queue-work-final.json')]
    assert len(matches)==1,matches
    parent=matches[0][0];children=[r for r in rows if r[1]==parent and str(HERE)+'/' in r[3]]
    assert 1<=len(children)<=2,children
    assert all(r[2]==10 and os.getsid(r[0])==r[0] for r in children),children
    os.kill(parent,signal.SIGTERM)
    for r in children:
        try:os.killpg(r[0],signal.SIGTERM)
        except ProcessLookupError:pass
    record=dict(status='INTERRUPTED',controller=parent,children=[dict(pid=r[0],command=r[3],nice=r[2]) for r in children],
                ended_ns=time.time_ns(),reason='The six-hour task limit requires the final focused queue and artifact cleanup. Unfinished tests are not passing results.')
    (HERE/'interrupted-final.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record))
if __name__=='__main__':main()
