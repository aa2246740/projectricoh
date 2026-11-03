"""已应用长名称 Look、记忆写忙时，提示不得带上名字尾部。"""
from pathlib import Path
import json
import os
import sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from native_support import Camera,H,expected
from dat_format import expand_effect,sha


def main():
    cam=Camera('50mm');cam.open_menu();cam.goto(7);cam.press('OK');cam.open_menu()
    previous=cam.s_bytes(0,4096);cam.set_lock(0);frames=[]
    for number in range(1,7):
        cam.press('DOWN');frame=cam.check_frame();frames.append(frame)
        entry=expand_effect(H.DAT_BYTES[cam.dat_path],number-1)
        assert cam.unit_rows()==expected(cam,entry) and cam.engine_bytes(H.LAYOUT['g.live'],552)==entry
        assert cam.s_bytes(0,4096)==previous
    result=dict(backend=os.environ['GXR_HARNESS_BACKEND'],dat_sha256=sha(H.DAT.read_bytes()),frames=frames)
    (HERE/'evidence'/('pending-'+os.environ['GXR_HARNESS_BACKEND']+'.json')).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)
    assert all(frame['labels'][frame['physical']]=='>Unsaved' for frame in frames),frames


if __name__=='__main__':main()
