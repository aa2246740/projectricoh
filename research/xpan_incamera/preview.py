#!/usr/bin/python3 -I -B
"""Evaluate original display arithmetic with the existing GNU M32R library."""
from dataclasses import asdict
import importlib.util
import json
from pathlib import Path
import struct
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


evaluation = load_module('xpan_evaluation', HERE / 'evaluate.py')
gnu = load_module('xpan_gnu', ROOT / 'tools/gxr_emulator/backend.py')


def map_image(cpu, name):
    data = evaluation.readers.read(name)
    flag_slot = evaluation.MAPS[name]['flag_slot']
    pos = 0x20000000
    for f, v, n in sorted(evaluation.readers.sections(data), key=lambda row: row[1]):
        if v < 0x20000000:
            cpu.map(v, data[f:f+n], False)
            continue
        if pos < v:
            cpu.map(pos, bytes(v-pos))
        if v <= flag_slot < v+n:
            part = flag_slot-v
            if part:
                cpu.map(v, data[f:f+part], False)
            cpu.map(flag_slot, data[f+part:f+part+4], True)
            if part+4 < n:
                cpu.map(flag_slot+4, data[f+part+4:f+n], False)
        else:
            cpu.map(v, data[f:f+n], False)
        pos = v+n
    if pos < 0x20800000:
        cpu.map(pos, bytes(0x20800000-pos))


def main():
    rows = []
    for name, sites in evaluation.MAPS.items():
        for flag in (0, 1):
            for aspect in range(4):
                with gnu.Backend() as cpu:
                    map_image(cpu, name)
                    cpu.write(sites['region'], struct.pack('>4H', 0, 639, 0, 479))
                    cpu.write(evaluation.CFG, struct.pack('>2I', aspect, 0))

                    def property_value(c, value=flag):
                        c.set_reg('r0', value)
                        c.set_reg('pc', c.get_reg('lr'))
                        return False

                    if flag == 0:
                        cpu.add_breakpoint(sites['flag'], property_value)
                    writes = []

                    def display_register(address, data):
                        writes.append([address, int.from_bytes(data, 'big')])

                    cpu.add_mmio(0xf0350000, 0xf0350040, None, display_register)
                    cpu.set_reg('r4', evaluation.CFG)
                    cpu.set_reg('sp', evaluation.STACK)
                    status = asdict(cpu.call(sites['preview'], (), evaluation.STOP, 30000))
                    bounds = [evaluation.integer(cpu, sites['display']+i)
                              for i in (20, 24, 28, 32)]
                    expected = [
                        [[0, 639, 0, 479], [0, 639, 26, 453],
                         [0, 639, 60, 419], [80, 559, 0, 479]],
                        [[0, 639, 0, 479], [0, 639, 0, 479],
                         [0, 639, 37, 442], [80, 559, 0, 479]],
                    ][flag][aspect]
                    expected_writes = [[0xf035002c + 2*i, v] for i, v in enumerate(expected)]
                    if status['reason'] != 'return' or bounds != expected or writes != expected_writes:
                        raise AssertionError((name, flag, aspect, status, bounds))
                    rows.append(dict(name=name, native_flag=flag, aspect=aspect,
                                     fixture_bounds=[0, 639, 0, 479], result_bounds=bounds,
                                     state=status, simulated_register_writes=writes,
                                     forced_alternative=flag == 0,
                                     boundaries=(['forced flag'] if flag == 0 else []) +
                                     ['simulated display registers']))
        print(name, 'GNU display cases 8/8')
    evaluation.readers.put(HERE / 'local/preview-gnu.json', json.dumps(rows, indent=2) + '\n')


if __name__ == '__main__':
    main()
