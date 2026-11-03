"""新旧身份在真实装载器执行前拒收。"""
from pathlib import Path
import json
import os
import sys
import time
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(HERE))
import native_support as N
from native_support import Camera,H

def main():
    start=time.monotonic();rows=[]
    body=H.BODY;resident=H.RESIDENT;engine=H.ENGINE;dat=H.DAT
    old_resident=ROOT/'research/v39_g153/local/body/local/resident/build/resident.elf'
    old_engine=ROOT/'firmware/engine_v63_g154/candidate/local/full-r13/engine.elf'
    cases=[('v39-g155-release',False,old_resident,ROOT/'firmware/package_v310_g155/GXRCE.DAT',ROOT/'firmware/engine_v64_g155/candidate/local/boot-off/engine.elf'),
           ('v39-g155-test',False,old_resident,dat,engine),
           ('v310-g154',True,resident,ROOT/'firmware/package_v39_g154_test/local/SD_ROOT/GXRCE.DAT',old_engine)]
    for name,overlay,elf,data,code in cases:
        N.OVERLAY=overlay;H.BODY=body;H.RESIDENT=elf;H.DAT=data;H.PACKAGE=data.parent;H.ENGINE=code
        cam=Camera('50mm');before=cam.s_bytes(0,4096);unit=cam.unit_rows();W=cam.writes();entries=[]
        raw=data.read_bytes();codeoff=int.from_bytes(raw[132:136],'big');entryoff=int.from_bytes(raw[112:116],'big')
        def loaded(e):
            address=cam.h.u(0x20054770)
            if 0x20000000<=address<0x21000000:cam.h.b.add_breakpoint(address+entryoff-codeoff,lambda b:entries.append(True) or False)
        cam.h.b.add_write_trace(0x20054770,0x20054774,loaded)
        cam.h.parent();result=cam.m.fr.native(cam.h,0x20287080,steps=30000000);assert result['ok'],result
        assert cam.h.u(0x20054705,1)==6 and cam.h.u(0x2022f5ac,1)==7 and not entries,(name,entries)
        assert cam.s_bytes(0,4096)==before and cam.unit_rows()==unit and cam.writes()==W
        rows.append(dict(case=name,dat_entries=0,colour_writes=0,root=6,native_rows=7))
    print(json.dumps(dict(status='PASS',backend=os.environ['GXR_HARNESS_BACKEND'],seconds=time.monotonic()-start,cases=rows)),flush=True)

if __name__=='__main__':main()
