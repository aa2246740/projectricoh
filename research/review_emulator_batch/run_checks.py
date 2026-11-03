"""Foreground subprocess runner. Each emulator has nice 10 and an explicit wall-clock timeout."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / 'local'
TMP = '/Volumes/Workspace/Scratch/tmp/projectricoh/review-emulator-batch'
REVISION = ''


def execute(name, argv, timeout, impl=None):
    name += REVISION
    env = dict(os.environ, TMPDIR=TMP, PYTHONDONTWRITEBYTECODE='1',
               GXR_EMULATOR_BATCH='1' if impl == 'batch' else '0')
    if impl:
        env['REVIEW_IMPL'] = impl
    command = ['nice', '-n', '10', '/usr/bin/python3', '-I', '-B', *argv]
    started = time.monotonic()
    record = {'command': command, 'timeout_seconds': timeout, 'impl': impl}
    with (OUT / (name + '.log')).open('x') as stream:
        try:
            completed = subprocess.run(command, env=env, cwd=ROOT, stdout=stream,
                                       stderr=subprocess.STDOUT, timeout=timeout)
            record['returncode'] = completed.returncode
        except subprocess.TimeoutExpired:
            record.update(returncode=None, timed_out=True)
    record['seconds'] = time.monotonic() - started
    (OUT / (name + '-process.json')).write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record), flush=True)
    return record


def main():
    global REVISION
    parser = argparse.ArgumentParser()
    parser.add_argument('group', choices=['g146', 'state', 'm2b', 'probes', 'm2-options', 'checkpoints', 'hooks'])
    parser.add_argument('--revision', default='')
    args = parser.parse_args()
    REVISION = '-' + args.revision if args.revision else ''
    if args.group == 'g146':
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(execute, 'g146-' + impl,
                       [str(HERE / 'g146_replay.py'), 'final', impl], 10800, impl)
                       for impl in ['step', 'batch']]
            records = [f.result() for f in futures]
    elif args.group == 'state':
        records = [execute('state-' + impl, [str(HERE / 'state_compare.py'), impl], 3600, impl)
                   for impl in ['step', 'batch']]
    elif args.group == 'm2b':
        records = [execute('m2b', [str(HERE / 'm2b_run.py')], 7200, 'batch')]
    elif args.group == 'm2-options':
        records = [execute('m2-options-' + impl, [str(HERE / 'm2_options.py'), impl], 3600, impl)
                   for impl in ['step', 'batch']]
    elif args.group == 'checkpoints':
        records = [execute('checkpoints', [str(HERE / 'checkpoints.py')], 3600, 'batch')]
    elif args.group == 'hooks':
        records = [execute('hooks', [str(HERE / 'reproduce_hooks.py')], 3600)]
    else:
        records = [execute('probes-' + impl, [str(HERE / 'probes.py'), impl], 3600, impl)
                   for impl in ['step', 'batch']]
    if any(r['returncode'] != 0 for r in records):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
