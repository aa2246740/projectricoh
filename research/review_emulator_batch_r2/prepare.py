"""Verify input identities, record read-only trees, and copy review entries."""
import difflib
import hashlib
import json
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from scope_guard import enable
enable()
TREES = ('tools/gxr_emulator', 'tools/gxr_emulator_batch', 'research/emulator_batch',
         'research/review_emulator_batch', 'research/emulator_speed', 'research/emulator_m2d',
         'research/unit28_stock', 'firmware')


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 << 20), b''):
            h.update(block)
    return h.hexdigest()


def main():
    started = time.monotonic()
    protected, checks, links = {}, {}, {}
    for directory, relative in [('research/emulator_batch', False),
                                ('tools/gxr_emulator', True),
                                ('research/emulator_speed', False),
                                ('research/review_emulator_batch', False)]:
        manifest = ROOT / directory / 'SHA256SUMS'
        rows = []
        for line in manifest.read_text().splitlines():
            expected, name = line.split('  ', 1)
            path = ROOT / directory / name if relative else ROOT / name
            key = str(path.relative_to(ROOT))
            actual = protected.setdefault(key, sha(path))
            rows.append({'path': key, 'expected': expected, 'actual': actual, 'ok': actual == expected})
        checks[directory] = {'total': len(rows), 'passed': sum(row['ok'] for row in rows),
                             'mismatches': [row for row in rows if not row['ok']]}
        print(json.dumps({'manifest': directory, **checks[directory]}), flush=True)
    if any(check['mismatches'] for check in checks.values()):
        (HERE / 'local/manifest-check.json').write_text(json.dumps(checks, indent=2) + '\n')
        raise SystemExit('input identity mismatch')
    for directory in TREES:
        count, total = 0, 0
        for path in sorted((ROOT / directory).rglob('*')):
            key = str(path.relative_to(ROOT))
            if path.is_symlink():
                links[key] = str(path.readlink())
            elif path.is_file():
                if key not in protected:
                    protected[key] = sha(path)
                count += 1
                total += path.stat().st_size
        print(json.dumps({'protected_tree': directory, 'files': count, 'bytes': total}), flush=True)
    record = {'manifests': checks, 'protected_files': protected, 'symlinks': links,
              'trees': TREES, 'seconds': time.monotonic() - started}
    (HERE / 'local/inputs-before.json').write_text(json.dumps(record, indent=2) + '\n')
    entries = [
        ('research/review_emulator_batch/reproduce_hooks.py', 'reproduce_hooks.py'),
        ('research/emulator_batch/hook_cases.py', 'hook_cases.py'),
        ('research/emulator_batch/output_cases.py', 'output_cases.py'),
        ('research/review_emulator_batch/state_compare.py', 'state_compare.py'),
        ('research/review_emulator_batch/m2b_run.py', 'm2b_run.py'),
    ]
    changes = []
    for source, target in entries:
        original = (ROOT / source).read_text()
        revised = original
        if target == 'm2b_run.py':
            revised = revised.replace('enable, admit_medium', 'enable')
            revised = revised.replace('admit_medium(sdcard)', 'import outputs\noutputs.declare_media(OUT)')
            revised = revised.replace("            module.HERE = HERE / 'local/conformance'\n            module.HERE.mkdir()",
                                      "            module.HERE = HERE / ('local/' + name)\n            module.HERE.mkdir()")
            revised = revised.replace("ROOT / 'research/emulator_m2d/regression.py'", "ROOT / 'research/emulator_batch/m2d_regression.py'")
        (HERE / target).write_text(revised)
        changes.append(''.join(difflib.unified_diff(original.splitlines(True), revised.splitlines(True),
                       fromfile=source, tofile=str((HERE / target).relative_to(ROOT)))))
    (HERE / 'local/entry-copies.diff').write_text(''.join(changes))
    print(json.dumps({'protected_files': len(protected), 'copied_entries': len(entries),
                      'seconds': time.monotonic() - started}), flush=True)


if __name__ == '__main__':
    main()
