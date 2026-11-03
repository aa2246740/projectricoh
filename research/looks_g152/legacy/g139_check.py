"""Host checks for g139 (M32R model; device, S and graphics leaves are models).

g150 copy of research/review_g139/tests/g139_check.py. Only the test package
(G150_TEST_PACKAGE) and the host-C source tree (taken from G139_ENGINE) are
parameters; the case code is unchanged unless a case says otherwise.

Covers DESIGN.md P1-01, P1-02, P1-03 (option B + MY dial), P2-01, P2-02,
P2-04, C and the user-entry titles. Each case boots a fresh model.
Results: research/g139_fix/tests/local/checks/<unit>-<case>.json.
  /usr/bin/python3 -I -B research/g139_fix/tests/g139_check.py <case...|all|set1|set2> [--unit 50mm]
"""
from pathlib import Path
import argparse
import json
import os
import sys
import time
import traceback
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g139_host as H

CONT1 = [100, 1, 0, 0, 0, 0, 0, 0, 0, 0]
ZERO = [100, 0, 0, 0, 0, 0, 0, 0, 0, 0]
STOCK_L1 = [' 1 GRPos', ' 2 GRNeg', ' 3 HC BW', '>4 Std', ' 5 F-CC', ' 6 F-CN', ' 7 L-Chr', ' 8 L-Viv']
UNMARKED_L1 = [' 1 GRPos', ' 2 GRNeg', ' 3 HC BW', ' 4 Std', ' 5 F-CC', ' 6 F-CN', ' 7 L-Chr', ' 8 L-Viv']
TEST_DAT = H.ROOT / os.environ.get('G150_TEST_PACKAGE', 'firmware/package_v38_g150_test') / 'local/SD_ROOT/GXRCE.DAT'
MY_BYTE = 0x205D9AA3
OK_KEY, ADJ_KEY = 0x23, 0x2B


# ---- helpers ---------------------------------------------------------------
def boot(unit, record=None, normal=True, dat=None, lock=-1):
    cam = H.Camera(unit, normal=normal, dat=dat)
    if record is not None:
        cam.put_s(0xfd4, record)
    cam.set_lock(lock)
    cam.calls = []
    def seen(b):
        cam.calls.append((b.core.r[0], b.core.r[1]))
        return False
    def loaded(b):
        # The DAT image base is known once the resident invokes it; register
        # the service-call counter on the first invocation only.
        if not cam.calls_ready and cam.p.image_base:
            cam.calls_ready = True
            cam.h.b.add_breakpoint(cam.symbol('rv_call'), seen)
        return False
    cam.calls_ready = False
    cam.h.b.add_breakpoint(cam.h.symbols['rv_invoke'], loaded)
    cam.stock_rows = cam.unit_rows()
    return cam


def valid(cam, slot=5, levels=CONT1):
    return H.record_bytes(H.DAT_BYTES[cam.dat_path], slot, H.UNITS[cam.unit], levels)


def calls(cam, sid, op):
    return sum(1 for x in cam.calls if x == (sid, op))


def snap(cam):
    return dict(S=cam.s_bytes(0, 4096), W=cam.writes(), lock=cam.lock(), log=len(cam.p.rpc.log))


def delta(cam, before):
    S = cam.s_bytes(0, 4096)
    log = cam.p.rpc.log[before['log']:]
    return dict(S_changed=[hex(i) for i in range(4096) if before['S'][i] != S[i]], W=cam.writes() - before['W'],
                reads=sum(e['cmd'] == 21 for e in log), lock=cam.lock())


def frame(cam):
    st = cam.check_frame()
    assert all(0 < len(t) <= 8 and all(32 <= ord(c) <= 126 for c in t) for t in st['labels']), st
    return st


def opened(cam):
    before = snap(cam)
    cam.open_menu()
    return frame(cam), delta(cam, before)


def press(cam, key):
    before = snap(cam)
    cam.press(key)
    return cam.state(), delta(cam, before)


def half(cam):
    fr = cam.m.fr
    for pc in (0x2029fdc4, 0x202bd724):
        result = fr.native(cam.h, pc, (0x29, 0), steps=30000000)
        assert result.get('ok'), result
    return cam.state()


def rows_equal_stock(cam):
    rows, t = cam.unit_rows()
    return rows == cam.stock_rows[0] and t == 2


def reference(unit, slot, levels):
    """Normal boot, no record, the same state chosen with keys: rows, T and S."""
    cam = boot(unit, bytes(40))
    opened(cam)
    cam.goto(slot - 1)
    if levels != ZERO:
        cam.press('DISP'); cam.press('DISP'); cam.goto(1); cam.press('DISP'); cam.press('UP')
        assert cam.levels() == levels, cam.state()
    rows, t = cam.unit_rows()
    return dict(rows=rows, T=t, S=cam.s_bytes(0, 4096), record=cam.record())


def card_default(cam):
    """L1 -> card of the applied slot -> Default (arm, apply)."""
    cam.press('DISP'); assert cam.ui('screen') == 1, cam.state()
    for row in range(8):
        cam.goto(row)
        if cam.labels()[cam.ui('physical')] == 'Default':
            break
    else:
        raise AssertionError(('no Default row', cam.state()))
    cam.press('DISP'); assert cam.ui('armed') == 1, cam.state()
    before = snap(cam)
    cam.press('DISP')
    return delta(cam, before)


# ---- P1-03 option B: offer, never apply at H01 ------------------------------
def cold_none(unit):
    cam = boot(unit, bytes(40))
    st, d = opened(cam)
    assert st['labels'] == STOCK_L1 and st['slot'] == 4 and st['cur'] == 3 and st['levels'] == ZERO, st
    assert d['W'] == 0 and d['S_changed'] == [] and cam.record() == bytes(40) and d['lock'] == (-1, 55), d
    return dict(state=st, delta=d)


def offered(unit, **kw):
    cam = boot(unit, **kw)
    record = valid(cam)
    cam.put_s(0xfd4, record)
    st, d = opened(cam)
    return cam, record, st, d


def offer(unit):
    cam, record, st, d = offered(unit)
    expect = list(STOCK_L1); expect[4] = ' 5*F-CC'
    assert st['labels'] == expect and st['cur'] == 4 and st['slot'] == 4 and st['levels'] == ZERO, st
    assert d['W'] == 0 and d['S_changed'] == [] and cam.record() == record and rows_equal_stock(cam), d
    assert calls(cam, 6, 2) == 0 and calls(cam, 6, 5) == 0, cam.calls
    return dict(state=st, delta=d)


def offer_ok(unit):
    cam, record, st, _ = offered(unit)
    assert st['cur'] == 4, st
    after, d = press(cam, 'OK')
    assert after['rows'] == 7, after
    rows, t = cam.unit_rows()
    S = cam.s_bytes(0, 4096)
    assert cam.record() == record, cam.record().hex()
    again, d2 = opened(cam)
    expect = list(UNMARKED_L1); expect[4] = '>5*F-CC'
    assert again['labels'] == expect and again['cur'] == 4 and d2['W'] == 0, again
    # One model per process at a time: the keyed reference boots after this one is done.
    ref = reference(unit, 5, CONT1)
    assert rows == ref['rows'] and t == ref['T'], 'OK apply differs from keyed apply (rows/T)'
    S_diff = [hex(i) for i in range(4096) if S[i] != ref['S'][i]]
    assert S_diff == [], ('OK apply differs from keyed apply (S)', S_diff)
    return dict(apply=d, reopen=again['labels'])


def exit_pure(how):
    def case(unit):
        cam, record, st, _ = offered(unit)
        before = snap(cam)
        if how == 'adj':
            cam.press('ADJ')
        else:
            half(cam)
        d = delta(cam, before)
        assert d['W'] == 0 and d['S_changed'] == [] and rows_equal_stock(cam) and cam.record() == record, d
        again, d2 = opened(cam)
        # Pure 04 applied; row 5 keeps the remembered values as its preview cache.
        expect = list(STOCK_L1); expect[4] = ' 5*F-CC'
        assert again['labels'] == expect and again['cur'] == 3 and d2['W'] == 0, again
        return dict(exit=d, reopen=again['labels'])
    return case


def offer_move_ok(unit):
    cam, record, st, _ = offered(unit)
    cam.press('DOWN')                    # row 5 = recipe 6, previewed as usual
    assert cam.ui('slot') == 6 and cam.record() == valid(cam, 6, ZERO), cam.state()
    cam.press('OK')
    rows, t = cam.unit_rows()
    record = cam.record()
    assert record == valid(cam, 6, ZERO)
    ref = reference(unit, 6, ZERO)
    assert rows == ref['rows'] and t == ref['T']
    return dict(record=record.hex())


def offer_disp(unit):
    cam, record, st, _ = offered(unit)
    card = cam.press('DISP')
    assert card['screen'] == 1 and card['slot'] == 5 and card['levels'] == CONT1, card
    assert card['labels'][0] == '<5*F-CC', card
    rows, t = cam.unit_rows()
    assert cam.record() == record
    ref = reference(unit, 5, CONT1)
    assert rows == ref['rows'] and t == ref['T']
    return dict(card=card['labels'])


def offer_unconfirmed(unit):
    cam = boot(unit)
    cam.put_s(0xfd4, valid(cam))
    dat = H.DAT_BYTES[cam.dat_path]
    directory = int.from_bytes(dat[156:160], 'big') + 64 * H.UNITS[unit]
    mapping = dat[int.from_bytes(dat[directory + 12:directory + 16], 'big'):][:152]
    address = int.from_bytes(mapping[32 + 24:36 + 24], 'big') & ~1
    cam.p.rpc.overlay[address] = cam.p.rpc.half(address) ^ 0x0101
    st, d = opened(cam)
    assert st['labels'] == UNMARKED_L1 and st['cur'] == 3 and d['W'] == 0 and d['S_changed'] == [], st
    return dict(state=st)


def my(value):
    def case(unit):
        cam = boot(unit)
        record = valid(cam)
        cam.put_s(0xfd4, record)
        cam.h.b.write(MY_BYTE, bytes([value]))
        st, d = opened(cam)
        assert d['W'] == 0 and d['S_changed'] == [] and cam.record() == record, d
        if value:
            assert st['labels'] == STOCK_L1 and st['cur'] == 3, st          # baseline confirmed, no offer
        else:
            assert st['cur'] == 4 and st['labels'][4] == ' 5*F-CC', st
        return dict(state=st)
    return case


def my_replay(unit):
    """Original instructions of the MY dispatcher 0x202E43D4: byte 1/2/3 -> recall(r4=0/1/2)."""
    out = {}
    for value in (0, 1, 2, 3):
        cam = boot(unit, bytes(40))
        hits = []
        def recall(b):
            hits.append(b.core.r[4])
            b.core.r[0] = 0
            b.pc = b.core.r[14]           # return at once: the recall itself is not under test
            return False
        cam.h.b.add_breakpoint(0x20262EF0, recall)
        cam.h.b.write(MY_BYTE, bytes([value]))
        cam.h.b.write(0x205DA00B, b'\x01')      # the dispatcher's recall-pending flag (tested at 0x202E440C)
        result = cam.m.fr.native(cam.h, 0x202E43D4, (), steps=20000000)
        out[value] = dict(ok=result.get('ok'), reason=result.get('reason'), recall_r4=hits[:3])
    assert out[0]['recall_r4'] == [] and [out[v]['recall_r4'][:1] for v in (1, 2, 3)] == [[0], [1], [2]], out
    return out


def bad(kind):
    def case(unit):
        cam = boot(unit)
        dat, u = H.DAT_BYTES[cam.dat_path], H.UNITS[unit]
        good = bytearray(valid(cam))
        if kind == 'crc':
            good[39] ^= 1
        elif kind == 'magic':
            good = bytearray(H.record_bytes(dat, 5, u, CONT1, magic=b'GXR1'))
        elif kind == 'unit':
            good = bytearray(H.record_bytes(dat, 5, (u + 1) % 3, CONT1))
        elif kind == 'dataid':
            good[28] ^= 0x80
            good[36:40] = (zlib.crc32(bytes(good[:36])) & 0xffffffff).to_bytes(4, 'big')
        elif kind == 'slot0':
            good = bytearray(H.record_bytes(dat, 0, u, ZERO))
        elif kind == 'slot9':
            good = bytearray(H.record_bytes(dat, 9, u, ZERO))
        elif kind == 'flags':
            good = bytearray(H.record_bytes(dat, 5, u, CONT1, flags=3))
        elif kind == 'version':
            good = bytearray(H.record_bytes(dat, 5, u, CONT1, version=2))
        elif kind == 'level':
            good = bytearray(H.record_bytes(dat, 5, u, [100, 20, 0, 0, 0, 0, 0, 0, 0, 0]))
        elif kind == 'garbage':
            good = bytearray([1] * 40)
        record = bytes(good)
        cam.put_s(0xfd4, record)
        st, d = opened(cam)
        assert st['labels'] == STOCK_L1 and st['cur'] == 3 and st['levels'] == ZERO, st
        assert d['W'] == 0 and d['S_changed'] == [] and cam.record() == record, d
        return dict(state=st)
    return case


def ineligible(kind):
    def case(unit):
        cam = boot(unit, normal=kind != 'raw')
        cam.put_s(0xfd4, valid(cam))
        marked = UNMARKED_L1
        if kind == 'mode4':
            cam.put_s(0x36e, b'\x04')
        elif kind == 'wb':
            cam.put_s(0x6dd, b'\x0a')
        elif kind == 'source':
            cam.put_s(8, b'\x01')
        elif kind == 't0':
            cam.p.rpc.t = 0
            marked = list(UNMARKED_L1); marked[3] = ' 4 Error'
        elif kind == 'extension':
            cam.put_s(0xe, b'\x01\x01')
            marked = STOCK_L1
        record = cam.record()
        st, d = opened(cam)
        assert st['labels'] == marked and st['cur'] == 3 and st['levels'] == ZERO, st
        assert d['W'] == 0 and d['S_changed'] == [] and cam.record() == record, d
        return dict(state=st)
    return case


# ---- P1-01: unverified boot, first apply writes and reads back everything ---
def p101_partial(unit):
    cam = boot(unit)
    dat = H.DAT_BYTES[cam.dat_path]
    directory = int.from_bytes(dat[156:160], 'big') + 64 * H.UNITS[unit]
    mapping = dat[int.from_bytes(dat[directory + 12:directory + 16], 'big'):][:152]
    address = int.from_bytes(mapping[32 + 24:36 + 24], 'big') & ~1
    cam.p.rpc.overlay[address] = cam.p.rpc.half(address) ^ 0x0101
    st, _ = opened(cam)
    assert st['labels'] == UNMARKED_L1, st
    d = card_default(cam)
    full = sum(len(r) for r in cam.stock_rows[0])
    assert d['W'] * 2 >= full and d['reads'] >= d['W'], ('first apply is not a full write and read-back', d, full)
    cam.press('OK')
    assert rows_equal_stock(cam), 'rows did not return to stock'
    assert cam.record() == valid(cam, 4, ZERO), cam.record().hex()
    return dict(apply=d, row_bytes=full)


def p101_five_mode4(unit):
    donor = boot(unit, bytes(40))
    opened(donor); donor.goto(4)
    dat = H.DAT_BYTES[donor.dat_path]
    directory = int.from_bytes(dat[156:160], 'big') + 64 * H.UNITS[unit]
    mapping = dat[int.from_bytes(dat[directory + 12:directory + 16], 'big'):][:152]
    halves = {}
    for i in range(9):
        address = int.from_bytes(mapping[32 + 12 * i:36 + 12 * i], 'big')
        size = int.from_bytes(mapping[36 + 12 * i:38 + 12 * i], 'big')
        for a in range(address & ~1, address + size, 2):
            halves[a] = donor.p.rpc.half(a)
    del donor
    cam = boot(unit)
    cam.p.rpc.overlay.update(halves)
    cam.put_s(0x36e, b'\x04')
    st, _ = opened(cam)
    assert st['labels'] == UNMARKED_L1, st
    d = card_default(cam)
    cam.press('OK')
    assert rows_equal_stock(cam), 'rows did not return to stock'
    assert cam.s_bytes(0x36e, 1) == b'\x01' and cam.s_bytes(0x6dd, 2) == b'\x09\x09', cam.s_bytes(0x36e, 1)
    assert cam.record() == valid(cam, 4, ZERO)
    return dict(apply=d)


def t_boot(unit):
    """T is 0 at power-on: list published, row 4 marked, no write until the user chooses 04."""
    cam = boot(unit, bytes(40))
    cam.p.rpc.t = 0
    st, d = opened(cam)
    assert st['labels'][3] == ' 4 Error' and d['W'] == 0 and d['S_changed'] == [], (st, d)
    card_default(cam)
    rows, t = cam.unit_rows()
    assert rows == cam.stock_rows[0] and t == 2, ('T not restored by the full write', t)
    st = frame(cam)
    cam.press('OK')
    again, _ = opened(cam)
    assert again['labels'] == STOCK_L1, again
    return dict(first=st['labels'], reopen=again['labels'])


def p101_normal(unit):
    cam = boot(unit, bytes(40))
    opened(cam)
    before = snap(cam)
    cam.press('DOWN')
    d = delta(cam, before)
    full = sum(len(r) for r in cam.stock_rows[0])
    assert 0 < d['W'] * 2 < full, ('normal boot must stay a difference write', d, full)
    return dict(apply=d, row_bytes=full)


# ---- P1-02: unknown tails stay read-only -------------------------------------
def tail(kind):
    def case(unit):
        cam = boot(unit)
        dat, u = H.DAT_BYTES[cam.dat_path], H.UNITS[unit]
        start = {'random': bytes((i * 37 + 11) & 255 for i in range(40)),
                 'gxr1': H.record_bytes(dat, 5, u, CONT1, magic=b'GXR1'),
                 'badcrc': bytes(valid(cam)[:39]) + bytes([valid(cam)[39] ^ 1]),
                 'v2': H.record_bytes(dat, 5, u, CONT1, version=2),
                 'nomagic': bytes(4) + bytes(valid(cam)[4:])}[kind]
        cam.put_s(0xfd4, start)
        opened(cam)
        cam.press('DOWN')
        st = frame(cam)
        assert cam.record() == start and st['labels'][4] == '>Unsaved', st
        cam.press('DOWN')
        st = frame(cam)
        assert cam.record() == start and st['labels'][5] == '>Unsaved', st
        assert calls(cam, 6, 5) == 1, ('op 5 retried on an unknown tail', calls(cam, 6, 5))
        return dict(labels=st['labels'], op5=calls(cam, 6, 5))
    return case


def tail_own(unit):
    cam = boot(unit, None)
    cam.put_s(0xfd4, valid(cam, 6, ZERO))
    st, _ = opened(cam)
    assert st['cur'] == 5, st                                           # 6 is offered
    cam.press('UP')                                                    # choose 5: our own record is replaced
    assert cam.record() == valid(cam, 5, ZERO) and frame(cam)['labels'][4] == '>5 F-CC', cam.record().hex()
    return dict(record=cam.record().hex())


def tail_race(unit):
    cam = boot(unit, bytes(40))
    opened(cam)
    armed = {'op5': False, 'done': False}
    def entry(b):
        if (b.core.r[0], b.core.r[1]) == (6, 5) and not armed['done']:
            armed['op5'] = True
        return False
    def irq(b):
        if armed['op5'] and not armed['done']:
            armed['done'] = True
            cam.h.b.write(cam.s + 0xfd4 + 7, b'\x5a')          # the tail changes after the snapshot
        return False
    cam.h.b.add_breakpoint(cam.symbol('rv_call'), entry)
    cam.h.b.add_breakpoint(cam.symbol('rv_irq_save'), irq)
    before = snap(cam)
    cam.press('DOWN')
    d = delta(cam, before)
    assert armed['done'] and d['S_changed'] == ['0xfdb'] and cam.lock() == (-1, 55), d
    assert frame(cam)['labels'][4] == '>Unsaved'
    return dict(delta=d)


def tail_user(unit):
    start = bytes((i * 37 + 11) & 255 for i in range(40))
    cam = boot(unit, start, dat=TEST_DAT)
    opened(cam)
    cam.goto(9); cam.press('DISP'); cam.goto(5); cam.press('DISP')     # MyRec -> FCC
    cam.goto(2)                                                        # moving onto an entry applies it
    assert cam.ui('screen') == 5 and cam.ui('applied_user'), cam.state()
    assert cam.record() == start, 'a user entry cleared an unknown tail'
    return dict(state=cam.state())


# ---- P2-01 / P2-02: busy lock and the unsaved row ---------------------------
def record_busy(unit):
    cam = boot(unit)
    old = valid(cam, 5, ZERO)
    cam.put_s(0xfd4, old)
    st, _ = opened(cam)
    assert st['cur'] == 4 and st['labels'][3] == '>4 Std', st
    cam.set_lock(0)
    cam.press('DOWN')
    st = frame(cam)
    assert st['slot'] == 6 and cam.record() == old and cam.lock() == (0, 55) and st['labels'][5] == '>Unsaved', st
    cam.set_lock(-1)
    card = cam.press('DISP')                     # H06 boundary: the retry stores the record
    assert card['screen'] == 1 and card['labels'][0] == '<6 F-CN' and cam.record() == valid(cam, 6, ZERO), card
    cam.goto(0); back = cam.press('DISP')        # title row: back to L1, redrawn with the stored state
    assert back['screen'] == 0 and back['labels'][5] == '>6 F-CN', back
    return dict(card=card['labels'], back=back['labels'])


def record_busy_reopen(unit):
    """Known limit: a retry inside the H01 publication cannot redraw that frame."""
    cam = boot(unit)
    cam.put_s(0xfd4, valid(cam, 5, ZERO))
    opened(cam)
    cam.set_lock(0); cam.press('DOWN'); cam.press('ADJ')
    cam.set_lock(-1)
    st, _ = opened(cam)
    assert cam.record() == valid(cam, 6, ZERO), cam.record().hex()
    assert st['labels'][5] in ('>Unsaved', '>6 F-CN'), st
    cam.press('DISP'); cam.goto(0); st3 = cam.press('DISP')
    assert st3['screen'] == 0 and st3['labels'][5] == '>6 F-CN', st3
    return dict(h01_frame=st['labels'][5], next_frame=st3['labels'][5])


def held_lock(unit):
    cam = boot(unit, bytes(40))
    cam.put_s(0x6dd, b'\x0a')
    opened(cam)
    cam.set_lock(0)
    before = snap(cam); n2 = calls(cam, 6, 2)
    cam.press('DOWN')
    d = delta(cam, before)
    st = frame(cam)
    assert calls(cam, 6, 2) - n2 == 1, ('op 2 attempts per key', calls(cam, 6, 2) - n2)
    assert st['failed'] == 0 and d['S_changed'] == [] and cam.lock() == (0, 55), (st, d)
    assert st['labels'][4] == '>Unsaved', st
    cam.set_lock(-1)
    card = cam.press('DISP')                     # next boundary completes S and the record
    assert cam.s_bytes(0x6dd, 1) == b'\x09' and cam.record() == valid(cam, 5, ZERO), cam.s_bytes(0x6dd, 1)
    cam.goto(0); back = cam.press('DISP')
    assert back['labels'][4] == '>5 F-CC', back
    return dict(key=d, labels=back['labels'])


def t_error(unit):
    cam = boot(unit, bytes(40))
    opened(cam)
    cam.press('DOWN')                       # 5 applied, baseline confirmed
    cam.p.rpc.t = 0                         # the unit's T control changed under us
    cam.press('DOWN')                       # 6 is refused on T
    st = frame(cam)
    assert st['labels'][5][1:] == '6 Error' and st['labels'][4] == '>5 F-CC', st
    return dict(labels=st['labels'])


# ---- P2-04: length and version re-read inside the critical section ---------
def length_race(what):
    def case(unit):
        cam = boot(unit, bytes(40))
        if what == 'op2':
            cam.put_s(0x6dd, b'\x0a')
        opened(cam)
        target = (6, 2) if what == 'op2' else (6, 5)
        armed = {'on': False, 'done': False}
        def entry(b):
            if (b.core.r[0], b.core.r[1]) == target and not armed['done']:
                armed['on'] = True
            return False
        seen = {}
        def irq(b):
            if armed['on'] and not armed['done']:
                armed['done'] = True
                seen['S'] = cam.s_bytes(0, 4096)
                if what == 'version':
                    cam.h.b.write(cam.s + 0xe, b'\x0d\x25')
                else:
                    cam.h.b.write(0x200c0db0, (0xfff).to_bytes(4, 'big'))
            return False
        def restored(b):
            # The raced call's critical section ends here: capture S, undo the change.
            if armed['done'] and 'after' not in seen:
                seen['after'] = cam.s_bytes(0, 4096)
                seen['lock'] = cam.lock()
                cam.h.b.write(cam.s + 0xe, b'\x0d\x24')
                cam.h.b.write(0x200c0db0, (0x1000).to_bytes(4, 'big'))
            return False
        cam.h.b.add_breakpoint(cam.symbol('rv_call'), entry)
        cam.h.b.add_breakpoint(cam.symbol('rv_irq_save'), irq)
        cam.h.b.add_breakpoint(cam.symbol('rv_irq_restore'), restored)
        cam.press('DOWN')
        changed = [hex(i) for i in range(4096) if seen['S'][i] != seen['after'][i] and i not in (0xe, 0xf)]
        assert armed['done'] and changed == [] and seen['lock'] == (-1, 55), (changed, seen.get('lock'))
        return dict(changed=changed)
    return case


# ---- inherited P2-04: a failed preview, then close and reopen ---------------
def preview_fail_reopen(unit):
    cam = boot(unit, bytes(40))
    opened(cam)
    fired = []
    def fail(b):
        if not fired:
            fired.append(cam.p.rpc.t)
            b.core.r[0] = 1                  # the native preview reports a failure once
            b.pc = b.core.r[14]
        return False
    cam.h.b.add_breakpoint(cam.symbol('rv_native_preview'), fail)
    cam.press('DOWN')
    after_key = frame(cam)
    cam.press('ADJ')
    st, d = opened(cam)
    applied = [i for i, x in enumerate(st['labels']) if x.startswith('>')]
    assert fired and len(applied) == 1, (fired, st)
    slot = applied[0] + 1
    rows, t = cam.unit_rows()
    S = cam.s_bytes(0, 4096)
    ref = reference(unit, slot, ZERO)
    assert rows == ref['rows'] and t == ref['T'], ('rows/T do not match the shown recipe', slot)
    assert S[0x36e] == ref['S'][0x36e] and S[0x6dd:0x6df] == ref['S'][0x6dd:0x6df], 'S does not match the shown recipe'
    return dict(after_key=after_key['labels'], reopen=st['labels'], shown_slot=slot, reopen_W=d['W'])


# ---- C and B (user titles) --------------------------------------------------
def value_ends(unit):
    cam = boot(unit, bytes(40))
    opened(cam)
    cam.goto(0)
    card = cam.press('DISP'); items = cam.press('DISP')
    assert not any('!' in x for x in card['labels'] + items['labels']), (card, items)
    for i in range(items['count']):
        if cam.goto(i)['labels'][cam.ui('physical')].startswith('Satu'):
            break
    cam.press('DISP')
    seen = []
    top = {'50mm': 6, '28mm': 6, 'mount': 8}[unit]       # GR Pos Satu cap per unit (knob table)
    for key, end in (('UP', top), ('DOWN', -9)):
        for _ in range(20):
            b = cam.state(); a = cam.press(key); seen.append(a['labels'][a['physical']])
            if a['levels'][5] == b['levels'][5]:
                break
        assert a['levels'][5] == end and a['labels'][a['physical']] == 'Satu  %+d' % end, a
        assert not any('!' in x for x in a['labels']), a
    return dict(value_labels=seen)


def users(unit):
    cam = boot(unit, bytes(40), dat=TEST_DAT)
    opened(cam)
    cam.goto(9); cam.press('DISP'); assert cam.ui('screen') == 4
    cam.goto(5); cam.press('DISP'); assert cam.ui('screen') == 5
    st = cam.goto(2)
    assert st['labels'][st['physical']] == '>FCC-001' and cam.record() == bytes(40), st
    card = cam.press('DISP'); assert card['screen'] == 1 and card['labels'][0] == '<FCC-001', card
    items = cam.press('DISP'); assert items['screen'] == 2 and items['labels'][0] == '<FCC-001', items
    cam.goto(1); cam.press('DISP'); cam.press('UP')
    back = cam.press('DISP')
    assert back['labels'][0] == '<FCC*001', back
    assert cam.record() == bytes(40)
    cam.press('OK')
    again = boot(unit, cam.record(), dat=TEST_DAT)
    st2, d2 = opened(again)
    assert st2['labels'] == STOCK_L1 and st2['cur'] == 3 and d2['W'] == 0, st2
    return dict(card=card['labels'], items=items['labels'])


def host_compute(unit, slot, levels):
    """552-byte entry from a host-C build of the same engine sources."""
    import ctypes as ct, os, subprocess
    product = H.ENGINE.parents[2] / 'containers/product'
    core, container = product / 'src/firmware/engine/core', product / 'src/firmware/card_container_v2'
    sources = [H.ROOT / 'research/emptystack_v38/host_engine.c', product / 'memory.c', product / 'ui_v2_data.c',
               product.parents[1] / 'engine_services/crc.c']
    sources += [core / n for n in ('eng_data.c', 'eng_semantic.c', 'eng_crc_compat.c', 'eng_pin_stub.c')]
    sources += [container / n for n in ('common.c', 'gate.c', 'api.c')]
    sources += [product / 'kv2' / n for n in ('kv_data.c', 'kv_ui.c', 'kv_math.c', 'kv_i64.c')]
    out = H.TMP / 'check-host.dylib'
    if not out.exists():
        subprocess.run(['clang', '-std=c11', '-O2', '-shared', '-fPIC', '-DENG_HOST', '-ffreestanding', '-fno-builtin',
                        '-I', str(core), '-I', str(product), '-I', str(container), *map(str, sources), '-o', str(out)],
                       check=True, capture_output=True, env=dict(os.environ, TMPDIR=str(H.TMP)))
    class Levels(ct.Structure):
        _fields_ = [('v', ct.c_int16 * 10)]
    lib = ct.CDLL(str(out))
    dat = H.DAT.read_bytes()
    memory = (ct.c_uint8 * len(dat)).from_buffer_copy(dat)
    assert lib.g135_open(memory, len(dat), H.UNITS[unit]) == 0
    entry = (ct.c_uint8 * 552)()
    assert lib.g135_compute(slot, ct.byref(Levels((ct.c_int16 * 10)(*levels))), entry) == 0
    return bytes(entry)


def gr_bb(unit):
    """The GR IV bleach approximation (GRN*001, base 02) applies as its knob values."""
    cam = boot(unit, bytes(40), dat=TEST_DAT)
    opened(cam)
    cam.goto(9); cam.press('DISP'); cam.goto(2); cam.press('DISP')      # MyRec -> GRN
    st = cam.state()
    assert st['cur'] == 1 and st['labels'][1] == ' GRN*001', st          # the only entry, not yet applied
    levels = [100, 2, 5, 5, 0, -5, 0, 0, 0, 0]
    card = cam.press('DISP')                                            # DISP on the entry applies it
    assert card['screen'] == 1 and card['labels'][0] == '<GRN*001', card
    assert card['slot'] == 2 and card['levels'] == levels and card['applied_user'], card
    rows, t = cam.unit_rows()
    entry = host_compute(unit, 2, levels)
    dat = H.DAT_BYTES[cam.dat_path]
    directory = int.from_bytes(dat[156:160], 'big') + 64 * H.UNITS[unit]
    mapping = dat[int.from_bytes(dat[directory + 12:directory + 16], 'big'):][:152]
    expect = [entry[int.from_bytes(mapping[38 + 12 * i:40 + 12 * i], 'big'):][:int.from_bytes(mapping[36 + 12 * i:38 + 12 * i], 'big')]
              for i in range(9)]
    assert rows == expect and t == int.from_bytes(entry[445:447], 'big'), 'GRN*001 rows differ from the host compute'
    assert cam.record() == bytes(40)                     # user entries store forty zeros
    return dict(labels=st['labels'], card=card['labels'][0])


CASES = {
    'cold-none': cold_none, 'offer': offer, 'offer-ok': offer_ok, 'offer-adj': exit_pure('adj'),
    'offer-half': exit_pure('half'), 'offer-move-ok': offer_move_ok, 'offer-disp': offer_disp,
    'offer-unconfirmed': offer_unconfirmed, 'my-replay': my_replay,
    **{f'my-{v}': my(v) for v in (0, 1, 2, 3)},
    **{'bad-' + k: bad(k) for k in ('crc', 'magic', 'unit', 'dataid', 'slot0', 'slot9', 'flags', 'version', 'level', 'garbage')},
    **{'inel-' + k: ineligible(k) for k in ('mode4', 'wb', 'source', 't0', 'extension', 'raw')},
    't-boot': t_boot, 'p101-partial': p101_partial, 'p101-five-mode4': p101_five_mode4, 'p101-normal': p101_normal,
    **{'tail-' + k: tail(k) for k in ('random', 'gxr1', 'badcrc', 'v2', 'nomagic')},
    'tail-own': tail_own, 'tail-race': tail_race, 'tail-user': tail_user,
    'record-busy': record_busy, 'record-busy-reopen': record_busy_reopen, 'held-lock': held_lock, 't-error': t_error,
    'race-length-op2': length_race('op2'), 'race-length-op5': length_race('op5'), 'race-version-op5': length_race('version'),
    'value-ends': value_ends, 'users': users, 'preview-fail-reopen': preview_fail_reopen, 'gr-bb': gr_bb,
}
ORDER = list(CASES)
SETS = {'set1': ORDER[0::2], 'set2': ORDER[1::2]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('cases', nargs='+')
    parser.add_argument('--unit', default='50mm', choices=('50mm', '28mm', 'mount'))
    args = parser.parse_args()
    H.LOCAL = Path(__file__).resolve().parent / 'local' / os.environ.get('REVIEW_JOB', 'host')
    H.setup()
    names = []
    for name in args.cases:
        names += ORDER if name == 'all' else SETS.get(name, [name])
    created = []
    original_camera = H.Camera
    def camera(*a, **kw):
        result = original_camera(*a, **kw); created.append(result); return result
    H.Camera = camera
    failed = 0
    for name in names:
        created.clear()
        start = time.time()
        try:
            detail, status = CASES[name](args.unit), 'PASS'
        except Exception as exc:
            detail = {'error': type(exc).__name__ + ': ' + str(exc)[:2000], 'trace': traceback.format_exc()[-3000:]}
            status, failed = 'FAIL', failed + 1
        seconds = round(time.time() - start, 1)
        H.save(f'checks/{args.unit}-{name}.json', dict(case=name, unit=args.unit, status=status, seconds=seconds,
                                                       dat_sha256=H.sha(created[-1].dat_path) if created else None,
                                                       dat_identities=[dict(path=str(p),sha256=H.sha(p)) for p in dict.fromkeys(c.dat_path for c in created)], detail=detail))
        print(status, args.unit, name, seconds, '' if status == 'PASS' else detail['error'][:300], flush=True)
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
