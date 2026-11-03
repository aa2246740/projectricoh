"""Reuse the review's two-transaction and unstable-snapshot contracts on g153."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import sys
import time
import traceback

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / 'research/review_g152/independent_cases.py'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--unit', choices=('50mm', 'mount'), required=True)
    parser.add_argument('--slot', type=int, choices=(4, 8), default=8)
    parser.add_argument('--unstable', choices=('T', 'rows'))
    args = parser.parse_args()
    sys.path.insert(0, str(HERE))
    spec = importlib.util.spec_from_file_location('g153_review_cases', SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.OUT = HERE
    (HERE / 'runtime/evidence').mkdir(parents=True, exist_ok=True)
    label = ('snapshot-race-' + args.unstable if args.unstable else 'cross-exit-' + str(args.slot)) + '-' + args.unit
    row = dict(case=label, source=str(SOURCE.relative_to(ROOT)),
               source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
               started_ns=time.time_ns())
    clock = time.monotonic()
    try:
        details = module.snapshot_race(args.unit, args.unstable) if args.unstable else module.after_refusal(args.unit, args.slot)
        if not args.unstable:
            assert not details['S_stores']
            assert details['before']['S_sha256'] == details['after']['S_sha256'] == details['after_reopen']['S_sha256']
            assert [(call['op'], call['returned']) for call in details['calls']] == [(6, 0), (2, -2)]
        row.update(status='PASS', details=details)
    except BaseException:
        row.update(status='FAIL', error=traceback.format_exc())
        raise
    finally:
        row.update(ended_ns=time.time_ns(), seconds=time.monotonic()-clock)
        (HERE / 'evidence' / (label + '.json')).write_text(json.dumps(row, indent=2) + '\n')
        print(json.dumps({key:value for key,value in row.items() if key!='details'}), flush=True)


if __name__ == '__main__':
    main()
