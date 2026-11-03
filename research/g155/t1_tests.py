"""MOUNT 的 06 / Splt=1 通过真实菜单保存，再由 BOOT 恢复 T=0 完整目标。"""
from pathlib import Path
import json
import os
import sys
import time
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from native_support import Camera,H,boot_current,expected
from boot_tests import prepare,watch

def main():
    start=time.monotonic();cam=Camera('mount');cam.open_menu();cam.goto(5);cam.press('DISP');cam.goto(1);cam.press('DISP')
    assert cam.ui('screen')==2
    found=False
    for i in range(1,cam.ui('count')):
        cam.goto(i);frame=cam.check_frame()
        if frame['labels'][frame['physical']].startswith('Splt'):
            found=True;break
    assert found;cam.press('DISP');assert cam.ui('screen')==3
    for i in range(cam.ui('count')):
        cam.goto(i)
        if cam.levels()[8]==1:break
    assert cam.levels()[8]==1 and cam.unit_rows()[1]==0
    target=cam.engine_bytes(H.LAYOUT['g.live'],552);saved=cam.record()
    assert saved[:6]==b'GXR2\3\6' and int.from_bytes(saved[24:26],'big')==1
    restored=Camera('mount');prepare(restored);restored.put_s(0xfd4,saved);trace=watch(restored)
    answer=boot_current(restored);assert answer==dict(root=3,word=2,status=0,detail=1),answer
    assert restored.unit_rows()==expected(restored,target) and restored.engine_bytes(H.LAYOUT['g.live'],552)==target
    assert restored.record()==saved
    W=restored.writes();S=restored.s_bytes(0,4096);n=len(trace['service']);restored.open_menu();frame=restored.check_frame()
    assert frame['cur']==5 and frame['levels'][8]==1 and restored.unit_rows()[1]==0
    assert restored.writes()==W and restored.s_bytes(0,4096)==S and not any(x['id']==5 for x in trace['service'][n:])
    print(json.dumps(dict(status='PASS',backend=os.environ['GXR_HARNESS_BACKEND'],seconds=time.monotonic()-start,
        reply=answer,record=saved.hex(),frame=frame,T=0,first_H01_no_apply=True)),flush=True)

if __name__=='__main__':main()
