"""Boot the v3.8 body + gen 139 DAT in the existing host model (read-only reuse).

Copy of research/g138_persist/g138_host.py retargeted to g139: package and
engine from G139_PACKAGE / G139_ENGINE (defaults: the g139 release package).

Reuses research/g135_v37/accept.py's boot (engine_v48_own integration model,
python M32R backend) with every path rebound to gen 138. Writes only under
research/g138_persist/local. Run with /usr/bin/python3 -I -B.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import sys

ROOT = Path(__file__).resolve().parents[3]
WORK = Path(__file__).resolve().parent
import os as _os
LOCAL = WORK / 'local'
TMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/g139/host')
PACKAGE = ROOT / _os.environ.get('G139_PACKAGE', 'firmware/package_v38_g139') / 'local/SD_ROOT'
DAT = PACKAGE / 'GXRCE.DAT'
BODY = PACKAGE / 'ilaunch3'
RESIDENT = ROOT / 'firmware/resident_v38/local/resident/build/resident.elf'
ENGINE = ROOT / _os.environ.get('G139_ENGINE', 'firmware/engine_v56_g139') / 'candidate/local/full-r13/engine.elf'
BODY_SHA = 'd4fa3b46da137b8b7c7c703e66750a8249c0715271290c0fdb490a2f7a239a90'
R = 0x20054700
S_POINTER = 0x200c0dac
LOCK = 0x204104f0


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(name, value):
    path = LOCAL / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + '\n')


def setup():
    sys.dont_write_bytecode = True
    LOCAL.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    os.environ.update(TMPDIR=str(TMP), PYTHONDONTWRITEBYTECODE='1')
    sums = dict(reversed(line.split('  ', 1)) for line in (PACKAGE.parents[1] / 'SHA256SUMS').read_text().splitlines())
    assert sha(DAT) == sums[str(DAT.relative_to(ROOT))] and sha(BODY) == BODY_SHA


def accept_module():
    spec = importlib.util.spec_from_file_location('g139_accept_base', ROOT / 'research/g135_v37/accept.py')
    old = importlib.util.module_from_spec(spec)
    sys.modules['g139_accept_base'] = old
    spec.loader.exec_module(old)
    old.HERE = LOCAL
    old.PACKAGE, old.BODY, old.DAT = PACKAGE, BODY, DAT
    old.RESIDENT, old.ENGINE, old.GENERATION, old.TAG = RESIDENT, ENGINE, int.from_bytes(DAT.read_bytes()[28:32], 'big'), ''
    old.freeze = lambda: None
    old.save = lambda name, value: save(name, value)
    return old


LAYOUT = json.loads((ROOT / 'research/emptystack_v38/adapter-layout.json').read_text())
UI = LAYOUT['ui']
UNITS = {'50mm': 0, '28mm': 1, 'mount': 2}
DAT_BYTES = {}


def record_bytes(dat, slot, unit, levels, version=1, flags=1, magic=b'GXR2'):
    """Independent encoder of the S+0xFD4 record (REPORT section 7.1)."""
    import zlib
    body = magic + bytes([version, slot, unit, flags]) + b''.join(
        (v & 0xffff).to_bytes(2, 'big') for v in levels) + dat[20:28]
    return body + (zlib.crc32(body) & 0xffffffff).to_bytes(4, 'big')


class Camera:
    """One booted host model. All state access goes through h (the harness)."""

    def __init__(self, unit, normal=True, dat=None):
        self.old = accept_module()
        self.dat_path = Path(dat or DAT)
        if dat:
            self.old.DAT = self.dat_path
        DAT_BYTES[self.dat_path] = self.dat_path.read_bytes()
        self.m, self.h, self.p, self.w = self.old.boot(unit)
        self.unit = unit
        if normal:
            self.normal_boot()

    # ---- fixture state -------------------------------------------------
    @property
    def s(self):
        return self.h.u(S_POINTER)

    def s_bytes(self, offset, length):
        return bytes(self.h.b.read(self.s + offset, length))

    def put_s(self, offset, data):
        self.h.b.write(self.s + offset, bytes(data))

    def normal_boot(self):
        """Model a normal camera boot: Standard, WB 9/9, Body start settings,
        S extension 0xD24 and the stock parameter lock idle (count -1, ID 55)."""
        self.put_s(0x36e, b'\x01')
        self.put_s(0x6dd, b'\x09\x09')
        self.put_s(8, b'\x00')
        self.put_s(0xe, b'\x0d\x24')
        self.put_s(0xfd4, bytes(40))
        self.set_lock(-1)

    def set_lock(self, count, ident=55):
        self.h.b.write(LOCK, (count & 0xffffffff).to_bytes(4, 'big') + ident.to_bytes(4, 'big'))

    def lock(self):
        return int.from_bytes(self.h.b.read(LOCK, 4), 'big', signed=True), self.h.u(LOCK + 4)

    def record(self):
        return self.s_bytes(0xfd4, 40)

    # ---- engine-side reads ---------------------------------------------
    def symbol(self, name):
        return self.p.symbol_pc(name)

    def engine_bytes(self, offset, length):
        return bytes(self.h.b.read(self.symbol('g') + offset, length))

    def snapshot(self):
        return self.old.snapshot(self.h)

    def open_menu(self):
        """H01 (first open or reopen): parent view, then the native constructor."""
        self.h.parent()
        return self.m.published(self.h, self.p, self.w)

    # ---- adapter UI (offsets from the unchanged adapter layout) ----------
    @property
    def adapter(self):
        return self.p.symbol_pc('n')

    def ui(self, name):
        return self.h.u(self.adapter + UI + LAYOUT['ui.' + name], 1)

    def labels(self):
        base = self.adapter + UI + LAYOUT['ui.text']
        return [bytes(self.h.b.read(base + 9 * i, 9)).split(b'\0')[0].decode('ascii') for i in range(8)]

    def levels(self):
        raw = bytes(self.h.b.read(self.adapter + UI + LAYOUT['ui.levels'], 20))
        return [int.from_bytes(raw[2 * i:2 * i + 2], 'big', signed=True) for i in range(10)]

    def state(self):
        names = ('screen', 'cur', 'top', 'physical', 'count', 'slot', 'applied_user')
        result = {name: self.ui(name) for name in names}
        result.update(levels=self.levels(), labels=self.labels(), rows=self.h.u(0x2022f5ac, 1),
                      native_cursor=self.h.u(0x2022f726, 1), cursor_cache=self.h.u(0x205a2944, 1),
                      failed=self.h.u(self.adapter + LAYOUT['failed'], 1))
        return result

    def check_frame(self):
        st = self.state()
        assert st['rows'] == 8, st
        assert st['native_cursor'] == st['physical'] + 1 == st['cursor_cache'], st
        assert st['cur'] == st['top'] + st['physical'], st
        return st

    def press(self, key):
        fr = self.m.fr
        if key in ('UP', 'DOWN'):
            result = fr.move_key(self.h, 0x1f if key == 'UP' else 0x20, steps=30000000)
        elif key == 'DISP':
            result = fr.native(self.h, 0x202be220, steps=30000000)
        elif key in ('OK', 'ADJ'):
            result = fr.press(self.h, 0x23 if key == 'OK' else 0x2b, steps=30000000)
        else:
            raise ValueError(key)
        assert result.get('ok'), result
        return self.state()

    def goto(self, row):
        for _ in range(70):
            cur = self.ui('cur')
            if cur == row:
                return self.state()
            self.press('DOWN' if cur < row else 'UP')
        raise AssertionError(('row', row, self.state()))

    # ---- unit rows (read through the unit RPC model) ---------------------
    def unit_rows(self):
        dat = DAT_BYTES[self.dat_path]
        directory = int.from_bytes(dat[156:160], 'big') + 64 * UNITS[self.unit]
        mapping = dat[int.from_bytes(dat[directory + 12:directory + 16], 'big'):][:152]
        rows = []
        for i in range(9):
            address = int.from_bytes(mapping[32 + 12 * i:36 + 12 * i], 'big')
            size = int.from_bytes(mapping[36 + 12 * i:38 + 12 * i], 'big')
            rows.append(bytes((self.p.rpc.half(a & ~1) >> (0 if a & 1 else 8)) & 255 for a in range(address, address + size)))
        return rows, self.p.rpc.t

    def writes(self):
        return sum(e['cmd'] == 22 for e in self.p.rpc.log)
