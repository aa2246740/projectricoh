"""Prepare the post-fix two-transaction contract without a cached-flag assumption."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import inspect
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
    parser.add_argument('--slot', type=int, choices=(4, 8), required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(HERE))
    spec = importlib.util.spec_from_file_location('g153_lifetime_source', SOURCE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.OUT = HERE
    (HERE / 'runtime/evidence').mkdir(parents=True, exist_ok=True)
    function = inspect.getsource(module.after_refusal)
    marker = "    assert cam.engine_bytes(H.LAYOUT['g.live_verified'],1)==b'\\1'\n"
    # A repaired transaction may discard this flag immediately on refusal.
    # The actual state and persistent uncertainty below are the contract.
    assert function.count(marker) == 1
    function = function.replace(marker, '')
    old = "    result['contract_pass']=matches['actual_prior'] or matches['target_05'] or (matches['stock_04'] and frame['failed'])"
    new = ("    result['uncertainty_after_reopen']=bool(cam.engine_bytes(H.LAYOUT['g.uncertain'],1)[0])\n"
           "    result['contract_pass']=matches['actual_prior'] or (frame['failed'] and result['uncertainty_after_reopen'])")
    assert function.count(old) == 1
    function = function.replace(old, new)
    executed_sha = hashlib.sha256(function.encode()).hexdigest()
    (HERE / 'evidence' / ('lifetime-source-' + executed_sha[:12] + '.py')).write_text(function)
    exec(compile(function, str(HERE / 'lifetime_cases.py') + ':contract', 'exec'), vars(module))
    label = f'lifetime-{args.slot}-{args.unit}'
    row = dict(case=label, source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
               executed_function_sha256=executed_sha, started_ns=time.time_ns())
    clock = time.monotonic()
    try:
        details = module.after_refusal(args.unit, args.slot)
        assert not details['S_stores']
        assert details['before']['S_sha256'] == details['after']['S_sha256'] == details['after_reopen']['S_sha256']
        assert [(call['op'], call['returned']) for call in details['calls']] == [(6, 0), (2, -2)]
        if not details['matches']['actual_prior']:
            assert details['frame']['failed'] and details['reopened_frame']['failed']
            assert details['uncertainty_after_reopen']
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
