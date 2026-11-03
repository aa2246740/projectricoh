"""Check frozen input-map closure and local invertibility over observed domains."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np


def jacobian(raw, C):
    raw, C = np.asarray(raw), np.asarray(C)
    result = np.broadcast_to(np.eye(3)+C[1:4].T, (len(raw), 3, 3)).copy()
    if len(C) == 10:
        r, g, b = raw.T
        result[:, :, 0] += 2*r[:, None]*C[4]+g[:, None]*C[7]+b[:, None]*C[8]
        result[:, :, 1] += 2*g[:, None]*C[5]+r[:, None]*C[7]+b[:, None]*C[9]
        result[:, :, 2] += 2*b[:, None]*C[6]+r[:, None]*C[8]+g[:, None]*C[9]
    return result


def domain(raw, C):
    J = jacobian(raw, C)
    det = np.linalg.det(J)
    singular = np.linalg.svd(J, compute_uv=False)
    return dict(points=len(raw), determinant_min=float(det.min()), determinant_max=float(det.max()),
        nonpositive_determinants=int((det<=0).sum()),
        smallest_singular_value=float(singular[:, -1].min()),
        condition_max=float((singular[:, 0]/singular[:, -1]).max()))


def main():
    results = {}
    for unit in ('mount-a12', 'a12-50'):
        definition = rt.read(rt.LOCAL/'inputs'/unit/'definition.json')
        C = np.asarray(definition['calibration_coefficients'])
        calibration = rt.read(rt.HERE/definition['calibration_source'])
        assert np.array_equal(C, calibration['coefficients'])
        train_min, train_max = np.asarray(calibration['raw_train_min']), np.asarray(calibration['raw_train_max'])
        groups = {}
        observed = []
        for group in ('train', 'synthetic', 'photo_iso200', 'photo_other_iso'):
            values = rt.arrays(rt.LOCAL/'inputs'/unit/(group+'.npz'))
            raw = values['raw_codes']/4095
            if not len(raw):
                continue
            x = rt.calibration_apply(raw, C)
            error = float(abs(x-values['x']).max())
            assert error < 1e-6
            out = domain(raw, C)
            out.update(input_map_closure_max_code_error=error,
                outside_calibration_component_box_fraction=float(((raw<train_min)|(raw>train_max)).any(1).mean()),
                mapped_outside_type26_axis_fraction=float(((x<0)|(x>4095)).any(1).mean()))
            groups[group] = out
            if group.startswith('photo_'):
                observed.append(raw)
        raw = np.vstack(observed)
        lo, hi = raw.min(0), raw.max(0)
        grid = np.stack(np.meshgrid(*[np.linspace(a, b, 33) for a, b in zip(lo, hi)], indexing='ij'), axis=-1).reshape(-1, 3)
        dense = domain(grid, C)
        assert dense['nonpositive_determinants'] == 0, 'Selected input map has a sampled fold'
        # Exercise the quadratic terms independently of the inverse-map code.
        probe = raw[np.linspace(0, len(raw)-1, min(32, len(raw))).astype(int)]
        J = jacobian(probe, C)
        differences = []
        for k in range(3):
            step = np.eye(3)[k]*1e-6
            finite = (rt.calibration_apply(probe+step, C)-rt.calibration_apply(probe-step, C))/(2e-6*4095)
            differences.append(float(abs(finite-J[:, :, k]).max()))
        assert max(differences)<1e-7
        results[unit] = dict(label='电脑预测', groups=groups,
            observed_photo_bounding_box_dense_grid=dense,
            grid_size_per_axis=33, raw_bounds_saved_only_in_local=True,
            jacobian_finite_difference_max=max(differences),
            holdout_used_to_change_parameters=False,
            no_global_invertibility_claim=True,
            calibration_source_sha256=rt.sha(rt.HERE/definition['calibration_source']))
        rt.dump(rt.LOCAL/'inputs'/unit/'domain_bounds.json', dict(observed_raw_min=lo, observed_raw_max=hi,
            calibration_raw_min=train_min, calibration_raw_max=train_max))
    rt.dump('input_domain_summary.json', dict(label='电脑预测', units=results,
        scope='sampled local input-map geometry, not measured camera colorimetry'))
    for unit, result in results.items():
        print(unit, result['observed_photo_bounding_box_dense_grid'],
            'ISO200 extrapolation fraction', result['groups']['photo_iso200']['outside_calibration_component_box_fraction'])


if __name__ == '__main__':
    main()
