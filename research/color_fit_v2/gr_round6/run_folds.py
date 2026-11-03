#!/usr/bin/env python3
"""Run one bounded, explicit batch of folds. No workers or background jobs."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse
import contextlib
import runtime as r
from fit import fit

ap=argparse.ArgumentParser()
ap.add_argument('slot');ap.add_argument('tier');ap.add_argument('folds')
ap.add_argument('--nfev',type=int,default=160)
args=ap.parse_args()
out=[]
for fold in args.folds.split(','):
    with (r.LOCAL/'tmp'/f'{args.slot}_{args.tier}_{fold}.log').open('w') as log, contextlib.redirect_stdout(log):
        f=fit(args.slot,args.tier,fold=fold,nfev=args.nfev)
    h=f['heldout']
    out.append(dict(fold=fold,seconds=round(f['seconds'],2),converged=f['solve']['success'],
                    error=round(h['stats']['median'] if 'stats' in h else h['200'],4)))
print(r.jsonable(out))
