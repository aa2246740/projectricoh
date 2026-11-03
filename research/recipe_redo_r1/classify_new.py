"""Compare the new MOUNT JPEGs to frozen capture-era recipe rows, without fitting."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
from calibrate import sample
import collections
import hashlib
from gxr_studio.camdata import datcodec, knob_table
from gxr_studio.engine import menu, knobs


def bank():
    path = rt.source_copy('firmware/package_v38_g152_test/local/SD_ROOT/GXRCE.DAT')
    assert rt.sha(path) == '563c922711d4702a47724440537f9b29f4b5a920ab513dfffaf63a234955bc92'
    dat = datcodec.parse(path.read_bytes())
    current = rt.release_dat()
    builtin_matches = sum(dat.entry_of(ui, slot) == current.entry_of(ui, slot)
        for ui in range(3) for slot in range(1, 9))
    current_looks = {look.name: look.entry for look in current.looks}
    look_matches = sum(look.entry == current_looks.get(look.name) for look in dat.looks)
    assert builtin_matches == 24 and look_matches == len(dat.looks) == 10
    rt.dump('capture_current_row_equality.json', dict(capture_dat_sha256=rt.sha(path),
        current_dat_sha256=rt.sha(rt.SOURCE/'firmware/package_v39_g154_looks18_test/local/SD_ROOT/GXRCE.DAT'),
        builtin_552_byte_matches=builtin_matches, shared_look_552_byte_matches=look_matches,
        current_extra_looks=8, scope='exact data-row equality, no camera or DAT build'))
    entries = {f'{s:02d}': dat.entry_of(2, s) for s in range(1, 9)}
    assert dat.entry_of(2, 4) == rt.release_dat().entry_of(2, 4)
    for look in dat.looks:
        if look.unit_mask & 4:
            entries[look.name] = look.entry
    table = menu.load()
    table = knob_table.read(dat.kv2_block, table,
        mount_knobs_from_50mm=datcodec.PROFILES[dat.generation].mount_knobs_from_50mm)
    fields = ('contrast', 'highlight', 'shadow', 'saturation', 'fade', 'warmth', 'tint', 'split', 'filter', 'tone', 'amount')
    for name, user in zip(dat.user_names, dat.users):
        slot = user['base']
        rec = table['recipes'][2*8+slot-1]
        items = table['items'][rec['first_item']:rec['first_item']+rec['item_count']]
        chosen = dict(zip(fields, user['levels']))
        levels = [chosen[table['controls'][item['control']]['name']] for item in items]
        req = menu.request(table, 2, slot, levels)
        entries[name], _ = knobs.apply(dat.entry_of(2, 4), dat.entry_of(2, slot), req)
    rt.dump(rt.LOCAL/'new_capture_candidate_bank.json', dict(capture_dat=str(path), sha256=rt.sha(path),
        entries={k: v.hex() for k, v in entries.items()}, no_new_looks18_rows_used=True))
    signatures = collections.defaultdict(list)
    for name, e in entries.items():
        signature = bytes((e[1],)) + e[445:447] + b''.join(e[o:o+n] for o, n in zip(datcodec.OFFSETS, datcodec.ROW_BYTES))
        signatures[hashlib.sha256(signature).hexdigest()].append(name)
    equality = rt.read(rt.HERE/'capture_current_row_equality.json')
    equality.update(candidate_entries=len(entries), distinct_response_groups=len(signatures))
    rt.dump('capture_current_row_equality.json', equality)
    return entries, list(signatures.values())


def replay(model, entry, x):
    ordinary = bytearray(entry)
    ordinary[0] = 1  # Every candidate keeps Standard S; no special B&W model path.
    return np.rint(model.predict(bytes(ordinary), x))


def classify(errors, alias_groups, cells):
    med = {key: float(np.median(value)) for key, value in errors.items()}
    ordered = sorted(alias_groups, key=lambda names: (med[names[0]], names[0]))
    best, second = ordered[:2]
    b, s = best[0], second[0]
    blocks = [np.flatnonzero(cells == value) for value in np.unique(cells)]
    rng = np.random.default_rng(20261102)
    wins = 0
    for _ in range(200):
        ids = np.concatenate([blocks[j] for j in rng.integers(0, len(blocks), len(blocks))])
        wins += np.median(errors[b][ids]) < min(np.median(errors[names[0]][ids]) for names in ordered[1:])
    gap = med[s]-med[b]
    return dict(best_aliases=best, runner_aliases=second, median_de00=med[b], p95_de00=float(np.percentile(errors[b],95)),
        gap_de00=gap, spatial_block_win_fraction=wins/200, scores=med,
        model_supported=len(errors[b]) >= 48 and med[b] <= 3 and gap >= .75 and wins/200 >= .95,
        identity_is_model_inference=True, independent_recipe_truth=False)


def main():
    records = rt.read(rt.LOCAL/'new_materials_20261102.json')
    entries, aliases = bank()
    C = np.asarray(rt.read(rt.LOCAL/'calibration/mount-a12/mount_screen_20261101_degree1.json')['coefficients'])
    results = []
    for record in records:
        assert record['unit'] == 'mount-a12'
        values, info = sample(record)
        use = values['valid']
        raw = values['raw_wb'][use]
        actual = values['observed'][use]
        assert len(actual) >= 24
        centers = values['centers'][use]
        cells = (centers[:, 1].astype(int)//712)*4 + centers[:, 0].astype(int)//1072
        x = rt.calibration_apply(raw, C)
        model = rt.camera_model(2, iso=record['iso'])
        model200 = rt.camera_model(2)
        errors, control = {}, {}
        for name, entry in entries.items():
            errors[name] = rt.delta_e00(rt.lab_from_codes(replay(model, entry, x)), rt.lab_from_codes(actual))
            control[name] = rt.delta_e00(rt.lab_from_codes(replay(model200, entry, raw*4095)), rt.lab_from_codes(actual))
        main = classify(errors, aliases, cells)
        alternate = classify(control, aliases, cells)
        consensus = main['best_aliases'] == alternate['best_aliases']
        row = dict(frame=Path(record['path']).stem, iso=record['iso'], when=record['when'],
            unit=record['unit'], points=len(actual), light_group='scene light not independently recorded',
            selected_response_kernel=1600 if record['iso'] >= 566 else 200,
            frozen_calibration_used=True, no_new_jpeg_pixels_fitted=True,
            calibrated_input=main, transferred_200_without_input_correction=alternate,
            model_consensus=consensus,
            candidate_stock04=main['best_aliases']==['04'] and consensus and main['model_supported'],
            stock04_identity_independent_confirmation=False,
            calibration_admission='conditional inference only; excluded from strict 04 fitting without independent confirmation',
            raw_sha256=record['sha256'], jpeg_sha256=record['jpeg_pairs'][0]['sha256'])
        results.append(row)
        rt.dump(rt.LOCAL/'new_capture_response.json', results)
        print(row['frame'], row['iso'], main['best_aliases'], main['median_de00'], 'gap', main['gap_de00'],
            main['model_supported'], 'consensus', consensus, flush=True)
    summary = dict(pairs=len(results), supported=sum(r['calibrated_input']['model_supported'] for r in results),
        candidate04_frames=[r['frame'] for r in results if r['candidate_stock04']],
        inferred_groups=dict(collections.Counter('|'.join(r['calibrated_input']['best_aliases']) for r in results)),
        current_response_median=rt.stats([r['calibrated_input']['median_de00'] for r in results]),
        no_independent_labels=True, native_selector_alone_not_used=True, capture_bank='g152 test 563c9227',
        relation_to_current_g154_looks18='Existing 10 Looks and built-ins are capture-era rows; additional 8 current Looks were not assumed present')
    rt.dump('new_capture_response_summary.json', summary)
    print(summary)


if __name__ == '__main__':
    main()
