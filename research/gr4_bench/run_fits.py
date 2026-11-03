#!/usr/bin/env python3
"""Deterministic foreground batches. No workers, sleeps, polling, or background jobs."""
import argparse
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent


def tasks(stage):
    if stage=='gr':
        # Default first, without inspecting any result.
        scenarios=[('common_white',0.),('common_white',-.3),('common_white',.3),
                   ('per_camera',-.3),('per_camera',0.),('per_camera',.3)]
        for bridge,ev in scenarios:
            for slot in ('01','02'):
                for variant in ('B','C'):
                    for kind,fold in [('full',None)]+[('spatial',i) for i in range(4)]:
                        yield ['--slot',slot,'--variant',variant,'--kind',kind,
                               '--bridge',bridge,'--ev',str(ev)]+([] if fold is None else ['--fold',str(fold)])
    else:
        for slot in ('01','02'):
            for variant in ('B','C'):
                for index in range(18):
                    yield ['--slot',slot,'--variant',variant,'--kind','chartloo','--fold',str(index)]


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--stage',choices=('gr','chartloo'),required=True)
    p.add_argument('--batch',type=int,required=True)
    p.add_argument('--size',type=int,default=8)
    a=p.parse_args()
    assert 1<=a.size<=8 and a.batch>=0
    all_tasks=list(tasks(a.stage))
    batch=all_tasks[a.batch*a.size:(a.batch+1)*a.size]
    assert batch, 'Batch exceeds fixed task list'
    for args in batch:
        subprocess.run(['python3','-I','-B',str(HERE/'fit.py'),*args],check=True,cwd=HERE.parents[1])
    print(f'{a.stage} batch {a.batch}: {len(batch)} completed; total tasks {len(all_tasks)}')
