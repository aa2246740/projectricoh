"""Run one nice-priority foreground check with a generous wall-clock limit."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from scope_guard import enable
enable()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('name')
    parser.add_argument('--timeout', type=int, default=7200)
    parser.add_argument('arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    arguments = args.arguments[1:] if args.arguments[:1] == ['--'] else args.arguments
    command = ['nice', '-n', '10', '/usr/bin/python3', '-I', '-B', *arguments]
    started = time.monotonic()
    result = {'command': command, 'timeout_seconds': args.timeout, 'cwd': str(ROOT)}
    env = dict(os.environ, TMPDIR='/Volumes/Workspace/Scratch/tmp/projectricoh/review-emulator-batch-r2',
               PYTHONDONTWRITEBYTECODE='1', GXR_EMULATOR_BATCH='0')
    with (HERE / 'local' / (args.name + '.log')).open('w') as log:
        try:
            process = subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                                     timeout=args.timeout, check=False)
            result['returncode'] = process.returncode
        except subprocess.TimeoutExpired:
            result['returncode'], result['timed_out'] = 124, True
    result['seconds'] = time.monotonic() - started
    (HERE / 'local' / (args.name + '-process.json')).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result), flush=True)
    raise SystemExit(result['returncode'])


if __name__ == '__main__':
    main()
