"""Compare camera JPEGs without rescaling or registration."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from core import ROOT, HERE, LOCAL, guard, read, modules, dump, sha
from metadata import embedded, jpeg_info
import argparse
import io
import json
import hashlib
import numpy as np
from PIL import Image
from scipy.ndimage import uniform_filter, binary_erosion


def flat_mask(a):
    gr, _, _, _ = modules()
    h = gr.half(a)
    mask = np.ones(h.shape[:2], bool)
    for c in range(3):
        m = uniform_filter(h[..., c], 5)
        var = np.maximum(uniform_filter(h[..., c] ** 2, 5) - m ** 2, 0)
        mask &= np.sqrt(var) < 3.5
    hh, ww = mask.shape
    quads = a.reshape(hh, 2, ww, 2, 3)
    mask &= (quads.min(axis=(1, 3)) > 2).all(axis=-1)
    mask &= (quads.max(axis=(1, 3)) < 253).all(axis=-1)
    mask[:16] = mask[-16:] = False
    mask[:, :16] = mask[:, -16:] = False
    return binary_erosion(mask, iterations=2)


def stats(v):
    return dict(n=len(v), median=float(np.median(v)), p95=float(np.percentile(v, 95)),
                mean=float(np.mean(v)), maximum=float(np.max(v)))


def compare(f):
    blob = embedded(ROOT / f['dng'])
    info = jpeg_info(blob)
    record = dict(id=f['id'], embedded_bytes=len(blob), embedded_sha256=hashlib.sha256(blob).hexdigest(),
                  provided_bytes=(ROOT / f['jpg']).stat().st_size,
                  provided_sha256=sha(ROOT / f['jpg']), embedded=info,
                  provided=jpeg_info(ROOT / f['jpg']))
    record['byte_identical'] = record['embedded_sha256'] == record['provided_sha256']
    if not f['standalone_jpeg']:
        assert record['byte_identical']
        dump(HERE / ('jpeg_' + f['id'] + '.json'), record)
        print(json.dumps(dict(id=f['id'], byte_identical=True, size=info['size'])))
        return
    _, cm, _, _ = modules()
    with Image.open(io.BytesIO(blob)) as im:
        a = np.asarray(im.convert('RGB'))
    with Image.open(ROOT / f['jpg']) as im:
        b = np.asarray(im.convert('RGB'))
    assert a.shape == b.shape
    mask = flat_mask(a) & flat_mask(b)
    errors, deltas = [], []
    absolute_sum, signed_sum = np.zeros(3), np.zeros(3)
    flat_signed = np.zeros(3)
    exact_pixels = 0
    for y in range(0, a.shape[0], 128):
        aa, bb = a[y:y + 128], b[y:y + 128]
        diff = aa.astype(np.int16) - bb.astype(np.int16)
        absolute_sum += abs(diff).sum(axis=(0, 1))
        signed_sum += diff.sum(axis=(0, 1))
        exact_pixels += int((diff == 0).all(axis=-1).sum())
        use = np.repeat(np.repeat(mask[y // 2:(y + len(aa)) // 2], 2, axis=0), 2, axis=1)
        la, lb = cm.rgb_lab(aa[use] / 255), cm.rgb_lab(bb[use] / 255)
        errors.append(cm.delta_e00(la, lb))
        flat_signed += (la - lb).sum(axis=0)
    error = np.concatenate(errors)
    total = a.shape[0] * a.shape[1]
    record.update(mean_absolute_code_difference=float(absolute_sum.sum() / (3 * total)),
                  per_channel_mean_absolute_code_difference=absolute_sum / total,
                  signed_RGB_mean_embedded_minus_standalone=signed_sum / total,
                  identical_pixel_fraction=exact_pixels / total,
                  flat_pixels=int(len(error)), flat_DE00=stats(error),
                  flat_mean_delta_Lab_embedded_minus_standalone=flat_signed / len(error),
                  flat_mask_definition='Both JPEGs: 5x5 half-quad RGB std <3.5, unclipped, border16, erosion2; DE00 on all full-resolution pixels in mask')
    # Quantify differences after exactly the averaging used by gr_pairs.
    with np.load(LOCAL / 'samples' / (f['id'] + '.npz'), allow_pickle=False) as z:
        xy = z['xy']
    gr = modules()[0]
    ah, bh = gr.half(a), gr.half(b)
    x, y = xy.T
    am = np.column_stack([uniform_filter(ah[..., c], 5)[y, x] for c in range(3)])
    bm = np.column_stack([uniform_filter(bh[..., c], 5)[y, x] for c in range(3)])
    record['paired_observation_DE00'] = stats(cm.delta_e00(cm.rgb_lab(am / 255), cm.rgb_lab(bm / 255)))
    dump(HERE / ('jpeg_' + f['id'] + '.json'), record)
    print(json.dumps({k: record[k] for k in ('id', 'mean_absolute_code_difference', 'flat_DE00',
        'flat_mean_delta_Lab_embedded_minus_standalone', 'paired_observation_DE00')},
        default=lambda x: x.tolist()))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--frame', required=True)
    p.add_argument('--inventory', type=Path, required=True)
    args = p.parse_args()
    guard()
    compare(next(f for f in read(args.inventory) if f['id'] == args.frame))
