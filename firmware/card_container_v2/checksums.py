#!/usr/bin/env python3
"""Hash every task file, including ignored local evidence, without hashing self-list."""
import argparse
import importlib.util
from pathlib import Path

HERE=Path(__file__).resolve().parent
_s=importlib.util.spec_from_file_location('card2_pack',HERE/'pack.py')
pack=importlib.util.module_from_spec(_s); _s.loader.exec_module(pack)


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--check',action='store_true'); a=p.parse_args()
    pack.preflight(); target=HERE/'SHA256SUMS'
    if a.check:
        lines=target.read_text().splitlines()
        for line in lines:
            digest,name=line.split('  ',1); path=(HERE/name).resolve(); path.relative_to(HERE)
            if pack.sha(path.read_bytes())!=digest: raise ValueError('hash mismatch: '+name)
        print(f'PASS SHA256SUMS files={len(lines)}')
    else:
        files=[f for f in sorted(HERE.rglob('*')) if f.is_file() and f!=target]
        for f in files: f.resolve().relative_to(HERE)
        target.write_text(''.join(f'{pack.sha(f.read_bytes())}  {f.relative_to(HERE).as_posix()}\n' for f in files))
        print(f'WROTE SHA256SUMS files={len(files)}')


if __name__=='__main__': main()
