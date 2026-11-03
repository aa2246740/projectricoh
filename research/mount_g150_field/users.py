"""Decode the test package's known user entries with its existing C engine."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze as a
import ctypes as ct
import json


class Levels(ct.Structure):
    _fields_ = [('v', ct.c_int16 * 10)]


def main():
    import build_receipt
    build_receipt.main('after')
    b = a.models()
    dat = (a.ROOT / 'firmware/package_v38_g150_test/local/SD_ROOT/GXRCE.DAT').read_bytes()
    raw = (ct.c_uint8 * len(dat)).from_buffer_copy(dat)
    lib = ct.CDLL(str(a.TMP / 'g150-host.dylib'))
    assert lib.g135_open(raw, len(dat), 2) == 0
    defaults = {}
    for slot in range(1, 9):
        v = Levels()
        assert lib.g135_default(slot, ct.byref(v)) == 0
        out = (ct.c_uint8 * 552)()
        assert lib.g135_compute(slot, ct.byref(v), out) == 0
        defaults[slot] = dict(levels=list(v.v), equal_dat=bytes(out) == b['new']['l08firm']['entries'][slot])
        assert defaults[slot]['equal_dat'], defaults[slot]
    entries = {}
    for name, slot, unit, v in (
        ('FCC-001', 5, 2, [100, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
        ('FCC*002', 5, 2, [100, 1, 0, 0, 0, 0, 0, 0, 0, 0]),
        ('GRN*001', 2, 2, [100, 2, 5, 5, 0, -5, 0, 0, 0, 0]),
        ('GRN*001@50mm', 2, 0, [100, 2, 5, 5, 0, -5, 0, 0, 0, 0]),
    ):
        assert lib.g135_open(raw, len(dat), unit) == 0
        out = (ct.c_uint8 * 552)()
        assert lib.g135_compute(slot, ct.byref(Levels((ct.c_int16 * 10)(*v))), out) == 0
        p = a.HERE / 'users' / (name.replace('*', '_') + '.bin')
        p.parent.mkdir(exist_ok=True)
        p.write_bytes(bytes(out))
        entries[name] = dict(base=slot, levels=v, unit='mount' if unit==2 else '50mm', file=str(p.relative_to(a.HERE)), sha256=a.sha(p))
    a.dump('user_rows.json', dict(default_checks=defaults, entries=entries,
           engine='firmware/engine_v58_g150/candidate/containers/product',
           library_sha256=a.sha(a.TMP / 'g150-host.dylib')))
    print(json.dumps(entries, indent=1))
    a.finish('users')


if __name__ == '__main__': main()
