#!/usr/bin/env python3
"""Generate or verify task-wide SHA256SUMS without any external writes."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from runtime import HERE, guard, sha

def main():
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
    guard();target=HERE/'SHA256SUMS'
    if a.check:
        lines=target.read_text().splitlines()
        for line in lines:
            expected,rel=line.split('  ',1);path=(HERE/rel).resolve();path.relative_to(HERE)
            assert sha(path)==expected,rel
        print(f'SHA256SUMS: {len(lines)} files verified')
    else:
        files=[p for p in sorted(HERE.rglob('*')) if p.is_file() and p!=target and '__pycache__' not in p.parts]
        target.write_text(''.join(f'{sha(p)}  {p.relative_to(HERE).as_posix()}\n' for p in files))
        print(f'SHA256SUMS: {len(files)} files recorded')

if __name__=='__main__':main()
