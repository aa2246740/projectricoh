#!/usr/bin/python3 -I -B
"""Evaluate output parameters and the separate YUV window calculation."""
import importlib.util
import json
from pathlib import Path
import struct

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('xpan_capture_eval', HERE / 'evaluate.py')
evaluation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluation)

SITES = {
    'jlaunch3': dict(output=0x2019fc5c, rectangle=0x2018646c, fill=0x20121074),
    'qlaunch3': dict(output=0x201a3090, rectangle=0x2018986c, fill=0x20123cb8),
    'l08firm3': dict(output=0x2019f490, rectangle=0x20185aec, fill=0x2011bc10),
}


def main():
    rows = []
    for name, sites in SITES.items():
        layout = evaluation.MAPS[name]
        for changed in (False, True):
            for size in (20, 19):
                cpu = evaluation.machine(name)
                evaluation.invoke(cpu, layout['init'][0], end=layout['init'][1])
                cpu.write(layout['bank']+108, bytes([2]))
                cpu.write(evaluation.CFG+5, bytes([size, 2]))
                if changed:
                    for off, value in ((24, 4160), (28, 1536), (96, 64), (100, 656),
                                       (56, 3120), (60, 1152)):
                        cpu.write(layout['bank']+off, struct.pack('>I', value))
                output_state = evaluation.invoke(cpu, sites['output'], (evaluation.CFG,))
                parameters = [evaluation.integer(cpu, evaluation.CFG+off, 2)
                              for off in (352, 354, 356, 374, 376, 386, 388, 402, 404)]
                expected = ((4160, 1536) if size == 20 else (3120, 1152)) if changed else (
                    (4288, 2416) if size == 20 else (3456, 1944))
                assert parameters[:3] == [expected[0]*2, *expected]
                assert parameters[3:] == [640, 480, 160, 120, 640, 480]
                picture = 0x20480000
                source_w, source_h = (4288, 2848) if size == 20 else (3456, 2304)
                stride = source_w*2
                cpu.write(evaluation.CFG+344, struct.pack('>I', picture))
                cpu.write(evaluation.CFG+352, struct.pack('>3H', stride, source_w, source_h))
                calls = []

                def rectangle_fill(c):
                    sp = c.get_reg('r15')
                    args = [c.get_reg('r'+str(i)) for i in range(4, 8)]
                    args += [evaluation.integer(c, sp+i) for i in (0, 4, 8)]
                    calls.append(args)
                    c.set_reg('r0', 0)
                    c.pc = c.get_reg('r14')
                    return False

                cpu.add_breakpoint(sites['fill'], rectangle_fill)
                rectangle_state = evaluation.invoke(cpu, sites['rectangle'], (evaluation.CFG,))
                shifted = evaluation.integer(cpu, evaluation.CFG+344)
                vertical = (source_h-expected[1])//2
                assert shifted-picture == stride*vertical
                assert len(calls) == 2
                rows.append(dict(name=name, size=size, changed_ram_only=changed,
                                 output_parameters=parameters, output_state=output_state,
                                 fixture_source=[picture, stride, source_w, source_h],
                                 pointer_delta=shifted-picture, vertical_rows=vertical,
                                 rectangle_state=rectangle_state, fill_calls=calls,
                                 boundaries=['zeroed configuration fields except size and aspect',
                                             'chosen full-width source fixture',
                                             'rectangle fill recorded without pixel writes']))
        print(name, 'output and YUV geometry cases 4/4')
    evaluation.readers.put(HERE / 'local/capture.json', json.dumps(rows, indent=2)+'\n')


if __name__ == '__main__':
    main()
