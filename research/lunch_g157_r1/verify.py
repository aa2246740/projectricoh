"""Read the real sealed artifacts again, including originals and independent pixel equations."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C


def main():
    C.admit('verify')
    C.numerical()
    C.sys.addaudithook(C.fence)
    np = C.np
    inputs = C.read(C.LOCAL / 'inputs.json')
    changed = [r['path'] for r in inputs['files'] if C.sha(r['path']) != r['sha256']]
    assert not changed, 'Model/input drift: ' + repr(changed)
    original_files = []
    for row in C.read(C.LOCAL / 'inventory.json'):
        for pathkey, hashkey, statkey in (('path', 'raw_sha256', 'raw_stat'), ('jpeg', 'jpeg_sha256', 'jpeg_stat')):
            p = Path(row[pathkey])
            assert C.sha(p) == row[hashkey]
            assert [p.stat().st_size, p.stat().st_mtime_ns] == row[statkey]
            original_files.append(dict(path=str(p), sha256=row[hashkey], stat_unchanged=True))
    assert len(original_files) == 114 and C.sha(C.DAT) == C.DAT_SHA
    # Independent published literal equations, not a second call to Model.predict.
    source = C.ROOT / 'research/bluecyan_r1/verify.py'
    tree = C.ast.parse(source.read_text())
    node = next(n for n in tree.body if isinstance(n, C.ast.FunctionDef) and n.name == 'predict_literal')
    scope = dict(np=np, struct=C.struct)
    exec(compile(C.ast.Module(body=[node], type_ignores=[]), str(source), 'exec'), scope)
    literal = scope['predict_literal']
    bank = C.read(C.LOCAL / 'bank.json')['records']
    maximum = 0.
    score_delta = 0.
    checks = []
    allframes = []
    for row in C.read(C.LOCAL / 'inventory.json'):
        if row['group'] == 'previous_day':
            continue
        pid = row['id']
        frame = C.LOCAL / 'frames' / pid
        saved = C.read(frame / 'result.json')
        with np.load(frame / 'samples.npz', allow_pickle=False) as z:
            v = dict(z)
        expected_input = C.input_codes(v['raw_codes'])
        assert np.array_equal(expected_input, v['conditioned'])
        model = C.camera_model(row['metadata']['iso'], row['metadata']['color_raw13'])
        fixed = C.read(C.ROOT / 'research/model_c040_r1/local/physical/ring-mount-a12-200.json')
        assert np.array_equal(model.engine.table.nodes, np.asarray(fixed['nodes_unwrapped_deg']))
        best = saved['best_index']
        record = Path(bank[best]['record']).read_bytes()
        replay = literal(model, record, v['conditioned'])
        diff = float(np.max(np.abs(replay-v['predictions'][best])))
        assert diff < 1e-8
        maximum = max(maximum, diff)
        err = C.de(replay, v['observed'])
        sd = float(np.max(np.abs(err-v['errors50'][best])))
        assert sd < 1e-8
        score_delta = max(score_delta, sd)
        held_stats = C.stats(err[v['held']])
        assert abs(held_stats['median']-saved['prediction_D50']['median']) < 1e-8
        assert not (v['identity'] & v['held']).any()
        assert np.array_equal(v['identity'] | v['held'], v['valid'])
        # Check every candidate's saved RGB against literal equations at 24 held points.
        selected = np.flatnonzero(v['held'])
        selected = selected[np.linspace(0, len(selected)-1, min(24, len(selected))).astype(int)]
        for j, r in enumerate(bank):
            entry = Path(r['record']).read_bytes()
            assert C.sha(r['record']) == r['sha256']
            q = literal(model, entry, v['conditioned'][selected])
            assert np.max(np.abs(q-v['predictions'][j, selected])) < 1e-8
        jpgs = list((frame / 'predictions').glob('*.jpg'))
        assert len(jpgs) == len(bank)
        for p in jpgs:
            with C.Image.open(p) as image:
                assert image.size == (256, 170) or image.size == (256, 171)
                image.verify()
        target = C.read(frame / 'targets.json')
        with np.load(frame / 'targets.npz', allow_pickle=False) as z:
            t = dict(z)
        for i, tag in enumerate(('best', 'second')):
            # Accepted frames may still retain a runner-up; its style is a sensitivity result.
            if i >= len(target['scores']):
                continue
            for mode, key in (('old', 'g157_original_target'), ('r2', 'film_r2_target')):
                s = target['scores'][i][key]
                if s is None:
                    continue
                den = float(np.median(t[f'{tag}_{mode}_baseline_target']))
                numerator = float(np.median(t[f'{tag}_{mode}_actual_target']))
                expected = None if den < .25 else 100*(1-numerator/den)
                assert expected == s['actual_similarity']
        checks.append(dict(id=pid, samples=len(err), max_literal_RGB_difference=diff,
                           max_literal_DE00_difference=sd, preview_count=len(jpgs),
                           spatial_masks_disjoint=True, style_formula_recomputed=True))
        allframes.append(saved)
    assert len(checks) == 55
    # Prove that the scene-target renderer matches the existing film-r2 cache,
    # including the unusually low real-scene Kodachrome25 score.
    from targets import Targets
    target_renderer = Targets()
    target_replays = []
    for name, oldindex, filmordinal in (('Kodachrome25', 22, 17), ('Portra 400', 20, 9), ('Vision3 500T', 24, 14), ('instax mini', 25, 18)):
        for convention in ('original', 'scene'):
            if convention == 'original':
                p = C.ROOT / 'research/model_c040_r1/local/targets/mount-a12' / f'{oldindex:02d}/photo_iso200.npz'
            else:
                p = C.ROOT / 'research/film_looks_r2/local/films' / f'{filmordinal:02d}/mount-a12/photo_iso200.npz'
            with np.load(p, allow_pickle=False) as z:
                value = dict(z)
            take = np.linspace(0, len(value['raw_codes'])-1, min(256, len(value['raw_codes']))).astype(int)
            raw, xyz = value['raw_codes'][take], value['xyz'][take]
            # C040 intentionally retained original targets computed from the old
            # 04 base; only the scene-r2 cache was rebuilt from scene light.
            basekey = 'base' if convention == 'original' else 'base_new' if 'base_new' in value else 'base'
            base = value[basekey][take]
            if convention == 'original':
                replay, valid, detail = target_renderer.old_target(name, raw, xyz, base)
            else:
                replay, detail = target_renderer.current_target(name, raw, xyz, base, None)
            expected = value['want'][take]
            maximum_target_difference = float(np.max(np.abs(replay-expected)))
            assert maximum_target_difference < 1e-8, (name, convention, maximum_target_difference)
            target_replays.append(dict(name=name, convention=convention, samples=len(take),
                                       max_RGB_difference=maximum_target_difference, frozen_cache_sha256=C.sha(p)))
    for name, path, official in (
        ('03 HC BW', C.ROOT / 'research/model_c040_r1/local/targets/mount-a12/29/photo_iso200.npz', False),
        ('Acros', C.ROOT / 'research/film_looks_r2/local/targets/mount-a12/14/photo_iso200.npz', True)):
        with np.load(path, allow_pickle=False) as z:
            value = dict(z)
        take = np.linspace(0, len(value['raw_codes'])-1, min(256, len(value['raw_codes']))).astype(int)
        raw, xyz = value['raw_codes'][take], value['xyz'][take]
        base = value['base_new' if 'base_new' in value else 'base'][take]
        if official:
            replay, detail = target_renderer.current_target(name, raw, xyz, base, None)
        else:
            replay, valid, detail = target_renderer.old_target(name, raw, xyz, base)
        difference = float(np.max(np.abs(replay-value['want'][take])))
        assert difference < 1e-8, (name, difference)
        target_replays.append(dict(name=name, samples=len(take), max_RGB_difference=difference,
                                   frozen_cache_sha256=C.sha(path)))
    summary = C.read(C.LOCAL / 'summary.json')
    assert summary['scopes']['lunch']['photos'] == 44
    assert summary['scopes']['morning']['photos'] == 11
    assert summary['scopes']['lunch']['accepted'] == sum(r['accepted'] for r in allframes if r['group'] == 'lunch')
    C.dump('originals-after.json', original_files)
    C.dump('verification.json', dict(status='PASS', original_photo_files=114, original_DAT_unchanged=True,
         model_input_files_unchanged=len(inputs['files']), native_c040_matches_frozen_reference=True,
         target_replays_against_existing_frozen_caches=target_replays,
         frame_checks=checks, max_literal_RGB_difference=maximum, max_literal_DE00_difference=score_delta,
         prediction_previews=55*len(bank), all_isolated=True, all_nice15=True,
         no_network_or_device_operations=True, created_utc=C.utc()))
    C.decision('verification', '重读原始文件并用独立字面方程复核预测',
               '缓存存在不代表原件未变，模型自报也不能代替重放',
               'local/verification.json; local/originals-after.json', 'PASS')
    print('VERIFY PASS', len(checks), 'frames, 114 originals,', len(inputs['files']),
          'model inputs, max literal RGB', maximum, flush=True)


if __name__ == '__main__':
    main()
