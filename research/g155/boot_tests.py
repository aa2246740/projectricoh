"""真实 DAT、resident 的开机事务场景；设备和调度边界为明示模型。"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import struct
import sys
import time
import zlib
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE))
from native_support import Camera,H,boot_current,expected,snapshot,exit_menu
from dat_format import expand,expand_effect

def record(cam,kind='builtin',number=2,version=3):
    code=number if kind=='builtin' else 0x40+number-1 if kind=='look' else 0x80+number-1
    raw=b'GXR2'+bytes([version,code,H.UNITS[cam.unit],1])+struct.pack('>10h',100,*([0]*9))+cam.dat_path.read_bytes()[20:28]
    return raw+struct.pack('>I',zlib.crc32(raw))

def prepare(cam):
    cam.h.b.write(0x205d9aa3,b'\0');cam.h.b.write(0x205da00b,b'\0')

def watch(cam):
    result=dict(S=[],word=[],service=[],states=[],unit=[])
    h=cam.h
    h.b.add_write_trace(cam.s,cam.s+4096,lambda e:result['S'].append(dict(pc=hex(e.pc) if e.pc is not None else None,address=hex(e.address),size=len(e.data),word=h.u(0x200547ec))))
    h.b.add_write_trace(0x200547ec,0x200547f0,lambda e:result['word'].append(dict(value=h.u(0x200547ec),pc=hex(e.pc))) if h.u(0x20054700)==0x52565333 else None)
    h.b.add_write_trace(0x205d9c00,0x205d9c04,lambda e:result['states'].append(h.u(0x205d9c00)))
    code_offset=int.from_bytes(cam.dat_path.read_bytes()[132:136],'big');seen=set()
    def loaded(event):
        address=h.u(0x20054770)
        if not 0x20000000<=address<0x21000000 or address in seen:return
        seen.add(address);cam.p.image_base=address-code_offset
        def called(b):
            sid,op=b.get_reg('r0'),b.get_reg('r1')
            row=dict(id=sid,op=op,word=h.u(0x200547ec));result['service'].append(row)
            if sid==4 and op==3:
                assert row['word']&4,row;result['unit'].append(row)
            if sid==6 and op==2:assert row['word']&4,row
            return False
        h.b.add_breakpoint(cam.symbol('rv_call'),called)
    h.b.add_write_trace(0x20054770,0x20054774,loaded)
    return result

def no_colour(cam,before,observed):
    assert cam.writes()==before['W'] and cam.unit_rows()==(before['rows'],before['T'])
    assert cam.s_bytes(0,4096)==before['S'] and not observed['S']
    assert not observed['unit'] and not any(x['value']&12 for x in observed['word'])

def success(unit,kind,number):
    menu=Camera(unit);menu.open_menu()
    row=number-1 if kind=='builtin' else 7+number if kind=='look' else 17+number
    menu.goto(row);target=menu.engine_bytes(H.LAYOUT['g.live'],552);saved=menu.record()
    assert saved[:5]==b'GXR2\3' and saved[5]==(number if kind=='builtin' else 0x40+number-1 if kind=='look' else 0x80+number-1),saved.hex()
    assert zlib.crc32(saved[:36])==int.from_bytes(saved[36:],'big')
    boot=Camera(unit);prepare(boot)
    # The 40 B record is retained in S. The unit and visible S start at pure 04.
    boot.put_s(0xfd4,saved);before=snapshot(boot);observed=watch(boot)
    answer=boot_current(boot)
    assert answer==dict(root=3,word=2,status=0,detail=1),(answer,observed['service'][-8:])
    assert boot.unit_rows()==expected(boot,target)
    assert boot.engine_bytes(H.LAYOUT['g.live'],552)==target
    assert boot.record()==saved and observed['unit']
    assert 56 not in observed['states'],observed['states']
    assert not any(x['id'] in (10,12) for x in observed['service'])
    writes=boot.writes();S=boot.s_bytes(0,4096);service_count=len(observed['service'])
    boot.open_menu();frame=boot.check_frame()
    assert frame['cur']==row and frame['applied_user']==(number if kind=='user' else 0),(answer,frame)
    assert boot.writes()==writes and boot.s_bytes(0,4096)==S
    assert not any(x['id']==5 for x in observed['service'][service_count:])
    assert boot.engine_bytes(H.LAYOUT['g.live'],552)==target
    return dict(kind=kind,number=number,reply=answer,record=saved.hex(),target_sha256=hashlib.sha256(target).hexdigest(),
        W=boot.writes()-before['W'],S_stores=len(observed['S']),word=observed['word'],first_H01_no_apply=True,frame=frame)

def ineligible(unit,case):
    cam=Camera(unit);prepare(cam);rec=bytearray(record(cam))
    if case.startswith('my'):cam.h.b.write(0x205d9aa3,bytes([int(case[-1])]))
    elif case=='pending':cam.h.b.write(0x205da00b,b'\1')
    elif case=='unknown-my':cam.h.b.write(0x205d9aa3,b'\xff')
    elif case=='unknown-pending':cam.h.b.write(0x205da00b,b'\xff')
    elif case=='not-pure':cam.put_s(0x36e,b'\3')
    elif case=='not-pure-T':cam.p.rpc.t=0
    elif case=='not-pure-rows':
        raw=cam.dat_path.read_bytes();unit=int.from_bytes(raw[156:160],'big')+64*H.UNITS[unit]
        mapping=int.from_bytes(raw[unit+12:unit+16],'big');address=int.from_bytes(raw[mapping+32:mapping+36],'big')&~1
        cam.p.rpc.overlay[address]=cam.p.rpc.half(address)^1
    elif case=='empty':rec=bytearray(40)
    elif case=='crc':rec[39]^=1
    elif case in ('unit','identity','v1','controls','unknown-tail'):
        if case=='unit':rec[6]=(rec[6]+1)%3
        elif case=='identity':rec[28]^=1
        elif case=='v1':rec[4]=1
        elif case=='controls':rec[8:10]=struct.pack('>h',101)
        elif case=='unknown-tail':rec[:4]=b'XXXX'
        rec[36:40]=struct.pack('>I',zlib.crc32(rec[:36]))
    elif case=='busy':cam.set_lock(0)
    elif case!='release':raise ValueError(case)
    cam.put_s(0xfd4,rec);before=snapshot(cam);observed=watch(cam);answer=boot_current(cam)
    assert answer==dict(root=3,word=2,status=-4 if case=='release' else 0,detail=0 if case=='release' else 2),answer
    no_colour(cam,before,observed)
    if case.startswith('my') or case=='unknown-my':
        cam.open_menu();cam.check_frame();assert cam.engine_bytes(H.LAYOUT['g.baseline'],1)==b'\0'
        no_colour(cam,before,observed)
    return dict(case=case,reply=answer,zero_colour=True,word=observed['word'],service_calls=len(observed['service']))

def raw_mode_diagnostic(unit):
    cam=Camera(unit);prepare(cam);cam.h.b.write(0x205d9a7f,b'\xff');cam.put_s(0xfd4,record(cam))
    observed=watch(cam);answer=boot_current(cam)
    assert answer==dict(root=3,word=2,status=0,detail=1),answer
    assert cam.h.u(cam.symbol('ig_boot_raw_mode'),1)==255
    return dict(reply=answer,raw_mode=255,policy='只作诊断，按后续裁定不作门控。')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--unit',default='50mm',choices=('50mm','28mm','mount'))
    parser.add_argument('--case',default='success');parser.add_argument('--kind',default='builtin');parser.add_argument('--number',type=int,default=2)
    a=parser.parse_args();start=time.monotonic()
    if a.case=='release':
        H.DAT=ROOT/'firmware/package_v310_g155/GXRCE.DAT';H.PACKAGE=H.DAT.parent
        H.ENGINE=ROOT/'firmware/engine_v64_g155/candidate/local/boot-off/engine.elf'
    result=success(a.unit,a.kind,a.number) if a.case=='success' else raw_mode_diagnostic(a.unit) if a.case=='raw-mode' else ineligible(a.unit,a.case)
    result.update(status='PASS',backend=os.environ['GXR_HARNESS_BACKEND'],seconds=time.monotonic()-start,unit=a.unit)
    print(json.dumps(result,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
