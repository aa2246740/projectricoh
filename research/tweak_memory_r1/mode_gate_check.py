"""Replay actual final-DAT BOOT inputs with one declared host variant per gate."""
import argparse
import json
import os
from pathlib import Path
import struct
import sys
import zlib

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE))
from runtime import load_snapshot,sha,TEMP


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prefix',required=True)
    p.add_argument('--name',required=True)
    p.add_argument('--entry',choices=('both','eng_boot_check','boot_run'),default='both')
    p.add_argument('--backend',choices=('both','c','python'),default='both')
    p.add_argument('--only-case')
    p.add_argument('--fast-refusals-only',action='store_true')
    a=p.parse_args()
    assert os.getpriority(os.PRIO_PROCESS,0)>=10
    sys.path.insert(0,str(ROOT/'tools/native_harness_c'))
    import python_backend as PB
    dat=(ROOT/'firmware/package_v310_g155c_test/GXRCE.DAT').read_bytes()
    rows=[]
    for entry in ('eng_boot_check','boot_run'):
        if a.entry!='both' and entry!=a.entry:continue
        source=HERE/'local'/(a.prefix+'-'+entry+'.pkl.z')
        saved=load_snapshot(source);state=saved['cpu'];regs=state['registers']
        assert saved['dat_sha256']==sha(dat)
        def mem(at,n):
            for base,data,_ in state['regions']:
                if base<=at and at+n<=base+len(data):return bytes(data[at-base:at-base+n])
            raise ValueError(hex(at))
        def u(at,n=4):return int.from_bytes(mem(at,n),'big')
        S=u(0x200c0dac)
        base=u(0x20054770)-int.from_bytes(dat[132:136],'big')
        relocated=bytearray(dat)
        off,n=struct.unpack_from('>II',dat,144)
        for at in range(off,off+n,8):
            patch,rel=struct.unpack_from('>II',dat,at)
            struct.pack_into('>I',relocated,patch,base+rel)
        assert mem(base,len(dat))==relocated, 'actual loaded DAT binding differs'
        ordinary=dict(mode=u(0x205d9a7f,1),my=u(0x205d9aa3,1),pending=u(0x205da00b,1),
            state=u(0x205d9c00),activity=u(0x205d9bf8),native_selection=u(S+0x2fc),selector=u(S+0x36e,1))
        assert ordinary==dict(mode=0,my=0,pending=0,state=5,activity=0,native_selection=0x8001,selector=1),ordinary
        cases=[('ordinary',None,None),('mode127',0x205d9a7f,b'\x7f'),('mode255',0x205d9a7f,b'\xff'),
            ('unconfirmed-mode1',0x205d9a7f,b'\1'),('unconfirmed-mode4',0x205d9a7f,b'\4'),
            ('MY1',0x205d9aa3,b'\1'),('MY2',0x205d9aa3,b'\2'),('MY3',0x205d9aa3,b'\3'),
            ('pending',0x205da00b,b'\1'),('activity',0x205d9bf8,struct.pack('>I',8)),
            ('state',0x205d9c00,struct.pack('>I',56)),
            ('unconfirmed-selection',S+0x2fc,struct.pack('>I',0x8002))]
        if entry=='boot_run':
            record=mem(S+0xfd4,40)
            assert record[:5]==b'GXR2\3' and record[28:36]==dat[20:28]
            assert zlib.crc32(record[:36])==int.from_bytes(record[36:],'big')
            cases=cases[1:]+[('non-pure04',S+0x36e,b'\3')]
            for name,offset,new_value in (
                ('record-cross-unit',6,bytes([(record[6]+1)%3])),
                ('record-old-DAT',28,b'\0'*8),
                ('record-unknown-category',5,b'\xbf'),
                ('record-unknown-version',4,b'\x7f')):
                altered=bytearray(record);altered[offset:offset+len(new_value)]=new_value
                struct.pack_into('>I',altered,36,zlib.crc32(altered[:36]))
                cases.append((name,S+0xfd4,bytes(altered)))
            altered=bytearray(record);altered[-1]^=1
            cases.append(('record-bad-crc',S+0xfd4,bytes(altered)))
        for backend,Backend in (('c',PB.PythonBackend),('python',PB.PurePythonBackend)):
            if a.backend!='both' and backend!=a.backend:continue
            PB.CACHE=TEMP/'final-mode-check'/a.name/backend
            for name,address,data in cases:
                if a.only_case and name!=a.only_case:continue
                if a.fast_refusals_only and (name=='non-pure04' or name.startswith('record-')):continue
                b=Backend()
                for at,raw,writable in state['regions']:b.map(at,raw,writable)
                for key in ('psw','spi','spu','bpc','bbpc','evb',*[f'r{i}' for i in range(16)]):b.set_reg(key,regs[key])
                if 'acch' in regs:b.set_reg('acc',(regs['acch']<<32)|regs['accl'])
                if address is not None:b.write(address,data)
                before=b.read(S,4096);word=b.read(0x200547ec,4);writes=[];services=[]
                b.add_write_trace(S,S+4096,lambda event:writes.append(str(event)))
                b.add_write_trace(0x200547ec,0x200547f0,lambda event:writes.append(str(event)))
                # The native W/T dispatcher must never be reached by a refusal.
                def colour_call(current):
                    services.append(dict(pc=hex(current.get_reg('pc'))))
                    return True
                b.add_breakpoint(0x201a4298,colour_call)
                stop=b.call(saved['expected_function'],[],0x7ffffff0,500000)
                result=b.get_reg('r0')
                assert stop.reason=='return',(entry,backend,name,stop)
                if entry=='eng_boot_check':
                    assert result==(1 if name=='ordinary' else 0),(name,result)
                    reply=None
                else:
                    reply=b.read(regs['r3'],32).hex()
                    assert result==1 and int(reply[8:16],16)==0 and int(reply[-8:],16)==2,(name,result,reply)
                assert b.read(S,4096)==before and b.read(0x200547ec,4)==word and not writes and not services,(entry,backend,name,writes,services)
                rows.append(dict(entry=entry,backend=backend,case=name,result=result,reply=reply,steps=stop.steps,
                    declared_change=None if address is None else dict(address=hex(address),old=mem(address,len(data)).hex(),new=data.hex()),
                    other_native_inputs=ordinary,S_equal=True,word_equal=True,W_S_T_writes=0,DIRTY_GUARD_stores=0,
                    source=str(source.relative_to(ROOT)),source_sha256=sha(source.read_bytes())))
    out=HERE/'evidence'/(a.name+'.json');assert not out.exists()
    out.write_text(json.dumps(dict(status='PASS',layer='主机模型：新 DAT 实际冷启动输入的 C/Python 指令复放',
        dat_sha256=sha(dat),entire_loaded_DAT_equal_after_relocation=True,rows=rows,
        scope='Each variant changes only its named input. Full ordinary success is verified by a separate complete cold flow.'),ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(status='PASS',cases=len(rows),dat_sha256=sha(dat))))


if __name__=='__main__':main()
