"""Perturb the simulator without selecting parameters from outer holdouts."""
from pathlib import Path
import argparse
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
import fit as ff
import pipeline as pp


def fuji_scale(slot, a):
    # The old Fuji rule is independently frozen. No Film output is used to set it.
    anchor = rt.read('research/color_fit_v2/05_classic_chrome/round4/local/fit_v4_noT1.json')['anchor']
    records = rt.read(rt.LOCAL / 'data' / (slot + '_records.json'))
    base_rows = rt.exchange('04')
    metadata = rt.read(rt.LOCAL / 'gxrdng_metadata.json')
    result = np.ones(len(records))
    audit = []
    for page in range(1, 7):
        # Metering anchors come from the full frozen 04 scene, even when that
        # patch is absent from the stricter recipe scoring population.
        matches = [r for r in base_rows if r['page'] == page and r.get('sample_key') == 'ANCHOR_midgray']
        assert len(matches) == 1, (page, len(matches))
        b = matches[0]
        u = float(np.array(b['raw_rgb']) * np.array(b['meta']['white_balance']['gains']) @ np.array([.25, .5, .25]))
        rho = .18 * (u - anchor['f']) / (anchor['u_m'] - anchor['f'])
        # Our scene includes BE once; express the same legacy reflectance anchor in these coordinates.
        frame = next(r['frame'] for r in records if r['page'] == page)
        mat = np.asarray(metadata[frame]['raw_wb_to_scene_without_BE'])
        base_raw = np.asarray(b['raw_rgb']) * b['meta']['white_balance']['gains']
        base_scene = base_raw @ mat.T * 2 ** metadata[frame]['baseline_exposure']
        scale = rho / float(base_scene @ rt.cm.SRGB_XYZ[1])
        result[np.array([q['page'] == page for q in records])] = scale
        audit.append(dict(page=page, rho=rho, scale=scale, held_pixels_used_for_model_fit=False,
            inherited_target_metering_anchor=True))
    rt.dump('sensitivity/fuji_metering_' + slot + '.json', audit)
    return a['scene'] * result[:, None]


def target(slot, name, a):
    if name == 'relative_control':
        return pp.relative(rt.lab(a['base_rgb'] / 255), rt.lab(a['standard_rgb']), a['target'])
    if name == 'fuji_metering':
        return rt.lab(rt.sim.render_scene(fuji_scale(slot, a), pp.MODES[slot], pp.common()))
    return rt.lab(pp.render_variant(a['scene'], pp.MODES[slot], name))


def aggregate():
    rows = []
    for name in pp.VARIANTS:
        tag = 'sensitivity_' + name
        for row in ff.aggregate(tag):
            rows.append(row)
    rt.dump('aggregates/sensitivity.json', rows)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--variants', default=','.join(pp.VARIANTS))
    ap.add_argument('--routes', default='current_refit')
    aargs = ap.parse_args()
    m = rt.model()
    for slot in ('01', '02'):
        a = rt.arrays(rt.LOCAL / 'data' / (slot + '.npz'))
        for name in aargs.variants.split(','):
            t = target(slot, name, a)
            rt.dump(f'sensitivity/{slot}_{name}_target.json', dict(evidence='电脑预测',
                target_distance=rt.stats(rt.cm.delta_e00(t[a['supported']], a['target'][a['supported']])),
                perturbation=name, hardware_range_measured=False,
                scale_description='declared diagnostic range, not a confidence interval for physical hardware'))
            for fold in ff.FOLDS:
                d = ff.data(m, slot, fold, t)
                for route in aargs.routes.split(','):
                    ff.fit_one(m, slot, fold, route, d, tag='sensitivity_' + name)
    rows = aggregate()
    print(json.dumps(dict(complete_aggregate_rows=len(rows), summary='local/aggregates/sensitivity.json'), ensure_ascii=False), flush=True)
    rt.finish('sensitivity')


if __name__ == '__main__': main()
