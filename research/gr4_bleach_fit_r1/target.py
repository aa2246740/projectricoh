#!/usr/bin/env python3
"""Measured GR IV Standard/Bleach pair interpolation; finite hull support, no style fallback.

Copied from gr4_nega_returns_r1/target.py. Changes: style negative -> bleach,
Bleach factory gate, band skipped when its Bleach colour holdout fails, and the
relative-chroma rule keeps the chroma ratio when the styled colour drops below C 8.
"""
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
import argparse
from bleach_main import bleach_defaults
from scipy.interpolate import LinearNDInterpolator
from scipy.spatial import cKDTree


def feature(uc):
    uc = np.maximum(np.asarray(uc), 1e-7)
    return np.stack([np.log2(uc @ np.array([.25, .5, .25])),
                     np.log2(uc[..., 0] / uc[..., 1]), np.log2(uc[..., 2] / uc[..., 1])], axis=-1)


def relative(base, standard, styled):
    # r7 / gr_pairs convention, except the chroma ratio stays active when only
    # the styled colour is near neutral: Bleach desaturates to C < 8, which the
    # original rule would map back to the full base chroma. Hue rotation still
    # needs C >= 8 on all three, as before.
    cs, cm, cb = [np.hypot(v[..., 1], v[..., 2]) for v in (standard, styled, base)]
    active = (cs >= 8) & (cm >= 8) & (cb >= 8)
    scaled = (cs >= 8) & (cb >= 8)
    ratio = np.where(scaled, cm / np.maximum(cs, 1e-6), 1.)
    quotient = np.ones_like(cs, dtype=complex)
    np.divide(styled[..., 1] + 1j * styled[..., 2], standard[..., 1] + 1j * standard[..., 2] + 1e-20,
              out=quotient, where=active)
    angle = np.where(active, np.angle(quotient), 0.)
    ab = (base[..., 1] + 1j * base[..., 2]) * ratio * np.exp(1j * angle)
    return np.stack([base[..., 0] + styled[..., 0] - standard[..., 0], ab.real, ab.imag], axis=-1)


def grouped(f, y):
    keys, inv = np.unique(np.round(f, 9), axis=0, return_inverse=True)
    counts = np.bincount(inv)
    values = np.column_stack([np.bincount(inv, weights=y[:, j]) / counts for j in range(y.shape[1])])
    return keys, values


class DenseTarget:
    def __init__(self):
        with np.load(rt.LOCAL / 'target/paired_measurements.npz', allow_pickle=False) as z:
            self.a = dict(z)
        self.info = rt.read('target/manifest.json')
        f, y = grouped(self.a['feature'], np.c_[self.a['standard'], self.a['bleach']])
        self.function = LinearNDInterpolator(f, y)
        self.tree = cKDTree(f)
        self.T = np.asarray(self.info['bridge']['T_white_balanced_neutral_normalized'])
        self.u118 = self.info['u118_raw_wb_without_BE']

    def labs(self, x):
        wb = np.asarray(x) @ self.T.T * (self.u118 / 320.)
        f = feature(wb)
        y = self.function(f)
        distance = self.tree.query(f)[0]
        supported = np.isfinite(y).all(axis=1) & (wb > 0).all(axis=1) & (distance <= 1.)
        return y[:, :3], y[:, 3:], supported, distance

    def target(self, x, base):
        standard, bleach, valid, distance = self.labs(x)
        return relative(np.asarray(base), standard, bleach), valid, distance


def prepare():
    m = rt.model()
    rb, a, common = rt.readback_modules()
    from predict import Renderer
    renderer = Renderer()
    cards = rb.cards('gr4')
    quality, values, references = {}, [], []
    all_inputs = {}
    for band in range(1, 5):
        ident = f'dense-band-{band}'
        path = rt.RETURNS / f'{ident}-analysis.json'
        d = rt.read(path)
        assert set(d['modes']) == {'standard', 'bleach'}
        manifest, card = cards[ident]
        all_inputs[str(path.relative_to(rt.ROOT))] = rt.sha(path)
        all_inputs[str(manifest.relative_to(rt.ROOT))] = rt.sha(manifest)
        q = dict(modes={}, paired_usable=0, total_colour=sum(p['role'] == 'colour' for p in card['patches']))
        by_style = {}
        for mode, state in d['modes'].items():
            rb.defaults(state['metadata'], mode) if mode == 'standard' else bleach_defaults(state['metadata'])
            pp = state['patches']
            sd = np.max(np.array([p['std'] for p in pp]), axis=1) * 255
            clip = np.array([p['clipped_fraction'] for p in pp])
            radial = state['radial']
            q['modes'][mode] = dict(patches=len(pp), flat=sum(p['spatially_flat'] for p in pp),
                std_max_channel_codes=rt.stats(sd), any_clipped_patches=int(np.any(clip > 0, axis=1).sum()),
                channel_clipped_fraction_mean=clip.mean(axis=0),
                radial_supported=sum(p['radial_supported'] for p in pp),
                alignment=state['alignment'], radial={k: v for k, v in radial.items()
                    if k not in ('reference_log2_u', 'reference_rgb_monotone')})
            colour = np.array([p['role'] == 'colour' for p in card['patches']])
            near = np.array([np.any(np.array(p['rgb_observed']) * 255 <= 1) or np.any(np.array(p['rgb_observed']) * 255 >= 254)
                             or max(p['clipped_fraction']) > 0 for p in pp])
            q['modes'][mode].update(colour_regions=int(colour.sum()), colour_near_clip=int((near & colour).sum()),
                                    all_regions_near_clip=int(near.sum()))
            assert radial['passed'], 'radial correction not accepted'
            if not radial['colour_holdout']['passed']:
                # Original analyze() already withdrew colour support; keep the band out of pairs.
                assert mode == 'bleach'
                q['excluded_from_pairs'] = 'Bleach radial colour holdout failed (original gate)'
            by_style[mode] = {p['id']: p for p in pp}
        errors, observed_errors, ref = [], [], []
        for patch in card['patches']:
            ss, sp = by_style['standard'][patch['id']], by_style['bleach'][patch['id']]
            if patch['role'] == 'reference':
                ref.append((patch['level'], ss['rgb_observed']))
            raw = np.array(patch['raw'])
            pred = renderer.render(raw[None], card['geometry']['neutral'], 'standard')[0]
            if patch['role'] == 'colour':
                observed_errors.append(float(m.de(np.array([pred]) * 255, np.array([ss['rgb_observed']]) * 255)[0]))
                if ss['radial_supported']:
                    errors.append(float(m.de(np.array([pred]) * 255, np.array([ss['rgb_center']]) * 255)[0]))
            if patch['role'] not in ('colour', 'tone', 'reference', 'natural'):
                continue
            valid = ss['radial_supported'] and sp['radial_supported'] and 'excluded_from_pairs' not in q
            # Do not promote channel-clipped means, even if a monotone inverse exists.
            valid &= max(ss['clipped_fraction'] + sp['clipped_fraction']) == 0
            if not valid:
                continue
            std = m.fs.lab_from_codes(np.array(ss['rgb_center']) * 255)
            pos = m.fs.lab_from_codes(np.array(sp['rgb_center']) * 255)
            wb = raw / np.array(card['geometry']['neutral'])
            values.append(dict(band=band, id=patch['id'], role=patch['role'], raw_wb=wb,
                standard=std, bleach=pos, standard_rgb=ss['rgb_center'], bleach_rgb=sp['rgb_center'],
                nominal_hue=patch.get('hue', -1), nominal_L=patch.get('L', -1),
                family=patch.get('family', patch['role'])))
            q['paired_usable'] += 1
        ref.sort(key=lambda v: v[0])
        level, rgb = np.array([p[0] for p in ref]), np.array([p[1] for p in ref])
        luma = rgb @ np.array([.2126, .7152, .0722]) * 255
        assert np.all(np.diff(luma) >= -1.5)
        from analyze import pava
        u118 = float(2 ** np.interp(118., pava(luma), np.log2(level)))
        references.append(u118)
        q['u118_raw_wb_without_BE'] = u118
        q['standard_vs_frozen_GRIII_prediction_center_DE00_D65'] = rt.stats(errors)
        q['standard_vs_frozen_GRIII_prediction_observed_DE00_D65'] = rt.stats(observed_errors)
        quality[ident] = q
    array = {k: np.array([v[k] for v in values]) for k in values[0]}
    array['feature'] = feature(array['raw_wb'])
    folder = rt.LOCAL / 'target'
    folder.mkdir(exist_ok=True)
    np.savez_compressed(folder / 'paired_measurements.npz', **array)
    bridge_cm = rt.module('dense_bridge_math', rt.ROOT / 'research/color_references/colour_math.py')
    _, source = rb.n.template('gr4')
    gxr = rb.n.Tiff((rt.ROOT / 'captures/a12-50/2026-10-19/stage2d-colorchecker/R8051150.DNG').read_bytes())
    B, info = bridge_cm.common_white_sensor_bridge(gxr.tags(), source.tags())
    mg, mr = np.array(info['M_gxr_xyz_to_camera']), np.array(info['M_gr_xyz_to_camera'])
    ng, nr = mg @ bridge_cm.D65, mr @ bridge_cm.D65
    ng, nr = ng / ng[1], nr / nr[1]
    T = np.diag(1 / nr) @ B @ np.diag(ng)
    T /= (T @ np.ones(3))[1]
    assert np.max(abs(T @ np.ones(3) - 1)) < 1e-10
    info['T_white_balanced_neutral_normalized'] = T
    manifest = dict(schema='gr4-dense-paired-target/1', styles=['standard', 'bleach'],
        diagnostic_styles_used=False, partial_MAIN=False, measured_patch_count=len(values),
        distinct_input_count=len(np.unique(np.round(array['feature'], 9), axis=0)),
        lab_white='D65, converted from measured sRGB; readback also retains its original D50 values',
        interpolation='linear tetrahedra in [log2 weighted WB RAW, log2 R/G, log2 B/G]; duplicate inputs averaged',
        support='inside measured convex hull, all positive RAW, nearest feature distance <=1; no fallback',
        target_transfer='r7 relative LCh; chroma ratio when source and base C>=8 (styled may be <8); hue rotation only when all three C>=8',
        u118_raw_wb_without_BE=float(np.median(references)), u118_per_band=references,
        u118_with_template_BE=float(np.median(references) * 2 ** source.geometry()['baseline_exposure']),
        anchor_is_convention=True, anchor_fit_uses_only_Standard_neutral_references=True,
        bridge=info, camera_acceptance=False, firmware_ready=False, inputs_sha256=all_inputs)
    rt.dump('target/manifest.json', manifest)
    rt.dump('target/quality.json', quality)
    coverage = []
    std = array['standard']
    C = np.hypot(std[:, 1], std[:, 2])
    h = np.degrees(np.arctan2(std[:, 2], std[:, 1])) % 360
    for lo in range(0, 360, 15):
        use = (h >= lo) & (h < lo + 15) & (C >= 8)
        coverage.append(dict(hue=[lo, lo+15], n=int(use.sum()),
            L_range=[float(std[use, 0].min()), float(std[use, 0].max())] if use.any() else None,
            C_range=[float(C[use].min()), float(C[use].max())] if use.any() else None))
    rt.dump('target/coverage.json', dict(total=len(std), neutral=int((C < 8).sum()), hue_bands=coverage,
        L_range=[float(std[:, 0].min()), float(std[:, 0].max())],
        C_range=[float(C.min()), float(C.max())]))
    print('paired target', len(values), 'u118 noBE / BE', manifest['u118_raw_wb_without_BE'],
          manifest['u118_with_template_BE'], flush=True)


def cross_validate():
    m = rt.model()
    d = DenseTarget()
    a = d.a
    f, y = a['feature'], np.c_[a['standard'], a['bleach']]
    std = a['standard']
    hue = np.degrees(np.arctan2(std[:, 2], std[:, 1])) % 360
    hue_group = (hue // 15).astype(int) % 3
    rows = []
    for kind, groups in [('page', a['band']), ('hue', hue_group)]:
        for group in np.unique(groups):
            test = groups == group
            # Identical RAW inputs on other pages must not enter interpolation training.
            held_keys = {tuple(v) for v in np.round(f[test], 9)}
            train = np.array([not held and tuple(v) not in held_keys
                              for held, v in zip(test, np.round(f, 9))])
            ff, yy = grouped(f[train], y[train])
            pred = LinearNDInterpolator(ff, yy)(f[test])
            valid = np.isfinite(pred).all(axis=1)
            observed = y[test][valid]
            rows.append(dict(scheme=kind, fold=int(group), train=int(train.sum()), test=int(test.sum()),
                interpolation_supported=int(valid.sum()), outside_training_hull=int((~valid).sum()),
                standard_de00=rt.stats(m.fs.delta_e00(pred[valid, :3], observed[:, :3])),
                bleach_de00=rt.stats(m.fs.delta_e00(pred[valid, 3:], observed[:, 3:])),
                duplicate_RAW_leakage=False))
    rt.dump('target/interpolation_holdouts.json', rows)
    for r in rows:
        print(r['scheme'], r['fold'], r['interpolation_supported'], r['bleach_de00'].get('median'), flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action', choices=['prepare', 'cv'])
    args = ap.parse_args()
    {'prepare': prepare, 'cv': cross_validate}[args.action]()
