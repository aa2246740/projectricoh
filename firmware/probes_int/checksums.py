#!/usr/bin/env python3
"""Hash this task's sources and private evidence; never follows symlinks."""
import argparse
import hashlib
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUMS = HERE / 'SHA256SUMS'


def digest(path):
    assert not path.is_symlink() and path.resolve().is_relative_to(HERE)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.check:
        rows = SUMS.read_text().splitlines()
        for row in rows:
            expected, name = row.split('  ', 1)
            assert digest(HERE / name) == expected, name
        print(f'PASS SHA256SUMS: {len(rows)} files')
        return
    entry = importlib.util.spec_from_file_location('pi_sum_support', HERE / 'support.py')
    support = importlib.util.module_from_spec(entry)
    entry.loader.exec_module(support)
    support.preflight()
    paths = [p for p in sorted(HERE.rglob('*')) if p.is_file() and p.name != 'SHA256SUMS'
             and not p.is_relative_to(HERE / 'local/tmp')]
    assert not any(p.is_symlink() for p in HERE.rglob('*'))
    SUMS.write_text(''.join(f'{digest(p)}  {p.relative_to(HERE).as_posix()}\n' for p in paths))
    print(f'Wrote SHA256SUMS: {len(paths)} files')


if __name__ == '__main__':
    main()
