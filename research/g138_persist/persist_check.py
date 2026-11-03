"""New gen 138 checks: remembered recipe (A) and user-entry titles (B).

Host model only (python M32R backend, device leaves are models). Each case
boots a fresh model. Results: research/g138_persist/local/checks/<case>.json.
  /usr/bin/python3 -I -B research/g138_persist/persist_check.py <case|all|half1|half2> [--unit 50mm]
"""
from pathlib import Path
import argparse
import json
import sys
import time
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g138_host as H

CONT1 = [100, 1, 0, 0, 0, 0, 0, 0, 0, 0]
ZERO = [100, 0, 0, 0, 0, 0, 0, 0, 0, 0]
STOCK_L1 = [' 1 GRPos', ' 2 GRNeg', ' 3 HC BW', '>4 Std', ' 5 F-CC', ' 6 F-CN', ' 7 L-Chr', ' 8 L-Viv']
UNMARKED_L1 = [' 1 GRPos', ' 2 GRNeg', ' 3 HC BW', ' 4 Std', ' 5 F-CC', ' 6 F-CN', ' 7 L-Chr', ' 8 L-Viv']
USERS = H.LOCAL / 'users-fixture/GXRCE.DAT'


def boot(unit, record=None, normal=True, dat=None, lock=-1):
    cam = H.Camera(unit, normal=normal, dat=dat)
    if record is not None:
        cam.put_s(0xfd4, record)
    cam.set_lock(lock)
    return cam


def valid(cam, slot=5, levels=CONT1):
    return H.record_bytes(H.DAT_BYTES[cam.dat_path], slot, H.UNITS[cam.unit], levels)


def opened(cam):
    before = dict(S=cam.s_bytes(0, 4096), W=cam.writes(), lock=cam.lock())
    cam.open_menu()
    st = cam.check_frame()
    after = dict(S=cam.s_bytes(0, 4096), W=cam.writes(), lock=cam.lock())
    changed = [hex(i) for i in range(4096) if before['S'][i] != after['S'][i]]
    return st, dict(S_changed=changed, W=after['W'] - before['W'], lock_after=after['lock'])


# ---- A: normal boot -------------------------------------------------------
def cold_none(unit):
    cam = boot(unit, bytes(40))
    st, d = opened(cam)
    assert st['labels'] == STOCK_L1 and st['slot'] == 4 and st['cur'] == 3 and st['levels'] == ZERO, st
    assert d['W'] == 0 and d['S_changed'] == [] and cam.record() == bytes(40) and d['lock_after'] == (-1, 55), d
    return dict(state=st, delta=d)


def restore(unit):
    cam = boot(unit)
    record = valid(cam)
    cam.put_s(0xfd4, record)
    st, d = opened(cam)
    assert st['slot'] == 5 and st['cur'] == 4 and st['levels'] == CONT1 and st['labels'][4] == '>5*F-CC', st
    assert [x for i, x in enumerate(st['labels']) if i != 4] == [x for i, x in enumerate(UNMARKED_L1) if i != 4], st
    assert d['W'] > 0 and d['S_changed'] == [] and cam.record() == record and d['lock_after'] == (-1, 55), d
    rows, t = cam.unit_rows()
    return dict(state=st, delta=d, rows=[r.hex() for r in rows], T=t)


def select_reference(unit):
    """Normal path: no record, select 5 and Cont +1 with the keys. The stored
    record must equal the independent encoder, and rows/T must equal restore."""
    cam = boot(unit, bytes(40))
    opened(cam)
    cam.press('DOWN')
    assert cam.ui('slot') == 5 and cam.record() == valid(cam, 5, ZERO), cam.record().hex()
    cam.press('DISP'); assert cam.ui('screen') == 1, cam.state()
    cam.press('DISP'); assert cam.ui('screen') == 2, cam.state()
    cam.goto(1)
    cam.press('DISP'); assert cam.ui('screen') == 3, cam.state()
    st = cam.press('UP')
    assert st['levels'] == CONT1, st
    assert cam.record() == valid(cam, 5, CONT1), cam.record().hex()
    rows, t = cam.unit_rows()
    cam.press('OK')
    assert cam.record() == valid(cam, 5, CONT1)
    return dict(record=cam.record().hex(), rows=[r.hex() for r in rows], T=t, lock=cam.lock())


def restore_matches_select(unit):
    a, b = restore(unit), select_reference(unit)
    assert a['rows'] == b['rows'] and a['T'] == b['T'], 'restore rows/T differ from the keyed selection'
    return dict(restore=a, select=b)


def restore_once(unit):
    cam = boot(unit)
    cam.put_s(0xfd4, valid(cam))
    opened(cam)
    cam.press('OK')
    other = valid(cam, 6, ZERO)
    cam.put_s(0xfd4, other)
    st, d = opened(cam)
    assert st['slot'] == 5 and st['levels'] == CONT1 and st['labels'][4] == '>5*F-CC', st
    assert d['W'] == 0 and cam.record() == other, d
    return dict(state=st, delta=d)


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
            import zlib
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
        assert st['labels'] == STOCK_L1 and st['slot'] == 4 and st['levels'] == ZERO, st
        assert d['W'] == 0 and d['S_changed'] == [] and cam.record() == record, d
        return dict(state=st, delta=d, record=record.hex())
    return case


def ineligible(kind):
    def case(unit):
        cam = boot(unit)
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
        elif kind == 'row':
            dat = H.DAT_BYTES[cam.dat_path]
            directory = int.from_bytes(dat[156:160], 'big') + 64 * H.UNITS[unit]
            mapping = dat[int.from_bytes(dat[directory + 12:directory + 16], 'big'):][:152]
            address = int.from_bytes(mapping[32 + 12 * 2:36 + 12 * 2], 'big') & ~1
            cam.p.rpc.overlay[address] = cam.p.rpc.half(address) ^ 0x0101
        elif kind == 'extension':
            cam.put_s(0xe, b'\x01\x01')
            marked = STOCK_L1
        elif kind == 'raw':
            cam = boot(unit, normal=False)
            cam.put_s(0xfd4, valid(cam))
        record = cam.record()
        st, d = opened(cam)
        assert st['labels'] == marked and st['slot'] == 4 and st['levels'] == ZERO, st
        assert d['W'] == 0 and d['S_changed'] == [] and cam.record() == record, d
        return dict(state=st, delta=d)
    return case


# ---- A: the stock parameter lock ------------------------------------------
def op2(count, ident=55):
    def case(unit):
        cam = boot(unit, bytes(40))
        cam.put_s(0x6dd, b'\x0a')              # needs an S write on the next choice
        opened(cam)
        cam.set_lock(count, ident)
        before = cam.s_bytes(0, 4096)
        result = dict(lock_before=cam.lock())
        try:
            cam.press('DOWN')
        except AssertionError as exc:
            result['press'] = str(exc)[:300]
        after = cam.s_bytes(0, 4096)
        changed = [hex(i) for i in range(4096) if before[i] != after[i]]
        result.update(S_changed=changed, lock_after=cam.lock(), state=cam.state())
        if count == -1 and ident == 55:
            assert changed and '0x6dd' in changed and cam.s_bytes(0x6dd, 1) == b'\x09', result
            assert cam.lock() == (-1, 55) and cam.record() == valid(cam, 5, ZERO), result
        else:
            assert changed == [] and cam.lock() == (count, ident), result
        return result
    return case


def record_busy(unit):
    cam = boot(unit)
    old = valid(cam, 5, ZERO)
    cam.put_s(0xfd4, old)
    st, _ = opened(cam)
    assert st['slot'] == 5 and st['labels'][4] == '>5 F-CC', st
    cam.set_lock(0)
    st = cam.press('DOWN')
    assert st['slot'] == 6 and cam.record() == old and cam.lock() == (0, 55), st
    assert st['labels'][5] == '!6 F-CN', st             # chosen, not remembered
    S_before = cam.s_bytes(0, 4096)
    cam.set_lock(1)                                     # a queued waiter is busy too
    cam.press('OK')
    assert cam.record() == old and cam.s_bytes(0, 4096) == S_before
    cam.set_lock(-1)
    st, _ = opened(cam)                                 # next boundary retries
    after = cam.record()
    assert after == valid(cam, 6, ZERO) and cam.lock() == (-1, 55), (after.hex(), st)
    # Known: the retry runs after this frame's labels were drawn, so the
    # first frame may still show '!'; the next redraw shows '>'.
    assert st['labels'][5] in ('!6 F-CN', '>6 F-CN'), st
    st2, d2 = opened(cam)
    assert st2['labels'][5] == '>6 F-CN' and d2['W'] == 0 and d2['S_changed'] == [], (st2, d2)
    return dict(first_frame=st['labels'], next_frame=st2['labels'], kept=old.hex(), stored=after.hex())


# ---- A + B: user entries --------------------------------------------------
def users(unit):
    cam = boot(unit, dat=USERS)
    cam.put_s(0xfd4, valid(cam, 5, ZERO))
    st, _ = opened(cam)
    assert st['slot'] == 5 and st['labels'][4] == '>5 F-CC', st
    cam.goto(9)
    cam.press('DISP'); assert cam.ui('screen') == 4, cam.state()
    cam.goto(5)
    cam.press('DISP'); assert cam.ui('screen') == 5 and cam.ui('cur') == 1, cam.state()
    cam.goto(25)
    st = cam.state()
    assert st['applied_user'] == 8 and st['labels'][st['physical']] == '>FCC-001', st
    assert cam.record() == bytes(40), cam.record().hex()
    card = cam.press('DISP')
    assert card['screen'] == 1 and card['labels'][0] == '<FCC-001', card
    items = cam.press('DISP')
    assert items['screen'] == 2 and items['labels'][0] == '<FCC-001', items
    cam.goto(1)
    value = cam.press('DISP'); assert value['screen'] == 3, value
    changed = cam.press('UP')
    assert changed['levels'] == CONT1, changed
    back = cam.press('DISP')
    trace = dict(card=card['labels'], items=items['labels'], value=value['labels'], back=back['labels'],
                 back_screen=back['screen'])
    if back['screen'] in (1, 2):
        assert back['labels'][0] == '<FCC*001', back
    assert cam.record() == bytes(40), cam.record().hex()
    cam.press('OK')
    # Reboot with the stored (forgotten) record: canonical stock 04.
    again = boot(unit, cam.record(), dat=USERS)
    st2, d2 = opened(again)
    assert st2['labels'] == STOCK_L1 and d2['W'] == 0, st2
    return dict(trace=trace, reboot=st2)


# ---- C: no end marks; the value page stops at the real range --------------
def value_ends(unit):
    cam = boot(unit, bytes(40))
    opened(cam)
    cam.goto(0)                                         # 1 GRPos
    card = cam.press('DISP')
    assert card['screen'] == 1 and not any('!' in x for x in card['labels']), card
    items = cam.press('DISP')
    assert items['screen'] == 2 and not any('!' in x for x in items['labels']), items
    row = next(i for i in range(items['count']) if cam.goto(i)['labels'][cam.ui('physical')].startswith('Satu'))
    value = cam.press('DISP')
    assert value['screen'] == 3, value
    seen = []
    for key, end in (('UP', 6), ('DOWN', -9)):
        for _ in range(20):
            before = cam.state()
            after = cam.press(key)
            seen.append(after['labels'][after['physical']])
            if after['levels'][5] == before['levels'][5]:
                break
        else:
            raise AssertionError((key, 'no stop', after))
        assert after['levels'][5] == end and after['cur'] == before['cur'], (key, after)
        label = after['labels'][after['physical']]
        assert label == 'Satu  %+d' % end, (key, label)
        assert not any('!' in x for x in after['labels']), after
    return dict(items_row=row, card=card['labels'], items=items['labels'], value_labels=seen)


CASES = {
    'cold-none': cold_none, 'restore': restore, 'restore-matches-select': restore_matches_select,
    'restore-once': restore_once,
    **{'bad-' + k: bad(k) for k in ('crc', 'magic', 'unit', 'dataid', 'slot0', 'slot9', 'flags', 'version', 'level', 'garbage')},
    **{'inel-' + k: ineligible(k) for k in ('mode4', 'wb', 'source', 't0', 'row', 'extension', 'raw')},
    'op2-idle': op2(-1), 'op2-held': op2(0), 'op2-waiter': op2(1), 'op2-id': op2(-1, 54),
    'record-busy': record_busy, 'users': users, 'value-ends': value_ends,
}
ORDER = list(CASES)
HALVES = {'half1': ORDER[0::2], 'half2': ORDER[1::2]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('cases', nargs='+')
    parser.add_argument('--unit', default='50mm', choices=('50mm', '28mm', 'mount'))
    args = parser.parse_args()
    H.setup()
    names = []
    for name in args.cases:
        names += ORDER if name == 'all' else HALVES.get(name, [name])
    failed = 0
    for name in names:
        start = time.time()
        try:
            detail = CASES[name](args.unit)
            status = 'PASS'
        except Exception as exc:
            detail = {'error': type(exc).__name__ + ': ' + str(exc)[:2000], 'trace': traceback.format_exc()[-3000:]}
            status = 'FAIL'
            failed += 1
        seconds = round(time.time() - start, 1)
        H.save(f'checks/{args.unit}-{name}.json', dict(case=name, unit=args.unit, status=status, seconds=seconds,
                                                       dat_sha256=H.sha(H.DAT), detail=detail))
        print(status, args.unit, name, seconds, '' if status == 'PASS' else detail['error'][:300], flush=True)
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
