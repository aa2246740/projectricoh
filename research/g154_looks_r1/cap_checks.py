"""49 行边界及用户条目数量规则。"""
from pathlib import Path
import argparse
import ctypes as C
import json
import os
import struct
import sys
import time
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from native_support import Camera,H,TMP,load,expected
from dat_format import seal,u32,u16,effect_area,crc,descriptor,content_crc,expand,strict_effects,sha
from reference import Reference,user_record
from verify import published_rows


def fixture(users,looks=18):
    raw=H.DAT.read_bytes();out=bytearray(raw)
    tool=load(H.ROOT/'firmware/engine_v65_g154_looks/candidate/user_entries.py','g154_entry_tool')
    if looks!=18:
        at,length=effect_area(raw);out[at+32:at+length]=bytes(length-32)
        struct.pack_into('>H',out,at+10,looks);out[at+20:at+24]=bytes(4)
        base=descriptor(raw,0,5)
        for index in range(looks):
            record=bytearray(base[:18]+bytes((7,0))+f'L{index+1:011d}'.encode())
            struct.pack_into('>I',record,4,content_crc(expand(raw,0,5),7))
            out[at+32+32*index:at+64+32*index]=record
        struct.pack_into('>I',out,at+24,crc(out[at+32:at+length]));struct.pack_into('>I',out,at+28,crc(out[at:at+28]))
    out=seal(out);strict_effects(out);at=u32(out,204)+1408
    values=[dict(base=1,levels=[1]+[0]*10) for _ in range(users)]
    ext=tool.gxui.extension(out[at+64:at+tool.gxui.USER_OFFSET],tool.banks(out),values)
    data=bytearray(out);data[at:at+1984]=ext;data=seal(data)
    expected_limit=min(32,40-looks);assert tool.entry_limit(data)==expected_limit
    if users<=expected_limit:
        assert len(tool.parse(data)[2])==users
    else:
        try:tool.parse(data)
        except ValueError as error:assert 'flat list user limit' in str(error)
        else:raise AssertionError('工具未拒收超限条目')
        try:tool.replace(out,values)
        except ValueError as error:assert 'flat list user limit' in str(error)
        else:raise AssertionError('工具未拒收超限构建')
    folder=TMP/'fixtures';folder.mkdir(parents=True,exist_ok=True)
    path=folder/f'users-{users}-looks-{looks}.DAT';path.write_bytes(data)
    return path


def main():
    p=argparse.ArgumentParser();p.add_argument('--unit',choices=('50mm','28mm','mount'),default='50mm');args=p.parse_args();tick=time.monotonic()
    ref=Reference(154);windows=0
    for count in (1,8,9,27,30,49):
        for current in range(count):
            for top in range(count):
                out=(C.c_uint8*2)(165,165);assert ref.lib.check_window(count,current,top,out)==0
                assert out[0]+out[1]==current and out[1]<8 and out[0]<=max(0,count-8);windows+=1
    out=(C.c_uint8*2)(165,165);assert ref.lib.check_window(50,49,42,out)==-1 and list(out)==[165,165]
    cases=[]
    for users,looks in ((22,18),(23,18),(32,18),(32,8),(32,0),(0,0)):
        dat=fixture(users,looks);cam=Camera(args.unit,dat=dat);before_s=cam.s_bytes(0,4096);before_rows=cam.unit_rows();before_w=cam.writes()
        if users>min(32,40-looks):
            cam.h.parent();opened=cam.m.fr.native(cam.h,0x20287080,steps=30000000);assert opened['ok']
            assert cam.h.u(0x2022f5ac,1)==7 and cam.s_bytes(0,4096)==before_s
            assert cam.unit_rows()==before_rows and cam.writes()==before_w
            cases.append(dict(users=users,looks=looks,result='REJECT',rows=7,unit_W=0,S_equal=True,sha256=sha(dat.read_bytes())))
        else:
            cam.open_menu();rows=published_rows(cam);frame=cam.check_frame();assert frame['count']==9+looks+users
            frames=[frame]
            if users:
                cam.goto(frame['count']-2);frames.append(cam.check_frame())
                assert f'{users:03d}' in frames[-1]['labels'][frames[-1]['physical']],frames[-1]
                assert max(len(x) for f in frames for x in f['labels'])<=13
                slot,levels,_=user_record(dat.read_bytes(),users)
                status,entry=ref.compute(dat.read_bytes(),H.UNITS[args.unit],expand(dat.read_bytes(),H.UNITS[args.unit],slot),levels)
                assert status==0 and cam.ui('applied_user')==users
                assert cam.unit_rows()==expected(cam,entry) and cam.engine_bytes(H.LAYOUT['g.live'],552)==entry
            cam.goto(frame['count']-1);cam.press('DOWN');frames.append(cam.check_frame());assert frames[-1]['cur']==0
            cam.press('UP');frames.append(cam.check_frame());assert frames[-1]['cur']==frame['count']-1
            assert rows and set(rows)=={8}
            cases.append(dict(users=users,looks=looks,result='ACCEPT',logical_rows=frame['count'],frames=frames,published_rows=rows,sha256=sha(dat.read_bytes())))
    result=dict(status='PASS',unit=args.unit,backend=os.environ['GXR_HARNESS_BACKEND'],seconds=time.monotonic()-tick,
        window_cases=windows,above_49_rejected=True,cases=cases,rule='用户条目 <= min(32, 40 - 本单元可见 Looks 数)，超限整份 DAT 拒收。')
    (HERE/'evidence'/f'cap-{args.unit}-{os.environ["GXR_HARNESS_BACKEND"]}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(status='PASS',cases=len(cases),window_cases=windows,seconds=result['seconds'])))


if __name__=='__main__':main()
