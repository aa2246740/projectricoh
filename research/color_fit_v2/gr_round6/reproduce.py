#!/usr/bin/env python3
"""Finite sequential reproduction. No device access, background jobs or polling."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import contextlib
import runtime as r
import fit
import validate
import package
import finish
import verify


def main():
    r.common.mount_guard()
    for slot in ('01','02'):
        for tier in ('a','b','c'):
            for fold in [None]+[f'h{i}' for i in range(6)]+[f'l{i}' for i in range(18)]:
                label='full' if fold is None else fold
                with (r.LOCAL/'tmp'/f'reproduce_{slot}_{tier}_{label}.log').open('w') as log,contextlib.redirect_stdout(log):
                    f=fit.fit(slot,tier,fold=fold,nfev=160)
                if fold is None:
                    v=validate.check(r.Inputs(slot),f['quantized'])
                    r.dump(r.LOCAL/'validation'/f'{slot}_{tier}_+0.0.json',v)
                print(f'{slot} {tier} {label}',flush=True)
        for tier in ('a','b','c'):
            f=fit.fit(slot,tier,ev=-.3,nfev=160)
            if tier=='c':
                v=validate.check(r.Inputs(slot,-.3),f['quantized'])
                r.dump(r.LOCAL/'validation'/f'{slot}_c_-0.3.json',v)
    package.assemble()
    for order in ('roundtrips','standard','repeat'):package.host(order)
    finish.finish();verify.run();finish.finish();verify.run();verify.checksums()


if __name__=='__main__':main()
