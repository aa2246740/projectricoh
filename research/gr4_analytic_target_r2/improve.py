"""B: source-scoped radial correction, single BE rule, frozen-source inventory, validation."""
from pathlib import Path
import json
import re
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
import pipeline as pp
import input_adapter as ia


def source_inventory():
    repo = rt.ROOT / 'artifacts/downloads/gr3-film-mods/repo'
    commit = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
    assert commit == '04d5d5dd6e85d80089c6200bd0f0de5fff2d658f'
    paths = [
        'research/gr_complete_pipeline/arm_gamma_NOTES.md',
        'research/gr_complete_pipeline/REPORT.md',
        'research/gr_complete_pipeline/arm_gamma_gr4_params.asm.txt',
        'research/gr_complete_pipeline/arm_color_gr4_settings.asm.txt',
        'research/gr_complete_pipeline/arm_gamma_gr4_property_fields.json',
        'research/gr_complete_pipeline/forward_model_results.json',
        'research/gr_firmware/data/gr4-1.11-tables.json',
        'artifacts/downloads/gr3-film-mods/repo/FINDINGS.md',
        'artifacts/downloads/gr3-film-mods/repo/work/films_v16/refit16.py',
        'artifacts/downloads/gr3-film-mods/repo/work/v16_plan/hue15.py',
    ]
    matches = []
    for path in paths:
        text = rt.inp(path).read_text()
        for number, line in enumerate(text.splitlines(), 1):
            if re.search(r'ToneControl|histogram|scene-adaptive|still gain|拍摄上下文|初始缓存|38B08|38AD0|what selects the 5|level semantics|control\[10|thresholds are not required', line, re.I):
                matches.append(dict(path=path, line=number, text=line))
    tables = rt.read('research/gr_firmware/data/gr4-1.11-tables.json')
    names = [x['id'] for x in tables['tables']]
    properties = rt.read('research/gr_complete_pipeline/arm_gamma_gr4_property_fields.json')
    rt.dump('B/source_inventory.json', dict(commit=commit, sources={p: rt.sha(rt.ROOT / p) for p in paths},
        matches=matches, extracted_table_ids=names,
        tone_control_named_tables=[n for n in names if re.search('tone.?control', n, re.I)],
        relevant_named_properties={k: v for k, v in properties.items() if re.search('gain|ToneControl|DRange|DynamicRange', k, re.I)},
        gain_status='runtime ShootingInfo low16 source is identified; capture-specific value is not recovered',
        tone_status='no complete GR IV ToneControl transfer or capture histogram recovered from these extracted tables',
        multiaxial_status='geometry supported; exact thresholds and five-level selection remain open in pinned findings',
        no_default_gain_substitution=True, no_downloaded_code_executed=True))
    return dict(commit_verified=True, runtime_gain_recovered=False, ToneControl_pixel_semantics_recovered=False,
        MultiAxial_threshold_and_level_semantics_recovered=False, source_files=len(paths))


def validate():
    c = pp.common()
    dense = rt.arrays('research/gr4_analytic_target_r1/local/dense.npz')
    audit = rt.read('research/gr4_analytic_target_r1/local/dense_audit.json')
    rows = []
    dense_predictions = {}
    for mode in rt.sim.MODES:
        prediction = np.zeros_like(dense['raw_wb'])
        for source in audit:
            take = dense['band'] == source['band']
            prediction[take] = ia.render_template_camera(dense['raw_wb'][take], source['geometry']['baseline_exposure'], mode,
                dense['radius'][take], source['dng_sha256'], c)
        use = (dense['band'] == 4) & dense[mode + '_valid'] & np.isin(dense['role'], ['colour', 'tone', 'reference', 'natural'])
        err = rt.de(prediction[use], dense[mode][use])
        rows.append(dict(dataset='dense', split='held_page4', mode=mode, evidence='对真实 GR IV 照片的验证',
            **rt.stats(err), radial_scope='exact frozen chart DNG hashes only', parameters_refitted=False))
        dense_predictions[mode] = prediction
    np.savez_compressed(rt.LOCAL / 'B/dense_predictions.npz', **dense_predictions)
    for file in ('natural.npz', 'natural_modes.npz'):
        a = rt.arrays('research/gr4_analytic_target_r1/local/' + file)
        labels = np.full(len(a['scene']), 'standard') if file == 'natural.npz' else a['mode']
        pred = np.zeros_like(a['scene'])
        before = np.zeros_like(pred)
        for mode in np.unique(labels):
            take = labels == mode
            # Natural source hashes do not belong to the chart whitelist.
            pred[take] = ia.render_scene(a['scene'][take], str(mode), radius=a['radius'][take], common=c)
            rad = 2 ** np.interp(a['radius'][take], c['radius'], c['radial_ev'])
            before[take] = rt.sim.render_scene(a['scene'][take] * rad[:, None], str(mode), c)
        actual = a['standard'] if file == 'natural.npz' else a['observed']
        for frame in np.unique(a['frame']):
            take = a['frame'] == frame
            rows.append(dict(dataset=file, split='whole_photo_holdout', frame=str(frame), mode=str(labels[take][0]),
                evidence='对真实 GR IV 照片的验证', **rt.stats(rt.de(pred[take], actual[take])),
                previous_fixed_radial=rt.stats(rt.de(before[take], actual[take])),
                parameters_refitted=False, radial_scope='off for non-chart source',
                baseline_exposure='already applied once in stored scene coordinates'))
        np.savez_compressed(rt.LOCAL / 'B' / ('prediction_' + file), prediction=pred, previous=before, actual=actual, mode=labels, frame=a['frame'])
    rt.dump('B/real_photo_scores.json', rows)
    return rows


def main():
    gate = rt.read(rt.LOCAL / 'A_gate.json')
    assert gate['enter_B'] and rt.read(rt.LOCAL / 'A_complete.json')['A_complete']
    (rt.LOCAL / 'B').mkdir(exist_ok=True)
    inventory = source_inventory()
    scores = validate()
    meta = rt.read(rt.LOCAL / 'gxrdng_metadata.json')
    for slot in ('01', '02'):
        a = rt.arrays(rt.LOCAL / 'data' / (slot + '.npz'))
        records = rt.read(rt.LOCAL / 'data' / (slot + '_records.json'))
        check = np.empty_like(a['scene'])
        for frame in {r['frame'] for r in records}:
            take = np.array([r['frame'] == frame for r in records])
            md = meta[frame]
            check[take] = ia.scene_from_raw(a['raw'][take], md['raw_wb_to_scene_without_BE'], md['baseline_exposure'])
        assert np.array_equal(check, a['scene'])
        changed = ia.render_scene(check, pp.MODES[slot])
        assert np.array_equal(changed, a['target_rgb'])
    result = dict(B_entered_for='02', evidence='对真实 GR IV 照片的验证',
        input_repairs=['BaselineExposure exactly once before scene API', 'radial fit only for exact chart hashes'],
        common_parameters_refitted=False, GXR_A_targets_unchanged=True,
        recovered=inventory, real_photo_accuracy_gate_passed=False,
        reason='held page Positive/Negative remain above 1.0 DeltaE00',
        scores=scores, no_holdout_parameter_search=True)
    rt.dump('B/summary.json', result)
    for row in scores:
        print(json.dumps({k: row[k] for k in ('dataset', 'mode', 'n', 'median', 'p90')}), flush=True)
    rt.finish('B')


if __name__ == '__main__': main()
