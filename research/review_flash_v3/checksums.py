#!/usr/bin/env python3
"""Bind all review deliverables, including ignored evidence, except this list."""
import hashlib
import importlib.util
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('review',HERE/'review.py')
r=importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


def main():
    r.preflight()
    files=[]
    for p in sorted(HERE.rglob('*')):
        assert not p.is_symlink(),p
        if p.is_file() and p!=HERE/'SHA256SUMS':
            files.append(p)
    text=''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(HERE))+'\n' for p in files)
    if sys.argv[1:]==['--verify']:
        assert (HERE/'SHA256SUMS').read_text()==text,'review checksum list or members changed'
        print('SHA256SUMS_VERIFIED files=%d'%len(files))
    else:
        assert not sys.argv[1:]
        (HERE/'SHA256SUMS').write_text(text)
        print('SHA256SUMS_WRITTEN files=%d'%len(files))


if __name__=='__main__':
    main()
