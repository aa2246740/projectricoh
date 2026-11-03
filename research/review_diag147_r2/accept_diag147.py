"""Host acceptance: diag v38 gen 147 (read-only: glyph pages P1A/P1B, OK-time card read P2, guarded 8-row
overlay) on the v3.8 body and the real v3.8 resident.

Usage: TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/diag147 \
       /usr/bin/python3 -I -B research/diag147/accept_diag147.py <case> <50mm|28mm|mount>

Body, resident and diag engine run as M32R instructions in tools/native_harness (used, not modified); the
harness setup follows research/unit28_stock/accept_diag146.py (accept_diag38 is imported read-only). The DAT
reaches the card only through seven native entries, and those are models here (as in gen 146):
  0x2005E360 with id 47  semaphore try: free -> 0 (taken); injected busy -> -50, or another code
  0x0500D4FC             signal 47
  0x200A531C/0x200A65F8/0x200AB4F0/0x200A6750/0x200AAD38
                         parse, lookup, attach (sectors per cluster and the handle buffer 0x204CBAB0, as in the
                         emulator), release, fill (file -> handle buffer from the position; returns the valid count;
                         advances the kernel tick word 0x200D183C by 7 so the tick rows can be checked)
Watched, must never be reached: flush 0x200AB02C, lseek, direct read/write, create, rename, delete, the wait on
47 0x0500D4E4, and every high-level file write API. Checked in every case:
  - every successful try is followed by exactly one signal, no signal without a taken try, no try with a
    timeout other than 0, no wait on 47; a busy or failed try is followed by no file call;
  - every file internal runs with 47 held; each read is parse, lookup, attach, (fill), release on a fresh handle;
  - card: zero writes, no flush, content byte-identical; S area: no write, hash unchanged; RPC W count 0;
  - every page of ours is exactly 8 rows; after an OK with keep 0 the stock words are back (7 rows).

cases (each on 50mm, 28mm, mount)
  full     open 1: page S; DISP cycles S P1A P1B P2 G I J H S (all rows checked incl. the two 32-character
           rulers, glyph labels published);
           up/down consumed; OK (keep 0) reads OK and closes; open 2 starts on P2 = OK 25152 32768 T7 F7 N01;
           ADJ and half-press on our list: no read; open 3 is S again; OK reads again (N02); open 4 P2.
  keep1    the official keep setter 0x20265818(1), then OK: one read, P2 drawn at once (K1); the native confirm
           tail then clears the activity word (recorded); a second OK in that state is recorded; a fresh open,
           OK (keep 0) reads again and the next open shows P2 K0.
  faults   one boot, one OK per condition, each next open shows it on P2: busy, lock error -25, no file,
           one other file open, two files open (both BUSY, no file call), 25,151 B, 25,153 B, 40,000 B (fill = cluster), header CRC, effect CRC (byte at 24,000),
           magic, 16 KiB cluster (no fill), fill -1, close -1, then a clean read OK (nothing latched).
  otherfile  review D147-01: OK while another file is open (native count 1): BUSY, the card log is exactly
           try + signal (no parse/lookup/attach/fill/release); the next OK with no file open reads OK.
  refuse   opens refused by part 0/4 at entry show the overlay A/B (DIAG 147); OK there does not reach the DAT
           (no try); then a normal open and OK read.
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
import gxrfx

TREE = ROOT / 'firmware/engine_diag_v38_g147'
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
FIELDS = ('rows', 'opens', 'page', 'wide', 'fx_tries', 'fx_busy', 'reopen_p2', 'ov_rows', 'ov_on', 'ov_fail',
          'refused', 'fx.result', 'fx.keep', 'fx.bytes', 'fx.cluster', 'fx.ticks', 'fx.fill_ticks', 'fx.task')
WORDS = ['NONE', 'OK', 'BUSY', 'LOCK', 'OPEN', 'LEN', 'READ', 'HDR', 'CRC', 'CLOS']
GOOD = gxrfx.build()
READ_CALLS = ['try', 'parse', 'lookup', 'attach', 'fill', 'release', 'signal']


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
    reader = load(ROOT / 'firmware/stage2l_switch/tools/build.py', 'diag147_offset_reader')
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
    m = load(ENGINE_TREE / 'integration_native.py', 'diag147_integration')
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


def p2_expected(opens, result, nbytes=None, cluster=None, ticks=0, fill=None, tries=0, busy=0, keep=0,
                task=None, lock_rc=None, busy_files=0, last_busy=0):
    rows = ['P2 K%s %02X' % ('-' if result == 'NONE' else keep, min(opens, 255))]
    rows.append('RES L%02X' % lock_rc if result == 'LOCK' else 'RES ' + result)
    if result == 'BUSY':
        rows.append('B F%d' % busy_files if busy_files else 'B L47')
    else:
        rows.append('B -' if nbytes is None else 'B %d' % nbytes)
    rows.append('C -' if cluster is None else 'C %d' % cluster)
    rows.append('T -' if result == 'NONE' else 'T %d' % ticks)
    rows.append('F -' if fill is None else 'F %d' % fill)
    rows.append('N%02d BZ%02d' % (tries, busy))
    rows.append('ID%s L%s' % ('--' if result == 'NONE' else '%02X' % min(task, 255),
                               '%02d' % last_busy if last_busy else '--'))
    return rows


def glyph_expected():
    a = ['P1A ', *[''.join(chr(c) for c in range(0x20 + 8 * i, 0x28 + 8 * i)) for i in range(7)]]
    b = ['P1B ', *[''.join(chr(c) for c in range(0x58 + 8 * i, min(0x60 + 8 * i, 0x7f))) for i in range(5)]]
    return a, b


def main():
    case, unit = sys.argv[1], sys.argv[2]
    assert unit in UNIT_NAME and case in ('full', 'keep1', 'faults', 'refuse', 'otherfile'), (case, unit)
    assert sha(base.BODY) == base.BODY_SHA
    scope.freeze_check()
    off = offsets()
    card = Card(GOOD)
    m, h, p, w, syms, file_log = boot(unit, card)
    fr = m.fr
    h.b.add_breakpoint(GETTER, lambda b: False)
    report = {'case': case, 'unit': unit, 'dat': sha(DAT), 'gxrfx': hashlib.sha256(GOOD).hexdigest(),
              'opens': [], 'reads': []}
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

    def ok(label, keep=0, **plan):
        """One OK on our list with the given read condition; returns the card calls of that read."""
        mark = len(card.log)
        card.plan = plan
        saved = None
        if 'open_count' in plan:
            # negative case: n native handles already open (another file, e.g. a photo being written) at the read
            saved = h.u(OPEN_COUNT)
            h.b.write(OPEN_COUNT, plan['open_count'].to_bytes(4, 'big'))
        set_keep(keep)
        assert fr.press(h, 0x23, steps=40000000).get('ok'), label
        if saved is not None:
            assert h.u(OPEN_COUNT) == plan['open_count'], 'open count changed by a refused open'
            h.b.write(OPEN_COUNT, saved.to_bytes(4, 'big'))
        card.plan = {}
        calls = [x['op'] for x in card.log[mark:]]
        row = dict(label=label, keep=keep, plan={k: (v if k != 'content' else len(v)) for k, v in plan.items()},
                   calls=calls, result=WORDS[field('fx.result')], bytes=field('fx.bytes', 4),
                   cluster=field('fx.cluster', 4), ticks=field('fx.ticks', 4), fill=field('fx.fill_ticks', 4),
                   tries=field('fx_tries', 4), busy=field('fx_busy', 4), task=field('fx.task', 2),
                   names_after=hex(h.u(NAMES)), rows_after=h.u(ROWS, 1), reopen_p2=field('reopen_p2'),
                   open_count_after=h.u(OPEN_COUNT))
        report['reads'].append(row)
        print('READ', json.dumps(row), flush=True)
        assert row['open_count_after'] == 0, row
        if keep == 0:
            assert h.u(NAMES) == STOCK and h.u(ROWS, 1) == 7, row
        return row

    def other_key(key, label):
        mark = len(card.log)
        tries = field('fx_tries', 4)
        set_keep(0)
        assert fr.press(h, key, steps=40000000).get('ok'), label
        assert card.log[mark:] == [] and field('fx_tries', 4) == tries, (label, card.log[mark:])
        assert h.u(NAMES) == STOCK and h.u(ROWS, 1) == 7, label
        report.setdefault('other_keys', []).append(dict(key=hex(key), label=label, card_calls=0))

    glyph_a, glyph_b = glyph_expected()

    def check_s(snap):
        r = snap['dat_rows']
        assert snap['rows'] == 8 and snap['page_index'] == 0, snap
        assert r[0][0] == 'S' and r[0][1:5] == '%04X' % snap['opens'] and r[0][5:7] == ' R', r
        assert r[1] == UNIT_NAME[unit] and r[2] == '01510000', r

    def check_p2(snap, **want):
        assert snap['rows'] == 8 and snap['page_index'] == 3, snap
        want.setdefault('task', task_word)
        exp = p2_expected(snap['opens'], **want)
        assert snap['dat_rows'] == exp, (snap['dat_rows'], exp)

    if case == 'full':
        o = open_menu('open1')
        assert o['getter'] == 0
        assert h.u(h.u(R + 56) + 332) == GENERATION
        check_s(o)
        pages = [o]
        for i, name in enumerate(('P1A', 'P1B', 'P2', 'G', 'I', 'J', 'H', 'S')):
            snap = disp('disp%d %s' % (i + 1, name))
            snap['labels'] = labels()
            pages.append(snap)
            r = snap['dat_rows']
            if name == 'P1A':
                assert r == [glyph_a[0] + '%04X' % snap['opens']] + glyph_a[1:], r
            elif name == 'P1B':
                assert r[:6] == [glyph_b[0] + '%04X' % snap['opens']] + glyph_b[1:], r
                assert r[6:] == ['1234567890ABCDEFGHIJKLMNOPQRSTUV', 'MW' * 16], r
            elif name == 'P2':
                check_p2(snap, result='NONE')
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
        r1 = ok('ok1 keep0')
        assert r1['calls'] == READ_CALLS and r1['result'] == 'OK' and r1['reopen_p2'] == 1, r1
        o = open_menu('open2')
        check_p2(o, result='OK', nbytes=25152, cluster=32768, ticks=7, fill=7, tries=1)
        other_key(0x2b, 'ADJ on P2')
        o = open_menu('open3')
        check_s(o)
        other_key(0x0d, 'half-press on S')
        o = open_menu('open4')
        check_s(o)
        r2 = ok('ok2 keep0')
        assert r2['calls'] == READ_CALLS and r2['result'] == 'OK', r2
        o = open_menu('open5')
        check_p2(o, result='OK', nbytes=25152, cluster=32768, ticks=7, fill=7, tries=2)
        r3 = ok('ok3 keep0 on P2')
        assert r3['calls'] == READ_CALLS and r3['result'] == 'OK'
        o = open_menu('open6')
        check_p2(o, result='OK', nbytes=25152, cluster=32768, ticks=7, fill=7, tries=3)
        other_key(0x2b, 'ADJ close')
    elif case == 'keep1':
        # keep 1: the DAT reads and draws P2 at once. The native confirm block still runs its own tail after
        # H07 (research/g121_field_fix/REPORT.md: keep 1 alone does not keep the menu; 0x202C3384 clears the
        # activity word), so what follows is recorded as observed, with the safety checks of every case.
        o = open_menu('open1')
        check_s(o)
        r1 = ok('ok1 keep1', keep=1)
        assert r1['calls'] == READ_CALLS and r1['result'] == 'OK', r1
        snap = snapshot('after ok keep1')
        check_p2(snap, result='OK', nbytes=25152, cluster=32768, ticks=7, fill=7, tries=1, keep=1)
        assert r1['reopen_p2'] == 0, r1
        report['after_keep1'] = dict(activity=snap['activity'], names=snap['names'], rows=snap['rows'])
        # a second OK in that state: recorded (whether it reaches the DAT depends on the resident's owned())
        mark, tries = len(card.log), field('fx_tries', 4)
        set_keep(0)
        assert fr.press(h, 0x23, steps=40000000).get('ok')
        second = [x['op'] for x in card.log[mark:]]
        snap = snapshot('second OK after keep1')
        report['second_ok_after_keep1'] = dict(card_calls=second, tries_before=tries, tries_after=field('fx_tries', 4),
                                               names=snap['names'], rows=snap['rows'], activity=snap['activity'])
        assert second in ([], READ_CALLS), second
        o = open_menu('open2')
        assert o['rows'] == 8 and o['page_index'] in (0, 3), o
        r2 = ok('ok3 keep0')
        assert r2['calls'] == READ_CALLS and r2['result'] == 'OK'
        o = open_menu('open3')
        check_p2(o, result='OK', nbytes=25152, cluster=32768, ticks=7, fill=7, tries=field('fx_tries', 4), keep=0)
        other_key(0x2b, 'ADJ close')
    elif case == 'faults':
        good = bytearray(GOOD)
        hdr = bytearray(GOOD)
        hdr[30] ^= 1                    # reserved header byte inside the header CRC
        eff = bytearray(GOOD)
        eff[24000] ^= 0x40              # inside the last effect, past 16 KiB
        mag = bytearray(GOOD)
        mag[7] = ord('1')
        opened = ['try', 'parse', 'lookup', 'attach', 'release', 'signal']
        steps = [
            ('busy', dict(busy=True), dict(result='BUSY', calls=['try'], busy=1)),
            ('lock -25', dict(try_rc=-25), dict(result='LOCK', calls=['try'], lock_rc=0x19)),
            ('no file', dict(nofile=True), dict(result='OPEN', calls=['try', 'parse', 'lookup', 'signal'])),
            ('one file open', dict(open_count=1), dict(result='BUSY', calls=['try', 'signal'], busy=1, busy_files=1)),
            ('two files open', dict(open_count=2), dict(result='BUSY', calls=['try', 'signal'], busy=1, busy_files=2)),
            ('25151 B', dict(content=bytes(good[:-1])), dict(result='LEN', nbytes=25151)),
            ('25153 B', dict(content=bytes(good) + b'\0'), dict(result='LEN', nbytes=25153)),
            ('40000 B', dict(content=bytes(good) + bytes(40000 - len(good))), dict(result='LEN', nbytes=32768)),
            ('header CRC', dict(content=bytes(hdr)), dict(result='CRC', nbytes=25152)),
            ('effect CRC', dict(content=bytes(eff)), dict(result='CRC', nbytes=25152)),
            ('magic', dict(content=bytes(mag)), dict(result='HDR', nbytes=25152)),
            ('16 KiB cluster', dict(sectors=32), dict(result='LEN', cluster=16384, calls=opened)),
            ('fill -1', dict(fill_fail=True), dict(result='READ')),
            ('close -1', dict(release_fail=True), dict(result='CLOS', nbytes=25152)),
            ('clean', {}, dict(result='OK', nbytes=25152)),
        ]
        # the independent Python reading of the same files gives the same words
        for label, plan, want in steps:
            if 'content' in plan:
                assert gxrfx.check(plan['content'], 32768) == want['result'], label
        assert gxrfx.check(GOOD, 16384) == 'LEN' and gxrfx.check(GOOD, 32768) == 'OK'
        o = open_menu('open1')
        check_s(o)
        busy = last = 0
        for i, (label, plan, want) in enumerate(steps):
            row = ok(label, **plan)
            calls = want.get('calls', READ_CALLS)
            assert row['calls'] == calls, (label, row['calls'], calls)
            assert row['result'] == want['result'], (label, row)
            busy += want.get('busy', 0)
            last = i + 1 if want.get('busy') else last
            o = open_menu('open after ' + label)
            filled = 'fill' in calls
            check_p2(o, result=want['result'], nbytes=want.get('nbytes'),
                     cluster=want.get('cluster', 32768 if 'attach' in calls else None),
                     ticks=7 if filled else 0, fill=7 if filled else None, tries=i + 1, busy=busy,
                     lock_rc=want.get('lock_rc'), busy_files=want.get('busy_files', 0), last_busy=last)
        other_key(0x2b, 'ADJ close')
        report['fault_words'] = [(label, want['result']) for label, _, want in steps]
    elif case == 'otherfile':
        # review D147-01: another file open (native count 1) when OK is pressed: BUSY with 47 taken and released
        # once, no parse/lookup/attach/fill/release call; nothing latched, the next OK with no file open reads.
        o = open_menu('open1')
        check_s(o)
        r1 = ok('ok with one other file open', open_count=1)
        assert r1['calls'] == ['try', 'signal'] and r1['result'] == 'BUSY', r1
        o = open_menu('open2')
        check_p2(o, result='BUSY', tries=1, busy=1, busy_files=1, last_busy=1)
        r2 = ok('ok with no file open')
        assert r2['calls'] == READ_CALLS and r2['result'] == 'OK', r2
        o = open_menu('open3')
        check_p2(o, result='OK', nbytes=25152, cluster=32768, ticks=7, fill=7, tries=2, busy=1, last_busy=1)
        other_key(0x2b, 'ADJ close')
        report['otherfile'] = dict(busy_calls=r1['calls'], then=r2['calls'])
    elif case == 'refuse':
        inject = {'part': None}

        def at_observe(b):
            if b.get_reg('r1') == 1 and inject['part'] is not None:
                b.write(0x205a280f, bytes([inject['part']]))
            return False
        h.b.add_breakpoint(syms['rv_hook_observe'], at_observe)
        o = open_menu('open1 normal')
        check_s(o)
        other_key(0x2b, 'ADJ close')
        for index, part in enumerate((0, 4)):
            inject['part'] = part
            o = open_menu('refuse part%d' % part)
            inject['part'] = None
            assert o['rows'] == 8 and o['ov_on'] == 1 and o['overlay'][7] == 'DIAG 147', o
            assert o['overlay'][0][0] == 'AB'[index], o['overlay']
            mark, tries = len(card.log), field('fx_tries', 4)
            set_keep(0)
            assert fr.press(h, 0x23, steps=40000000).get('ok')
            assert card.log[mark:] == [] and field('fx_tries', 4) == tries, card.log[mark:]
            report.setdefault('refused_ok', []).append(dict(part=part, card_calls=0))
        o = open_menu('open normal after')
        check_s(o)
        assert o['ov_on'] == 0
        r = ok('ok after refusals')
        assert r['calls'] == READ_CALLS and r['result'] == 'OK'
        o = open_menu('open P2')
        check_p2(o, result='OK', nbytes=25152, cluster=32768, ticks=7, fill=7, tries=1)
        other_key(0x2b, 'ADJ close')

    # ---- lock, file, card, S and unit audit ------------------------------------------------------
    report['card_log'] = card.log
    report['violations'] = card.violations
    tries = [x for x in card.log if x['op'] == 'try']
    taken = [x for x in tries if x['result'] == 0]
    signals = [x for x in card.log if x['op'] == 'signal']
    report['lock'] = dict(tries=len(tries), taken=len(taken), not_taken=len(tries) - len(taken), signals=len(signals))
    assert not card.violations, card.violations
    assert len(taken) == len(signals), report['lock']
    for i, x in enumerate(card.log):
        if x['op'] == 'try' and x['result'] != 0:
            nxt = card.log[i + 1] if i + 1 < len(card.log) else None
            assert nxt is None or nxt['op'] == 'try', (i, x, nxt)
    assert all(x['locked'] for x in card.log if x['op'] in FS.values()), 'file call without the lock'
    report['high_level_fx_opens'] = [x for x in file_log if x['path'] == FX]
    assert not report['high_level_fx_opens']
    report['creates_renames_deletes'] = [x for x in p.native_log if x.get('op') in ('create', 'rename', 'delete')]
    assert not report['creates_renames_deletes']
    report['card_writes'] = 0          # the model has no write entry; flush and every write API are watched above
    assert card.content == GOOD
    report['card_unchanged'] = True
    report['s_writes'] = s_writes
    report['s_hash_same'] = hashlib.sha256(h.b.read(s_base, 4096)).hexdigest() == s0
    assert not s_writes and report['s_hash_same'], s_writes[:5]
    report['rpc_w'] = sum(1 for e in p.rpc.log if e['cmd'] == 22)
    assert report['rpc_w'] == 0
    report['rpc_commands'] = sorted({e['cmd'] for e in p.rpc.log})
    save(HERE / ('local/accept147-%s-%s.json' % (case, unit)), report)
    print('ACCEPT_DONE', case, unit, 'lock', json.dumps(report['lock']), 'reads', len(report['reads']), flush=True)


if __name__ == '__main__':
    main()
