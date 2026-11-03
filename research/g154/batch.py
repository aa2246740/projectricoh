"""同进程串行执行所选组，每组保留独立回执，失败即停。"""
from pathlib import Path
import argparse
import json
import runpy
import sys
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
JOBS=[('pending','pending_checks.py',[])]
for unit in ('50mm','mount','28mm'):
    JOBS.append(('cache-'+unit,'cache_checks.py',['--unit',unit]))
for unit in ('50mm','mount','28mm'):
    for group in ('navigation','cards'):
        JOBS.append((group+'-'+unit,'verify.py',[group,'--unit',unit]))
for group in ('busy','cross','exits','lifecycle','power','ownership'):
    for unit in (('50mm','mount') if group in ('busy','cross','exits') else ('50mm','mount','28mm')):
        JOBS.append((group+'-'+unit,'state_checks.py',[group,'--unit',unit]))
JOBS += [('cap-'+unit,'cap_checks.py',['--unit',unit]) for unit in ('50mm','mount')]
JOBS += [('knobs','knob_checks.py',[]),('mount-knobs','verify.py',['mount_knobs','--unit','mount']),
    ('pending-power','pending_power.py',[]),('identity','identity_checks.py',[])]


def main():
    p=argparse.ArgumentParser();p.add_argument('--tag',required=True);p.add_argument('--start',type=int,default=0)
    p.add_argument('--stop',type=int,default=len(JOBS));a=p.parse_args()
    assert 0<=a.start<a.stop<=len(JOBS)
    results=[];started=time.time_ns()
    for index in range(a.start,a.stop):
        name,script,arguments=JOBS[index];job=a.tag+'-'+name
        sys.argv=[str(HERE/'run.py'),'--name',job,'research/g154/'+script,*arguments]
        status=0
        try:runpy.run_path(str(HERE/'run.py'),run_name='__main__')
        except SystemExit as error:status=error.code
        results.append(dict(index=index,name=job,status=status))
        print('WAITED',index,job,status,flush=True)
        (HERE/'evidence'/('batch-'+a.tag+'.json')).write_text(json.dumps(dict(started_ns=started,
            updated_ns=time.time_ns(),start=a.start,stop=a.stop,jobs=results,status='PASS' if len(results)==a.stop-a.start and not status else 'RUNNING' if not status else 'FAIL'),indent=2)+'\n')
        if status:return status
    return 0


if __name__=='__main__':sys.exit(main())
