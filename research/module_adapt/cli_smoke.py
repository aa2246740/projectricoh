"""Exercise the public calibration and refitting commands with synthetic files."""
import copy
import json
import subprocess
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import support as s
from unit_model import UnitModel
from calibrate import prior_bias


def run(name, arguments):
    p = subprocess.run([sys.executable, '-I', '-B', str(s.HERE/'calibrate.py'), *arguments],
                       cwd=s.ROOT, capture_output=True, text=True, timeout=55)
    s.output('local/selfcheck/cli_'+name+'.log').write_text(p.stdout+p.stderr)
    assert p.returncode == 0, p.stderr


def main():
    s.guard()
    patch_path = s.source('research/module_adapt/local/selfcheck/noiseless_patches.jsonl')
    frames_path = s.source('research/module_adapt/local/selfcheck/noiseless_frames.json')
    rows = [json.loads(line) for line in patch_path.read_text().splitlines()]
    known = s.read('research/module_adapt/local/selfcheck_results.json')['calibration']['noiseless_roi_mean']['known_bias_coefficients']
    C = np.array(known)
    raw = np.array([r['raw_rgb'] for r in rows])
    x = (raw+np.column_stack([np.ones(len(raw)), raw])@C)*4095
    m = UnitModel('28mm')
    row, A, B = m.parameters('05')
    truth = row.copy(coef=row.coef.copy())
    truth.coef[0] += [8, -12, 4]
    h = np.arange(24)*2*np.pi/24
    rgb = m.predict('05', x, truth, A+np.rint(2*np.cos(h)).astype(int), B+np.rint(2*np.sin(h)).astype(int))
    target = m.fs.lab_from_codes(rgb)
    target_path = s.output('local/selfcheck/cli_targets.json')
    s.dump(target_path, {'schema': 'ricoh-module-targets/1', 'whitepoint': 'D65',
        'source': 'synthetic known unit and recipe parameters, not camera data',
        'samples': [{'page': r['page'], 'patch_id': r['patch_id'], 'slot': '05', 'target_lab': lab}
                    for r, lab in zip(rows, target)]})
    shared = ['--patches', str(patch_path), '--frames', str(frames_path), '--unit', '28mm']
    cal_path = s.output('local/selfcheck/cli_calibration.json')
    run('fit04', ['fit-04', *shared, '--holdout-page', 'validation', '--output', str(cal_path)])
    candidate_path = s.output('local/selfcheck/cli_recipe_05.json')
    run('fitrecipe', ['fit-recipe', *shared, '--slot', '05', '--calibration', str(cal_path),
                     '--targets', str(target_path), '--output', str(candidate_path)])
    candidate = json.loads(candidate_path.read_text())
    assert candidate['holdout_after']['median'] < .01
    assert candidate['holdout_before']['median'] > .1

    # Check that new 50mm recipe captures can become a marked residual prior.
    m50 = UnitModel('50mm', base=m.base)
    frames = json.loads(frames_path.read_text())
    for frame in frames['frames'].values():
        frame['module'] = '50mm'
        frame['selector_bytes']['recipe_slot'] = '05'
    measured = m50.predict('05', x, unclipped=True)+[.75, -.5, .25]
    new_rows = copy.deepcopy(rows)
    for r, jpeg in zip(new_rows, measured):
        r['jpeg_rgb'] = np.clip(jpeg, 0, 255).tolist()
        r['valid'] = bool(np.all((jpeg > 2) & (jpeg < 253)))
    p50, f50 = s.output('local/selfcheck/prior50_patches.jsonl'), s.output('local/selfcheck/prior50_frames.json')
    p50.write_text(''.join(json.dumps(r)+'\n' for r in new_rows))
    f50.write_text(json.dumps(frames, indent=2)+'\n')
    c50 = s.output('local/selfcheck/prior50_calibration.json')
    s.dump(c50, {'schema': 'ricoh-unit-calibration/1', 'module': '50mm', 'iso': 200, 'degree': 1,
                'residual_coefficients': C, 'table_sha256': s.digest(s.DAILY), 'source_kind': ['synthetic']})
    prior_path = s.output('local/selfcheck/prior50.json')
    run('prior50', ['learn-50mm-residual', '--patches', str(p50), '--frames', str(f50), '--unit', '50mm',
                   '--slot', '05', '--calibration', str(c50), '--output', str(prior_path)])
    prior = json.loads(prior_path.read_text())
    prior_error = float(np.max(abs(np.array(prior['bias_rgb'])-[.75, -.5, .25])))
    assert prior_error < 1e-10
    try:
        prior_bias(prior, x, '05')
        raise RuntimeError('合成先验被当成实拍使用')
    except AssertionError:
        pass
    s.dump('local/cli_smoke_results.json', {'fit04_cli': True, 'fitrecipe_cli': True, 'learn_50mm_prior_cli': True,
        'synthetic_prior_rejected_for_camera_transfer': True, 'known_rgb_prior_max_error': prior_error,
        'holdout_recipe_before': candidate['holdout_before'], 'holdout_recipe_after': candidate['holdout_after'],
        'camera_acceptance': False})
    s.finish('local/cli_smoke_inputs.json')
    print('通过三个 CLI 入口、已知配方恢复，以及合成先验隔离检查。')


if __name__ == '__main__':
    main()
