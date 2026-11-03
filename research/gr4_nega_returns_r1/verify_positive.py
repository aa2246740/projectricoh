#!/usr/bin/env python3
"""Replay the full-MAIN Positive target against the frozen partial-MAIN target."""
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
from positive_check import DenseTarget


def main():
    old = rt.ROOT/'research/gr4_dense_returns_r1/local'
    with np.load(old/'target/paired_measurements.npz', allow_pickle=False) as z:
        previous = dict(z)
    with np.load(rt.LOCAL/'positive_check/paired_measurements.npz', allow_pickle=False) as z:
        current = dict(z)
    assert set(previous) == set(current)
    differences = {}
    for key in previous:
        assert previous[key].shape == current[key].shape
        if previous[key].dtype.kind in 'biuf':
            differences[key] = float(np.max(abs(previous[key].astype(float)-current[key].astype(float))))
            assert differences[key] < 1e-12, key
        else:
            assert np.array_equal(previous[key], current[key]), key
    m = rt.model()
    with np.load(old/'fit/data.npz', allow_pickle=False) as z:
        data = dict(z)
    target, supported, distance = DenseTarget().target(data['scene_x'], m.fs.lab_from_codes(m.predict('04', data['scene_x'])))
    same_support = supported == data['supported']
    assert same_support.all()
    maximum = float(np.max(abs(target[supported]-data['new_target'][supported])))
    assert maximum < 1e-10
    oldmanifest = rt.read(old/'target/manifest.json')
    newmanifest = rt.read('positive_check/manifest.json')
    assert oldmanifest['u118_raw_wb_without_BE'] == newmanifest['u118_raw_wb_without_BE']
    assert oldmanifest['bridge'] == newmanifest['bridge']
    rt.dump('verification/positive_equivalence.json', dict(passed=True, paired_measurements=len(current['raw_wb']),
        arrays_max_abs_difference=differences, supported_fit_queries=int(supported.sum()),
        all_fit_query_support_equal=True, target_lab_max_abs_difference=maximum,
        same_bridge_and_Standard_anchor=True,
        positive_candidate_unchanged=True, method='original target.py with full MAIN input and output paths only'))
    print('Positive equivalence passed; measurement max delta', max(differences.values()), 'target Lab max delta', maximum, flush=True)


if __name__ == '__main__':
    main()
