"""Host observation: what the stock Image list does with the cursor cache 0x205A2944 on open and close, compared
with the gen 148 list. Writes local/cache-native-probe.json. Run like accept_cpuprobe.py."""
import json
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import accept_cpuprobe as cp
from scope import save

CACHE = 0x205A2944


def main():
    s = cp.Session('50mm')
    s.h.b.set_reg('psw', s.h.b.get_reg('psw') | 0x40)
    writes, phase = [], ['setup']
    s.h.b.add_write_trace(CACHE, CACHE + 1, lambda e: writes.append(
        (phase[0], e.data.hex(), hex(e.pc) if e.pc is not None else None)))
    out = []

    def run(label, a, b, cache, key=0x23):
        s.h.b.write(cp.CUR_A, bytes([a])); s.h.b.write(cp.CUR_B, bytes([b])); s.h.b.write(CACHE, bytes([cache]))
        phase[0] = label + ':open'
        o = s.open()
        at_open = dict(rows=o['rows'], a=s.h.u(cp.CUR_A, 1), b=s.h.u(cp.CUR_B, 1), cache=s.h.u(CACHE, 1),
                       state=hex(s.h.u(0x205a293c)))
        phase[0] = label + ':close'
        s.press(key)
        row = dict(label=label, before=(a, b, cache), open=at_open,
                   after=dict(a=s.h.u(cp.CUR_A, 1), b=s.h.u(cp.CUR_B, 1), cache=s.h.u(CACHE, 1),
                              state=hex(s.h.u(0x205a293c))))
        out.append(row)
        print(json.dumps(row), flush=True)
    run('ours 7/7 cache 7', 7, 7, 7)
    run('ours 7/7 cache 3', 7, 7, 3)
    run('stock (refused 0/5) cache 3', 0, 5, 3)
    run('stock (refused 8/4) cache 6', 8, 4, 6)
    save(HERE / 'local/cache-native-probe.json', dict(cases=out, writes=writes))
    for w in sorted(set(writes)):
        print(w)


if __name__ == '__main__':
    main()
