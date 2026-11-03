"""Freeze r1 without changing it; reusable when rebuilding an empty r2 local/."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import json
import support as s


def main():
    s.guard()
    r1 = s.ROOT/'research/knobs_v2_r1'
    count = 0
    for line in (r1/'SHA256SUMS').read_text().splitlines():
        h, rel = line.split('  ', 1)
        p = (s.ROOT/rel).resolve()
        assert p.is_relative_to(s.ROOT) and s.sha(p) == h, 'r1 input mismatch: '+rel
        count += 1
    snapshot = {str(p.relative_to(s.ROOT)):s.sha(p) for p in sorted(r1.rglob('*')) if p.is_file()}
    dest = s.LOCAL/'r1_snapshot.json'
    if dest.exists():
        assert json.loads(dest.read_text()) == snapshot, 'r1 changed from initial snapshot'
    else:
        s.dump(dest, snapshot)
    print('PASS r1 original manifest:', count, 'checks;', len(snapshot), 'r1 files frozen')


if __name__ == '__main__':
    main()
