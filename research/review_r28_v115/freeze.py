"""Review-owned freeze. Never writes any input or follows a device path."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PROTECTED = [
    'firmware/engine_v36_r28', 'firmware/engine_v35_publish',
    'firmware/resident_v34c', 'firmware/image_v34c',
    'research/r28_bank_design', 'research/review_publish_v114',
    'artifacts/firmware', 'artifacts/downloads/gxr-151.zip',
    'artifacts/downloads/gxr_vup', 'sources',
    'firmware/stage2l_switch', 'artifacts/stage2l-switch-packages',
    'artifacts/a12-50', 'artifacts/flash-v32',
] + [str(p.relative_to(ROOT)) for p in sorted((ROOT/'artifacts').glob('card*'))]

# The shared downloads directory is an active worker output area, not an input
# tree. Only the official Ricoh archive/extraction belongs in this review's
# protected scope. Keep the initial over-broad manifest as evidence.
OFFICIAL_DOWNLOADS = ('artifacts/downloads/gxr-151.zip', 'artifacts/downloads/gxr_vup/')

def in_scope(name):
    return not name.startswith('artifacts/downloads/') or any(
        name == prefix or name.startswith(prefix) for prefix in OFFICIAL_DOWNLOADS)

def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as stream:
        for part in iter(lambda: stream.read(1048576), b''):
            h.update(part)
    return h.hexdigest()

def inventory():
    result = {}
    for name in PROTECTED:
        p = ROOT/name
        if not p.exists():
            continue
        for f in ([p] if p.is_file() else sorted(p.rglob('*'))):
            name = str(f.relative_to(ROOT))
            if f.is_file() and f.name != 'decisions.tsv' and in_scope(name):
                result[name] = sha(f)
    return result

def freeze():
    dest = HERE/'frozen.json'
    assert not dest.exists(), 'do not replace a freeze'
    result = inventory()
    dest.write_text(json.dumps(result, sort_keys=True, indent=2)+'\n')
    print('FROZEN', len(result), 'files; decisions.tsv excluded')

def check():
    old = {p:h for p,h in json.loads((HERE/'frozen.json').read_text()).items() if in_scope(p)}
    now = inventory()
    bad = {p: {'before': old.get(p), 'after': now.get(p)}
           for p in old.keys() | now.keys() if old.get(p) != now.get(p)}
    if bad:
        report=HERE/'PROTECTED_DRIFT.json'
        if report.exists():report=HERE/('PROTECTED_DRIFT-'+sha(report)[:12]+'.json')
        report.write_text(json.dumps(bad, indent=2)+'\n')
        raise SystemExit('STOP_PROTECTED_INPUT_CHANGED '+repr(list(bad)))
    print('PASS frozen SHA256', len(now))

def seal():
    check()
    files = sorted(p for p in HERE.rglob('*') if p.is_file() and p.name != 'SHA256SUMS')
    (HERE/'SHA256SUMS').write_text(''.join(sha(p)+'  '+str(p.relative_to(HERE))+'\n' for p in files))
    print('SEALED', len(files))

if __name__ == '__main__':
    assert len(sys.argv) == 2 and sys.argv[1] in ('freeze', 'check', 'seal')
    globals()[sys.argv[1]]()
