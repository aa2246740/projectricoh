"""Task-local protected-input freeze. Run with python3 -I -B."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / 'local'
PROTECTED = ('firmware/resident_v34c', 'firmware/image_v34c',
             'firmware/engine_v35_publish', 'firmware/engine_v36_r28',
             'firmware/stage2k_p0', 'research/review_lut_p0',
             'research/review_publish_v114')


def snapshot():
    result = {}
    for directory in PROTECTED:
        for p in sorted((ROOT / directory).rglob('*')):
            if p.is_file() and p.name != 'decisions.tsv':
                result[str(p.relative_to(ROOT))] = digest(p)
    return result


def digest(p):
    with p.open('rb') as f:
        if hasattr(hashlib, 'file_digest'):
            return hashlib.file_digest(f, 'sha256').hexdigest()
        h = hashlib.sha256()
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
        return h.hexdigest()


def verify_existing(before):
    return [name for name, sha in before.items()
            if Path(name).name != 'decisions.tsv' and
            (not (ROOT/name).is_file() or digest(ROOT/name) != sha)]


def main():
    path = LOCAL / 'protected-inputs-r3.json'
    now = snapshot()
    if sys.argv[1:] == ['--init']:
        assert not path.exists(), 'never replace a freeze'
        old = json.loads((LOCAL/'protected-inputs.json').read_text())
        assert not verify_existing(old), 'STOP original frozen input changed'
        # Downloads are a shared, growing collection. Freeze existing inputs,
        # not other workers' new files. Never read their bridge cache.
        for p in (ROOT/'artifacts').rglob('*'):
            rel = p.relative_to(ROOT)
            if 'bridge_public_r1' in rel.parts or p.name == 'decisions.tsv':
                continue
            if p.is_file() and (rel.parts[1] in ('firmware', 'downloads') or
                                any('backup' in part.lower() for part in rel.parts)):
                now[str(rel)] = digest(p)
        LOCAL.mkdir(exist_ok=True)
        path.write_text(json.dumps(now, indent=2, sort_keys=True) + '\n')
        print('FROZEN files=' + str(len(now)))
    else:
        before = json.loads(path.read_text())
        changed = verify_existing(before)
        changed += [p for p in now if p not in before]
        if changed:
            (LOCAL / 'STOP_FROZEN_INPUT_DRIFT.json').write_text(json.dumps(changed, indent=2) + '\n')
            raise SystemExit('STOP frozen input drift: ' + ', '.join(changed[:8]))
        print('PASS protected inputs files=' + str(len(before)))


if __name__ == '__main__':
    main()
