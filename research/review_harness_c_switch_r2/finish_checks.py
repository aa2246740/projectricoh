"""Run the remaining review checks serially after the real regression batch exits."""
from pathlib import Path
import json,os,resource,subprocess,time

ROOT=Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
OUT=Path(__file__).resolve().parent

def main():
    jobs=[('prepare-original','prepare_original_replays.py',[]),
          ('original-identity','original_identity_args_r2.py',[]),
          ('original-event-entry','original_event_entry.py',[]),
          ('entry-controls','entry_controls.py',[]),
          ('event-constructor','entry/event_cases.py',[]),
          ('audit-warm','audit_warm.py',[]),
          ('mutation','mutation_control.py',[]),
          ('observations','audit_evidence.py',['observations']),
          ('real-comparison','audit_evidence.py',['real']),
          ('stored-comparison','audit_evidence.py',['stored'])]
    records=[]
    for label,script,args in jobs:
        command=['/usr/bin/sandbox-exec','-f',str(OUT/'fence.sb'),'/usr/bin/python3','-I','-B',str(OUT/script),*args]
        before=resource.getrusage(resource.RUSAGE_CHILDREN);started=time.monotonic()
        print(json.dumps({'event':'start','check':label}),flush=True)
        with (OUT/'evidence'/(label+'.log')).open('wb') as stream:
            result=subprocess.run(command,cwd=ROOT,env=dict(os.environ,TMPDIR='/Volumes/Workspace/Scratch/tmp/projectricoh/review-cswitch-r2'),stdout=stream,stderr=subprocess.STDOUT,timeout=10800)
        after=resource.getrusage(resource.RUSAGE_CHILDREN)
        row={'check':label,'returncode':result.returncode,'command':command,'wall_seconds':time.monotonic()-started,
             'cpu_seconds':after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,'nice':os.getpriority(os.PRIO_PROCESS,0),'timeout_seconds':10800}
        records.append(row);(OUT/'evidence/finish-progress.json').write_text(json.dumps(records,indent=2)+'\n')
        print(json.dumps(row),flush=True)
    (OUT/'evidence/finish-complete.json').write_text(json.dumps(records,indent=2)+'\n')

if __name__=='__main__':main()
