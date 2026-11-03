"""Replay private hypothetical fields with the frozen reference equations."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
from fit_one import model, quality, ring_masks
from entry_codec import predict


def main():
    rows = []
    for path in sorted((rt.LOCAL/'hypotheses').rglob('*.json')):
        doc = rt.read(path)
        assert not doc['main_candidate'] and not doc['recommend_next_dat_build'] and doc['no_552_record_claim']
        ui = ('a12-50', 'a12-28', 'mount-a12').index(doc['unit'])
        base = rt.LOCAL/'targets'/doc['unit']
        meta = rt.read(base/f'{doc["index"]:02d}.json')
        assert rt.sha(base/f'{doc["index"]:02d}.json') == doc['target_sha256']
        current = bytes.fromhex(meta['template_hex'])
        train = rt.arrays(base/f'{doc["index"]:02d}_train.npz')
        camera, fixture = rt.Camera(ui), rt.Camera(ui)
        camera.row = rt.mm.MatrixRow.from_bytes(current[216:244])
        camera.curve = rt.mm.Curve(doc['parameters']['curve_x_u12'], camera.curve.ys)
        P = model.Problem(camera, train['x'], train['want'], train['sw'], doc['config'])
        state = P.unpack(doc['parameters'])
        packed = doc['parameters']
        assert abs(np.asarray(packed['matrix_q10'])).max()<=2047
        assert (np.diff(np.asarray(packed['curve_y_u8']), axis=1)>=0).all()
        assert np.asarray(packed['c120_gains_u8']).min()>=0 and np.asarray(packed['c120_gains_u8']).max()<=255
        points = 0
        for group, scores in doc['scores'].items():
            if not scores:
                continue
            values = rt.arrays(base/f'{doc["index"]:02d}_{group}.npz')
            actual = P.predict_state(state, values['x'])
            saved = rt.arrays(path.parent/(path.stem+'_'+group+'.npz'))['prediction']
            assert np.array_equal(actual, saved)
            rescore = rt.score(values['base'], actual, values['want'])
            for key in ('median', 'p95', 'max', 'mean'):
                assert abs(rescore['de00'][key]-scores['candidate']['de00'][key])<1e-10
            points += len(actual)
        gradients, rings = quality.fixtures(fixture)
        fn = lambda x, rounding:P.predict_state(state, x, round_output=rounding)
        q = quality.diagnostics(fixture, fn, gradients, rings)
        before = ring_masks(fixture, lambda x, rounding:predict(current, x, ui, round_output=rounding), rings)
        after = ring_masks(fixture, fn, rings)
        added = sum(int((a & ~b).sum()) for a, b in zip(after, before))
        assert added == doc['quality']['new_reverse_hue_intervals']
        assert abs(q['max_integer_gradient_step_de00']-doc['quality']['max_integer_gradient_step_de00'])<1e-10
        rows.append(dict(file=str(path.relative_to(rt.HERE)), points=points,
            parameters_sha256=rt.sha(path), integer_outputs_identical=True,
            scores_recomputed=True, quality_recomputed=True,
            main_candidate=False, no_dat_or_552_hypothesis_record=True))
    rt.dump('hypothesis_verification.json', dict(status='PASS', branches=len(rows),
        rows=rows, physical_equations_verified=False, created_utc=rt.utc()))
    print('Hypothesis replay PASS', len(rows), 'branches,', sum(r['points'] for r in rows), 'points')


if __name__ == '__main__':
    main()
