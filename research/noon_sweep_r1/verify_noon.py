#!/usr/bin/env python3
"""Deterministic behaviour checks; photos/tables/generated fixtures stay local/."""
import os
import sys
from pathlib import Path
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_noon as n
import argparse
import datetime as dt
import time
import numpy as np
from PIL import Image
from scipy import ndimage
from geometry import locate_grid, page_identity, project, homography


def geometry(out):
    records = []
    pages = n.read(n.ROOT/'research/color_references/screen_chart.json')['pages']
    render = n.read(n.LOCAL/'synthetic-pages/render.json')
    # Each page gets a different camera position, perspective and blur. Absolute
    # corner coordinates below are independent ground truth for the test.
    for i, item in enumerate(render['pages']):
        source = Image.open(n.LOCAL/'synthetic-pages'/item['filename']).convert('RGB')
        sw, sh = source.size
        phase = i/7
        quad = np.array([[.08+.035*phase, .10], [.91, .075+.025*phase], [.94-.02*phase, .91], [.065, .94-.03*phase]])
        S = homography([[0, 0], [1, 0], [1, 1], [0, 1]], quad)
        # PIL inverse map works in pixels, not the helper's normalized coordinates.
        pix = np.diag([sw, sh, 1]) @ np.linalg.inv(S) @ np.diag([1/1800, 1/1200, 1])
        pix /= pix[2, 2]
        warped = source.transform((1800, 1200), Image.Transform.PERSPECTIVE,
            tuple(pix.ravel()[:8]), Image.Resampling.BICUBIC, fillcolor=(18, 20, 19))
        a = np.asarray(warped, float)
        a = ndimage.gaussian_filter(a, (.6+phase*.65, .6+phase*.65, 0))
        rng = np.random.default_rng(900+i)
        a = np.clip(a * [.89, .94, 1.02]+rng.normal(0, .6, a.shape), 0, 255).astype(np.uint8)
        path = out/(item['id']+'-perspective.png')
        Image.fromarray(a).save(path)
        H, loc = locate_grid(a)
        identity = page_identity(a, H, pages, n.LOCAL/'header-templates')
        assert identity['page'] == item['id'], (item['id'], identity)
        expected = []
        for roi in item['rois']:
            b = roi['box']
            expected.append(project(S, [[(b['x']+b['width']/2)/sw, (b['y']+b['height']/2)/sh]])[0])
        actual = project(H, [[(c+.5)/8, (r+.5)/6] for r in range(6) for c in range(8)])
        error = np.linalg.norm((actual-np.array(expected))*[1800, 1200], axis=1)
        assert error.max() < 8., (item['id'], error.max())
        records.append(dict(page=item['id'], recognized=identity['page'], center_error_max_px=float(error.max()),
            center_error_p95_px=float(np.percentile(error, 95)), inliers=loc['inliers']))
        print('GEOMETRY', records[-1], flush=True)
    return records


def numeric(out):
    model = n.Reference()
    cm = n.module(n.ROOT/'research/color_references/colour_math.py', 'noon_verify_cm')
    raw = n.module(n.ROOT/'research/probe_pack_r1/field_20261103.py', 'noon_verify_raw')
    meta = raw.metadata(raw.Tiff((n.ROOT/'captures/probe3-field-20261104/R8051955.DNG').read_bytes()))
    pages = n.read(n.ROOT/'research/color_references/screen_chart.json')['pages']
    rng = np.random.default_rng(156)
    inputs = []
    while len(inputs) < 48:
        x = rng.uniform(100, 1600, (1, 3))
        values = np.array([model.predict(k, x)[0] for k in n.SETTINGS])
        if values.min() > 4 and values.max() < 250:
            inputs.append(x[0])
    inputs = np.array(inputs)
    # A separate spelling of the pre/row/table chain checks the adapter against
    # the deployed reference model without comparing it to its own wrapper.
    manual_error = []
    for setting in n.SETTINGS:
        b = model.entries[setting]
        xs = np.r_[0, n.struct.unpack_from('>31H', b, 20), 4095]
        curves = (b[379:412], b[82:115], b[412:445]) if b[1] & 4 else (b[82:115],)*3
        pre = np.column_stack([np.interp(inputs[:, c], xs, list(curves[c])) for c in range(3)])
        row = model.mm.MatrixRow.from_bytes(b[216:244])
        yy, ci = row.apply(pre)
        if b[0] == 3:
            cc = np.zeros_like(ci)
        else:
            coeff = np.array([model.fs.decode_word(b[p:p+4]) for p in range(115, 211, 4)])
            z = model.fs.Z_of_words(coeff[:, 0], coeff[:, 1], model.model.engine.ctx)
            cc = model.model.engine.table.forward(ci, z)[0]
        manual = np.clip(model.mm.rgb_from_ycc(yy, cc), 0, 255)
        error = float(np.max(abs(manual-model.predict(setting, inputs))))
        assert error < 1e-12, (setting, error)
        manual_error.append(dict(setting=setting, max_rgb_error=error))
    # A 15x15 region is valid for a small physical card, but the historical
    # screen gate must still reject it. Its CFA means are independent literals.
    rgb = np.full((100,100,3), [16,32,48], dtype=np.uint8)
    native = np.full_like(rgb, [33,144,99])
    cfa = np.array([[0,1],[1,2]])[np.arange(100)[:,None]%2,np.arange(100)[None,:]%2]
    sensor = np.array([100,200,300])[cfa]
    patch = dict(id='small-card', rgb=[0,0,0], swatch=dict(x=.25,y=.25,w=.5,h=.5))
    info = dict(crop_origin_xy=[0,0],black=10,white=4095)
    sampler = n.loaders()[1]
    try:
        sampler(rgb,native,sensor,info,np.eye(3),patch,.3,[1,2,4])
    except AssertionError:
        pass
    else:
        raise AssertionError('Historical screen >300 pixel gate must remain enforced')
    small = n.sample_physical_patch(rgb,native,sensor,info,np.eye(3),patch,.3,[1,2,4])
    assert np.array_equal(small['jpeg_mean'],[16,32,48])
    assert np.array_equal(small['raw_wb'],[90,95,72.5])
    assert 128 <= small['pixels'] <= 300 and min(small['cfa_pixels']) >= 32
    try:
        n.sample_physical_patch(rgb,native,sensor,info,np.eye(3),patch,.1,[1,2,4])
    except ValueError:
        pass
    else:
        raise AssertionError('Under-supported physical ROI must be rejected')
    for key in ('jpeg_mean','native_ycc_mean','raw_wb','raw_clip_fraction','jpeg_clip_fraction','polygon'):
        old = sampler(rgb,native,sensor,info,np.eye(3),patch,.5,[1,2,4])
        new = n.sample_physical_patch(rgb,native,sensor,info,np.eye(3),patch,.5,[1,2,4])
        assert np.array_equal(old[key],new[key]),key
    frames = []
    for group in range(9):
        for pi, page in enumerate(pages):
            i = len(frames)
            setting = n.SETTINGS[group] if group < 8 else '04 Std'
            # Include a known recipe identity conflict, not a relabelled PASS.
            actual = '06 F-CN' if i == 8 else setting
            drift = 1 + i*.0002*np.array([1., .8, .5])
            x = inputs*drift
            jpg = model.predict(actual, x)
            roi = []
            for k, patch in enumerate(page['patches']):
                roi.append(dict(id=patch['id'], group=patch['group'], jpeg_mean=jpg[k].tolist(),
                    raw_wb=(x[k]/np.array([.9, 1.1, 1.05])).tolist(),
                    native_ycc_mean=(n.ycc(jpg[k])+[0, .2, -.1]).tolist(),
                    jpeg_clip_fraction=[0, 0, 0], raw_clip_fraction=[0, 0, 0]))
            metadata = dict(meta, time=(dt.datetime(2026, 11, 4, 12)+dt.timedelta(seconds=i)).strftime('%Y:%m:%d %H:%M:%S'))
            frames.append(dict(frame=f'synth_{i:03d}', kind='screen', has_raw=True, metadata=metadata,
                synthetic=True,
                patches={str(f):roi for f in n.FRACTIONS}, override={}, identity=dict(page=page['id']),
                acquisition_index=i, acquisition_count=72))
    for i in range(11):
        setting = n.SETTINGS[i] if i < 8 else '04 Std'
        scene = 'daylight' if i < 9 else 'indoor'
        x = inputs[:27]*(1+i*.0003)
        jpg = model.predict(setting, x)
        rois = []
        for k in range(27):
            name = f'card_{k//6+1}_{k%6+1}' if k < 24 else ('skin', 'blue', 'leaf')[k-24]
            group = 'untrusted_card' if k < 24 else ('memory_skin', 'blue', 'memory_foliage')[k-24]
            rois.append(dict(id=name, group=group, jpeg_mean=jpg[k].tolist(), raw_wb=(x[k]/[.9, 1.1, 1.05]).tolist(),
                native_ycc_mean=(n.ycc(jpg[k])+[0, .2, -.1]).tolist(), jpeg_clip_fraction=[0, 0, 0], raw_clip_fraction=[0, 0, 0]))
        metadata = dict(meta, time=(dt.datetime(2026, 11, 4, 12, 10)+dt.timedelta(seconds=i)).strftime('%Y:%m:%d %H:%M:%S'))
        frames.append(dict(frame=f'physical_{i:03d}', kind='physical', has_raw=True, metadata=metadata,
            synthetic=True,
            patches={str(f):rois for f in n.FRACTIONS}, override=dict(scene=scene), identity=dict(page=scene),
            acquisition_index=72+i, acquisition_count=83))
    issues = []
    result = n.analyse(frames, out, cm, issues)
    clean = [r for r in result['rows'] if r['frame'] != 'synth_008']
    assert len(clean) == 71*48*3+11*27*3, len(clean)
    assert all(r['valid'] for r in clean), 'Unexpected invalid synthetic patch'
    maximum = max(r['DE00'] for r in clean)
    assert maximum < 1e-6, maximum
    conflict = next(r for r in result['identity'] if r['frame'] == 'synth_008')
    assert conflict['conflict'] and conflict['response'] == '06 F-CN', conflict
    assert all(r['time_bracketed'] for r in clean if r['setting'] != '04 Std'), 'Missing tail bracket'
    # The measured sign is deliberately zero here; it must stay unresolved.
    assert any(r['state'] == 'unresolved_small_component' for r in result['sign_gaps'])
    n.dump(out/'numeric-detail.json', result)
    report_args = argparse.Namespace(photos=Path('synthetic-83-frames'))
    n.report(report_args, out, frames, result, issues, 0.)
    return dict(frames=83, screen_frames=72, physical_frames=11, compared_rows=len(result['rows']), clean_max_DE00=maximum,
        conflict_detected=conflict, reference_adapter=manual_error, issues=issues)


def inventory(out):
    pages = n.read(n.ROOT/'research/color_references/screen_chart.json')['pages']
    folders = sorted({*n.ROOT.glob('captures/mount-probe-ramp-20261103*'),
        *n.ROOT.glob('captures/mount-g150-20261101'), *n.ROOT.glob('captures/showcase-*')})
    records = []
    for folder in folders:
        pairs = n.discover(folder)
        entry = dict(directory=str(folder.relative_to(n.ROOT)), paired_images=len(pairs), frames=[])
        for pair in pairs:
            im = Image.open(pair['jpeg']).convert('RGB')
            im.thumbnail((1500, 1000))
            a = np.asarray(im)
            try:
                H, loc = locate_grid(a)
                identity = page_identity(a, H, pages, n.LOCAL/'header-templates')
                row = dict(frame=pair['jpeg'].stem, page=identity['page'], valid=identity['valid'], identity=identity)
            except ValueError as e:
                row = dict(frame=pair['jpeg'].stem, page='unsupported-layout', valid=False, reason=str(e))
            entry['frames'].append(row)
            print('INVENTORY', folder.name, row['frame'], row['page'], flush=True)
        records.append(entry)
    return records


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('phase', choices=('geometry', 'numeric', 'inventory'))
    args = ap.parse_args()
    lock = n.setup()
    out = n.LOCAL/('verify-'+args.phase)
    out.mkdir(exist_ok=True)
    sys.addaudithook(n.guard)
    start = time.monotonic()
    frozen = n.source_identity()
    result = {'geometry':geometry, 'numeric':numeric, 'inventory':inventory}[args.phase](out)
    n.dump(out/'receipt.json', dict(status='PASS', phase=args.phase, result=result,
        elapsed_seconds=time.monotonic()-start, source_sha256=frozen, sources_unchanged=n.source_identity() == frozen))
    print('PASS', args.phase, 'elapsed_s', time.monotonic()-start, flush=True)


if __name__ == '__main__':
    main()
