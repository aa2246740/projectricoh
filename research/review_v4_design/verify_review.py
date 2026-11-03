#!/usr/bin/python3 -I -B
"""Offline checks for the v4 design review; no target files are produced."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import subprocess
import sys

ROOT = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
OUT = ROOT / 'research/review_v4_design'
SCRATCH = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-v4')
BEGIN, CAPACITY = 0x20704800, 262144


def digest(data):
    return hashlib.sha256(data).hexdigest()


def frozen_inputs():
    rows = json.loads((OUT / 'input_receipt.json').read_text())['read_only_inputs']
    changed = [r['path'] for r in rows
               if digest((ROOT / r['path']).read_bytes()) != r['sha256']]
    assert not changed, changed
    manifest = ROOT / 'research/body_v4_design/SHA256SUMS'
    checked = []
    for line in manifest.read_text().splitlines():
        expected, name = line.split(None, 1)
        name = name.lstrip('*')
        path = (ROOT / name).resolve()
        assert path.is_relative_to(ROOT)
        assert digest(path.read_bytes()) == expected, name
        checked.append(name)
    assert len(checked) == 44
    return {'frozen_count': len(rows), 'changed': changed, 'manifest_passed': len(checked)}


def static_checks():
    raw = (ROOT / 'artifacts/firmware/gxr-1.51/ilaunch3').read_bytes()
    assert digest(raw) == 'da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7'
    sections = [struct.unpack_from('>5I', raw, 32 + 20 * i) for i in range(16)]
    checked, mismatches = 0, []
    for path in sorted((ROOT / 'research/tooling_m32r/disasm').glob('ilaunch3-sec*.disasm.txt')):
        for line in path.read_text().splitlines():
            match = re.match(r'^([0-9a-f]+):\s*\t((?:[0-9a-f]{2}\s+)+)\t', line)
            if not match:
                continue
            address = int(match[1], 16)
            code = bytes.fromhex(match[2])
            for source, base, size, _, _ in sections:
                if base <= address and address + len(code) <= base + size:
                    checked += 1
                    offset = source + 512 + address - base
                    if raw[offset:offset + len(code)] != code:
                        mismatches.append({'file': path.name, 'pc': hex(address)})
                    break
    assert checked > 500000 and not mismatches, (checked, mismatches[:10])
    command = ['/usr/bin/python3', '-I', '-B',
               str(ROOT / 'research/body_v4_design/static/er_scan.py')]
    scan = json.loads(subprocess.check_output(command, text=True))
    saved = json.loads((ROOT / 'research/body_v4_design/static/er-scan.json').read_text())
    saved.pop('note', None)
    normalized = dict(scan)
    normalized['raw_words'] = dict(scan['raw_words'])
    for name, compact in saved['raw_words'].items():
        if isinstance(compact, dict):
            assert set(compact) == {'count', 'first'}
            normalized['raw_words'][name] = {
                'count': len(scan['raw_words'][name]),
                'first': scan['raw_words'][name][:len(compact['first'])]}
    assert normalized == saved
    images = []
    for reserved, expected in (
            (0xc80000, '7cca5869f82091e756b9877bf468cd984edd8f67a90be81977768dbc7628bd8c'),
            (0xc40000, '2d0de3c8b4adf1b2bbb341b71b0b4540bbb77f5ee11b4641ff15bd7d284cacff')):
        modified = bytearray(raw)
        locations = [source + 512 + 0x200c0dd4 - base
                     for source, base, size, _, _ in sections
                     if base <= 0x200c0dd4 < base + size]
        assert locations == [0x75fd4]
        assert struct.unpack_from('>I', raw, locations[0])[0] == 0x076c0000
        struct.pack_into('>I', modified, locations[0], 0x076c0000 - reserved)
        content = modified[512:]
        checksum = sum(sum(content[k::6]) * (k + 2) for k in range(6)) & 0xffffffff
        struct.pack_into('>I', modified, 0x16c, checksum)
        assert digest(modified) == expected
        changed = [i for i, (a, b) in enumerate(zip(raw, modified)) if a != b]
        assert all(0x16c <= i < 0x170 or 0x75fd4 <= i < 0x75fd8 for i in changed)
        images.append({'reserved_bytes': reserved, 'image_sha256': expected,
                       'changed_offsets': [hex(i) for i in changed]})
    return {'disassembly_rows_equal_to_official': checked,
            'scan_equal_to_saved_compact_representation': True,
            'top16_constants': [scan[k] for k in
                ('constants_in_top16_8window_count', 'constants_in_top16_2window_count')],
            'resolved_table_loads': scan['table_accesses']['loads'],
            'resolved_table_stores': scan['table_accesses']['store_count'],
            'end_relative_candidates': len(scan['end_relative_sites']),
            'length_images_reconstructed_in_memory': images,
            'limit': 'linear scan only; no complete pointer or DMA ownership proof'}


def recovery_checks():
    base = json.loads((ROOT / 'research/body_v39/evidence/recovery-yes-official.json').read_text())
    keys = ('label', 'step', 'task', 'path', 'r0', 'r4')
    sequence = lambda doc: [tuple(row.get(k) for k in keys) for row in doc['milestones']]
    result = []
    for filename in ('recovery-yes-er12m5.json', 'recovery-yes-er12m25c.json'):
        run = json.loads((ROOT / 'research/body_v4_design/static' / filename).read_text())
        assert sequence(run) == sequence(base) and len(run['milestones']) == 99
        assert run['nand_commands'] == base['nand_commands']
        assert run['steps'] == base['steps'] == 500000000
        assert run['confirm_phase']['confirm_step'] == 65975242
        assert run['stop'] == base['stop'] == 'budget'
        old = [h for h in run['hooks_or_resident_executed'] if not h.startswith('hook-word C-')]
        assert not old and not run['pc_in_resident_window']
        candidate = {k: v for k, v in run['counts'].items() if k.startswith('hook-word C-')}
        if filename.endswith('25c.json'):
            assert candidate['hook-word C-rect'] == 91
            assert all(candidate.get('hook-word ' + x, 0) == 0 for x in
                       ('C-H42', 'C-thumb-fn', 'C-osd-present', 'C-osd-copy', 'C-osd-type67'))
        result.append({'file': filename, 'image_sha256': run['image_sha256'],
                       'milestones': len(run['milestones']), 'identical_sequence': True,
                       'nand_counts_equal': True, 'steps': run['steps'], 'stop': run['stop'],
                       'files_opened': sum(r['label'] == 'file-open' for r in run['milestones']),
                       'candidate_counts': candidate,
                       'recorded_library_sha256': run['library_sha256']})
    return {'runs': result, 'new_full_boot_runs': 0,
            'limit': 'rechecked recorded observations; no NAND completion or camera evidence'}


def geometry_and_oracles():
    reservation, frame = 0xc40000, 2144 * 2848 * 2
    assert reservation == 12845056 and frame == 12212224
    assert 0x50000 + frame == 0xbf5800
    assert reservation - (0x50000 + frame) == 305152
    bands = ((0, 632), (2216, 2848))
    invalid_rows = sum(max(0, end - max(start, 2416)) for start, end in bands)
    assert invalid_rows == 432
    ticks = []
    for rate in (40000000, 15000000):
        duration_ms = 65536 / rate * 1000
        observed = sorted({math.floor(phase / 1000 + duration_ms) for phase in range(1000)})
        ticks.append({'actual_bytes_per_second': rate, 'duration_ms': duration_ms,
                      'possible_1ms_ticks': observed,
                      'reported_bytes_per_second': [65536 / n * 1000 for n in observed]})
    original = bytes(range(256)) * 16
    after_fill = bytes([0xa5]) * len(original)
    before_sum = digest(after_fill)
    native_read = bytes(after_fill)
    assert digest(after_fill) == before_sum and native_read != original
    return {'er_bytes': reservation, 'frame_bytes': frame, 'tail_bytes': 305152,
            'hardcoded_2848_bands_on_2416_rows': {
                'invalid_rows': invalid_rows, 'invalid_bytes': invalid_rows * 8576,
                'correct_16_9_bands': [[0, 416], [2000, 2416]]},
            'bandwidth_tick_quantization': ticks,
            'sentinel_read_only_client_counterexample': {
                'sentinel_unchanged': True, 'native_source_data_changed': True,
                'scope': 'acceptance-condition model; not a claim about a specific native DMA path'}}


def native_heap_checks():
    assert os.environ.get('GXR_EMULATOR_BATCH') == '1'
    sys.path.insert(0, str(ROOT / 'tools/gxr_emulator_batch'))
    import outputs
    from backend import Backend
    from image import Image
    outputs.require(SCRATCH)
    image = Image('official')
    results = []
    for split in (False, True):
        with Backend(mode='fast') as cpu:
            cpu.set_batch(True)
            image.load(cpu)
            cpu.set_reg('sp', 0x206ffff0)
            calls = []

            def call(address, value=None):
                if value is not None:
                    cpu.set_reg('r4', value)
                stopped = cpu.call(address, (), 0x0bad0000, 2000000)
                assert stopped.reason == 'return', stopped.to_dict()
                value_out = cpu.get_reg('r0')
                calls.append({'entry': hex(address), 'argument': value,
                              'result': hex(value_out), 'steps': stopped.steps})
                return value_out

            def free_blocks():
                address = struct.unpack('>I', cpu.read(BEGIN, 4))[0]
                seen, blocks = set(), []
                while address:
                    assert BEGIN <= address < BEGIN + CAPACITY and address not in seen
                    seen.add(address)
                    following, flag, size = struct.unpack('>IB3xI', cpu.read(address, 12))
                    assert flag == 0 and size >= 12
                    blocks.append({'address': hex(address), 'span': size})
                    address = following
                return blocks

            call(0x200bbd98)
            temporary = [call(0x200bbe00, size) for size in (8560, 938, 8560)]
            barriers = [call(0x200bbe00, size) for size in (32768, 32768, 32768, 16384, 16384, 938)]
            assert all(temporary + barriers)
            for pointer in temporary:
                call(0x200bbf20, pointer)
            assert call(0x2005bf5c, 608)
            if split:
                assert call(0x2005bf5c, 8192)
                assert call(0x2005bf5c, 99908)
                own_span = 620 + 8204 + 99920
            else:
                assert call(0x2005bf5c, 108124)
                own_span = 620 + 108136
            blocks = free_blocks()
            if split:
                stopped = cpu.call(0x200da69c, (), 0x0bad0000, 2000000)
                assert stopped.reason == 'fault', stopped.to_dict()
                assert cpu.get_reg('r4') == 0
                attempt = {'reason': stopped.reason, 'pc': hex(stopped.pc),
                           'steps': stopped.steps, 'detail': stopped.detail,
                           'destination_r4': cpu.get_reg('r4')}
            else:
                pointer = call(0x200bbe00, 12368)
                assert pointer
                attempt = {'allocation_returned': hex(pointer), 'success': True}
            assert cpu.batch_stats.get('batch-steps', 0) > 0
            results.append({'layout': 'extension_and_dat' if split else 'single_main',
                            'own_span': own_span, 'free_blocks_before_client': blocks,
                            'total_free': sum(b['span'] for b in blocks),
                            'max_free': max(b['span'] for b in blocks),
                            'client_12368': attempt, 'calls': calls,
                            'batch_stats': dict(cpu.batch_stats)})
    assert results[1]['own_span'] == 108744 < results[0]['own_span']
    assert results[0]['max_free'] >= 12392 > results[1]['max_free']
    return {'image_sha256': image.sha256, 'results': results,
            'precondition': 'explicit native allocation history; its camera reachability is not established',
            'limit': 'native instruction counterexample to a total-only condition, not a full RTOS test'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output).resolve()
    assert output.is_relative_to(OUT) or output.is_relative_to(SCRATCH)
    assert Path(os.environ['TMPDIR']).resolve() == SCRATCH
    assert SCRATCH.is_dir()
    result = {'input_before': frozen_inputs(), 'static': static_checks(),
              'recorded_recovery': recovery_checks(), 'arithmetic': geometry_and_oracles(),
              'native_heap': native_heap_checks(), 'input_after': frozen_inputs(),
              'review_checker_adjustment': {
                  'first_run': 'AssertionError at direct scan == saved comparison',
                  'cause': 'saved raw_words uses count and first entries, while stdout contains full lists',
                  'correction': 'compare exact counts and saved prefixes, and compare all other fields exactly',
                  'classification': 'review checker format correction; original design inputs unchanged'}}
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'output': str(output), 'inputs_unchanged': True,
                      'scan_reproduced': True, 'recorded_recovery_equal': True,
                      'heap_counterexample_confirmed': True}, ensure_ascii=False))


if __name__ == '__main__':
    main()
