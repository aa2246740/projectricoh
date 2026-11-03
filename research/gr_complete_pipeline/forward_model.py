"""Evaluate an explicitly incomplete, firmware-derived GR III forward model.

Fit only two nuisance scalars on the six neutral patches. Never fit colours or
an arbitrary residual curve. The omitted MultiAxial/pixel stages stay explicit.
"""
import sys
sys.dont_write_bytecode = True
import hashlib
import json
from pathlib import Path
from functools import lru_cache
import numpy as np
from scipy.optimize import minimize_scalar

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from arm_gamma_model import evaluate_gamma, effective_curve
from pipeline_math import compose_q13, compose_q13_i32, front_q8, metrics, curve_lookup, RGB_LUMA, pack_record

REFERENCE_PATH = ROOT / 'research/color_references/gr3_reference_measurements.json'
TABLE_PATH = ROOT / 'research/gr_firmware/data/gr3-2.10-tables.json'


def load():
    reference = json.loads(REFERENCE_PATH.read_text())
    doc = json.loads(TABLE_PATH.read_text())
    tables = {t['id']: t for t in doc['tables']}
    metadata = json.loads((HERE / 'reference_metadata.json').read_text())
    md = {r['mode']: r for r in metadata['records']}
    out = {}
    for mode, name in [('standard', 'Standard'), ('positive', 'Positive_Film'), ('negative', 'Negative_Film')]:
        patches = reference['variants'][mode]['patches']
        sliders = md[mode]['first_seven_fields_inferred']
        WB = np.array(md[mode]['wb_rggb_u16'])[[0, 1, 3]] / 8192
        sat = np.array(tables[name + f'-saturation-{sliders["saturation"]:+d}']['values']).reshape(3, 3)
        look = np.array(tables[name + '-look-matrix']['values']).reshape(3, 3)
        sensor = np.array(tables[name + '-sensor-ccm']['values']).reshape(3, 3)
        composed = compose_q13_i32(compose_q13(sat, look), sensor)
        quantized_front = front_q8(composed)
        raw = np.array([p['camera_RGB_black_white_normalized'] for p in patches])
        out[mode] = dict(
            patches=patches, sliders={k: sliders[k] for k in ['key', 'contrast', 'highlight', 'shadow']},
            raw=raw, target=np.array([p['target_srgb'] for p in patches]),
            WB=WB, composed=composed, quantized_front=quantized_front,
            linear=(raw * WB) @ (quantized_front / 256).T,
            neutral=np.array([p['group'] == 'neutral' for p in patches]),
        )
    return reference, out


@lru_cache(maxsize=10000)
def gamma_cached(sliders_tuple, gain, flag):
    sliders = dict(zip(['key', 'contrast', 'highlight', 'shadow'], sliders_tuple))
    return np.array(evaluate_gamma(sliders, gain, model='gr3', flag=flag), dtype=float)


def predict(state, exposure, gain, flag=0):
    curve = gamma_cached(tuple(state['sliders'][k] for k in ['key', 'contrast', 'highlight', 'shadow']),
                         int(gain), flag)
    return np.clip(curve_lookup(curve, np.clip(state['linear'] * exposure, 0, 1) * 4095) / 16384, 0, 1)


def loss(states, modes, ev, gain, flag=0):
    residuals = []
    for mode in modes:
        state = states[mode]
        mask = state['neutral']
        residuals.extend(((predict(state, 2 ** ev, gain, flag) - state['target'])
                          @ RGB_LUMA)[mask])
    return float(np.mean(np.asarray(residuals) ** 2))


def fit(states, modes, flag=0):
    """Finite, deterministic gain search and bounded scalar exposure minimization.

    Bounds are declared modelling choices, not a claim about live runtime gains.
    Flag 1 gives the same family of curves at doubled gain; use flag 0 explicitly.
    """
    best = None
    observations = []
    for gain in range(1024, 65537, 256):
        solve = minimize_scalar(lambda ev: loss(states, modes, ev, gain, flag),
                                method='bounded', bounds=(-3, 3),
                                options={'xatol': 1e-8})
        item = (float(solve.fun), gain, float(solve.x))
        observations.append(item)
        if best is None or item < best:
            best = item
    center = best[1]
    for gain in range(max(1024, center - 255), min(65536, center + 255) + 1):
        solve = minimize_scalar(lambda ev: loss(states, modes, ev, gain, flag),
                                method='bounded', bounds=(-3, 3),
                                options={'xatol': 1e-10})
        item = (float(solve.fun), gain, float(solve.x))
        if item < best:
            best = item
    mse, gain, ev = best
    return {'gain': gain, 'flag': flag, 'exposure_scale': 2 ** ev, 'exposure_EV': ev,
            'neutral_luma8_rmse_objective': mse ** .5 * 255,
            'modes_used_for_neutral_fit': list(modes),
            'fit_colour_patches': 0, 'gain_bounds': [1024, 65536], 'exposure_EV_bounds': [-3, 3],
            'search': 'gain step256 plus every integer in best coarse +/-255; bounded scalar exposure search per gain',
            'bounds_are_analyst_choices': True,
            'parameter_identifiability': 'unknown: gain and input exposure can partly compensate; this is a nuisance fit, not measurement of camera gain',
            'coarse_best_8': [{'mse': a, 'gain': b, 'EV': c} for a, b, c in sorted(observations)[:8]]}


def evaluate(states, params, mode):
    state = states[mode]
    prediction = predict(state, params['exposure_scale'], params['gain'], params['flag'])
    curves, detail = effective_curve(model='gr3', **state['sliders'], gain=params['gain'], flag=params['flag'], details=True)
    statistic = metrics(prediction, state['target'], state['neutral'])
    for patch, pred, measured, row in zip(state['patches'], prediction, state['target'], statistic['per_patch']):
        row.update(chart_label=patch['chart_label'], group=patch['group'],
                   predicted_srgb=pred.tolist(), measured_srgb=measured.tolist())
    return {
        'metric': statistic, 'sliders_inferred_from_original_MakerNote_0247': state['sliders'],
        'white_balance_RGB_gains': state['WB'].tolist(),
        'composed_sensor_look_saturation_q13': state['composed'].tolist(),
        'ColorMatrix_Calc_front_signed12_Q8_hypothesis': state['quantized_front'].tolist(),
        'GammaTuning_explicit_state': detail,
        'effective_curve256_u16LE': pack_record(curves, 'H', '<'),
        'input_negative_channels_before_clamp': int(np.sum(state['linear'] < 0)),
        'input_channels_above_one_before_clamp': int(np.sum(state['linear'] * params['exposure_scale'] > 1)),
    }


def annotate_reference_defaults(result):
    source = json.loads((HERE / 'gr3_gr4_effective_curves.json').read_text())
    metadata = json.loads((HERE / 'reference_metadata.json').read_text())
    metadata = {r['mode']: r for r in metadata['records']}
    matching = {}
    for mode, name in [('standard', 'Standard'), ('positive', 'PositiveFilm'), ('negative', 'NegativeFilm')]:
        defaults = source['modes'][name]['gr3_initialization_defaults']
        values = metadata[mode]['first_seven_fields_inferred']
        matching[mode] = all(defaults[k] == values[k] for k in values)
    assert all(matching.values())
    result['GRIII_reference_settings_match_recovered_initialization_defaults'] = matching
    result['factory_slider_evidence'] = 'gr3_gr4_effective_curves.json and arm_gamma_gr3_defaults.json; named property/parser/setter/default-store chain, then exact match to original 0247 bytes under stated field-order interpretation'
    return result


def main():
    reference, states = load()
    fixed = {'gain': 8192, 'flag': 0, 'exposure_scale': 1., 'exposure_EV': 0.,
             'meaning': 'explicit diagnostic state; not verified camera default gain or exposure'}
    common = fit(states, tuple(states))
    print('common nuisance fit', json.dumps(common, ensure_ascii=False), flush=True)
    individual = {mode: fit(states, [mode]) for mode in states}
    result = {
        'schema': 'gr3-firmware-derived-partial-forward-model-v1',
        'evidence_level': '推断',
        'complete_firmware_reference': False,
        'reference_renderer_acceptance_pass': False,
        'source_measurements': {'path': str(REFERENCE_PATH),
                                'sha256': hashlib.sha256(REFERENCE_PATH.read_bytes()).hexdigest()},
        'firmware_matrix_source': {'path': str(TABLE_PATH),
                                   'sha256': hashlib.sha256(TABLE_PATH.read_bytes()).hexdigest()},
        'equation': 'curve256(clamp(E * (ColorMatrix_Calc_front /256) * (WB .* RAW), 0,1) * 4095) /16384',
        'integer_matrix_composition': 'A_sat*look MMUL16: (sum+4096)>>13 low16; multiply sensor MMUL32: trunc0((sum+4096)/8192); quantize with gain_scalar128 then diagonal row-sum correction and signed12 clamp',
        'ColorMatrix_runtime_state': {'setting_0x58': 8, 'setting_0x5a': 256, 'gain_scalar': 128,
                                     'meaning': 'confirmed normal default branch, not proof of shot runtime state; Q8 pixel scale inferred from row sum256'},
        'GammaTuning': 'independent integer formula, checked against bounded interpreter of original arithmetic routine',
        'MultiAxial': 'omitted in this ablation: register programming recovered, hardware pixel math unknown; shared does not imply identity',
        'curve_interpolation': '推断: per-channel linear knots16*k, clamp last15 input codes',
        'output_transfer_function': '推断: GammaTuning output used as encoded RGB, no second sRGB OETF',
        'neutral_fit_rule': 'only six neutral patches per included mode; minimise encoded (77R+150G+29B)/256 luma squared error; do not fit colour outputs',
        'metric_convention': 'CIEDE2000 kL=kC=kH=1 in Lab D50 from encoded ROI means; numpy percentile linear interpolation; encoded luma residual prediction-minus-JPEG in RGB8 codes',
        'measurement_limit': 'F(mean RAW) vs mean encoded JPEG; spatial stages, lens/sensor calibration, demosaic and nonlinear ROI averaging not recovered',
        'version_limit': 'matrix/gamma firmware2.10 vs Standard/Positive JPEG1.60 and Negative JPEG1.71; settings bytes recovered but full EXIF writer semantics unknown',
        'fixed_diagnostic_parameters': fixed,
        'fixed_diagnostic': {mode: evaluate(states, fixed, mode) for mode in states},
        'shared_neutral_calibration': {'parameters': common,
                                      'results': {mode: evaluate(states, common, mode) for mode in states}},
        'separate_mode_neutral_calibration': {
            'meaning': 'optimistic sensitivity diagnostic, each mode may choose different nuisance parameters; not a frozen common pipeline',
            'results': {mode: {'parameters': individual[mode], **evaluate(states, individual[mode], mode)} for mode in states}},
        'missing_stages': ['hardware MultiAxial pixel function', 'runtime gain and sensor input scaling',
                           'ToneControlTuning / shadow correction', 'highlight gamut/clipping and final YCC steps',
                           'exact per-pixel ROI rendering'],
    }
    annotate_reference_defaults(result)
    (HERE / 'forward_model_results.json').write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + '\n')
    for scenario in ['fixed_diagnostic', 'shared_neutral_calibration', 'separate_mode_neutral_calibration']:
        rows = result[scenario].get('results', result[scenario])
        print(scenario, json.dumps({mode: {k: row['metric'][k] for k in ['de00_median', 'de00_p90', 'encoded_luma8_mae', 'encoded_luma8_rmse']}
                                    for mode, row in rows.items()}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
