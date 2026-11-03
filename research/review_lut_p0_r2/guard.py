"""Read-only freeze; every write is confined to this independent review."""
from pathlib import Path
import hashlib
import json
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TREES = (
    'firmware/lut_p0_timing', 'firmware/engine_v35_publish',
    'firmware/engine_v36_r28', 'firmware/resident_v34c',
    'firmware/image_v34c', 'firmware/stage2k_p0',
    'research/review_lut_p0', 'research/review_publish_v114',
    'research/body_lut_r2',
)
BASELINE = HERE / 'protected-inputs.json'

def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()

def names():
    result = {str(p.relative_to(ROOT)) for tree in TREES
              for p in (ROOT / tree).rglob('*') if p.is_file()}
    if BASELINE.exists():
        result.update(json.loads(BASELINE.read_text()))
    else:
        # Existing official files and backup inputs already enumerated by r3.
        prior = ROOT / 'firmware/lut_p0_timing/local/protected-inputs-r3.json'
        result.update(json.loads(prior.read_text()))
        result.update(str(p.relative_to(ROOT)) for p in (ROOT / 'artifacts/firmware').rglob('*') if p.is_file())
    return sorted(n for n in result if Path(n).name != 'decisions.tsv'
                  and 'research/emulator_feasibility_r1/' not in n
                  and 'bridge_public_r1/' not in n)

def guard(init=False):
    current = {n: sha(ROOT / n) if (ROOT / n).is_file() else None for n in names()}
    if init:
        assert not BASELINE.exists(), 'never replace a freeze'
        assert all(current.values()), 'missing initial protected input'
        BASELINE.write_text(json.dumps(current, sort_keys=True, indent=2) + '\n')
    else:
        before = json.loads(BASELINE.read_text())
        changed = [n for n in sorted(before.keys() | current.keys()) if before.get(n) != current.get(n)]
        if changed:
            (HERE / 'STOP_FROZEN_INPUT_DRIFT.json').write_text(json.dumps(changed, indent=2) + '\n')
            raise SystemExit('STOP frozen protected input changed: ' + ', '.join(changed[:8]))
        (HERE / 'frozen-verification.json').write_text(json.dumps({'status': 'PASS', 'files': len(current)}, indent=2) + '\n')
    print(('FROZEN' if init else 'PASS frozen inputs') + ': ' + str(len(current)), flush=True)

if __name__ == '__main__':
    guard(sys.argv[1:] == ['--init'])
