"""One controller lease, retained by each test child through its lifetime."""
from contextlib import contextmanager
from pathlib import Path
import fcntl,json,os,subprocess,time
HERE=Path(__file__).resolve().parent
LEASE=HERE/'local/controller.lease'

def workers(scripts):
    found=[]
    for line in subprocess.check_output(['/bin/ps','-axo','pid=,ppid=,ni=,command='],text=True).splitlines():
        p=line.strip().split(None,3)
        if len(p)!=4:continue
        if any(str(HERE/name) in p[3] for name in scripts):
            found.append(dict(pid=int(p[0]),parent=int(p[1]),nice=int(p[2]),command=p[3]))
    return found

@contextmanager
def controller_lease(jobs):
    LEASE.parent.mkdir(exist_ok=True)
    handle=LEASE.open('a+')
    try:
        try:fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise RuntimeError('CONTROLLER_BUSY: the prior controller or a test child still holds the lease.')
        scripts={j['script'] for j in jobs}
        for path in HERE.glob('queue-*.json'):
            data=json.loads(path.read_text())
            if isinstance(data,list):scripts.update(j['script'] for j in data if isinstance(j,dict) and 'script' in j)
        active=workers(scripts)
        if active:raise RuntimeError('WORKERS_PRESENT: '+json.dumps(active))
        handle.seek(0);handle.truncate()
        handle.write(json.dumps(dict(controller=os.getpid(),started_ns=time.time_ns()))+'\n');handle.flush()
        yield handle.fileno()
    finally:handle.close()
