#!/usr/bin/python3
"""Execute original return continuations with literal encoder result values."""
import hashlib
import json
from pathlib import Path
import signal
import struct
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0,str(ROOT/'tools/gxr_emulator_batch'))
from backend import Backend
from image import Image


def main():
    signal.alarm(240)
    rows = []
    cases = [
        ('local-success',0x2015f9dc,0,0x2015f9e4),
        ('local-negative',0x2015f9dc,0xffffffff,0x20051000),
        ('outer-558a8-negative',0x201558a8,0xffffffff,0x20155a5c),
        ('outer-eaa4-negative',0x2015eaa4,0xffffffff,0x2015edb0),
        ('outer-55428-negative',0x20155428,0xffffffff,0x2015f584),
        ('outer-55478-negative',0x20155478,0xffffffff,0x2015f584),
        ('outer-e9b0-negative',0x2015e9b0,0xffffffff,0x2015f584),
    ]
    for name,pc,value,target in cases:
        cpu = Backend(trace_limit=128)
        try:
            image = Image('official')
            image.load(cpu)
            cpu.set_mode('fast')
            cpu.set_batch(True)
            cpu.set_reg('psw',0x80)
            cpu.set_reg('spu',0x20440000)
            cpu.set_reg('r15',0x20440000)
            cpu.set_reg('lr',0x20051000)
            cpu.set_reg('r0',value)
            cpu.set_reg('r8',0x20480000)
            cpu.set_reg('r9',0x20480000)
            frame = [0x13131313,0x20051000,0x12121212,0x11111111,
                     0x10101010,0x09090909,0x08080808]
            cpu.write(0x20440000,struct.pack('>7I',*frame))
            cpu.set_reg('pc',pc)
            cpu.add_breakpoint(target,lambda current:True)
            result = cpu.run(64)
            assert cpu.get_reg('pc') == target,(name,result.to_dict())
            if name == 'local-negative':
                assert cpu.get_reg('r0') == 0xffffffff
                assert cpu.get_reg('r15') == 0x2044001c
            rows.append(dict(name=name,start=hex(pc),input_result=hex(value),
                             reached=hex(target),steps=cpu.steps,
                             result_register=hex(cpu.get_reg('r0')),
                             sp=hex(cpu.get_reg('r15')),stop=result.reason))
        finally:
            cpu.close()
    target = HERE/'local/return-path-results.json'
    target.write_text(json.dumps(dict(
        classification='original_machine_code_continuation_replay',
        image_sha256=image.sha256,
        library_sha256=hashlib.sha256((ROOT/'tools/gxr_emulator_batch/build/libgxr_m32r.dylib').read_bytes()).hexdigest(),
        cases=rows,
        limitations=['Starts at the original call return continuation with a supplied return value.',
                     'No v39 bridge, encoder hardware, file save or RAW cleanup was executed.'],
    ),ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(cases=len(rows),status='PASS_SCOPED_MACHINE_CODE',output=str(target.relative_to(ROOT)))))
    signal.alarm(0)


if __name__=='__main__':
    main()
