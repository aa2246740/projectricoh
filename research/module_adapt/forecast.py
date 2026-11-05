"""Three-fold hue holdout and explicit response-sensitivity scenarios."""
import copy
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import support as s
from unit_model import UnitModel
from calibrate import recipe_fit
from predict import SLOTS


def scenarios(base, unit):
    result = {'nominal': UnitModel(unit, base=base)}
    for label, sign in (('response_low', -1), ('response_high', 1)):
        spec = copy.deepcopy(base.model)
        spec['nodes_unwrapped_deg'] = (np.array(spec['nodes_unwrapped_deg'])+1.5*sign).tolist()
        spec['nodes_deg'] = (np.array(spec['nodes_deg'])+1.5*sign).tolist()
        spec['gain'] *= 1+.05*sign
        spec['k_coupling'] += .02*sign
        spec['kernel']['blur_kappa'] *= 1+.15*sign
        result[label] = UnitModel(unit, base=base, model_spec=spec)
    return result


def main():
    s.guard()
    base = s.engine()
    frames = s.read('research/closed_loop/local/m20261021_r1.json')['frames']
    result = {'schema': 'module-adapt-forecast/1', 'evidence': 'conditional model sensitivity, not a camera confidence interval',
        'assumptions': {'new_unit_04_calibration_input_error': 0,
                        'target_and_scene_coordinates': 'frozen 50mm screen dataset',
                        'scenarios': ['nominal', 'all nodes -1.5deg, gain -5%, coupling -0.02, blur_kappa -15%',
                                     'all nodes +1.5deg, gain +5%, coupling +0.02, blur_kappa +15%'],
                        'scenario_bounds_are_engineering_choices': True,
                        'other_module_response_observed': False,
                        'per_recipe_50mm_measured_residual_applied': False,
                        'heldout_target_used_in_this_refit': False,
                        'starting_daily_table_has_prior_training_history': True,
                        'independence_of_starting_table_from_screen_dataset_proven': False,
                        'legacy_04_input_and_target_calibration_rebuilt_per_fold': False}, 'units': {}}
    for unit in ('28mm', 'mount'):
        variants = scenarios(base, unit)
        m = variants['nominal']
        for slot in SLOTS:
            frame = next(f for f in frames if f['id'] == 'screen'+slot)
            keep = np.array(frame['valid'], bool)
            x = np.array(frame['input_x'])[keep]
            bx = np.array(frame['baseline_input_x'])[keep]
            target = np.array(frame['target_lab'])[keep]
            baseline_target = np.array(frame['baseline_target_lab'])[keep]
            _, ci = m.stock_matrix.apply(m.curve04(x))
            folds = np.floor(m.mm.hue_deg(ci)/15).astype(int) % 3
            # Near-grey samples have no reliable hue; keep whole patch IDs together.
            grays = np.array([p.get('gray', False) for p, ok in zip(frame['patches'], keep) if ok])
            folds[grays] = np.arange(len(x))[grays] % 3
            error_by_scenario = {name: np.full(len(x), np.nan) for name in variants}
            fold_results = []
            for fold in range(3):
                train = folds != fold
                artifact, _, _ = recipe_fit(m, slot, x, target, train=train, max_nfev=55)
                s.dump(f'local/forecast/{unit}_{slot}_fold{fold}.json', artifact)
                row = m.mm.MatrixRow(artifact['matrix_row1_q10'], artifact['matrix_tail'])
                A, B = np.array(artifact['colour_A']), np.array(artifact['colour_B'])
                for name, variant in variants.items():
                    rgb = variant.predict(slot, x[~train], row, A, B)
                    error_by_scenario[name][~train] = m.fs.delta_e00(m.fs.lab_from_codes(rgb), target[~train])
                fold_results.append({'fold': fold, 'n_train': int(train.sum()), 'n_holdout': int((~train).sum()),
                                     'solver_success': artifact['solver_success'], 'nfev': artifact['nfev'], 'checks': artifact['checks']})
            scored = {}
            for name, variant in variants.items():
                errors = error_by_scenario[name]
                assert np.isfinite(errors).all()
                baseline = m.fs.delta_e00(m.fs.lab_from_codes(variant.predict('04', bx)), baseline_target)
                port = m.fs.delta_e00(m.fs.lab_from_codes(variant.predict(slot, x)), target)
                scored[name] = {'after_cv': s.stats(errors), 'port_before': s.stats(port),
                    'baseline': s.stats(baseline), 'refit_similarity': s.similarity(errors, baseline),
                    'port_similarity': s.similarity(port, baseline)}
            values = [v['refit_similarity'] for v in scored.values()]
            row = {'n': len(x), 'n_chromatic': int((~grays).sum()), 'scenarios': scored,
                   'similarity_min': min(values), 'similarity_max': max(values),
                   'folds': fold_results, 'firmware_ready': False, 'camera_acceptance': False}
            result['units'].setdefault(unit, {})[slot] = row
            s.dump('local/forecast.json', result)
            print(unit, slot, 'model sensitivity %', round(min(values)*100, 1), round(max(values)*100, 1))
    s.finish('local/forecast_inputs.json')


if __name__ == '__main__':
    main()
