#!/usr/bin/env python3
"""Verify original pairs, summarize cached RAW, and select matched spatial blocks."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import argparse
import benchlib as b
b.guard()
import numpy as np
from PIL import Image

FRAMES = {'std': ('gr4hdf-set', 'R0003009_standard', 'hdf_std'),
          'pos': ('gr4hdf-set', 'R0003004_positive', 'hdf_pos'),
          'neg': ('gr4hdf-set', 'R0003006_negative', 'hdf_neg'),
          'hc': ('gr4hdf-set', 'R0003007_bw', 'hdf_hc'),
          'A_pos': ('gr4-modes', 'positive', 'positive'),
          'A_neg': ('gr4-modes', 'negative', 'negative'),
          'A_hc': ('gr4-modes', 'hc_bw', 'hc_bw')}
CAP = b.ROOT / 'captures/contrib/2026-10-19'
GR4 = b.ROOT / 'research/gr4_modes/local'
K = 8  # 16 by 16 full-resolution sensor/JPEG pixels, non-overlapping.


def blk(a, k=K):
    h, w = a.shape[:2]
    h -= h % k
    w -= w % k
    return a[:h, :w].reshape(h//k, k, w//k, k, *a.shape[2:])


def preflight():
    checked = {}
    for folder in ('gr4hdf-set', 'gr4-modes'):
        for line in (CAP / folder / 'SHA256SUMS').read_text().splitlines():
            h, name = line.split(maxsplit=1)
            p = CAP / folder / name.lstrip('*')
            assert b.sha(p) == h, p
            checked[str(p.relative_to(b.ROOT))] = h
    recorded = b.read(GR4 / 'input_hashes_after.json')
    for p, h in checked.items():
        assert recorded[p] == h, f'Prepared cache original identity mismatch: {p}'
    assert b.sha(b.TABLE) == b.EXPECTED_TABLE
    package=b.read(b.TABLE.parent/'manifest.json')
    diff=b.read(b.TABLE.parent/'field_diff.json')
    assert package['dat_sha256']==b.EXPECTED_TABLE
    for source in package['round5_sources'].values():
        assert b.sha(b.ROOT/source['path'])==source['sha256']
    assert diff['tables-v4r2-noprobe']['file_sha256']==b.EXPECTED_TABLE
    t = b.tiff_reader()
    maker = b.load('bench_maker', b.ROOT / 'research/contrib_gr_analysis/tiff_makernote.py')
    meta = {}
    for key, (folder, stem, cache) in FRAMES.items():
        raw = (CAP / folder / (stem + '.DNG')).read_bytes()
        tags = t.Tiff(raw).tags()
        _, off, _, _, _ = maker.maker_note_bytes(maker.Tiff(raw))
        _, mn = maker.decode_gr3_family(maker.Tiff(raw), off)
        root = t.Tiff(raw).ifd(t.Tiff(raw).root)
        exif = t.Tiff(raw).ifd(root[34665]['value'][0]) if 34665 in root else {}
        meta[key] = dict(file=stem, baseline_exposure=tags.get(50730, [0])[0],
                         DR_tag=mn.get('dynamic_range_0x0069'), neutral=tags[50728],
                         forward_matrix_present=50964 in tags or 50965 in tags,
                         iso=exif.get(34855, {}).get('value'),
                         image_tone=mn['image_tone'], cache_sha256=b.sha(GR4/(cache+'.npz')))
    b.dump(b.LOCAL / 'preflight.json', dict(mount=b.mount_guard(), original_hashes=checked,
           frames=meta, table_sha256=b.sha(b.TABLE), cache_original_hashes_match=True,
           package_manifest_sha256=b.sha(b.TABLE.parent/'manifest.json'),
           package_field_diff_sha256=b.sha(b.TABLE.parent/'field_diff.json'),
           cache_generation='gr4_modes/prepare.py -> gr4io.load_pair, normalized RGGB and 2x2 JPEG mean'))
    print('preflight:', len(checked), 'original hashes verified; metadata for', len(meta), 'frames')


def frame(key):
    check = b.read(b.LOCAL / 'preflight.json')
    folder, stem, cache = FRAMES[key]
    path = GR4/(cache+'.npz')
    assert b.sha(path) == check['frames'][key]['cache_sha256']
    with np.load(path, allow_pickle=False) as z:
        rgb, jpeg = z['rgb'], z['jpeg_half']
        n, be = z['neutral'].astype(float), float(z['baseline_exposure'])
        assert abs(be-check['frames'][key]['baseline_exposure']) < 1e-6
        assert np.allclose(n, check['frames'][key]['neutral'], rtol=1e-7)
        wb = rgb / n
        u = wb @ np.array([.25, .5, .25])
        mu = blk(u).mean(axis=(1, 3))
        cam = blk(rgb).mean(axis=(1, 3))
        j = blk(jpeg).mean(axis=(1, 3))
        full = np.asarray(Image.open(CAP/folder/(stem+'.JPG')).convert('RGB'))
        jfull = blk(full, 2*K)
        regen = jfull.mean(axis=(1, 3))
        mismatch = float(np.max(abs(regen-j)))
        assert mismatch < 3e-5, mismatch
        out = dict(cam=cam, wb=cam/n*2**be, jpeg=j, u=mu*2**be,
                   ucv=blk(u).std(axis=(1, 3))/np.maximum(mu, 1e-6),
                   channel_cv=blk(wb).std(axis=(1, 3))/np.maximum(blk(wb).mean(axis=(1, 3)), .01),
                   rawmax=blk(rgb).max(axis=(1, 3, 4)),
                   rawclip=blk(z['raw_clip']).any(axis=(1, 3)),
                   jpegmax=jfull.max(axis=(1, 3, 4)), jpegmin=jfull.min(axis=(1, 3, 4)),
                   jpeg_std=blk(jpeg).std(axis=(1, 3)).max(axis=-1),
                   neutral=n, baseline_exposure=be)
        np.savez(b.LOCAL / f'blocks_{key}.npz', **out)
        b.dump(b.LOCAL / f'cache_check_{key}.json', dict(jpeg_block_mean_max_error=mismatch,
               half_shape=list(rgb.shape), block_shape=list(j.shape),
               original_cache_sha256=b.sha(path), original_jpeg_sha256=b.sha(CAP/folder/(stem+'.JPG'))))
    print(key, list(j.shape[:2]), 'JPEG cache max error', mismatch)


def bridges():
    cm, t = b.colour(), b.tiff_reader()
    gr = t.Tiff((CAP/'gr4hdf-set/R0003009_standard.DNG').read_bytes()).tags()
    gx = t.Tiff((b.ROOT/'captures/a12-50/2026-10-20/stage2j-v1-calibration/R8051178.DNG').read_bytes()).tags()
    A4, i4 = cm.dng_camera_to_xyz(gr)
    AX, ix = cm.dng_camera_to_xyz(gx)
    # Primary: existing common-white ColorMatrix bridge, at the GR scene white.
    white = np.array(i4['scene_white_xyz_y1'])
    old, info = cm.common_white_sensor_bridge(gx, gr, white)
    n4 = np.asarray(gr[50728])
    nx_common = np.linalg.solve(old, n4)
    primary = np.diag(1/nx_common) @ np.linalg.inv(old) @ np.diag(n4)
    # Alternative: independent AsShotNeutral adaptations into D50, as bw_helpers.
    alternative = np.linalg.inv(AX @ np.diag(gx[50728])) @ (A4 @ np.diag(n4))
    for matrix in (primary, alternative):
        assert np.allclose(matrix @ np.ones(3), np.ones(3), atol=3e-6)
    np.savez(b.LOCAL/'bridges.npz', common_white=primary, per_camera=alternative)
    b.dump(b.LOCAL/'bridges.json', dict(primary='common_white', alternative='per_camera',
        common_white=info, gr_dng=i4, gxr_dng=ix,
        gr_to_gxr_wb_common_white=primary, gr_to_gxr_wb_per_camera=alternative,
        gr_cct=i4['cct_K_approx'], gxr_as_shot_cct=ix['cct_K_approx'],
        no_forward_matrix_in_either_file=not i4['forward_matrix_present'] and not ix['forward_matrix_present'],
        primary_source='research/color_references/colour_math.py:common_white_sensor_bridge',
        alternative_source='research/closed_loop/local/vendor/bw_helpers.py:gr4_blocks',
        scale='x = bridge(wb including BE and g(r)) * 320/0.0853 * 2**EV'))


def select():
    data = {k: dict(np.load(b.LOCAL/f'blocks_{k}.npz')) for k in ('std', 'pos', 'neg', 'hc')}
    d = data['std']
    hh, ww = d['u'].shape
    yy, xx = np.mgrid[:hh, :ww]
    px, py = (xx+.5)*(2*K), (yy+.5)*(2*K)
    width, height = 6192, 4128
    r2 = ((px-width/2)**2+(py-height/2)**2)/((width/2)**2+(height/2)**2)
    base = r2 <= .85**2
    counts = {'total': int(base.size), 'r_le_0p85': int(base.sum())}
    for key in ('std', 'pos', 'neg'):
        f = data[key]
        base &= ((f['ucv'] < .04) & (f['channel_cv'].max(axis=-1) < .08)
                 & (f['rawmax'] < .97) & ~f['rawclip'] & (f['jpegmax'] < 250)
                 & (f['jpegmin'] > 2) & (f['jpeg_std'] < 3.))
        counts['flat_unclipped_after_'+key] = int(base.sum())
    # Exposure match uses BE-free WB RAW; it cannot use the styled JPEG target.
    w0 = d['wb']/2**float(d['baseline_exposure'])
    differences = []
    for key in ('pos', 'neg'):
        f = data[key]
        w = f['wb']/2**float(f['baseline_exposure'])
        dev = np.max(abs(w-w0)/np.maximum(w0, .01), axis=-1)
        ev = abs(np.log2(np.maximum(f['u']/2**float(f['baseline_exposure']),1e-6)
                       / np.maximum(d['u']/2**float(d['baseline_exposure']),1e-6)))
        base &= (dev < .06) & (ev < .08)
        differences.append(dev)
    counts['same_position_raw_agreement'] = int(base.sum())
    # A 32-pixel moat on both sides of each 4x4 cell boundary prevents adjacency leakage.
    gridx = np.minimum((px/(width/4)).astype(int), 3)
    gridy = np.minimum((py/(height/4)).astype(int), 3)
    dx = np.minimum(px % (width/4), width/4-px % (width/4))
    dy = np.minimum(py % (height/4), height/4-py % (height/4))
    base &= (dx >= 32) & (dy >= 32)
    counts['spatial_buffer'] = int(base.sum())
    radial = np.asarray(b.read(GR4/'tone_curves.json')['radial']['gr4_coef_natural_log'])
    gain = np.exp(-(radial[0]*r2+radial[1]*r2**2+radial[2]*r2**3))
    effective = d['wb']*gain[..., None]
    bb = dict(np.load(b.LOCAL/'bridges.npz'))
    # One support mask for all sensitivity rows, fixed before looking at fit error.
    for m in bb.values():
        x = effective @ m.T * (320/.0853)
        base &= np.all((x*2**(-.3) > 0) & (x*2**.3 < 4095), axis=-1)
    counts['all_bridges_and_EV_physical'] = int(base.sum())
    assert base.sum() >= 100
    result = dict(wb_effective=effective[base], pos_xy=np.stack([px[base],py[base]],axis=-1),
                  cell=(4*gridy+gridx)[base], fold=(2*(gridy//2)+(gridx//2))[base],
                  u_c=(d['u']*gain)[base], raw_agreement=np.max(differences,axis=0)[base])
    for key in data:
        result['jpeg_'+key] = data[key]['jpeg'][base]
    # Training thinning: at most 80 uniformly spaced blocks per cell, chosen without targets.
    train = np.zeros(int(base.sum()), bool)
    for cell in range(16):
        idx = np.flatnonzero(result['cell'] == cell)
        if len(idx):
            train[idx[np.unique(np.linspace(0,len(idx)-1,min(80,len(idx))).astype(int))]] = True
    result['fit_subset'] = train
    np.savez(b.LOCAL/'matched.npz', **result)
    b.dump(b.LOCAL/'selection.json', dict(counts=counts, full_pixel_block=16,
           radius_max=.85, raw_cv_max=.04, raw_channel_cv_max=.08, raw_max_limit=.97,
           jpeg_min_exclusive=2, jpeg_max_exclusive=250, jpeg_channel_std_max=3,
           raw_crossframe_channel_relative_max=.06, raw_crossframe_exposure_EV_max=.08,
           spatial_buffer_pixels=32, grid='4x4; group 2x2 cells into four contiguous quadrant folds',
           fold_counts=np.bincount(result['fold'],minlength=4), training_subset_count=int(train.sum()),
           training_total_weight=24, thinning_rule='at most 80 uniformly spaced blocks per spatial cell',
           reference_input='Standard frame RAW only; pos/neg RAW only test same-location agreement',
           target_independent_selection=True))
    print('selection', counts, 'folds', np.bincount(result['fold']), 'fit subset', train.sum())


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('command', choices=('preflight','frame','select'))
    p.add_argument('--key', choices=tuple(FRAMES))
    args=p.parse_args()
    if args.command == 'preflight': preflight()
    elif args.command == 'frame': frame(args.key)
    else: bridges(); select()
