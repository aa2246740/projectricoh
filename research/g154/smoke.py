"""同一场景先运行 g153 对照，再运行 g154。"""
from pathlib import Path
import json
import os
import sys
import time
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from native_support import Camera,H,CONTROL,expected,expand_effect,exit_menu


def main():
    started=time.monotonic();cam=Camera('50mm');cam.open_menu();opened=cam.check_frame()
    assert opened['count']==(11 if CONTROL else 22),opened
    look=cam.select_effect(1)
    assert cam.unit_rows()==expected(cam,expand_effect(H.DAT_BYTES[cam.dat_path],0))
    cam.press('DISP');card=cam.check_frame();assert card['screen']==1,card
    cam.goto(0);cam.press('DISP');back=cam.check_frame()
    assert back['screen']==(7 if CONTROL else 0),back
    if CONTROL:
        cam.goto(0);cam.press('DISP')
    user=cam.select_user(1);assert user['applied_user']==1,user
    cam.press('DISP');user_card=cam.check_frame();assert user_card['screen']==1,user_card
    result=dict(status='PASS',control=CONTROL,backend=os.environ['GXR_HARNESS_BACKEND'],
        seconds=time.monotonic()-started,opened=opened,look=look,card=card,back=back,user=user,user_card=user_card,
        native_stats=getattr(cam.h.b,'native_stats',{}))
    suffix='g153' if CONTROL else 'g154'
    (HERE/'evidence'/('smoke-'+suffix+'.json')).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(status='PASS',control=CONTROL,seconds=result['seconds'],native_stats=result['native_stats'])))


if __name__=='__main__':main()
