"""Verify frozen inputs and generate or check this review's artifact manifest."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def frozen():
    initial = json.loads((HERE / 'local/inputs-before.json').read_text())
    checked, mismatches = 0, []
    for name, digest in initial['protected_files'].items():
        path = ROOT / name
        actual = sha(path) if path.is_file() else None
        checked += 1
        if actual != digest:
            mismatches.append({'path': name, 'expected': digest, 'actual': actual})
    added, deleted, changed_links = [], [], []
    for directory in initial['trees']:
        before = {name for name in initial['protected_files'] if name.startswith(directory + '/')}
        after = {str(path.relative_to(ROOT)) for path in (ROOT / directory).rglob('*')
                 if path.is_file() and not path.is_symlink()}
        added.extend(sorted(after - before))
        deleted.extend(sorted(before - after))
    for name, expected in initial['symlinks'].items():
        path = ROOT / name
        actual = str(path.readlink()) if path.is_symlink() else None
        if actual != expected:
            changed_links.append({'path': name, 'expected': expected, 'actual': actual})
    runtime = json.loads((HERE / 'local/runtime-inputs.json').read_text())['files']
    runtime_mismatches = []
    for row in runtime:
        path = ROOT / row['path']
        actual = sha(path) if path.is_file() else None
        if actual != row['sha256']:
            runtime_mismatches.append({'path': row['path'], 'expected': row['sha256'], 'actual': actual})
    result = {'checked_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'files': checked, 'unchanged': checked - len(mismatches), 'mismatches': mismatches,
              'added_tool_files': added, 'deleted_tool_files': deleted, 'changed_symlinks': changed_links,
              'runtime_inputs_checked': len(runtime), 'runtime_input_mismatches': runtime_mismatches,
              'passed': not any((mismatches, added, deleted, changed_links, runtime_mismatches))}
    (HERE / 'local/inputs-after.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result), flush=True)
    assert result['passed']


def create():
    rows = []
    for path in sorted(HERE.rglob('*')):
        if path.is_file() and path.name != 'SHA256SUMS':
            rows.append(sha(path) + '  ' + str(path.relative_to(ROOT)))
    (HERE / 'SHA256SUMS').write_text('\n'.join(rows) + '\n')
    print(json.dumps({'manifest_entries': len(rows)}), flush=True)


def verify():
    rows = (HERE / 'SHA256SUMS').read_text().splitlines()
    failures, listed = [], set()
    for row in rows:
        expected, name = row.split('  ', 1)
        path = ROOT / name
        listed.add(path)
        if not path.is_file() or sha(path) != expected:
            failures.append(name)
    present = {path for path in HERE.rglob('*') if path.is_file() and path.name != 'SHA256SUMS'}
    unlisted = sorted(str(path.relative_to(ROOT)) for path in present - listed)
    print(json.dumps({'total': len(rows), 'passed': len(rows) - len(failures),
                      'failures': failures, 'unlisted_files': unlisted}))
    assert not failures and not unlisted and len(listed) == len(rows)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('frozen', 'create', 'verify'))
    {'frozen': frozen, 'create': create, 'verify': verify}[parser.parse_args().command]()
