"""Run generation acceptance and DAT-bound record creation from the final DAT."""
from pathlib import Path
import json
import struct
import sys
import zlib
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
C.setup()
sys.path.insert(0,str(C.ROOT/'tools/native_harness_c'))
import python_backend as P
P.CACHE=C.TMP/'instruction-decode'
E=C.load(C.ROOT/'firmware/stage2l_switch/tools/build.py','review_instruction_elf').Elf
saved=json.loads((C.HERE/'evidence/g155c_saved_records.json').read_text())
generation=[];pairing=[]
for profile,build in [('release','boot-off'),('test','boot-on')]:
    raw=(C.PACKAGES[profile]/'GXRCE.DAT').read_bytes()
    elf=E(C.ENGINE/'candidate/local'/build/'engine.elf')
    base=0x21004000
    image=bytearray(raw)+bytes(C.DF.u32(raw,116))
    rel,n=C.DF.sections(raw)[1]
    for off in range(rel,rel+n,8):
        at,target=struct.unpack_from('>II',raw,off);struct.pack_into('>I',image,at,base+target)
    cpu=P.PurePythonBackend();cpu.map(base,image,True);cpu.map(0x22000000,bytes(0x20000),True)
    cpu.set_reg('r15',0x2201fff0)
    for gen in (155,156,157):
        for unit in range(3):
            view=struct.pack('>5I',base,len(raw),gen,C.DF.u32(raw,112),C.DF.u32(raw,116))
            view+=b''.join(struct.pack('>II',at,n)for at,n in C.DF.sections(raw))
            view+=struct.pack('>HH4B',8,28,unit,1,0,0)
            assert len(view)==84
            cpu.write(0x22000100,view)
            stop=cpu.call(base+elf.symbols['eng_data_accept']['value'],[0x22000100],0x7ffffff0,30000)
            assert stop.reason=='return' and cpu.get_reg('r0')==int(gen!=156)
            generation.append(dict(profile=profile,generation=gen,unit=unit,result=cpu.get_reg('r0'),instructions=stop.steps))
    for old in saved:
        source=C.ROOT/old['path'];settings=source.read_bytes();assert C.sha(settings)==old['sha256']
        record=settings[0xfd4:0xffc];unit=record[6];index=record[5]
        assert record==bytes.fromhex(old['record']) and zlib.crc32(record[:36])==int.from_bytes(record[36:40],'big')
        g=base+elf.symbols['g']['value']
        # M32R ABI: Engine.port 36 B, EngData.image +0, EngData.unit +28.
        # Verified against the declared structures and existing g.current offset 192.
        cpu.write(g+36,struct.pack('>I',base));cpu.write(g+64,bytes([unit]))
        ref=bytearray(56);ref[0]=unit;ref[1]=index if 1<=index<=8 else 3
        user=0
        if 0x40<=index<0x80:ref[51]=index-0x40+1
        elif 0x80<=index<0xa0:user=index-0x80+1
        cpu.write(0x22000200,ref);cpu.write(0x22000300,record[8:28]);cpu.write(0x22000400,b'\xa5'*40)
        stop=cpu.call(base+elf.symbols['memory_build']['value'],[0x22000400,0x22000200,0x22000300,user],0x7ffffff0,50000)
        assert stop.reason=='return'
        actual=cpu.read(0x22000400,40)
        expected=bytearray(record);expected[28:36]=raw[20:28]
        expected[36:40]=zlib.crc32(expected[:36]).to_bytes(4,'big')
        assert actual==expected and actual!=record and actual[28:36]!=record[28:36]
        pairing.append(dict(profile=profile,unit=unit,index=index,source=old['path'],source_sha256=old['sha256'],
            old_record=record.hex(),current_DAT_record=actual.hex(),old_record_whole_equality=False,
            instructions=stop.steps,DAT_sha256=C.sha(raw)))
C.save(C.HERE/'evidence/instructions.json',dict(status='PASS',backend='PurePythonBackend',generation=generation,pairing=pairing,
    boundary='Final DAT function instructions with a host-declared view and memory_build inputs. Does not simulate BOOT transaction; cold-start receipts cover it.'))
print(json.dumps(dict(status='PASS',generation_cases=len(generation),old_record_pairing_cases=len(pairing))))
