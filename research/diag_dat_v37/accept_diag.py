"""Host acceptance: diag v37 DAT on the v3.7 body and the real v3.7 resident.

Usage: /usr/bin/python3 -I -B accept_diag.py <50mm|28mm|mount>

Per unit: load state 3; two normal opens with the 9 pages cycled; the field shape
(Image view on the part-2 stack, part byte 1, then the constructor); part 0 and
part 4 forced at ig_menu entry (nothing published, record visible on the next
open); no file writes; engine-attributed memory writes classified.
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
scope.enable_fence()

BODY = ROOT / 'firmware/package_v37_diag/SD_ROOT/ilaunch3'
DAT = ROOT / 'firmware/package_v37_diag/SD_ROOT/GXRCE.DAT'
RESIDENT = ROOT / 'firmware/resident_v37/local/resident/build/resident.elf'
ENGINE = ROOT / 'firmware/engine_diag_v37/candidate/local/full-r13/engine.elf'
PRODUCT = ROOT / 'firmware/engine_diag_v37/candidate/containers/product'
ORDER = 'GIJABCDFHG'
SHARED_BODY = 'da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7'
ENGINE_TREE = ROOT / 'firmware/engine_v48_own'
# Native words the diagnostic and its services may touch (diag_dat_v1 allowlist
# plus the resident root and the engine's own allocation).
NATIVE_RANGES = ((0x2022f5a8, 0x2022f5b0), (0x2022f71c, 0x2022f73c), (0x2037f3bc, 0x2037f3c0),
                 (0x205a279c, 0x205a27e0), (0x205a280c, 0x205a2814), (0x205a293c, 0x205a2948),
                 (0x205d9bf8, 0x205d9c04), (0x205d4f64, 0x205d4f68))
OPEN_FIELDS = ('seq', 'rc', 'names', 'restore6', 'restore0', 'top_state', 'activity', 'mode')
OPEN_BYTES = ('outcome', 'rows', 'kind', 'count', 'top_tag', 'part', 'flags', 'state', 'valid')


def probe_offsets():
    out = HERE / 'local/layout'
    out.mkdir(parents=True, exist_ok=True)
    names = ('rows', 'page', 'opens', 'cur', 'hist', 'shown')
    members = OPEN_FIELDS + OPEN_BYTES
    src = out / 'probe.c'
    src.write_text('#include "' + str(PRODUCT / 'diag.c') + '"\n' +
                   'const uint32_t diag_offsets[]={' +
                   ','.join(['offsetof(Diagnostic,%s)' % n for n in names] +
                            ['offsetof(DiagOpen,%s)' % n for n in members] + ['sizeof(DiagOpen)']) + '};\n')
    gcc = ROOT / 'research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc'
    subprocess.run([str(gcc), '-std=c11', '-Os', '-ffreestanding', '-fpic', '-m32r', '-mmodel=medium',
                    '-msdata=none', '-G0', '-fno-builtin', '-c', str(src), '-o', str(out / 'probe.o')],
                   check=True, cwd=ROOT)
    reader = load(ROOT / 'firmware/stage2l_switch/tools/build.py', 'diag37_offset_reader')
    elf = reader.Elf(out / 'probe.o')
    s = elf.symbols['diag_offsets']
    count = len(names) + len(members) + 1
    blob = elf.content(elf.sections[s['section']])[s['value']:s['value'] + 4 * count]
    values = struct.unpack('>%dI' % count, blob)
    result = dict(zip(names + tuple('open.' + k for k in members) + ('open_size',), values))
    return result


def snapshot(h):
    count = h.u(0x205a27d4, 1)
    array = h.u(0x205a27d8)
    top = array + 8 * (count - 1) if array == 0x205a279c and 1 <= count <= 2 else None
    return {'part': h.u(0x205a280f, 1), 'count': count,
            'tag': h.u(top, 1) if top else None,
            'state': hex(h.u(top + 4)) if top else None,
            'names': hex(h.u(0x2022f5a8)), 'rows': h.u(0x2022f5ac, 1),
            'kind': h.u(0x2022f71c, 1), 'activity': h.u(0x205d9bf8),
            'native_state': hex(h.u(0x205d9c00)), 'cursor': h.u(0x2022f726, 1),
            'ui_restore0': hex(h.u(0x20054700 + 156))}


def boot(unit):
    sys.path.insert(0, str(ENGINE_TREE))
    m = load(ENGINE_TREE / 'integration_native.py', 'diag37_integration')
    v, fr, pe = m.v, m.fr, m.pe
    v.BODY_SHA = sha(BODY)
    v.RESIDENT_ELF = RESIDENT
    v.ENGINE_ELF = ENGINE
    defaults = list(v.V35Harness.__init__.__defaults__)
    defaults[0] = BODY
    v.V35Harness.__init__.__defaults__ = tuple(defaults)
    m.DAT = DAT
    pe.STAGED, pe.STAGED_SHA, pe.ENGINE_ELF = DAT, sha(DAT), ENGINE
    v.python_backend.CACHE = HERE / 'local/decode'
    pe.FileEdge, fr.Product = m.Files, m.Product
    pe.UNITS['mount'] = (ROOT / 'firmware/package_v36_g120b/SD_ROOT/l08firm3',
                         '0a4dff6d3be9b9a9b56dfcbd98a2df59efcb31f7d4eaca6b0c3fbdb1641fde44', 2)
    v.harness_mod.Harness = v.V35Harness
    syms = v.Elf(RESIDENT).symbols
    fr.OBSERVE = syms['rv_hook_observe']
    fr.LAND = {syms['rv_skip_06']: 'h06_skip', syms['rv_close_07']: 'h07_close',
               syms['rv_skip_08']: 'h08_skip', 0x202871dc: 'native_setter',
               0x202bb96c: 'native_h08', 0x20268768: 'native_setter_store',
               0x20268774: 'native_row_store'}
    h, p, w = m.boot(unit)
    original = p.symbol_pc

    def symbol(name):
        actual = next((n for n in (name, name + '.constprop.0', name + '.lto_priv.0')
                       if n in p.elf.symbols), name)
        return original(actual)
    p.symbol_pc = symbol
    h.stub(0x0500c6ec, 'kernel_context', value=0)

    def task_id(b):
        b.write(b.core.r[4], (6).to_bytes(2, 'big'))
        return 0
    h.stub(0x0500c574, 'kernel_task_id', task_id)
    return m, h, p, w, syms


def main():
    unit = sys.argv[1] if len(sys.argv) > 1 else '50mm'
    assert sha(BODY) == 'd00607405a5bd33290f99e9eda20df31a46386b6e0891cd5e62b15a9e3376283'
    layout = json.loads((ENGINE.parent / 'layout.json').read_text())
    off = probe_offsets()
    m, h, p, w, syms = boot(unit)
    fr, pe = m.fr, m.pe
    jl = 0x202870a4
    h.b.add_breakpoint(jl, lambda b: False)
    report = {'unit': unit, 'body': sha(BODY), 'dat': sha(DAT), 'dat_bytes': DAT.stat().st_size}
    entry = {'force': None, 'seen': []}
    engine_writes = []
    heap_pcs = {}
    services = []

    def image_entered(b):
        block = h.u(pe.ROOT_ADDR + 56)
        if block:
            if p.image_base != h.u(block + 312):
                p.image_base = h.u(block + 312)
                hook()
        return False
    attached = []

    def hook():
        if attached:
            return
        attached.append(True)
        base = p.image_base
        lo, hi = base, base + layout['engine_bytes']

        def at_menu(b):
            if entry['force'] is not None:
                b.write(0x205a280f, bytes([entry['force']]))
            entry['seen'].append(h.u(0x205a280f, 1))
            return False
        h.b.add_breakpoint(base + layout['entries']['ig_menu'], at_menu)

        def traced(event):
            if event.pc is not None and lo <= event.pc < hi:
                engine_writes.append((event.address, len(event.data)))
                if 0x20704000 <= event.address < 0x20704a84:
                    heap_pcs[event.pc - base] = heap_pcs.get(event.pc - base, 0) + 1
        h.b.add_write_trace(0, 2**32, traced)
    h.b.add_breakpoint(h.symbols['rv_invoke'], image_entered)

    def ntext():
        return p.image_base + p.elf.symbols['n']

    def rows():
        at = ntext() + off['rows']
        return [h.b.read(at + 9 * i, 9).split(b'\0', 1)[0].decode('ascii') for i in range(8)]

    def record(table, index):
        at = ntext() + off[table] + index * off['open_size']
        d = {k: h.u(at + off['open.' + k]) for k in OPEN_FIELDS}
        d.update({k: h.u(at + off['open.' + k], 1) for k in OPEN_BYTES})
        d['outcome'] = chr(d['outcome'])
        return d

    def opened():
        return h.u(ntext() + off['opens'])

    def run(stage, address, arguments=()):
        before = h.b.visits.get(jl, 0)
        result = fr.native(h, address, arguments, steps=30000000)
        assert result.get('ok'), (stage, result)
        snap = snapshot(h)
        snap['jl_delta'] = h.b.visits.get(jl, 0) - before
        report[stage] = snap
        print('ACCEPT', stage, json.dumps(snap), flush=True)
        return snap

    def cycle(label):
        """Pages G I J A B C D F H G through the DISP panel; returns the texts."""
        seen = []
        for index, expected in enumerate(ORDER):
            if index:
                result = fr.native(h, 0x202be220, steps=30000000)
                assert result.get('ok'), (label, index, result)
            r = rows()
            assert len(r) == 8 and all(0 < len(x) <= 8 for x in r), (label, index, r)
            assert r[0][0] == expected, (label, index, r)
            # G/I/J show a past attempt (its own sequence number); the rest show this open.
            assert r[0][5] == ' ' and (expected in 'GIJ' or r[0][1:5] == '%04X' % opened()), (label, index, r)
            seen.append(r)
            if expected in 'GIJ':
                print('PAGE', label, expected, ' | '.join(r), flush=True)
        return seen

    def check_history(page, expect):
        r = rows()
        assert r[0][0] == page, r
        for key, value in expect.items():
            got = {'seq': r[0][1:5], 'outcome': r[0][6], 'rc': r[1][:4], 'flags': r[1][4:6],
                   'state': r[1][6:8], 'names': r[2], 'list': r[3], 'restore6': r[4],
                   'restore0': r[5], 'activity': r[6][:4], 'mode': r[6][4:6], 'part': r[6][6:8],
                   'top_state': r[7]}[key]
            assert got == value, (page, key, got, value, r)
        return r

    # ---- opening 1: normal open --------------------------------------------------
    h.parent()
    o1 = run('open1', 0x20287080)
    root = fr.root_fields(h)
    report['root'] = root
    report['rv_load'] = h.b.visits.get(h.symbols['rv_load'], 0)
    report['fault'] = h.u(pe.ROOT_ADDR + 92)
    print('ROOT', json.dumps(root), 'rv_load', report['rv_load'], 'fault', report['fault'], flush=True)
    assert root['state'] == 3 and report['fault'] == 0 and report['rv_load'] == 1, root
    assert o1['rows'] == 8 and o1['jl_delta'] == 0 and o1['part'] == 2, o1
    block = h.u(pe.ROOT_ADDR + 56)
    report['generation'] = h.u(block + 332)
    assert report['generation'] == 133, report['generation']
    assert h.u(pe.ROOT_ADDR + 5, 1) == 3
    report['offsets'] = off
    pages = cycle('open1')
    assert pages[0][1] == 'NONE' and pages[1][1] == 'NONE', pages[:2]
    assert entry['seen'] == [2], entry
    report['open1_pages'] = pages
    assert fr.press(h, 0x23, steps=30000000).get('ok')

    # ---- opening 2: record of opening 1 is shown -------------------------------------
    h.parent()
    run('open2', 0x20287080)
    assert snapshot(h)['rows'] == 8 and entry['seen'] == [2, 2], entry
    g = check_history('G', {'seq': '0001', 'outcome': 'K', 'rc': '0000', 'activity': '0008',
                            'mode': '38', 'part': '02'})
    report['open2_G'] = g
    print('G', ' | '.join(g), flush=True)
    pages = cycle('open2')
    report['open2_pages'] = pages
    assert fr.press(h, 0x23, steps=30000000).get('ok')

    # ---- opening 3: field shape, part byte 1 ------------------------------------------
    h.parent()
    run('open3 normal', 0x20287080)       # opening 3 (normal) so shape 4 is opening 4
    aborted = p.call(h.symbols['rv_ui_abort'], (pe.ROOT_ADDR,), steps=100000)
    assert aborted.get('ok') and snapshot(h)['rows'] == 7, aborted
    run('enable part1', 0x201c06f4, (1, 0, 0))
    shown = run('show part1', 0x201c092c, (1, 0, 0))
    assert shown['part'] == 1 and shown['rows'] == 7 and shown['tag'] == 33, shown
    before_seen = len(entry['seen'])
    field = run('open4 field shape', 0x20287080)
    assert entry['seen'][before_seen:] == [1], entry
    assert field['rows'] == 8 and field['jl_delta'] == 0 and field['part'] == 2, field
    assert 1 <= field['cursor'] <= 8
    pages = cycle('open4')
    report['open4_pages'] = pages

    # ---- openings 5/6: part 0 and part 4 forced at ig_menu entry ----------------------
    sequence = [('open5 part0', 0, 5), ('open6 part4', 4, 6)]
    for stage, part, number in sequence:
        aborted = p.call(h.symbols['rv_ui_abort'], (pe.ROOT_ADDR,), steps=100000)
        assert aborted.get('ok') and snapshot(h)['rows'] == 7, aborted
        entry['force'] = part
        bad = run(stage, 0x20287080)
        entry['force'] = None
        assert opened() == number and entry['seen'][-1] == part, (opened(), entry)
        assert bad['rows'] == 7 and bad['jl_delta'] >= 1, bad          # nothing published, stock getter ran
        assert bad['names'] == '0x2022d610', bad
        last = record('hist', 0)
        report[stage + ' record'] = last
        assert last['outcome'] == '6' and last['part'] == part and last['rc'] & 0xffff == 0xfffb, last
        assert last['seq'] == number and last['activity'] == 8 and last['mode'] == 0x38, last
    report['writes_during_failures'] = None
    # next open shows the failure records: G = opening 6 (part 4), I = opening 5 (part 0),
    # J = opening 4 (part 1, published)
    aborted = p.call(h.symbols['rv_ui_abort'], (pe.ROOT_ADDR,), steps=100000)
    assert aborted.get('ok')
    run('open7 normal', 0x20287080)
    assert snapshot(h)['rows'] == 8 and opened() == 7
    r = check_history('G', {'seq': '0006', 'outcome': '6', 'rc': 'FFFB', 'activity': '0008',
                            'mode': '38', 'part': '04'})
    print('G', ' | '.join(r), flush=True)
    report['open7_G'] = r
    res = fr.native(h, 0x202be220, steps=30000000)
    assert res.get('ok')
    r = check_history('I', {'seq': '0005', 'outcome': '6', 'rc': 'FFFB', 'activity': '0008',
                            'mode': '38', 'part': '00'})
    print('I', ' | '.join(r), flush=True)
    report['open7_I'] = r
    res = fr.native(h, 0x202be220, steps=30000000)
    assert res.get('ok')
    r = check_history('J', {'seq': '0004', 'outcome': 'K', 'rc': '0000', 'activity': '0008',
                            'mode': '38', 'part': '01'})
    print('J', ' | '.join(r), flush=True)
    report['open7_J'] = r

    # ---- writes ---------------------------------------------------------------------
    h.select_item_8()
    panel = run('disp', 0x202be220)
    report['panel_rows'] = panel['rows']
    moved = fr.move_key(h, 0x20)
    report['move'] = {'ok': moved.get('ok'), 'cursor': h.u(0x2022f726, 1)}
    report['writes'] = m.no_writes(p)
    base = p.image_base
    own = (h.u(pe.ROOT_ADDR + 56), h.u(pe.ROOT_ADDR + 56) + root['block_bytes'])
    ui_root = (pe.ROOT_ADDR, pe.ROOT_ADDR + 0x400)
    outside = {}
    for address, width in engine_writes:
        if own[0] <= address < own[1] or ui_root[0] <= address < ui_root[1]:
            continue
        if any(lo <= address and address + width <= hi for lo, hi in NATIVE_RANGES):
            continue
        outside[hex(address)] = outside.get(hex(address), 0) + 1
    report['engine_write_events'] = len(engine_writes)
    spans = []
    for address in sorted(int(x, 16) for x in outside):
        if spans and address <= spans[-1][1] + 8:
            spans[-1][1] = address + 1
        else:
            spans.append([address, address + 1])
    report['engine_writes_outside_allowlist'] = [[hex(lo), hex(hi), sum(c for a_, c in outside.items() if lo <= int(a_, 16) < hi)]
                                                 for lo, hi in spans]
    report['sp_at_end'] = hex(h.b.get_reg('r15'))
    symbols = sorted((v_, k_) for k_, v_ in p.elf.symbols.items() if v_ < layout['engine_bytes'])
    def nearest(pc):
        best = [name for value, name in symbols if value <= pc]
        return best[-1] if best else '?'
    report['writes_before_block_by_pc'] = {hex(pc): [nearest(pc), c_] for pc, c_ in sorted(heap_pcs.items())}
    report['own_allocation'] = [hex(own[0]), hex(own[1])]
    print('ENGINE_WRITES', len(engine_writes), 'outside allowlist:', json.dumps(report['engine_writes_outside_allowlist']), flush=True)
    save(HERE / ('local/accept-%s.json' % unit), report)
    print('ACCEPT_DONE', unit, json.dumps({k: report[k] for k in ('generation', 'panel_rows', 'move', 'writes')}))


if __name__ == '__main__':
    main()
