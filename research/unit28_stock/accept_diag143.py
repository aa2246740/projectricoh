"""Host acceptance: diag v38 gen 143 (refusal overlay) on the v3.8 body and the real v3.8 resident.

Usage: TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/unit28-stock-r1 \
       /usr/bin/python3 -I -B research/unit28_stock/accept_diag143.py <50mm|28mm|mount> <mode>

Body, resident and diag engine run as M32R instructions in tools/native_harness (used, not
modified); device edges are models (see tools/native_harness/STUBS.md).

modes
  publish   gen 142 behaviour kept: page S published, DISP S G I J H S, OK closes, no overlay
  refuse    seven refusal shapes at H01 entry (activity 7, state 0x37, part 0, part 4, view array,
            top tag, rows 6); each shows its readings on the stock list (pages A, B, C rotate), the
            native drawer reads our labels, the next normal open puts the saved word back and
            publishes; G/I/J record the refusals as 'X'
  init      the unit snapshot changes right after the load, so the resident retires before
            menu_open: page I stays on the stock list ("NO MENU"); a second push shows it again
  notready  rpc_ready=0: pure stock list (stock label word), then ready: page S
Every mode: RPC W = 0, file writes = 0; engine writes outside its block are listed (gen 142 classes
plus the label word 0x2022f5a8). diag.c itself has no store to the row count 0x2022f5ac.
"""
import json
import struct
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scope
from scope import ROOT, load, save, sha
import accept_diag38 as base

base.DAT = DAT = ROOT / 'firmware/engine_diag_v38_g143/candidate/local/full-r1/GXRCE.DAT'
base.ENGINE = ENGINE = ROOT / 'firmware/engine_diag_v38_g143/candidate/local/full-r1/engine.elf'
PRODUCT = ROOT / 'firmware/engine_diag_v38_g143/candidate/containers/product'
GENERATION = 143
R = 0x20054700
GETTER = 0x202870a4
NAMES, ROWS = 0x2022f5a8, 0x2022f5ac
STOCK = 0x2022d610
UNIT_NAME = {'50mm': 'jlaunch', '28mm': 'qlaunch', 'mount': 'l08firm'}
FIELDS = ('rows', 'opens', 'hist', 'ov_rows', 'ov_labels', 'ov_refs', 'ov_glyphs', 'ov_on', 'ov_saved',
          'refused', 'body_mask', 'dat_mask', 'page')
OPEN_FIELDS, OPEN_BYTES = base.OPEN_FIELDS, base.OPEN_BYTES
ALLOWED = base.NATIVE_RANGES


def offsets():
    out = HERE / 'local/layout143'
    out.mkdir(parents=True, exist_ok=True)
    src = out / 'offsets.c'
    members = OPEN_FIELDS + OPEN_BYTES
    src.write_text('#include "' + str(PRODUCT / 'diag.c') + '"\n' + 'const uint32_t diag_offsets[]={' +
                   ','.join(['offsetof(Diagnostic,%s)' % k for k in FIELDS] +
                            ['offsetof(DiagOpen,%s)' % k for k in members] + ['sizeof(DiagOpen)']) + '};\n')
    gcc = ROOT / 'research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc'
    subprocess.run([str(gcc), '-std=c11', '-Os', '-ffreestanding', '-fpic', '-m32r', '-mmodel=medium',
                    '-msdata=none', '-G0', '-fno-builtin', '-c', str(src), '-o', str(out / 'offsets.o')],
                   check=True, cwd=ROOT)
    reader = load(ROOT / 'firmware/stage2l_switch/tools/build.py', 'diag143_offset_reader')
    elf = reader.Elf(out / 'offsets.o')
    s = elf.symbols['diag_offsets']
    count = len(FIELDS) + len(members) + 1
    blob = elf.content(elf.sections[s['section']])[s['value']:s['value'] + 4 * count]
    return dict(zip(FIELDS + tuple('open.' + k for k in members) + ('open_size',),
                    struct.unpack('>%dI' % count, blob)))


def main():
    unit, mode = sys.argv[1], sys.argv[2]
    assert sha(base.BODY) == base.BODY_SHA
    scope.freeze_check()
    layout = json.loads((ENGINE.parent / 'layout.json').read_text())
    off = offsets()
    m, h, p, w, syms = base.boot(unit, ready=0 if mode == 'notready' else 1)
    fr = m.fr
    h.b.add_breakpoint(GETTER, lambda b: False)
    report = {'unit': unit, 'mode': mode, 'dat': sha(DAT), 'generation': None, 'opens': []}
    engine_writes, label_reads = [], []
    state = {'base': None}

    def image_entered(b):
        block = h.u(R + 56)
        if block and p.image_base != h.u(block + 312):
            p.image_base = h.u(block + 312)
            lo, hi = p.image_base, p.image_base + layout['engine_bytes']
            state['base'] = p.image_base
            state['own'] = (block, block + h.u(R + 104))

            def traced(event):
                if event.pc is not None and lo <= event.pc < hi:
                    engine_writes.append((event.address, len(event.data)))
            h.b.add_write_trace(0, 2**32, traced)
        return False
    h.b.add_breakpoint(h.symbols['rv_invoke'], image_entered)

    def nb():
        return p.image_base + p.elf.symbols['n']

    def field(name, size=1):
        return h.u(nb() + off[name], size)

    def overlay_text():
        at = nb() + off['ov_rows']
        return [h.b.read(at + 9 * i, 9).split(b'\0', 1)[0].decode('ascii') for i in range(8)]

    def page_rows():
        at = nb() + off['rows']
        return [h.b.read(at + 9 * i, 9).split(b'\0', 1)[0].decode('ascii') for i in range(8)]

    def record(index):
        at = nb() + off['hist'] + index * off['open_size']
        d = {k: h.u(at + off['open.' + k]) for k in OPEN_FIELDS}
        d.update({k: h.u(at + off['open.' + k], 1) for k in OPEN_BYTES})
        d['outcome'] = chr(d['outcome'])
        return d

    def drawn_labels():
        """What the native list would draw: names word -> label -> ref -> glyph pointer."""
        names, rows = h.u(NAMES), h.u(ROWS, 1)
        out = []
        for i in range(rows):
            label = h.u(names + 4 * i)
            out.append(h.u(label))
        return names, rows, out

    def check_overlay(expect_first, rows_expected=7):
        names, rows, glyphs = drawn_labels()
        labels = nb() + off['ov_labels']
        assert names == labels and field('ov_on') == 1, (hex(names), hex(labels))
        assert rows == rows_expected, rows
        glyph0 = nb() + off['ov_glyphs']
        assert glyphs == [glyph0 + 70 * i for i in range(rows)], [hex(g) for g in glyphs]
        text = overlay_text()
        assert text[0].startswith(expect_first) and all(0 < len(x) <= 8 for x in text), text
        return text

    def open_once(label, before=None):
        g0 = h.b.visits.get(GETTER, 0)
        rpc0 = len(p.rpc.log)
        h.parent()
        if before:
            before()
        result = fr.native(h, 0x20287080, (), steps=40000000)
        assert result.get('ok'), (label, result)
        snap = base.snapshot(h)
        snap.update(label=label, getter=h.b.visits.get(GETTER, 0) - g0,
                    rpc_w=sum(1 for e in p.rpc.log[rpc0:] if e['cmd'] == 22),
                    root_state=h.u(R + 5, 1), names_word=hex(h.u(NAMES)))
        if p.image_base:
            snap.update(ov_on=field('ov_on'), refused=field('refused'), body_mask=hex(field('body_mask')),
                        dat_mask=hex(field('dat_mask')), overlay=overlay_text(), page=page_rows())
        report['opens'].append(snap)
        print('OPEN', json.dumps(snap), flush=True)
        return snap

    def native_draw():
        """Run the native list drawer 0x201fd360 on the stock state, as a redraw does, and
        count glyph-stage calls (stubs glyph_draw / raster_glyph_layout) that receive a
        pointer inside our overlay glyphs."""
        lo = nb() + off['ov_glyphs']
        hi = lo + 70 * 8
        hits = []
        added = []
        for addr in (0x201d7170, 0x201dbaf0):
            def cb(b, addr=addr):
                for r in range(1, 8):
                    v = b.get_reg('r%d' % r)
                    if lo <= v < hi:
                        hits.append((hex(addr), r, (v - lo) // 70))
                return False
            h.b.add_breakpoint(addr, cb)
            added.append((addr, cb))
        res = fr.native(h, 0x201fd360, (2, 0x2022f71c, 0), steps=40000000)
        for addr, cb in added:
            h.b.breakpoints[addr].remove(cb)
        return bool(res.get('ok')), sorted({x[2] for x in hits})

    def close():
        assert fr.press(h, 0x23, steps=40000000).get('ok')

    if mode == 'publish':
        o = open_once('open1')
        assert o['rows'] == 8 and o['getter'] == 0 and o['ov_on'] == 0 and o['names_word'] != hex(STOCK), o
        report['generation'] = h.u(h.u(R + 56) + 332)
        assert report['generation'] == GENERATION
        assert o['page'][0] == 'S0001 R9' and o['page'][1] == UNIT_NAME[unit] and o['page'][3] == 'T  0002', o['page']
        for i in range(5):
            assert fr.native(h, 0x202be220, steps=40000000).get('ok')
        assert page_rows()[0][0] == 'S'
        close()
        assert h.u(NAMES) == STOCK and h.u(ROWS, 1) == 7
        o2 = open_once('open2')
        assert o2['rows'] == 8 and o2['page'][0] == 'S0002 R9'
        close()

    elif mode == 'refuse':
        first = open_once('open1 normal')
        assert first['rows'] == 8 and first['ov_on'] == 0
        report['generation'] = h.u(h.u(R + 56) + 332)
        close()
        assert h.u(NAMES) == STOCK
        locations = {'activity': (0x205d9bf8, 4), 'native': (0x205d9c00, 4), 'part': (0x205a280f, 1),
                     'array': (0x205a27d8, 4), 'tag': (0x205a279c, 1), 'rows': (ROWS, 1)}
        shapes = [('activity7', {'activity': 7}, 0x01, 0), ('state37', {'native': 0x37}, 0x02, 0),
                  ('part0', {'part': 0}, 0x04, 0), ('part4', {'part': 4}, 0x04, 0),
                  ('array', {'array': 0x205a27a0}, 0x08, 0), ('toptag', {'tag': 0x22}, 0x20, 0),
                  ('rows6', {'rows': 6}, 0, 0x02)]
        expect_page = 'ABC'
        saved = {}
        pending = {'v': None}
        observe = syms['rv_hook_observe']['value'] if isinstance(syms['rv_hook_observe'], dict) else syms['rv_hook_observe']

        def at_observe(b):
            if b.get_reg('r1') == 1 and pending['v'] is not None:
                for at, width, value in pending['v']:
                    saved.setdefault(at, (width, h.u(at, width)))
                    b.write(at, int(value).to_bytes(width, 'big'))
                pending['v'] = None
            return False
        h.b.add_breakpoint(observe, at_observe)
        results = []
        for index, (name, change, body_bits, dat_bits) in enumerate(shapes):
            pending['v'] = [(locations[k][0], locations[k][1], v) for k, v in change.items()]
            o = open_once('refuse ' + name)
            text = check_overlay(expect_page[index % 3] + '%X' % (index + 1), change.get('rows', 7))
            assert o['getter'] >= 1 and o['rpc_w'] == 0, o
            assert int(o['body_mask'], 16) & body_bits == body_bits and int(o['dat_mask'], 16) & 15 & dat_bits == dat_bits, o
            if index % 3 == 0:
                assert text[0][3:5] == '%02X' % int(o['body_mask'], 16), text
            ok, reads = native_draw()
            assert ok and reads == list(range(change.get('rows', 7))), (ok, reads)
            results.append(dict(shape=name, overlay=text, body_mask=o['body_mask'], dat_mask=o['dat_mask'],
                                native_draw_ok=ok, label_reads=reads))
            print('REFUSE', name, ' | '.join(text), 'draw', ok, reads, flush=True)
            for at, (width, value) in list(saved.items()):
                h.b.write(at, value.to_bytes(width, 'big'))
            saved.clear()
            assert record(0)['outcome'] == 'X', record(0)
        report['refusals'] = results
        # a later normal open puts the saved word back before anything else, then publishes
        back = open_once('open normal after refusals')
        assert back['rows'] == 8 and back['ov_on'] == 0 and back['getter'] == 0, back
        assert fr.native(h, 0x202be220, steps=40000000).get('ok')
        g = page_rows()
        assert g[0].startswith('G') and g[0][6] == 'X', g
        close()
        assert h.u(NAMES) == STOCK and h.u(ROWS, 1) == 7

    elif mode == 'init':
        armed = {'on': False, 'done': False}
        check = syms['rv_check']['value'] if isinstance(syms['rv_check'], dict) else syms['rv_check']

        def at_check(b):
            if armed['on'] and not armed['done'] and h.u(R + 5, 1) == 3:
                h.b.write(0x2040f84a, bytes.fromhex('0001'))
                armed['done'] = True
            return False
        h.b.add_breakpoint(check, at_check)
        armed['on'] = True
        o = open_once('open1 retired after load')
        assert armed['done'] and o['root_state'] == 6 and o['rows'] == 7 and o['getter'] == 1, o
        text = check_overlay('I2')
        assert text[1].startswith('R11') and text[2] == UNIT_NAME[unit] and text[3] == '01510000' and text[4] == 'NO MENU', text
        report['init_overlay'] = text
        print('INIT', ' | '.join(text), flush=True)
        ok, reads = native_draw()
        report['native_draw'] = [ok, reads]
        o2 = open_once('open2 disabled')
        assert o2['root_state'] == 6 and o2['rows'] == 7 and h.u(NAMES) == nb() + off['ov_labels'], o2
        report['generation'] = None

    elif mode == 'notready':
        o = open_once('open1 not ready')
        assert o['root_state'] == 0 and o['rows'] == 7 and o['names_word'] == hex(STOCK) and o['getter'] == 1, o
        assert fr.native(h, 0x200935b4, (1,)).get('ok')
        o2 = open_once('open2 ready')
        assert o2['rows'] == 8 and o2['page'][0] == 'S0001 R9' and o2['ov_on'] == 0, o2
        report['generation'] = h.u(h.u(R + 56) + 332)

    else:
        raise SystemExit('mode?')

    report['writes'] = m.no_writes(p)
    report['rpc_w'] = sum(1 for e in p.rpc.log if e['cmd'] == 22)
    assert report['rpc_w'] == 0 and not p.rpc.overlay
    own = state.get('own', (0, 0))
    report['own_block'] = [hex(own[0]), hex(own[1])]
    outside = {}
    for address, width in engine_writes:
        if own[0] <= address < own[1] or R <= address < R + 0x400:
            continue
        if any(lo <= address and address + width <= hi for lo, hi in ALLOWED):
            continue
        outside[hex(address)] = outside.get(hex(address), 0) + 1
    spans = []
    for address in sorted(int(x, 16) for x in outside):
        if spans and address <= spans[-1][1] + 8:
            spans[-1][1] = address + 1
        else:
            spans.append([address, address + 1])
    report['engine_writes_outside_allowlist'] = [[hex(a), hex(b)] for a, b in spans]
    report['label_word_writes'] = sum(1 for a, w_ in engine_writes if a <= NAMES < a + w_)
    save(HERE / ('local/accept143-%s-%s.json' % (unit, mode)), report)
    print('ENGINE_WRITES_OUTSIDE', json.dumps(report['engine_writes_outside_allowlist']), 'label_word_writes', report['label_word_writes'], flush=True)
    print('ACCEPT_DONE', unit, mode, flush=True)


if __name__ == '__main__':
    main()
