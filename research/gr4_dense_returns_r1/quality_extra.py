#!/usr/bin/env python3
"""Check ROI periodic modulation and two-pixel sampling sensitivity on actual returns."""
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
import argparse
from scipy.ndimage import map_coordinates


def run(band):
    m = rt.model()
    rb, a, _ = rt.readback_modules()
    _, card = rb.cards('gr4')[f'dense-band-{band}']
    record = rt.read(rt.RETURNS / f'dense-band-{band}-partial-analysis.json')
    result = dict(band=band, criterion='moire diagnostic: strongest detrended non-DC Fourier amplitude >6 RGB codes',
                  moire_threshold_codes=6, target_change=False, modes={})
    for mode, state in record['modes'].items():
        image = a.load_jpeg(state['path'])
        pixels = np.asarray(image, np.float32)
        h = np.array(state['alignment']['homography'])
        peaks, shifts = [], []
        for p in card['patches']:
            if p['role'] != 'colour':
                continue
            x1, y1, x2, y2 = p['roi']
            yy, xx = np.mgrid[y1+.5:y2:1., x1+.5:x2:1.]
            xy = a.project(h, np.c_[xx.ravel(), yy.ravel()])
            values = np.stack([map_coordinates(pixels[..., c], [xy[:, 1], xy[:, 0]],
                order=1, output=np.float64) for c in range(3)], axis=-1)
            hh, ww = xx.shape
            plane = np.c_[np.ones(len(values)), xx.ravel()-xx.mean(), yy.ravel()-yy.mean()]
            residual = values-plane@np.linalg.lstsq(plane, values, rcond=None)[0]
            ft = np.fft.rfft2(residual.reshape(hh, ww, 3), axes=(0, 1))
            ft[0, 0] = 0
            peaks.append(float(2*abs(ft).max()/len(values)))
            shifted = []
            for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
                xy2 = a.project(h, np.c_[xx.ravel()+dx, yy.ravel()+dy])
                shifted.append([map_coordinates(pixels[..., c], [xy2[:, 1], xy2[:, 0]],
                    order=1, output=np.float64).mean() for c in range(3)])
            centre = m.fs.lab_from_codes(values.mean(axis=0))
            shifts.append(float(m.fs.delta_e00(m.fs.lab_from_codes(np.array(shifted)), centre).max()))
        result['modes'][mode] = dict(colour_patches=len(peaks),
            detrended_peak_amplitude_codes=rt.stats(peaks), moire_flags=int((np.array(peaks) > 6).sum()),
            shift2px_max_de00=rt.stats(shifts),
            limit='this measures patch-centre modulation; it does not prove all image borders are free of aliasing')
    rt.dump(f'target/quality_extra_band{band}.json', result)
    print(band, [(k, v['moire_flags'], v['shift2px_max_de00']['p90']) for k, v in result['modes'].items()], flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--band', required=True, type=int, choices=range(1, 5))
    run(ap.parse_args().band)
