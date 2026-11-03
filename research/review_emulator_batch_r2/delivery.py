"""Recheck read-only inputs, refresh entry diffs, and verify the delivery."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from scope_guard import enable, TMP
enable()
MANIFEST = HERE / 'SHA256SUMS'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 << 20), b''):
            h.update(block)
    return h.hexdigest()


def inputs():
    before = json.loads((HERE / 'local/inputs-before.json').read_text())
    differences = []
    for name, expected in before['protected_files'].items():
        path = ROOT / name
        actual = sha(path) if path.is_file() else None
        if actual != expected:
            differences.append({'path': name, 'expected': expected, 'actual': actual})
    current, links = set(), {}
    for directory in before['trees']:
        for path in (ROOT / directory).rglob('*'):
            key = str(path.relative_to(ROOT))
            if path.is_symlink():
                links[key] = str(path.readlink())
            elif path.is_file():
                current.add(key)
    added = sorted(current - before['protected_files'].keys())
    removed = sorted(before['protected_files'].keys() - current)
    result = {'protected_files': len(before['protected_files']), 'unchanged': len(before['protected_files']) - len(differences),
              'differences': differences, 'added': added, 'removed': removed,
              'symlinks_unchanged': links == before['symlinks']}
    (HERE / 'local/inputs-after.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result), flush=True)
    assert not differences and not added and not removed and result['symlinks_unchanged']


def refresh_diffs():
    changes = []
    for source, target in [
        ('research/review_emulator_batch/reproduce_hooks.py', 'reproduce_hooks.py'),
        ('research/emulator_batch/hook_cases.py', 'hook_cases.py'),
        ('research/emulator_batch/output_cases.py', 'output_cases.py'),
        ('research/review_emulator_batch/state_compare.py', 'state_compare.py'),
        ('research/review_emulator_batch/m2b_run.py', 'm2b_run.py')]:
        original, revised = (ROOT / source).read_text(), (HERE / target).read_text()
        changes.append(''.join(difflib.unified_diff(original.splitlines(True), revised.splitlines(True),
                       fromfile=source, tofile=str((HERE / target).relative_to(ROOT)))))
    (HERE / 'local/entry-copies.diff').write_text(''.join(changes))


def reviewed_inputs():
    before = json.loads((HERE / 'local/inputs-before.json').read_text())
    prefixes = ('tools/gxr_emulator/', 'tools/gxr_emulator_batch/', 'research/emulator_batch/',
                'research/review_emulator_batch/', 'research/emulator_speed/')
    selected = {name: digest for name, digest in before['protected_files'].items() if name.startswith(prefixes)}
    differences = []
    for name, expected in selected.items():
        path = ROOT / name
        actual = sha(path) if path.is_file() else None
        if actual != expected:
            differences.append({'path': name, 'expected': expected, 'actual': actual})
    current = {str(path.relative_to(ROOT)) for prefix in prefixes for path in (ROOT / prefix).rglob('*')
               if path.is_file() and not path.is_symlink()}
    added, removed = sorted(current - selected.keys()), sorted(selected.keys() - current)
    result = {'files': len(selected), 'unchanged': len(selected) - len(differences),
              'differences': differences, 'added': added, 'removed': removed}
    (HERE / 'local/reviewed-inputs-after.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result), flush=True)
    assert not differences and not added and not removed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('inputs', 'reviewed-inputs', 'seal', 'verify', 'cleanup', 'diffs'))
    args = parser.parse_args()
    if args.command == 'inputs':
        inputs()
    elif args.command == 'reviewed-inputs':
        reviewed_inputs()
    elif args.command == 'diffs':
        refresh_diffs()
    elif args.command == 'cleanup':
        if TMP.exists():
            shutil.rmtree(TMP)
        assert not TMP.exists()
        record = {'temporary_directory': str(TMP), 'removed': True}
        (HERE / 'local/cleanup.json').write_text(json.dumps(record, indent=2) + '\n')
        print(json.dumps(record))
    elif args.command == 'seal':
        paths = sorted(path for path in HERE.rglob('*') if path.is_file() and path != MANIFEST)
        MANIFEST.write_text(''.join(sha(path) + '  ' + str(path.relative_to(ROOT)) + '\n' for path in paths))
        print(json.dumps({'sealed_files': len(paths)}))
    else:
        rows = [line.split('  ', 1) for line in MANIFEST.read_text().splitlines()]
        differences = [name for expected, name in rows if sha(ROOT / name) != expected]
        listed = {name for _, name in rows}
        actual = {str(path.relative_to(ROOT)) for path in HERE.rglob('*') if path.is_file() and path != MANIFEST}
        print(json.dumps({'files': len(rows), 'passed': len(rows) - len(differences),
                          'differences': differences, 'unlisted': sorted(actual - listed),
                          'missing': sorted(listed - actual)}))
        assert not differences and actual == listed


if __name__ == '__main__':
    main()
