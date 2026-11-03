"""Run unchanged gr_pairs extraction and flat-neighborhood averaging."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from core import ROOT, HERE, LOCAL, guard, read, load, pair_modules, dump
import argparse
import csv
import json
import numpy as np


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--frame', required=True)
    p.add_argument('--inventory', type=Path, required=True)
    a = p.parse_args()
    guard()
    f = next(f for f in read(a.inventory) if f['id'] == a.frame)
    _, extractor = pair_modules()
    # Exercise the established jpg=None route for all DNG-only pairs.
    if not f['standalone_jpeg']:
        f['provided_jpg'] = f['jpg']
        f['jpg'] = None
    extractor.extract(f, 60000)
    denoise = load('webpairs_denoise', ROOT / 'research/gr_pairs/denoise.py')
    denoise.augment(f)
    meta = read(LOCAL / 'samples' / (f['id'] + '.json'))
    counts = np.asarray(meta['coverage_h12_l5_c3'])
    with (HERE / ('coverage_' + f['id'] + '.csv')).open('w') as h:
        w = csv.writer(h)
        w.writerow(['frame', 'scene_hue_low_deg', 'scene_hue_high_deg', 'scene_L_bin',
                    'scene_C_bin', 'eligible_quad_count'])
        for hi in range(12):
            for li in range(5):
                for ci in range(3):
                    w.writerow([f['id'], 30 * hi, 30 * (hi + 1), li, ci, int(counts[hi, li, ci])])
    summary = dict(id=f['id'], group=f['group'], counts=meta['counts'],
                   registration=meta['registration'],
                   chromatic_150_270_eligible=int(counts[5:9, :, 1:].sum()),
                   chromatic_180_240_eligible=int(counts[6:8, :, 1:].sum()),
                   chromatic_150_270_by_hue=counts[5:9, :, 1:].sum(axis=(1, 2)),
                   radial_family='gr4_shared' if f['family'] == 'gr4' else 'gr3',
                   gr3x_radial_is_proxy=f['family'] == 'gr3x')
    dump(HERE / ('extraction_' + f['id'] + '.json'), summary)
    print(json.dumps({k: v for k, v in summary.items() if k != 'registration'}, default=lambda x: x.tolist()))


if __name__ == '__main__':
    main()
