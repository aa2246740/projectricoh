"""Freeze per-unit input definitions and complete-scene photo splits."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
from gxr_studio.raw.dng import Dng
from gxr_studio.lut.scene import scene_colour
import collections
import argparse

UNITS = ('a12-50', 'a12-28', 'mount-a12')
PRIMARY_CALIBRATION = {'a12-50': '50mm_native_physical_20261026_degree2', 'mount-a12': 'mount_screen_20261101_degree1'}


def sample(record):
    key = record['sha256'][:20]
    path = rt.LOCAL / 'raw_samples' / (key + '.npz')
    if path.exists():
        info = rt.read(path.with_suffix('.json'))
        info.update({k: record.get(k) for k in ('path', 'unit', 'iso', 'when', 'date_group', 'light_group', 'scene_group', 'stock04_status')})
        return rt.arrays(path), info
    d = Dng(record['path'])
    assert d.sha256 == record['sha256']
    color = scene_colour(d)
    y0, x0, h, w = d.crop_window()
    width, height = 32, max(2, round(h*32/w))
    ys = y0 + 2*np.linspace(0, (h-2)//2, height).astype(int)
    xs = x0 + 2*np.linspace(0, (w-2)//2, width).astype(int)
    yy, xx = np.meshgrid(ys, xs, indexing='ij')
    raw, count = np.zeros((height, width, 3)), np.zeros((height, width, 3))
    clipped = np.zeros((height, width), bool)
    for dy in (0, 1):
        for dx in (0, 1):
            value = d.normalised_at(yy+dy, xx+dx)
            color_index = d.cfa_at(yy+dy, xx+dx)
            clipped |= value >= .98
            for channel in range(3):
                mask = color_index == channel
                raw[..., channel] += value*mask
                count[..., channel] += mask
    raw /= count
    raw_codes = (raw/d.as_shot_neutral*4095).reshape(-1, 3)
    xyz = color.xyz(raw_codes)
    valid = (~clipped).ravel() & np.isfinite(xyz).all(1)
    take = np.flatnonzero(valid)
    take = take[np.linspace(0, len(take)-1, min(96, len(take))).astype(int)] if len(take) else take
    out = dict(raw_codes=raw_codes[take], xyz=xyz[take], neutral=color.neutral, matrix=color.matrix)
    info = {k: record.get(k) for k in ('path', 'sha256', 'unit', 'iso', 'when', 'date_group', 'light_group', 'scene_group', 'stock04_status')}
    info.update(samples_total=len(valid), sampled=len(take), clipped_share=float(clipped.mean()),
                original_jpeg_used_for_target_or_identity=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **out)
    rt.dump(path.with_suffix('.json'), info)
    d.release()
    return out, info


def inverse_input(x, coefficient):
    C = np.asarray(coefficient)
    raw = (np.asarray(x)/4095-C[0]) @ np.linalg.inv(np.eye(3)+C[1:4])
    if len(C) == 10:
        for _ in range(16):
            residual = rt.calibration_apply(raw, C)/4095-np.asarray(x)/4095
            if abs(residual).max() < 1e-12:
                break
            r, g, b = raw.T
            derivative = np.zeros((len(raw), 10, 3))
            derivative[:, 1:4] = np.eye(3)
            derivative[:, 4, 0], derivative[:, 5, 1], derivative[:, 6, 2] = 2*r, 2*g, 2*b
            derivative[:, 7, 0], derivative[:, 7, 1] = g, r
            derivative[:, 8, 0], derivative[:, 8, 2] = b, r
            derivative[:, 9, 1], derivative[:, 9, 2] = b, g
            jac = np.eye(3)[None] + np.einsum('nfi,fo->noi', derivative, C)
            assert (np.linalg.det(jac) > 0).all(), 'Input-map inverse folded'
            raw -= np.linalg.solve(jac, residual[..., None])[..., 0]
    assert abs(rt.calibration_apply(raw, C)-x).max() < 1e-6, 'Input-map inverse did not close'
    return 4095*raw


def synthetic(camera, n, seed):
    rng = np.random.default_rng(seed)
    x = camera.curve.inverse(rng.uniform(8, 247, (n*2, 3)))
    base = camera.stock(x)
    x = x[np.all((base > 3) & (base < 252), axis=1)][:n]
    gray = np.repeat(camera.curve.inverse(np.linspace(4, 251, 77))[:, None], 3, axis=1)
    return np.vstack([x, gray]), np.r_[np.ones(len(x)), np.full(77, 4.)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--units', nargs='+', choices=UNITS, default=list(UNITS))
    args = parser.parse_args()
    rows = rt.read(rt.LOCAL / 'materials.json')
    # This split is frozen before any recipe fitting. Dates are camera EXIF
    # dates, not folder dates; whole capture folders remain on one side.
    sources, seen = [], set()
    rejected_payloads = {r.get('sensor_payload_sha256', r['sha256']) for r in rows
                         if r['calibration_role'] == 'excluded_owner_rejected_capture'}
    priority = lambda r: (r['calibration_role'] != 'primary_iso200', r['source_collection'] == 'Downloads', r['path'])
    for row in sorted(rows, key=priority):
        exposure = row.get('sensor_payload_sha256', row['sha256'])
        if row['unit'] not in args.units or exposure in seen or row.get('sensor_identity_unit_conflict') or row.get('exclude_from_recipe_photo_holdout'):
            continue
        seen.add(exposure)
        if exposure in rejected_payloads:
            continue
        sources.append(row)
    sampled = []
    for i, row in enumerate(sources):
        if row['unit'] == 'a12-28':
            # Unpaired metadata is not a photograph holdout or a 04 calibration.
            continue
        values, info = sample(row)
        if len(values['raw_codes']):
            sampled.append((row, values, info))
        if i % 75 == 0:
            print('RAW sampling', i, '/', len(sources), flush=True)
    protocol_path = rt.HERE/'input_protocol.json'
    manifest = rt.read(protocol_path)['units'] if protocol_path.exists() else {}
    for ui, unit in enumerate(UNITS):
        if unit not in args.units:
            continue
        camera = rt.Camera(ui)
        if unit in PRIMARY_CALIBRATION:
            calibration = rt.read(rt.LOCAL / 'calibration' / unit / (PRIMARY_CALIBRATION[unit]+'.json'))
            C = np.asarray(calibration['coefficients'])
            reference_record = next(r for r in sources if r['unit'] == unit and r['calibration_role'] == 'primary_iso200'
                                    and r['scene_group'] in calibration['training_groups'])
            reference, _ = sample(reference_record)
            coefficients_source = 'local/calibration/'+unit+'/'+PRIMARY_CALIBRATION[unit]+'.json'
        else:
            reference_record = next(r for r in sources if r['unit'] == unit)
            d = Dng(reference_record['path'])
            col = scene_colour(d)
            reference = dict(neutral=col.neutral, matrix=col.matrix)
            d.release()
            C = np.zeros((4, 3))
            coefficients_source = 'none; no usable paired 28mm 04 calibration'
        definition = dict(unit=unit, calibration_coefficients=C,
            calibration_source=coefficients_source, reference_raw_path=reference_record['path'],
            reference_raw_sha256=reference_record['sha256'], neutral=reference['neutral'], matrix=reference['matrix'],
            middle_gray_anchor=camera.anchor, anchor_scope='existing 50mm measured anchor; no independent physical colorimetric truth',
            metadata_only_reference=True, target_style_pixels_used=False,
            no_observed_28mm_response=unit == 'a12-28')
        output = rt.LOCAL / 'inputs' / unit
        output.mkdir(parents=True, exist_ok=True)
        rt.dump(output / 'definition.json', definition)
        trainx, sw = synthetic(camera, 700, 151)
        testx, _ = synthetic(camera, 1400, 20261023)
        seen_train = {tuple(np.round(x, 9)) for x in trainx}
        testx = np.array([x for x in testx if tuple(np.round(x, 9)) not in seen_train])
        def syn_group(x, weight=None):
            raw = inverse_input(x, C)
            return dict(x=x, raw_codes=raw, xyz=camera.xyz(raw, reference['neutral'], reference['matrix']),
                        sw=np.ones(len(x)) if weight is None else weight,
                        photo_id=np.full(len(x), -1, int), iso=np.full(len(x), 200, int))
        groups = {'train': syn_group(trainx, sw), 'synthetic': syn_group(testx)}
        photos = []
        train_scenes = collections.defaultdict(list)
        held_iso200, held_other = [], []
        response_directories = {str(Path(r['path']).parent) for r in sources
                                if r['unit'] == unit and r['calibration_role'] == 'primary_iso200'}
        early_training_directories = {str(Path(r['path']).parent) for r, _, _ in sampled
            if r['unit'] == unit and r['iso'] == 200 and str(r.get('when') or '')[:10]
            <= ('2026:10:20' if ui == 0 else '2026:10:24')}
        for row, a, info in sampled:
            if row['unit'] != unit:
                continue
            # ISO100 bypasses A5 in the actual camera; not scored under A5.
            if row['iso'] == 100:
                photos.append({**info, 'role': 'excluded_ISO100_curve_bypass'})
                continue
            early = str(row.get('when') or '')[:10] <= ('2026:10:20' if ui == 0 else '2026:10:24')
            used_for_response = str(Path(row['path']).parent) in response_directories
            if early and row['iso'] == 200:
                train_scenes[row['scene_group']].append((row, a, info))
            elif used_for_response:
                photos.append({**info, 'role': 'response_calibration_only'})
            elif str(Path(row['path']).parent) in early_training_directories:
                photos.append({**info, 'role': 'training_scene_other_iso_diagnostic'})
            elif row['iso'] == 200:
                held_iso200.append((row, a, info))
            else:
                held_other.append((row, a, info))
        selected_train = []
        for scene, candidates in sorted(train_scenes.items()):
            ix = np.linspace(0, len(candidates)-1, min(3, len(candidates))).astype(int)
            selected_train.extend(candidates[i] for i in ix)
        for row, a, info in selected_train:
            take = np.linspace(0, len(a['raw_codes'])-1, min(64, len(a['raw_codes']))).astype(int)
            raw = a['raw_codes'][take]
            addition = dict(x=rt.calibration_apply(raw/4095, C), raw_codes=raw, xyz=a['xyz'][take],
                            sw=np.ones(len(raw)), photo_id=np.full(len(raw), len(photos), int),
                            iso=np.full(len(raw), row['iso'], int))
            groups['train'] = {k: np.concatenate([groups['train'][k], addition[k]]) for k in groups['train']}
            photos.append({**info, 'role': 'recipe_train'})
        for name, candidates in [('photo_iso200', held_iso200), ('photo_other_iso', held_other)]:
            values = []
            for row, a, info in candidates:
                raw = a['raw_codes']
                values.append(dict(x=rt.calibration_apply(raw/4095, C), raw_codes=raw, xyz=a['xyz'],
                    sw=np.ones(len(raw)), photo_id=np.full(len(raw), len(photos), int),
                    iso=np.full(len(raw), row['iso'], int)))
                photos.append({**info, 'role': name})
            groups[name] = {k: np.concatenate([v[k] for v in values]) if values else np.empty((0, 3))
                           if k in ('x', 'raw_codes', 'xyz') else np.empty(0) for k in groups['train']}
        train_groups = {p['scene_group'] for p in photos if p['role'] == 'recipe_train'}
        held_groups = {p['scene_group'] for p in photos if p['role'].startswith('photo_')}
        assert not train_groups & held_groups
        for name, values in groups.items():
            np.savez_compressed(output / (name+'.npz'), **values)
        rt.dump(output / 'photos.json', photos)
        manifest[unit] = dict(groups={k: len(v['x']) for k, v in groups.items()},
            photo_roles=dict(collections.Counter(p['role'] for p in photos)),
            train_scenes=sorted(train_groups), holdout_scenes=sorted(held_groups),
            source_photos=len(photos), all_parameters_selected_without_photo_holdout=True,
            response_holdout=PRIMARY_CALIBRATION.get(unit),
            only_synthetic=unit == 'a12-28',
            high_iso_scores_are_transfer_diagnostics=True)
        print(unit, manifest[unit], flush=True)
    rt.dump('input_protocol.json', dict(label='电脑预测', units=manifest,
        scene_holdout='Complete capture/date/light groups, exact duplicate RAW hashes removed',
        synthetic_exact_train_duplicate_points_removed=True,
        unknown_daily_jpegs_used_as_standard=False, created_utc=rt.utc()))


if __name__ == '__main__':
    main()
