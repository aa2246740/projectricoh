#!/usr/bin/env python3
"""Seal delivery files after all calculations. Each sums file excludes itself."""
import hashlib
from pathlib import Path

HERE=Path(__file__).resolve().parent
LOCAL=HERE/'local'


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1<<20),b''):h.update(chunk)
    return h.hexdigest()


def seal(base,public=False):
    dest=base/'SHA256SUMS'
    files=sorted(p for p in base.rglob('*') if p.is_file() and p!=dest
                 and (not public or not p.is_relative_to(LOCAL)))
    assert all(not p.is_symlink() for p in files)
    title='research/gr4_bench' if public else 'research/gr4_bench/local'
    rows=[f'# Base directory: repository-root/{title}; SHA256SUMS itself excluded.']
    rows.extend(f'{sha(p)}  {p.relative_to(base)}' for p in files)
    dest.write_text('\n'.join(rows)+'\n')
    print(title,len(files),'files')


if __name__=='__main__':
    import sys
    sys.path.insert(0,str(HERE))
    import benchlib as b
    b.mount_guard()
    # Check integrity before resealing, so sealing cannot silently approve changed inputs.
    import json
    for name,expected in json.loads((LOCAL/'input_ledger.json').read_text()).items():
        assert sha(HERE.parents[1]/name)==expected,f'Input changed before seal: {name}'
    seal(LOCAL)
    seal(HERE,True)
