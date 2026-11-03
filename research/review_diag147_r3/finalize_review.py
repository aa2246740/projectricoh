"""Summarize evidence, verify frozen inputs, clean temporary storage, and hash the review."""
from pathlib import Path
import datetime
import json
import os
import plistlib
import re
import signal
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scope
scope.enable_fence()
signal.alarm(1800)
DAT_HASH = '85fd69ffcd8bf1566f0d9f1657bb8380240b6991ab1cacebc4a39f039533a532'
FX_HASH = '920560c157b93094137538baff18f957f16d253877556831933c83b0eb38af9b'


def read_json(name):
    return json.loads((HERE / name).read_text())


def summarize():
    hosts = []
    for case, unit in [('full', '50mm'), ('full', '28mm'), ('full', 'mount'),
                       ('faults', '50mm'), ('otherfile', '50mm'), ('otherfile', '28mm'), ('otherfile', 'mount')]:
        result = read_json('local/accept147-%s-%s.json' % (case, unit))
        timing = read_json('timing-accept_diag147.py-%s-%s.json' % (case, unit))
        assert result['dat'] == DAT_HASH and result['gxrfx'] == FX_HASH
        assert not result['violations'] and not result['card_writes'] and result['card_unchanged']
        assert not result['s_writes'] and result['s_hash_same'] and not result['rpc_w']
        assert not result['creates_renames_deletes'] and not result['high_level_fx_opens']
        assert timing['exit_code'] == 0 and timing['nice'] == 10
        row = dict(case=case, unit=unit, reads=len(result['reads']), seconds=timing['seconds'],
                   violations=result['violations'], card_writes=result['card_writes'], rpc_w=result['rpc_w'])
        if case == 'full':
            p1a = next(x for x in result['page_cycle'] if x['page'] == 1)
            p1b = next(x for x in result['page_cycle'] if x['page'] == 2)
            characters = ''.join(p1a['rows'][1:8] + p1b['rows'][1:6])
            assert characters == ''.join(chr(x) for x in range(0x20, 0x7f))
            assert p1b['rows'][6:] == ['1234567890ABCDEFGHIJKLMNOPQRSTUV', 'MW'*16]
            lengths = [len(bytes.fromhex(x)) for x in p1b['labels'][6:]]
            assert lengths == [64, 64]
            row.update(glyph_characters=len(characters), ruler_glyph_bytes=lengths)
        if case == 'otherfile':
            assert result['reads'][0]['result'] == 'BUSY' and result['reads'][0]['calls'] == ['try', 'signal']
            assert result['reads'][1]['result'] == 'OK'
        hosts.append(row)
    fault = read_json('local/accept147-faults-50mm.json')
    pages = {x['label']: x['dat_rows'] for x in fault['opens']}
    assert pages['open after busy'][2] == 'B L47' and pages['open after busy'][7] == 'IDFF L01'
    assert pages['open after one file open'][2] == 'B F1' and pages['open after one file open'][7] == 'IDFF L04'
    assert pages['open after two files open'][2] == 'B F2' and pages['open after two files open'][7] == 'IDFF L05'
    assert pages['open after clean'][7] == 'IDFF L05'
    gate = read_json('elf-gate-results.json')
    assert gate['status'] == 'PASS' and gate['dat_sha256'] == DAT_HASH
    static = read_json('static-diag147.json')
    assert static['status'] == 'PASS' and static['dat_sha256'] == DAT_HASH
    proof, _ = json.JSONDecoder().raw_decode((HERE / 'lock-proof.log').read_text())
    assert proof['status'] == 'PASS' and not proof['failures']
    assert all(x['caught'] for x in proof['open_count_gate']['mutants'].values())
    baseline = read_json('local/native-replay147.json')
    assert baseline['counts'] == {'PASS': 4, 'FAIL': 0, 'INCOMPLETE': 2}
    native = read_json('elf-native-handoff-results.json')
    assert native['counts'] == {'PASS': 2, 'FAIL': 0, 'INCOMPLETE': 0}
    for row in native['cases']:
        assert row['open_count'] == 0 and row['native_slot_volume'] == 1 and row['native_slot_index'] == 0
        assert row['lock_owner'] == 'diagnostic'
        assert [x['kind'] for x in row['requests']] == ['read', 'write']
        assert row['requests'][1]['args'][:3] == [0, 32, 3]
        assert row['requests'][1]['original_file_dirty'] == 1
        assert not row['close_phase_device_calls']
        assert not any(x['name'] in ('allocate_slot', 'slot_check') for x in row['native_boundaries'])
    closed = read_json('close-window-results.json')
    assert closed['counts'] == {'PASS': 4, 'FAIL': 0, 'INCOMPLETE': 0}
    for row in closed['cases']:
        assert row['volume_index'] == 1
        if row['mode'] == 'close_complete':
            assert row['close_result'] == 0 and row['dirty_after_close_phase'] == 0
            assert row['native_slot_volume'] == 255 and row['native_slot_index'] == 255
            assert row['first_request'] == 'read'
    timings = [json.loads(p.read_text()) for p in HERE.glob('timing-*.json')]
    assert all(row['nice'] == 10 and row['timeout_seconds'] >= row['seconds'] * 3 for row in timings)
    result = dict(verdict='不能上卡', new_p1_count=1, dat_sha256=DAT_HASH, gxrfx_sha256=FX_HASH,
                  host_groups=hosts, host_group_count=len(hosts), host_read_attempts=sum(x['reads'] for x in hosts),
                  fault_pages={k: pages[k] for k in ('open after busy', 'open after one file open',
                                                    'open after two files open', 'open after clean')},
                  original_native_replay=baseline['counts'], complete_close_and_handoff=closed['counts'],
                  actual_elf_and_native_handoff=native['counts'],
                  maximum_measured_seconds=max(x['seconds'] for x in timings), timeout_seconds=1800,
                  limits=['Host file internals are models in the seven acceptance groups.',
                          'The native handoff cases execute the ELF gate and native file operations on synthetic FAT32 RAM.',
                          'No physical camera, storage card, RTOS handoff, LCD width or real clock was measured.'])
    scope.save(HERE / 'verification-summary.json', result)
    blocks = []
    selections = [('engine-disassembly.txt', 0x384c, 0x3918),
                  ('local/native-listings/filesystem-full.asm.txt', 0x200a437c, 0x200a449c),
                  ('local/native-listings/filesystem-full.asm.txt', 0x200a4910, 0x200a4a58),
                  ('local/native-listings/filesystem-full.asm.txt', 0x200b86ec, 0x200b8890),
                  ('local/native-listings/filesystem-full.asm.txt', 0x200bb660, 0x200bb698)]
    for name, start, end in selections:
        blocks.append('%s %08x..%08x\n' % (name, start, end))
        for line in (HERE / name).read_text().splitlines():
            match = re.match(r'\s*([0-9a-f]+):', line)
            if match and start <= int(match[1], 16) < end:
                blocks.append(line + '\n')
        blocks.append('\n')
    (HERE / 'native-evidence.txt').write_text(''.join(blocks))
    return result


def verify_manifest():
    count = 0
    for line in (HERE / 'SHA256SUMS').read_text().splitlines():
        expected, name = line.split(None, 1)
        path = scope.ROOT / name.strip()
        assert path.is_relative_to(HERE) and scope.sha(path) == expected, name
        count += 1
    return count


mode = sys.argv[1] if len(sys.argv) > 1 else 'summarize'
if mode == 'verify':
    print('MANIFEST PASS', verify_manifest())
    sys.exit(0)
assert mode in ('summarize', 'finalize')
summary = summarize()
if mode == 'summarize':
    print(json.dumps({k: summary[k] for k in ('verdict', 'host_group_count', 'host_read_attempts',
                                              'maximum_measured_seconds', 'actual_elf_and_native_handoff')}, ensure_ascii=False))
    sys.exit(0)
assert (HERE / 'REVIEW.md').read_text().splitlines()[0] == '不能上卡'
volume = plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil', 'info', '-plist', '/Volumes/Workspace'], timeout=1800))
assert volume['MountPoint'] == '/Volumes/Workspace' and volume['FilesystemType'].lower() == 'apfs'
assert volume['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8' and volume['WritableVolume']
before = read_json('inputs-before.json')
changed = [name for name, row in before.items() if scope.sha(scope.ROOT / name) != row['sha256']]
roots = ['firmware/engine_diag_v38_g147', 'firmware/package_v38_diag147', 'research/diag147']
current = {str(p.relative_to(scope.ROOT)) for name in roots for p in (scope.ROOT / name).rglob('*') if p.is_file()}
expected = {name for name in before if any(name.startswith(root + '/') for root in roots)}
assert not changed and current == expected, (changed, sorted(current ^ expected))
assert scope.SCRATCH == Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-diag147-r3')
assert not scope.SCRATCH.is_symlink()
temporary_entries = len(list(scope.SCRATCH.rglob('*'))) if scope.SCRATCH.exists() else 0
if scope.SCRATCH.exists():
    for path in sorted(scope.SCRATCH.rglob('*'), key=lambda p: len(p.parts), reverse=True):
        if path.is_symlink() or path.is_file():
            path.unlink()
        else:
            path.rmdir()
    scope.SCRATCH.rmdir()
assert not scope.SCRATCH.exists()
scope.save(HERE / 'final-receipt.json', dict(status='PASS', frozen_files=len(before), changed_files=changed,
           input_tree_file_sets_unchanged=True, temporary_directory=str(scope.SCRATCH),
           temporary_entries_removed=temporary_entries, temporary_directory_absent=True,
           volume_uuid=volume['VolumeUUID'], filesystem=volume['FilesystemType'],
           write_locations=[str(HERE), str(scope.SCRATCH)], nice=os.getpriority(os.PRIO_PROCESS, 0),
           completed=datetime.datetime.now().astimezone().isoformat(),
           report_sha256=scope.sha(HERE / 'REVIEW.md')))
files = sorted(p for p in HERE.rglob('*') if p.is_file() and p.name != 'SHA256SUMS')
(HERE / 'SHA256SUMS').write_text(''.join(scope.sha(p) + '  ' + str(p.relative_to(scope.ROOT)) + '\n' for p in files))
count = verify_manifest()
print('FINAL PASS', 'frozen', len(before), 'review files', count, 'temporary directory absent',
      'manifest sha256', scope.sha(HERE / 'SHA256SUMS'))
