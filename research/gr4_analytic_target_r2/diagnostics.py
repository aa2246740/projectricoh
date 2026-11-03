"""Arithmetic attribution and an explicitly separate GXR search-radius control."""
from pathlib import Path
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
import fit as ff


class WideProblem(rt.old.Problem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Same parameter kinds and regularization; a fixed expanded radius only.
        for key, radius in [('Y', 128.), ('sector', 64.), ('curve', 32.)]:
            if key in self.blocks:
                s = self.blocks[key]
                self.limits[s.start:s.stop] = [radius] * (s.stop - s.start)


def denominator():
    rows = rt.read(rt.LOCAL / 'aggregates/main.json')
    output = []
    for slot in ('01', '02'):
        for scheme in ('page', 'hue'):
            old = next(r for r in rows if r['slot'] == slot and r['scheme'] == scheme and r['route'] == 'frozen_current')['old_target']
            for route in ('current_refit', 'candidate_Y', 'candidate_all', 'candidate_RLUT'):
                new = next(r for r in rows if r['slot'] == slot and r['scheme'] == scheme and r['route'] == route)
                eo, en = old['median'], new['median']
                bo, bn = old['baseline_median'], new['baseline_median']
                residual_pp = 100 * (eo - en) / bo
                denominator_pp = 100 * en * (1 / bo - 1 / bn)
                reported_pp = 100 * (new['similarity'] - old['similarity'])
                assert abs(residual_pp + denominator_pp - reported_pp) < 1e-10
                output.append(dict(slot=slot, scheme=scheme, route=route, evidence='电脑预测',
                    old_error=eo, new_error=en, old_denominator=bo, new_denominator=bn,
                    old_percent=100 * old['similarity'], new_percent=100 * new['similarity'],
                    shared_old_denominator_percent=100 * (1 - en / bo),
                    absolute_error_drop=eo - en, residual_change_pp=residual_pp,
                    denominator_change_pp=denominator_pp, reported_change_pp=reported_pp,
                    target_definition_changed=True, bridge_noise_not_identified=True))
    rt.dump('aggregates/denominator.json', output)
    for r in output:
        if r['route'] == 'current_refit': print(json.dumps(r, ensure_ascii=False), flush=True)
    return output


def wide_radius():
    m = rt.model()
    for slot in ('01', '02'):
        for fold in ff.FOLDS:
            ff.fit_one(m, slot, fold, 'current_refit', ff.data(m, slot, fold), tag='wide_radius', cls=WideProblem)
    ff.aggregate('wide_radius')


def gate():
    rows = rt.read(rt.LOCAL / 'aggregates/main.json')
    delta = rt.read(rt.LOCAL / 'aggregates/denominator.json')
    checks = []
    for slot in ('01', '02'):
        raw = [next(r for r in rows if r['slot'] == slot and r['scheme'] == scheme and r['route'] == 'current_refit')
            for scheme in ('page', 'hue')]
        shared = [next(r for r in delta if r['slot'] == slot and r['scheme'] == scheme and r['route'] == 'current_refit')
            for scheme in ('page', 'hue')]
        absolute_gate = all(r['similarity'] >= .75 for r in raw)
        corrected_improvement_gate = all(r['residual_change_pp'] >= 8 for r in shared)
        checks.append(dict(slot=slot, both_raw_at_least_75=absolute_gate,
            both_shared_denominator_gain_at_least_8pp=corrected_improvement_gate,
            passed=absolute_gate or corrected_improvement_gate,
            B_scope='limited input-state repair and frozen-source research' if absolute_gate or corrected_improvement_gate else 'defer'))
    result = dict(evidence='电脑预测', checks=checks, enter_B=any(c['passed'] for c in checks),
        analytical_model_validated=False, accepted_for_GXR_target=False,
        target_definition_change_not_identified_as_bridge_noise=True)
    rt.dump('A_gate.json', result)
    expected = {'main': 28, 'lut': 8, 'decomposition': 24, 'sensitivity': 68}
    if all((rt.LOCAL / f'aggregates/{name}.json').exists() for name in expected):
        assert all(len(rt.read(rt.LOCAL / f'aggregates/{name}.json')) == count for name, count in expected.items())
        rt.dump('A_complete.json', dict(A_complete=True, aggregate_rows=expected,
            primary_results_never_replaced_by_sensitivity=True, main_refit_reused_after_interruption=True))
    return result


def wide_sensitivity():
    import sensitivity as ss
    m = rt.model()
    rows = []
    for name in ('exposure_minus_quarter', 'exposure_plus_quarter', 'relative_control', 'fuji_metering'):
        tag = 'wide_sensitivity_' + name
        for slot in ('01', '02'):
            a = rt.arrays(rt.LOCAL / 'data' / (slot + '.npz'))
            target = ss.target(slot, name, a)
            for fold in ff.FOLDS:
                ff.fit_one(m, slot, fold, 'current_refit', ff.data(m, slot, fold, target), tag=tag, cls=WideProblem)
        rows.extend(ff.aggregate(tag))
    rt.dump('aggregates/wide_sensitivity.json', rows)


if __name__ == '__main__':
    denominator()
    if '--wide-radius' in sys.argv: wide_radius()
    if '--wide-sensitivity' in sys.argv: wide_sensitivity()
    print(json.dumps(gate(), ensure_ascii=False), flush=True)
    rt.finish('diagnostics')
