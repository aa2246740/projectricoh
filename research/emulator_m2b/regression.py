#!/usr/bin/env python3
"""Run existing native checks without writing earlier research evidence."""
import argparse
import contextlib
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TOOLS = ROOT/'tools/gxr_emulator'
OUT = HERE/'local'
sys.path.insert(0, str(TOOLS))
import m2
m2.OUT = OUT
import conformance
import m2_checks
import rpc_check
from backend import Backend
from image import Image


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('name')
    args = parser.parse_args()
    if Path(args.name).name != args.name:
        parser.error('simple evidence name required')
    target = OUT/(args.name+'.json')
    if target.exists():
        parser.error('choose a fresh evidence name')
    seeds = ('baseline-task1', 'control-transport-stop',
             'unit-info-chunk-stop', 'startup-wait-stop')
    inputs = []
    for seed in seeds:
        for suffix in ('.pkl', '.json'):
            original = ROOT/'research/emulator_m2/local'/(seed+suffix)
            copy = OUT/(seed+suffix)
            if copy.exists():
                assert digest(original) == digest(copy), copy
            else:
                shutil.copyfile(original, copy)
            inputs.append({'path': copy.name, 'sha256': digest(copy)})
    rows = []
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        failures = conformance.check(Backend)
    rows.append({'case': 'gnu_native_conformance',
                 'status': 'FAIL' if failures else 'PASS',
                 'failures': failures, 'checks': stream.getvalue().splitlines()})
    for function in (m2_checks.native_cache, m2_checks.banked_snapshot,
                     m2_checks.native_tick, m2_checks.native_serial,
                     m2_checks.native_unit_info):
        try:
            row = function()
            row.pop('limits', None)
        except Exception as error:
            row = {'case': function.__name__, 'status': 'FAIL',
                   'error': type(error).__name__+': '+str(error)}
        rows.append(row)
    rpc = rpc_check.run()
    rpc.pop('limits', None)
    rows.append({'case': 'native_rpc_eight_cases', **rpc})
    result = {'status': 'PASS' if all(row['status'] == 'PASS' for row in rows) else 'FAIL',
              'scope': 'Native callable and checkpoint checks; separate from MAIN acceptance.',
              'official_sha256': Image().sha256,
              'library_sha256': digest(TOOLS/'build/libgxr_m32r.dylib'),
              'source_hashes': {p.name: digest(p) for p in TOOLS.glob('*.py')},
              'runner_sha256': digest(Path(__file__)), 'inputs': inputs, 'cases': rows}
    target.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'status': result['status'],
                      'cases': [{'case': r['case'], 'status': r['status'],
                                 'error': r.get('error')} for r in rows]}, indent=2))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
