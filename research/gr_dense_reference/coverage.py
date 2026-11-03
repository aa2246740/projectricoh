#!/usr/bin/env python3
"""Publish aggregate coverage only; never publish designed point coordinates."""
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import dense
common = dense.legacy()
from collections import Counter
import numpy as np
import lattice


def mapping_checks(cards):
    from predict import Renderer
    cm, renderer = common.colour(), Renderer()
    by_point = {}
    lightness_errors = []
    for card in cards:
        name = Path(card['dng_path']).stem
        mapped = {p['id']: p for p in dense.read(dense.LOCAL / 'mapped' / f'{name}.json')}
        for p in card['patches']:
            if p.get('family') != 'lch':
                continue
            actual = mapped[p['id']]['decoded_gain_corrected_camera_rgb']
            rgb = renderer.render(actual, card['geometry']['neutral'], 'standard')
            lab = cm.xyz_lab(cm.srgb_decode(rgb) @ cm.SRGB_XYZ.T, cm.D65)
            by_point[(p['hue'], p['L'], p['saturation_fraction'])] = lab
            lightness_errors.append(abs(float(lab[0]) - p['L']))
    l_steps, c_steps = [], []
    for hue in lattice.HUES:
        for f in lattice.FRACTIONS:
            l_steps.extend(np.diff([by_point[(hue, L, f)][0] for L in lattice.LIGHTNESS]))
        for L in lattice.LIGHTNESS:
            c_steps.extend(np.diff([np.hypot(*by_point[(hue, L, f)][1:]) for f in lattice.FRACTIONS]))
    dense.require(min(l_steps) > 0 and min(c_steps) > 0, 'decoded L/chroma ordering reversed')
    dense.require(max(lightness_errors) < .15, 'decoded model Standard misses designed lightness')
    return dict(passed=True, points=len(by_point), minimum_lightness_step=float(min(l_steps)),
        minimum_chroma_step=float(min(c_steps)), maximum_lightness_error=float(max(lightness_errors)),
        scope='decoded RAW through the partial Standard predictor, not measured camera output')


def summarize():
    cards = [dense.read(dense.LOCAL / 'cards' / f'R090000{i}.json') for i in range(2, 6)]
    patches = [p for c in cards for p in c['patches']]
    colours = [p for p in patches if p['role'] == 'colour']
    lch = [p for p in colours if p['family'] == 'lch']
    dense.require(len({p['id'] for p in colours}) == len(colours), 'duplicate main point IDs')
    expected = {(h, L, f) for h in lattice.HUES for L in lattice.LIGHTNESS for f in lattice.FRACTIONS}
    dense.require({(p['hue'], p['L'], p['saturation_fraction']) for p in lch} == expected,
                  'incomplete LCh grid')
    dense.require(len([p for p in colours if p['family'] == 'camera-cube']) == len(lattice.CAMERA_LEVELS) ** 3,
                  'incomplete camera cube')
    arc = [p for p in lch if 150 <= p['hue'] <= 270]
    saturated = lambda rows: sum(p['saturation_fraction'] >= .90 for p in rows)
    old_path = common.pin(dense.ROOT / 'research/hue_ring/patches.json')
    old = [p for p in dense.read(old_path)['patches'] if p['ring'] in (1, 2)]
    old_arc = [p for p in old if 150 <= p['lab_h_design_deg'] <= 270]
    chroma = np.array([p['designed_standard_chroma'] for p in lch])
    old_chroma = np.array([p['lab_C_design'] for p in old])
    nominal = np.array([p['linear_srgb'] for p in colours])
    cam = [p for p in colours if p['family'] == 'camera-cube']
    camera_outside = sum(any(x < 0 or x > 1 for x in p['linear_srgb']) for p in cam)
    coverage = dict(schema='gr-dense-coverage/1', main_dngs=4, styles_per_dng=3,
        colour_patches=len(colours), total_patches=len(patches),
        roles=dict(Counter(p['role'] for p in patches)),
        families=dict(Counter(p['family'] for p in colours)),
        lch_coordinate=cards[0]['lch_coordinate'],
        hue_count=len(lattice.HUES), hue_step_degrees=3,
        lightness_levels=list(lattice.LIGHTNESS), chroma_fractions=list(lattice.FRACTIONS),
        saturated_definition='at least 90 percent of own hue/lightness boundary under the partial Standard model',
        saturated_patches=saturated(lch), arc_150_270=dict(hues=len({p['hue'] for p in arc}),
            count=len(arc), saturated=saturated(arc), endpoints_included=True),
        by_hue={h: dict(count=sum(p['hue'] == h for p in lch),
                    saturated=sum(p['hue'] == h and p['saturation_fraction'] >= .90 for p in lch))
                for h in lattice.HUES},
        by_lightness={L: dict(count=sum(p['L'] == L for p in lch),
                    saturated=sum(p['L'] == L and p['saturation_fraction'] >= .90 for p in lch))
                for L in lattice.LIGHTNESS},
        by_chroma_fraction={f: sum(p['saturation_fraction'] == f for p in lch) for f in lattice.FRACTIONS},
        designed_standard_chroma=dict(minimum=float(chroma.min()), maximum=float(chroma.max()),
            at_least_40=int((chroma >= 40).sum()), above_old_maximum=int((chroma > old_chroma.max()).sum()),
            bins={f'{a}..{b}': int(((chroma >= a) & (chroma < b)).sum())
                  for a, b in zip((0, 20, 40, 60, 80, 100), (20, 40, 60, 80, 100, 200))}),
        camera_domain=dict(axis_levels=len(lattice.CAMERA_LEVELS), minimum=lattice.LOW,
            maximum=lattice.HIGH, count=len(cam), nominal_dng_srgb_outside=camera_outside,
            white_balance='container AsShotNeutral retained; unbalanced RGB coordinates stored locally',
            spectral_gamut_known=False, boundary_epsilon=lattice.LOW, upper_headroom=.02),
        nominal_dng_srgb_outside_all=int(((nominal < 0) | (nominal > 1)).any(axis=1).sum()),
        model_output_inverse=cards[0]['standard_inverse_lattice'],
        decoded_lch_mapping=mapping_checks(cards),
        old_screen=dict(colour_patches=len(old), total_patches=155, hues=72,
            lightness_levels=[45, 65], chroma_per_lightness=[23.17, 30.77],
            arc_150_270_count=len(old_arc), chroma_at_least_40=int((old_chroma >= 40).sum()),
            caveat='old values describe emitted screen design; new LCh describes modeled camera output, not identical physical coordinates'),
        files=[dict(name=Path(c['dng_path']).name, patches=len(c['patches']),
                    colour_patches=sum(p['role'] == 'colour' for p in c['patches'])) for c in cards])
    dense.dump(dense.HERE / 'coverage.json', coverage)
    return coverage


def validation_summary():
    result = dict(schema='gr-dense-offline-validation/1', passed=True, camera_acceptance=False,
                  firmware_ready=False, deployable=False, cards=[])
    for i in range(1, 6):
        card = dense.read(dense.LOCAL / 'cards' / f'R090000{i}.json')
        d = dense.read(dense.LOCAL / 'validation' / f'R090000{i}-decode.json')
        j = dense.read(dense.LOCAL / 'validation' / f'R090000{i}-jpeg.json')
        dense.require(d['sha256'] == card['dng_sha256'] and j['dng_sha256'] == card['dng_sha256']
                      and d['passed'] and j['passed'],
                      'missing/current validation required')
        modes = {}
        for mode, q in j['modes'].items():
            v = {k: x for k, x in q.items() if k != 'colour_holdout'}
            if 'colour_holdout' in q:
                hold = q['colour_holdout']
                v['colour_holdout'] = dict(n=hold['n'], passed=hold['passed'],
                    median_de00=float(np.median(hold['delta_e00'])) if hold['n'] else None,
                    max_de00=float(np.max(hold['delta_e00'])) if hold['n'] else None)
            modes[mode] = v
        result['cards'].append(dict(name=Path(card['dng_path']).name, sha256=card['dng_sha256'],
            path=str(Path(card['dng_path']).relative_to(dense.ROOT)), bytes=Path(card['dng_path']).stat().st_size,
            patches=len(card['patches']), raw_clipped_patches=d['raw_clipped_patches'],
            all_ifd_offsets_preserved=d['ifd_offsets_preserved'], raw_round_trip_exact=d['raw_round_trip_exact'],
            all_three_previews_valid=d['all_three_previews_valid'],
            camera_coordinate_error=d['camera_coordinate_error'],
            designed_to_predicted_de00=d['designed_to_predicted_de00'],
            neutral_monotonicity=d['neutral_monotonicity'], modes=modes))
    dense.dump(dense.HERE / 'offline_validation.json', result)
    return result


if __name__ == '__main__':
    result = summarize()
    validation_summary()
    print(f'{result["colour_patches"]} colour points; {result["total_patches"]} patches; coverage complete')
