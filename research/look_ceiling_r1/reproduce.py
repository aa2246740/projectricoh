"""Bounded, low-priority reruns using the retained private datasets and control seeds."""
import argparse
import concurrent.futures
import json
import os
import plistlib
from pathlib import Path
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
LOCAL=HERE/'local'
PYTHON=ROOT/'studio/.venv/bin/python'

def run(script,*args):
    log=LOCAL/('rerun_'+script.removesuffix('.py')+'_'+('_'.join(args).replace('/','_').replace(':','-'))+'.log')
    env=os.environ.copy()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','VECLIB_MAXIMUM_THREADS','MKL_NUM_THREADS'):env[key]='1'
    command=['nice','-n','10',str(PYTHON),'-I','-B',str(HERE/script),*args]
    with log.open('w') as stream:
        result=subprocess.run(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT)
    if result.returncode:raise RuntimeError(f'{script} failed ({result.returncode}); see {log}')
    print('Completed',script,*args,flush=True)

def parallel(script,workers,*extra):
    partitions=((0,18),(18,36),(36,51))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures=[pool.submit(run,script,'--indices',f'{a}:{b}',*extra) for a,b in partitions]
        for future in concurrent.futures.as_completed(futures):future.result()

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mode',choices=('verify','refit'),default='verify')
    ap.add_argument('--workers',type=int,choices=(1,2,3),default=3)
    args=ap.parse_args()
    assert ROOT==Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
    subprocess.run(['df','-h','/Volumes/Workspace'],check=True)
    volume=plistlib.loads(subprocess.check_output(['diskutil','info','-plist','/Volumes/Workspace']))
    assert Path('/Volumes/Workspace').is_mount() and volume.get('FilesystemType')=='apfs'
    assert volume.get('DiskUUID',volume.get('VolumeUUID'))=='14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert volume.get('WritableVolume') and volume.get('WritableMedia')
    assert (LOCAL/'studio_source_snapshot.tar.gz').is_file(),'Private source snapshot is required'
    run('environment.py')
    if args.mode=='refit':
        stamp=time.strftime('%Y%m%dT%H%M%S',time.gmtime())
        previous=LOCAL/'previous_runs'/stamp;previous.mkdir(parents=True)
        # Preserve the bounded fits: they are the declared starting seeds, not held-out choices.
        for directory in ('fits','two_pass_full','two_pass_full_C','free_curves','published_axis','original_flog2'):
            origin=LOCAL/directory
            if not origin.exists():continue
            for path in sorted(origin.rglob('*')):
                if not path.is_file():continue
                if directory=='fits' and not (path.stem in ('L0','L1') or path.stem.endswith('_fullfields')):continue
                dest=previous/directory/path.relative_to(origin);dest.parent.mkdir(parents=True,exist_ok=True)
                path.rename(dest)
        # Recreate L0/L1, then the primary layers, with the same retained control starts.
        parallel('run.py',args.workers,'--keys','L0,L1')
        parallel('run.py',args.workers,'--full-fields')
        run('original_flog2.py','prepare')
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures=[pool.submit(run,'original_flog2.py','fit','--indices',p) for p in ('31:33','39:41','47:49')]
            for future in concurrent.futures.as_completed(futures):future.result()
        run('original_flog2.py','infinite')
        parallel('two_pass.py',args.workers,'--full-fields')
        run('two_pass.py','--check','--full-fields','--axis','C')
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures=[pool.submit(run,'two_pass.py','--indices',p,'--full-fields','--axis','C') for p in ('0:14','14:27','43:51')]
            for future in concurrent.futures.as_completed(futures):future.result()
        run('free_curves.py')
        run('published_axis.py')
        run('ablations.py');run('analyze.py');run('costs.py');run('target_diagnostics.py')
    run('error_modes.py')
    parallel('verify.py',args.workers)
    run('verify_auxiliary.py')
    run('original_flog2_verify.py')
    print('Verification complete. Temporary files remain in the named Scratch directory until seal.py --clean.',flush=True)

if __name__=='__main__':main()
