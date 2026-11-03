#!/usr/bin/python3 -I -B
"""Reproduce the reviewed completeness failures against a selected checker."""
import argparse
import importlib.util
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--checker', required=True, type=Path)
    parser.add_argument('--result', required=True, type=Path)
    parser.add_argument('--complete-records', type=Path)
    args = parser.parse_args()
    assert args.result.resolve().is_relative_to(HERE)
    spec = importlib.util.spec_from_file_location('reviewed_gate', args.checker)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    review_path=ROOT/'research/review_v4_design_r2/record-variants.json'
    records = json.loads(review_path.read_text())
    variants=records['variants']
    base_stage=None
    if args.complete_records:
        import copy
        sys.path.insert(0,str(HERE))
        from record_cases import apply_review_variant
        base=json.loads(args.complete_records.read_text())
        base_stage=module.classify(base)['record_stage']
        assert base_stage=='records_complete_for_offline_review'
        variants=[dict(name=row['name'],input=apply_review_variant(copy.deepcopy(base),row['name']))
                  for row in variants[1:]]
    outcomes = []
    for case in variants:
        actual = module.classify(case['input'])
        outcomes.append(dict(name=case['name'], expected='undetermined',
                             input_sha256=hashlib.sha256(json.dumps(case['input'],sort_keys=True,
                                          separators=(',',':'),allow_nan=False).encode()+b'\n').hexdigest(),
                             actual=actual, passed=actual['record_stage']=='undetermined'))
    failed = [r['name'] for r in outcomes if not r['passed']]
    args.result.write_text(json.dumps(dict(checker=str(args.checker),
                                           checker_sha256=hashlib.sha256(args.checker.read_bytes()).hexdigest(),
                                           runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                                           reviewed_inputs_sha256=hashlib.sha256(review_path.read_bytes()).hexdigest(),
                                           complete_records_sha256=hashlib.sha256(args.complete_records.read_bytes()).hexdigest() if args.complete_records else None,
                                           base_stage=base_stage,
                                           cases=outcomes,
                                           failed_cases=failed), ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(dict(cases=len(outcomes), failures=len(failed), names=failed)))
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
