"""C validation and the passing round-4 host suite extended to generation 107."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c
import host_compile

CHANGED = {(0, 2), (2, 2)}
SLOTS = {0: (1, 2, 5), 1: (1,), 2: (1, 2)}
VALUES = [3, 2, -2, 1, 0, 0]


def identity_changed(generation, unit, slot):
    if generation == 105:
        return (unit, slot) in {(0, 1), (0, 2), (2, 1), (2, 2)}
    assert generation == 106
    return (unit, slot) in CHANGED


def validate_and_expand(out, pack):
    validators = []
    for name in pack.NAMES:
        result = c.run([out / 'validate', c.OUT / 'GXRCE.DAT', c.OUT / 'trust.bin', name],
                       'validate-' + name)
        assert 'OK build=107' in result.stdout and 'semantic=1' in result.stdout
        validators.append(dict(unit=name, status='PASS', output=result.stdout.strip()))
    streams = {}
    for label, folder in (('full-r3', c.R3), ('full-r4', c.BASE), ('full-r5', c.OUT)):
        result = c.run([out / 'expand', folder / 'GXRCE.DAT', folder / 'trust.bin'], 'expand-' + label)
        rows = [line.split() for line in result.stdout.splitlines()]
        assert len(rows) == 48
        streams[label] = {(int(row[0]), int(row[1])): [bytes.fromhex(v) for v in row[2:]] for row in rows}
        assert set(streams[label]) == {(mi, slot) for mi in range(3) for slot in range(1, 17)}
    manifest = json.loads((c.OUT / 'manifest.json').read_text())
    replacements = {(row['unit'], row['slot']): row for row in manifest['changes']}
    checks = []
    for mi, name in enumerate(pack.NAMES):
        for slot in range(1, 17):
            key = mi, slot
            entry, record, binding, default = streams['full-r5'][key]
            old_entry, old_record, old_binding, old_default = streams['full-r4'][key]
            assert tuple(map(len, (entry, record, binding, default))) == (448, 64, 160, 240)
            assert entry == (c.OUT / 'expanded' / name / f'{slot:02}.entry').read_bytes()
            assert old_entry == (c.BASE / 'expanded' / name / f'{slot:02}.entry').read_bytes()
            assert record == old_record
            assert pack.u32(record, 60) == pack.crc(record[:60])
            if key in CHANGED:
                source = replacements[name, slot]
                table = (c.ROOT / source['source']).read_bytes()
                entries = [table[16 + 448*i:16 + 448*(i+1)] for i in range(8)]
                expected = next(e for e in entries if e[0] == 2)
                assert entry == expected == (c.HERE / 'local/rebound' / name / '02.entry').read_bytes()
                assert pack.u32(entry, 4) == pack.crc(pack.identity(record))
                assert entry != old_entry and binding != old_binding and default != old_default
            else:
                assert (entry, binding, default) == (old_entry, old_binding, old_default)
            for generation, label in ((105, 'full-r3'), (106, 'full-r4')):
                assert (binding != streams[label][key][2]) == identity_changed(generation, mi, slot)
            checks.append(dict(unit=name, slot=slot, changed=key in CHANGED,
                               entry_sha256=hashlib.sha256(entry).hexdigest(),
                               record_sha256=hashlib.sha256(record).hexdigest(),
                               record_identical=True, binding_changed=binding != old_binding,
                               default_identical=default == old_default))
    # Independently retain both Posi entries and the v6 Posi/Nega pair.
    sources = (
        (0, 1, 'research/gr4_dense_returns_r1/local/candidate/DEEPTBL_50mm_gr4_positive_r1.DAT', 1),
        (2, 1, 'research/gr4_dense_returns_r1/local/mount/candidate/DEEPTBL_mount_gr4_positive_r1.DAT', 1),
        (0, 9, 'research/refit_50mm_r7/local/v6/candidate_v6.DEEPTBL', 1),
        (0, 10, 'research/refit_50mm_r7/local/v6/candidate_v6.DEEPTBL', 2),
    )
    for mi, slot, path, source_slot in sources:
        raw = (c.ROOT / path).read_bytes()
        expected = bytearray(next(raw[16 + 448*i:16 + 448*(i+1)] for i in range(8)
                                  if raw[16 + 448*i] == source_slot))
        expected[0] = slot
        pack.p32(expected, 4, pack.crc(pack.identity(streams['full-r5'][mi, slot][1])))
        assert streams['full-r5'][mi, slot][0] == expected
    effective = []
    for label, folder in (('full-r3', c.R3), ('full-r4', c.BASE), ('full-r5', c.OUT)):
        rows = bytearray()
        per_slot = {}
        for mi in range(3):
            stock = streams[label][mi, 4][0]
            for slot in range(1, 17):
                entry = streams[label][mi, slot][0]
                values = bytearray()
                for _, count, offset, _, mask, _ in pack.v1.ROWS:
                    source = entry if not mask or entry[1] & mask else stock
                    values += source[offset:offset + count]
                values += (0 if entry[1] & 4 else 2).to_bytes(2, 'big')
                assert len(values) == 410
                per_slot[mi, slot] = bytes(values)
                rows += values
        assert bytes(rows) == (folder / 'effective-rows.bin').read_bytes()
        effective.append((label, per_slot))
    r4_effective, r5_effective = effective[1][1], effective[2][1]
    assert {key for key in r5_effective if r5_effective[key] != r4_effective[key]} == CHANGED
    summary = dict(status='PASS', validators=validators, expanded_slots=48, changed_entries=2,
                   unchanged_entries=46, identical_records=48, effective_slots=48,
                   expanded_containers=3, total_expanded_slots=144,
                   retained_GR_IV_Posi_50mm01_and_Mount01=True, retained_v6_50mm09_10=True,
                   unchanged_entry_binding_default_vectors=46, slots=checks)
    c.save(c.LOCAL / 'slot-checks.json', summary)
    return streams, summary


def verify_gxts(evidence, generation, unit, expanded):
    result = []
    old_label = 'full-r3' if generation == 105 else 'full-r4'
    for slot in SLOTS[unit]:
        old_path = evidence / f'slot-{slot:02}-saved-old.BIN'
        cold_path = evidence / f'slot-{slot:02}-cold107.BIN'
        old, cold = old_path.read_bytes(), cold_path.read_bytes()
        assert cold == old and len(old) == 240 and old[:4] == b'GXTS'
        assert struct.unpack_from('>HHII', old, 4) == (2, 192, 240, 1)
        assert int.from_bytes(old[16:20], 'big') == zlib.crc32(old[:16] + bytes(4) + old[20:]) & 0xffffffff
        assert struct.unpack_from('>HHII', old, 180) == (6, 8, 192, 0)
        assert [struct.unpack_from('>Ii', old, 192 + 8*i) for i in range(6)] == list(enumerate(VALUES, 1))
        assert old[20:180] == expanded[old_label][unit, slot][2]
        changed = identity_changed(generation, unit, slot)
        assert (old[20:180] != expanded['full-r5'][unit, slot][2]) == changed
        result.append(dict(unit=unit, slot=slot, old_generation=generation, new_generation=107,
                           saved_values=VALUES, effective_after107=[0]*6 if changed else VALUES,
                           outcome='RESET_IDENTITY' if changed else 'KEPT',
                           GXTS_file_generation=1, GXTS_file_bytes=240, old_file_retained=True,
                           before_sha256=c.sha(old_path), after_sha256=c.sha(cold_path)))
    return result


def run_case(binary, expanded, generation, folder, scenario, unit):
    evidence = c.LOCAL / 'host-evidence' / f'{scenario}-{generation}-{unit}'
    evidence.mkdir(parents=True)
    result = c.run([binary, scenario, unit, folder / 'GXRCE.DAT', c.OUT / 'GXRCE.DAT',
                    c.OUT / 'trust.bin', folder / 'effective-rows.bin', c.OUT / 'effective-rows.bin', evidence],
                   f'flow-{scenario}-{generation}-{unit}')
    lines = result.stdout.splitlines()
    assert lines[-1].startswith('OK ') and 'missing_open=-1' in lines[-1]
    first = 'first' in scenario
    update = 'update' in scenario
    if first:
        assert result.stdout.count('FIRST_PASS ') == 1
        assert result.stdout.count('SAVE_PASS ') == 0
        gxts = []
    else:
        assert result.stdout.count('IV_B_PASS ') == 1
        assert result.stdout.count('SAVE_PASS ') == len(SLOTS[unit])
        if update:
            assert result.stdout.count('D_PASS ') == 1
        else:
            assert result.stdout.count('IV_A_PASS ') == 1
            assert 'install=RV_CONFLICT rows=16 no_writes=1 SaveFail=0 disabled=0' in result.stdout
        gxts = verify_gxts(evidence, generation, unit, expanded)
    single = first or 'single' in scenario
    expected_a = c.OUT if single else folder
    assert (evidence / 'IROM-GXRCE0.DAT').read_bytes() == (expected_a / 'GXRCE.DAT').read_bytes()
    if single:
        assert not (evidence / 'IROM-GXRCE1.DAT').exists()
    else:
        assert (evidence / 'IROM-GXRCE1.DAT').read_bytes() == (c.OUT / 'GXRCE.DAT').read_bytes()
    assert not (evidence / 'card-GXRCE.DAT').exists()
    if 'empty' in scenario:
        assert not (evidence / 'card-GXRCE.OK').exists()
    else:
        assert (evidence / 'card-GXRCE.OK').read_bytes() == (c.OUT / 'GXRCE.DAT').read_bytes()
    return dict(scenario=scenario, old_generation=generation, unit=unit, status='PASS', GXTS=gxts,
                assertions=int(re.search(r'assertions=(\d+)', lines[-1])[1]),
                evidence=str(evidence.relative_to(c.HERE)),
                observations=[line for line in lines if line.startswith((
                    'FIRST_PASS', 'IV_A_PASS', 'IV_B_PASS', 'READONLY_PASS', 'SAVE_PASS', 'GXTS_PASS', 'D_PASS'))])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt', required=True)
    args = parser.parse_args()
    assert re.fullmatch(r'attempt-[0-9]{2}', args.attempt)
    run_dir = c.LOCAL / args.attempt
    assert not run_dir.exists(), 'Preserve previous attempts; choose a new directory after a development fix'
    frozen = c.freeze_check()
    c.LOCAL = run_dir
    c.guard()
    stage, results = 'DEVELOPMENT_COMPILE', []
    try:
        _, pack, build = c.upstream()
        layout = json.loads((c.OUT / 'layout.json').read_text())
        header = (c.ROOT / 'firmware/engine_fix_r2/local/product/entries.h').read_text()
        for name, offset in layout['entries'].items():
            assert f'#define OFF_{name.upper()} {offset}u\n' in header
        c.write(c.LOCAL / 'fixture-source.c', (c.HERE / 'host.c').read_bytes())
        c.write(c.LOCAL / 'verifier-source.py', Path(__file__).read_bytes())
        out = host_compile.compile_all(build)
        stage = 'PRODUCT_CONTAINER_VALIDATION'
        expanded, vectors = validate_and_expand(out, pack)
        cases = [(105, c.R3, scenario, unit) for scenario in ('r5-first-reject', 'r5-first-replace') for unit in range(3)]
        cases += [(generation, folder, scenario, unit)
                  for generation, folder in ((105, c.R3), (106, c.BASE))
                  for scenario in ('r5-update-reject', 'r5-update-replace',
                                   'r5-conflict-pair-ok', 'r5-conflict-pair-empty',
                                   'r5-conflict-single-ok', 'r5-conflict-single-empty')
                  for unit in range(3)]
        for generation, folder, scenario, unit in cases:
            stage = f'PRODUCT_BEHAVIOUR {scenario} old={generation} unit={unit}'
            results.append(run_case(out / 'host_checks', expanded, generation, folder, scenario, unit))
            c.save(c.LOCAL / 'host-results.json', results)
            print(json.dumps(dict(scenario=scenario, old=generation, unit=unit, status='PASS',
                                  GXTS=[r['outcome'] for r in results[-1]['GXTS']])), flush=True)
        assert c.freeze_check() == frozen
        summary = dict(status='PASS', generation=107, sha256=c.sha(c.OUT / 'GXRCE.DAT'),
                       host_cases=len(results), first_install_cases=6, clean_update_cases=12,
                       old_card_conflict_cases=24, cold107_cases=42,
                       assertions=sum(r['assertions'] for r in results),
                       GXTS_slot_observations=sum(len(r['GXTS']) for r in results),
                       GXTS_update_slot_observations=sum(len(r['GXTS']) for r in results if 'update' in r['scenario']),
                       GXTS_update_distinct_slots=6, protected_inputs=len(frozen), protected_inputs_unchanged=True,
                       validator_units=3, expanded_slots=48, total_expanded_slots=144,
                       changed_entries=2, unchanged_entries=46, identical_records=48, effective_slots=48,
                       sanitizers=['ASan', 'UBSan'], warnings_as_errors=True, real_missing_open=-1,
                       stage='READY_TO_STAGE_HOST_ONLY', camera_acceptance=False)
        c.save(c.LOCAL / 'verification.json', summary)
        c.save(c.LOCAL / 'scope-after.json', dict(status='PASS', protected_inputs=len(frozen), unchanged=True))
        print(json.dumps(summary), flush=True)
    except Exception as error:
        c.save(c.LOCAL / 'failure.json', dict(status='FAILED_REQUIRES_CLASSIFICATION', stage=stage,
               error=repr(error), completed_cases=len(results), card_files_staged=False, camera_acceptance=False))
        raise


if __name__ == '__main__':
    main()
