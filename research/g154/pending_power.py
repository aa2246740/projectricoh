"""记忆写忙时保留原内置记录，冷启动仍保持纯 04。"""
from pathlib import Path
import json
import os
import sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import pending_checks as P
from native_support import Camera


def main():
    made=[];original=P.Camera
    def camera(*args,**kwargs):
        cam=original(*args,**kwargs);made.append(cam);return cam
    P.Camera=camera
    try:P.main()
    finally:P.Camera=original
    saved=made[-1].s_bytes(0,4096);record=made[-1].record()
    assert record[:4]==b'GXR2' and record[5]==8
    fresh=Camera('50mm');stock=fresh.unit_rows();fresh.put_s(0,saved);writes=fresh.writes();fresh.open_menu()
    frame=fresh.check_frame()
    assert frame['cur']==7 and frame['slot']==4 and frame['effect']==0
    assert fresh.unit_rows()==stock and fresh.writes()==writes and fresh.record()==record
    result=dict(status='PASS',backend=os.environ['GXR_HARNESS_BACKEND'],frame=frame,record=record.hex(),unit_W=0,
        scope='记忆写忙时，最后一个有效内置记录保留；仅高亮该内置，实际保持纯 04。')
    (HERE/'evidence/pending-power.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
