"""Check the final data identity, protected inputs and source invariants."""
from pathlib import Path
import json
import struct
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import ROOT,OUT,TREE,DAT,BASE_DAT,save,file_sha,sha,load

def u32(b,at):return struct.unpack_from('>I',b,at)[0]

def main():
    final=DAT.read_bytes();base=BASE_DAT.read_bytes()
    assert u32(final,28)==122 and len(final)<=65536
    assert final[48:112]==base[48:112] and final[212:228]==base[212:228]
    binary=(TREE/'candidate/local/full-r13/engine.bin').read_bytes()
    assert final[u32(final,132):u32(final,132)+u32(final,136)]==binary
    reader=load(ROOT/'tools/native_harness/image_loader.py','final_elf')
    elf=reader.Elf(TREE/'candidate/local/full-r13/engine.elf')
    assert next(s['data'] for s in elf.sections if s['name']=='.engine')==binary
    modules=[]
    for i,name in enumerate(('jlaunch','qlaunch','l08firm')):
        fd=u32(final,156)+64*i;bd=u32(base,156)+64*i
        record=dict(unit=name)
        final_bank=final[u32(final,fd+16):u32(final,fd+16)+32]
        base_bank=base[u32(base,bd+16):u32(base,bd+16)+32]
        assert final_bank[:16]==base_bank[:16] and final_bank[20:28]==base_bank[20:28]
        assert u32(final_bank,16)==122 and u32(base_bank,16)==120
        for field,skip,size,label in ((12,0,152,'map'),(16,32,16*64,'records'),(24,0,16*28,'metadata')):
            a=final[u32(final,fd+field)+skip:u32(final,fd+field)+skip+size]
            b=base[u32(base,bd+field)+skip:u32(base,bd+field)+skip+size]
            assert a==b,(name,label)
            record[label+'_sha256']=sha(a)
        modules.append(record)
    assert (TREE/'candidate/local/full-r13/effective-rows.bin').read_bytes()==(ROOT/'firmware/engine_v42_ux/candidate/local/full-r13/effective-rows.bin').read_bytes()
    source=TREE/'candidate/containers/product'
    adapter=(source/'adapter.c').read_text();core=(source/'src/firmware/engine/core/eng_core.c').read_text()
    assert adapter.count('while(++round<16)')==2
    assert adapter.count('n.failed=1;')==1
    assert 'if(n.failed||!eng_uncertain()||!eng_write_started())return;' in adapter
    assert 'if(r.detail==1)g.write_started=1;' in core
    assert 'else if(tentative&&!g.write_started)g.uncertain=0;' in core
    assert 'for(attempt=0;attempt<4;' in core and 'for(attempt=0;attempt<2;' in core
    save('final-data-check.json',dict(status='PASS',bytes=len(final),sha256=sha(final),modules=modules,
         elf_and_binary_match_dat=True,engine_sha256=sha(binary),
         resident_build_id=final[80:112].hex(),abi_id=final[212:228].hex(),
         source_invariants=dict(merge_rounds=16,confirmed_attempts=4,stock_attempts=2,actual_w_receipt=True),
         card_files=[p.name for p in sorted(DAT.parent.iterdir())]))
    frozen=json.loads((OUT/'inputs-before.json').read_text())
    changes=[]
    for row in frozen['files']:
        name=bytes.fromhex(row['path_hex']).decode();p=ROOT/name
        if not p.is_file() or file_sha(p)!=row['sha256']:changes.append(row['path_hex'])
    save('protected-input-check.json',dict(status='PASS' if not changes else 'FAIL',files=len(frozen['files']),changed_paths_hex=changes))
    assert not changes,changes
    print('PASS final recipe data and protected inputs',len(frozen['files']),sha(final),flush=True)

if __name__=='__main__':main()
