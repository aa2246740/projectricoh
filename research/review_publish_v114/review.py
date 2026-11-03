"""Independent, read-only input audit. All writes stay in this review directory."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PROTECTED = [
    'firmware/engine_v35_publish', 'firmware/resident_v34c',
    'firmware/image_v34c', 'firmware/stage2l_switch',
    'artifacts/firmware', 'artifacts/downloads', 'sources',
] + [str(p.relative_to(ROOT)) for p in sorted((ROOT/'artifacts').glob('card*'))]

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()

def inventory():
    files = {}
    for name in PROTECTED:
        p = ROOT/name
        if not p.exists():
            continue
        for f in ([p] if p.is_file() else sorted(p.rglob('*'))):
            if f.is_file() and f.name != 'decisions.tsv':
                files[str(f.relative_to(ROOT))] = sha(f)
    return files

def freeze():
    dest = HERE/'frozen.json'
    assert not dest.exists(), 'never replace the original freeze'
    files = inventory()
    dest.write_text(json.dumps(files, sort_keys=True, indent=2)+'\n')
    print('FROZEN', len(files), 'files')
    check()

def check():
    old = json.loads((HERE/'frozen.json').read_text())
    new = inventory()
    bad = [p for p in old.keys() | new.keys() if old.get(p) != new.get(p)]
    if bad:
        (HERE/'PROTECTED_DRIFT.json').write_text(json.dumps(bad, indent=2)+'\n')
        raise SystemExit('STOP_PROTECTED_INPUT_CHANGED '+repr(bad))
    for extra_file in HERE.glob('frozen-*.json'):
        extra = json.loads(extra_file.read_text())
        bad = [name for name,digest in extra.items() if not (ROOT/name).is_file() or sha(ROOT/name)!=digest]
        if bad:
            raise SystemExit('STOP_EXTRA_PROTECTED_INPUT_CHANGED '+repr(bad))
    print('PASS protected inventory and SHA256:', len(new))

def freeze_extra():
    dest=HERE/'frozen-extra.json'
    assert not dest.exists()
    files={}
    for name in ('artifacts/stage2l-switch-packages','artifacts/a12-50'):
        for f in sorted((ROOT/name).rglob('*')):
            if f.is_file() and f.name!='decisions.tsv':files[str(f.relative_to(ROOT))]=sha(f)
    dest.write_text(json.dumps(files,sort_keys=True,indent=2)+'\n')
    print('FROZEN extra recovery evidence',len(files),'files')

def freeze_carda():
    dest=HERE/'frozen-carda.json'
    assert not dest.exists()
    files={str(f.relative_to(ROOT)):sha(f) for f in sorted((ROOT/'artifacts/flash-v32').rglob('*'))
           if f.is_file() and f.name!='decisions.tsv'}
    dest.write_text(json.dumps(files,sort_keys=True,indent=2)+'\n')
    print('FROZEN card A historical backup evidence',len(files),'files')

def seal():
    check()
    files = sorted(p for p in HERE.rglob('*') if p.is_file() and p.name != 'SHA256SUMS')
    (HERE/'SHA256SUMS').write_text(''.join(sha(p)+'  '+str(p.relative_to(HERE))+'\n' for p in files))
    print('SEALED', len(files), 'review files')

if __name__ == '__main__':
    assert len(sys.argv) == 2 and sys.argv[1] in ('freeze', 'freeze_extra', 'freeze_carda', 'check', 'seal')
    globals()[sys.argv[1]]()
