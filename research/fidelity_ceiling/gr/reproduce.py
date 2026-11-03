#!/usr/bin/env python3
"""Foreground-only reproduction from the existing frozen local inputs.

No network, no downloads, no camera/SD access, no shared-source entrypoints.
Individual stages and folds remain available through analyze.py/levers.py.
"""
import os
for _k in ('OPENBLAS_NUM_THREADS','VECLIB_MAXIMUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[_k]='1'
import sys
sys.dont_write_bytecode=True
from pathlib import Path
import subprocess
import json
HERE=Path(__file__).resolve().parent


def run(script,*args):
    subprocess.run([sys.executable,'-I','-B',str(HERE/script),*map(str,args)],check=True)


def fit(slot,kind,fold=None):
    stem='full' if fold is None else f'fold{fold:02d}'
    args=[kind,'--slot',slot,'--max-nfev','240']
    if fold is not None:args+=['--fold',str(fold)]
    run('levers.py',*args)
    result=HERE/'local'/f'{slot}_{kind}_{stem}.json'
    if not json.loads(result.read_text())['solver']['success']:
        # One bounded optimizer retry after a completed foreground solve.
        args[args.index('--max-nfev')+1]='500'
        run('levers.py',*args)
    assert json.loads(result.read_text())['solver']['success'],result


if __name__=='__main__':
    run('analyze.py','baseline')
    run('analyze.py','bw')
    for slot in ('01','02'):
        for kind in ('H24','Hshared','T1','T1_33','T3','T2','D48','D96'):fit(slot,kind)
        for fold in range(18):
            for kind in ('H24','Hshared','T1','T3','T2','D48'):fit(slot,kind,fold)
    run('diagnostics.py')
    for slot in ('01','02'):run('levers.py','3D','--slot',slot)
    run('bw_extra.py')
    run('finish.py')
    run('verify.py')
