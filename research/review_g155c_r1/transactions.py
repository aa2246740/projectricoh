"""Bounded original-RTOS BOOT transactions with declared negative inputs/faults."""
import argparse
import copy
import json
import os
from pathlib import Path
import struct
import sys
import time
import zlib
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C


def run(case,label):
    source=C.PRIOR/'local/p1final-mount-cold1-boot_run.pkl.z'
    saved=C.snapshot(source)
    _,binding=C.bind(saved)
    R=C.RT
    engine=C.ROOT/'firmware/engine_v67_g155c'
    r=R.Runtime(source,'txn-'+case+'-'+label+'-'+str(os.getpid()),engine,engine/'candidate/local/boot-on/engine.elf')
    import unit_peer
    original=unit_peer.call
    result=dict(status='OPEN',case=case,source=C.file_info(source),binding=binding,
                layer='original standby RTOS model; actual DAT instructions',faults=[],native_input_edits=[])
    S=r.u(0x200c0dac)
    record=bytearray(r.cpu.read(S+0xfd4,40))
    def edit(address,raw):
        old=r.cpu.read(address,len(raw))
        r.cpu.write(address,raw)
        result['native_input_edits'].append(dict(address=hex(address),old=old.hex(),new=raw.hex()))
    if case in ('not-standard','wb-a','wb-b','source-my'):
        offset,value={'not-standard':(0x36e,3),'wb-a':(0x6dd,10),'wb-b':(0x6de,8),'source-my':(8,1)}[case]
        edit(S+offset,bytes([value]))
    if case.startswith('record-'):
        kind=case[7:]
        if kind=='crc':
            record[-1]^=1
        else:
            if kind=='unit': record[6]=(record[6]+1)%3
            elif kind=='dat': record[28:36]=b'\0'*8
            elif kind=='category': record[5]=0xbf
            elif kind=='version': record[4]=0x7f
            elif kind=='incomplete': record[7]=0
            elif kind=='range': record[8:10]=b'\x7f\xff'
            elif kind=='empty': record[:]=b'\0'*40
            else: raise ValueError(kind)
            if kind!='empty': struct.pack_into('>I',record,36,zlib.crc32(record[:36]))
        edit(S+0xfd4,record)
    before=r.cpu.read(S,4096)
    fixed=r.u(0x200547ec)
    peer=r.machine.devices['startup'].rpc_state
    before_peer=copy.deepcopy(peer)
    initial_w=sum(row['cmd']==22 for row in peer.get('log',[]))
    stores=[]
    fixed_stores=[]
    r.cpu.add_write_trace(S,S+4096,lambda at,data: stores.append(dict(step=r.cpu.steps,offset=at-S,data=bytes(data).hex())))
    r.cpu.add_write_trace(0x200547ec,0x200547f0,lambda at,data: fixed_stores.append(dict(step=r.cpu.steps,value=int.from_bytes(data,'big'))))
    w_count=0
    def declared_peer(state,command,value,unit='50mm'):
        nonlocal w_count
        answer=original(state,command,value,unit)
        if command==22:
            w_count+=1
            fail=(case=='w-fail-once' and w_count==50) or (case=='w-fail-compensation' and w_count in (50,60))
            if fail:
                result['faults'].append(dict(step=r.cpu.steps,command=22,W_index=w_count,value=value,
                                             actual_peer_result=answer,declared_result=-1,write_applied_before_error=True))
                return -1
            if case=='mode-after-W' and w_count==50:
                edit(0x205d9a7f,b'\x7f')
                result['faults'].append(dict(step=r.cpu.steps,kind='mode becomes unknown after W 50'))
        return answer
    unit_peer.call=declared_peer
    regs=saved['cpu']['registers']
    ret=regs['r14']
    reply_at=regs['r3']
    task=r.machine.task()
    done=[]
    def returned(cpu):
        if r.machine.task()!=task:
            return False
        reply=cpu.read(reply_at,32)
        done.append(dict(result=cpu.get_reg('r0'),reply=reply.hex(),
                         status=int.from_bytes(reply[4:8],'big',signed=True),detail=int.from_bytes(reply[-4:],'big')))
        return True
    r.cpu.add_breakpoint(ret,returned)
    start=time.monotonic()
    start_steps=r.cpu.steps
    try:
        for chunk in range(350):
            stop=r.cpu.run(1_000_000)
            if stop.reason=='breakpoint':break
            assert stop.reason=='max_steps',stop
            if time.monotonic()-start>1800: raise TimeoutError('30 minute transaction bound')
        assert done,(case,stop)
        after=r.cpu.read(S,4096)
        word=r.u(0x200547ec)
        W=sum(row['cmd']==22 for row in peer.get('log',[]))-initial_w
        result.update(return_value=done[0],S_stores=stores,fixed_word_stores=fixed_stores,
                      final_word_before_resident=word,W_calls=W,T=peer.get('t',2),
                      instructions=r.cpu.steps-start_steps,elapsed_seconds=round(time.monotonic()-start,3),
                      S_equal=after==before,record_equal=after[0xfd4:0xffc]==before[0xfd4:0xffc])
        if case=='baseline':
            assert done[0]['result']==1 and done[0]['status']==0 and done[0]['detail']==1
            assert word==2 and fixed_stores[0]['value']==6 and fixed_stores[-1]['value']==2
            # Recalculate the complete target using the independent C math reference.
            sys.path.insert(0,str(C.PRIOR))
            import reference
            reference.HERE=C.HERE
            reference.TMP=C.TMP/'reference'
            raw=C.dat('test')
            unit=record[6]
            slot=record[5]
            assert 1<=slot<=8
            levels=list(struct.unpack('>10h',record[8:28]))
            status,target=reference.Reference(engine.name).compute(raw,unit,reference.expand(raw,unit,slot),levels)
            assert status==0 and len(target)==552
            result['target']=verify_colour(r,raw,unit,slot,target)
            assert after[0xfd4:0xffc]==before[0xfd4:0xffc]
            allowed={0x645,0x646,0x6dd,0x6de,0x36e}
            changed={i for i,(a,b) in enumerate(zip(before,after)) if a!=b}
            assert changed<=allowed,changed
            result['S_changed_offsets']=[hex(i) for i in sorted(changed)]
        elif case=='w-fail-once':
            assert done[0]['result']==1 and done[0]['status']==0 and done[0]['detail']==3
            assert word==2 and after==before and len(result['faults'])==1
            sys.path.insert(0,str(C.ROOT/'research/v39_g153'))
            from dat_format import expand
            result['stock']=verify_colour(r,C.dat('test'),record[6],4,expand(C.dat('test'),record[6],4))
        elif case in ('w-fail-compensation','mode-after-W'):
            assert word&4 and done[0]['result']==3 and done[0]['status']!=0
            # Let the unchanged resident process the DAT fault and establish GUARD.
            r.cpu.breakpoints.pop(ret,None)
            def guard_return(cpu): return r.u(0x200547ec)==14
            r.cpu.add_breakpoint(0x202b1210,guard_return)
            for chunk in range(20):
                stop=r.cpu.run(1_000_000)
                if stop.reason=='breakpoint':break
                assert stop.reason=='max_steps',stop
            assert r.u(0x200547ec)==14
            result['resident_guard_word']=14
            result['unverified_colour_is_guarded']=True
            # The error state is expected fail-closed behavior, not a product FAIL.
        else:
            assert done[0]['result']==1 and done[0]['status']==0 and done[0]['detail']==2
            assert after==before and word==fixed==2 and not stores and not fixed_stores and W==0
            assert peer.get('t',2)==before_peer.get('t',2) and peer.get('overlay',{})==before_peer.get('overlay',{})
        result['status']='PASS'
    except BaseException as error:
        result.update(status='CHECK_ERROR',error=type(error).__name__+': '+str(error))
        raise
    finally:
        unit_peer.call=original
        C.save('transaction-'+case+'-'+label,result)
        r.machine.close()


def verify_colour(r,raw,unit,slot,target):
    live=r.cpu.read(r.at('g.live'),552)
    assert live==target,('g.live differs',C.digest(live),C.digest(target))
    peer=r.machine.devices['startup'].rpc_state
    from unit_peer import UnitImage
    image=UnitImage(('50mm','28mm','mount')[unit])
    def actual(address):
        aligned=address&~1
        if aligned in peer.get('overlay',{}):
            return peer['overlay'][aligned]>>(0 if address&1 else 8)&255
        return image.bytes_at(address,1)[0]
    directory=int.from_bytes(raw[156:160],'big')+64*unit
    map_at=int.from_bytes(raw[directory+12:directory+16],'big')
    mapping=raw[map_at:map_at+152]
    rows=[]
    for i in range(9):
        address,n,offset=struct.unpack_from('>IHH',mapping,32+12*i)
        observed=bytes(actual(address+j) for j in range(n))
        assert observed==target[offset:offset+n],('unit row',i)
        rows.append(dict(row=i,bytes=n,sha256=C.digest(observed),equal=True))
    assert peer.get('t',2)==int.from_bytes(target[445:447],'big')
    S=r.cpu.read(r.u(0x200c0dac),4096)
    bank=int.from_bytes(raw[directory+16:directory+20],'big')+32+64*(slot-1)
    record=raw[bank:bank+64]
    mode=record[3]
    offsets=[0x36f,0x370,0x371,*range(0x8ac,0x8b6)] if mode==4 else [0x645,0x646] if mode==3 else [0x641,0x642,0x644,0x643] if mode==6 else []
    plan={off:record[36+i] for i,off in enumerate(offsets)}
    plan.update({0x6dd:record[49]+9,0x6de:record[50]+9,0x36e:mode})
    assert all(S[off]==value for off,value in plan.items()),plan
    return dict(complete_552_equal=True,target_sha256=C.digest(target),nine_rows=rows,T_equal=True,
                S_plan_equal=True,S_plan={hex(k):v for k,v in plan.items()})


p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--label',default='r1')
p.add_argument('cases',nargs='+',choices=('baseline','not-standard','wb-a','wb-b','source-my',
    'record-crc','record-unit','record-dat','record-category','record-version','record-incomplete',
    'record-range','record-empty','w-fail-once','w-fail-compensation','mode-after-W'))
a=p.parse_args()
for case in a.cases:
    run(case,a.label)
