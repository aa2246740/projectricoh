#!/usr/bin/python3
"""旧 g153 对新 BOOT 操作零写，并与随后的 H01 共用同一次初始化。"""
import argparse
import json
import os
from pathlib import Path
import signal
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
HERE=ROOT/'research/v310_resident'
sys.path.insert(0,str(HERE))
import fixtures_r2 as F
import host_setup_r2 as H


def run(args):
    start=time.monotonic();cam,old,fixture,work,adapters,pb=H.setup(args)
    h,p=cam.h,cam.p;R=0x20054700
    data=Path(fixture['dat']).read_bytes()
    codeoff=int.from_bytes(data[132:136],'big');entryoff=int.from_bytes(data[112:116],'big')
    calls=[];registered=set()
    def hit(b):
        q=b.get_reg('r2');calls.append(dict(pc=hex(b.get_reg('pc')),state=h.u(R+5,1),op=h.u(q+40)))
        return False
    def entry_changed(event):
        block=h.u(R+56);offset=h.u(block+20)
        if offset and h.u(R+5,1) in (2,3):
            address=h.u(block+312)+offset
            if address not in registered:registered.add(address);h.b.add_breakpoint(address,hit)
    def code_changed(event):
        code=h.u(R+112);block=h.u(R+56)
        if code:
            address=code+entryoff-codeoff
            if address not in registered:registered.add(address);h.b.add_breakpoint(address,hit)
            h.b.add_write_trace(block+20,block+24,entry_changed)
    h.b.add_write_trace(R+112,R+116,code_changed)
    original_s=cam.s_bytes(0,4096);original_t=p.rpc.t
    for value in (0,2,32,63,32):h.invoke(0x202b0a74,(value,),native=True,max_steps=100000)
    def transition():
        h.b.set_reg('r0',0x202b0a74);h.b.set_reg('r12',5)
        h.run_slice(0x2029ebc0,0x2029ebc4,100000)
        h.b.set_reg('r0',0);h.run_slice(0x202b1310,0x202b1314,30000000)
    transition()
    assert h.u(R+5,1)==3 and h.u(R+236)==2
    assert cam.writes()==0 and p.rpc.t==original_t and cam.s_bytes(0,4096)==original_s
    assert len([x for x in calls if x['state']==2])==1,calls
    assert len([x for x in calls if x['state']==3 and x['op']==0x101])==1,calls
    # H01 executes real g153 code after BOOT has already loaded the session.
    cam.open_menu();frame=cam.check_frame();cam.press('OK')
    assert h.u(0x2022f5ac,1)==7
    assert len([x for x in calls if x['state']==2])==1
    h.invoke(0x202b0a74,(32,),native=True,max_steps=100000);transition()
    assert len([x for x in calls if x['state']==3 and x['op']==0x101])==1
    assert not p.files.live
    result=dict(status='PASS',variant=args.name,unit=args.unit,side=args.side,
                seconds=time.monotonic()-start,boot_unit_writes=0,boot_s_unchanged=True,
                boot_t_unchanged=True,boot_calls=1,pure_init_calls=1,h01_frame=frame,
                word=h.u(R+236),entries=calls,native_stats=dict(getattr(h.b,'native_stats',{})),
                body_sha256=fixture['body_sha256'],elf_sha256=fixture['elf_sha256'],
                dat_sha256=fixture['dat_sha256'],nice=os.getpriority(os.PRIO_PROCESS,0))
    (HERE/'evidence_r2'/args.name/('g153-boot-'+args.unit+'-'+args.side+'.json')).write_text(json.dumps(result,indent=2)+'\n')
    signal.alarm(0);print(json.dumps({k:result[k] for k in ('status','variant','unit','side','seconds')}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('name');p.add_argument('--side',default='c',choices=['c','python'])
    p.add_argument('--unit',choices=['50mm','28mm','mount']);args=p.parse_args();args.case='g153-boot'
    for unit in ([args.unit] if args.unit else ['50mm','28mm','mount']):
        args.unit=unit
        try:run(args)
        except Exception as exc:
            (HERE/'evidence_r2'/args.name/('g153-boot-'+unit+'-'+args.side+'-failure.json')).write_text(json.dumps(dict(status='FAIL',error=repr(exc)),indent=2)+'\n')
            raise
        __import__('gc').collect()
