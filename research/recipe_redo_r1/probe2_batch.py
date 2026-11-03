"""At most two independent, bounded MOUNT local-response fits."""
import argparse
import concurrent.futures
import datetime
import json
from pathlib import Path
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
OUT=HERE/'local/probe2_local_response'


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--indices',required=True);ap.add_argument('--tag',required=True)
    ap.add_argument('--workers',type=int,choices=(1,2),default=2);args=ap.parse_args()
    indices=list(map(int,args.indices.split(',')))
    assert len(set(indices))==len(indices) and 1<=len(indices)<=9 and all(0<=i<35 for i in indices)
    root=OUT/'batches'/args.tag;root.mkdir(parents=True,exist_ok=False);started=time.monotonic()
    def one(index):
        results=[];before=time.monotonic()
        for phase,nfev in (('iterate',100),('exact',500)):
            command=[sys.executable,'-I','-B',str(HERE/'probe2_refit.py'),phase,'--index',str(index),'--nfev',str(nfev)]
            print('PROBE2 START',index,phase,flush=True)
            with (root/f'{index:02d}_{phase}.log').open('w') as stream:
                result=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT,timeout=1500)
            results.append(dict(command=command,exit_code=result.returncode))
            print('PROBE2 FINISH',index,phase,result.returncode,round(time.monotonic()-before,2),flush=True)
            if result.returncode:break
        return dict(index=index,commands=results,passed=len(results)==2 and all(r['exit_code']==0 for r in results))
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:rows=list(pool.map(one,indices))
    receipt=dict(results=rows,workers=args.workers,actual_solver='TRF/SVD',elapsed_seconds=time.monotonic()-started,
        all_passed=all(r['passed'] for r in rows),created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    (root/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n');assert receipt['all_passed']


if __name__=='__main__':main()
