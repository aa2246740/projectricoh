"""Independent synthetic unit bias, interchange round trip and recipe recovery."""
import json
import struct
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import support as s
from extract import Image, UNITS
from unit_model import UnitModel
from calibrate import fit04, apply_calibration, load_exchange, recipe_fit
from predict import synthetic_inputs


def rom_checks():
    data = s.read('research/module_adapt/local/official_parameters.json')['units']
    getters = {'50mm': 0x201159D8, '28mm': 0x2011862C, 'mount': 0x201105C8}
    checks = {}
    for unit, name in UNITS.items():
        image = Image(name)
        pointers = []
        for off in (0x5C, 0xA8, 0xF4, 0x140):
            b = image.raw(getters[unit]+off, 8)
            ptr = (int.from_bytes(b[2:4], 'big') << 16) | int.from_bytes(b[6:8], 'big')
            pointers.append(ptr)
        assert pointers == [q['vma'] for q in data[unit]['rom_d0']]
        checks[unit] = {'getter': getters[unit], 'normal_r5_0_pointers': pointers,
                        'matched_extracted_rom_records': True}
    s.dump('local/rom_getter_checks.json', checks)


def parity(base):
    model = UnitModel('50mm', base=base)
    x = np.random.default_rng(522).uniform(20., 2800., (256, 3))
    errors = {slot: float(np.max(abs(model.predict(slot, x)-base.predict(slot, x)))) for slot in ('01', '02', '03', '04', '05')}
    assert max(errors.values()) < 1e-10
    # Independent expression for the previously unsupported T1 slot.
    entry = base.entries['06']['written']
    xs = np.r_[0., np.frombuffer(entry[0], dtype='>u2'), 4095.]
    channels = (np.frombuffer(entry[6][:33], dtype='u1'), np.frombuffer(entry[1], dtype='u1'), np.frombuffer(entry[6][33:], dtype='u1'))
    pre = np.column_stack([np.interp(x[:, i], xs, channels[i]) for i in range(3)])
    row, A, B = base.parameters('06')
    y, ci = row.apply(pre)
    W = base.table.kernel_weights(base.mm.hue_deg(ci), abs(ci))
    Z = base.fs.Z_of_words(A, B, base.ctx)
    effective = abs(Z)*np.exp(1j*base.table.k*np.angle(Z))
    co = ci*(W@base.ctx.S_eff+(W*base.table.gain)@(base.ctx.S_eff*(effective-1)))
    expected = np.clip(base.mm.rgb_from_ycc(y, co), 0, 255)
    t1_error = float(np.max(abs(expected-model.predict('06', x))))
    assert t1_error < 1e-10
    neutral_display = {k: 5 for k in model.display}
    ideals = [UnitModel(u, base=base, ideal=True, display=neutral_display) for u in UNITS]
    cancellation = {slot: max(float(np.max(abs(ideals[0].predict(slot, x)-m.predict(slot, x)))) for m in ideals[1:]) for slot in ('01', '02', '03', '05', '06')}
    assert max(cancellation.values()) < 1e-10
    return {'closedloop_non_T1_max_rgb_error': errors, 'independent_T1_max_rgb_error': t1_error,
            'ideal_full_row_replacement_neutral_modifiers_max_rgb_error': cancellation,
            'similarity_negative_value_is_retained': s.similarity([3, 4, 5], [1, 2, 3]) == -1,
            'similarity_small_denominator_is_null': s.similarity([.1, .2], [.05, .1]) is None}


def simulated_capture(model, bias, gain, quantize=False):
    rng = np.random.default_rng(8143)
    raw = rng.uniform(.018, .19, (800, 3))
    x = (raw@gain+bias)*4095
    jpeg = model.predict('04', x, unclipped=True)
    ok = np.all((jpeg > 3) & (jpeg < 250), axis=1)
    raw, jpeg = raw[ok][:144], jpeg[ok][:144]
    assert len(raw) == 144
    if quantize:
        jpeg = np.rint(jpeg)
    rows = []
    names = ('contrast', 'sharpness', 'vividness', 'orange_saturation', 'green_saturation',
             'blue_saturation', 'red_saturation', 'magenta_saturation',
             'orange_hue', 'green_hue', 'blue_hue', 'red_hue', 'magenta_hue')
    to_raw = (7, 6, 1, 2, 3, 4, 5, 8, 9)
    raw13 = [to_raw[model.display[k]-1] for k in names]
    frames = {'schema': 'ricoh-module-frames/1', 'frames': {}}
    for i, (camera, rgb) in enumerate(zip(raw, jpeg)):
        frame = 'synthetic_validation' if i >= 96 else 'synthetic_train'
        frames['frames'][frame] = {'module': model.unit, 'iso': 200, 'shutter_s': 1/60,
            'aperture_f': 5.6, 'white_balance': {'mode': 'manual', 'gains': [1., 1., 1.]},
            'selector_bytes': {'recipe_slot': '04', 'image_setting': 1, 'type26_control': 2, 'raw13': raw13},
            'lens_id': 'synthetic-reference', 'corrections': {'peripheral': 0, 'color_shading': [0, 0]},
            'source_kind': 'synthetic'}
        rows.append({'frame': frame, 'page': 'validation' if i >= 96 else 'train',
            'patch_id': f'S{i:03d}', 'class': 'synthetic_color', 'raw_rgb': camera.tolist(),
            'jpeg_rgb': rgb.tolist(), 'valid': True,
            'spatial_sd': {'raw_rgb': [.001]*3, 'jpeg_rgb': [.5]*3}})
    prefix = 'quantized' if quantize else 'noiseless'
    if model.unit != '28mm':
        prefix = model.unit+'_'+prefix
    p = s.output('local/selfcheck/'+prefix+'_patches.jsonl')
    p.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    f = s.output('local/selfcheck/'+prefix+'_frames.json')
    f.write_text(json.dumps(frames, indent=2)+'\n')
    loaded, _ = load_exchange(p, f, model.unit)
    return loaded, raw


def main():
    s.guard()
    rom_checks()
    base = s.engine()
    checks = parity(base)
    unit = UnitModel('28mm', base=base)
    gain = np.array([[1.035, .004, -.002], [.003, .972, .004], [-.003, .006, 1.018]])
    bias = np.array([.0011, -.0007, .0005])
    expected = np.vstack([bias, gain-np.eye(3)])
    calibrations = {}
    for quantized in (False, True):
        rows, raw = simulated_capture(unit, bias, gain, quantized)
        result = fit04(unit, rows, holdout_page='validation')
        key = 'quantized_8bit' if quantized else 'noiseless_roi_mean'
        result['known_bias_coefficients'] = expected.tolist()
        result['coefficient_max_absolute_error'] = float(np.max(abs(np.asarray(result['residual_coefficients'])-expected)))
        s.dump('local/selfcheck/calibration_'+key+'.json', result)
        true_x = (raw[96:]@gain+bias)*4095
        estimated_x = apply_calibration(raw[96:], result)
        result['recipe_prediction_checks'] = {slot: s.stats(unit.de(unit.predict(slot, true_x), unit.predict(slot, estimated_x))) for slot in ('01', '02', '03', '05', '06')}
        assert result['holdout']['corrected_de00']['median'] < (.3 if quantized else .001)
        assert result['coefficient_max_absolute_error'] < (.008 if quantized else 1e-5)
        assert max(v['median'] for v in result['recipe_prediction_checks'].values()) < (.4 if quantized else .001)
        calibrations[key] = result

    mount = UnitModel('mount', base=base)
    mount_rows, _ = simulated_capture(mount, bias, gain)
    mount_result = fit04(mount, mount_rows, holdout_page='validation')
    mount_result['coefficient_max_absolute_error'] = float(np.max(abs(np.array(mount_result['residual_coefficients'])-expected)))
    assert mount_result['coefficient_max_absolute_error'] < 1e-5
    assert mount_result['holdout']['corrected_de00']['median'] < .001
    s.dump('local/selfcheck/calibration_mount.json', mount_result)

    # A separate challenge exercises the refitter rather than just the 04 calibration.
    samples, _ = synthetic_inputs(unit)
    x = samples['hue_ring'][::4]
    _, ci = unit.stock_matrix.apply(unit.curve04(x))
    train = (np.floor(unit.mm.hue_deg(ci)/.5).astype(int) % 2) == 0
    recipe_checks = {}
    theta = np.arange(24)*2*np.pi/24
    for slot in ('01', '02', '03', '05', '06'):
        row, A, B = unit.parameters(slot)
        truth_row = row.copy(coef=row.coef.copy())
        truth_row.coef[0] += [8, -12, 4]
        truthA = A+np.rint(2*np.cos(theta)).astype(int)
        truthB = B+np.rint(2*np.sin(theta)).astype(int)
        target = unit.fs.lab_from_codes(unit.predict(slot, x, truth_row, truthA, truthB))
        artifact, pred, err = recipe_fit(unit, slot, x, target, train, max_nfev=35)
        s.dump('local/selfcheck/recipe_'+slot+'.json', artifact)
        after, before = artifact['holdout_after']['median'], artifact['holdout_before']['median']
        assert before > .05 and after < .25 and after < before*.5, (slot, before, after)
        recipe_checks[slot] = {'holdout_before': artifact['holdout_before'], 'holdout_after': artifact['holdout_after'],
                               'solver_success': artifact['solver_success'], 'checks': artifact['checks']}
    checks.update(calibration=calibrations, mount_calibration=mount_result, recipe_refit=recipe_checks,
                  evidence_kind='synthetic_host_only', firmware_ready=False, camera_acceptance=False)
    s.dump('local/selfcheck_results.json', checks)
    s.finish('local/selfcheck_inputs.json')
    for key, result in calibrations.items():
        print(key, 'heldout median ΔE00', result['holdout']['uncorrected_de00']['median'], '->', result['holdout']['corrected_de00']['median'])
    print('五配方重拟合、三单元原厂值、完整行替换和 T1 路径自检均通过。')


if __name__ == '__main__':
    main()
