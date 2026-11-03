#!/usr/bin/env python3
"""Hash only this task; never follows links or changes other workers' files."""
import hashlib
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
INDEX=HERE/'SHA256SUMS'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def files():
    return sorted(p for p in HERE.rglob('*') if p.is_file() and not p.is_symlink() and p!=INDEX
                  and 'tmp' not in p.relative_to(HERE).parts and '__pycache__' not in p.parts)
def main():
    if '--verify' in sys.argv:
        count=0
        for line in INDEX.read_text().splitlines():
            expected,name=line.split('  ',1);p=HERE/name;p.resolve().relative_to(HERE)
            if p.is_symlink() or digest(p)!=expected:raise SystemExit('HASH_MISMATCH '+name)
            count+=1
        print(f'HASHES_OK files={count}');return
    spec_path=HERE/'build.py'
    import importlib.util
    s=importlib.util.spec_from_file_location('checksum_preflight',spec_path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);m.preflight()
    selected=files();INDEX.write_text(''.join(f'{digest(p)}  {p.relative_to(HERE)}\n' for p in selected))
    print(f'HASHES_WRITTEN files={len(selected)}')
if __name__=='__main__':main()
