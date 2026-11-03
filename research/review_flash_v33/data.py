"""Compare complete decoded records using the earlier independent reader and C."""
import difflib
import hashlib
import json
import struct
import sys
import zlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import review as c
import artifacts as a
from host import module, HOST, FINAL, PRODUCT, ACCEPT, RES

def main():
    prior=module(c.ROOT/'research/review_full_r4/review.py','frozen_independent_expander')
    inputs={109:c.ROOT/'firmware/engine_v33d/local/full-r7',110:ACCEPT/'local/full-r8',111:FINAL}
    decoded={}
    for generation,folder in inputs.items():
        raw=(folder/'GXRCE.DAT').read_bytes();decoded[generation]=prior.parse(raw)
        assert struct.unpack_from('>I',raw,28)[0]==generation
        out=c.run([HOST/'expand',folder/'GXRCE.DAT',folder/'trust.bin'],'data/expand-'+str(generation)+'.txt')
        vectors={}
        for line in out.splitlines():
            m,s,*pieces=line.split();vectors[int(m),int(s)]=tuple(bytes.fromhex(x) for x in pieces)
        assert len(vectors)==48
        for key,r in decoded[generation]['slots'].items():
            assert vectors[key][:3]==(r['entry'],r['record'],r['binding'])
        decoded[generation]['c_vectors']=vectors
        assert decoded[generation]['golden']==(folder/'effective-rows.bin').read_bytes()
    changed=[];rows=[];source=c.ROOT/'research/bw03_standard_mode/local/candidate'
    for key,new in decoded[111]['slots'].items():
        vector=decoded[111]['c_vectors'][key]
        assert decoded[109]['c_vectors'][key]==decoded[110]['c_vectors'][key]
        if vector!=decoded[110]['c_vectors'][key]:
            changed.append(key);assert key in ((0,3),(2,3))
            src=source/('DEEPTBL_50mm_bw03_standard.DAT' if key[0]==0 else 'DEEPTBL_mount_bw03_standard.DAT')
            raw=src.read_bytes();entry=next(raw[16+448*i:16+448*(i+1)] for i in range(8) if raw[16+448*i]==3)
            assert new['entry']==entry and new['record']==(source/'recipe03.record64.bin').read_bytes()
            record=new['record'];identity=record[2:3]+record[4:36]+record[3:4]+record[36:51]
            assert record[3]==1 and record[36:51]==bytes(15)
            assert zlib.crc32(identity)==0x8015cba7
            assert new['entry'][1]==1 and new['entry'][445:447]==struct.pack('>H',2)
            # Both 3x3 matrices retain luminance, and both chroma rows are zero.
            entry=new['entry']
            for start in (216,244):
                # Each type-28 row is 28B. Six chroma coefficients follow luminance.
                assert entry[start+6:start+18]==bytes(12),(key,start)
            assert entry[115:211]==bytes(96)
            # Reconstruct the change from the old effective 03, without the new-data generator.
            old=decoded[110]['slots'][key]['entry'];expected=bytearray(old)
            matrix_source=old if old[1]&1 else decoded[110]['slots'][key[0],4]['entry']
            expected[1]|=1;expected[4:8]=struct.pack('>I',0x8015cba7)
            expected[115:211]=bytes(96);expected[216:272]=matrix_source[216:272]
            for start in (216,244):expected[start+6:start+18]=bytes(12)
            for crc_offset,start,length in ((16,115,96),(212,216,56)):
                struct.pack_into('>I',expected,crc_offset,zlib.crc32(expected[start:start+length]))
            assert new['entry']==expected
        rows.append(dict(unit=key[0],slot=key[1],label=new['record'][4:4+new['record'][2]].decode(),
            record_offset=new['record_offset'],descriptor_offset=new['descriptor_offset'],
            entry_sha256=hashlib.sha256(new['entry']).hexdigest(),changed=key in changed))
    assert changed==[(0,3),(2,3)]
    for unit in (0,2):
        for slot in range(1,9):
            record=decoded[111]['slots'][unit,slot]['record']
            assert record[3]==1 and record[36:51]==bytes(15)
    engine=a.Elf(FINAL/'engine.elf');raw=(a.PACKAGE/'SD_ROOT/GXRCE.DAT').read_bytes()
    section=engine.by_name['.engine'];o,n=decoded[111]['sections'][0]
    assert raw==(FINAL/'GXRCE.DAT').read_bytes()
    assert raw[o:o+n]==engine.data(section)==(FINAL/'engine.bin').read_bytes()
    assert engine.by_name['.bss']['va']==len(raw) and engine.by_name['.bss']['size']==struct.unpack_from('>I',raw,116)[0]
    manifest=json.loads((FINAL/'layout.json').read_text())
    for path,want in {**manifest['sources'],**manifest['tools']}.items():assert c.digest(c.ROOT/path)==want,path
    # Every source compiled into this review's engine host objects belongs to the final layout source list.
    compiled=json.loads((c.LOCAL/'host-source-proof.json').read_text())
    for r in compiled:
        if r['source'] in manifest['sources']:assert r['sha256']==manifest['sources'][r['source']]
    changes={};patch=[]
    for base in ('containers/product','engine_services'):
        for f in sorted((ACCEPT/base).rglob('*')):
            if not f.is_file() or f.suffix not in ('.c','.h','.S','.ld'):continue
            rel=f.relative_to(ACCEPT);old=c.ROOT/'firmware/engine_v33d'/rel
            if old.is_file() and f.read_bytes()!=old.read_bytes():
                changes[str(rel)]=dict(old=c.digest(old),new=c.digest(f))
                patch+=list(difflib.unified_diff(old.read_text().splitlines(True),f.read_text().splitlines(True),fromfile='r7/'+str(rel),tofile='r9/'+str(rel)))
    (c.LOCAL/'engine-source.patch').write_text(''.join(patch))
    # Target-only sizeof object, not an engine/resident/firmware rebuild.
    layout=c.HERE/'target_layout.c';obj=c.LOCAL/'target-layout.o'
    c.run([c.GCC,'-std=c11','-Os','-ffreestanding','-fno-builtin','-m32r','-mmodel=medium','-msdata=none','-G0',
        '-DPN_CORE_HEADER="../core/eng_core.h"','-DPN_GXTS_SHARED_PARAMETER',
        '-I',ACCEPT,'-c',layout,'-o',obj],'data/layout-compile.log')
    size_elf=a.Elf(obj);sym=size_elf.symbols['review_target_sizes'];s=size_elf.sections[sym['section']]
    p=s['off']+sym['va']-s['va'];sizes=list(struct.unpack_from('>8I',size_elf.raw,p))
    work,gxts,store,load,ui,integrated,session,overhead=sizes
    main_request=overhead+((len(raw)+engine.by_name['.bss']['size']+3)&~3)
    # Main + permanently retained load-work + private session-work + UI snapshot, each with a 12B native header.
    steady=main_request+load+work+ui+4*12
    first_install=main_request+load+2*65536+4*12
    with_snapshot=first_install+ui+12
    c.write('data.json',dict(status='PASS',complete_vectors=144,changed=changed,unchanged_final_slots=46,
        slots=rows,engine_bytes=n,file_bytes=len(raw),bss_bytes=engine.by_name['.bss']['size'],
        source_hashes_verified=len(manifest['sources']),tools_verified=len(manifest['tools']),source_differences=changes,
        target_sizes=dict(zip(('SessionWork','PnGxts','PsStore','RvLoadWork','RvUiSnapshot','Integrated','RvSession','RV_BLOCK_OVERHEAD'),sizes)),
        main_request=main_request,steady_with_ui_native_headers=steady,install_peak_native_headers=first_install,
        install_with_existing_ui=with_snapshot,device_free_heap_measured=False))
    print('PASS Python/C vectors=144; changed only two 03; main request',main_request,'install peak',first_install,flush=True)

if __name__=='__main__':main()
