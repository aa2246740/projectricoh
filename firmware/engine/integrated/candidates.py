#!/usr/bin/env python3
"""Build real local-only containers from frozen owner inputs and final PIC ELF."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import pack
from runtime import HERE, ROOT, LOCAL, SRC, guard, sha
import build

def models(huzi=False):
    modules=pack.initial_model()
    for m in modules:
        for ranges in m['ranges']:
            ranges[4:6]=[(0,0,0)]*2
    evidence=[]
    if huzi:
        base=ROOT/'research/huzi_luts'
        index=json.loads((base/'local/best_candidates/INDEX.json').read_text())
        rows=index['entries'] if 'entries' in index else index['candidates']
        for slot,name,look in ((7,'07 Chrome','Leica Chrome'),(8,'08 Vivid','Leica VIVID')):
            item=next(r for r in rows if r['look']==look)
            assert item['basis']=='panasonic_s1rii' and item['concentration']==70 and item['variant']=='safe'
            folder=base/item['path'];source=folder/'candidate.entry';meta=json.loads((folder/'candidate.json').read_text())
            entry=bytearray(source.read_bytes());identity=bytes.fromhex(meta['identity49_hex'])
            assert len(entry)==448 and len(identity)==49 and sha(source)==meta['entry_sha256']
            assert pack.u32(entry,4)==pack.crc(identity) and entry[0]==5
            record=bytearray(64);label=name.encode('ascii');record[:4]=bytes((slot,1,len(label),identity[33]))
            record[4:4+len(label)]=label;record[36:51]=identity[34:49]
            pack.p32(record,60,pack.crc(record[:60]));entry[0]=slot
            pack.p32(entry,4,pack.crc(pack.identity(record)))
            m=modules[0];m['records'][slot-1]=bytes(record);m['entries'][slot]=bytes(entry);m['refs'][slot-1]=slot
            evidence.append(dict(slot=slot,name=name,source=str(source.relative_to(ROOT)),source_sha256=sha(source),
                                 original_identity49=identity.hex(),rebound_identity49=pack.identity(record).hex(),
                                 entry_sha256=hashlib.sha256(entry).hexdigest(),basis=item['basis'],percent=70,variant='safe'))
    return modules,evidence

def identity():
    trust_path=ROOT/'firmware/resident_slim/local/trust.c'
    # Capture the current upstream resident identity explicitly, never fabricate
    # a product build identity from the host fixture or integrated test loader.
    raw=trust_path.read_text()
    import re
    fields=re.search(r'const RvTrust rv_trust=\{\{([^}]*)\},\{([^}]*)\},\{([^}]*)\}\}',raw)
    assert fields,'resident trust source not recognized'
    body,resident,abi=[bytes(int(v) for v in g.split(',')) for g in fields.groups()]
    assert [len(body),len(resident),len(abi)]==[32,32,16]
    assert body.hex()==pack.v1.SOURCE_HASHES['ilaunch3']
    (LOCAL/'resident-trust.c').write_text(raw)
    return body,resident,abi

def main():
    guard();body,resident,abi=identity();summary=[]
    for variant,huzi,generation in (('base',False,101),('huzi',True,102)):
        modules,evidence=models(huzi)
        inert,_,stats=pack.pack_model(modules,generation)
        data_bytes=len(inert)-16-256
        layout=build.build(data_bytes,lto=True)
        out=LOCAL/'candidates'/variant;out.mkdir(parents=True,exist_ok=True)
        engine=(LOCAL/'m32r-lto/engine.bin').read_bytes()
        relraw=(LOCAL/'m32r-lto/reloc.bin').read_bytes()
        rel=[struct.unpack_from('>II',relraw,i) for i in range(0,len(relraw),8)]
        blob,trust,stats=pack.pack_model(modules,generation,engine=engine,relocations=rel,bss=layout['bss_bytes'],
                                        entry=layout['entries']['ig_bootstrap'],resident_id=resident,abi_id=abi)
        assert len(blob)==layout['file_bytes']
        pack.write_bytes(out/'GXRCE.DAT',blob);pack.write_bytes(out/'trust.bin',trust)
        pack.write_json(out/'layout.json',layout)
        pack.write_bytes(out/'engine.bin',engine);pack.write_bytes(out/'reloc.bin',relraw)
        for m in modules:
            for slot,e in m['entries'].items():pack.write_bytes(out/'expanded'/m['name']/(f'{slot:02}.entry'),e)
            pack.write_bytes(out/'extracted'/m['name']/'map.bin',m['map'])
        golden=bytearray()
        for m in modules:
            for owner in m['refs']:
                entry=m['entries'][owner];stock=m['entries'][4]
                for _,count,offset,_,mask,_ in pack.v1.ROWS:
                    effective=entry if not mask or entry[1]&mask else stock
                    golden+=effective[offset:offset+count]
                golden+=struct.pack('>H',0 if entry[1]&4 else 2)
        assert len(golden)==3*16*410
        pack.write_bytes(out/'effective-rows.bin',golden)
        manifest=dict(variant=variant,build=generation,**stats,**{'bss_bytes':layout['bss_bytes'],
                      'image_bss_bytes':len(blob)+layout['bss_bytes'],'sha256':sha(out/'GXRCE.DAT'),
                      'resident_build_id':resident.hex(),'abi_id':abi.hex(),'huzi':evidence,
                      'body_sha256':body.hex(),'camera_acceptance':False,'deployable':False,
                      'resident_changes_required':True,'wb_axes_enabled':False})
        pack.write_json(out/'manifest.json',manifest);pack.checksums(out);summary.append(manifest)
    pack.write_json(LOCAL/'candidates.json',summary)
    print(json.dumps([{k:m[k] for k in ('variant','build','file_bytes','engine_bytes','bss_bytes','image_bss_bytes')} for m in summary]))

if __name__=='__main__':main()
