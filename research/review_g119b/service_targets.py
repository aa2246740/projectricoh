"""Real M32R dispatcher differential cases beyond the author's early guards.

All machine bodies execute. Only named external/callee contracts are stubbed,
as in the accepted gen117 function proof. These are direct-function fixtures,
not native UI or device evidence. Both generations receive identical mutations.
"""
from pathlib import Path
import collections
import itertools
import json
import random
import struct
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import misc_diff as m
from common import OUT, save, sha

d = m.d
R, S, D, Q, P, B, UI = m.R, m.S, m.D, m.Q, m.REPLY, m.BUF, m.UI
VIEW = 0x205a279c


def replace(p, name, cb):
    for r in p.rs:
        for n, symbol in r.e.symbols.items():
            if n == name or n.startswith(name + '.constprop.') or n.startswith(name + '.lto_priv.'):
                r.b.breakpoints.pop(d.BASE + symbol['address'], None)
    m.hook(p, name, cb)


def setup(p):
    m.setup(p, 'rv_call')
    p.service_counts = {118: collections.Counter(), 119: collections.Counter()}

    def value(name, default):
        def cb(b, r):
            index = p.service_counts[r.g][name]
            p.service_counts[r.g][name] += 1
            seq = p.mode.get('returns', {}).get(name, [default])
            return seq[min(index, len(seq) - 1)] & 0xffffffff
        return cb

    for name, default in [('identity', 1), ('current', 1), ('es_range', 1),
                          ('es_ui_capture', 1), ('ui_seed', 1),
                          ('rv_native_context', 0), ('rv_native_rpc_ready', 1),
                          ('rv_native_rpc_limit', 16), ('rv_native_preview', 0),
                          ('rv_native_layer', 0), ('rv_native_close', 0),
                          ('rv_native_open', 3), ('rv_native_create', 3),
                          ('rv_native_rename', 0), ('rv_native_delete', 0),
                          ('rv_native_language', 0)]:
        replace(p, name, value(name, default))

    # A range callee cannot admit a null/overflow/unmapped buffer. Keep its
    # explicit failure schedule, while honoring this real boundary contract.
    range_result=value('es_range',1)
    def checked_range(b,r):
        result=range_result(b,r)
        at,size=b.core.r[1:3]
        if not at or size>0x30000 or at+size>0xffffffff:
            return 0
        try:
            if size:b.read(at,size)
        except (RuntimeError,ValueError,d.ex.pb.Fault):
            return 0
        return result
    replace(p,'es_range',checked_range)

    def rpc(b, r):
        return p.mode.get('rpc_result', b.core.r[1]) & 0xffffffff
    replace(p, 'rv_rpc8_native', rpc)

    def read(b, r):
        amount = p.mode.get('file_result', b.core.r[2])
        if 0 < amount <= b.core.r[2]:
            b.write(b.core.r[1], bytes([0x59]) * amount)
        return amount & 0xffffffff
    replace(p, 'rv_native_read', read)
    replace(p, 'rv_native_write', lambda b, r: p.mode.get('file_result', b.core.r[2]) & 0xffffffff)

    def sd(b, r):
        b.write(b.core.r[0], p.mode.get('sd_bytes', b'\x11' * 16))
        return p.mode.get('sd_result', 0) & 0xffffffff
    replace(p, 'rv_native_sd_id', sd)


def base(p, sid, op, index):
    m.seed(p, random.Random(index), index, True)
    p.mode.update(returns={}, file_result=1, sd_result=0, sd_bytes=b'\x11' * 16)
    p.mode.pop('rpc_result', None)
    a = [0x77, 0x77, 1, 2, 3, 4, 7, 8, 0, 0, 0, 0, 0, 0]
    size = 0
    data = bytearray()
    if sid == 1:
        a = [0] * 14
        if op != 1:
            a[0] = 12
            if op in (4, 5, 6):
                a[1] = 0x99
                if op != 6:
                    a[6], a[7] = D + 0x13000, 1
            else:
                a[2], a[5] = 1, 1 if op == 2 else 4
                if op == 3:
                    a[8] = 64
                if op == 7:
                    a[9], a[10] = 2, 3
                if op in (8, 9):
                    a[5] = 4
    elif sid == 2:
        if op == 1:
            size = 32
            a[8:10] = [1460, 4]
        elif op == 2:
            a[1] = 0x88
        else:
            size = 32
            a[8] = 0x88
    elif sid == 3:
        size = 4
    elif sid == 4:
        a[8] = 0x1234 if op in (2, 3, 4) else 0
        if op != 1:
            a[1] = 0x88
    elif sid == 6:
        size = 24 if op == 1 else 80 if op == 2 else 0
        if op == 2:
            data = bytearray(80)
            struct.pack_into('>II', data, 8, 0x88, 3)
            for j, (off, val) in enumerate(((0x6dd, 10), (0x6de, 10), (0x36e, 1))):
                struct.pack_into('>HBB', data, 16 + 4*j, off, val, 0)
    elif sid == 7:
        size = 36
    elif sid == 8:
        size = 16
    elif sid == 9:
        if op == 12:
            size = 60
    elif sid == 10:
        size = 40
        a[9] = a[12] = 8
        data = bytearray(struct.pack('>HHI8I', 1, size, 0, D+0x7000, 32, 8, 3,
                                     D+0x9000, D+0x8000, 0x77, 7))
        if op == 4:
            a[9] = a[12] = 0
    elif sid == 11:
        if op == 1:
            size = 40
            data = bytearray(struct.pack('>HHI8I', 1, size, 0, D+0xb000, 1,
                                         0x77, D+0xb100, 32, 0x77, 0, 0))
    elif sid == 12:
        size = 48
        data = bytearray(struct.pack('>HHI10I', 1, size, 0, 2, 33, D+0x7000,
                                     32, 0x77, 7, VIEW, 1, 33, D+0x7000))
    elif sid == 13:
        if op == 1:
            size = 72
    elif sid == 14:
        if op == 2:
            a[8:10] = [1, 2]
        else:
            size = 72
    elif sid == 15:
        size = 16
    elif sid == 16:
        size = 4
    if size:
        if not data:
            data = bytearray(size)
        if sid not in (3, 8, 16):
            struct.pack_into('>HHI', data, 0, 1, size, 0)
        a[10], a[11] = B, size
    for r in p.rs:
        p.service_counts[r.g].clear()
        r.write(B, data or bytes(128))
        r.write(Q, struct.pack('>HHI14I', 1, 64, 0, *a))
        r.w32(0x200c0dac, D+0x14000)
        r.w32(0x200c0db0, 4096)
        r.write(D+0x14000, bytes([1])*4096)
        r.w32(S+368, D+0x14000)
        r.w32(S+372, 4096)
        r.w32(S+376, 8)
        r.w32(S+380, 0x88)
        r.w32(S+384, 0 if sid == 4 and op == 1 else 0x88 if sid == 4 else 0)
        r.w32(S+388, 0)
        r.write(S+180, struct.pack('>5I', 0x88, ~0x88 & 0xffffffff, UI, 1460, 4))
        r.write(S+280, struct.pack('>4I', 0x99, 3, 12, int(op == 5)))
        r.w32(S+496, 0)
        r.w32(S+504, 73728)
        r.w32(S+512, 0x01000001)
        r.w32(S+520, 0)
        r.w32(S+484, D+0x7000)
        r.w32(R+136, UI)
        r.w32(R+140, ~UI)
        r.w32(R+144, 1980)
        r.w32(R+156, 1)
        r.w32(0x205a27d8, VIEW)
        r.write(0x205a27d4, b'\1')
        r.write(0x205a280f, b'\2')
        r.w32(0x205d9bf8, 8)
        r.w32(VIEW, 33 << 24)
        r.w32(VIEW+4, D+0x7000)
        for j in range(8):
            r.w32(D+0x9000+4*j, D+0xa000+4*j)
            r.w32(D+0xa000+4*j, D+0xb000+96*j)
            r.write(D+0xb000+96*j, b'A\0')
        r.write(D+0x7000, b'\x05'+bytes(31))
        r.write(D+0xb000, b'A\0')
        r.write(D+0xb100, bytes(256))
    return [sid, op, Q, P]


def execute(p, args, label, index, rows, seen):
    results = []
    for r in p.rs:
        r.reset(0x119e0000 + index)
        results.append(r.call('rv_call', args, steps=250000))
    a, b = results
    pa, pb = [p.projection(r, x) for r, x in zip(p.rs, results)]
    ok = (a['stop']['reason'] == b['stop']['reason'] == 'return' and
          a['result'] == b['result'] and a['saved'] == b['saved'] and
          a['abi_ok'] and b['abi_ok'] and pa == pb)
    row = dict(index=index, label=label, args=args, ok=ok,
               results=[a['result'], b['result']], stops=[a['stop'], b['stop']],
               edges={r.g: x['edges'] for r, x in zip(p.rs, results)})
    rows.append(row)
    if not ok:
        save('service-target-failure.json', dict(row=row, old=a, new=b,
                                               old_projection=pa, new_projection=pb))
        raise AssertionError((label, a['result'], b['result'], a['stop'], b['stop']))
    for r, x in zip(p.rs, results):
        seen[r.g].update(map(tuple, x['edges']))


def main():
    p = d.Pair()
    setup(p)
    rows, seen = [], {118: set(), 119: set()}
    cases = [(1, x) for x in range(1, 10)]
    cases += [(2, x) for x in (1, 2, 3)] + [(3, 1)]
    cases += [(4, x) for x in range(1, 6)] + [(5, 1)]
    cases += [(6, x) for x in (1, 2, 3)] + [(7, 1), (8, 1)]
    cases += [(9, x) for x in range(14)]
    cases += [(10, x) for x in (1, 2, 3, 4)]
    cases += [(11, x) for x in (1, 2)] + [(12, x) for x in (1, 2, 3)]
    cases += [(13, x) for x in (0, 1, 2, 3)] + [(14, 1), (14, 2), (15, 1), (16, 1)]
    start = time.monotonic()

    def run(sid, op, mutation=None, label='base'):
        args = base(p, sid, op, len(rows))
        if mutation:
            mutation(p, args)
        execute(p, args, [sid, op, label], len(rows), rows, seen)

    for sid, op in cases:
        run(sid, op)
        # All request wire fields; mutations remain mapped and aligned.
        for off in (0, 4, *range(8, 64, 4)):
            vals = (0, 1, 0xffffffff) if off != 0 else (0, 0x0001003f, 0x00020040)
            for value in vals:
                run(sid, op, lambda p, a, off=off, v=value:
                    [r.w32(Q+off, v) for r in p.rs], 'q+'+str(off)+'='+str(value))
        for off, values in [(R+5, (0, 3, 6)), (R+6, (0, 1, 2)),
                            (R+212, (0, 2, 16, 32, 64, 128, 0xffffffff)),
                            (S+340, (0x7fff, 0xe7fff, 0xf7fff))]:
            for value in values:
                def mutate(p, args, off=off, value=value):
                    for r in p.rs:
                        if off in (R+5, R+6):
                            r.write(off, bytes([value]))
                        else:
                            r.w32(off, value)
                run(sid, op, mutate, 'state:'+hex(off)+'='+str(value))
        for name in ('identity', 'current', 'es_range', 'es_ui_capture', 'ui_seed'):
            for seq in ([0], [1, 0], [1, 1, 0]):
                run(sid, op, lambda p, a, name=name, seq=seq:
                    p.mode['returns'].update({name: seq}), name+'='+str(seq))
        if sid not in (1, 4, 5, 9):
            for off in (0, 4, 8, 12, 16, 20, 24, 28, 32, 36):
                for value in (0, 1, 16, 255, 0xffffffff):
                    run(sid, op, lambda p, a, off=off, value=value:
                        [r.w32(B+off, value) for r in p.rs], 'buffer+'+str(off)+'='+str(value))
        if len(rows) % 100 < 100:
            print('service targets', sid, op, 'cases', len(rows),
                  'seconds', round(time.monotonic()-start, 1), flush=True)
    coverage = {}
    for r in p.rs:
        pcs = {x['pc'] for x in d.cg.atoms(r.g, 'rv_call')[0]
               if x['asm'].split(' ')[0] in d.ex.COND}
        edges = {(pc, t) for pc, t in seen[r.g] if pc in pcs}
        coverage[r.g] = dict(outcomes=len(edges), possible=2*len(pcs),
                             uncovered=[dict(pc=hex(pc), taken=t)
                                        for pc in sorted(pcs) for t in (False, True)
                                        if (pc, t) not in edges])
    save('service-targets.json', dict(status='PASS', cases=rows, coverage=coverage,
        artifacts={r.g: dict(elf=sha(r.e.raw), dat=sha(r.original)) for r in p.rs},
        common_boundaries='Named callee contracts; no replacement of rv_call or handler bodies.',
        seconds=time.monotonic()-start))
    print('PASS dispatcher differential', len(rows), 'pairs', coverage, flush=True)


if __name__ == '__main__':
    main()
