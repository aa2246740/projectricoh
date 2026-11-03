#!/usr/bin/env python3
"""Create or verify separate source and private-output SHA256 manifests."""
import argparse
import hashlib
import importlib.util
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def files(private):
    result = []
    for path in HERE.rglob('*'):
        if path.is_symlink():
            raise RuntimeError('symlink in task output: '+str(path))
        if not path.is_file() or ('local' in path.relative_to(HERE).parts) != private:
            continue
        if path in (HERE/'SHA256SUMS', HERE/'local/SHA256SUMS'):
            continue
        result.append(path)
    return sorted(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location('pv_support', HERE/'support.py')
    s = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(s)
    s.preflight()
    for private in (False, True):
        paths = files(private)
        target = HERE/('local/SHA256SUMS' if private else 'SHA256SUMS')
        text = ''.join(f'{digest(p)}  {p.relative_to(HERE)}\n' for p in paths)
        if args.check:
            if target.read_text() != text:
                raise RuntimeError('manifest/content/file-set mismatch: '+str(target))
        else:
            target.write_text(text)
        print(('checked ' if args.check else 'wrote ')+str(len(paths))+' files: '+str(target.relative_to(HERE)))


if __name__ == '__main__':
    main()
