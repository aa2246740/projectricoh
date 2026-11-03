#!/usr/bin/env python3
"""Run the saved JPEG path, geometric perturbations, and the real closed-loop hook."""
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import copy
import json
import subprocess
import numpy as np
from PIL import Image, ImageDraw
from common import HERE, ROOT, LOCAL, TMP, read, dump, output, colour, sha, require, pin
from analyze import analyze, align, load_jpeg, sample, homography, project
from export_targets import export, validate_requests
from predict import predict, Renderer


def stats(x):
    a = np.asarray(x, float)
    return dict(n=int(a.size), median=float(np.median(a)), p90=float(np.percentile(a, 90)), max=float(a.max()))


def expect_rejection(call, description):
    try:
        call()
    except (ValueError, AssertionError):
        return description
    raise AssertionError('应当拒绝: ' + description)


def consumer_check(result_path, requests_path):
    # A clean process imports the existing consumer's own `common`, read-only.
    pin(ROOT / 'research/closed_loop/common.py')
    program = '''
import sys,json,copy
from pathlib import Path
import numpy as np
sys.path.insert(0,sys.argv[1])
from targets import Targets
from types import SimpleNamespace
result=json.loads(Path(sys.argv[2]).read_text());requests=json.loads(Path(sys.argv[3]).read_text())
t=Targets(SimpleNamespace(fs=None),SimpleNamespace(add=lambda p:p),sys.argv[2])
checks=0
for r in requests['frames']:
 f={'id':r['id'],'slot':r['slot'],'patches':[{'label':l} for l in r['labels']],'hashes':{'DNG':r['dng_sha256']}}
 q=result['frames'][r['key']]
 for ev in r['required_anchor_EV']:
  got,_=t.render(f,{},None,None,ev)
  expected=q['lab'] if ev==0 else q['anchor_lab'][f'{ev:+.1f}']
  assert np.array_equal(got,np.asarray(expected));checks+=1
 bad=copy.deepcopy(f);bad['hashes']['DNG']='0'*64
 try:t.render(bad,{},None,None)
 except ValueError:checks+=1
 else:raise AssertionError('consumer accepted a wrong DNG hash')
print(json.dumps({'existing_consumer_checks':checks}))
'''
    process = subprocess.run([sys.executable, '-I', '-B', '-c', program,
                              str(ROOT / 'research/closed_loop'), str(result_path), str(requests_path)],
                             cwd=ROOT, check=True, capture_output=True, text=True)
    return json.loads(process.stdout)


def run():
    folder = output(LOCAL / 'dry_run')
    folder.mkdir(parents=True, exist_ok=True)
    cm = colour()
    analyses, metrics = [], {}
    for name in ('GR3_tone', 'GR3_colour'):
        manifest = LOCAL / 'cards' / (name + '.json')
        prediction = read(LOCAL / 'predictions' / name / 'prediction.json')
        styles = {k: v['path'] for k, v in prediction['files'].items()}
        out = folder / (name + '_analysis.json')
        result = analyze(manifest, styles, out, 'model_prediction')
        analyses.append(out)
        predicted = np.load(LOCAL / 'predictions' / name / 'patch_predictions.npz', allow_pickle=False)
        card = read(manifest)
        this = {}
        for mode, state in result['modes'].items():
            got = np.asarray([m['rgb_observed'] for m in state['patches']])
            expected = predicted[mode]
            errors = cm.delta_e00(cm.rgb_lab(got), cm.rgb_lab(expected))
            primary = np.array([p['role'] in ('tone', 'colour', 'natural') for p in card['patches']])
            gains = np.array(state['radial']['gain_ev'])
            this[mode] = dict(sample_de00=stats(errors), primary_de00=stats(errors[primary]),
                              align=state['alignment'], measured_radial_gain_ev=gains,
                              radial_rmse_ev=state['radial']['rmse_ev'],
                              radial_gain_max_error_ev=float(np.max(abs(gains - np.array([0, .23, .48, .75, 1.13])))))
            require(np.percentile(errors[primary], 90) < .65, 'JPEG 回读误差超出干跑阈值')
            require(state['radial']['passed'] and this[mode]['radial_gain_max_error_ev'] < .09,
                    '径向拟合没有恢复已知增益')
        metrics[name] = this
    # One saved card is rotated, resized, JPEG re-encoded, and projectively displaced.
    card = read(LOCAL / 'cards/GR3_colour.json')
    original = load_jpeg(LOCAL / 'predictions/GR3_colour/standard.JPG')
    rotated = original.rotate(90, expand=True).resize((2000, 3000), Image.Resampling.LANCZOS)
    rotated_path = folder / 'rotated_resized.JPG'
    rotated.save(rotated_path, quality=92, subsampling=0)
    h, rotated_alignment = align(load_jpeg(rotated_path), card)
    got = np.array([p['rgb_observed'] for p in sample(load_jpeg(rotated_path), card, h)])
    baseline = read(analyses[1])['modes']['standard']['patches']
    expected = np.array([p['rgb_observed'] for p in baseline])
    rotated_error = cm.delta_e00(cm.rgb_lab(got), cm.rgb_lab(expected))
    require(np.percentile(rotated_error, 90) < .65, '旋转缩放对位后取色不一致')
    w, h0 = original.size
    input_corners = [[0, 0], [w, 0], [w, h0], [0, h0]]
    output_corners = [[60, 50], [w - 30, 20], [w - 70, h0 - 60], [40, h0 - 20]]
    forward = homography(input_corners, output_corners)
    backward = np.linalg.inv(forward); backward /= backward[2, 2]
    warped = original.transform(original.size, Image.Transform.PERSPECTIVE, backward.ravel()[:8],
                                Image.Resampling.BICUBIC, fillcolor=(127, 127, 127))
    warp_path = folder / 'projective.JPG'
    warped.save(warp_path, quality=95, subsampling=0)
    estimated, warped_alignment = align(load_jpeg(warp_path), card)
    control = np.array([p['center'] for p in card['patches']])
    warp_residual = np.linalg.norm(project(forward, control) - project(estimated, control), axis=1)
    require(np.max(warp_residual) < 7., '投影变换没有被正确恢复')
    missing = original.copy()
    m = card['markers'][0]
    x, y = m['xy']
    ImageDraw.Draw(missing).rectangle([x, y, x + 220, y + 220], fill=(127, 127, 127))
    rejected = [expect_rejection(lambda: align(missing, card), 'missing fiducial')]
    # A deliberately different radial profile tests correction rather than exact cancellation.
    mismatch_manifest = LOCAL / 'cards/GR3_colour.json'
    mismatch_prediction = predict(mismatch_manifest, folder / 'radial_mismatch', radial_scale=1.15)
    pred = read(mismatch_prediction)
    mismatch = analyze(mismatch_manifest, {k: v['path'] for k, v in pred['files'].items()},
                       folder / 'radial_mismatch_analysis.json', 'model_prediction')
    mismatch_gains = {}
    renderer = Renderer()
    for mode, state in mismatch['modes'].items():
        error = np.max(np.abs(np.asarray(state['radial']['gain_ev']) - 1.15 * np.array([0, .23, .48, .75, 1.13])))
        require(state['radial']['passed'] and error < .10, '未恢复偏离先验的径向增益')
        supported = [(p, m) for p, m in zip(card['patches'], state['patches'])
                     if p['role'] in ('colour', 'natural') and m['radial_supported']]
        truth = renderer.render(np.array([p['raw'] for p, m in supported]), card['geometry']['neutral'], mode)
        before = np.array([m['rgb_observed'] for p, m in supported])
        after = np.array([m['rgb_center'] for p, m in supported])
        e_before = cm.delta_e00(cm.rgb_lab(before), cm.rgb_lab(truth))
        e_after = cm.delta_e00(cm.rgb_lab(after), cm.rgb_lab(truth))
        require(np.median(e_after) < .8 * np.median(e_before), '扣除径向增益没有改善已知输入的色块输出')
        mismatch_gains[mode] = dict(gain_ev=state['radial']['gain_ev'], max_error_ev=float(error),
                                   correction_before_de00=stats(e_before), correction_after_de00=stats(e_after))
    # Closed-loop requests include the styled frame and its baseline for every slot.
    result = read(analyses[1])
    requests = dict(schema='closedloop-target-requests/1', frames=[])
    anchors = dict(schema='gr-incamera-anchors/1', frames={})
    for slot, mode in (('01', 'positive'), ('02', 'negative'), ('03', 'hc_bw')):
        valid = [p for p in result['transforms'][mode] if p['usable_for_fit']][:36]
        require(len(valid) >= 24, '干跑的回填色块不足')
        for fid in ('demo04', 'demo' + slot):
            key = fid + ':' + slot
            labels = [p['id'] for p in valid]
            evs = [-.3, 0., .3] if slot != '03' else [0.]
            fake_hash = sha(Path(card['dng_path']))
            requests['frames'].append(dict(id=fid, slot=slot, key=key, baseline_id='demo04',
                dng_sha256=fake_hash, labels=labels, chart='gr_synthetic',
                xyz_camera=[cm.lab_xyz(p['normalized']['standard_lab']) for p in valid], required_anchor_EV=evs))
            lab = np.array([p['normalized']['standard_lab'] for p in valid])
            anchors['frames'][key] = dict(labels=labels, dng_sha256=fake_hash,
                lab_by_ev={('0.0' if ev == 0 else f'{ev:+.1f}'): cm.xyz_lab(cm.lab_xyz(lab) * 2. ** ev) for ev in evs})
    req, anc, targets = [folder / n for n in ('requests.json', 'anchors.json', 'closedloop_targets.json')]
    dump(req, requests); dump(anc, anchors)
    exported = export(analyses, req, anc, targets)
    consumer = consumer_check(targets, req)
    for f in requests['frames']:
        if f['slot'] == '03':
            continue
        row = exported['frames'][f['key']]
        require(not np.array_equal(np.asarray(row['lab']), np.asarray(row['anchor_lab']['+0.3'])), 'EV 行被伪造为相同数据')
    bad = copy.deepcopy(requests); bad['frames'] = bad['frames'][1:]
    rejected.append(expect_rejection(lambda: validate_requests(bad), 'missing baseline request'))
    bad = copy.deepcopy(anchors); first_key = next(iter(bad['frames'])); bad['frames'][first_key]['dng_sha256'] = '0' * 64
    bad_path = folder / 'bad_anchor.json'; dump(bad_path, bad)
    rejected.append(expect_rejection(lambda: export(analyses, req, bad_path, folder / 'must_not_exist.json'), 'wrong anchor DNG hash'))
    bad = copy.deepcopy(anchors); del bad['frames'][first_key]['lab_by_ev']['+0.3']; dump(bad_path, bad)
    rejected.append(expect_rejection(lambda: export(analyses, req, bad_path, folder / 'must_not_exist.json'), 'missing EV anchor'))
    summary = dict(schema='gr-incamera-dry-run/1', passed=True, camera_evidence=False,
        prediction_roundtrip=metrics, rotated_resized=dict(alignment=rotated_alignment, de00=stats(rotated_error)),
        projective=dict(alignment=warped_alignment, center_position_error_px=stats(warp_residual)),
        radial_mismatch_15_percent=mismatch_gains, consumer=consumer,
        rejected=rejected, closedloop_frames=len(exported['frames']),
        generated_from_real_camera=False, high_contrast_bw_is_toy=True,
        camera_acceptance=False, firmware_ready=False, deployable=False)
    dump(folder / 'summary.json', summary)
    print(json.dumps({'passed': True, 'closedloop_frames': len(exported['frames']), **consumer}))
    return summary


if __name__ == '__main__':
    run()
