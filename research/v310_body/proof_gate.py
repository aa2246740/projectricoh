#!/usr/bin/python3
"""Re-run a pure BOOT check from unmodified RAM captured during actual cold execution."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import pickle
import signal
import sys
import zlib

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
TEMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/v310-body-pack-r1')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--name',required=True)
    a=p.parse_args()
    assert a.input.resolve().is_relative_to(HERE/'local')
    assert Path(os.environ['TMPDIR']).resolve()==TEMP
    assert os.getpriority(os.PRIO_PROCESS,0)>=10
    sys.path.insert(0,str(ROOT/'tools/native_harness_c'))
    import python_backend as PB
    PB.CACHE=TEMP/'gate-proof-decode'/a.name
    state=pickle.loads(zlib.decompress(a.input.read_bytes()))
    b=PB.PythonBackend()
    for at,data,writable in state['regions']:b.map(at,data,writable)
    b.set_reg('psw',state['registers']['psw'])
    for key,value in state['registers'].items():
        if key not in ('psw','pc'):b.set_reg(key,value)
    observed=[]
    base=state['expected_function']-0x5eb8
    for offset in (0x5fec,0x5ff0,0x5ef4):
        def trace(current,offset=offset):
            observed.append(dict(offset=hex(offset),r4=hex(current.get_reg('r4')),
                activity=int.from_bytes(current.read(0x205d9bf8,4),'big')))
            return False
        b.add_breakpoint(base+offset,trace)
    signal.alarm(300)
    try:
        stop=b.call(state['expected_function'],[],0x20fff000,100000)
        result=dict(backend=os.environ['GXR_HARNESS_BACKEND'],input_sha256=hashlib.sha256(a.input.read_bytes()).hexdigest(),
            cold_step=state['cold_step'],native_state_changes=[],function=hex(state['expected_function']),
            stop=dict(reason=stop.reason,pc=stop.pc,steps=stop.steps,detail=stop.detail),
            result=b.get_reg('r0'),gate=state['gate'],observed=observed)
        (HERE/'evidence'/f'{a.name}.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result))
        if stop.reason!='return':raise SystemExit(1)
    finally:signal.alarm(0)


if __name__=='__main__':main()
