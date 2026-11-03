from pathlib import Path
import argparse
import json
import sys

OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(OUT))
from check_stored import compare, read


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    source = next((OUT / 'busy/python/tests/local').rglob('50mm-busy-settings-exit.json'))
    reference = read(source)['detail']
    reference.pop('native_UI_audit')
    candidate = read(OUT / 'busy-diagnostic/summary.json')['c_detail']
    count, differences = compare(reference, candidate)
    proof = {'equal': not differences, 'compared_values': count, 'differences': differences,
             'scope': 'Persisted JSON values; original in-memory tuple/list comparison is retained in summary.json'}
    if args.write:
        (OUT / 'busy-diagnostic/comparison.json').write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps(proof))
    return 0 if proof['equal'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
