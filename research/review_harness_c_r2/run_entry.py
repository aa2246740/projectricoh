"""Run one foreground entry with a deadline and a process receipt."""
import contextlib
import json
import os
from pathlib import Path
import resource
import runpy
import signal
import sys
import time
import traceback
sys.path.insert(0, str(Path(__file__).resolve().parent))
from scope_guard import HERE, emit, enable, sha

enable()
timeout=float(sys.argv[1])
name=sys.argv[2]
entry=(HERE/sys.argv[3]).resolve()
arguments=sys.argv[4:]
started=time.monotonic()
record=dict(pid=os.getpid(), nice=os.getpriority(os.PRIO_PROCESS,0), timeout_seconds=timeout,
            entry=str(entry), entry_sha256=sha(entry), arguments=arguments,
            started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()))
emit(HERE/'local'/(name+'-started.json'),record)
def expired(signum, frame):
    raise TimeoutError('review entry deadline exceeded')
signal.signal(signal.SIGALRM,expired)
signal.setitimer(signal.ITIMER_REAL,timeout)
status=0
with (HERE/'local'/(name+'.log')).open('w',buffering=1) as output:
    with contextlib.redirect_stdout(output),contextlib.redirect_stderr(output):
        try:
            sys.argv=[str(entry)]+arguments
            runpy.run_path(str(entry),run_name='__main__')
        except SystemExit as error:
            status=error.code if type(error.code) is int else int(bool(error.code))
        except BaseException as error:
            status=1
            record['error']=dict(type=type(error).__name__,message=str(error))
            traceback.print_exc()
signal.setitimer(signal.ITIMER_REAL,0)
own=resource.getrusage(resource.RUSAGE_SELF)
children=resource.getrusage(resource.RUSAGE_CHILDREN)
record.update(completion_pid=os.getpid(),returncode=status,wall_seconds=time.monotonic()-started,
              own_cpu_seconds=own.ru_utime+own.ru_stime, child_cpu_seconds=children.ru_utime+children.ru_stime)
emit(HERE/'local'/(name+'-process.json'),record)
print(json.dumps(dict(name=name,returncode=status,wall_seconds=record['wall_seconds'])),flush=True)
raise SystemExit(status)
