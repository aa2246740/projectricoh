"""Generate a private stress fixture, never a card/deployment artifact."""
import json
from pathlib import Path
import struct
import sys
import zlib
sys.path.insert(0,str(Path(__file__).resolve().parent))
from runtime import HERE,ROOT,LOCAL,guard,load,sha

def build():
    guard(); pack=load(ROOT/'firmware/card_container/pack.py','readonly_extractor')
    daily,old=pack.read_daily(); canonical=daily[3]
    modules=[pack.extract_module(c,canonical) for c in pack.MODULES]
    banks=[];pools=[];metas=[]
    for m in modules:
        records=[];entries=[m['entry']];meta=[]
        for slot in range(1,17):
            if slot==4:
                records.append(canonical); index=0;flags=3
            else:
                source=3 if slot==3 else 6 if slot in (6,7) else 1 if slot%2 else 2
                r=bytearray(daily[source-1]);name=f'{slot:02d} Host Stress'.encode()
                r[:4]=bytes((slot,1,len(name),r[3]));r[4:36]=name+bytes(32-len(name));r[49:51]=bytes(2)
                pack.p32(r,60,pack.crc(r[:60]));records.append(bytes(r))
                e=bytearray(old[source]);e[0]=slot
                # Explicit stress masks include C/D, row20 and native grain.
                if slot in (3,8):e[1]|=8
                if slot in (7,8):e[1]|=16
                if m['name']!='jlaunch':
                    # This is a transport/transaction fixture, not a colour fit.
                    e[115:211]=m['entry'][115:211]
                    e[116]=(e[116]&128)|min(127,(e[116]&127)+1)
                    pack.p32(e,16,pack.crc(e[115:211]))
                if slot in (7,8):
                    e[346:379]=old[1][82:115];pack.p32(e,276,pack.crc(e[346:379]))
                pack.p32(e,4,pack.crc(pack.identity(r)))
                index=len(entries);flags=1;entries.append(bytes(e))
            rec=records[-1];t=bytearray(28)
            for j in range(6):
                t[3*j:3*j+3]=bytes((248,8,0)) if not(j==1 and rec[3] in (3,6)) else bytes(3)
            t[24:28]=bytes((index,flags,2,0));meta.append(bytes(t))
        banks.append(pack.bank_blob(records,19));pools.append(pack.pool_blob(entries));metas.append(b''.join(meta))
    v2=load(ROOT/'firmware/card_container_v2/pack.py','readonly_v2_model_packer')
    for unit,m in enumerate(modules):
        m['records']=[banks[unit][32+64*i:96+64*i] for i in range(16)]
        m['entries']={e[0]:e for e in (pools[unit][16+448*i:16+448*(i+1)] for i in range(16))}
        m['refs']=list(range(1,17))
        m['ranges']=[[(int.from_bytes(t[j:j+1],'big',signed=True),
                       int.from_bytes(t[j+1:j+2],'big',signed=True),
                       int.from_bytes(t[j+2:j+3],'big',signed=True)) for j in range(0,24,3)]
                     for t in (metas[unit][28*i:28*(i+1)] for i in range(16))]
        m['crc_pin']=pack.crc(m['map']+m['raw_stock'])
        assert m['crc_pin']==v2.PIN_CRC32[unit]
        m['pin']=struct.pack('>I',m['crc_pin'])+bytes(28)
    result,trust,stats=v2.pack_model(modules,19,engine=bytes(16),resident_id=bytes([1])*32)
    (LOCAL/'host-stress.bin').write_bytes(result)
    (LOCAL/'host-trust.bin').write_bytes(trust)
    # Reuse the container worker's already-validated constructive row upper
    # bound. Normalize only the approved CRC binding cells and inert header.
    worst=bytearray((ROOT/'firmware/card_container_v2/local/verification/worst-local-only.dat').read_bytes())
    assert len(worst)-16==25216
    directory=v2.sections(worst)[2][0]
    worst[12:16]=bytes(4);worst[80:112]=bytes([1])*32;worst[256:272]=bytes(16)
    for unit,pin in enumerate(v2.PIN_CRC32):
        worst[directory+64*unit+32:directory+64*unit+64]=struct.pack('>I',pin)+bytes(28)
    (LOCAL/'host-max-data.bin').write_bytes(v2.seal(worst))
    (LOCAL/'fixture-stats.json').write_text(json.dumps(stats,indent=2)+'\n')
    # Independent Python expectations exercise the integration's effective-row
    # selection, six-axis vector and immutable-base recomputation.
    algorithm=load(ROOT/'research/recipe_tweak/r2/tweak.py','independent_tweak_oracle')
    vectors=[(0,0,0,0,0,0),(-8,0,-8,8,-8,8),(8,0,8,-8,8,-8),
             (2,5,-3,4,2,-3),(-5,-8,5,-5,-5,5)]
    golden=[]
    for unit in range(3):
        stock=pools[unit][16:464]
        for slot in (1,3,4,6,7,8):
            index=metas[unit][(slot-1)*28+24]
            entry=pools[unit][16+448*index:16+448*(index+1)]
            rows=[entry[o:o+n] if not bit or entry[1]&bit else stock[o:o+n]
                  for _,n,o,_,bit,_ in pack.ROWS]
            for vector in vectors:
                vector=list(vector)
                if banks[unit][32+(slot-1)*64+3] in (3,6): vector[1]=0
                levels=algorithm.Levels(*vector)
                computed,_=algorithm.apply(dict(rows=rows,mask=entry[1]|1,slot=slot),levels,320)
                wb=(9+vector[4],9-vector[5])
                record=bytes((unit,slot))+bytes(v&255 for v in vector)+bytes(2)+bytes(wb)+b''.join(computed)
                assert len(record)==420
                golden.append(record)
    (LOCAL/'host-golden.bin').write_bytes(b''.join(golden))
    (LOCAL/'fixture.json').write_text(json.dumps(dict(host_only=True,executable=False,bytes=len(result),
        note='Engine bytes are inert. No card filename or deployment wrapper is emitted.',
        source_hashes={str(pack.OFFICIAL/(m['name']+'3')):sha(pack.OFFICIAL/(m['name']+'3')) for m in modules},
        units=[dict(name=m['name'],stock_crc=m['evidence']['stock_entry_crc32']) for m in modules]),indent=2)+'\n')
    print(f'host fixture: {len(result)} bytes, 3 units x 16 occupied slots')
if __name__=='__main__':build()
