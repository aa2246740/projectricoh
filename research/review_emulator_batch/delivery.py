"""Recheck protected inputs and seal or verify the review artifacts."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'SHA256SUMS'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['inputs', 'seal', 'verify'])
    args = parser.parse_args()
    if args.command == 'inputs':
        before = json.loads((HERE / 'local/inputs-before.json').read_text())['protected_files']
        differences = []
        for name, expected in before.items():
            actual = sha(ROOT / name)
            if actual != expected:
                differences.append({'path': name, 'expected': expected, 'actual': actual})
        result = {'protected_files': len(before), 'unchanged': len(before) - len(differences),
                  'differences': differences}
        (HERE / 'local/inputs-after.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result))
        assert not differences
    elif args.command == 'seal':
        files = sorted(path for path in HERE.rglob('*') if path.is_file() and path != MANIFEST
                       and '__pycache__' not in path.parts)
        MANIFEST.write_text(''.join(sha(path) + '  ' + str(path.relative_to(ROOT)) + '\n' for path in files))
        print(json.dumps({'sealed_files': len(files)}))
    else:
        rows = [line.split('  ', 1) for line in MANIFEST.read_text().splitlines()]
        differences = [name for expected, name in rows if sha(ROOT / name) != expected]
        print(json.dumps({'files': len(rows), 'passed': len(rows) - len(differences), 'differences': differences}))
        assert not differences


if __name__ == '__main__':
    main()
