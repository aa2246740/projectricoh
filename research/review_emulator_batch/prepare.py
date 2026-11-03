"""Verify reviewed inputs and copy the unselected g146 entry into the review boundary."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / 'local'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def main():
    protected = {}
    checks = {}
    for directory, relative in [('research/emulator_batch', False),
                                ('tools/gxr_emulator', True),
                                ('research/emulator_speed', False)]:
        manifest = ROOT / directory / 'SHA256SUMS'
        rows = []
        for line in manifest.read_text().splitlines():
            digest, name = line.split('  ', 1)
            path = (ROOT / directory / name) if relative else ROOT / name
            actual = sha(path)
            rows.append({'path': str(path.relative_to(ROOT)), 'expected': digest,
                         'actual': actual, 'ok': actual == digest})
            protected[str(path.relative_to(ROOT))] = actual
        checks[directory] = {'total': len(rows), 'passed': sum(r['ok'] for r in rows),
                             'mismatches': [r for r in rows if not r['ok']]}
        protected[str(manifest.relative_to(ROOT))] = sha(manifest)
    for directory in ['tools/gxr_emulator', 'tools/gxr_emulator_batch', 'research/unit28_stock']:
        for path in (ROOT / directory).iterdir():
            if path.is_file():
                protected[str(path.relative_to(ROOT))] = sha(path)
    for row in json.loads((ROOT / 'tools/gxr_emulator/local/protected-inputs.json').read_text())['files']:
        path = ROOT / row['path']
        protected[row['path']] = sha(path)
    reference = ROOT / 'research/emulator_m2d/local/unit28-g146/final5'
    for path in reference.iterdir():
        if path.is_file():
            protected[str(path.relative_to(ROOT))] = sha(path)
    source = ROOT / 'research/unit28_stock/emu_g146_trace.py'
    original = source.read_text()
    revised = original
    edits = [
        ("BASE = ROOT / 'research/emulator_m2d/local/unit28-g146'",
         "BASE = HERE / 'local/g146'"),
        ("EMU = ROOT / 'tools/gxr_emulator'",
         "EMU = ROOT / ('tools/gxr_emulator' if os.environ['REVIEW_IMPL'] == 'step' else 'tools/gxr_emulator_batch')"),
        ("sys.path.insert(0, str(HERE))",
         "sys.path.insert(0, str(ROOT / 'research/unit28_stock'))\nsys.path.insert(0, str(HERE))\nfrom scope_guard import enable, admit_medium\nenable()\nimport sdcard\nadmit_medium(sdcard)"),
        ("assert Path(os.environ['TMPDIR']) == Path('/Volumes/Workspace/Scratch/tmp/projectricoh/unit28-r5')",
         "assert Path(os.environ['TMPDIR']) == Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-emulator-batch')"),
        ("        create(image)\n        result['placement'] = place(image, layout.blank(nonce))",
         "        # Review: both implementations start from the identical archived final5 medium.\n"
         "        import shutil\n"
         "        frozen = ROOT / 'research/emulator_m2d/local/unit28-g146/final5'\n"
         "        shutil.copyfile(frozen / 'card.img', image)\n"
         "        result['placement'] = json.loads((frozen / 'result.json').read_text())['placement']"),
    ]
    for before, after in edits:
        if revised.count(before) != 1:
            raise ValueError('copy edit anchor is not unique: ' + before)
        revised = revised.replace(before, after)
    (HERE / 'g146_replay.py').write_text(revised)
    (OUT / 'g146-entry.diff').write_text(''.join(difflib.unified_diff(
        original.splitlines(True), revised.splitlines(True),
        fromfile=str(source.relative_to(ROOT)), tofile='research/review_emulator_batch/g146_replay.py')))
    metadata = {'manifests': checks, 'protected_files': protected,
                'g146_source_sha256': sha(source), 'g146_reference': str(reference.relative_to(ROOT)),
                'g146_reference_status': json.loads((reference / 'result.json').read_text())['status'],
                'g146_input_sha256': sha(reference / 'card.img')}
    (OUT / 'inputs-before.json').write_text(json.dumps(metadata, indent=2) + '\n')
    print(json.dumps({k: {'passed': v['passed'], 'total': v['total']} for k,v in checks.items()}))
    if any(v['mismatches'] for v in checks.values()):
        raise SystemExit('input identity mismatch')


if __name__ == '__main__':
    main()
