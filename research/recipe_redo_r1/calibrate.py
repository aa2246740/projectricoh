"""Fit per-unit RAW-to-04 input maps, leaving complete date/light groups out."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
import argparse
import time
from PIL import Image
from scipy.optimize import least_squares
from gxr_studio.raw.dng import Dng
from gxr_studio.lut.scene import scene_colour

UNITS = {'a12-50': 0, 'mount-a12': 2}


def features(raw, degree=1):
    r, g, b = np.asarray(raw).T
    cols = [np.ones(len(raw)), r, g, b]
    if degree == 2:
        cols += [r*r, g*g, b*b, r*g, r*b, g*b]
    return np.column_stack(cols)


def apply(raw, coefficient):
    degree = 1 if len(coefficient) == 4 else 2
    return 4095 * (raw + features(raw, degree) @ coefficient)


def sample(record):
    key = record['sha256'][:20]
    target = rt.LOCAL / 'calibration_samples' / (key + '.npz')
    manifest = target.with_suffix('.json')
    if target.exists():
        info = rt.read(manifest)
        assert info['raw_sha256'] == record['sha256'], 'RAW cache identity mismatch'
        assert info['jpeg_sha256'] == record['jpeg_pairs'][0]['sha256'], 'Same RAW has a different companion JPEG'
        # A byte-identical file alias may have different scene provenance. Use
        # the admitted material row, rather than the first cache alias.
        info.update(path=record['path'], jpeg=record['jpeg_pairs'][0]['path'],
            scene_group=record['scene_group'], light_group=record['light_group'],
            stock04_status=record['stock04_status'], identity_evidence=record.get('identity_evidence'))
        return rt.arrays(target), info
    path = Path(record['path'])
    jp = Path(record['jpeg_pairs'][0]['path'])
    assert rt.sha(path) == record['sha256'] and rt.sha(jp) == record['jpeg_pairs'][0]['sha256']
    d = Dng(path)
    color = scene_colour(d)
    with Image.open(jp) as im:
        image = np.asarray(im.convert('RGB'))
        assert im.getexif().get(274, 1) == d.orientation and 1 <= d.orientation <= 8, 'RAW/JPEG stored orientations differ'
    y0, x0, h, w = d.crop_window()
    assert image.shape == (h, w, 3)
    # One fixed grid and 12x12 flat areas; no selection by prediction error.
    xx, yy = np.meshgrid(np.linspace(48, w-49, 40).astype(int), np.linspace(48, h-49, 28).astype(int))
    centers = np.c_[xx.ravel(), yy.ravel()]
    dx, dy = np.meshgrid(np.arange(-6, 6), np.arange(-6, 6))
    xs = centers[:, 0, None] + dx.ravel()[None, :]
    ys = centers[:, 1, None] + dy.ravel()[None, :]
    block = image[ys, xs].astype(float)
    observed, jpeg_sd = block.mean(1), block.std(1)
    candidates = []
    for shift in (-1, 0, 1):
        pixels = d.normalised_at(ys + y0, xs + x0 + shift)
        cfa = d.cfa_at(ys + y0, xs + x0 + shift)
        raw = np.column_stack([np.sum(np.where(cfa == k, pixels, 0), axis=1) / np.sum(cfa == k, axis=1) for k in range(3)])
        candidates.append(raw)
    # Fixed -1 offset follows existing independent registration evidence for
    # these GXR carriers. Other offsets are retained as registration diagnostics.
    shift = -1
    raw = candidates[shift+1]
    pixels = d.normalised_at(ys+y0, xs+x0+shift)
    cfa = d.cfa_at(ys+y0, xs+x0+shift)
    maximum = np.column_stack([np.max(np.where(cfa == k, pixels, -1), axis=1) for k in range(3)])
    raw_sd = np.column_stack([np.sqrt(np.sum(np.where(cfa == k, (pixels-raw[:, k, None])**2, 0), axis=1)
                           / np.sum(cfa == k, axis=1)) for k in range(3)])
    valid = ((maximum < .98).all(1) & (raw > .0005).all(1)
             & (observed > 3).all(1) & (observed < 252).all(1)
             & (jpeg_sd.max(1) < 10) & (raw_sd.max(1) < .025))
    raw_wb = raw / d.as_shot_neutral
    values = dict(raw=raw, raw_wb=raw_wb, observed=observed, valid=valid, centers=centers,
        raw_sd=raw_sd, jpeg_sd=jpeg_sd, neutral=color.neutral, matrix=color.matrix,
        xyz=color.xyz(raw_wb*4095), shifted_raw=np.stack(candidates), max_raw=maximum)
    info = dict(path=str(path), raw_sha256=d.sha256, jpeg=str(jp), jpeg_sha256=rt.sha(jp),
        scene_group=record['scene_group'], light_group=record['light_group'], unit=record['unit'], iso=record['iso'],
        samples_total=len(raw), samples_valid=int(valid.sum()), raw_jpeg_shift_xy=[shift, 0],
        registration_source='previous carrier registration; fixed before calibration, three-offset sensitivity retained',
        raster_orientation=d.orientation, identical_raw_jpeg_orientation=True,
        stored_raster_dimensions_equal=True, no_exif_display_rotation_applied_to_sampling=True,
        dng_summary=d.summary(), wb_user_offsets=record.get('wb_user_offsets'),
        identity_evidence=record.get('identity_evidence'), stock04_status=record['stock04_status'],
        no_per_frame_exposure_fit=True, no_per_frame_wb_fit=True,
        mask_rule='RAW maximum<0.98, mean>0.0005, JPEG 3..252, JPEG sd<10, RAW sd<0.025')
    target.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(target, **values)
    rt.dump(manifest, info)
    d.release()
    return values, info


def central_mask(values, info, fraction=.6):
    """Keep complete 12x12 blocks inside the fixed central width and height."""
    width,height=info['dng_summary']['default_crop_size_wh']
    centers=values['centers'];margin=(1-fraction)/2
    # RAW registration is fixed at -1 in x; include that extra left pixel.
    return ((centers[:,0]-7>=width*margin)&(centers[:,0]+5<width*(1-margin))
            &(centers[:,1]-6>=height*margin)&(centers[:,1]+5<height*(1-margin)))


def prepare(unit):
    rows = [r for r in rt.read(rt.LOCAL / 'materials.json') if r['unit'] == unit
            and r['calibration_role'] in ('primary_iso200', 'high_iso_diagnostic')]
    seen, data, infos = set(), [], []
    for row in rows:
        if row['sha256'] in seen:
            continue
        seen.add(row['sha256'])
        values, info = sample(row)
        if row['calibration_role'] == 'primary_iso200':
            good = values['valid'].copy()
            if unit=='mount-a12':good &= central_mask(values,info)
            assert good.sum() >= 10, 'Insufficient valid flat samples'
            info.update(prepared_sample_count=int(good.sum()),
                prepared_region='central60' if unit=='mount-a12' else 'legacy_full_frame',
                minimum_edge_margin_fraction=.2 if unit=='mount-a12' else None)
            data.append(dict(raw=values['raw_wb'][good], observed=values['observed'][good],
                xyz=values['xyz'][good], jpeg_sd=values['jpeg_sd'][good],
                centers=values['centers'][good],
                group=np.full(good.sum(), row['scene_group']), frame=np.full(good.sum(), Path(row['path']).stem)))
        infos.append(info)
        print('sample', Path(row['path']).stem, row['iso'], info['samples_valid'], flush=True)
    pooled = {k: np.concatenate([a[k] for a in data]) for k in data[0]}
    out = rt.LOCAL / 'calibration' / unit
    out.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out / 'dataset.npz', **pooled)
    rt.dump(out / 'frames.json', infos)
    return pooled


def fit(unit, holdout, degree, max_nfev, exclude_groups=(), prefix='', initial_coefficients=None):
    output = rt.LOCAL / 'calibration' / unit
    data = rt.arrays(output / 'dataset.npz')
    groups = sorted(set(data['group']))
    # Eligibility does not change the natural session's assigned outer split.
    natural='mount_natural_20261103_whole_collection'
    decision=rt.HERE/'local/new7/owner_identity_decision.json'
    if unit=='mount-a12' and natural in groups and holdout!=natural and decision.exists():
        if not rt.read(decision).get('used_for_current_04_training',False):
            exclude_groups=tuple(sorted(set(exclude_groups)|{natural}))
    assert holdout in groups or holdout == 'full'
    train = (data['group'] != holdout) & ~np.isin(data['group'], exclude_groups)
    held = data['group'] == holdout
    H = features(data['raw'], degree)
    assert np.linalg.matrix_rank(H[train]) == H.shape[1]
    # Equal total weight per date/light group and per frame prevents screen-page
    # or repeated-shot counts from defining the chosen response.
    sw = np.zeros(len(H))
    for group in groups:
        frames = np.unique(data['frame'][data['group'] == group])
        for frame in frames:
            use = (data['group'] == group) & (data['frame'] == frame)
            sw[use] = 1 / (len(frames) * use.sum())
    sw /= sw[train].mean()
    weight = np.sqrt(sw / (1 + data['jpeg_sd'].mean(1)**2))
    c = rt.Camera(UNITS[unit])
    transferred = rt.Camera(UNITS[unit], transferred=True)
    x = data['raw'] * 4095
    # No inverse-root or label selection on the held-out group.
    C0 = np.zeros((H.shape[1], 3)) if initial_coefficients is None else np.asarray(initial_coefficients,float)
    assert C0.shape==(H.shape[1],3)
    def residual(flat):
        C = flat.reshape(C0.shape)
        candidate = apply(data['raw'][train], C)
        rgb = c.stock(candidate)
        return np.r_[((rgb-data['observed'][train])*weight[train, None]).ravel(),
                     (C[1:]*.10).ravel(), (C[:1]*2).ravel()]
    start = time.monotonic()
    opt = least_squares(residual, C0.ravel(), max_nfev=max_nfev, diff_step=1e-4,
        ftol=2e-7, xtol=2e-7, gtol=1e-5)
    coefficient = opt.x.reshape(C0.shape)
    predicted = c.stock(apply(data['raw'], coefficient))
    baseline = transferred.stock(x)
    unit_uncorrected = c.stock(x)
    legacy = rt.read(rt.source_copy('research/refit_50mm_r7/local/folds/full/calibration.json'))
    legacy_pred = c.stock(apply(data['raw'], np.asarray(legacy['residual_coefficients'])))
    per_group = {}
    for group in groups:
        use = data['group'] == group
        def error(pred):
            return rt.stats(rt.delta_e00(rt.lab_from_codes(pred[use]), rt.lab_from_codes(data['observed'][use])))
        per_group[group] = dict(role='excluded_outer_holdout' if group in exclude_groups else 'holdout' if group == holdout else 'train',
            transferred_50mm=error(baseline), unit_uncorrected=error(unit_uncorrected),
            legacy_50mm_input_map=error(legacy_pred), recalibrated=error(predicted), frames=sorted(set(data['frame'][use])))
    doc = dict(label='电脑预测，与相机原厂 Standard JPEG 比较', unit=unit, holdout_group=holdout,
        degree=degree, coefficients=coefficient, group_scores=per_group,
        solver=dict(success=bool(opt.success), nfev=int(opt.nfev), seconds=time.monotonic()-start,
                    message=opt.message), n_train=int(train.sum()), n_holdout=int(held.sum()),
        training_objective_weighted_rgb_plus_regularization=float(2*opt.cost),
        training_groups=[g for g in groups if g != holdout and g not in exclude_groups],
        excluded_groups=list(exclude_groups), condition=float(np.linalg.cond(H[train])),
        raw_train_min=data['raw'][train].min(0), raw_train_max=data['raw'][train].max(0),
        calibration_location='native normalized RAW / per-image AsShotNeutral, before type26',
        full_scene_holdout=True, heldout_used_for_fit=False, unknown_wb_offsets=True,
        kernel='original unit sector words and native five-colour modifiers; 50mm measured angular kernel transferred',
        input_xyz_definition='per-image DNG metadata; 50mm middle-gray photometric anchor remains a declared assumption',
        primary_eligible=(degree == 1), camera_acceptance=False)
    rt.dump(output / f'{prefix}{holdout}_degree{degree}.json', doc)
    np.savez_compressed(output / f'{prefix}{holdout}_degree{degree}.npz', predicted=predicted, baseline=baseline,
                        unit_uncorrected=unit_uncorrected, legacy_50mm=legacy_pred, train=train, held=held)
    print(unit, holdout, degree, doc['solver'], flush=True)
    for group, row in per_group.items():
        print(group, row['role'], 'DE00', row['transferred_50mm']['median'], '->', row['recalibrated']['median'], flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('action', choices=('prepare', 'fit'))
    ap.add_argument('--unit', choices=tuple(UNITS), required=True)
    ap.add_argument('--holdout', default='full')
    ap.add_argument('--degree', type=int, choices=(1, 2), default=1)
    ap.add_argument('--max-nfev', type=int, default=35)
    ap.add_argument('--exclude-groups',default='')
    args = ap.parse_args()
    if args.action == 'prepare':
        prepare(args.unit)
    else:
        fit(args.unit, args.holdout, args.degree, args.max_nfev,
            exclude_groups=tuple(p for p in args.exclude_groups.split(',') if p))


if __name__ == '__main__':
    main()
