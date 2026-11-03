"""Check frozen exact nodes on each task unit's own train inputs and rows."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
import argparse
import copy
import struct
from fit_one import model, seed, quality
from fast_backend import load
import os
NORMAL=os.environ.get('RECIPE_REDO_EQ_BACKEND')=='guarded_normal'
if NORMAL:
    from normal_backend import load
PRIVATE=rt.LOCAL/('normal_fast_engine' if NORMAL else 'fast_engine')
from fast_equivalence import close
from entry_codec import predict, encode
from guarded_problem import GuardedProblem


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--unit', required=True, choices=('mount-a12', 'a12-50', 'a12-28'))
    args = ap.parse_args()
    fast, solver = load()
    ui = ('a12-50', 'a12-28', 'mount-a12').index(args.unit)
    level = 0 if ui==2 else 1
    cases = []
    for index in (0, 4, 14, 27, 29, 31, 32):
        base = rt.LOCAL/'targets'/args.unit
        meta = rt.read(base/f'{index:02d}.json')
        data = rt.arrays(base/f'{index:02d}_train.npz')
        current = bytes.fromhex(meta['template_hex'])
        camera = rt.Camera(ui)
        camera.row = rt.mm.MatrixRow.from_bytes(current[216:244])
        camera.curve = rt.mm.Curve([0, *struct.unpack_from('>31H', current, 20), 4095], camera.curve.ys)
        config = dict(level=level, key='cross_unit_exact')
        A = model.Problem(camera, data['x'], data['want'], data['sw'], config)
        B = fast.Problem(camera, data['x'], data['want'], data['sw'], config)
        p = seed(A, current)
        if not A.bw:
            p[26:50] += .13*np.sin(np.arange(24)*1.7)
        p = np.clip(p, np.asarray(A.lower)+1e-6, np.asarray(A.upper)-1e-6)
        ar, aj = A.evaluate(p)
        br, bj = B.evaluate(p)
        checks = [close(ar, br, 'residual'), close(aj, bj, 'jacobian', atol=2e-5, rtol=2e-5)]
        pack = rt.plain(A.packed(p))
        assert pack == rt.plain(B.packed(p))
        entry = encode(current, pack, level=level, gray=A.bw)
        apred = A.predict_state(A.unpack(pack), data['x'])
        bpred = B.predict_state(B.unpack(pack), data['x'])
        ordinary = predict(entry, data['x'], ui)
        assert np.array_equal(apred, bpred) and np.array_equal(apred, ordinary)
        if not A.bw:
            _, rings = quality.fixtures(rt.Camera(ui))
            ga = GuardedProblem(A, lambda x:predict(current, x, ui, round_output=False), camera, rings)
            gb = GuardedProblem(B, lambda x:predict(current, x, ui, round_output=False), camera, rings, optimizer=solver.least_squares)
            av, ad = ga.penalty(p)
            bv, bd = gb.penalty(p)
            checks += [close(av, bv, 'hue_penalty', atol=1e-5),
                       close(ad, bd, 'hue_penalty_derivative', atol=2e-4, rtol=2e-4)]
        cases.append(dict(index=index, name=meta['name'], points=len(data['x']), checks=checks,
                          packed_parameters_equal=True, integer_Standard_predictions_equal=True))
        print('PASS', args.unit, index, flush=True)
    rt.dump(PRIVATE/('equivalence_'+args.unit+'.json'), dict(status='PASS',
        created_utc=rt.utc(), backend_fingerprint=rt.read(PRIVATE/'adapter_receipt.json')['backend_fingerprint'],
        unit=args.unit, cases=cases))


if __name__ == '__main__':
    main()
