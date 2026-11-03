"""Parameter sweep of the three unit-related native getters that tools/native_harness/STUBS.md fixes
at 0 for every unit, with the gen 143 diag on the v3.8 body.

Usage: TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/unit28-stock-r1 \
       /usr/bin/python3 -I -B research/unit28_stock/sweep_stubs.py [28mm|50mm]

Getters: 0x202738ac "unit_category" (reads byte 0x205d9a7f), 0x20273828 "unit_mode" (reads S+0x3b5),
0x20270d78 "adj_capability". For every combination one Image ADJ open is driven through real native
code: the item-8 arm of the ADJ dispatcher 0x2029bedc..0x2029e0b4 *with its conditions* (the harness
parent() runs only the unconditional store), then 0x202b0a74(56), the ADJ parent builder 0x202856d0
and the Image constructor 0x20287080 with H01. Recorded per open: activity / state / part / view stack
/ rows at H01, the diag's body and DAT masks, the outcome (K published, X refused with overlay), and
whether the stock list showed our overlay. Values are a model sweep, not camera readings.
"""
import itertools
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scope
from scope import save, sha
import accept_diag143 as a

CATEGORY = (0, 1, 2, 3, 4)
MODE = (0, 3, 5, 9, 10, 19, 22, 27, 29, 44)
CAPABILITY = (0, 1, 2, 3)
GETTERS = ((0x202738ac, 'unit_category'), (0x20273828, 'unit_mode'), (0x20270d78, 'adj_capability'))


def main():
    unit = sys.argv[1] if len(sys.argv) > 1 else '28mm'
    scope.freeze_check()
    off = a.offsets()
    m, h, p, w, syms = a.base.boot(unit, ready=1)
    fr = m.fr

    def image_entered(b):
        block = h.u(a.R + 56)
        if block:
            p.image_base = h.u(block + 312)
        return False
    h.b.add_breakpoint(h.symbols['rv_invoke'], image_entered)
    h.b.add_breakpoint(a.GETTER, lambda b: False)

    def nb():
        return p.image_base + p.elf.symbols['n']

    def overlay_text():
        at = nb() + off['ov_rows']
        return [h.b.read(at + 9 * i, 9).split(b'\0', 1)[0].decode('ascii') for i in range(8)]

    def last_outcome():
        at = nb() + off['hist']
        return chr(h.u(at + off['open.outcome'], 1))

    def set_getters(values):
        for (addr, name), value in zip(GETTERS, values):
            h.b.breakpoints[addr] = []
            h.stub(addr, name, value=value)

    # one normal open first so the DAT is loaded under the harness defaults
    h.parent()
    assert fr.native(h, 0x20287080, (), steps=40000000).get('ok')
    assert fr.press(h, 0x23, steps=40000000).get('ok')
    rows = []
    summary = {}
    for values in itertools.product(CATEGORY, MODE, CAPABILITY):
        set_getters(values)
        entry = {'category': values[0], 'mode': values[1], 'capability': values[2]}
        h.put(0x205d9bf8, 0)
        try:
            h.run_slice(0x2029bedc, 0x2029e0b4)
            h.invoke(0x202b0a74, (56,))
            h.invoke(0x202856d0)
        except RuntimeError as exc:
            entry['dispatch_error'] = str(exc)[:160]
        entry['activity_after_dispatch'] = h.u(0x205d9bf8)
        g0 = h.b.visits.get(a.GETTER, 0)
        opens0 = h.u(nb() + off['opens'])
        result = fr.native(h, 0x20287080, (), steps=40000000)
        entry['open_ok'] = bool(result.get('ok'))
        if not result.get('ok'):
            entry['open_error'] = {k: result.get(k) for k in ('reason', 'pc', 'detail')}
        snap = a.base.snapshot(h)
        entry.update(rows=snap['rows'], part=snap['part'], count=snap['count'], tag=snap['tag'],
                     native_state=snap['native_state'], activity=snap['activity'],
                     getter=h.b.visits.get(a.GETTER, 0) - g0,
                     dat_ran=h.u(nb() + off['opens']) != opens0,
                     outcome=last_outcome(), body_mask=hex(h.u(nb() + off['body_mask'], 1)),
                     dat_mask=hex(h.u(nb() + off['dat_mask'], 1)), ov_on=h.u(nb() + off['ov_on'], 1),
                     names_word=hex(h.u(a.NAMES)))
        if entry['ov_on']:
            entry['overlay'] = overlay_text()
            assert h.u(a.NAMES) == nb() + off['ov_labels'], entry
        # what the user would see
        if entry['rows'] == 8 and entry['getter'] == 0:
            entry['seen'] = 'diag page'
        elif entry['ov_on'] and h.u(a.NAMES) == nb() + off['ov_labels']:
            entry['seen'] = 'stock list with readings'
        else:
            entry['seen'] = 'plain stock list'
        key = (entry['seen'], entry['outcome'], entry['body_mask'], entry['dat_mask'])
        summary.setdefault(json.dumps(key), []).append(list(values))
        rows.append(entry)
        print('SWEEP', json.dumps({k: entry[k] for k in ('category', 'mode', 'capability', 'activity_after_dispatch',
                                                          'seen', 'outcome', 'body_mask', 'dat_mask')}), flush=True)
        if entry['open_ok']:
            fr.press(h, 0x23, steps=40000000)
        # leave the next open with the stock label word, as a real close/open would see it
    report = {'unit': unit, 'dat': sha(a.DAT), 'combinations': len(rows),
              'by_result': {k: {'count': len(v), 'examples': v[:6]} for k, v in summary.items()},
              'rows': rows}
    save(HERE / ('local/sweep143-%s.json' % unit), report)
    print('SWEEP_DONE', unit, json.dumps({k: len(v) for k, v in summary.items()}), flush=True)


if __name__ == '__main__':
    main()
