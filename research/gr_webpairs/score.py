"""Frozen round5 scoring against independent observed style JPEGs. No fitting."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from core import ROOT, HERE, LOCAL, guard, read, dump, load, modules
import argparse
import ast
import csv
import inspect
import json
import types
import numpy as np


def runtime():
    # Import read-only gr_pairs model code. Its output functions are never called.
    p = load('webpairs_frozen_refit', ROOT / 'research/gr_pairs/refit.py')
    ns = dict(np=np, FS=p.FS)
    path = ROOT / 'research/color_fit_v2/gr_dense_t1/runtime.py'
    tree = ast.parse(path.read_text())
    defs = ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef)
                           and n.name in ('stats', 'score')], type_ignores=[])
    exec(compile(defs, str(path), 'exec'), ns)
    r = types.SimpleNamespace(P=p, FS=p.FS, stats=ns['stats'], score=ns['score'])
    path = ROOT / 'research/color_fit_v2/gr_dense_t1/analyze_dense.py'
    tree = ast.parse(path.read_text())
    defs = ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef)
                           and n.name == 'decomposition'], type_ignores=[])
    ns = dict(r=r, np=np, inspect=inspect)
    exec(compile(defs, str(path), 'exec'), ns)
    r.decomposition = ns['decomposition']
    r.generator = p.G.GRGenerator(ROOT / 'artifacts/downloads/bastibe-gr3')
    return r


def bridge(meta, family, anchor=None):
    gr, cm, meas, tn = modules()
    source = ROOT / 'captures/a12-50/2026-10-19/stage2d-colorchecker/R8051150.DNG'
    t = gr.load_tiff(source)
    _, _, _, root, _ = tn.maker_note_bytes(t)
    raw = next(meas.tag_map(e) for e in [root] + meas.subifds(t, root)
               if meas.scalar(meas.tag_map(e).get(262)) == 32803)
    gx = {k: v['value'] for k, v in {**meas.tag_map(root), **raw}.items()}
    tags = {int(k): v for k, v in meta['raw']['tags'].items()}
    B, info = cm.common_white_sensor_bridge(gx, tags)
    mg, mr = np.asarray(info['M_gxr_xyz_to_camera']), np.asarray(info['M_gr_xyz_to_camera'])
    ng, nr = mg @ cm.D65, mr @ cm.D65
    ng, nr = ng / ng[1], nr / nr[1]
    T = np.diag(1 / nr) @ B @ np.diag(ng)
    T /= (T @ np.ones(3))[1]
    assert np.max(abs(T @ np.ones(3) - 1)) < 1e-10
    anchors = read(ROOT / 'research/gr4_modes/local/candidates.json')['gr4_standard_118_u_c']
    u118 = (.08577678 if family in ('gr3', 'gr3x') else anchors['pooled_gruser_dr_off']) if anchor is None else anchor
    info.update(u118=u118, sensor_mapping='common-white ColorMatrix inference',
                exposure='existing 118 convention, unmeasured for the new body',
                standard_model='gr3 existing joint/pooled' if family != 'gr4' else 'existing GR IV HDF Standard, different body')
    return T, u118, info


def selected(d):
    key = np.floor(d['features'] / np.array([.12, .04, .04])).astype(int)
    _, inverse = np.unique(key, axis=0, return_inverse=True)
    order = np.lexsort((-d['weight'], inverse))
    _, first = np.unique(inverse[order], return_index=True)
    select = order[first]
    if len(select) > 1600:
        select = select[np.linspace(0, len(select) - 1, 1600, dtype=int)]
    return select


def assess(r, target, pred, base):
    return dict(score=r.score(target, pred, base), residual=r.decomposition(target, pred))


def strata(r, target, pred, base):
    L, C, h = r.FS.lch(base)
    error = r.FS.delta_e00(target, pred)
    energy = float(np.sum(error ** 2))
    result = []
    masks = [('neutral', -1, C < 8)]
    masks += [('hue', lo, (C >= 8) & (h >= lo) & (h < lo + 30)) for lo in range(0, 360, 30)]
    masks += [('lightness', lo, (L >= lo) & ((L < lo + 20) if lo < 80 else True)) for lo in range(0, 100, 20)]
    masks += [('hue_lightness', lo * 100 + ll, (C >= 8) & (h >= lo) & (h < lo + 30) &
               (L >= ll) & ((L < ll + 20) if ll < 80 else True)) for lo in range(0, 360, 30)
              for ll in range(0, 100, 20)]
    for kind, lo, mask in masks:
        rec = dict(kind=kind, start=lo, **r.score(target[mask], pred[mask], base[mask]))
        rec['squared_error_share'] = float(np.sum(error[mask] ** 2) / energy) if energy else 0
        if mask.any():
            dec = r.decomposition(target[mask], pred[mask])
            rec['signed_delta_L_median'] = dec['signed_delta_L_median']
            rec['median_abs_delta_C'] = dec['abs_delta_C']['median']
            rec['median_abs_delta_hue_deg'] = dec['abs_delta_hue_deg']['median']
            rec['exact_squared_DE00_energy_fraction'] = dec['exact_squared_DE00_energy_fraction']
        result.append(rec)
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--frame', required=True)
    p.add_argument('--inventory', type=Path, required=True)
    p.add_argument('--anchor', type=float)
    p.add_argument('--suffix', default='')
    a = p.parse_args()
    guard()
    f = next(f for f in read(a.inventory) if f['id'] == a.frame)
    r = runtime()
    slot = '02' if f['mode'] == 'negative' else '01'
    group = 'gr4_hdf' if f['family'] == 'gr4' else 'gr3'
    transfer = r.P.Transfer(group, f['mode'], r.P.G, r.generator)
    meta = read(LOCAL / 'samples' / (f['id'] + '.json'))
    assert meta['registration']['geometry_confirmed']
    with np.load(LOCAL / 'samples' / (f['id'] + '.npz'), allow_pickle=False) as z:
        d = dict(z)
    take = selected(d)
    T, u118, info = bridge(meta, f['family'], a.anchor)
    x = d['uc'][take] @ np.linalg.inv(T).T * (320 / u118)
    D = r.P.data_of(slot, 200)
    rgb04 = r.P.rgb04(D, x)
    base = r.FS.lab_from_codes(rgb04)
    std, _, ignored_style_support, standard_support, confidence = transfer.labs(x)
    styled = r.P.CM.rgb_lab(d['jpeg'][take] / 255)
    target = r.P.apply_relative(base, std, styled)
    valid = (x > 0).all(axis=1) & (x < 4095).all(axis=1)
    valid &= (rgb04 > 2).all(axis=1) & (rgb04 < 253).all(axis=1)
    eligible = valid.copy()
    valid &= standard_support
    out = dict(id=f['id'], group=f['group'], slot=slot, default_parameters=f['default_parameters'],
               holdout='entire unseen RAW, fixed recipe and fixed Standard models', bridge=info,
               source_points=len(d['uc']), feature_thinned_points=len(take),
               physically_eligible_points=int(eligible.sum()), supported_points=int(valid.sum()),
               excluded_unsupported_standard=int((eligible & ~standard_support).sum()),
               reference_group=group, models={})
    arrays = dict(x=x, target=target, base=base, valid=valid, eligible=eligible,
                  standard=std, style_observed=styled, xy=d['xy'][take],
                  source_scene_lab=d['scene_lab'][take])
    for iso in (200, 1600):
        DD = r.P.data_of(slot, iso)
        pred = r.P.prediction(DD, DD.current, x)
        arrays['pred' + str(iso)] = pred
        sc = assess(r, target[valid], pred[valid], base[valid])
        sc['strata'] = strata(r, target[valid], pred[valid], base[valid])
        if (eligible & ~standard_support).any():
            sc['unsupported_standard_proxy_diagnostic'] = r.score(
                target[eligible & ~standard_support], pred[eligible & ~standard_support],
                base[eligible & ~standard_support])
        out['models'][str(iso)] = sc
        print(json.dumps(dict(id=f['id'], iso=iso, **sc['score'])))
    if f['standalone_jpeg']:
        from metadata import embedded
        from PIL import Image
        from scipy.ndimage import uniform_filter
        import io
        with Image.open(io.BytesIO(embedded(ROOT / f['dng']))) as im:
            half = modules()[0].half(np.asarray(im.convert('RGB')))
        xx, yy = d['xy'][take].T
        embedded_rgb = np.column_stack([uniform_filter(half[..., c], 5)[yy, xx] for c in range(3)])
        embedded_lab = r.P.CM.rgb_lab(embedded_rgb / 255)
        alternate = r.P.apply_relative(base, std, embedded_lab)
        out['embedded_same_coordinates_sensitivity'] = {str(iso): r.score(alternate[valid],
            arrays['pred' + str(iso)][valid], base[valid]) for iso in (200, 1600)}
        arrays['embedded_target'] = alternate
    with (LOCAL / ('scores_' + f['id'] + a.suffix + '.npz')).open('wb') as h:
        np.savez_compressed(h, **arrays)
    dump(HERE / ('scores_' + f['id'] + a.suffix + '.json'), out)


if __name__ == '__main__':
    main()
