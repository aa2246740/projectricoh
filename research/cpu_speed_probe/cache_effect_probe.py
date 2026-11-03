"""Host observation for the product question (REPORT §11): run the stock Image-list event handler 0x201CA4A0 on the
real body code with a cursor cache left over from an 8-row list, after a normal close (cursor restored by the
resident). Event codes from the handler table 0x202217A8: 0x13, 0x14, 0x1D, 0x1E, 0x32. Each case starts from a
fresh copy of the same state. Records the cursor 0x2022F726, the dot 0x2022F725, the cache and S+0x36E. Writes
local/cache-effect-probe.json. Fixture values: the cache residue (1..8) and the restored cursor; nothing else."""
import json
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import accept_cpuprobe as cp
from scope import save

CACHE = 0x205A2944
HANDLER = 0x201CA4A0


def main():
    s = cp.Session('50mm')
    s.h.b.set_reg('psw', s.h.b.get_reg('psw') | 0x40)
    s.h.b.write(cp.CUR_A, bytes([7])); s.h.b.write(cp.CUR_B, bytes([7])); s.h.b.write(CACHE, bytes([7]))
    s.open()
    s.press(0x23)
    base = dict(state=hex(s.h.u(0x205a293c)), count=s.h.u(s.h.u(0x205a2940), 1) if s.h.u(0x205a2940) else None,
                cursor=s.h.u(cp.CUR_B, 1), mode=s.s_mode())
    print('BASE', json.dumps(base), flush=True)
    snapshot = {a: bytes(s.h.b.read(a, n)) for a, n in ((0x2022f700, 0x100), (0x205a2700, 0x300),
                                                         (s.s_base, 0x1000), (0x20229a60, 0x10))}
    rows = []
    for event in (0x1e, 0x1d, 0x14, 0x13, 0x32):
        for residue in (1, 7, 8):
            for a, data in snapshot.items():
                s.h.b.write(a, data)
            s.h.b.write(CACHE, bytes([residue]))
            done = s.fr.native(s.h, HANDLER, (event,), steps=20000000)
            row = dict(event=hex(event), residue=residue, ok=done.get('ok'), reason=done.get('reason'),
                       cursor=s.h.u(cp.CUR_B, 1), dot=s.h.u(cp.CUR_A, 1), cache=s.h.u(CACHE, 1), mode=s.s_mode())
            rows.append(row)
            print('EVENT', json.dumps(row), flush=True)
    for a, data in snapshot.items():
        s.h.b.write(a, data)
    save(HERE / 'local/cache-effect-probe.json', dict(base=base, cases=rows))


if __name__ == '__main__':
    main()
