#!/usr/bin/env python3
"""Exhaustively audit sector-11 magnitude feasibility under combined uncertainty."""
import importlib.util
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True
sp = importlib.util.spec_from_file_location('t3_bounds_model', Path(__file__).with_name('model_t3.py'))
m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
p = m.p
import numpy as np


def main():
    p.preflight()
    frames = m.calibration()
    e = m.Engine(frames[0]['meta']['display'])
    doc = json.loads((p.LOCAL / 'predictions.json').read_text())
    ci = [np.array(t['real']) + 1j*np.array(t['imag']) for t in doc['ci']]
    weights = np.array(doc['weights'])
    mask = e.ring & (weights[:, 11] >= .1)
    rgb = .5 * (frames[0]['rgb'] + frames[1]['rgb'])
    old = m.signmag(e.stock[2][11*4+3])
    layouts = ('candidate', 'transpose', 'swap_axes', 'swap_outputs', 'diagonal_swap')
    scales = (.5, 1., 2.)
    rows = []
    for change in range(-127-old, 128-old):
        if change == 0:
            continue
        delta = .5 * sum(e.basis(c, 11, 'candidate') * change for c in ci)
        de = e.delta_e(np.clip(rgb + delta, 0, 255), rgb)
        qualifying = np.where(mask & (de >= 3))[0]
        rays = {e.layout['patches'][i]['hue_index'] for i in qualifying}
        if len(qualifying) < 2:
            continue
        min_head, max_hue, worst = 255., 0., None
        for layout in layouts:
            for scale in scales:
                for frame, c in zip(frames, ci):
                    out = frame['rgb'] + e.basis(c, 11, layout) * change * scale
                    min_head = min(min_head, float(np.minimum(out[e.ring], 255-out[e.ring]).min()))
                    _, c0 = e.mm.ycbcr(frame['rgb']); _, c1 = e.mm.ycbcr(out)
                    shift = float(abs(e.v2.sm.wrap180(e.mm.hue_deg(c1[mask])-e.mm.hue_deg(c0[mask]))).max())
                    if shift > max_hue:
                        max_hue, worst = shift, {'layout': layout, 'scale': scale}
        rows.append({'change': change, 'qualifying_patches': len(qualifying), 'distinct_hue_rays': len(rays),
                     'min_headroom_codes': min_head, 'max_hue_shift_deg': max_hue, 'worst_hue_case': worst})
    safe = [r for r in rows if r['min_headroom_codes'] >= 0 and r['max_hue_shift_deg'] <= 45]
    safe90 = [r for r in rows if r['min_headroom_codes'] >= 0 and r['max_hue_shift_deg'] <= 90]
    chosen = p.load('t3_bounds_parameters', p.HERE/'build_validate.py').CHANGES[11]
    selected = next(r for r in rows if r['change'] == chosen)
    selected_changes = {int(k): v for k,v in doc['changes'].items()}
    full_mask = e.ring & (weights[:, list(m.SECTORS)].sum(1) >= .1)
    full_head, full_hue, full_worst = 255., 0., None
    for layout in layouts:
        for scale in scales:
            for frame, c in zip(frames, ci):
                delta = sum(e.basis(c, sec, layout) * value * scale for sec,value in selected_changes.items())
                out = frame['rgb'] + delta
                full_head = min(full_head, float(np.minimum(out[e.ring],255-out[e.ring]).min()))
                _, c0=e.mm.ycbcr(frame['rgb']); _, c1=e.mm.ycbcr(out)
                hue=float(abs(e.v2.sm.wrap180(e.mm.hue_deg(c1[full_mask])-e.mm.hue_deg(c0[full_mask]))).max())
                if hue > full_hue:
                    full_hue, full_worst = hue, {'layout': layout, 'scale': scale}
    full_safe = full_head >= 0 and full_hue <= 45
    folder = p.ROOT/'research/hue_ring/local/calibration_20261020'
    deps = [p.HERE/'model_t3.py', p.HERE/'audit_bounds.py', p.MODEL, p.BASE/'DEEPTBL0.DAT']
    deps += [folder/f'R805{n}_{kind}.json' for n in (1179,1182) for kind in ('frame','robust')]
    summary = {'inputs_sha256': p.source_manifest(deps), 'changes': doc['changes'], 'schema': 'gxr-t3-bound-audit-1', 'signed_values_tested': 254,
               'qualifying_increments_count': len(rows), 'feasible_within_45deg_count': len(safe),
               'feasible_within_90deg_count': len(safe90), 'chosen_increment': chosen,
               'chosen_bound_result': selected, 'camera_handoff_ready': bool(safe and selected in safe and full_safe),
               'chosen_full_candidate_cross_product': {'minimum_headroom_codes': full_head,
                  'max_hue_shift_deg': full_hue, 'worst_hue_case': full_worst, 'pass': full_safe},
               'host_artifact_only': True,
               'criterion': 'Two ring patches >=3 DE00; no ring clipping; hue shift <=45deg in layout x positive half/one/double scales',
               'criterion_origin': '45deg is an explicit diagnostic choice for wild colour; this is an implementation acceptance bound, not a limit supplied by the user',
               'inference': 'Candidate models applied to existing 04 calibration pixels, not measured camera behavior',
               'single_hue_ray_satisfies_user_patch_count': True,
               'minimum_hue_shift_of_nonclipping_qualifiers': min(r['max_hue_shift_deg'] for r in rows if r['min_headroom_codes'] >= 0)}
    p.dump(p.LOCAL/'bounds_feasibility.json', {'summary': summary, 'rows': rows}, private=True)
    p.dump(p.HERE/'bounds_validation.json', summary)
    print('bound audit:', len(rows), 'qualifying increments; safe at 45deg:', len(safe), '; at 90deg:', len(safe90))
    print('chosen', chosen, 'worst hue shift', round(selected['max_hue_shift_deg'],3), 'degrees; camera_handoff_ready=False')


if __name__ == '__main__':
    main()
