"""Actual DAT + service code, with the existing harness's native device edges.

The only substitutions are the native RPC dispatcher, normal preview return,
and task-context/ready/limit calls used by tools/native_harness/product_execute.
Settings ownership, tokens, locks, plans, mode checks and DIRTY run as M32R.
"""
import argparse
import copy
from pathlib import Path
import struct
import sys
import zlib
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--backend',choices=('c','python','both'),default='both')
    p.add_argument('--name',default='fast-transactions')
    p.add_argument('--cases',nargs='+',default=['baseline','not-standard','wb-a','wb-b','source-my',
        'record-crc','record-unit','record-dat','record-category','record-version','record-incomplete',
        'record-range','record-empty','stock-lock','wrong-T','wrong-row',
        'w-fail-once','w-fail-compensation','mode-before-W','mode-after-W','preview-fail-once'])
    a=p.parse_args()
    source=C.PRIOR/'local/p1final-mount-cold1-boot_run.pkl.z'
    saved=C.snapshot(source)
    base,binding=C.bind(saved)
    import unit_peer
    syms=C.RT.symbols(C.ROOT/'firmware/engine_v67_g155c/candidate/local/boot-on/engine.elf')
    rows=[]
    native_edges=[0x2009005c,0x202d6f38,0x2005f228,0x2009359c,0x20094e2c]
    for backend,Backend in C.backends():
        if a.backend!='both' and a.backend!=backend:
            continue
        for case in a.cases:
            b=C.cpu_for(saved,Backend)
            S=int.from_bytes(b.read(0x200c0dac,4),'big')
            peer=copy.deepcopy(next(d for t,d in zip(saved['cpu']['device_types'],saved['cpu']['devices'])
                                   if t=='StartupRegisters')['rpc_state'])
            prior_peer=copy.deepcopy(peer)
            count=0
            previews=0
            fault_log=[]
            edits=[]
            def edit(address,raw):
                edits.append(dict(address=hex(address),old=b.read(address,len(raw)).hex(),new=raw.hex()))
                b.write(address,raw)
            if case in ('not-standard','wb-a','wb-b','source-my'):
                offset,value={'not-standard':(0x36e,3),'wb-a':(0x6dd,10),'wb-b':(0x6de,8),'source-my':(8,1)}[case]
                edit(S+offset,bytes([value]))
            if case=='stock-lock':
                edit(0x204104f0,b'\0\0\0\0')
            if case=='wrong-T':
                peer['t']=0
            if case=='wrong-row':
                raw=C.dat('test')
                unit=raw_unit=saved['unit'] if isinstance(saved.get('unit'),int) else 2
                directory=int.from_bytes(raw[156:160],'big')+64*unit
                map_at=int.from_bytes(raw[directory+12:directory+16],'big')
                address=int.from_bytes(raw[map_at+32:map_at+36],'big')&~1
                image=unit_peer.UnitImage('mount')
                peer.setdefault('overlay',{})[address]=int.from_bytes(image.bytes_at(address,2),'big')^1
            record=bytearray(b.read(S+0xfd4,40))
            if case.startswith('record-'):
                kind=case[7:]
                if kind=='crc': record[-1]^=1
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
            before=b.read(S,4096)
            fixed=b.read(0x200547ec,4)
            before_overlay=copy.deepcopy(peer.get('overlay',{}))
            before_t=peer.get('t',2)
            initial_w=sum(x['cmd']==22 for x in peer.get('log',[]))
            stores=[]
            fixed_stores=[]
            def native(address,fn):
                def hit(current):
                    value=fn(current)
                    current.set_reg('r0',value&0xffffffff)
                    current.set_reg('pc',current.get_reg('r14'))
                    return False
                b.add_breakpoint(address,hit)
            def rpc(current):
                nonlocal count
                sp=current.get_reg('r15')
                command=int.from_bytes(current.read(sp+4,4),'big')
                value=int.from_bytes(current.read(sp+8,4),'big')
                answer=unit_peer.call(peer,command,value,'mount')
                if command==22:
                    count+=1
                    if ((case=='w-fail-once' and count==50) or
                        (case=='w-fail-compensation' and count in (50,60))):
                        fault_log.append(dict(W_index=count,command=command,value=value,answer=answer,error=-1))
                        return -1
                    if case=='mode-after-W' and count==50:
                        edit(0x205d9a7f,b'\x7f')
                return answer
            def preview(current):
                nonlocal previews
                previews+=1
                if case=='preview-fail-once' and previews==1:
                    fault_log.append(dict(preview_index=previews,error=-1))
                    return -1
                return 0
            native(0x2009005c,rpc)
            native(0x202d6f38,preview)
            native(0x2005f228,lambda current: 0)
            native(0x2009359c,lambda current: 1)
            native(0x20094e2c,lambda current: 9)
            b.add_write_trace(S,S+4096,lambda event: stores.append(dict(offset=event.address-S,data=event.data.hex())))
            def fixed_store(event):
                fixed_stores.append(event.value)
                if case=='mode-before-W' and event.value==6:
                    edit(0x205d9a7f,b'\x7f')
            b.add_write_trace(0x200547ec,0x200547f0,fixed_store)
            stop=b.call(saved['expected_function'],[],0x7ffffff0,100000000)
            regs=saved['cpu']['registers']
            reply=b.read(regs['r3'],32)
            end=dict(result=b.get_reg('r0'),status=int.from_bytes(reply[4:8],'big',signed=True),
                     detail=int.from_bytes(reply[-4:],'big'))
            word=int.from_bytes(b.read(0x200547ec,4),'big')
            row=dict(case=case,backend=backend,stop=stop.__dict__,return_value=end,word=word,
                     W_calls=count,preview_calls=previews,fixed_word_stores=fixed_stores,
                     S_stores=stores,S_equal=b.read(S,4096)==before,record_equal=b.read(S+0xfd4,40)==before[0xfd4:0xffc],
                     faults=fault_log,host_edits=edits,T=peer.get('t',2))
            rows.append(row)
            # Retain diagnostics before checking, so a new counterexample can be replayed.
            if stop.reason!='return':
                row['status']='HARNESS_BOUNDARY'
                C.save(a.name+'-'+backend+'-boundary',dict(status='HARNESS_BOUNDARY',rows=rows,binding=binding))
                raise RuntimeError((case,backend,stop))
            if case in ('w-fail-compensation','mode-before-W','mode-after-W'):
                assert word==6 and end['result']==3 and end['status']!=0,row
                row['expected_error_is_guarded_by_DIRTY']=True
                row['stock_rows_equal']=unit_rows_equal(C.dat('test'),peer,None)
            elif case in ('w-fail-once','preview-fail-once'):
                assert word==2 and end==dict(result=1,status=0,detail=3) and row['S_equal'],row
                # Read all owned bytes directly from the unit peer after compensation.
                row['stock_rows_equal']=unit_rows_equal(C.dat('test'),peer,None)
                assert row['stock_rows_equal'] and peer['t']==2,row
            elif case=='baseline':
                assert word==2 and end==dict(result=1,status=0,detail=1) and fixed_stores==[6,2],row
            else:
                assert end==dict(result=1,status=0,detail=2),row
                assert word==2 and not stores and not fixed_stores and count==0 and row['S_equal'],row
                assert peer.get('overlay',{})==before_overlay and peer.get('t',2)==before_t,row
            assert row['record_equal'],row
            row['status']='PASS'
            print(case,backend,'PASS',stop.steps,flush=True)
    C.save(a.name,dict(status='PASS',rows=rows,binding=binding,source=C.file_info(source),
                       native_edges=[hex(pc) for pc in native_edges],
                       boundary='Function model. RTOS scheduling, NAND, actual transport and preview timing are not modeled.'))


def unit_rows_equal(raw,peer,target):
    import unit_peer
    sys.path.insert(0,str(C.ROOT/'research/v39_g153'))
    from dat_format import expand
    target=expand(raw,2,4) if target is None else target
    image=unit_peer.UnitImage('mount')
    directory=int.from_bytes(raw[156:160],'big')+64*2
    at=int.from_bytes(raw[directory+12:directory+16],'big')
    for i in range(9):
        address,n,offset=struct.unpack_from('>IHH',raw,at+32+12*i)
        observed=[]
        for address in range(address,address+n):
            aligned=address&~1
            value=peer.get('overlay',{}).get(aligned)
            observed.append(image.bytes_at(address,1)[0] if value is None else value>>(0 if address&1 else 8)&255)
        if bytes(observed)!=target[offset:offset+n]:return False
    return True


if __name__=='__main__':main()
