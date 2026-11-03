from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research/review_g135_gpt'
MANIFEST = OUT / 'SHA256SUMS'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


if '--verify-only' not in sys.argv:
    state = json.loads((OUT / 'evidence/scheduler.json').read_text())
    assert not state['active'], 'Verification groups still run'
    protected = json.loads((OUT / 'local/protected-before.json').read_text())
    for name, expected in protected.items():
        assert digest(ROOT / name) == expected
    paths = {path for path in OUT.rglob('*') if path.is_file() and path != MANIFEST}
    paths.update(ROOT / name for name in protected)
    paths.update((ROOT / 'research/knobs_v2_r2/src').glob('*.[ch]'))
    paths.update(ROOT / name for name in ['research/review_g135/SHA256SUMS', 'research/review_g135/runner.py', 'research/review_g135/r2_oracle.py', 'research/review_g135/ui_adapter.py', 'firmware/engine_v46_ui/user_entries.py', 'firmware/engine_v46_ui/candidate/ui_data.py'])
    plan = json.loads((OUT / 'queue.json').read_text())
    for job in plan['jobs']:
        paths.update(ROOT / arg for arg in job['args'] if arg.endswith('.py') and (ROOT / arg).is_file())
    lines = [digest(path) + '  ' + str(path.relative_to(ROOT)) for path in sorted(paths)]
    MANIFEST.write_text('\n'.join(lines) + '\n')

verified = 0
for row in MANIFEST.read_text().splitlines():
    expected, name = row.split('  ', 1)
    assert digest(ROOT / name) == expected, name
    verified += 1
print(json.dumps({'verified': verified, 'manifest_sha256': digest(MANIFEST)}))
