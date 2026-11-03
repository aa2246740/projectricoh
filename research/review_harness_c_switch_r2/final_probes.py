"""Serial final checks, including a fresh-name repeat of the resume counterexample."""
from pathlib import Path
import json,os,resource,subprocess,time
ROOT=Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
OUT=Path(__file__).resolve().parent

def main():
    jobs=[('equal-labels','audit_evidence.py',['labels'],0),
          ('before-five','audit_evidence.py',['before'],0),
          ('event-entry-variant','event_entry_variant.py',[],0),
          ('subprocess-fresh-repeat','replay_subprocess_identity.py',['--tag','final-repeat'],1),
          ('controls-and-errors','verify_controls_and_errors.py',[],0)]
    rows=[]
    for name,script,args,expected in jobs:
        command=['/usr/bin/sandbox-exec','-f',str(OUT/'fence.sb'),'/usr/bin/python3','-I','-B',str(OUT/script),*args]
        started=time.monotonic();before=resource.getrusage(resource.RUSAGE_CHILDREN)
        print(json.dumps({'event':'start','check':name}),flush=True)
        with (OUT/'evidence'/(name+'.log')).open('wb') as stream:
            result=subprocess.run(command,cwd=ROOT,env=dict(os.environ,TMPDIR='/Volumes/Workspace/Scratch/tmp/projectricoh/review-cswitch-r2'),stdout=stream,stderr=subprocess.STDOUT,timeout=10800)
        after=resource.getrusage(resource.RUSAGE_CHILDREN)
        row={'check':name,'returncode':result.returncode,'expected_for_review':expected,'as_expected':result.returncode==expected,
             'command':command,'wall_seconds':time.monotonic()-started,'cpu_seconds':after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,
             'nice':os.getpriority(os.PRIO_PROCESS,0),'timeout_seconds':10800}
        rows.append(row);(OUT/'evidence/final-probes-progress.json').write_text(json.dumps(rows,indent=2)+'\n')
        print(json.dumps(row),flush=True)
    (OUT/'evidence/final-probes-complete.json').write_text(json.dumps(rows,indent=2)+'\n')

if __name__=='__main__':main()
