"""Frozen-image witnesses for the exact uncovered branch predicates."""
from pathlib import Path
import collections,hashlib,json,struct,sys,zlib
OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(OUT))
import differential as d
ex=d.ex


def main():
    shapes={}
    for gen in (116,117):
        b=(d.R1/f'container{gen}.dat').read_bytes()
        sections=[struct.unpack_from('>II',b,132+12*i) for i in range(7)]
        next_=256
        for off,z in sections:
            assert off==next_ and off%4==0 and z%4==0 and off+z<=len(b)
            next_+=z
        assert next_==len(b)
        assert 16<=sections[0][1]<=65536 and sections[1][1]<=2048
        assert sections[2][1]==192 and sections[3][1]==456 and sections[4][1]==3168 and sections[6][1]==1408
        bss=int.from_bytes(b[116:120],'big')
        assert 256<=len(b)<=98304 and bss<=114688-len(b)
        shapes[str(gen)]=dict(bytes=len(b),bss=bss,sections=sections,sha256=hashlib.sha256(b).hexdigest())
    b=d.IMAGE;u32=lambda off:int.from_bytes(b[off:off+4],'big')
    ids=[u32(u32(204)+32+4*k) for k in range(8)]
    metadata=[];styles=[];occupied=[];crc_witness=[]
    for m in range(3):
        direct=u32(156)+64*m;bank=u32(direct+16);meta=u32(direct+24)
        entry=d.EXPANDED[m]['entries'][3]
        expected=[0x94762b9f,0x1ff40907,0xf80736de][m]
        assert zlib.crc32(entry)==expected
        crc=zlib.crc32(d.EXPANDED[m]['map'])
        for off,z in zip(d.packed.OFFSETS,d.packed.LENGTHS):crc=zlib.crc32(entry[off:off+z],crc)
        pool=u32(direct+20);crc=zlib.crc32(b[pool+18:pool+20],crc)
        assert crc==[0xf09fe7b4,0xfb3fbcb2,0x95f3dca9][m]
        crc_witness.append(dict(unit=m,stock_crc32=hex(expected),map_stock_pin=hex(crc),entry_sha256=hashlib.sha256(entry).hexdigest()))
        for s in range(16):
            r=b[bank+32+64*s:bank+32+64*(s+1)];styles.append(r[3]);occupied.append(r[1])
            for k,pid in enumerate(ids):
                vals=[x if x<128 else x-256 for x in b[meta+28*s+3*k:meta+28*s+3*k+3]]
                lo,hi,default=vals
                assert hi>=0
                assert s!=3 or lo<=0<=hi
                assert pid not in (1,2,3,4) or -8<=lo<=hi<=8
                assert pid!=2 or r[3] not in (3,6) or vals==[0,0,0]
                metadata.append(dict(unit=m,slot=s+1,parameter=pid,lo=lo,hi=hi,default=default))
    assert set(styles)=={1} and set(occupied)=={1}
    proof=dict(shapes=shapes,parameter_ids=ids,records=48,styles=dict(collections.Counter(styles)),
               occupied=dict(collections.Counter(occupied)),metadata=metadata,crc_witness=crc_witness,
               domain='the two frozen engine/container generations; immutable recipe data during a private image lease')
    (OUT/'frozen-invariants.json').write_text(json.dumps(proof,indent=2)+'\n')
    runs=[]
    for g in (116,117):
        runner=ex.Runner(g);runner.crc_hooks()
        for m in range(3):
            raw,trust=ex.gate_seed();runner.write(ex.DATA,raw)
            # gate_seed only needs stock_crc32. The semantic API also requires
            # the pin tag that the real adapter's trust_init always writes.
            for i,pin in enumerate((0xf09fe7b4,0xfb3fbcb2,0x95f3dca9)):
                trust[80+48*i+16:80+48*i+20]=pin.to_bytes(4,'big')
            view=bytearray(84)
            struct.pack_into('>5I',view,0,ex.DATA,len(raw),117,int.from_bytes(raw[112:116],'big'),int.from_bytes(raw[116:120],'big'))
            for i in range(7):view[20+8*i:28+8*i]=raw[132+12*i:140+12*i]
            struct.pack_into('>HH',view,76,8,28);view[80:83]=bytes([m,1,0])
            runner.write(ex.DATA+0x20000,view);runner.write(ex.DATA+0x21000,trust);runner.write(ex.DATA+0x22000,bytes(84))
            runner.reset(0x117d00+m)
            semantic=runner.call('gxr2_semantic_validate',(ex.DATA+0x20000,ex.DATA+0x21000,ex.DATA+0x22000),steps=2000000)
            assert semantic['stop']['reason']=='return' and semantic['result']==0,(g,m,semantic['stop'],semantic['result'])
            runner.reset(0x117e00+m)
            expand=runner.call('gxr2_expand.constprop.0',(ex.DATA+0x22000,m,4),steps=500000)
            symbol=runner.e.symbols.get('expanded',runner.e.symbols.get('expanded.lto_priv.0'))
            actual=runner.read(ex.BASE+symbol['address'],552)
            assert expand['stop']['reason']=='return' and expand['result']==0 and actual==d.EXPANDED[m]['entries'][3]
            runs.append(dict(generation=g,unit=m,semantic_return=semantic['result'],semantic_steps=semantic['stop']['steps'],
                             expand_return=expand['result'],expand_steps=expand['stop']['steps'],entry_sha256=hashlib.sha256(actual).hexdigest(),
                             crc_boundary='exact zlib CRC specifications; semantic and expansion bodies execute their frozen M32R instructions'))
            print('validated',g,m,flush=True)
    (OUT/'frozen-helper-execution.json').write_text(json.dumps(runs,indent=2)+'\n')


if __name__=='__main__':main()
