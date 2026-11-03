#!/usr/bin/env python3
"""Run sequential host checks and seal repository-relative hashes. No DAT build."""
import argparse
import ast
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import collect


def run(script, args, name):
    argv = ['/usr/bin/nice', '-n', '10', '/usr/bin/python3', '-I', '-B', str(HERE/script), *args]
    result = subprocess.run(argv, cwd=collect.ROOT, text=True, capture_output=True,
                            env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
    (collect.OUT/(name+'.stdout')).write_text(result.stdout)
    (collect.OUT/(name+'.stderr')).write_text(result.stderr)
    print(name, 'PASS' if result.returncode == 0 else 'FAIL', flush=True)
    assert result.returncode == 0, (name, result.stderr)
    return dict(argv=argv, exit_code=result.returncode,
                stdout='local/'+name+'.stdout', stderr='local/'+name+'.stderr')


def hashes():
    paths = sorted(p for p in HERE.rglob('*') if p.is_file() and p.name != 'SHA256SUMS'
                   and '__pycache__' not in p.parts)
    (HERE/'SHA256SUMS').write_text(''.join(
        collect.sha(p)+'  '+str(p.relative_to(collect.ROOT))+'\n' for p in paths))
    print('SHA256SUMS', len(paths), 'repository-relative files')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--full', action='store_true')
    ap.add_argument('--seal-only', action='store_true')
    a = ap.parse_args()
    assert not (a.full and a.seal_only)
    collect.preflight()
    if not a.seal_only:
        records = [run('collect.py', ['before'], 'protected-before')]
        if a.full:
            records.append(run('collect.py', ['windows'], 'collect'))
        records.append(run('evidence.py', [], 'evidence'))
        for name in ('replay', 'metadata_replay', 'bank_model'):
            records.append(run(name+'.py', [], name.replace('_','-')))
        for path in HERE.glob('*.py'):
            ast.parse(path.read_text(), filename=str(path))
        records.append(run('collect.py', ['after'], 'protected-after'))
        collect.save('verification-summary.json', dict(
            status='PASS_HOST_AND_BOUNDED_INSTRUCTIONS', commands=records,
            device_network_DAT='NOT_RUN',
            product_modification='NONE',
            limits='Host storage boundaries, synthetic schema and read-only source inspection only.'))
    hashes()


if __name__ == '__main__':
    main()
