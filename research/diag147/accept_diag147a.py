"""Host acceptance: g147a (file-free diag v38 DAT: glyph pages P1A/P1B with 32-character rulers, S/G/I/J/H pages,
guarded 8-row overlay; no card read) on the v3.8 body and the real v3.8 resident.

Usage: TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/diag147 \
       /usr/bin/python3 -I -B research/diag147/accept_diag147a.py <full|refuse> <50mm|28mm|mount>

Body, resident and diag engine run as M32R instructions in tools/native_harness (used, not modified); the harness
setup and the card watch points are those of accept_diag147.py: the semaphore-47 try 0x2005E360 (id 47), its
signal 0x0500D4FC and wait 0x0500D4E4, the five read internals, flush, lseek, direct read/write, create, rename,
delete and every high-level file API are breakpoints. For g147a every one of them must stay at zero calls.
Checked in every case: card log empty (no try, no file call), S area no write and hash unchanged, RPC W 0, no
create/rename/delete, every page of ours exactly 8 rows, stock words back (7 rows) after each close.

cases (each on 50mm, 28mm, mount)
  full    open 1: page S; DISP cycles S P1A P1B G I J H S (every row checked incl. the two 32-character rulers,
          8 non-empty glyph labels per page, rulers 64 B); up/down consumed; OK (keep 0) closes, no card call;
          open 2 is S again; OK with keep 1 (official setter 0x20265818): recorded, no card call, then a second
          OK; ADJ and half-press close; final open S
  refuse  opens refused by part 0/4 at entry show the overlay A/B (last row DIAG147A); OK there: no card call;
          then a normal open and OK close
"""
import hashlib
import json
import struct
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import scope
from scope import load, save, sha
scope.enable_fence()
U28 = ROOT / 'research/unit28_stock'
sys.path.insert(1, str(U28))
import accept_diag38 as base

TREE = ROOT / 'firmware/engine_diag_v38_g147a'
DAT = TREE / 'candidate/local/full-r1/GXRCE.DAT'
ENGINE = TREE / 'candidate/local/full-r1/engine.elf'
PRODUCT = TREE / 'candidate/containers/product'
ENGINE_TREE = ROOT / 'firmware/engine_v48_own'
GENERATION = 147
R = 0x20054700
GETTER = 0x202870a4
NAMES, ROWS, STOCK = 0x2022f5a8, 0x2022f5ac, 0x2022d610
FX = '/ATA1/GXRFX.BIN'
POLL, WAIT47, SIGNAL47 = 0x2005E360, 0x0500D4E4, 0x0500D4FC
TICK, OPEN_COUNT = 0x200D183C, 0x204C8668
FS = {0x200A531C: 'parse', 0x200A65F8: 'lookup', 0x200AB4F0: 'attach', 0x200A6750: 'release',
      0x200AAD38: 'fill'}
NEVER = {0x200AB02C: 'flush', 0x200AB580: 'lseek', 0x200ADAD0: 'direct read', 0x200AE360: 'direct write',
         0x200A544C: 'create', 0x200A41AC: 'create', 0x200A49D8: 'rename', 0x200A4910: 'delete'}
HIGH = {0x200A449C: 'api_read', 0x200A45E8: 'api_write', 0x200A437C: 'api_close', 0x200A479C: 'api_write_b',
        0x200A48C8: 'api_write_c', 0x200A4880: 'api_read_b', 0x200A46F0: 'api_read_c', 0x200A519C: 'api_seek'}
UNIT_NAME = {'50mm': 'jlaunch', '28mm': 'qlaunch', 'mount': 'l08firm'}
FIELDS = ('rows', 'opens', 'page', 'wide', 'ov_rows', 'ov_on', 'ov_fail', 'refused')
GOOD = b''          # no file is read; the card model only watches for calls


def offsets():
    out = HERE / 'local/layout147'
    out.mkdir(parents=True, exist_ok=True)
    src = out / 'offsets.c'
    src.write_text('#include "' + str(PRODUCT / 'diag.c') + '"\n' + 'const uint32_t diag_offsets[]={' +
                   ','.join('offsetof(Diagnostic,%s)' % k for k in FIELDS) + '};\n')
    gcc = ROOT / 'research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc'
    subprocess.run([str(gcc), '-std=c11', '-Os', '-ffreestanding', '-fpic', '-m32r', '-mmodel=medium',
                    '-msdata=none', '-G0', '-fno-builtin', '-c', str(src), '-o', str(out / 'offsets.o')],
                   check=True, cwd=ROOT)
    reader = load(ROOT / 'firmware/stage2l_switch/tools/build.py', 'diag147a_offset_reader')
    elf = reader.Elf(out / 'offsets.o')
    s = elf.symbols['diag_offsets']
    blob = elf.content(elf.sections[s['section']])[s['value']:s['value'] + 4 * len(FIELDS)]
    return dict(zip(FIELDS, struct.unpack('>%dI' % len(FIELDS), blob)))


class Card:
    """Semaphore 47 and the read internals; `plan` holds the condition of the next read."""

    def __init__(self, content):
        self.content = bytes(content)
        self.plan = {}
        self.count, self.holder = 1, None
        self.tries = 0
        self.parsed, self.handles, self.next_fd = None, {}, 0x81
        self.log, self.violations, self.high = [], [], []

    def note(self, op, **kw):
        row = dict(op=op, locked=self.holder == 'dat', **kw)
        self.log.append(row)
        return row

    def need_lock(self, op):
        if self.holder != 'dat':
            self.violations.append('%s without semaphore 47' % op)

    def try_(self, timeout):
        self.tries += 1
        if timeout != 0:
            self.violations.append('try with timeout %d' % timeout)
        if self.plan.get('busy'):
            self.note('try', result=-50, holder='native')
            return -50
        if self.plan.get('try_rc'):
            self.note('try', result=self.plan['try_rc'], holder='none')
            return self.plan['try_rc']
        if self.count == 0:
            self.violations.append('second try while held by the DAT')
            self.note('try', result=-50, holder=self.holder)
            return -50
        self.count, self.holder = 0, 'dat'
        self.note('try', result=0)
        return 0

    def signal(self):
        if self.holder != 'dat':
            self.violations.append('signal without a taken try')
        self.note('signal')
        self.count, self.holder = 1, None


def install_card(h, card, pe):
    occupied = {hex(a): bool(h.b.breakpoints.get(a)) for a in (POLL, WAIT47, SIGNAL47, *FS)}
    assert not any(occupied.values()), occupied

    def ret(b, value):
        if value is not None:
            b.set_reg('r0', value & 0xffffffff)
        b.set_reg('pc', b.get_reg('r14'))
        return False

    def poll(b):
        if b.get_reg('r4') != 47:
            return False          # other semaphores: the real wrapper runs
        timeout = b.get_reg('r5')
        return ret(b, card.try_(timeout if timeout < 0x80000000 else timeout - (1 << 32)))
    h.b.add_breakpoint(POLL, poll)

    def wait47(b):
        card.violations.append('wait on 47 (0x0500D4E4) from lr %08x' % b.get_reg('r14'))
        return False
    h.b.add_breakpoint(WAIT47, wait47)

    def signal(b):
        card.signal()
        return ret(b, None)
    h.b.add_breakpoint(SIGNAL47, signal)

    def high(name):
        def hit(b):
            card.high.append(dict(api=name, fd=b.get_reg('r4')))
            if name.startswith('api_write'):
                card.violations.append('high-level file write %s reached' % name)
            return False
        return hit
    for address, name in HIGH.items():
        h.b.add_breakpoint(address, high(name))

    def fs(name):
        def hit(b):
            r4, r5, r6 = (b.get_reg('r%d' % i) for i in (4, 5, 6))
            card.need_lock(name)
            plan = card.plan
            if name == 'parse':
                card.parsed = pe.cstr(h, r4)
                card.note('parse', path=card.parsed)
                return ret(b, 0)
            if name == 'lookup':
                ok = not plan.get('nofile') and card.parsed == FX and r5 == 2 and r4 == 0x204c866c
                fd = card.next_fd if ok else -1
                if ok:
                    card.handles[fd] = 0
                    card.next_fd += 1
                card.note('lookup', path=card.parsed, mode=r5, fd=fd)
                return ret(b, fd)
            if name == 'attach':
                if r4 not in card.handles or r5 != r6 + 2 or r6 != 0x204c86ec + 16 * (r4 & 15) + 2:
                    card.violations.append('attach arguments %x %x %x' % (r4, r5, r6))
                h.b.write(r6, (plan.get('sectors', 64)).to_bytes(2, 'big'))
                h.b.write(r5, (0x204cbab0).to_bytes(4, 'big'))
                card.note('attach', fd=r4)
                return ret(b, 0)
            if name == 'release':
                card.handles.pop(r4, None)
                rc = -1 if plan.get('release_fail') else 0
                card.note('release', fd=r4, result=rc)
                return ret(b, rc)
            if r4 not in card.handles:
                card.violations.append('%s on a handle that is not open' % name)
                return ret(b, -1)
            pos = card.handles[r4]
            entry = 0x204c86ec + 16 * (r4 & 15)
            buffer, sectors = h.u(entry + 4), h.u(entry + 2, 2)
            if pos != 0:
                card.violations.append('fill not from position 0')
            if h.u(entry, 2) != 2 or r6 != sectors << 9:
                card.violations.append('fill arguments differ from the buffered read API (%x %x)' % (r4, r6))
            h.b.write(TICK, ((h.u(TICK) + 7) & 0xffffffff).to_bytes(4, 'big'))
            if plan.get('fill_fail'):
                card.note('fill', offset=pos, n=r6, result=-1)
                return ret(b, -1)
            content = plan.get('content', card.content)
            chunk = bytes(content[pos:pos + r6])
            h.b.write(buffer, chunk)
            card.handles[r4] = pos + len(chunk)
            card.note('fill', offset=pos, n=r6, result=len(chunk))
            return ret(b, len(chunk))
        return hit
    for address, name in FS.items():
        h.b.add_breakpoint(address, fs(name))
    for address, name in NEVER.items():
        def never(b, name=name):
            card.violations.append('%s reached' % name)
            return False
        h.b.add_breakpoint(address, never)


def boot(unit, card):
    sys.path.insert(0, str(ENGINE_TREE))
    m = load(ENGINE_TREE / 'integration_native.py', 'diag147a_integration')
    v, fr, pe = m.v, m.fr, m.pe
    v.BODY_SHA = sha(base.BODY)
    v.RESIDENT_ELF = base.RESIDENT
    v.ENGINE_ELF = ENGINE
    defaults = list(v.V35Harness.__init__.__defaults__)
    defaults[0] = base.BODY
    v.V35Harness.__init__.__defaults__ = tuple(defaults)
    m.DAT = DAT
    pe.STAGED, pe.STAGED_SHA, pe.ENGINE_ELF = DAT, sha(DAT), ENGINE
    v.python_backend.CACHE = HERE / 'local/decode' / unit
    file_log = []

    class Files(m.Files):
        def __init__(self, dat):
            super().__init__(dat)
            self.paths = {k: bytearray(v_) for k, v_ in self.paths.items()}

    class Product(m.Product):
        def _install(self):
            super()._install()
            h = self.h

            def opened(b):
                path = pe.cstr(h, b.get_reg('r4'))
                fd = self.files.open(path) if path != FX else -1
                file_log.append(dict(op='open', path=path, flags=b.get_reg('r5'), fd=fd))
                self.native_log.append(dict(op='open', path=path, flags=b.get_reg('r5'), fd=fd))
                return fd
            h.b.breakpoints.pop(0x200a40b4, None)
            self._native(0x200a40b4, 'file_open', opened)

    pe.FileEdge, fr.Product = Files, Product
    pe.UNITS['mount'] = (ROOT / 'firmware/package_v36_g120b/SD_ROOT/l08firm3',
                         '0a4dff6d3be9b9a9b56dfcbd98a2df59efcb31f7d4eaca6b0c3fbdb1641fde44', 2)
    v.harness_mod.Harness = v.V35Harness
    syms = v.Elf(base.RESIDENT).symbols
    fr.OBSERVE = syms['rv_hook_observe']
    fr.LAND = {syms['rv_skip_06']: 'h06_skip', syms['rv_close_07']: 'h07_close',
               syms['rv_skip_08']: 'h08_skip', 0x202871dc: 'native_setter',
               0x202bb96c: 'native_h08', 0x20268768: 'native_setter_store',
               0x20268774: 'native_row_store'}
    h, p, w = m.boot(unit, files={'/ATA1/GXRCE.DAT': DAT.read_bytes()}, ready=1, link=1)
    h.stub(0x0500c6ec, 'kernel_context', value=0)

    def task_id(b):
        b.write(b.core.r[4], (6).to_bytes(2, 'big'))
        return 0
    h.stub(0x0500c574, 'kernel_task_id', task_id)
    install_card(h, card, pe)
    return m, h, p, w, syms, file_log


def glyph_expected():
    a = ['P1A ', *[''.join(chr(c) for c in range(0x20 + 8 * i, 0x28 + 8 * i)) for i in range(7)]]
    b = ['P1B ', *[''.join(chr(c) for c in range(0x58 + 8 * i, min(0x60 + 8 * i, 0x7f))) for i in range(5)]]
    return a, b


def main():
    case, unit = sys.argv[1], sys.argv[2]
    assert unit in UNIT_NAME and case in ('full', 'refuse'), (case, unit)
    assert sha(base.BODY) == base.BODY_SHA
    scope.freeze_check()
    off = offsets()
    card = Card(GOOD)
    m, h, p, w, syms, file_log = boot(unit, card)
    fr = m.fr
    h.b.add_breakpoint(GETTER, lambda b: False)
    report = {'case': case, 'unit': unit, 'dat': sha(DAT), 'opens': [], 'presses': []}
    s_base = h.u(0x200c0dac)
    s_writes = []
    h.b.add_write_trace(s_base, s_base + 4096, lambda e: s_writes.append(
        dict(pc=hex(e.pc) if e.pc is not None else None, offset=hex(e.address - s_base), value=e.data.hex())))
    s0 = hashlib.sha256(h.b.read(s_base, 4096)).hexdigest()
    task_word = h.u(0x200d1838, 2)
    report['kernel_task_word'] = task_word

    def image_entered(b):
        block = h.u(R + 56)
        if block:
            p.image_base = h.u(block + 312)
        return False
    h.b.add_breakpoint(h.symbols['rv_invoke'], image_entered)

    def nb():
        return p.image_base + p.elf.symbols['n']

    def field(name, size=1):
        return h.u(nb() + off[name], size)

    def text_rows(key='rows', width=9, count=8):
        at = nb() + off[key]
        return [h.b.read(at + width * i, width).split(b'\0', 1)[0].decode('ascii') for i in range(count)]

    def shown():
        """The DAT's 8 source rows of the page last formatted (P1B rows 6-7 from the 32-character buffer)."""
        r = text_rows()
        if field('page') == 2:
            r[6:8] = text_rows('wide', 33, 2)
        return r

    def labels():
        """Glyph strings of the live 8-row label table (0x2022F5A8), as the native list draws them."""
        table, rows = h.u(NAMES), h.u(ROWS, 1)
        out = []
        for i in range(rows):
            g = h.u(h.u(table + 4 * i))
            out.append(h.b.read(g, 96).split(b'\0', 1)[0].hex())
        return out

    def snapshot(label):
        snap = base.snapshot(h)
        snap.update(label=label, root_state=h.u(R + 5, 1))
        if p.image_base:
            snap.update(page_index=field('page'), dat_rows=shown(), ov_on=field('ov_on'),
                        overlay=text_rows('ov_rows'), opens=field('opens', 4))
        report['opens'].append(snap)
        print('SNAP', json.dumps({k: v for k, v in snap.items() if k != 'overlay'}), flush=True)
        return snap

    def open_menu(label):
        g0 = h.b.visits.get(GETTER, 0)
        h.parent()
        result = fr.native(h, 0x20287080, (), steps=40000000)
        assert result.get('ok'), (label, result)
        snap = snapshot(label)
        snap['getter'] = h.b.visits.get(GETTER, 0) - g0
        return snap

    def disp(label):
        assert fr.native(h, 0x202be220, steps=40000000).get('ok'), label
        snap = snapshot(label)
        assert snap['rows'] == 8, snap
        return snap

    def set_keep(keep):
        # the official flag setter (as research/g122_keep_list/confirm_paths.py); 0x2037F2FE is not written here
        assert fr.native(h, 0x20265818, (keep,)).get('ok') and h.u(0x2037f2fe, 1) == keep

    def press(key, label, keep=0, closes=True):
        """One key on our list through the native confirm block; no card call may follow."""
        mark = len(card.log)
        set_keep(keep)
        assert fr.press(h, key, steps=40000000).get('ok'), label
        snap = snapshot('after ' + label)
        row = dict(label=label, key=hex(key), keep=keep, card_calls=[x['op'] for x in card.log[mark:]],
                   names=snap['names'], rows=snap['rows'], activity=snap['activity'])
        report['presses'].append(row)
        print('PRESS', json.dumps(row), flush=True)
        assert row['card_calls'] == [], row
        if closes:
            assert h.u(NAMES) == STOCK and h.u(ROWS, 1) == 7, row
        return row

    glyph_a, glyph_b = glyph_expected()

    def check_s(snap):
        r = snap['dat_rows']
        assert snap['rows'] == 8 and snap['page_index'] == 0, snap
        assert r[0][0] == 'S' and r[0][1:5] == '%04X' % snap['opens'] and r[0][5:7] == ' R', r
        assert r[1] == UNIT_NAME[unit] and r[2] == '01510000', r

    if case == 'full':
        o = open_menu('open1')
        assert o['getter'] == 0
        assert h.u(h.u(R + 56) + 332) == GENERATION
        check_s(o)
        pages = [o]
        for i, name in enumerate(('P1A', 'P1B', 'G', 'I', 'J', 'H', 'S')):
            snap = disp('disp%d %s' % (i + 1, name))
            snap['labels'] = labels()
            pages.append(snap)
            r = snap['dat_rows']
            if name == 'P1A':
                assert snap['page_index'] == 1 and r == [glyph_a[0] + '%04X' % snap['opens']] + glyph_a[1:], r
            elif name == 'P1B':
                assert snap['page_index'] == 2 and r[:6] == [glyph_b[0] + '%04X' % snap['opens']] + glyph_b[1:], r
                assert r[6:] == ['1234567890ABCDEFGHIJKLMNOPQRSTUV', 'MW' * 16], r
                assert [len(x) // 2 for x in snap['labels'][6:]] == [64, 64], snap['labels']
            elif name == 'S':
                check_s(snap)
            else:
                assert r[0][0] == name and r[0][1:5] == '%04X' % snap['opens'], r
            assert len(snap['labels']) == 8 and all(snap['labels']), snap['labels']
        report['page_cycle'] = [dict(page=p_['page_index'], rows=p_['dat_rows'], labels=p_.get('labels'))
                                for p_ in pages]
        before = len(s_writes)
        for key in (0x20, 0x1f):
            assert fr.move_key(h, key, steps=40000000).get('ok')
            snap = snapshot('move %x' % key)
            assert snap['rows'] == 8 and snap['page_index'] == 0, snap
        assert len(s_writes) == before
        press(0x23, 'OK keep0 on S')
        o = open_menu('open2')
        check_s(o)
        k1 = press(0x23, 'OK keep1', keep=1, closes=False)
        report['after_keep1'] = k1
        press(0x23, 'second OK after keep1')
        o = open_menu('open3')
        check_s(o)
        press(0x2b, 'ADJ close')
        o = open_menu('open4')
        check_s(o)
        press(0x0d, 'half-press close')
        o = open_menu('open5')
        check_s(o)
        press(0x23, 'OK close')
    elif case == 'refuse':
        fault_case = {'part': None}

        def at_observe(b):
            if b.get_reg('r1') == 1 and fault_case['part'] is not None:
                b.write(0x205a280f, bytes([fault_case['part']]))
            return False
        h.b.add_breakpoint(syms['rv_hook_observe'], at_observe)
        o = open_menu('open1 normal')
        check_s(o)
        press(0x2b, 'ADJ close')
        for index, part in enumerate((0, 4)):
            fault_case['part'] = part
            o = open_menu('refuse part%d' % part)
            fault_case['part'] = None
            assert o['rows'] == 8 and o['ov_on'] == 1 and o['overlay'][7] == 'DIAG147A', o
            assert o['overlay'][0][0] == 'AB'[index], o['overlay']
            press(0x23, 'OK on refusal page %d' % part, closes=False)
        o = open_menu('open normal after')
        check_s(o)
        assert o['ov_on'] == 0
        press(0x23, 'OK close')

    # ---- card, S and unit audit ------------------------------------------------------------------
    report['card_log'] = card.log
    report['violations'] = card.violations
    report['lock'] = dict(tries=card.tries, card_calls=len(card.log))
    assert not card.violations, card.violations
    assert card.tries == 0 and card.log == [], card.log
    report['high_level_calls'] = card.high
    report['high_level_fx_opens'] = [x for x in file_log if x['path'] == FX]
    assert not report['high_level_fx_opens']
    report['creates_renames_deletes'] = [x for x in p.native_log if x.get('op') in ('create', 'rename', 'delete')]
    assert not report['creates_renames_deletes']
    report['card_writes'] = 0
    report['s_writes'] = s_writes
    report['s_hash_same'] = hashlib.sha256(h.b.read(s_base, 4096)).hexdigest() == s0
    assert not s_writes and report['s_hash_same'], s_writes[:5]
    report['rpc_w'] = sum(1 for e in p.rpc.log if e['cmd'] == 22)
    assert report['rpc_w'] == 0
    report['rpc_commands'] = sorted({e['cmd'] for e in p.rpc.log})
    save(HERE / ('local/accept147a-%s-%s.json' % (case, unit)), report)
    print('ACCEPT_DONE', case, unit, 'card calls', len(card.log), 'presses', len(report['presses']), flush=True)


if __name__ == '__main__':
    main()
