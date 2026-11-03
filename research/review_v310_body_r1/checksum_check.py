#!/usr/bin/python3
"""Execute the official checksum routine over every candidate MAIN data byte."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
TEMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-v310-body-r1')


def sha(raw):return hashlib.sha256(raw).hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--backend',choices=('c','python'),required=True);a=p.parse_args()
    assert os.getpriority(os.PRIO_PROCESS,0)>=10
    os.environ['GXR_HARNESS_BACKEND']=a.backend
    sys.path.insert(0,str(ROOT/'tools/native_harness_c'))
    import python_backend as PB
    PB.CACHE=TEMP/'checksum-decode'/a.backend
    target=HERE/'evidence'/('candidate-checksum-'+a.backend+'.json');assert not target.exists()
    official=(ROOT/'artifacts/firmware/gxr-1.51/ilaunch3').read_bytes()
    candidate=(ROOT/'firmware/image_v310/local/ilaunch3').read_bytes()
    b=PB.PythonBackend()
    for i in range(16):
        pos,at,n,_,_=struct.unpack_from('>5I',official,32+20*i)
        if n:b.map(at,official[512+pos:512+pos+n],True)
    b.map(0x27000000,candidate[512:],False)
    b.map(0x27f00000,bytes(65536),True)
    b.set_reg('psw',0);b.set_reg('r15',0x27f0ff00)
    b.set_reg('r4',0x27000000);b.set_reg('r5',0);b.set_reg('r6',len(candidate)-512)
    began=time.monotonic()
    stop=b.call(0x20087af0,[],0x7ffffff0,100000000)
    actual=b.get_reg('r0');expected=int.from_bytes(candidate[0x16c:0x170],'big')
    result=dict(status='ERROR',backend=a.backend,official_MAIN_sha256=sha(official),
        candidate_sha256=sha(candidate),data_bytes=len(candidate)-512,
        routine='0x20087af0',calculated=actual,declared=expected,stop=stop.reason,
        steps=stop.steps,seconds=time.monotonic()-began,comparison_branches=[],
        scope='Official checksum routine and updater comparison branch; no file-service or NAND completion claimed')
    try:
        assert stop.reason=='return' and actual==expected
        b.add_breakpoint(0x2008d28c,lambda cpu:True)
        for value,wanted in ((expected,0),(expected^1,0xffffffff)):
            b.set_reg('r13',actual);b.set_reg('r12',value)
            branch=b.call(0x2008d280,[],0x7ffffff0,100)
            assert branch.reason=='breakpoint' and b.get_reg('r0')==wanted
            result['comparison_branches'].append(dict(expected_checksum=value,
                actual_checksum=actual,native_result=wanted,steps=branch.steps))
        result['status']='PASS'
    finally:
        target.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps({k:result[k] for k in ('status','backend','data_bytes','calculated','declared','steps','seconds')}),flush=True)


if __name__=='__main__':main()
