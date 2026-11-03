#!/usr/bin/env python3
"""Decode final DNGs, replay the frozen predictor, and measure saved JPEGs."""
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import dense
common = dense.legacy()
import importlib.util
import io
import numpy as np
from PIL import Image, ImageFilter
from predict import decode_card, predict, Renderer
from tiff_io import Tiff
import chart
from analyze import analyze, align, sample
import lattice


def stats(values):
    a = np.asarray(values, float)
    return dict(n=int(a.size), median=float(np.median(a)), p90=float(np.percentile(a, 90)),
                p99=float(np.percentile(a, 99)), max=float(np.max(a)))


def manifest(number):
    return dense.LOCAL / 'cards' / f'R090000{number}.json'


def structure(card):
    path = common.pin(dense.ROOT / 'research/gr_incamera_dev/verify.py')
    spec = importlib.util.spec_from_file_location('gr_dense_legacy_verify', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.verify_dng(manifest(int(Path(card['dng_path']).stem[-1])))
    # The legacy check covers the two compressed previews. Also read RGB IFD0 here.
    t = Tiff(Path(card['dng_path']).read_bytes())
    for node in t.ifds:
        if node is t.raw or 256 not in node.entries or t.scalar(node, 259) != 1:
            continue
        seg = t.segments(node)[0]
        size = tuple(t.scalar(node, k) for k in (256, 257))
        im = Image.frombytes('RGB', size, t.data[seg['offset']:seg['offset'] + seg['capacity']])
        im.load()
        dense.require(np.ptp(np.asarray(im)) > 100, 'RGB thumbnail is blank')
    result['all_three_previews_valid'] = True
    return result


def decode_check(number):
    card = dense.read(manifest(number))
    result = structure(card)
    raw = decode_card(card)
    fresh = lattice.design(Tiff(Path(card['template_path']).read_bytes()),
                           card['band'], card['acceptance_microtest'])
    for key in fresh:
        dense.require(dense.plain(fresh[key]) == card[key], f'saved design differs from generator: {key}')
    expected = lattice.mosaic(fresh)
    dense.require(np.array_equal(raw, expected), 'final DNG differs from newly synthesized mosaic')
    g = card['geometry']
    for k, (y, x) in enumerate(((0, 0), (0, 1), (1, 0), (1, 1))):
        dense.require((raw[y::2, x::2] >= g['black'][k]).all() and
                      (raw[y::2, x::2] <= g['white']).all(), 'RAW beyond black/white bounds')
    half = chart.camera_half(raw, card)
    w, h = g['crop_wh']
    yy, xx = np.mgrid[0:h:2, 0:w:2]
    half *= (2. ** chart.gain_ev(chart.radial(xx + 1, yy + 1, (w, h))))[..., None]
    mapped, errors = [], []
    renderer, cm = Renderer(), common.colour()
    raw_clipped = 0
    for p in card['patches']:
        x1, y1, x2, y2 = np.asarray(p['roi']) // 2
        actual = half[y1:y2, x1:x2].mean(axis=(0, 1))
        target = np.asarray(p['raw']) * (1 if p['precompensated'] else 2. ** chart.gain_ev(p['radius']))
        errors.append(float(np.max(np.abs(actual - target))))
        bx1, by1, bx2, by2 = p['box']
        ox, oy = g['crop_xy']
        pixels = raw[oy+by1:oy+by2, ox+bx1:ox+bx2]
        raw_clipped += int((pixels >= g['white']).any())
        mapped.append(dict(id=p['id'], designed_camera_rgb=target,
                           decoded_gain_corrected_camera_rgb=actual,
                           wb_camera_rgb=actual / g['neutral']))
    dense.require(raw_clipped == 0, 'injected patch clips RAW')
    # Uncompensated probes span a radius inside their ROI; validate principal patches separately.
    primary = [i for i, p in enumerate(card['patches']) if p['precompensated']]
    dense.require(max(errors[i] for i in primary) < 1.5e-4, 'camera-space round-trip error too high')
    ideal = np.array([mapped[i]['designed_camera_rgb'] for i in primary])
    actual = np.array([mapped[i]['decoded_gain_corrected_camera_rgb'] for i in primary])
    mapping = {}
    for mode in ('standard', 'positive', 'negative'):
        a = renderer.render(ideal, g['neutral'], mode)
        b = renderer.render(actual, g['neutral'], mode)
        delta = cm.delta_e00(cm.rgb_lab(a), cm.rgb_lab(b))
        dense.require(float(delta.max()) < .75, 'quantization changes predicted mapping excessively')
        mapping[mode] = stats(delta)
    levels = np.geomspace(.0001, .98, 4096)
    monotonic = {}
    for mode in ('standard', 'positive', 'negative'):
        out = renderer.render(levels[:, None] * g['neutral'], g['neutral'], mode)
        step = np.diff(out, axis=0)
        dense.require(np.isfinite(out).all() and step.min() >= -1e-12,
                      'neutral predictor response is not monotonic')
        monotonic[mode] = dict(levels=len(levels), minimum_step=float(step.min()),
                               maximum_step=float(step.max()), passed=True)
    dense.dump(dense.LOCAL / 'mapped' / f'R090000{number}.json', mapped)
    result.update(passed=True, raw_clipped_patches=raw_clipped,
        raw_round_trip_exact=True, patch_count=len(card['patches']),
        camera_coordinate_error=stats([errors[i] for i in primary]),
        designed_to_predicted_de00=mapping, neutral_monotonicity=monotonic,
        camera_acceptance=False)
    dense.dump(dense.LOCAL / 'validation' / f'R090000{number}-decode.json', result)
    print(f'R090000{number}: decode/IFD/preview/RAW bounds/mapping PASS; patches={len(card["patches"])}')
    return result


def predictions(number):
    path = predict(manifest(number), dense.LOCAL / 'predictions' / f'R090000{number}')
    print(f'R090000{number}: three saved model JPEGs at {path.parent.relative_to(dense.ROOT)}')


def jpeg_check(number):
    card = dense.read(manifest(number))
    folder = dense.LOCAL / 'predictions' / f'R090000{number}'
    record = dense.read(folder / 'prediction.json')
    dense.require(record['card_dng_sha256'] == card['dng_sha256'], 'stale prediction')
    for item in record['files'].values():
        dense.require(dense.sha(item['path']) == item['sha256'], 'predicted JPEG hash changed')
    styles = {k: v['path'] for k, v in record['files'].items()}
    destination = dense.LOCAL / 'roundtrip' / f'R090000{number}.json'
    if number == 1:
        # Micro-test does not carry the production card's 256 radial/reference controls.
        result = dict(modes={})
        for mode, path in styles.items():
            with Image.open(path) as im:
                image = im.convert('RGB')
            h, alignment = align(image, card)
            result['modes'][mode] = dict(patches=sample(image, card, h), alignment=alignment)
        dense.dump(destination, result)
    else:
        result = analyze(manifest(number), styles, destination, 'model_prediction')
    saved = np.load(folder / 'patch_predictions.npz', allow_pickle=False)
    cm, metrics = common.colour(), {}
    primary = np.array([p['role'] in ('colour', 'tone') for p in card['patches']])
    for mode, state in result['modes'].items():
        observed = np.array([p['rgb_observed'] for p in state['patches']])
        expected = saved[mode]
        error = cm.delta_e00(cm.rgb_lab(observed), cm.rgb_lab(expected))
        dense.require(np.percentile(error[primary], 90) < .9 and error[primary].max() < 4,
                      'saved JPEG round-trip error exceeds tolerance')
        clipped = ((expected <= 2/255) | (expected >= 253/255)).any(axis=1)
        hard_clipped = ((expected <= 0) | (expected >= 1)).any(axis=1)
        # A modest develop blur must leave every central ROI and all fiducials usable.
        with Image.open(styles[mode]) as im:
            blurred = im.convert('RGB').filter(ImageFilter.GaussianBlur(2.))
        buffer = io.BytesIO()
        blurred.save(buffer, format='JPEG', quality=90, subsampling=1)
        with Image.open(io.BytesIO(buffer.getvalue())) as im:
            blurred = im.convert('RGB')
        h, alignment = align(blurred, card)
        measured = np.array([p['rgb_observed'] for p in sample(blurred, card, h)])
        blur_error = cm.delta_e00(cm.rgb_lab(measured), cm.rgb_lab(observed))
        dense.require(np.percentile(blur_error[primary], 90) < 1 and blur_error[primary].max() < 4,
                      'blur/JPEG contaminates the central ROI')
        q = dict(saved_jpeg_de00=stats(error[primary]), blur2px_jpeg90_de00=stats(blur_error[primary]),
                 primary_patches=int(primary.sum()), output_near_endpoint_primary=int((clipped & primary).sum()),
                 output_hard_clipped_primary=int((hard_clipped & primary).sum()),
                 fiducials=state['alignment']['marker_ids'], blurred_fiducials=alignment['marker_ids'])
        if number != 1:
            radial = state['radial']
            dense.require(radial['passed'], 'radial fit failed')
            q.update(radial_fit_passed=True, radial_rmse_ev=radial['rmse_ev'],
                     radial_gain_max_error_ev=float(np.max(np.abs(np.asarray(radial['gain_ev'])-chart.GAIN_EV))),
                     colour_holdout=radial['colour_holdout'],
                     normalized_fit_supported=sum(p['radial_supported'] for p in state['patches']))
        metrics[mode] = q
    dense.dump(dense.LOCAL / 'validation' / f'R090000{number}-jpeg.json',
               dict(passed=True, dng_sha256=card['dng_sha256'], modes=metrics, camera_acceptance=False))
    print(f'R090000{number}: saved JPEG + alignment + 2px blur round-trip PASS')
    return metrics


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--decode', type=int, choices=range(1, 6))
    group.add_argument('--predict', type=int, choices=range(1, 6))
    group.add_argument('--jpeg', type=int, choices=range(1, 6))
    args = parser.parse_args()
    if args.decode:
        decode_check(args.decode)
    elif args.predict:
        predictions(args.predict)
    else:
        jpeg_check(args.jpeg)
