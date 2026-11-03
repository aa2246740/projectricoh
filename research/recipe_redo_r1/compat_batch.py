"""Run bounded, independent g155c shared-record fits and confirmations."""
import argparse
import concurrent.futures
import datetime
import json
from pathlib import Path
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
PROFILES=[('a12-50',i) for i in (20,21,22,24,26)]+[('mount-a12',i) for i in (20,22,23,24,26)]


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--family',default='free')
    ap.add_argument('--range',required=True);ap.add_argument('--workers',type=int,choices=(1,2),default=2)
    args=ap.parse_args();lo,hi=map(int,args.range.split(':'));assert 0<=lo<hi<=10 and hi-lo<=6
    root=HERE/'local/compat_g155c'/args.family/f'batch_{lo:02d}_{hi:02d}';root.mkdir(exist_ok=False)
    started=time.monotonic()
    def one(item):
        unit,index=item;commands=[];before=time.monotonic()
        for phase,nfev in (('iterate',100),('confirm',500)):
            command=[sys.executable,'-I','-B',str(HERE/'compat_g155c.py'),phase,'--family',args.family,
                     '--unit',unit,'--index',str(index),'--nfev',str(nfev)]
            print('COMPAT START',args.family,unit,index,phase,flush=True)
            with (root/(unit+'_'+str(index)+'_'+phase+'.log')).open('w') as stream:
                result=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT,timeout=1500)
            commands.append(dict(command=command,exit_code=result.returncode))
            print('COMPAT FINISH',unit,index,phase,result.returncode,round(time.monotonic()-before,2),flush=True)
            if result.returncode:break
        return dict(unit=unit,index=index,commands=commands,passed=len(commands)==2 and all(x['exit_code']==0 for x in commands),elapsed_seconds=time.monotonic()-before)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        rows=list(pool.map(one,PROFILES[lo:hi]))
    receipt=dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),family=args.family,profiles=rows,
        workers=args.workers,actual_solver='exact TRF/SVD',elapsed_seconds=time.monotonic()-started,
        all_passed=all(r['passed'] for r in rows),no_DAT_built=True)
    (root/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    assert receipt['all_passed']


if __name__=='__main__':main()
