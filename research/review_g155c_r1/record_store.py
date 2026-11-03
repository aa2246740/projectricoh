"""Replay actual RV_SETTINGS op 5; assert the 40-byte replacement boundary."""
import argparse
from pathlib import Path
import sys
import zlib
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--name',default='record-store')
p.add_argument('--backend',choices=('c','python','both'),default='both')
a=p.parse_args()
source=C.PRIOR/'local/p1final-mount-tweak-only-record-store-input.pkl.z'
saved=C.snapshot(source)
regs=saved['cpu']['registers']
assert (regs['r0'],regs['r1'])==(6,5)
syms=C.RT.symbols(C.ROOT/'firmware/engine_v67_g155c/candidate/local/boot-on/engine.elf')
_,binding=C.bind(saved,mutable=[(syms['t_seen'],4)])
buffer=C.word(saved,regs['r2']+48)
expected=C.mem(saved,buffer+24,40)
assert expected[:5]==b'GXR2\3' and expected[28:36]==C.dat('test')[20:28]
assert zlib.crc32(expected[:36])==int.from_bytes(expected[36:],'big')
rows=[]
for backend,Backend in C.backends():
    if a.backend!='both' and backend!=a.backend:continue
    for case,want in (('valid-update',0),('unknown-tail',-7),('busy-lock',-2),('bad-new-record',-3)):
        b=C.cpu_for(saved,Backend)
        S=C.word(saved,0x200c0dac)
        if case=='unknown-tail':b.write(S+0xfd4,b'UNKN'+bytes(range(36)))
        if case=='busy-lock':b.write(0x204104f0,bytes(4))
        if case=='bad-new-record':b.write(buffer+24+39,bytes([expected[-1]^1]))
        before=b.read(S,4096)
        fixed=b.read(0x200547ec,4)
        stores=[]
        b.add_write_trace(S,S+4096,lambda event: stores.append(dict(offset=event.address-S,bytes=len(event.data))))
        def native_context(current):
            current.set_reg('r0',0)
            current.set_reg('pc',current.get_reg('r14'))
            return False
        b.add_breakpoint(0x2005f228,native_context)
        stop=b.call(regs['pc'],[],0x7ffffff0,200000)
        value=b.get_reg('r0')
        result=value if value<0x80000000 else value-0x100000000
        after=b.read(S,4096)
        assert stop.reason=='return' and result==want,(case,backend,stop,result)
        assert before[:0xfd4]==after[:0xfd4] and before[0xffc:]==after[0xffc:] and b.read(0x200547ec,4)==fixed
        if case=='valid-update':
            assert after[0xfd4:0xffc]==expected and sum(row['bytes'] for row in stores)==40
        else:
            assert after==before and not stores
        rows.append(dict(case=case,backend=backend,result=result,instructions=stop.steps,
                         outside_40B_equal=True,checksum_equal=True,stores=stores,
                         record_after=after[0xfd4:0xffc].hex()))
C.save(a.name,dict(status='PASS',rows=rows,source=C.file_info(source),binding=binding,
                   expected_record=expected.hex(),native_edge='task_context normal return 0 only',
                   boundary='RAM update only. No claim about NAND programming.'))
