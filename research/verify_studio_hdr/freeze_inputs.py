"""Read-only input receipts for this HDR review."""
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
OUT = ROOT / 'research/review_studio_hdr'

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for part in iter(lambda: f.read(8 << 20), b''):
            h.update(part)
    return h.hexdigest()

def git(*args):
    return subprocess.check_output(['git', '--no-optional-locks', '-C', str(ROOT / 'studio'), *args])

def collect():
    entries = git('ls-files', '-z', '--cached', '--others', '--exclude-standard').split(b'\0')
    files = [ROOT / 'studio' / os.fsdecode(n) for n in entries if n]
    for rel in ['research/studio_hdr_r1', 'research/hdr_gainmap', 'captures/street-g137-20261031', 'captures/a12-50']:
        for base, dirs, names in os.walk(ROOT / rel, followlinks=False):
            dirs[:] = sorted(d for d in dirs if not (Path(base) / d).is_symlink())
            files.extend(Path(base) / n for n in sorted(names) if not (Path(base) / n).is_symlink())
    files += [ROOT / 'studio/.git/index', ROOT / 'studio/.git/HEAD']
    receipts = {}
    for p in sorted(set(files)):
        if p.is_file():
            receipts[str(p.relative_to(ROOT))] = {'bytes': p.stat().st_size, 'sha256': sha(p)}
    return {'utc': datetime.now(timezone.utc).isoformat(), 'head': git('rev-parse', 'HEAD').decode().strip(),
            'branch': git('branch', '--show-current').decode().strip(),
            'status': git('status', '--short', '--untracked-files=all').decode(), 'files': receipts}

def main():
    current = collect()
    if len(sys.argv) > 1 and sys.argv[1] == 'verify':
        frozen = json.loads((OUT / 'frozen_inputs.json').read_text())
        changed = sorted(n for n in set(frozen['files']) | set(current['files']) if frozen['files'].get(n) != current['files'].get(n))
        result = {'utc': current['utc'], 'files_checked': len(current['files']), 'changed': changed,
                  'head_equal': frozen['head'] == current['head'], 'status_equal': frozen['status'] == current['status']}
        (OUT / 'input_verification.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result))
        return int(bool(changed) or not result['head_equal'] or not result['status_equal'])
    lines = (ROOT / 'research/studio_hdr_r1/SHA256SUMS').read_text().splitlines()
    verified = []
    for line in lines:
        if not line.strip():
            continue
        expected, name = line.split(maxsplit=1)
        actual = sha(ROOT / name.lstrip('*'))
        verified.append({'path': name, 'expected': expected, 'actual': actual, 'equal': expected == actual})
    assert len(verified) == 25 and all(v['equal'] for v in verified)
    current['implementation_manifest'] = verified
    assert not (OUT / 'frozen_inputs.json').exists(), 'Do not replace the initial receipt'
    (OUT / 'frozen_inputs.json').write_text(json.dumps(current, indent=2, ensure_ascii=False) + '\n')
    diff = git('diff', '--no-ext-diff', '--binary')
    (OUT / 'source_diff_receipt.json').write_text(json.dumps({'bytes': len(diff), 'sha256': hashlib.sha256(diff).hexdigest()}, indent=2) + '\n')
    print(json.dumps({'head': current['head'], 'branch': current['branch'], 'files': len(current['files']), 'manifest_ok': 25}))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
