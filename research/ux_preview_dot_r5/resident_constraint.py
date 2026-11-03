"""Prove the H07 return constraint and read the unchanged resident byte budget."""
from pathlib import Path
import json
import re
import shutil
import struct
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, OUT, TREE, PACKAGE, save, file_sha, sha

resident = ROOT / 'firmware/resident_v36'
elf_path = resident / 'local/resident/build/resident.elf'
raw = elf_path.read_bytes()
h = struct.unpack_from('>16sHHIIIIIHHHHHH', raw)
sections = [struct.unpack_from('>10I', raw, h[6] + i*h[11]) for i in range(h[12])]
code = [p for p in sections if p[1] == 1 and p[2] & 4]
assert len(code) == 1
code = code[0]
begin, amount = code[3], code[5]
end = begin + amount
root_address, root_bytes, reserve = 0x20054700, 256, 200
assert begin == 0x2005276c and amount == 7884 and end == 0x20054638
assert root_address - end == reserve
linker = (resident / 'resident/resident.ld').read_text()
assert 'ASSERT(__resident_code_end <= 0x20054700 - 200' in linker
hooks = (resident / 'resident/hooks.c').read_text()
assert 'keep=hook==7?f[11]:1;' in hooks
assert 'else if(hook==7&&keep==0)(void)rv_ui_abort(r);' in hooks
assert 'if(hook==7&&(result==RV_CLOSE_AND_PASS||result==RV_FAULT||keep==0))skip=rv_close_07;' in hooks
objdump = ROOT / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
listing = subprocess.check_output([str(objdump), '-d', '--disassemble=rv_hook_observe', str(elf_path)], text=True)
listing = listing[listing.index('2005276c <rv_hook_observe>:'):]
(OUT / 'resident-h07-machine.txt').write_text(listing)
required = ('20052990:', '200529c4:', '20052aa4:', '20052aac:', '200529ec:')
assert all(pc in listing for pc in required)
records = []
for unit in ('50mm', '28mm', 'mount'):
    path = OUT / f'native/entry-switch-{unit}-ok-at1.json'
    row = json.loads(path.read_text())
    calls = row['call_trace']
    assert row['schedule']['fired'] and row['schedule']['resident_inflight'] == 1
    assert row['schedule']['after_native']['native_activity'] == 7
    assert row['schedule']['after_native']['native_overlay'] == 21
    assert any(c['function'] == 'release_view' and c['after_switch'] for c in calls)
    assert any(c['function'] == 'rv_ui_abort' and c['after_switch'] for c in calls)
    assert len(row['writes_after_switch']) == 9
    assert row['complete_slots'] == [4] and row['after']['W'] == 0
    assert row['after']['root']['state'] == 3 and row['after']['native_overlay'] == 0
    records.append(dict(unit=unit, record=str(path.relative_to(OUT)), sha256=file_sha(path),
        writes=len(row['writes_after_switch']), complete_slots=[4], W=0,
        release_view_reached=True, resident_abort_reached=True,
        overlay_after_constructor=21, overlay_after_completion=0))
save('resident-h07-constraint.json', dict(status='REQUIRES_RESIDENT_CHANGE',
    body_sha256=file_sha(ROOT/'firmware/image_v36/local/package/SD_ROOT/ilaunch3'),
    resident_elf_sha256=file_sha(elf_path), source_sha256=file_sha(resident/'resident/hooks.c'),
    keep_capture_pc='0x20052990', engine_call_pc='0x200529C4',
    keep_test_pc='0x20052AA4', abort_call_pc='0x20052AAC', close_selection_pc='0x200529EC',
    legal_returns=[dict(value=v, name=n, keep=0, abort=True, native_close=True)
                   for v,n in ((0,'RV_PASS'),(1,'RV_CONSUMED'),(2,'RV_CLOSE_AND_PASS'),(3,'RV_FAULT'))],
    native_records=records,
    reason='H07 captures keep in preserved r12 before calling the recipe. For keep=0, every valid engine return reaches resident restoration and the native close continuation. The existing ABI has no return that cancels this completion.'))
save('resident-byte-budget.json', dict(status='VERIFIED_UNCHANGED_ELF',
    code_begin=hex(begin), code_end=hex(end), code_bytes=amount,
    root_begin=hex(root_address), root_bytes=root_bytes, total_window_bytes=root_address+root_bytes-begin,
    occupied_bytes=amount+root_bytes, actual_gap_bytes=root_address-end,
    required_gap_bytes=reserve, allowed_net_code_growth_bytes=root_address-reserve-end,
    required_change='Recheck native menu ownership after rv_engine and before either H07 restoration or native close. A lost view must retain rv_skip_07.',
    budget_rule='Keep the 200-byte reserve: net code growth must be zero or less. Any N added bytes require at least N bytes recovered in the resident.',
    new_guard_compiled=False, new_guard_exact_bytes=None,
    reason='The task requires stopping construction once a resident dependency is proved; no modified resident was compiled.'))
partial = OUT / 'partial-runs/initial-candidate'
partial.mkdir(parents=True, exist_ok=True)
for name in ('GXRCE.DAT', 'engine.elf', 'engine.bin', 'manifest.json', 'layout.json'):
    shutil.copyfile(TREE / 'candidate/local/full-r13' / name, partial / name)
unaccepted = PACKAGE / 'unaccepted'
unaccepted.mkdir(exist_ok=True)
if (PACKAGE / 'SD_ROOT').exists():
    (PACKAGE / 'SD_ROOT').rename(unaccepted / 'SD_ROOT')
if (PACKAGE / 'CARD_SHA256SUMS').exists():
    (PACKAGE / 'CARD_SHA256SUMS').rename(unaccepted / 'CARD_SHA256SUMS')
(PACKAGE / 'STATUS.txt').write_text('STOPPED: requires a resident H07 change. The unaccepted directory is diagnostic evidence and has not passed acceptance.\n')
save('task-stop.json', dict(status='STOPPED_REQUIRES_RESIDENT_CHANGE', build_stopped=True,
    accepted_gen120_package=False, package_evidence='firmware/package_v36_g120b/unaccepted',
    initial_dat_sha256=file_sha(partial/'GXRCE.DAT'), resident_modified=False,
    next_decision='User decision on permitting a resident H07 ownership-completion change within the unchanged 200-byte reserve.'))
print('PROVED H07 requires a resident change; three units reproduce; resident code 7884 B, reserve 200 B, permitted growth 0 B', flush=True)
