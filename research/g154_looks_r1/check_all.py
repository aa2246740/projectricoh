"""串行重跑本轮所选组；C 失败时保留回执并用 Python 后端确认。"""
from pathlib import Path
import argparse
import datetime
import os
import json
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import HERE, ROOT, TMP, guard


def jobs():
    yield 'data-c', ['data_checks.py']
    yield 'equality-c', ['verify.py', 'equality']
    for group, entry in (('navigation', 'verify.py'), ('cards', 'verify.py'), ('cap', 'cap_checks.py')):
        for unit in ('50mm', '28mm', 'mount'):
            arguments = [entry] + ([group] if entry == 'verify.py' else []) + ['--unit', unit]
            yield f'{group}-{unit}-c', arguments
    yield 'identity-c', ['identity_checks.py']
    yield 'sizes-c', ['size_checks.py']


def accepted_name(prefix, name):
    selection = json.loads((HERE / 'job-selection.json').read_text()).get(prefix, {})
    return selection.get(name, prefix + '-' + name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--prefix', default='rerun-' + datetime.datetime.now().strftime('%Y%m%dT%H%M%S'))
    parser.add_argument('--only', nargs='+', choices=[name for name, _ in jobs()])
    args = parser.parse_args()
    assert args.prefix and all(c.isalnum() or c in '-_' for c in args.prefix)
    guard()
    env = dict(os.environ, GXR_HARNESS_BACKEND='c', TMPDIR=str(TMP), PYTHONDONTWRITEBYTECODE='1')
    for name, arguments in jobs():
        if args.only and name not in args.only:
            continue
        entry = ['research/g154_looks_r1/' + arguments[0], *arguments[1:]]
        command = ['nice', '-n', '10', '/usr/bin/python3', '-I', '-B',
                   str(HERE / 'run.py'), '--name', args.prefix + '-' + name, '--timeout', '10800', *entry]
        result = subprocess.run(command, cwd=ROOT, env=env, timeout=10860)
        if result.returncode:
            command[command.index('--name') + 1] += '-python-confirm'
            confirmed = subprocess.run(command, cwd=ROOT, env=dict(env, GXR_HARNESS_BACKEND='python'), timeout=10860)
            print('C failure retained; Python confirmation exit:', confirmed.returncode, flush=True)
            return result.returncode
    return 0


if __name__ == '__main__':
    sys.exit(main())
