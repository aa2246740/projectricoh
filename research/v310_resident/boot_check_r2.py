#!/usr/bin/python3
"""通过真实机身跳板及测试 DAT 执行 BOOT 主机模型。"""
import argparse
import hashlib
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
import stub_build_r2 as B

R=0x20054700
WORD=R+236
KINDS={'unsupported':0,'success':1,'mid-error':2,'retire':3,'my1':1,'my2':1,'my3':1,
       'unknown':1,'missing':0,'maintenance':1}


def run(args):
    start=time.monotonic()
    base=F.prepare(args.name)
    stub=B.build(args.name,KINDS[args.case])
    fixture=dict(base,dat=stub['dat'],engine=stub['engine'],
                 dat_sha256=stub['dat_sha256'],engine_sha256=stub['engine_sha256'])
    cam,old,fixture,work,adapters,pb=H.setup(args,fixture)
    h,p=cam.h,cam.p
    signal.alarm(1800)
    # Explicit host-model preconditions; these do not claim full cold boot.
    h.b.write(0x205d9aa3,bytes([int(args.case[-1]) if args.case.startswith('my') else 0]))
    h.b.write(0x205d9a7f,bytes([255 if args.case=='unknown' else 0]))
    if args.case=='missing':p.files.paths.clear();p.files.present=False
    entries=[];registered=set();words=[];state_writes=[]
    def entered(b):
        q=b.get_reg('r2')
        block=h.u(R+56)
        entries.append(dict(state=h.u(R+5,1),op=h.u(q+8+8*4),
                            trace=h.u(block+312)+h.u(block+316)))
        return False
    def code_published(event):
        address=h.u(R+112)
        if address and address not in registered:
            registered.add(address);h.b.add_breakpoint(address,entered)
    h.b.add_write_trace(R+112,R+116,code_published)
    h.b.add_write_trace(WORD,WORD+4,lambda e: words.append(dict(value=h.u(WORD),pc=e.pc,state=h.u(R+5,1))))
    h.b.add_write_trace(0x205d9c00,0x205d9c04,lambda e: state_writes.append(h.u(0x205d9c00)))
    original_s=cam.s_bytes(0,4096);original_t=p.rpc.t;original_writes=cam.writes()
    def state(value):h.invoke(0x202b0a74,(value,),native=True,max_steps=100000)
    for value in (0,2,32,63,32):state(value)
    if args.case=='maintenance':
        # Negative control: a state 5 written outside the T02 call site must
        # not create a BOOT latch or load. This is not all maintenance paths.
        state(5)
    else:
        h.b.set_reg('r0',0x202b0a74);h.b.set_reg('r12',5)
        h.run_slice(0x2029ebc0,0x2029ebc4,100000)
        assert h.u(0x205d9c00)==5 and h.u(WORD)==1
    def after():
        h.b.set_reg('r0',0)
        h.run_slice(0x202b1310,0x202b1314,30000000)
        assert h.b.get_reg('r2')==0 and h.b.get_reg('r0')==2
    after()
    boot_entries=[e for e in entries if e['state']==3 and e['op']==0x101]
    assert len(boot_entries)==(0 if args.case in ('missing','maintenance') else 1),entries
    init_entries=[e for e in entries if e['state']==2]
    assert len(init_entries)==len(boot_entries)
    if args.case=='maintenance':
        assert h.u(R+5,1)==255 and h.u(WORD)==0xffffffff and not entries
        result=dict(status='PASS',variant=args.name,case=args.case,side=args.side,
                    seconds=time.monotonic()-start,boot_calls=0,init_calls=0,
                    scope='negative model: native state setter outside T02; not all maintenance paths',
                    unit_writes=cam.writes()-original_writes,s_unchanged=cam.s_bytes(0,4096)==original_s,
                    t_unchanged=p.rpc.t==original_t)
        assert result['unit_writes']==0 and result['s_unchanged'] and result['t_unchanged']
        (HERE/'evidence_r2'/args.name/('boot-maintenance-'+args.side+'.json')).write_text(json.dumps(result,indent=2)+'\n')
        signal.alarm(0);print(json.dumps(result),flush=True);return
    word=h.u(WORD);root_state=h.u(R+5,1)
    expected_dirty=args.case in ('mid-error','retire')
    assert bool(word&4)==expected_dirty,(args.case,hex(word))
    assert bool(word&8)==expected_dirty,(args.case,hex(word))
    assert root_state==(6 if args.case in ('retire','missing') else 0xff if args.case=='maintenance' else 3),(args.case,root_state)
    reply=None
    if boot_entries and args.case!='retire':
        layout=json.loads((HERE/'evidence_r2'/args.name/'measurement.json').read_text())['layout']
        address=h.u(R+56)+layout['RvSession']['offsets']['call_reply']
        status=h.u(address+4);status=status if status<0x80000000 else status-0x100000000
        detail=h.u(address+28)
        expected=(-4,0) if args.case=='unsupported' else (-1,3) if args.case=='mid-error' else (0,1) if args.case=='success' else (0,2)
        assert (status,detail)==expected,(args.case,status,detail)
        reply=dict(status=status,detail=detail)
    if args.case=='retire':assert h.u(R+152)==5 and not h.u(R+56)
    assert not any(e['state']==2 and e['value']&12 for e in words)
    if boot_entries:
        trace=boot_entries[0]['trace']
        values=[h.u(trace+4*i) for i in range(5)]
        assert values[:4]==[1,1,WORD,2],values
        if args.case in ('success','mid-error','retire'):assert values[4]&4
    else:values=[]
    before=len(boot_entries)
    for _ in range(2):
        state(32)
        h.b.set_reg('r0',0x202b0a74);h.b.set_reg('r12',5)
        h.run_slice(0x2029ebc0,0x2029ebc4,100000)
        after()
    assert len([e for e in entries if e['state']==3 and e['op']==0x101])==before
    assert cam.writes()==original_writes and p.rpc.t==original_t
    assert cam.s_bytes(0,4096)==original_s
    msg=cam.m.pe.SCRATCH+0x800
    h.b.write(msg,bytes(32));h.b.write(msg+6,(0x700b).to_bytes(2,'big'))
    h.b.write(msg+12,(14).to_bytes(4,'big'));h.b.write(msg+16,(1).to_bytes(4,'big'))
    h.b.set_reg('r4',msg)
    sp=h.b.get_reg('r15');psw=h.b.get_reg('psw')
    consumers=[0x202afeec,0x202b02c4,0x202b05e0,0x20272ed8]
    counts={pc:h.b.visits.get(pc,0) for pc in consumers}
    if expected_dirty:
        result=h.invoke(0x202afe98,(msg,),native=True,max_steps=100000)
        assert result==0 and h.b.get_reg('r15')==sp
        shot='cancelled'
    else:
        active=[True]
        h.b.add_breakpoint(0x202afe9c,lambda b: None if active[0] else False)
        stop=h.b.call(0x202afe98,(),0x0bad0000,100000)
        active[0]=False
        assert stop.reason=='breakpoint' and stop.pc==0x202afe9c
        assert h.b.get_reg('r15')==sp-8
        h.b.set_reg('r15',sp)
        shot='native prologue continued'
    assert h.b.get_reg('psw')==psw
    assert all(h.b.visits.get(pc,0)==counts[pc] for pc in consumers)
    assert not p.files.live
    stats=dict(getattr(h.b,'native_stats',{}))
    if args.side=='c':assert stats.get('instructions',0)>0,stats
    result=dict(status='PASS',variant=args.name,case=args.case,side=args.side,unit=args.unit,
                seconds=time.monotonic()-start,scope='host model; real resident and test DAT instructions',
                boot_calls=before,init_calls=len(init_entries),word=word,root_state=root_state,
                trace=values,reply=reply,states=state_writes,shot=shot,word_writes=words,
                unit_writes=cam.writes()-original_writes,s_unchanged=True,t_unchanged=True,
                native_stats=stats,fixture=dict(body=fixture['body_sha256'],elf=fixture['elf_sha256'],
                    dat=fixture['dat_sha256'],stub_elf=stub['engine_sha256']),
                adapters=adapters,nice=os.getpriority(os.PRIO_PROCESS,0),timeout=1800)
    out=HERE/'evidence_r2'/args.name/('boot-'+args.case+'-'+args.side+'.json')
    out.write_text(json.dumps(result,indent=2)+'\n')
    signal.alarm(0)
    print(json.dumps({k:result[k] for k in ('status','variant','case','side','seconds','word','shot')}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('name');p.add_argument('--case',choices=KINDS,default='success')
    p.add_argument('--unit',default='50mm');p.add_argument('--side',choices=['c','python'],default='c')
    p.add_argument('--matrix',action='store_true')
    args=p.parse_args()
    names=args.name.split(',');cases=list(KINDS) if args.matrix else [args.case]
    for name in names:
        args.name=name
        for case in cases:
            args.case=case
            try:run(args)
            except Exception as exc:
                record=dict(status='FAIL',case=args.case,side=args.side,error=repr(exc))
                (HERE/'evidence_r2'/args.name/('boot-'+args.case+'-'+args.side+'-failure.json')).write_text(json.dumps(record,indent=2)+'\n')
                raise
            __import__('gc').collect()
