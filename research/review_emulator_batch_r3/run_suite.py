"""Run review stages serially and wait for every foreground child."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REL = 'research/review_emulator_batch_r3/'
STAGES = {
    'short': [('static-audit', 1800, ['static_audit.py']),
              ('reproduce-hooks', 1800, ['reproduce_hooks.py']),
              ('forwarding-hooks', 1800, ['forwarding_hooks.py']),
              ('machine-forwarding', 1800, ['machine_forwarding.py']),
              ('extended-hooks', 1800, ['extended_hooks.py']),
              ('independent-hooks', 1800, ['independent_hooks.py']),
              ('hook-cases', 1800, ['hook_cases.py'])],
    'state': [('state-step', 7200, ['state_check.py', '--impl', 'step', '--name', 'state-step']),
              ('state-batch', 7200, ['state_check.py', '--impl', 'batch', '--name', 'state-batch'])],
    'm2b': [('m2b', 10800, ['m2b_run.py'])],
    'entry': [('entry-paths', 3600, ['entry_paths.py'])],
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=tuple(STAGES) + ('all',))
    args = parser.parse_args()
    stages = STAGES if args.stage == 'all' else {args.stage: STAGES[args.stage]}
    records = []
    for values in stages.values():
        for name, timeout, arguments in values:
            command = [sys.executable, '-I', '-B', str(HERE / 'run_check.py'),
                       '--timeout', str(timeout), name, REL + arguments[0], *arguments[1:]]
            process = subprocess.run(command, cwd=ROOT, timeout=timeout + 30, check=False)
            records.append({'name': name, 'returncode': process.returncode})
            (HERE / 'local' / ('suite-' + args.stage + '.json')).write_text(json.dumps(records, indent=2) + '\n')
            if process.returncode:
                raise SystemExit(process.returncode)


if __name__ == '__main__':
    main()
