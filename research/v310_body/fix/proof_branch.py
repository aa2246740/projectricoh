#!/usr/bin/python3
"""Continue a saved native branch with the C or Python instruction backend."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import pickle
import sys
import zlib

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
TEMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/v310-body-pack-r1')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--name',required=True)
    p.add_argument('--stop',type=lambda x:int(x,0),required=True)
    a=p.parse_args()
    assert a.input.resolve().is_relative_to(HERE/'local')
    assert Path(os.environ['TMPDIR']).resolve()==TEMP
    assert os.getpriority(os.PRIO_PROCESS,0)>=10
    sys.path.insert(0,str(ROOT/'tools/native_harness_c'))
    import python_backend as PB
    PB.CACHE=TEMP/'proof-branch'/a.name
    raw=a.input.read_bytes();state=pickle.loads(zlib.decompress(raw))['cpu']
    b=PB.PythonBackend()
    for at,data,writable in state['regions']:b.map(at,data,writable)
    regs=state['registers']
    b.set_reg('psw',regs['psw'])
    for i in range(16):b.set_reg('r'+str(i),regs['r'+str(i)])
    b.set_reg('acc',(regs['acch']<<32)|regs['accl'])
    # Backend.call uses a return sentinel; restore the captured LR before any instruction.
    b.add_breakpoint(regs['pc'],lambda cpu:cpu.set_reg('r14',regs['r14']) or False)
    b.add_breakpoint(a.stop,lambda cpu:True)
    stop=b.call(regs['pc'],[],0x7ffffff0,100)
    result=dict(layer='saved native branch replay',backend=os.environ['GXR_HARNESS_BACKEND'],
        input_sha256=hashlib.sha256(raw).hexdigest(),cold_step=state['steps'],
        native_state_presets=[],start_pc=hex(regs['pc']),stop_pc=hex(stop.pc),
        stop_reason=stop.reason,steps=stop.steps,r0=b.get_reg('r0'),
        signed_r0=(b.get_reg('r0')+2**31)%2**32-2**31,
        scope='Only the captured return branch; not the preceding file read or a full recovery')
    (HERE/'evidence'/f'{a.name}.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
    assert stop.reason=='breakpoint' and stop.pc==a.stop


if __name__=='__main__':main()
