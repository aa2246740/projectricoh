"""Independent host-only review driver. All writes are in this directory."""
from pathlib import Path
import hashlib
import json
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PROTECTED = (
    'firmware/lut_p0_timing', 'firmware/engine_v35_publish',
    'firmware/resident_v34c', 'firmware/image_v34c',
    'firmware/stage2k_p0', 'artifacts/firmware', 'artifacts/downloads',
    'research/body_lut_r2', 'research/review_publish_v114',
)
EXCLUDED_LIVE = ('artifacts/downloads/bridge_public_r1/',)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def snapshot():
    baseline_file = HERE / 'protected-inputs.json'
    baseline = json.loads(baseline_file.read_text()) if baseline_file.exists() else None
    result = {}
    for directory in PROTECTED:
        # Downloads are shared. New unrelated downloads were never inputs to
        # this review. Keep every originally frozen download immutable, but
        # do not adopt concurrent additions into the input set.
        if directory == 'artifacts/downloads' and baseline is not None:
            paths = [ROOT / p for p in sorted(baseline) if p.startswith(directory + '/')]
        else:
            paths = sorted((ROOT / directory).rglob('*'))
        for p in paths:
            relative = str(p.relative_to(ROOT))
            if p.is_file() and p.name != 'decisions.tsv' and not relative.startswith(EXCLUDED_LIVE):
                result[relative] = digest(p)
    return result


def freeze(init=False):
    file = HERE / 'protected-inputs.json'
    now = snapshot()
    if init:
        assert not file.exists(), 'do not replace a freeze'
        file.write_text(json.dumps(now, sort_keys=True, indent=2) + '\n')
    else:
        before = {p: value for p, value in json.loads(file.read_text()).items()
                  if not p.startswith(EXCLUDED_LIVE)}
        changed = [p for p in sorted(before.keys() | now.keys())
                   if before.get(p) != now.get(p)]
        if changed:
            (HERE / 'STOP_FROZEN_INPUT_DRIFT.json').write_text(
                json.dumps(changed, indent=2) + '\n')
            raise SystemExit('STOP frozen input drift: ' + ', '.join(changed[:8]))
    print(('FROZEN' if init else 'PASS frozen inputs') + ' files=' + str(len(now)))


if __name__ == '__main__':
    freeze(sys.argv[1:] == ['--init'])
