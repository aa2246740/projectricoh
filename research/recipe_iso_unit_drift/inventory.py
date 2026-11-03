"""EXIF/MakerNote inventory of the 2026-10-31 g137 captures (read-only)."""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent))
from drift_common import *
ac = load('ac', 'research/color_calibration/analyze_capture.py')
safe_rationals(ac)

DIRS = ['captures/three-units-g137-20261031', 'captures/street-g137-20261031/jpg']


def row(p):
    t = ac.jpeg_tiff(p); s = ac.shot_info(t)
    root = t.ifd(t.root); ex = t.ifd(root[34665]['value'][0])
    g = lambda d, k: d.get(k, {}).get('value')
    return dict(file=p.name, dir=str(p.parent.relative_to(ROOT)), time=s['date_time'], iso=s['iso'],
                exp=s['exposure_seconds'], f=s['f_number'], focal=g(ex, 37386), focal35=g(ex, 41989),
                model=g(root, 272), lens=g(ex, 42036), expmode=g(ex, 34850), wb=g(ex, 41987),
                selector=s['profile_record_selector'], raw13=s['color_raw_13'], e2f=s['record_0x2f_unknown_enum'])


rows = []
for d in DIRS:
    for p in sorted((ROOT / d).glob('*.JPG')):
        try:
            rows.append(row(p))
        except Exception as e:
            rows.append(dict(file=p.name, dir=d, error=repr(e)))
dump(LOCAL / 'inventory.json', rows)
for r in rows:
    print(r['file'], r.get('time'), r.get('iso'), r.get('exp'), r.get('f'), r.get('focal'), r.get('model'), r.get('lens'), r.get('expmode'), r.get('wb'), r.get('selector'), r.get('raw13'), r.get('error', ''))
