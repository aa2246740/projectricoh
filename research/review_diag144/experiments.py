"""Bounded independent probes. Inputs and faults are host supplied, never camera events."""
from pathlib import Path
import hashlib
import json
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scope
scope.enable_fence()
scope.freeze_check()
a = scope.load(scope.ROOT / 'research/unit28_stock/accept_diag144.py', 'review144_probes')
a.DAT = a.base.DAT = scope.ROOT / 'firmware/package_v38_diag144/SD_ROOT/GXRCE.DAT'
a.HERE = a.base.HERE = scope.SCRATCH / 'experiments'
a.HERE.mkdir(parents=True, exist_ok=True)
a.FIELDS += ('ov_saved_a', 'ov_saved_b', 'ov_restored')
off = a.offsets()
R, NAMES, ROWS = a.R, a.NAMES, a.ROWS
m, h, p, w, syms = a.base.boot('28mm', ready=1)
settings = h.u(0x200c0dac)
state = dict(force=False)
writes, frees = [], []
h.b.add_write_trace(settings, settings+4096, lambda e: writes.append(dict(
    pc=hex(e.pc) if e.pc is not None else None, offset=e.address-settings,
    size=len(e.data), value=int.from_bytes(e.data, 'big'))))


def entered(b):
    block = h.u(R+56)
    if block:
        p.image_base = h.u(block+312)
        state['block'] = block
    return False


def forcing(b):
    if state['force'] and b.get_reg('r1') == 1:
        b.write(0x205a280f, bytes(1))
    return False


h.b.add_breakpoint(h.symbols['rv_invoke'], entered)
h.b.add_breakpoint(syms['rv_hook_observe'], forcing)
def freed(b):
    frees.append(hex(b.get_reg('r4')))
    return False


h.b.add_breakpoint(0x2005c038, freed)


def nb():
    return p.image_base + p.elf.symbols['n']


def field(name, size=1):
    return h.u(nb()+off[name], size)


def text():
    return [h.b.read(nb()+off['ov_rows']+9*i, 9).split(b'\0', 1)[0].decode('ascii') for i in range(8)]


def native(addr, args=()):
    value = m.fr.native(h, addr, args, steps=40000000)
    assert value.get('ok'), value
    return value


def open_menu(force=False):
    state['force'] = force
    h.parent()
    native(0x20287080)
    state['force'] = False
    return dict(names=hex(h.u(NAMES)), rows=h.u(ROWS, 1), cursor=h.u(0x2022f726, 1),
        opens=field('opens', 4), overlay=field('ov_on'), text=text())


def close():
    return native(0x202c2abc, (0x23,))


result = dict(dat_sha256=scope.sha(a.DAT), body_sha256=scope.sha(a.base.BODY),
    boundary='host-directed final M32R artifact calls; device edges modeled')
photo_start = len(writes)
photo_steps = []
for index, key in enumerate((0x2b, 0x23, 0x2b), 1):
    shot = open_menu(True)
    assert shot['text'][0].startswith('ABC'[index-1]+'%02X'%index), shot
    assert shot['rows'] == 8 and shot['overlay'] == 1
    done = native(0x202c2abc, (key,))
    photo_steps.append(dict(photo=index, snapshot=shot, close_key=hex(key),
        close_result=done['r0'], after_close_names=hex(h.u(NAMES)), after_close_rows=h.u(ROWS,1)))
result['three_photo_sequence'] = dict(steps=photo_steps,s_writes=writes[photo_start:])
assert not writes[photo_start:]
open_menu()
close()
initial = open_menu(True)
assert initial['overlay'] == 1 and initial['rows'] == 8

# All legal cursor values, including the added eighth row, through the real drawer.
detail_reads, detail_writes = set(), []
original_read = h.b.read


def read_trace(address, size):
    value = original_read(address, size)
    if h.b.running and 0x2023fd38 <= address < 0x2023fe20:
        detail_reads.add((h.b.pc, address, size))
    return value


h.b.read = read_trace
h.b.add_write_trace(0x2023fd38, 0x2023fe20, lambda e: detail_writes.append(hex(e.address)))
draws = []
for cursor in range(1, 9):
    h.b.write(0x2022f725, bytes([cursor]))
    h.b.write(0x2022f726, bytes([cursor]))
    start = len(writes)
    done = native(0x201fd360, (2, 0x2022f71c, 0))
    draws.append(dict(cursor=cursor, ok=done['ok'], s_writes=writes[start:]))
    assert not writes[start:]
h.b.read = original_read
result['eight_cursor_draws'] = dict(cases=draws,
    detail_reads=[dict(pc=hex(pc), address=hex(at), size=n) for pc, at, n in sorted(detail_reads)],
    detail_writes=detail_writes, eighth_record_zero=original_read(0x2023fd8c, 12) == bytes(12))
assert not detail_writes and result['eight_cursor_draws']['eighth_record_zero']
saved_cursor = dict(a=field('ov_saved_a'), b=field('ov_saved_b'))
back = open_menu()
close()
result['restore_from_cursor8'] = dict(saved=saved_cursor, publish=back,
    final_names=hex(h.u(NAMES)), final_rows=h.u(ROWS, 1),
    final_a=h.u(0x2022f725, 1), final_b=h.u(0x2022f726, 1))
assert h.u(NAMES) == a.STOCK and h.u(ROWS, 1) == 7
assert 1 <= h.u(0x2022f726, 1) <= 7

# 0x7c is not a navigation getter: distinguish legal EV settings from this model's invalid 1.
ev_cases = []
for value in (3, 9, 19, 1):
    open_menu(True)
    h.b.write(settings+0x63b, bytes([value]))
    start = len(writes)
    done = native(0x2029a1c8, (0x7c,))
    ev_cases.append(dict(before=value, after=h.u(settings+0x63b, 1),
        result=done['r0'], s_writes=writes[start:]))
    if value in (3, 9, 19):
        assert not writes[start:] and h.u(settings+0x63b, 1) == value
    else:
        assert h.u(settings+0x63b, 1) == 9
result['event_7c_legal_and_invalid_ev'] = ev_cases

# The actual loop passes a message pointer in r5. Three supplied failures omit it.
# These are synthetic messages, not established physical button payloads.
message_cases = []
for event, first in ((0x8d, 0x202e0408), (0x85, 0x202bfaa0), (0xbc, 0x202b767c)):
    open_menu(True)
    message = 0x206e1100
    data = bytearray(140)
    data[44:46] = h.b.read(settings+0xac0, 2)
    data[46:48] = h.b.read(settings+0xac2, 2)
    h.b.write(message, data)
    start = len(writes)
    done = m.fr.native(h, first, (event, message), steps=40000000)
    message_cases.append(dict(event=hex(event), message='synthetic 140 B, r5 set',
        result=done, s_writes=writes[start:]))
result['message_abi_probes'] = message_cases

# Native horizontal navigation still updates the remembered ADJ slot.
open_menu(True)
slot_before = h.u(settings+0x39f, 1)
start = len(writes)
native(0x202b848c, (0x22,))
horizontal = native(0x202bab34, (0x22,))
slot_after = h.u(settings+0x39f, 1)
result['horizontal_slot'] = dict(before=slot_before, after=slot_after,
    second_return=horizontal['r0'], s_writes=writes[start:],
    names=hex(h.u(NAMES)), rows=h.u(ROWS, 1))
assert slot_before != slot_after and any(e['offset'] == 0x39f for e in writes[start:])

# Saturation is a bounded negative control for the claimed per-entry counter change.
open_menu(True)
h.b.write(nb()+off['opens'], (254).to_bytes(4, 'big'))
h.b.write(nb()+off['refused'], bytes([254]))
one = open_menu(True)
two = open_menu(True)
result['counter_saturation'] = dict(first=one, second=two)
assert one['text'][0][:3] == two['text'][0][:3] == 'CFF'
assert two['opens'] == one['opens']+1

# The root corruption case is deliberately outside normal inputs. Keep it separate.
open_menu(True)
h.b.write(R+212, (h.u(R+212) | 8).to_bytes(4, 'big'))  # RF_BUSY
start = len(writes)
native(0x202c25b8, (0x20,))
result['busy_guard'] = dict(s_writes=writes[start:], rows=h.u(ROWS, 1))
assert not writes[start:]
h.b.write(R+212, (h.u(R+212) & ~8).to_bytes(4, 'big'))
h.b.write(R, bytes(4))
start = len(writes)
native(0x202c25b8, (0x20,))
result['root_corruption_negative'] = dict(s_writes=writes[start:], normal_path=False)
assert any(e['offset'] == 0x36e for e in writes[start:])
result['published_main_allocation'] = dict(block=hex(state['block']),
    allocated=h.u(state['block']-8, 1), span=h.u(state['block']-4), free_calls=frees)
scope.save(scope.HERE/'experiments-ui.json', result)
print('UI_PROBES_PASS', flush=True)

# Execute the exact v3.8 save/read functions with RAM-backed block services only.
# No raw firmware or saved parameter bytes are retained in review outputs.
replay = scope.load(scope.ROOT/'research/persist_recipe/replay.py', 'review144_persist')
replay.collect.OFFICIAL = a.base.BODY
replay.collect.EXPECTED = a.base.BODY_SHA
r = replay.Rig()
try:
    before = bytearray(r.valid_s())
    before[0x39f], before[0x63b] = slot_after, 14
    r.cpu.write(replay.S, before)
    r.stub(0x2009ac80, 0, 'block_write_model', r.block_write)
    assert r.call(0x20067bb4) == 0
    saved = r.blocks
    assert saved[0x39f] == slot_after and saved[0x63b] == 14
    saved_hash = hashlib.sha256(saved).hexdigest()
    save_events = r.events
finally:
    r.close()
r = replay.Rig()
try:
    r.blocks = saved
    r.stub(0x2009ac58, 0, 'block_read_model', r.block_read)
    assert r.call(0x20067d68) == 0
    loaded = r.cpu.read(replay.S, 4096)
    assert loaded == saved
    persistence = dict(body_sha256=a.base.BODY_SHA, backend='GNU libsim; locks/notify and block device modeled',
        save_entry='0x20067bb4', read_entry='0x20067d68', saved_size=len(saved), saved_sha256=saved_hash,
        loaded_sha256=hashlib.sha256(loaded).hexdigest(), slot_offset='0x39f', slot_value=loaded[0x39f],
        ev_offset='0x63b', ev_value=loaded[0x63b], save_events=save_events, read_events=r.events)
    scope.save(scope.HERE/'experiments-persistence.json', persistence)
finally:
    r.close()
scope.freeze_check()
print('PERSISTENCE_PROBES_PASS', flush=True)
