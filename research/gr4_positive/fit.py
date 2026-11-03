"""Small round5-centred Y/sector refit with whole-scene selection."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as r
import argparse
import time
import numpy as np

b = r.b


class Problem(r.P.Problem):
    def __init__(self, ridge, leave=None):
        chunks = [r.dataset(ident) for ident in b.read(b.LOCAL / 'protocol.json')['training_scenes'] if ident != leave]
        D = r.data()
        dense = dict(input_x=np.concatenate([a['x'] for a in chunks]),
                     aux_target=np.concatenate([a['target'] for a in chunks]),
                     aux_weights=np.concatenate([a['weight'] for a in chunks]))
        anchors = np.zeros(24, bool)
        anchors[D.greys] = True
        super().__init__(D, dense, anchors, dense['aux_weights'] > 0, protect=True)
        self.centre = self.initial(D.current)
        self.R *= np.sqrt(ridge)
        self.ridge, self.leave = ridge, leave


def path(ridge, leave):
    return b.LOCAL / 'fits' / ('ridge_' + str(ridge) + '_leave_' + (leave or 'none') + '.json')


def run(ridge, leave):
    dest = path(ridge, leave)
    if dest.exists():
        print('Existing fit retained:', dest.name)
        return
    started = time.monotonic()
    p = Problem(ridge, leave)
    protocol = b.read(b.LOCAL / 'protocol.json')
    sol = p.solve(p.centre, max_nfev=protocol['max_nfev'])
    row, A, B, q, cost, blend = p.quantize(sol.x, passes=protocol['integer_passes'])
    fit = r.E.f.pack_solution(p.D, row, A, B)
    fit.update(ridge=ridge, leave=leave, solver=dict(success=bool(sol.success), status=int(sol.status),
        message=sol.message, nfev=int(sol.nfev), cost=float(sol.cost), integer_cost=cost,
        elapsed_s=time.monotonic()-started), theta=sol.x,
        curves_unchanged=bool(np.array_equal(q, np.tile(np.rint(p.D.a['curve_y']).astype(int), (3, 1)))))
    results = {}
    for ident in protocol['training_scenes']:
        a = r.dataset(ident); m = a['valid']
        old = r.score(a['target'][m], r.predict(p.D.current, a['x'][m]), a['base'][m])
        new = r.score(a['target'][m], r.predict(fit, a['x'][m]), a['base'][m])
        results[ident] = dict(role='held_scene' if ident == leave else 'training', old=old, new=new,
            gain_pp=100*(new['similarity']-old['similarity']))
    fit['training_scene_scores'] = results
    r.dump(dest, fit)
    print(r.jsonable(dict(fit=dest.name, **fit['solver'], scene_gain_pp={k:v['gain_pp'] for k,v in results.items()})))


def select():
    dest = b.LOCAL / 'selection.json'
    assert not dest.exists(), 'Selection is frozen; do not tune on blind holdouts'
    protocol = b.read(b.LOCAL / 'protocol.json')
    records = []
    for ridge in protocol['ridge_multipliers']:
        held = [b.read(path(ridge, ident)) for ident in protocol['training_scenes']]
        gains = [f['training_scene_scores'][ident]['gain_pp'] for f, ident in zip(held, protocol['training_scenes'])]
        converged = all(f['solver']['success'] for f in held)
        records.append(dict(ridge=ridge, held_scene_gain_pp=gains, worst_gain_pp=min(gains),
                            converged=converged))
    eligible = [s for s in records if s['converged']]
    assert eligible, 'All scene-selection fits failed to converge'
    selected = max(eligible, key=lambda s:(s['worst_gain_pp'],s['ridge']))
    selection = dict(protocol=protocol['selection'], candidates=records, selected_ridge=selected['ridge'],
        validation_used=['hdf_positive', 'gr4b_positive'], blind_holdouts_used=False)
    r.dump(dest, selection)
    r.dump(b.HERE / 'selection.json', selection)
    print(selection)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ridge', type=float)
    parser.add_argument('--leave', choices=['hdf_positive', 'gr4b_positive'])
    parser.add_argument('--select', action='store_true')
    parser.add_argument('--final', action='store_true')
    args = parser.parse_args()
    if args.select:
        select()
    elif args.final:
        ridge = b.read(b.LOCAL / 'selection.json')['selected_ridge']
        run(ridge, None)
        src = path(ridge, None)
        dest = b.LOCAL / 'gr4_positive_01.json'
        assert not dest.exists()
        dest.write_bytes(src.read_bytes())
    else:
        assert args.ridge in b.read(b.LOCAL / 'protocol.json')['ridge_multipliers']
        run(args.ridge, args.leave)


if __name__ == '__main__':
    main()
