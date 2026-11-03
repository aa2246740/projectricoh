#!/usr/bin/env python3
"""Finite host-only reconstruction. No polling, devices, RPC transport or /tmp."""
import os
from pathlib import Path
import subprocess
import sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
env=dict(os.environ,TMPDIR=str(HERE/'local/tmp'),OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
subprocess.run([sys.executable,'-I','-B',str(HERE/'bootstrap.py')],cwd=ROOT,env=env,check=True)
(HERE/'local/tmp').mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(HERE))
import fit_round5 as fit
import verify_round5 as verify
import build_tables
import finalize
for slot in ('05','06'):
    fit.full(slot)
    for level in ('a','b','c','full24'):
        fit.crossvalidate(slot,level,'hue',55 if slot=='05' else 100)
    for level in ('a','b','c'):
        fit.crossvalidate(slot,level,'loo',55 if slot=='05' else 100)
    verify.audit(slot)
build_tables.main()
finalize.main()
