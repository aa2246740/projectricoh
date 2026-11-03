"""ISO -> MakerNote ShotInfo byte 0x27 (the C+0x24 ISO code the units test against 11) over every available frame."""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent))
from drift_common import *
inv = load('drift_inv_src', 'research/color_calibration/analyze_capture.py')
safe_rationals(inv)
codes = {}
pats = ['captures/street-g137-20261031/jpg/*.JPG', 'captures/three-units-g137-20261031/*.JPG', 'captures/a12-50/*/*/*.JPG', 'captures/a12-50/*/*.JPG']
for pat in pats:
    for p in sorted(ROOT.glob(pat)):
        try:
            t = inv.jpeg_tiff(p); root = t.ifd(t.root); ex = t.ifd(root[34665]['value'][0])
            rec = t.ifd(ex[37500]['offset'] + 8, '>')[0x1001]['raw']
            iso = ex[34855]['value'][0]; c = rec[0x27]
            codes.setdefault(iso, {}).setdefault(c, 0); codes[iso][c] += 1
        except Exception as e:
            print('skip', p.name, repr(e))
codes = {k: codes[k] for k in sorted(codes)}
dump(LOCAL / 'iso_codes.json', codes); print(codes)
