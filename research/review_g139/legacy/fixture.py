"""(Copy of research/g138_persist/fixture.py.) Normal-boot fixture binding for reused g137 suites run against gen 138.

The shared host model maps S as 4096 bytes of 0x01 (WB 1/1, Start Settings
source 1, S+0xE 0x0101) and leaves the stock parameter lock at 0/0. On the
camera the lock is initialised to count -1 / semaphore 55 at boot, and a
normal boot reads S as Standard, WB 9/9, Body source, extension 0xD24 with a
zero tail. Gen 138 depends on both (lock protocol for every S write; restore
eligibility), so each booted model is bound to that normal state right after
field_replay.boot. Nothing else in the model changes.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
LOCK = 0x204104f0
NORMAL = ((0x36e, b'\x01'), (0x6dd, b'\x09\x09'), (8, b'\x00'), (0xe, b'\x0d\x24'), (0xfd4, bytes(40)))


def apply(h):
    s = h.u(0x200c0dac)
    for offset, data in NORMAL:
        h.b.write(s + offset, data)
    h.b.write(LOCK, (0xffffffff).to_bytes(4, 'big') + (55).to_bytes(4, 'big'))


def install():
    path = str(ROOT / 'tools/native_harness')
    if path not in sys.path:
        sys.path.insert(0, path)
    import field_replay
    if getattr(field_replay.boot, 'g138_normal', False):
        return field_replay
    original = field_replay.boot

    def boot(*args, **kwargs):
        h, product, watch = original(*args, **kwargs)
        apply(h)
        return h, product, watch
    boot.g138_normal = True
    field_replay.boot = boot
    return field_replay
