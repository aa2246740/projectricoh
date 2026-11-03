"""Wait for the frozen dispatcher's active commands, then retire it."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import select
import shlex
import signal
import subprocess
import sys

HERE=Path(__file__).resolve().parent
OUT=HERE.parent
ROOT=OUT.parents[1]
meta=json.loads((HERE/'scope-stop.json').read_text())
children={r['pid']:r for r in meta['children']}
pending=set(children);finished={}

def now():return datetime.datetime.now(datetime.timezone.utc)
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def inspect(pid):
    raw=subprocess.run(['/bin/ps','-ww','-p',str(pid),'-o','pid=,lstart=,stat=,xstat=,command='],capture_output=True,text=True)
    row=raw.stdout.strip().split(None,8)
    if len(row)!=9:return None
    return dict(pid=int(row[0]),birth=' '.join(row[1:6]),stat=row[6],xstat=int(row[7],16),command=row[8])

queue=select.kqueue()
for pid in list(pending):
    row=inspect(pid)
    assert row and row['birth']==children[pid]['birth']
    assert row['command']==children[pid]['command'] or row['stat'].startswith('Z') and row['command']=='<defunct>'
    if row['stat'].startswith('Z'):
        finished[pid]=dict(raw_exit_status=row['xstat'],ended_utc=now().isoformat(),exit_source='ps xstat of naturally exited child',exit_time_observed=True)
        pending.remove(pid)
    else:
        queue.control([select.kevent(pid,filter=select.KQ_FILTER_PROC,flags=select.KQ_EV_ADD|select.KQ_EV_ONESHOT,fflags=select.KQ_NOTE_EXIT)],0,0)
while pending:
    events=queue.control(None,len(pending),30)
    for event in events:
        pid=event.ident
        assert pid in pending and not event.flags&select.KQ_EV_ERROR,(pid,event)
        finished[pid]=dict(raw_exit_status=event.data,ended_utc=now().isoformat(),exit_source='kqueue process-exit event',exit_time_observed=False)
        pending.remove(pid)
        print('NATURAL EXIT',pid,event.data,flush=True)
    if pending:print('WAIT active commands',sorted(pending),flush=True)
queue.close()
records=[]
for pid,child in children.items():
    args=shlex.split(child['command']);parts=args[args.index(str(HERE/'run_one.py'))+1:]
    unit=next(u for u in ('50mm','28mm','mount') if u in parts)
    path=HERE/('commands-'+unit+'.json');value=json.loads(path.read_text())
    index=len(value['commands'])+1
    label=unit+'-'+str(index).zfill(2)+'-'+'-'.join(parts).replace('.py','')
    log=HERE/'logs'/(label+'.log')
    raw=finished[pid]['raw_exit_status'];code=os.waitstatus_to_exitcode(raw)
    start=datetime.datetime.fromtimestamp(log.stat().st_birthtime,datetime.timezone.utc)
    end=datetime.datetime.fromisoformat(finished[pid]['ended_utc'])
    sources=value['commands'][-1]['source_sha256']
    stable=all(digest(ROOT/name)==sha for name,sha in sources.items())
    record=dict(command=parts,argv=['/usr/bin/python3','-I','-B',str(HERE/'run_one.py'),*parts],cwd=str(ROOT),
        returncode=code,seconds=(end-start).total_seconds(),started_utc=start.isoformat(),
        dat_sha256=digest(ROOT/'firmware/package_v36_g122/SD_ROOT/GXRCE.DAT'),source_sha256=sources,
        sources_unchanged=stable,log=str(log.relative_to(OUT)),log_sha256=digest(log),reused=False,
        receipt_recovered_after_scope_change=True,timing_source='Log creation to observed natural exit; exit observed after completion is an upper bound.',
        duration_is_upper_bound=finished[pid]['exit_time_observed'],
        source_check='All source hashes match the preceding command snapshot and the files at natural completion.',**finished[pid])
    value['commands'].append(record);value['status']='STOPPED_USER_SCOPE'
    path.write_text(json.dumps(value,indent=2)+'\n');records.append(record)
    assert code==0 and stable,(unit,code,stable)
parent=meta['parent'];row=inspect(parent['pid'])
assert row and row['birth']==parent['birth'] and row['command']==parent['command'] and 'T' in row['stat'],row
os.kill(parent['pid'],signal.SIGKILL)
meta.update(status='STOPPED_USER_SCOPE',finished_utc=now().isoformat(),active_command_results=records,
    dispatcher_retirement='SIGKILL to the identity-checked stopped dispatcher only, after all active commands exited naturally. No command received a stop or termination signal.')
(HERE/'scope-stop.json').write_text(json.dumps(meta,indent=2)+'\n')
print('PASS active commands finished; dispatcher retired; no further commands started',flush=True)
