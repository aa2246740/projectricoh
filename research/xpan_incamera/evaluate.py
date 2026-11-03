#!/usr/bin/python3 -I -B
"""Evaluate original geometry functions in the existing host interpreter."""
from dataclasses import asdict
import importlib.util
import json
from pathlib import Path
import struct
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location('xpan_readers', HERE / 'inspect.py')
readers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(readers)
sys.path.insert(0, str(ROOT / 'tools/native_harness'))
import python_backend as native

native.CACHE = HERE / 'local/decode'
STOP = 0x207ff000
CFG = 0x20600000
RESULT = 0x20610000
STACK = 0x20700000

MAPS = {
    'jlaunch3': dict(init=(0x201a2e78, 0x201a2fec), dims=0x2019a9f4,
                     raw=0x2018b61c, bank=0x204392a0, preview=0x201255d0,
                     flag=0x201839d4, flag_slot=0x201844f0, region=0x204a6ed8, submit=0x20254a20,
                     display=0x2038b298),
    'qlaunch3': dict(init=(0x201a62ac, 0x201a6420), dims=0x2019ddf4,
                     raw=0x2018ea1c, bank=0x2043cb68, preview=0x20128214,
                     flag=0x20186dd4, flag_slot=0x201878f0, region=0x204aa7bc, submit=0x20258220,
                     display=0x2038eb60),
    'l08firm3': dict(init=(0x201a26ac, 0x201a2820), dims=0x2019a1f0,
                       raw=0x2018acb0, bank=0x20438f7c, preview=0x2012016c,
                       flag=0x20182dd4, flag_slot=0x201838f0, region=0x204a6b38, submit=0x20253620,
                       display=0x2038af28),
}

EXPECTED = {
    20: ((3776, 2832), (4288, 2848), (4288, 2416), (2848, 2848)),
    19: ((3072, 2304), (3456, 2304), (3456, 1944), (2304, 2304)),
    8: ((2592, 1944), (2592, 1728), (2592, 1456), (1936, 1936)),
    5: ((2048, 1536), (2048, 1368), (2048, 1152), (1536, 1536)),
    2: ((1280, 960), (1280, 856), (1280, 720), (960, 960)),
    1: ((640, 480), (640, 424), (640, 360), (480, 480)),
}


def machine(name):
    cpu = native.PythonBackend()
    cpu.map(0x20000000, bytes(0x800000))
    data = readers.read(name)
    for f, v, n in readers.sections(data):
        cpu.map(v, data[f:f+n], writable=False)
    return cpu


def invoke(cpu, addr, args=(), end=None):
    for i, value in enumerate(args):
        cpu.set_reg('r' + str(4+i), value)
    cpu.set_reg('r15', STACK)
    if end is not None:
        cpu.add_breakpoint(end, lambda _: True)
    state = cpu.call(addr, (), STOP, 30000)
    if state.reason != ('breakpoint' if end is not None else 'return'):
        raise RuntimeError(asdict(state))
    return asdict(state)


def integer(cpu, address, size=4):
    return int.from_bytes(cpu.read(address, size), 'big')


def preview_cases(name, sites):
    rows = []
    for flag in (0, 1):
        for aspect in range(4):
            cpu = machine(name)
            cpu.write(sites['region'], struct.pack('>4H', 0, 639, 0, 479))
            cpu.write(CFG, struct.pack('>2I', aspect, 0))

            def property_value(c, value=flag):
                c.set_reg('r0', value)
                c.pc = c.get_reg('r14')
                return False

            def display_boundary(c):
                c.set_reg('r0', 0)
                c.pc = c.get_reg('r14')
                return False

            cpu.add_breakpoint(sites['flag'], property_value)
            cpu.add_breakpoint(sites['submit'], display_boundary)
            for i, value in enumerate((CFG,)):
                cpu.set_reg('r' + str(4+i), value)
            cpu.set_reg('r15', STACK)
            status = asdict(cpu.call(sites['preview'], (), STOP, 30000))
            bounds = [integer(cpu, sites['display']+i) for i in (20, 24, 28, 32)]
            rows.append(dict(native_flag=flag, aspect=aspect,
                             fixture_bounds=[0, 639, 0, 479], result_bounds=bounds,
                             state=status, boundaries=['forced flag', 'display submission']))
    return rows


def main():
    report = []
    for name, sites in MAPS.items():
        cpu = machine(name)
        invoke(cpu, sites['init'][0], end=sites['init'][1])
        rows = []
        for size, values in EXPECTED.items():
            for aspect, expected in enumerate(values):
                status = invoke(cpu, sites['dims'], (size, aspect, RESULT, RESULT+4))
                actual = (integer(cpu, RESULT), integer(cpu, RESULT+4))
                if actual != expected:
                    raise AssertionError((name, size, aspect, actual, expected))
                rows.append(dict(size=size, aspect=aspect, dimensions=actual,
                                 returned=status['reason']))
        raw_rows = []
        for aspect, (width, height) in enumerate(EXPECTED[20]):
            cpu.write(CFG+540, bytes([aspect]))
            invoke(cpu, sites['raw'], (CFG,))
            actual = [integer(cpu, CFG+i) for i in (544, 548, 552, 556, 560, 564, 568, 572)]
            expected = [[256, 2], [0, 0], [0, 216], [720, 0]][aspect] + [width+16, height+14, 8, 7, width, height]
            if actual != expected:
                raise AssertionError((name, aspect, actual, expected))
            raw_rows.append(dict(aspect=aspect, source_origin=actual[:2],
                                 raw_dimensions=actual[2:4], default_origin=actual[4:6],
                                 default_dimensions=actual[6:]))
        candidate = dict(width=4160, height=1536, x=64, y=656)
        for off, val in ((24, candidate['width']), (28, candidate['height']),
                         (96, candidate['x']), (100, candidate['y'])):
            cpu.write(sites['bank']+off, struct.pack('>I', val))
        invoke(cpu, sites['dims'], (20, 2, RESULT, RESULT+4))
        candidate_dims = [integer(cpu, RESULT), integer(cpu, RESULT+4)]
        assert candidate_dims == [4160, 1536]
        cpu.write(CFG+540, bytes([2]))
        invoke(cpu, sites['raw'], (CFG,))
        candidate_raw = [integer(cpu, CFG+i) for i in (544, 548, 552, 556, 560, 564, 568, 572)]
        assert candidate_raw == [64, 656, 4176, 1550, 8, 7, 4160, 1536]
        previews = preview_cases(name, sites)
        report.append(dict(name=name, geometry=rows, raw=raw_rows,
                           candidate_ram_only=dict(values=candidate,
                                                   dimensions=candidate_dims, raw=candidate_raw),
                           preview=previews))
        print(name, 'dimension cases', len(rows), 'raw cases', len(raw_rows))
        print(name, 'preview returns', sum(x['state']['reason'] == 'return' for x in previews),
              'preview incomplete', sum(x['state']['reason'] != 'return' for x in previews))
    readers.put(readers.LOCAL / 'geometry.json', json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
