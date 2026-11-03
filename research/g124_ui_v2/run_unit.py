"""Run one unit's native checks with a bounded owned process group and retained logs."""
from pathlib import Path
from datetime import datetime,timezone
import argparse
import json
import os
import signal
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *

def main():
    parser=argparse.ArgumentParser();parser.add_argument('unit',choices=('50mm','28mm','mount'))
    parser.add_argument('--groups',nargs='+')
    parser.add_argument('--label',default='')
    args=parser.parse_args()
    plans={
      'transitions':['ui_acceptance.py','transitions','--unit',args.unit],
      'values':['ui_acceptance.py','values','--unit',args.unit],
      'counterexamples':['run_cases.py','suite','--unit',args.unit],
      'safety':['safety_cases.py','--unit',args.unit],
      'locked':['locked_cases.py',args.unit],
      'nested':['lock_nested.py','--unit',args.unit,'--cuts','record_failure_return','after_update_restore','before_redraw','row_draw'],
      'cutpoints':['lock_cutpoints.py','--unit',args.unit,'--irq-enabled'],
      'views':['view_reentry.py','--unit',args.unit],
      'official-half':['official_half.py','--unit',args.unit,'--hook-trace'],
      'users':['user_acceptance.py','--unit',args.unit],
      'project-boundary':['project_boundary.py','--unit',args.unit],
      'labels':['label_acceptance.py','--unit',args.unit],
    }
    groups=args.groups or list(plans)
    pin=sha(DAT.read_bytes());records=[]
    deadline=datetime.fromisoformat(DEADLINE_UTC.replace('Z','+00:00'))
    for group in groups:
        seconds=int((deadline-datetime.now(timezone.utc)).total_seconds())-120
        if seconds<30:
            records.append(dict(group=group,status='INCOMPLETE_TIMEBOX'))
            break
        script=OUT/plans[group][0]
        if not script.exists():
            records.append(dict(group=group,status='MISSING_TOOL'))
            continue
        assert sha(DAT.read_bytes())==pin,'candidate changed during the acceptance run'
        argv=['/usr/bin/python3','-I','-B',str(script),*plans[group][1:]]
        log=OUT/'local'/(group+'-'+args.unit+'.log')
        temporary=OUT/'local/tmp';temporary.mkdir(exist_ok=True)
        environment=dict(os.environ,TMPDIR=str(temporary),PYTHONDONTWRITEBYTECODE='1')
        print('START',args.unit,group,flush=True)
        status='PASS'
        with log.open('w') as stream:
            process=subprocess.Popen(argv,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,
                                     env=environment,start_new_session=True)
            try:
                code=process.wait(timeout=seconds)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGTERM)
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid,signal.SIGKILL);process.wait()
                code=124;status='INCOMPLETE_TIMEBOX'
        if code and status=='PASS':status='FAIL'
        row=dict(unit=args.unit,group=group,status=status,returncode=code,argv=argv,
                 dat_sha256=pin,log=str(log.relative_to(ROOT)))
        records.append(row)
        with (OUT/'commands.jsonl').open('a') as stream:stream.write(json.dumps(row)+'\n')
        save('evidence/runner-'+args.unit+('-'+args.label if args.label else '')+'.json',dict(dat_sha256=pin,records=records))
        print('RESULT',args.unit,group,status,flush=True)
    assert all(row['status']=='PASS' for row in records),records

if __name__=='__main__':main()
