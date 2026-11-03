"""Average only prevalidated flat neighborhoods; retain original quad samples."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, LOCAL, read, dump, guard, modules
from extract import raw_frame, camera_jpeg, feature
import argparse
import json
import numpy as np
from scipy.ndimage import uniform_filter


def augment(frame):
    p = LOCAL / 'samples' / (frame['id'] + '.npz')
    with np.load(p, allow_pickle=False) as z:
        d = dict(z)
    if 'uc_quad' in d:
        print(frame['id'], 'flat mean cache already present', flush=True)
        return
    raw, md = raw_frame(frame)
    jpg, _, _ = camera_jpeg(frame)
    wb = raw['rgb'] / np.asarray(md['tags']['50728'], np.float32) * 2 ** md['tags'].get('50730', [0])[0]
    hh, ww = wb.shape[:2]
    yy, xx = np.mgrid[:hh, :ww]
    r2 = (((yy - (hh - 1) / 2) ** 2 + (xx - (ww - 1) / 2) ** 2) / ((hh / 2) ** 2 + (ww / 2) ** 2)).astype(np.float32)
    radial = read(ROOT / 'research/gr4_modes/local/tone_curves.json')['radial']
    coef = radial['gr4_coef_natural_log' if frame['family'] == 'gr4' else 'gr3_coef_natural_log']
    gain = np.exp(-sum(c * r2 ** (i + 1) for i, c in enumerate(coef)))
    sx, sy = d['xy'].T
    uc = np.column_stack([uniform_filter(wb[..., c] * gain, 5)[sy, sx] for c in range(3)])
    jpeg = np.column_stack([uniform_filter(jpg[..., c], 5)[sy, sx] for c in range(3)])
    d.update(uc_quad=d['uc'], features_quad=d['features'], jpeg_quad=d['jpeg'], lab_quad=d['lab'],
             uc=uc.astype(np.float32), features=feature(uc).astype(np.float32),
             jpeg=jpeg.astype(np.float32), lab=modules()[1].rgb_lab(jpeg / 255).astype(np.float32))
    np.savez_compressed(p, **d)
    meta = read(p.with_suffix('.json'))
    meta['model_observation'] = '5x5 mean of 2x2 CFA quads and their own JPEG means, solely inside eroded flat masks; originals retained as *_quad'
    dump(p.with_suffix('.json'), meta)
    print(json.dumps({'frame': frame['id'], 'mean_samples': len(uc)}), flush=True)


def main():
    guard()
    p = argparse.ArgumentParser()
    p.add_argument('--frame', action='append')
    a = p.parse_args()
    for f in read(LOCAL / 'inventory.json'):
        if not a.frame or f['id'] in a.frame:
            augment(f)


if __name__ == '__main__':
    main()
