"""release 构建仍可手动应用 Looks 并保存 v3，显示 19 个逻辑行。"""
import json
import os
from pathlib import Path
import sys
import time
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(HERE))
from native_support import Camera,H,expected
from dat_format import expand_effect

def main():
    start=time.monotonic();H.DAT=ROOT/'firmware/package_v310_g155/GXRCE.DAT';H.PACKAGE=H.DAT.parent
    H.ENGINE=ROOT/'firmware/engine_v64_g155/candidate/local/boot-off/engine.elf'
    cam=Camera('50mm');cam.open_menu();assert cam.check_frame()['count']==19
    rows=[]
    for number in (1,10):
        cam.goto(7+number);frame=cam.check_frame();entry=expand_effect(cam.dat_path.read_bytes(),number-1)
        assert cam.unit_rows()==expected(cam,entry) and cam.engine_bytes(H.LAYOUT['g.live'],552)==entry
        assert cam.record()[4:6]==bytes([3,0x40+number-1])
        assert cam.h.u(0x200547ec)==0
        rows.append(dict(number=number,frame=frame,record=cam.record().hex()))
    print(json.dumps(dict(status='PASS',backend=os.environ['GXR_HARNESS_BACKEND'],seconds=time.monotonic()-start,
        rows=rows,logical_rows=19,manual_v3=True)),flush=True)

if __name__=='__main__':main()
