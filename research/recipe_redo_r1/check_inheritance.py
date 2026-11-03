"""Prove that L1 can embed the obtained MOUNT L0 records on the same nodes."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
from fit_one import model, seed
from entry_codec import encode, predict
import struct


def main():
    rows = []
    for index in (29, 31, 32):
        folder = rt.LOCAL/'fits/mount-a12'/f'{index:02d}'
        path = min(folder.glob('L0_*.json'), key=lambda p:rt.read(p)['objective'])
        doc = rt.read(path)
        original = path.with_suffix('.record552').read_bytes()
        base = rt.LOCAL/'targets/mount-a12'
        meta = rt.read(base/f'{index:02d}.json')
        assert rt.sha(base/f'{index:02d}.json')==doc['target_sha256']
        current = bytes.fromhex(meta['template_hex'])
        train = rt.arrays(base/f'{index:02d}_train.npz')
        camera = rt.Camera(2)
        camera.row = rt.mm.MatrixRow.from_bytes(current[216:244])
        camera.curve = rt.mm.Curve([0, *struct.unpack_from('>31H', original, 20), 4095], camera.curve.ys)
        P = model.Problem(camera, train['x'], train['want'], train['sw'], dict(level=1, key='L1_inheritance_check'))
        inherited = encode(current, rt.plain(P.packed(seed(P, original))), level=1, gray=P.bw)
        maximum, points = 0., 0
        for group, score in doc['scores'].items():
            if not score:
                continue
            values = rt.arrays(base/f'{index:02d}_{group}.npz')
            a, b = [predict(e, values['x'], 2, round_output=False) for e in (original, inherited)]
            maximum = max(maximum, float(abs(a-b).max()))
            assert np.array_equal(np.rint(a), np.rint(b))
            points += len(a)
        assert maximum<1e-7
        rows.append(dict(index=index, name=doc['name'], points=points,
            max_continuous_code_difference=maximum, integer_predictions_identical=True,
            source_record_sha256=doc['record']['sha256'],
            only_model_equivalence=True, MOUNT_T1_still_pending=True))
    rt.dump('L1_inheritance_check.json', dict(status='PASS', label='电脑预测', rows=rows,
        physical_MOUNT_T1_verified=False, no_new_candidate_record_saved=True))
    print('L1 embedding PASS', len(rows), 'profiles,', sum(r['points'] for r in rows), 'points')


if __name__=='__main__':
    main()
