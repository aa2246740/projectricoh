"""Replay final DAT instructions against captured native inputs on C and Python."""
import argparse
import json
from pathlib import Path
import struct
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import HERE, ROOT, PRIOR, EXPECTED, snapshot, backends, cpu_for, mem, word, bind, save, file_info, dat


def qualification():
    rows=[]
    bindings=[]
    for entry in ('eng_boot_check', 'boot_run'):
        path=PRIOR/'local'/('p1final-mount-cold1-'+entry+'.pkl.z')
        saved=snapshot(path)
        base,binding=bind(saved)
        bindings.append(dict(entry=entry, source=file_info(path), **binding))
        S=word(saved,0x200c0dac)
        ordinary=dict(mode=word(saved,0x205d9a7f,1),my=word(saved,0x205d9aa3,1),
                      pending=word(saved,0x205da00b,1),state=word(saved,0x205d9c00),
                      activity=word(saved,0x205d9bf8),selection=word(saved,S+0x2fc))
        assert ordinary==dict(mode=0,my=0,pending=0,state=5,activity=0,selection=0x8001)
        cases=[]
        if entry=='eng_boot_check':
            cases.append(('qualified',None,b''))
        for name,address,length,values in (
            ('mode',0x205d9a7f,1,[1,2,3,4,5,127,255]),
            ('MY',0x205d9aa3,1,[1,2,3,255]),
            ('pending',0x205da00b,1,[1,255]),
            ('activity',0x205d9bf8,4,[1,8,127]),
            ('state',0x205d9c00,4,[0,2,32,56]),
            ('native_selection',S+0x2fc,4,[0,0x8000,0x8002,0xffff]),
            ('settings_pointer',0x200c0dac,4,[0,0x1ffffffc,0x207ff004]),
            ('settings_length',0x200c0db0,4,[0,4095,4097])):
            for value in values:
                cases.append((name+'='+hex(value),address,value.to_bytes(length,'big')))
        for backend,Backend in backends():
            for name,address,raw in cases:
                b=cpu_for(saved,Backend)
                if address is not None:
                    b.write(address,raw)
                before=b.read(S,4096)
                fixed=b.read(0x200547ec,4)
                stores=[]
                services=[]
                b.add_write_trace(S,S+4096,lambda event: stores.append((event.address,event.data.hex())))
                b.add_write_trace(0x200547ec,0x200547f0,lambda event: stores.append((event.address,event.data.hex())))
                b.add_breakpoint(0x201a4298,lambda current: services.append(current.get_reg('pc')) or True)
                stop=b.call(saved['expected_function'],[],0x7ffffff0,100000)
                result=b.get_reg('r0')
                assert stop.reason=='return',(entry,backend,name,stop)
                reply=None
                if entry=='eng_boot_check':
                    assert result==(1 if name=='qualified' else 0),(name,result)
                else:
                    raw_reply=b.read(saved['cpu']['registers']['r3'],32)
                    reply=dict(status=int.from_bytes(raw_reply[4:8],'big',signed=True),
                               detail=int.from_bytes(raw_reply[-4:],'big'))
                    assert result==1 and reply==dict(status=0,detail=2),(name,result,reply)
                assert b.read(S,4096)==before and b.read(0x200547ec,4)==fixed and not stores and not services
                rows.append(dict(entry=entry,backend=backend,case=name,result=result,reply=reply,
                                 instructions=stop.steps,S_equal=True,W_T_dispatch_calls=0,
                                 S_and_fixed_word_stores=0,host_negative=address is not None))
    save('qualification',dict(status='PASS',layer='actual relocated DAT instructions; one host-declared change per negative',
                              bindings=bindings,rows=rows))


def native_selection():
    path=PRIOR/'local/p1final-mount-cold1-native-selection.pkl.z'
    saved=snapshot(path)
    regs=saved['cpu']['registers']
    S=word(saved,0x200c0dac)
    assert regs['pc']==0x202aed3c and word(saved,regs['r8'])==word(saved,S+0x2fc)==0x8001
    body=(ROOT/'artifacts/firmware/gxr-1.51/ilaunch3').read_bytes()
    bindings=[]
    for address,length in ((0x202aed3c,0x9c),(0x2026a2a4,12),(0x202738ac,12)):
        for i in range(16):
            offset,base,n,_,_=struct.unpack_from('>5I',body,32+20*i)
            if base<=address and address+length<=base+n:
                actual=body[512+offset+address-base:512+offset+address-base+length]
                assert mem(saved,address,length)==actual
                bindings.append(dict(address=hex(address),bytes=length,original_equal=True))
                break
        else:
            raise ValueError(hex(address))
    rows=[]
    for backend,Backend in backends():
        b=cpu_for(saved,Backend)
        stores=[]
        b.add_write_trace(0x205d9a7f,0x205d9a80,lambda event: stores.append(dict(field='mode',value=b.read(0x205d9a7f,1).hex())))
        b.add_write_trace(0x205d9aa3,0x205d9aa4,lambda event: stores.append(dict(field='MY',value=b.read(0x205d9aa3,1).hex())))
        b.add_breakpoint(0x202aedd8,lambda current: True)
        stop=b.call(regs['pc'],[],0x7ffffff0,2000)
        assert stop.reason=='breakpoint' and stop.pc==0x202aedd8
        assert stores==[dict(field='MY',value='00'),dict(field='mode',value='00')],stores
        assert b.read(S+0x2fc,4)==b'\0\0\x80\1'
        rows.append(dict(backend=backend,instructions=stop.steps,stores=stores,selection_unchanged=True))
    save('native-selection',dict(status='PASS',source=file_info(path),original_instruction_bindings=bindings,
                                 rows=rows,no_host_native_input_edits=True,
                                 boundary='Native 0x8001 branch only; physical dial mapping is not inferred.'))


def h52():
    rows=[]
    for index in (1,3):
        path=PRIOR/'local'/('final-guard-check-C01-'+str(index)+'.pkl.z')
        saved=snapshot(path)
        regs=saved['cpu']['registers']
        raw=word(saved,regs['r4']+12)
        assert raw in (13,14) and word(saved,0x200547ec)==14
        for backend,Backend in backends():
            b=cpu_for(saved,Backend)
            S=word(saved,0x200c0dac)
            before=b.read(S,4096)
            stop=b.call(regs['pc'],[],regs['r14'],20000)
            assert stop.reason=='return' and b.get_reg('r0')==0
            assert b.read(S,4096)==before and b.read(0x200547ec,4)==b'\0\0\0\x0e'
            rows.append(dict(backend=backend,raw=raw,result=0,instructions=stop.steps,source=file_info(path)))
    for key in ('half','full'):
        path=PRIOR/'local'/('final-noDAT-recovery-'+key+'-C01-input.pkl.z')
        saved=snapshot(path)
        regs=saved['cpu']['registers']
        raw=word(saved,regs['r4']+12)
        assert raw in (13,14) and word(saved,0x200547ec)==2
        for backend,Backend in backends():
            b=cpu_for(saved,Backend)
            S=word(saved,0x200c0dac)
            before=b.read(S,4096)
            b.add_breakpoint(0x202afe9c,lambda current: True)
            stop=b.call(regs['pc'],[],0x7ffffff0,20000)
            assert stop.reason=='breakpoint' and stop.pc==0x202afe9c
            assert b.read(S,4096)==before and b.read(0x200547ec,4)==b'\0\0\0\2'
            rows.append(dict(backend=backend,raw=raw,continuation='0x202afe9c',
                             instructions=stop.steps,no_DAT_cold_source=True,source=file_info(path)))
    save('h52',dict(status='PASS',rows=rows,layer='actual resident instructions, retained guarded HALF/FULL input'))


def release():
    path=PRIOR/'local/p1final-release-session.pkl.z'
    saved=snapshot(path)
    import common as C
    syms=C.RT.symbols(ROOT/'firmware/engine_v67_g155c/candidate/local/boot-off/engine.elf')
    base,binding=bind(saved,'release',mutable=[(syms['t_seen'],4)])
    context=word(saved,base+syms['n']+4)
    nonce=word(saved,context+60)
    assert nonce
    q_at=0x206d0000
    reply_at=q_at+64
    request=bytearray(64)
    struct.pack_into('>HHI',request,0,1,64,0)
    for i,value in ((0,nonce),(1,nonce),(8,257),(9,0x200547ec),(10,context),(11,120)):
        struct.pack_into('>I',request,8+4*i,value)
    rows=[]
    for backend,Backend in backends():
        for case in ('valid-request','unknown-mode','non-standard','wb-offset','already-dirty'):
            b=cpu_for(saved,Backend)
            S=word(saved,0x200c0dac)
            b.write(q_at,request)
            b.write(reply_at,b'\xa5'*32)
            if case=='unknown-mode':b.write(0x205d9a7f,b'\xff')
            if case=='non-standard':b.write(S+0x36e,b'\3')
            if case=='wb-offset':b.write(S+0x6dd,b'\x0a')
            if case=='already-dirty':b.write(0x200547ec,b'\0\0\0\x0e')
            before=b.read(S,4096)
            fixed=b.read(0x200547ec,4)
            stores=[]
            calls=[]
            b.add_write_trace(S,S+4096,lambda event: stores.append(event.address))
            b.add_write_trace(0x200547ec,0x200547f0,lambda event: stores.append(event.address))
            for pc in (0x2009005c,0x201a4298,0x202d6f38):
                b.add_breakpoint(pc,lambda current: calls.append(current.get_reg('pc')) or True)
            stop=b.call(base+syms['ig_panel_event'],[0,nonce,q_at,reply_at],0x7ffffff0,100000)
            raw=b.read(reply_at,32)
            status=int.from_bytes(raw[4:8],'big',signed=True)
            assert stop.reason=='return' and b.get_reg('r0')==0 and status==-4,(case,backend,stop,raw.hex())
            assert b.read(S,4096)==before and b.read(0x200547ec,4)==fixed and not stores and not calls
            rows.append(dict(backend=backend,case=case,result=0,status=-4,detail=int.from_bytes(raw[-4:],'big'),
                             instructions=stop.steps,S_W_T_stores=0,fixed_word_unchanged=True))
    save('release',dict(status='PASS',source=file_info(path),binding=binding,rows=rows,
                        request_is_host_constructed=True,entry='actual ig_panel_event, op 257'))


p=argparse.ArgumentParser(description=__doc__)
p.add_argument('kind',choices=('qualification','native','h52','release'))
p.add_argument('--name')
a=p.parse_args()
if a.name:
    original_save=save
    def save(name,value):
        return original_save(a.name,value)
{'qualification':qualification,'native':native_selection,'h52':h52,'release':release}[a.kind]()
