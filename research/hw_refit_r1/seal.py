"""Seal every file except the manifest itself; verify exact membership and hashes."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
import json


def main():
    combined = {}
    sources = sorted(p for p in rt.LOCAL.rglob('*.json') if p.parent.name == 'inputs')
    for path in sources:
        doc = json.loads(path.read_text())
        for key, value in doc.get('sha256', {}).items():
            assert key not in combined or combined[key] == value, 'inconsistent frozen input: ' + key
            combined[key] = value
    changed = [key for key, value in combined.items() if rt.sha(rt.ROOT / key) != value]
    rt.dump('verification/final_inputs.json', dict(files=len(combined), manifests=len(sources),
                                                 changed=changed, all_inputs_unchanged=not changed))
    assert not changed, changed
    manifest = rt.HERE / 'SHA256SUMS'
    files = sorted(p for p in rt.HERE.rglob('*') if p.is_file() and p != manifest)
    assert not any(p.is_symlink() for p in files)
    assert not any('__pycache__' in p.parts for p in files)
    lines = [rt.sha(p) + '  ' + str(p.relative_to(rt.HERE)) for p in files]
    manifest.write_text('\n'.join(lines) + '\n')
    entries = [line.split('  ', 1) for line in manifest.read_text().splitlines()]
    assert len(entries) == len(files)
    for digest, relative in entries:
        assert rt.sha(rt.HERE / relative) == digest, relative
    current = sorted(str(p.relative_to(rt.HERE)) for p in rt.HERE.rglob('*') if p.is_file() and p != manifest)
    assert current == [name for _, name in entries], 'manifest membership mismatch'
    print(json.dumps(dict(sha256_files=len(entries), manifest_covers_all_other_files=True,
                          all_ok=True, frozen_inputs=len(combined), frozen_inputs_unchanged=True)), flush=True)


if __name__ == '__main__':
    main()
