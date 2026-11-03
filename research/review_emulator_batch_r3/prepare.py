"""Freeze reviewed inputs and copy executable review entries into this directory."""
import datetime
import difflib
import hashlib
import json
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    started = time.monotonic()
    protected, checks, trees, links = {}, {}, {}, {}
    for directory, relative in [('research/emulator_batch', False), ('tools/gxr_emulator', True),
                                 ('research/emulator_speed', False),
                                 ('research/review_emulator_batch', False),
                                 ('research/review_emulator_batch_r2', False)]:
        manifest = ROOT / directory / 'SHA256SUMS'
        protected[str(manifest.relative_to(ROOT))] = sha(manifest)
        rows = []
        for line in manifest.read_text().splitlines():
            digest, name = line.split('  ', 1)
            path = (ROOT / directory / name) if relative else (ROOT / name)
            key = str(path.relative_to(ROOT))
            if path.is_file():
                actual = protected.setdefault(key, sha(path))
            else:
                actual = None
            rows.append({'path': key, 'expected': digest, 'actual': actual, 'ok': actual == digest})
        checks[directory] = {'total': len(rows), 'passed': sum(row['ok'] for row in rows),
                             'mismatches': [row for row in rows if not row['ok']]}
        print(json.dumps({'manifest': directory, **checks[directory]}), flush=True)
    # The tool directories include build products, sources and all existing files.
    for directory in ('tools/gxr_emulator', 'tools/gxr_emulator_batch'):
        count, size = 0, 0
        for path in sorted((ROOT / directory).rglob('*')):
            key = str(path.relative_to(ROOT))
            if path.is_symlink():
                links[key] = str(path.readlink())
            elif path.is_file():
                if key not in protected:
                    protected[key] = sha(path)
                count += 1
                size += path.stat().st_size
        trees[directory] = {'files': count, 'bytes': size}
    for path in (ROOT / 'firmware').rglob('*'):
        if path.is_file() and path.name == 'MAIN':
            protected[str(path.relative_to(ROOT))] = sha(path)
    record = {'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'manifests': checks, 'protected_files': protected, 'symlinks': links,
              'trees': trees, 'seconds': time.monotonic() - started}
    (HERE / 'local/inputs-before.json').write_text(json.dumps(record, indent=2) + '\n')
    if any(value['mismatches'] for value in checks.values()):
        raise SystemExit('manifest mismatch')
    changes, copies = [], []
    sources = [
        ('research/review_emulator_batch_r2/scope_guard.py', 'scope_guard.py'),
        ('research/review_emulator_batch_r2/extended_hooks.py', 'extended_hooks.py'),
        ('research/review_emulator_batch_r2/forwarding_hooks.py', 'forwarding_hooks.py'),
        ('research/review_emulator_batch_r2/machine_forwarding.py', 'machine_forwarding.py'),
        ('research/review_emulator_batch/reproduce_hooks.py', 'reproduce_hooks.py'),
        ('research/emulator_batch/hook_cases.py', 'hook_cases.py'),
        ('research/review_emulator_batch_r2/state_check.py', 'state_check.py'),
        ('research/review_emulator_batch_r2/m2b_run.py', 'm2b_run.py'),
    ]
    for source, name in sources:
        path = ROOT / source
        original = path.read_text()
        revised = original.replace('review-emulator-batch-r2', 'review-emulator-batch-r3') if name == 'scope_guard.py' else original
        (HERE / name).write_text(revised)
        copies.append({'source': source, 'sha256': sha(path), 'copy': str((HERE / name).relative_to(ROOT)),
                       'identical': original == revised})
        changes.append(''.join(difflib.unified_diff(original.splitlines(True), revised.splitlines(True),
                        fromfile=source, tofile=str((HERE / name).relative_to(ROOT)))))
    (HERE / 'local/entry-copies.diff').write_text(''.join(changes))
    (HERE / 'local/entry-copies.json').write_text(json.dumps(copies, indent=2) + '\n')
    print(json.dumps({'frozen_files': len(protected), 'trees': trees, 'copied': len(copies),
                      'seconds': time.monotonic() - started}), flush=True)


if __name__ == '__main__':
    main()
