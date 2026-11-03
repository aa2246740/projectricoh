#!/usr/bin/env python3
"""Freeze task inputs, decode five held-out DNGs, and audit ten Standard inverses."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from support import *


SCENES = [
    'captures/a12-50/2026-10-16/S1b-sd-import/DCIM/100RICOH/R8051131.DNG',
    'captures/a12-50/2026-10-19/stage2c-first-run/R8051144.DNG',
    'captures/a12-50/2026-10-23/stage2l-daily-R8051219-1228/R8051219.DNG',
    'captures/a12-50/2026-10-23/stage2l-daily-R8051219-1228/R8051222.DNG',
    'captures/a12-50/2026-10-23/stage2l-daily-R8051219-1228/R8051225.DNG',
]


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--width', type=int, default=400)
    ap.add_argument('--samples', type=int, default=1400)
    args = ap.parse_args()
    preflight(); install_fence()
    import numpy as np
    from panasonic import StandardInverse, summary
    Camera, _, _, stats, Cube, samples, _, xyz_to_encoded = converter()
    c = Camera()
    out = LOCAL / 'prepared'
    out.mkdir(exist_ok=True)
    paths = [ROOT / p for p in SCENES]
    scenes = [c.scene(p, args.width) for p in paths]
    ref = scenes[0]
    x, sw = samples(c, args.samples, 151)
    tx, _ = samples(c, args.samples*2, 20261024)
    # The converter appends the same 77 greys to every call. Replace the test greys.
    tx = np.vstack([tx[:-77], np.repeat(c.curve.inverse(np.linspace(5.5, 250.5, 91))[:, None], 3, axis=1)])
    train_rows = set(map(tuple, x))
    unseen = np.array([tuple(row) not in train_rows for row in tx])
    shared_removed = int((~unseen).sum())
    tx = tx[unseen]
    ramp = np.repeat(c.curve.xs[:, None], 3, axis=1)
    data = {'train_x': x, 'train_stock': c.stock(x), 'train_weights': sw,
            'test_x': tx, 'test_stock': c.stock(tx), 'ramp_x': ramp, 'ramp_stock': c.stock(ramp)}
    for k, a in [('train', x), ('test', tx), ('ramp', ramp)]:
        data[k+'_vlog'] = xyz_to_encoded(c.xyz(a, ref['neutral'], ref['matrix']), 'vlog')
    meta = []
    for i, s in enumerate(scenes):
        xfull = s['x'].reshape(-1, 3)
        valid = np.flatnonzero(~s['clipped'].ravel())
        take = valid[np.linspace(0, len(valid)-1, min(3000, len(valid))).astype(int)]
        data[f'scene{i}_x'] = xfull
        data[f'scene{i}_shape'] = np.array(s['x'].shape)
        data[f'scene{i}_stock'] = c.stock(xfull)
        data[f'scene{i}_vlog'] = xyz_to_encoded(s['xyz'].reshape(-1, 3), 'vlog')
        data[f'scene{i}_take'] = take
        meta.append({**s['meta'], 'fit_role': 'whole-frame holdout; no real-scene pixels used in fitting',
                     'metric_samples': len(take), 'shape': s['x'].shape})
    np.savez_compressed(out/'dataset.npz', **data)
    dataset_sha256 = sha(out/'dataset.npz')
    inverse_sha256 = sha(HERE/'panasonic.py')
    dump(out/'scenes.json', meta)
    def de(a, b):
        return c.fs.delta_e00(c.fs.lab_from_codes(a), c.fs.lab_from_codes(b))
    manifest_path = DOWNLOAD/'Luts/Panasonic-Standard/manifest.json'
    manifest = json.loads(manifest_path.read_text())
    audit, models = {}, {}
    for entry in manifest['luts']:
        name = Path(entry['path']).stem.removesuffix('S2V')
        dest = out/(name+'.npz')
        docpath = out/(name+'.json')
        if (dest.exists() and docpath.exists() and
                json.loads(docpath.read_text()).get('dataset_sha256') == dataset_sha256 and
                json.loads(docpath.read_text()).get('inverse_code_sha256') == inverse_sha256):
            audit[name] = json.loads(docpath.read_text())
            with np.load(dest, allow_pickle=False) as z:
                models[name] = {k: z[k].copy() for k in z.files}
            print(name, 'reused verified prepared data', flush=True)
            continue
        cube_path = manifest_path.parent/entry['path']
        assert sha(cube_path) == entry['sha256']
        inv = StandardInverse(Cube.read(cube_path))
        result, boundaries = {}, {}
        for k in ('train', 'test', 'ramp'):
            vlog = data[k+'_vlog']
            rgb, residual = inv.invert(vlog)
            result[k] = rgb*255
            result[k+'_inverse_residual'] = residual
            boundaries[k] = inv.boundary(vlog, rgb, residual)
        for i in range(len(scenes)):
            take = data[f'scene{i}_take']
            # Full raster is needed for S1RII previews only; all bodies get the same held-out pixels.
            vlog = data[f'scene{i}_vlog']
            query = vlog if name == 'S1RII' else vlog[take]
            rgb, residual = inv.invert(query)
            result[f'scene{i}'] = rgb*255 if name == 'S1RII' else rgb*255
            result[f'scene{i}_inverse_residual'] = residual
            srgb = rgb[take] if name == 'S1RII' else rgb
            se = residual[take] if name == 'S1RII' else residual
            boundaries[f'scene{i}'] = inv.boundary(vlog[take], srgb, se)
        comparisons = {'synthetic': stats(de(data['test_stock'], result['test'])), 'scenes': []}
        all_s, calibrated_s = [], []
        for i, smeta in enumerate(meta):
            take = data[f'scene{i}_take']
            rgb = result[f'scene{i}'][take] if name == 'S1RII' else result[f'scene{i}']
            e = de(data[f'scene{i}_stock'][take], rgb)
            all_s.append(e)
            if smeta['model_calibrated_for_scene_iso']:
                calibrated_s.append(e)
            comparisons['scenes'].append({'scene': Path(smeta['path']).stem, **stats(e)})
        comparisons['all_scenes'] = stats(np.concatenate(all_s))
        comparisons['iso200_scenes'] = stats(np.concatenate(calibrated_s))
        document = {'name': name, 'upstream': entry, 'adapter_sha256': sha(cube_path),
                    'dataset_sha256': dataset_sha256,
                    'inverse_code_sha256': inverse_sha256,
                    'diagnostic': inv.diagnostic(c.fs), 'boundary': boundaries,
                    'difference_to_gxr04': comparisons,
                    'scene_array_scope': 'full' if name == 'S1RII' else 'metric_samples_only',
                    'inverse_method': 'tetrahedral Gauss-Newton, four starts, exact 27-active-set local box steps for hard cases',
                    'physical_camera_model_confirmed': False}
        np.savez_compressed(dest, **result)
        dump(docpath, document)
        audit[name], models[name] = jsonable(document), result
        print(name, 'inverse audit done; synthetic difference to 04 median',
              round(comparisons['synthetic']['median'], 3), flush=True)
    pairs = []
    for i, a in enumerate(models):
        for b in list(models)[i+1:]:
            es = []
            for j in range(len(scenes)):
                take = data[f'scene{j}_take']
                aa = models[a][f'scene{j}'][take] if a == 'S1RII' else models[a][f'scene{j}']
                bb = models[b][f'scene{j}'][take] if b == 'S1RII' else models[b][f'scene{j}']
                es.append(de(aa, bb))
            pairs.append({'a': a, 'b': b, 'synthetic': stats(de(models[a]['test'], models[b]['test'])),
                          'scenes': stats(np.concatenate(es))})
    dump(out/'model_comparison.json', {'models': audit, 'pairwise': pairs,
         'range_definition': 'ten published aliases; S5II/X and G9II/GH7 share numerical transforms',
         'recommended_comparison_body': 'S1RII',
         'not_a_probability_interval': True})
    # Record every data dependency used by the reused Engine and DNG reader.
    c.E.provenance.finish()
    dependencies = {Path(p) for p in c.E.provenance.before}
    for p in (ROOT/'research/lut_convert').glob('*.py'):
        dependencies.add(p)
    for p in (ROOT/'research/closed_loop/local/vendor').rglob('*'):
        if p.is_file():
            dependencies.add(p)
    dependencies |= set(paths) | set(ORIGINAL.iterdir()) | {manifest_path, ROOT/'artifacts/downloads/huzi-panasonic-std-luts-20261024/SHA256SUMS'}
    original_hashes = {}
    for line in (ROOT/'artifacts/downloads/huzi-panasonic-std-luts-20261024/SHA256SUMS').read_text().splitlines():
        h, name = line.split('  ', 1)
        assert sha(ORIGINAL/name) == h
        original_hashes[name] = h
    dump(LOCAL/'input_manifest.json', {'files': {str(Path(p).relative_to(ROOT)): sha(p) for p in sorted(dependencies)},
         'original_sha256_verified': original_hashes, 'source_commit': json.loads((DOWNLOAD/'commit.json').read_text())['sha'],
         'synthetic_train_n': len(x), 'synthetic_test_n': len(tx),
         'synthetic_exact_shared_input_rows': len(set(map(tuple, x)) & set(map(tuple, tx))),
         'shared_gray_input_rows_removed_from_test': shared_removed,
         'fit_uses_scene_pixels': False, 'reference_DNG_for_synthetic_xyz': SCENES[0],
         'fixed_middle_grey_anchor': c.anchor, 'model': c.description(),
         'all_metrics_evidence': 'host simulation; no new camera captures'})
    print('Prepared ten models and five whole-frame holdouts', flush=True)


if __name__ == '__main__':
    main()
