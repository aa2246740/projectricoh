#!/usr/bin/env python3
"""Sequential foreground reproduction; no firmware outputs or shared writes.

Default: recompute dense checks and re-render all saved full/fold parameters.
--refit: first repeat all 228 fixed-design numerical fits from frozen inputs.
--report-only: rebuild statistical report from the already verified metrics.
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


if __name__=='__main__':
    if '--report-only' in sys.argv:
        run('realistic_finish.py','--report-only')
    else:
        for slot in ('01','02'):
            for kind in ('R0','R1','R2','R3','R4','R5'):
                if '--refit' in sys.argv:
                    for fold in [None,*range(18)]:
                        args=['fit','--slot',slot,'--kind',kind,'--nfev','80','--passes','2']
                        if fold is not None:args+=['--fold',fold]
                        run('realistic.py',*args)
                        stem='full' if fold is None else f'fold{fold:02d}'
                        path=HERE/'local/realistic'/f'{slot}_{kind}_{stem}.json'
                        if not json.loads(path.read_text())['history'][-1]['success']:
                            args[args.index('--nfev')+1]='180';args[args.index('--passes')+1]='0';args+=['--resume']
                            run('realistic.py',*args)
                        assert json.loads(path.read_text())['history'][-1]['success'],path
                run('realistic_evaluate.py','--slot',slot,'--kind',kind)
        run('realistic_finish.py')
    # Old stock04-node regression and private-file ignore check remain applicable.
    run('verify.py')
    import importlib.util
    spec=importlib.util.spec_from_file_location('gr_manifest',HERE/'finish.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.manifest()
