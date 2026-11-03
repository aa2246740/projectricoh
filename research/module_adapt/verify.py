"""Check delivered evidence, protected input hashes, write fence, and optional SHA seal."""
import argparse
import csv
import json
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import support as s


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--seal', action='store_true')
    args = ap.parse_args()
    s.guard()
    checked = {}
    manifests = ['extract_inputs.json', 'predict_inputs.json', 'selfcheck_inputs.json', 'forecast_inputs.json', 'cli_smoke_inputs.json', 'report_inputs.json']
    for name in manifests:
        j = json.loads((s.LOCAL/name).read_text())
        assert j['all_inputs_unchanged']
        for path, expected in j['sha256'].items():
            assert s.digest(s.ROOT/path) == expected, f'输入变化: {path}'
            checked[path] = expected
    forbidden = s.ROOT / 'research/multi_module/forbidden-write-probe.json'
    try:
        s.output(forbidden)
        raise AssertionError('写入边界失效')
    except ValueError:
        pass
    assert not forbidden.exists()
    assert not any(s.HERE.rglob('__pycache__'))
    assert not any(p.suffix.lower() in ('.dat', '.bin', '.dng', '.rom') for p in s.HERE.rglob('*') if p.is_file())
    selfcheck = json.loads((s.LOCAL/'selfcheck_results.json').read_text())
    assert selfcheck['evidence_kind'] == 'synthetic_host_only' and not selfcheck['camera_acceptance']
    assert selfcheck['calibration']['noiseless_roi_mean']['coefficient_max_absolute_error'] < 1e-5
    assert selfcheck['calibration']['quantized_8bit']['holdout']['corrected_de00']['median'] < .3
    for slot, r in selfcheck['recipe_refit'].items():
        assert r['solver_success'] and all(r['checks'].values())
        assert r['holdout_after']['median'] < r['holdout_before']['median']*.5
    forecast = json.loads((s.LOCAL/'forecast.json').read_text())
    for unit, slots in forecast['units'].items():
        assert set(slots) == {'01', '02', '03', '05', '06'}
        for slot, r in slots.items():
            assert sum(f['n_holdout'] for f in r['folds']) == r['n']
            assert all(f['solver_success'] and all(f['checks'].values()) for f in r['folds'])
            assert not r['firmware_ready'] and not r['camera_acceptance']
            for scenario in r['scenarios'].values():
                expected = 1-scenario['after_cv']['median']/scenario['baseline']['median']
                assert abs(expected-scenario['refit_similarity']) < 1e-12
    engine = s.engine()
    candidates = sorted((s.LOCAL/'forecast').glob('*.json'))
    candidates += sorted((s.LOCAL/'selfcheck').glob('recipe_*.json'))
    candidates += [s.LOCAL/'selfcheck/cli_recipe_05.json']
    for path in candidates:
        artifact = json.loads(path.read_text())
        row = engine.mm.MatrixRow(artifact['matrix_row1_q10'], artifact['matrix_tail'])
        decoded = engine.mm.MatrixRow.from_bytes(row.to_bytes())
        assert np.array_equal(decoded.coef, row.coef) and decoded.tail == row.tail
        for A, B in zip(artifact['colour_A'], artifact['colour_B']):
            assert engine.fs.decode_word(engine.fs.encode_word(A, B)) == (A, B)
    with (s.LOCAL/'by_hue_sector.csv').open() as f:
        sectors = list(csv.DictReader(f))
    assert len(sectors) == 2*3*6*3*24
    assert {int(r['sector_15deg']) for r in sectors} == set(range(24))
    with (s.LOCAL/'by_native_sector.csv').open() as f:
        native_sectors = list(csv.DictReader(f))
    assert len(native_sectors) == len(sectors)
    assert {int(r['colour_record_0based']) for r in native_sectors} == set(range(24))
    predictions = json.loads((s.LOCAL/'predictions.json').read_text())
    assert predictions['scene_projection']['p3_outside_srgb_retained'] > 0
    assert predictions['scene_projection']['p3_grid_total'] == 13**3
    for run in predictions['comparisons']:
        for dataset, stats in run['datasets'].items():
            for unit in ('28mm', 'mount'):
                assert stats['03/50mm:'+unit]['max'] == 0
    content = (s.HERE/'REPORT.md').read_text()
    assert all(x in content for x in ('已核实', '推断', '未知', 'SHA256SUMS', 'EXCHANGE.md'))
    s.dump('local/verification.json', {'passed': True, 'checked_input_files': len(checked),
        'all_protected_inputs_unchanged': True, 'all_writes_task_scoped': True,
        'native_firmware_getters_checked': True, 'synthetic_calibration_and_recipe_checks': True,
        'candidate_codec_roundtrip_count': len(candidates),
        'complete_cli_flow_checked': (s.LOCAL/'selfcheck/cli_recipe_05.json').exists(),
        'sector_rows': len(sectors), 'native_sector_rows': len(native_sectors), 'camera_acceptance': False, 'firmware_ready': False,
        'no_card_or_body_outputs': True})
    if args.seal:
        lines = []
        for p in sorted(s.HERE.rglob('*')):
            if p.is_file() and p.name != 'SHA256SUMS':
                assert not p.is_symlink()
                lines.append(s.digest(p)+'  '+str(p.relative_to(s.HERE)))
        (s.HERE/'SHA256SUMS').write_text('\n'.join(lines)+'\n')
    print(f'通过：{len(checked)} 个输入哈希、2592 行扇区结果、合成标定与配方留出；无卡文件。')


if __name__ == '__main__':
    main()
