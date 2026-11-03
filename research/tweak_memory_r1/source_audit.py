"""List every source difference and verify the frozen parent tree."""
import difflib
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main():
    old, new = [ROOT/'firmware'/name for name in ('engine_v66_g155b', 'engine_v67_g155c')]
    def files(root):
        return {str(path.relative_to(root)):path for path in root.rglob('*')
            if path.is_file() and 'local' not in path.relative_to(root).parts and '__pycache__' not in path.parts}
    a, b = files(old), files(new)
    changes, patch = [], []
    for name in sorted(a.keys()|b.keys()):
        before = a[name].read_bytes() if name in a else b''
        after = b[name].read_bytes() if name in b else b''
        if before != after:
            changes.append(dict(path=name, old_sha256=hashlib.sha256(before).hexdigest(), new_sha256=hashlib.sha256(after).hexdigest()))
            patch.extend(difflib.unified_diff(before.decode().splitlines(True), after.decode().splitlines(True),
                fromfile='g155b/'+name, tofile='g155c/'+name))
    baseline = json.loads((HERE/'evidence/g155b-source-freeze.json').read_text())
    mismatches = [name for name, digest in baseline.items() if hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != digest]
    assert not mismatches
    result = dict(old_files=len(a), new_files=len(b), changed=changes, old_only=sorted(a.keys()-b.keys()),
        new_only=sorted(b.keys()-a.keys()), frozen_parent_files=len(baseline), parent_mismatches=mismatches,
        firmware_logic_changed=any(x['path'].endswith('boot_adapter.inc.c') for x in changes),
        release_boot_enabled=False, test_boot_enabled=True)
    (HERE/'evidence/source-differences.json').write_text(json.dumps(result, indent=2)+'\n')
    (HERE/'evidence/source-differences.patch').write_text(''.join(patch))
    print(json.dumps(result))


if __name__ == '__main__':
    main()
