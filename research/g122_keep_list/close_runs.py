"""Stop only this task's foreground model groups at the timebox boundary."""
from pathlib import Path
import datetime
import os
import shlex
import signal
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import ROOT,OUT,DAT,file_sha,save

ALLOWED={'first_open.py','h01_view_change.py','run_native.py','fn2_all.py',
    'keep_cases.py','recovery_cases.py','field_cases.py','open_counts.py',
    'resident_entries.py','fn2_quality.py','run_final_extra.py','bounded_moves.py',
    'allocation_cases.py','notice_cases.py','boundary_cases.py','list_counts.py'}

def processes():
    result={}
    raw=subprocess.check_output(['/bin/ps','-ww','-axo','pid=,ppid=,pgid=,lstart=,command='],text=True)
    for line in raw.splitlines():
        parts=line.split(None,8)
        if len(parts)!=9:continue
        pid,parent,group=map(int,parts[:3])
        command=parts[8]
        try:args=shlex.split(command)
        except ValueError:continue
        script=None
        if '-I' in args and '-B' in args:
            at=args.index('-B')+1
            if at<len(args) and args[at].endswith('.py'):
                path=Path(args[at]);path=path if path.is_absolute() else ROOT/path
                if path.resolve().parent==OUT and path.name in ALLOWED:script=path.name
        result[pid]=dict(pid=pid,parent=parent,group=group,birth=' '.join(parts[3:8]),
            command=command,script=script)
    return result

def main():
    now=datetime.datetime.now(datetime.timezone.utc)
    assert now>=datetime.datetime.fromisoformat('2026-10-28T06:45:22+00:00'),now
    initial=processes();anchor=os.getppid();stopped=[]
    for row in initial.values():
        if not row['script'] or row['pid']!=row['group'] or row['parent']!=anchor:continue
        members=[p for p in initial.values() if p['group']==row['group']]
        assert all(p['script'] for p in members),members
        current=processes().get(row['pid'])
        if current!=row:continue
        method=signal.SIGINT if row['script']=='run_native.py' and ' matrix ' in row['command'] else signal.SIGTERM
        try:os.killpg(row['group'],method)
        except ProcessLookupError:continue
        stopped.append(dict(root=row,members=members,signal=method.name))
    save('timebox-stopped-runs.json',dict(dat_sha256=file_sha(DAT),
        status='INCOMPLETE_TIMEBOX',time=now.isoformat(),execution_parent=anchor,groups=stopped,
        scope='PID, parent, process group, birth string and full command are checked immediately before each signal. Other process groups are excluded.'))
    print('Stopped owned model groups',len(stopped),flush=True)

if __name__=='__main__':main()
