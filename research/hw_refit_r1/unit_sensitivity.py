"""Unknown offset-code units: rescore the same trained solutions without refitting."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from model import *
from run import routes, SLOTS, FOLDS
from report import write_csv


def main():
    m = rt.model()
    points, cache = {}, {}
    variants = [('base1', 1., 1.), ('offset_quarter', .25, 1.), ('tint_quarter', 1., .25),
                ('both_quarter', .25, .25), ('both_sixteenth', 1 / 16, 1 / 16)]
    paths = sorted((rt.LOCAL / 'fits').rglob('*.json')) + sorted((rt.LOCAL / 'unfrozen06/fits').rglob('*.json'))
    for path in paths:
        doc = rt.read(path)
        features = doc['features']
        if not any(k in features for k in ('offsets', 'tint_add', 'tint_Y')):
            continue
        slot, fold = doc['slot'], doc['fold']
        if (slot, fold) not in cache:
            cache[slot, fold] = prepare_data(m, slot, fold)
        d = cache[slot, fold]
        _, daily = routes()[doc['route'].split('_reg')[0]]
        if 'scope_variant' in doc:
            from unfrozen06 import UnfrozenProblem
            P = UnfrozenProblem(m, slot, d, features, daily)
            display_route = 'u06_' + doc['route']
        else:
            P = Problem(m, slot, d, features, daily)
            display_route = doc['route']
        p = np.array(doc['theta'])
        for name, out_unit, tint_unit in variants:
            state = P.state(p, True)
            rlut_grid = np.r_[0, np.arange(1, 32) * 128, 4095] * 255 / 4095
            if 'rlut' in P.blocks:
                state['rlut'] = np.array([np.maximum.accumulate(np.rint(np.interp(rlut_grid, np.linspace(0,255,33), q) * 4095 / 255)) * 255 / 4095 for q in state['rlut']])
            if 'offsets' in P.blocks:
                state['offsets'] = np.rint(P.val(p, 'offsets') / out_unit) * out_unit
            key = next((k for k in ('tint_add', 'tint_Y') if k in P.blocks), None)
            tint_valid = True
            if key:
                codes = np.rint(P.val(p, key) / tint_unit)
                tint_valid = bool(np.max(abs(codes)) <= 127)
                # Out-of-range codes are reported invalid, never silently saturated.
                state['tint'] = codes * tint_unit
            pre = np.einsum('ncj,cj->nc', P.H, state['q'])
            if 'rlut' in P.blocks:
                transformed = np.column_stack([np.interp(pre[:, ch], rlut_grid, state['rlut'][ch]) for ch in range(3)])
                raw = P.forward(state, transformed, skip_rlut=True)
            else:
                raw = P.forward(state, pre)
            pred = np.clip(raw + d['bias'], 0, 255)
            e = m.fs.delta_e00(m.fs.lab_from_codes(pred), d['target'])
            scheme = 'full' if fold == 'full' else 'page' if fold.startswith('page') else 'hue'
            held = d['held'] if fold != 'full' else d['score_mask']
            key2 = slot, display_route, name, scheme
            points.setdefault(key2, []).append((e[held], d['baseline'][held], tint_valid))
    rows = []
    for (slot, route, name, scheme), arrays in points.items():
        required = 6 if scheme == 'page' else 3 if scheme == 'hue' else 1
        if len(arrays) != required:
            continue
        e = np.concatenate([a[0] for a in arrays])
        b = np.concatenate([a[1] for a in arrays])
        rows.append(dict(slot=slot, route=route, units=name, scheme=scheme, label='电脑预测',
                         tint_code_valid=all(a[2] for a in arrays), same_continuous_fit=True, **score(e, b)))
    write_csv('offset_unit_sensitivity.csv', rows)
    rt.dump(rt.HERE / 'offset_unit_sensitivity.json', dict(variants=variants, rows=rows,
              note='same training-only continuous solutions, different assumed local code units; no refit or hardware verification'))
    rt.finish('unit_sensitivity')
    print('unit sensitivity rows', len(rows), flush=True)


if __name__ == '__main__':
    main()
