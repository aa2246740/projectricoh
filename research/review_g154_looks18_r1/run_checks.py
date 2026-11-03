"""Serial bounded native checks, preserve first failure and confirm it in Python."""
import argparse, json, os, subprocess, sys, time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common_review import *

def run(group,unit,backend):
    os.environ.pop('REVIEW_VOLUME_WITNESS',None)
    guard(False)
    args=['/usr/bin/nice','-n','10','/usr/bin/sandbox-exec','-f',str(HERE/'offline.sb'),'/usr/bin/python3','-I','-B',str(HERE/'native_review.py'),group,'--unit',unit]
    suffix='-baseline' if os.environ.get('REVIEW_DAT')=='baseline' else ''
    log=HERE/'evidence'/f'bounded-{group}-{unit}-{backend}{suffix}.log';started=time.monotonic()
    with log.open('wb') as output:
        try:
            p=subprocess.run(args,cwd=ROOT,stdout=output,stderr=subprocess.STDOUT,env=dict(os.environ,GXR_HARNESS_BACKEND=backend),timeout=10800)
            code=p.returncode;timed=False
        except subprocess.TimeoutExpired:code=124;timed=True
    receipt=dict(group=group,unit=unit,backend=backend,argv=args,dat_sha256=sha(dat(os.environ.get('REVIEW_DAT')=='baseline')),returncode=code,timed_out=timed,timeout_seconds=10800,seconds=time.monotonic()-started,log=str(log.relative_to(HERE)))
    receipt['dat_variant']='baseline' if suffix else 'looks18'
    save(f'evidence/job-{group}-{unit}-{backend}{suffix}.json',receipt)
    print(json.dumps(receipt),flush=True);return code

def main():
    p=argparse.ArgumentParser();p.add_argument('--groups',nargs='+',default=['navigation','cards','cap']);p.add_argument('--units',nargs='+',default=['50mm','28mm','mount']);p.add_argument('--backend',choices=['c','python'],default='c');a=p.parse_args()
    for group in a.groups:
        for unit in a.units:
            if run(group,unit,a.backend):
                if a.backend=='c':run(group,unit,'python')
                raise SystemExit(1)
    print('All selected checks passed',flush=True)

if __name__=='__main__':main()
