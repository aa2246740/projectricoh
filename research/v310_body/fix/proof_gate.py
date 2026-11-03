#!/usr/bin/python3
"""Replay a pure qualification function from its actual cold-call input."""
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
ROOT=HERE.parents[2]
TEMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/v310-body-pack-r1')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--name',required=True)
    a=p.parse_args()
    assert a.input.resolve().is_relative_to(HERE/'local')
    assert os.getpriority(os.PRIO_PROCESS,0)>=10
    assert Path(os.environ['TMPDIR']).resolve()==TEMP
    sys.path.insert(0,str(ROOT/'tools/native_harness_c'))
    import python_backend as PB
    PB.CACHE=TEMP/'proof-decode'/a.name
    state=pickle.loads(zlib.decompress(a.input.read_bytes()))
    b=PB.PythonBackend()
    for at,data,writable in state['regions']:b.map(at,data,writable)
    b.set_reg('psw',state['registers']['psw'])
    for key,value in state['registers'].items():
        if key not in ('psw','pc'):b.set_reg(key,value)
    signal.alarm(900)
    try:
        stop=b.call(state['expected_function'],[],state['registers']['r15'],200000)
        result=dict(backend=os.environ['GXR_HARNESS_BACKEND'],
            input_sha256=hashlib.sha256(a.input.read_bytes()).hexdigest(),
            cold_step=state['cold_step'],native_state_presets=[],gate=state['gate'],
            function=hex(state['expected_function']),stop=dict(reason=stop.reason,steps=stop.steps),
            result=b.get_reg('r0'))
        (HERE/'evidence'/f'{a.name}.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result))
        assert stop.reason=='return'
    finally:signal.alarm(0)


if __name__=='__main__':main()
