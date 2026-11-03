"""Run independent offline replay jobs with disjoint logs and decode caches."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import os
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from scope import *


def main():
    tmp=OUT/'local/tmp';tmp.mkdir(exist_ok=True)
    jobs=[]
    for unit in ('50mm','28mm','mount'):
        for error in (False,True):
            for kind in ('nested','loss'):
                jobs.append((f'{kind}-{unit}'+('-error' if error else ''),
                             ['cutpoints.py','--unit',unit,'--kind',kind]+(['--error'] if error else [])))
    for unit in ('50mm','28mm','mount'):
        jobs.append((f'h01-{unit}',['h01_cuts.py','--unit',unit]))
    for unit in ('50mm','28mm','mount'):
        jobs.append((f'variants-{unit}',['variants.py','--unit',unit]))
    for unit in ('50mm','28mm','mount'):
        jobs.append((f'functional-{unit}',['functional.py','--unit',unit]))
    environment=dict(os.environ,TMPDIR=str(tmp),PYTHONDONTWRITEBYTECODE='1',LC_ALL='C')
    def execute(job):
        label,args=job;argv=['/usr/bin/python3','-I','-B',str(OUT/args[0]),*args[1:]]
        with (OUT/'local'/(label+'.log')).open('w') as stream:
            result=subprocess.run(argv,cwd=ROOT,env=environment,stdout=stream,stderr=subprocess.STDOUT)
        return dict(job=label,argv=argv,returncode=result.returncode)
    results=[]
    with ThreadPoolExecutor(max_workers=3) as executor:
        pending={executor.submit(execute,job):job[0] for job in jobs}
        for future in as_completed(pending):
            record=future.result();results.append(record)
            save(OUT/'evidence/matrix-run.json',dict(status='RUNNING',jobs=results))
            print(record['job'],'PASS' if not record['returncode'] else 'FAIL',flush=True)
    save(OUT/'evidence/matrix-run.json',dict(status='PASS' if all(not r['returncode'] for r in results) else 'FAIL',jobs=results))
    assert all(not r['returncode'] for r in results),results


if __name__=='__main__':main()
