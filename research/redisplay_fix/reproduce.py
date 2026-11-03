"""Trace pinned native instructions through half-press and menu redisplay."""
from pathlib import Path
import argparse
import json
import sys
import traceback
sys.path.insert(0, str(Path(__file__).resolve().parent))
from scope import *


def setup(unit):
    freeze()
    tree = ROOT / 'firmware/engine_v48_own'
    sys.path.insert(0, str(tree))
    m = load(tree / 'integration_native.py', 'redisplay_integration')
    v, fr, pe = m.v, m.fr, m.pe
    dat = ROOT / 'firmware/package_v36_g127/SD_ROOT/GXRCE.DAT'
    elf = tree / 'candidate/local/full-r13/engine.elf'
    body = ROOT / 'firmware/package_v36_g120b/SD_ROOT/ilaunch3'
    assert sha(body) == '50720c80696ca88f25dc25a85285acd0e0f19906e1d7da1dd404f6cc243f9008'
    assert sha(dat) == '9100616f24dae04eb43138805336b3eebc3eebcc5b86f14b3e0b30969474ead6'
    m.DAT = dat
    m.OUT = HERE / 'local/runtime' / unit
    pe.STAGED, pe.STAGED_SHA, pe.ENGINE_ELF = dat, sha(dat), elf
    v.python_backend.CACHE = HERE / 'local/decode'
    pe.FileEdge, fr.Product = m.Files, m.Product
    pe.UNITS['mount'] = (ROOT / 'firmware/package_v36_g120b/SD_ROOT/l08firm3',
                        '0a4dff6d3be9b9a9b56dfcbd98a2df59efcb31f7d4eaca6b0c3fbdb1641fde44', 2)
    v.harness_mod.Harness = v.V35Harness
    syms = v.Elf(v.RESIDENT_ELF).symbols
    fr.OBSERVE = syms['rv_hook_observe']
    fr.LAND = {syms['rv_skip_06']: 'h06_skip', syms['rv_close_07']: 'h07_close',
               syms['rv_skip_08']: 'h08_skip', 0x202871dc: 'native_setter',
               0x202bb96c: 'native_h08', 0x20268768: 'native_setter_store',
               0x20268774: 'native_row_store'}
    h, p, w = m.boot(unit)
    original_symbol = p.symbol_pc
    def symbol(name):
        actual = next((n for n in (name, name+'.constprop.0', name+'.lto_priv.0')
                       if n in p.elf.symbols), name)
        return original_symbol(actual)
    p.symbol_pc = symbol
    # Retain native CRC instructions. Only identify the image after rv_load.
    def image_entered(b):
        block = h.u(pe.ROOT_ADDR + 56)
        if block:
            p.image_base = h.u(block + 312)
        return False
    h.b.add_breakpoint(h.symbols['rv_invoke'], image_entered)
    h.stub(0x0500c6ec, 'kernel_context', value=0)
    def task_id(b):
        b.write(b.core.r[4], (6).to_bytes(2, 'big'))
        return 0
    h.stub(0x0500c574, 'kernel_task_id', task_id)
    return m, h, p, w


def snapshot(h):
    count = h.u(0x205a27d4, 1)
    array = h.u(0x205a27d8)
    top = array+8*(count-1) if array == 0x205a279c and 1 <= count <= 2 else None
    return {'part': h.u(0x205a280f, 1), 'count': count, 'array': hex(array),
            'tag': h.u(top, 1) if top else None,
            'state': hex(h.u(top+4)) if top else None,
            'names': hex(h.u(0x2022f5a8)), 'rows': h.u(0x2022f5ac, 1),
            'kind': h.u(0x2022f71c, 1), 'activity': h.u(0x205d9bf8),
            'native_state': hex(h.u(0x205d9c00)), 'overlay': h.u(0x2037f3bc),
            'ui_restore0': hex(h.u(0x20054700+156)),
            'ui_restore6': hex(h.u(0x20054700+180))}


class Trace:
    def __init__(self, h):
        self.h, self.rows, self.stage = h, [], 'open'
        self.layer_stack = []
        h.b.add_breakpoint(h.symbols['rv_hook_observe'], self.hook)
        for pc, name in ((0x20287080, 'Image constructor'), (0x201c092c, 'layer action'),
                         (0x201c0ce0, 'part store'), (0x201c07e0, 'view push'),
                         (0x201c06f4, 'view clear'), (0x201d82fc, 'render dispatch'),
                         (0x202871c4, 'after layer action')):
            h.b.add_breakpoint(pc, lambda b, pc=pc, name=name: self.enter(b, pc, name))
        h.b.add_write_trace(0x205a280f, 0x205a2810, self.part_write)

    def record(self, name, **extra):
        row = {'sequence': len(self.rows), 'stage': self.stage, 'event': name,
               **snapshot(self.h), **extra}
        self.rows.append(row)
        print(json.dumps(row), flush=True)
        save('local/reproduction-events.json', self.rows)

    def hook(self, b):
        self.record('hook', hook=b.get_reg('r1'))
        return False

    def enter(self, b, pc, name):
        self.record(name, pc=hex(pc), lr=hex(b.get_reg('r14')),
                    args=[hex(b.get_reg('r'+str(i))) for i in range(4, 8)])
        return False

    def part_write(self, e):
        self.record('part written', writer_pc=hex(e.pc) if e.pc else None,
                    value=e.value, origin=e.origin)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--unit', default='50mm')
    args = parser.parse_args()
    m, h, p, w = setup(args.unit)
    t = Trace(h)
    results = []
    def run(stage, address=None, arguments=()):
        t.stage = stage
        result = m.fr.native(h, address, arguments, steps=30000000) if address else None
        results.append({'stage': stage, 'result': result, 'after': snapshot(h)})
        save('local/reproduction-actions.json', results)
        print('ACTION', stage, json.dumps(results[-1]), flush=True)
        assert result is None or result.get('ok'), result
    try:
        h.parent()
        run('open', 0x20287080)
        assert snapshot(h)['rows'] == 8, snapshot(h)
        h.select_item_8()
        run('half global', 0x2029fdc4, (0x29, 0))
        run('half ADJ', 0x202bd724, (0x29, 0))
        # Shooting layer show: 0x201C092C(part=1, action=0) stores part 1.
        # The hidden part-2 view is left in place. Then the image constructor
        # runs again, which is the redisplay the field sees after focus.
        run('shoot layer', 0x201c092c, (1, 0, 0))
        run('redisplay', 0x20287080)
        # Case 2: a real close (OK on the list task) then the same shooting
        # part, then the constructor. press() is the native key dispatcher.
        run('ok close', 0x202c2abc, (0x23,))
        run('shoot after close', 0x201c092c, (1, 0, 0))
        run('open after shot', 0x20287080)
        save('local/reproduction-initial.json', {'actions': results, 'hooks': w.rows,
                                                'native_calls': h.calls,
                                                'file_mutations': m.no_writes(p)})
    except BaseException:
        save('local/reproduction-failure.json', {'actions': results, 'events': t.rows,
                                                 'traceback': traceback.format_exc()})
        raise


if __name__ == '__main__':
    main()
