"""Inventory 83 pairs, extract only the owner-accepted M/C groups."""
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import argparse
import json
import traceback
import session_runtime as s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='extraction')
    ap.add_argument('--only', help='comma-separated stems, for a targeted fresh extraction')
    args = ap.parse_args()
    out = (s.LOCAL / args.out).resolve()
    assert out.is_relative_to(s.LOCAL) and not out.exists()
    a, chain, p = s.setup(out)
    from repair_mount_metadata import apply
    apply(a, chain)
    layout = json.loads((s.CHART / 'patches.json').read_text())
    pairs, inventory_errors = a.pair_inventory(s.CAPTURES)
    assert len(pairs) == 83 and not inventory_errors
    pairs = [v for v in pairs if int(v['frame'][1:]) % 10000 >= 1261]
    if args.only:
        pairs = [v for v in pairs if v['frame'] in args.only.split(',')]
    errors, frames = [], []
    for pair in pairs:
        n = int(pair['frame'][1:]) % 10000
        entry = {'unit': 'mount-a12' if 1261 <= n <= 1268 else 'a12-50'}
        if entry['unit'] == 'mount-a12':
            entry.update(slot='04', lens_note='owner reports 35mm f/2; exact physical lens ID unknown',
                         aperture_note='actual ring aperture unknown; requested f/5.6 is not confirmation')
        try:
            f = a.analyze_pair(pair, entry, layout, chain, out)
            f['evidence_kind'] = 'camera'
            s.dump(out / 'frames' / (pair['frame'] + '.json'), f)
            frames.append(f)
            print(f"{pair['frame']} {f['kind']} P{f['page']} valid={f['valid_patches']}/{len(f['patches'])}", flush=True)
        except Exception as exc:
            err = {'frame': pair['frame'], 'status': 'error', 'error': str(exc), 'traceback': traceback.format_exc()}
            s.dump(out / 'frames' / (pair['frame'] + '.json'), err)
            errors.append(err)
            print(f"{pair['frame']} ERROR {type(exc).__name__}: {exc}", flush=True)
    a.write_csv(out, frames)
    s.dump(out / 'extraction_summary.json', {'pairs': len(pairs), 'frames': len(frames), 'errors': errors})
    s.dump(out / 'provenance.json', p.finish())
    print(json.dumps({'frames': len(frames), 'errors': len(errors)}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
