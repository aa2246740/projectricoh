"""已提交后重复 32→5 和 H51，确认本会话只尝试一次。"""
import json
import os
from pathlib import Path
import sys
import time
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from native_support import Camera,boot_current
from boot_tests import prepare,record,watch

def main():
    start=time.monotonic();cam=Camera('50mm');prepare(cam);cam.put_s(0xfd4,record(cam));trace=watch(cam)
    answer=boot_current(cam);assert answer==dict(root=3,word=2,status=0,detail=1)
    before=(cam.unit_rows(),cam.s_bytes(0,4096),cam.writes(),len(trace['service']),len(cam.p.files.log))
    h=cam.h
    for _ in range(2):
        h.invoke(0x202b0a74,(32,),native=True,max_steps=100000)
        h.b.set_reg('r0',0x202b0a74);h.b.set_reg('r12',5);h.run_slice(0x2029ebc0,0x2029ebc4,100000)
        h.b.set_reg('r0',0);h.run_slice(0x202b1310,0x202b1314,100000)
        assert h.u(0x200547ec)==2
    after=(cam.unit_rows(),cam.s_bytes(0,4096),cam.writes(),len(trace['service']),len(cam.p.files.log))
    assert before==after and not cam.p.files.live
    print(json.dumps(dict(status='PASS',backend=os.environ['GXR_HARNESS_BACKEND'],seconds=time.monotonic()-start,
        repeated=2,additional_service_calls=0,additional_file_calls=0,additional_W=0)),flush=True)

if __name__=='__main__':main()
