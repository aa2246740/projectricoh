#!/usr/bin/env python3
"""Rebuild, predict, verify, and seal using only task-owned output directories."""
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import dense
common = dense.legacy()
import subprocess


def run(script, *args):
    subprocess.run([sys.executable, '-I', '-B', str(dense.HERE / script), *map(str, args)],
                   cwd=dense.ROOT, check=True)


if __name__ == '__main__':
    if not (dense.LOCAL / 'protected.json').exists():
        dense.snapshot()
    else:
        dense.preservation()
    run('inject.py', '--acceptance')
    for band in range(1, 5):
        run('inject.py', '--band', band)
    for number in range(1, 6):
        run('validate.py', '--predict', number)
        run('verify.py', '--card', number)
    run('instructions.py')
    run('coverage.py')
    run('report.py')
    run('verify.py', '--final', '--seal')
