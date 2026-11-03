#!/usr/bin/env python3
"""Replay byte-verified official instructions with explicit host-only boundaries."""
import importlib.util
import json
from pathlib import Path
import re
import sys
import traceback

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import evidence as e

spec=importlib.util.spec_from_file_location('prior_r3_replay',e.ROOT/'research/user_storage_r3/replay.py')
base=importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
CPU=base.CPU
native=base.native

class Program:
    def __init__(self):
        self.name='body-v4-storage-official'
        self.image=e.Image()
        self.symbols,self.code,self.width={},{},{}
        self.verified=0
        for path in sorted(e.OUT.glob('*.asm.txt')):
            for line in path.read_text().splitlines():
                m=re.match(r'^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2}\s)+)\s*(.*?)\s*$',line)
                if not m:continue
                pc,raw=int(m[1],16),bytes.fromhex(m[2])
                assert self.image.raw(pc,len(raw))==raw,(path,hex(pc))
                self.verified+=len(raw)
                if len(raw) in (2,4):
                    parsed=tuple(native.p.Program.parse(x) for x in re.split(r' -> | \|\| ',m[3]))
                    if pc in self.code:assert self.code[pc]==parsed,(path,hex(pc))
                    self.code[pc]=parsed
                    self.width[pc]=len(raw)

    def byte(self,address):
        try:return self.image.raw(address,1)[0]
        except AssertionError:return 0

def stub(c,address,name,value=0,hook=None):
    native.stub(c,address,name,value,hook)

def classifier(program):
    rows=[]
    for typ in (1,7):
        for code in (*range(0x1f00,0x1f14),0,0xffff):
            c=CPU(program)
            c.seed(0x204f41ba,code,2)
            c.seed(0x204f41c4,typ)
            c.seed(0x204f41c8,typ)
            event=c.call(0x2010e094)
            expected={0x1f02:0,0x1f03:1,0x1f04:2 if typ==7 else 3,0x1f08:4,
                0x1f09:5 if typ==7 else 6,0x1f0a:7,0x1f0b:8,0x1f12:10}.get(code,9)
            assert event==expected,(typ,code,event,expected)
            rows.append(dict(case='opcode_classifier',message=hex(code),type=typ,event=event))
    return rows

def dispatcher(program):
    rows=[]
    for code,typ,event in ((0x1f02,1,0),(0x1f03,1,1),(0x1f04,7,2),(0x1f04,1,3),
          (0x1f08,1,4),(0x1f09,7,5),(0x1f09,1,6),(0x1f0a,1,7),
          (0x1f0b,1,8),(0x7ffe,1,9),(0x1f12,1,10)):
        for state in range(3):
            c=CPU(program)
            c.seed(0x204f41e8,state,1)
            c.seed(0x204f41ea,0,1)
            c.seed(0x204f41c4,typ)
            c.seed(0x204f41c8,typ)
            target=c.read(0x201427b4+12*event+4*state)
            received=[]
            def receive(cc):
                if received:raise base.Stop()
                cc.seed(0x204f41ba,code,2)
                received.append(1)
                return 48
            stub(c,0x20109b28,'synthetic_receive',hook=receive)
            stub(c,0x2005ff88,'scheduler_hint')
            if target not in (0x201106d4,0x2010e064):stub(c,target,'selected_handler_boundary',state)
            try:c.call(0x2010de04,bound=10000)
            except base.Stop:pass
            else:raise AssertionError('second receive not reached')
            final=c.read(0x204f41e8,1)
            assert target in c.visits or target in c.calls
            assert final==(0 if target==0x201106d4 else state)
            rows.append(dict(case='dispatch_cell',message=hex(code),type=typ,initial_state=state,
               event=event,handler=hex(target),final_state=final,
               boundary='Nontrivial handlers are stubs here; tests table and loop only.'))
    return rows

def builders(program):
    entries={0x20109b58:0x1f02,0x20109bb4:0x1f03,0x20109c44:0x1f03,
      0x20109cdc:0x1f03,0x20109d88:0x1f03,0x20109e18:0x1f03,
      0x20109eb8:0x1f03,0x20109f4c:0x1f03,0x2010a010:0x1f04,
      0x2010a090:0x1f04,0x2010a110:0x1f04,0x2010a194:0x1f04,
      0x2010a248:0x1f08,0x2010a2cc:0x1f09,0x2010a340:0x1f0a,
      0x2010a3c4:0x1f0b,0x2010a420:0x1f12,0x2010a588:0x1f11}
    rows=[]
    for entry,opcode in entries.items():
        c=CPU(program)
        c.seed(0x204f0cc4,2)
        c.seed(0x204f0c90,123)
        for i in range(12):c.seed(c.r[15]+4*i,0x20660000+4*i)
        captured=[]
        def send(cc):
            msg=cc.r[5]
            captured.append(dict(queue=cc.r[4],size=cc.r[6],timeout=cc.r[7],
                 message=hex(cc.read(msg+6,2)),origin=cc.read(msg+2,2),
                 payload={str(k):hex(cc.read(msg+k)) for k in range(12,48,4)}))
            return 0
        stub(c,0x20069490,'mode_boundary')
        stub(c,0x20396594,'conditional_diversion_boundary',1)
        stub(c,0x2010ac50,'queue_send_boundary',hook=send)
        try:c.call(entry,(28,1,0x20650000,4096))
        except Exception as exc:
            e.save('constructor-failure.json',dict(entry=hex(entry),trace=c.trace,
                last_visits=[hex(x) for x in c.visits[-24:]]))
            raise AssertionError('constructor '+hex(entry)) from exc
        assert len(captured)==1 and captured[0]['queue']==2
        assert captured[0]['message']==hex(opcode) and captured[0]['size']==48
        assert captured[0]['timeout']==0
        rows.append(dict(case='constructor_queue2',entry=hex(entry),packet=captured[0],
            boundary='Mode, conditional diversion and sending are stubs. Payload pointers are synthetic.'))
    return rows

def pair_completion(program):
    rows=[]
    for flag7,kind,cross_object in ((0,0,False),(1,0,False),(1,4,False),(1,0,True)):
        c=CPU(program)
        message,obj=0x20640000,0x20650000
        c.seed(message+12,obj)
        c.seed(obj+7,flag7,1)
        c.seed(obj+13,0,1)
        c.seed(obj+112,kind,1)
        c.seed(0x201bc560,1)
        for addr in (0x2015664c,0x2016c75c,0x20155068,0x20155074,0x20155084,
                     0x20168e70,0x20171ed8,0x20171ecc,0x20171f0c,0x201554c8):
            stub(c,addr,'producer_external_'+hex(addr),0)
        forwarded=[]
        def send(cc):
            forwarded.append(dict(queue=cc.r[4],message=hex(cc.read(cc.r[5]+6,2)),
                 object=hex(cc.read(cc.r[5]+12))))
            return 0
        stub(c,0x2005e034,'forward_to_main_queue',hook=send)
        counts=[]
        for attempt in range(2):
            if cross_object and attempt==1:
                second=obj+0x1000
                c.seed(message+12,second)
                c.seed(second+7,flag7,1)
                c.seed(second+13,0,1)
                c.seed(second+112,kind,1)
            c.call(0x20173280,(message,),bound=20000)
            counts.append(dict(after_completion=attempt+1,pair_counter=c.read(0x201bc560),forwarded=len(forwarded)))
        expected=[1,2] if flag7==0 or kind==4 else [0,1]
        assert [r['forwarded'] for r in counts]==expected,(flag7,kind,counts)
        expected_object=hex(obj+0x1000 if cross_object else obj)
        assert all(r['queue']==1 and r['object']==expected_object for r in forwarded)
        rows.append(dict(case='task28_completion_pairing',object_field7=flag7,object_field112=kind,
           cross_object_sequence=cross_object,observations=counts,forwarded=forwarded,
           boundary='Object fields synthetic. Conditional helper outcomes fixed at 0. Does not prove menu mapping or all capture modes.'))
    return rows

def completion_routes(program):
    rows=[]
    for entry in (0x2010a5c8,0x2010a638,0x2010a6b8,0x2010a720,0x2010a7a4,
                  0x2010a810,0x2010a8ac,0x2010a948,0x2010a9e4,0x2010aa88,
                  0x2010ab14,0x2010aba0):
        for origin,typ in ((28,1),(17,7)):
            c=CPU(program)
            req=0x20640000
            c.seed(req,48,2)
            c.seed(req+2,origin,2)
            c.seed(req+16,typ)
            for at,val in ((0x204f0cc8,1),(0x204f0ccc,15),(0x204f0cd0,6)):c.seed(at,val)
            for i in range(10):c.seed(c.r[15]+4*i,0)
            packets=[]
            def copy(cc):
                raw=[cc.read(cc.r[5]+i,1) for i in range(cc.r[6])]
                for i,b in enumerate(raw):cc.seed(cc.r[4]+i,b,1)
                return 0
            def send(cc):
                msg=cc.r[5]
                packets.append(dict(queue=cc.r[4],size=cc.r[6],opcode=hex(cc.read(msg+6,2)),
                    destination=hex(cc.read(msg+4,2)),payload12=hex(cc.read(msg+12))))
                return 0
            stub(c,0x200627d8,'copy_message_bytes',hook=copy)
            stub(c,0x2010ac50,'completion_send',hook=send)
            c.call(entry,(req,0x1234,0,0),bound=10000)
            assert len(packets)==1,(hex(entry),packets)
            rows.append(dict(case='completion_constructor_route',entry=hex(entry),origin=origin,
                format=typ,packet=packets[0],boundary='Message copy and send are stubs. No receiver or durability proof.'))
    return rows

def close_paths(program):
    rows=[]
    fd=0x81
    cache=0x204c86ec+16*(fd&15)
    # Aligned buffered write still calls the lower writer with zero bytes on close.
    for position in (512,513):
        c=CPU(program)
        c.seed(0x204c8668,1)
        c.seed(cache,1,2)
        c.seed(cache+2,1,2)
        c.seed(cache+8,position)
        stub(c,0x0500d4e4,'semaphore_wait')
        stub(c,0x0500d4fc,'semaphore_signal')
        stub(c,0x200ab02c,'tail_flush_failure',-1)
        stub(c,0x200a6750,'lower_close_boundary')
        result=c.call(0x200a437c,(fd,))
        assert result==-1 and c.read(0x204c8668)==1
        tail=[t for t in c.trace if t['name']=='tail_flush_failure']
        assert len(tail)==1 and tail[0]['args'][2]==position%512
        rows.append(dict(case='buffered_close_count_leak',position=position,tail_bytes=position%512,
             result=result,high_count=c.read(0x204c8668),trace=c.trace,
             boundary='Tail flush failure injected; lower close is a success stub.'))
    # The official 479C wrapper resets cache+8 even when C020 returns -1.
    for failure in (0,1,2,None):
        c=CPU(program)
        c.seed(0x204c8668,1)
        c.seed(cache,0,2)
        c.seed(cache+2,1,2)
        c.seed(cache+8,0)
        stub(c,0x0500d4e4,'semaphore_wait')
        stub(c,0x0500d4fc,'semaphore_signal')
        submitted=[]
        def direct(cc):
            submitted.append(cc.r[6])
            return -1 if failure==len(submitted)-1 else cc.r[6]
        stub(c,0x200ac020,'direct_write_boundary',hook=direct)
        stub(c,0x200ab02c,'unexpected_tail_flush',-1)
        stub(c,0x200a6750,'lower_close_boundary')
        result=c.call(0x200a479c,(fd,0x20660000,1536))
        assert result==(-1 if failure in (0,1,2) else 1536)
        assert c.read(cache+8)==0
        closed=c.call(0x200a437c,(fd,))
        assert closed==0 and c.read(0x204c8668)==0
        assert 0x200ab02c not in c.calls
        assert c.calls.count(0x200a6750)==1
        rows.append(dict(case='direct_wrapper_avoids_high_dirty_close',failure_chunk=failure,
             submitted_lengths=submitted,write_result=result,close_result=closed,high_count=0,
             tail_flush_calls=0,trace=c.trace,
             boundary='C020 and lower close stubs; proves high wrapper cleanup only.'))
    c=CPU(program)
    c.seed(cache+2,1,2)
    stub(c,0x0500d4e4,'semaphore_wait')
    stub(c,0x0500d4fc,'semaphore_signal')
    stub(c,0x200ac020,'positive_short_write_boundary',1)
    result=c.call(0x200a479c,(fd,0x20660000,1536))
    assert result==1536 and c.calls.count(0x200ac020)==3 and c.read(cache+8)==0
    rows.append(dict(case='direct_wrapper_hides_positive_short_write',native_return_per_chunk=1,
        requested=1536,reported=result,lower_calls=3,trace=c.trace,
        boundary='Positive short native result injected; normal existing-file reachability is unknown.'))
    # Real lower close with a valid selected slot and an error before release.
    for status in (34,):
        c=CPU(program)
        c.seed(0x204c8668,1)
        c.seed(cache,1,2)
        c.seed(cache+8,0)
        slot=0x204c8c78
        c.seed(slot+4,0,1)
        c.seed(slot+6,0,1)
        stub(c,0x0500d4e4,'semaphore_wait')
        stub(c,0x0500d4fc,'semaphore_signal')
        stub(c,0x200af828,'fd_select_error',status)
        result=c.call(0x200a437c,(fd,))
        assert result==-1 and c.read(0x204c8668)==0
        assert c.read(slot+4,1)==0 and c.read(slot+6,1)==0 and 0x200b8f88 not in c.calls
        rows.append(dict(case='low_slot_survives_high_count_zero',result=result,high_count=0,
            synthetic_slot_identity=[c.read(slot+4,1),c.read(slot+6,1)],release_calls=0,trace=c.trace,
            boundary='fd_select status 34 injected. Slot seed is synthetic; not a normal-fd reachability proof.'))
    c=CPU(program)
    f=0x204c8c78
    c.seed(0x204c8668,1)
    c.seed(cache,1,2)
    c.seed(cache+8,0)
    c.seed(0x204c9206,0,1)
    c.seed(0x204c9207,0,1)
    c.seed(f+4,0,1)
    c.seed(f+6,0,1)
    c.seed(f+7,0x82,1)
    c.seed(f+695,1,1)
    c.seed(f+124,16384)
    c.seed(f+156,16384)
    stub(c,0x0500d4e4,'semaphore_wait')
    stub(c,0x0500d4fc,'semaphore_signal')
    stub(c,0x200af828,'fd_select_success')
    stub(c,0x200b78f4,'lower_close_prepare')
    def decode_length(cc):
        cc.seed(cc.r[6],16384)
        return 0
    stub(c,0x200b9c28,'decode_original_length',hook=decode_length)
    stub(c,0x200b8890,'flush_media_error',50)
    stub(c,0x200af4ec,'native_error_return',-1)
    result=c.call(0x200a437c,(fd,))
    assert result==-1 and c.read(0x204c8668)==0
    assert 0x200b8f88 not in c.calls and [c.read(f+k,1) for k in (4,6)]==[0,0]
    rows.append(dict(case='valid_selected_dirty_close_flush_error_retains_slot',result=result,
        high_count=0,slot_sentinels=[c.read(f+k,1) for k in (4,6)],release_calls=0,
        native_mode_after=c.read(f+7,1),trace=c.trace,
        boundary='Valid selected slot seeded. Native flush status 50 injected. No media execution.'))
    c=CPU(program)
    c.seed(0x204c8668,0)
    c.seed(f+4,0,1)
    c.seed(f+6,0,1)
    stub(c,0x0500d4e4,'semaphore_wait')
    stub(c,0x0500d4fc,'semaphore_signal')
    stub(c,0x200a531c,'normalize_path')
    stub(c,0x200a65f8,'lower_open_slot_acquired',fd)
    stub(c,0x200ab4f0,'geometry_failure',-1)
    stub(c,0x200a6750,'cleanup_close_failure',-1)
    result=c.call(0x200a40b4,(0x20660000,2))
    assert result==-1 and c.read(0x204c8668)==0
    assert [c.read(f+k,1) for k in (4,6)]==[0,0]
    assert c.calls.count(0x200a6750)==1
    rows.append(dict(case='open_failure_can_hide_acquired_low_slot',result=result,high_count=0,
        slot_sentinels=[c.read(f+k,1) for k in (4,6)],trace=c.trace,
        boundary='Lower open acquires synthetic slot; geometry and cleanup close failures injected.'))
    return rows

def main():
    e.preflight()
    program=Program()
    rows=classifier(program)+dispatcher(program)+builders(program)+pair_completion(program)+completion_routes(program)+close_paths(program)
    result=dict(status='PASS_BOUNDED_OFFICIAL_INSTRUCTIONS',cases=len(rows),rows=rows,
       verified_disassembly_bytes_with_overlap=program.verified,
       limits=['No RTOS concurrent execution, camera, storage card or physical I/O.',
               'Each test declares its synthetic state and substituted external boundaries.',
               'A returned native error is injected, not observed on a camera.'])
    e.save('replay-results.json',result)
    print('PASS_BOUNDED_OFFICIAL_INSTRUCTIONS cases='+str(len(rows)))

if __name__=='__main__':
    try:main()
    except Exception:
        e.OUT.mkdir(exist_ok=True)
        old=len(list(e.OUT.glob('replay-failure-*.txt')))
        (e.OUT/('replay-failure-'+str(old+1)+'.txt')).write_text(traceback.format_exc())
        raise
