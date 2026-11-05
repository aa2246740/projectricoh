"""Run final DAT instructions. C for iteration; independent Python for final proof."""
from pathlib import Path
import argparse
import json
import os
import struct
import sys
import zlib
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
D=C.D
def main():
    p=argparse.ArgumentParser();p.add_argument('--backend',choices=('c','python'),required=True);p.add_argument('--dataset',choices=('control','model'),default='control');a=p.parse_args()
    C.setup();C.DATASET=a.dataset;C.compute_gate('host-'+a.backend)
    os.environ['GXR_HARNESS_BACKEND']=a.backend
    sys.path.insert(0,str(C.ROOT/'tools/native_harness_c'));import python_backend as P
    P.CACHE=C.LOCAL/'host-decode'/a.backend
    Elf=C.load(C.ROOT/'firmware/stage2l_switch/tools/build.py','g158_probe_elf').Elf
    offsets=json.loads((C.LOCAL/'layout.json').read_text())['offsets'];rows=[]
    for profile in ('test','release'):
        raw=C.artifact(profile)['dat'].read_bytes()
        folder=C.artifact(profile)['build']
        elf=Elf(folder/'engine.elf');sym=elf.symbols
        assert sym['g']['size']==4
        engine=next(s for s in elf.sections if s['name']=='.engine');assert elf.content(engine)==raw[256:256+D.u32(raw,136)]
        base=0x21004000;arena=0x22010000
        image=bytearray(raw)+bytes(D.u32(raw,116))
        rel,n=D.sections(raw)[1]
        for at in range(rel,rel+n,8):
            patch,target=struct.unpack_from('>II',raw,at);struct.pack_into('>I',image,patch,base+target)
        cpu=P.PythonBackend();cpu.map(base,image,True);cpu.map(0x22000000,bytes(0x40000),True);cpu.set_reg('r15',0x2203fff0)
        cpu.write(base+sym['g']['value'],struct.pack('>I',arena))
        cpu.write(arena+offsets['g.data.image'],struct.pack('>I',base))
        def call(name,args,budget=200000):
            stop=cpu.call(base+sym[name]['value'],args,0x7ffffff0,budget)
            assert stop.reason=='return',(profile,name,stop)
            return cpu.get_reg('r0'),stop.steps
        area,_=D.effect_area(raw)
        for u in range(3):
            cpu.write(arena+offsets['g.data.unit'],bytes([u]))
            for i in range(D.u16(raw,area+10)):
                e=raw[area+32+32*i:area+64+32*i]
                if not e[18]>>u&1:continue
                ref=bytearray(56);ref[0]=u;ref[1]=e[0];ref[51]=i+1
                levels=struct.pack('>10h',100,0,0,0,0,0,0,0,0,0)
                cpu.write(0x22000200,ref);cpu.write(0x22000300,levels)
                _,steps=call('memory_build',[0x22000400,0x22000200,0x22000300,0])
                literal=b'GXR2'+bytes((3,64+i,u,1))+levels+raw[20:28]
                literal+=zlib.crc32(literal).to_bytes(4,'big')
                actual=cpu.read(0x22000400,40);assert actual==literal
                result,csteps=call('owned_record',[0x22000400]);assert result==1
                rows.append(dict(profile=profile,unit=C.UNITS[u],index=i,name=e[20:].split(b'\0')[0].decode(),record_sha256=C.sha(actual),memory_build_literal_equal=True,owned_record=1,instructions=steps+csteps,DAT_sha256=C.sha(raw)))
        # Test the shared maximum, not the visible ordinal. Unknown tails stay foreign.
        boundary=[]
        for code,expected in ((64,1),(64+47,1),(64+48,0),(127,0),(128,1),(159,1),(160,0),(0,0)):
            record=b'GXR2'+bytes((3,code,0,1))+struct.pack('>10h',100,0,0,0,0,0,0,0,0,0)+raw[20:28]
            record+=zlib.crc32(record).to_bytes(4,'big');cpu.write(0x22000400,record)
            result,steps=call('owned_record',[0x22000400]);assert result==expected
            boundary.append(dict(code=code,result=result,instructions=steps))
        C.save(C.receipt('host-boundary-'+profile+'-'+a.backend+'.json'),boundary)
    assert len(rows)==108
    C.save(C.receipt('host-'+a.backend+'.json'),dict(status='PASS',dataset=C.DATASET,backend=a.backend,rows=rows,cases=len(rows),layer='Final DAT memory_build and shared own-tail classifier; actual op5 service results are separately observed during MAIN/UI runs.'))
    print(json.dumps(dict(status='PASS',backend=a.backend,cases=len(rows))))
if __name__=='__main__':main()
