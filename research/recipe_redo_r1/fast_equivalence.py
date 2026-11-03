"""Task-input forward/derivative/record equivalence after the notified delivery."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
import copy
import signal
import struct
from fit_one import model, quality, seed
from guarded_problem import GuardedProblem
from entry_codec import encode, predict
from fast_backend import load
import os
NORMAL=os.environ.get('RECIPE_REDO_EQ_BACKEND')=='guarded_normal'
if NORMAL:
    from normal_backend import load
PRIVATE=rt.LOCAL/('normal_fast_engine' if NORMAL else 'fast_engine')


def close(a, b, label, atol=1e-7, rtol=1e-6):
    a, b = np.asarray(a), np.asarray(b)
    assert a.shape == b.shape
    error = abs(a-b)
    assert np.all(error <= atol+rtol*np.maximum(abs(a), abs(b))), (label, float(error.max()))
    return dict(test=label, values=a.size, maximum_difference=float(error.max()) if error.size else 0., atol=atol, rtol=rtol)


def main():
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('Backend equivalence exceeded 25 minutes')))
    signal.alarm(1500)
    fast, _ = load()
    cases = []
    for index in (29, 31, 32):
        base = rt.LOCAL/'targets/mount-a12'
        meta = rt.read(base/f'{index:02d}.json')
        data = rt.arrays(base/f'{index:02d}_train.npz')
        current = bytes.fromhex(meta['template_hex'])
        fixture = rt.Camera(2)
        _, rings = quality.fixtures(fixture)
        for level in (0, 1):
            for axis in ('stock04', 'published'):
                camera = copy.copy(fixture)
                camera.row = rt.mm.MatrixRow.from_bytes(current[216:244])
                if axis == 'published':
                    camera.curve = rt.mm.Curve([0, *struct.unpack_from('>31H', current, 20), 4095], fixture.curve.ys)
                config = dict(level=level, key=f'L{level}_adapter_equivalence')
                A = model.Problem(camera, data['x'], data['want'], data['sw'], config)
                B = fast.Problem(camera, data['x'], data['want'], data['sw'], config)
                theta = seed(A, current)
                if not A.bw:
                    theta[26:50] += .2*np.sin(np.arange(24)*1.7)
                theta = np.clip(theta, np.asarray(A.lower)+1e-6, np.asarray(A.upper)-1e-6)
                ar, aj = A.evaluate(theta)
                br, bj = B.evaluate(theta)
                checks = [close(ar, br, 'residual'), close(aj, bj, 'jacobian', atol=2e-5, rtol=2e-5)]
                packed_a, packed_b = rt.plain(A.packed(theta)), rt.plain(B.packed(theta))
                assert packed_a == packed_b, 'Identical parameters have different integer packing'
                ea = encode(current, packed_a, level=level, gray=A.bw)
                eb = encode(current, packed_b, level=level, gray=B.bw)
                assert ea == eb and len(ea)==552
                integer_model = B.predict_state(B.unpack(packed_b), data['x'], round_output=False)
                ordinary_record = predict(eb, data['x'], 2, round_output=False)
                checks.append(close(integer_model, ordinary_record, 'ordinary_Standard_552_record', atol=1e-7, rtol=0))
                if not A.bw:
                    GA = GuardedProblem(A, lambda x:predict(current, x, 2, round_output=False), fixture, rings)
                    GB = GuardedProblem(B, lambda x:predict(current, x, 2, round_output=False), fixture, rings)
                    av, ad = GA.penalty(theta)
                    bv, bd = GB.penalty(theta)
                    checks.extend([close(av, bv, 'hue_penalty', atol=1e-5),
                        close(ad, bd, 'hue_penalty_derivative', atol=2e-4, rtol=2e-4)])
                cases.append(dict(index=index, name=meta['name'], level=level, axis=axis,
                    train_points=len(data['x']), bw=A.bw, checks=checks, packed_parameters_identical=True,
                    all_552_bytes_identical=True))
                print('PASS', index, level, axis, flush=True)
    receipt = rt.read(PRIVATE/'adapter_receipt.json')
    rt.dump(PRIVATE/'equivalence_task.json', dict(status='PASS', created_utc=rt.utc(),
        backend_fingerprint=receipt['backend_fingerprint'], cases=cases,
        solver_trajectory_equivalence='delivery acceptance; this adapter gate checks equations and record encoding',
        physical_camera_acceptance=False))


if __name__ == '__main__':
    main()
