"""Explain every changed DAT byte and prove model integration changed only data."""
from collections import Counter
from pathlib import Path
import json
import struct
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
import records as R
D=C.D
def shifted_code(raw,elf,delta):
    image=bytearray(raw);changes=[]
    engine=next(s for s in elf.sections if s['name']=='.engine');bss=next(s for s in elf.sections if s['name']=='.bss')
    assert bss['va']==len(raw) and elf.content(engine)==raw[256:256+engine['size']]
    for sec in elf.sections:
        if sec['type']!=4:continue
        symbols=elf.symbol_tables[sec['link']]
        for pos in range(0,sec['size'],12):
            patch,info,addend=struct.unpack_from('>IIi',elf.bytes,sec['offset']+pos);symbol=symbols[info>>8];kind=info&255
            if symbol['section']!=bss['index']:continue
            value=symbol['value']+addend-(engine['va'] if kind in (63,64) else 0);old=D.u32(raw,patch)
            if kind==63:
                assert old&65535==((value+32768)>>16)&65535
                new=(old&0xffff0000)|(((value+delta+32768)>>16)&65535)
            elif kind==64:
                assert old&65535==value&65535
                new=(old&0xffff0000)|((value+delta)&65535)
            elif kind in (2,34):assert old==value;new=value+delta
            else:raise AssertionError((kind,patch))
            struct.pack_into('>I',image,patch,new);changes.append(dict(patch=patch,kind=kind,old=old,new=new,symbol=symbol['name']))
    return image[256:256+engine['size']],changes
def byte_audit(dataset,profile,Elf):
    current=C.artifact(profile,dataset);raw=current['dat'].read_bytes();elf=Elf(current['build']/'engine.elf')
    old=R.frozen(Path('firmware/package_v310_g156'+('_test' if profile=='test' else '')+'/GXRCE.DAT'))
    sections=D.sections(raw);prior=D.sections(old);labels=['UNEXPLAINED']*len(raw)
    def mark(at,n,label):labels[at:at+n]=[label]*n
    mark(0,256,'header_generation_lengths_entries_CRCS')
    mark(*sections[0],'linked_engine_alignment_or_pointer_data')
    eng=next(s for s in elf.sections if s['name']=='.engine')
    for name,symbol in sorted(elf.symbols.items(),key=lambda p:p[1]['size'],reverse=True):
        if symbol['section']==eng['index'] and symbol['size'] and symbol['value']>=256 and symbol['value']+symbol['size']<=256+eng['size']:
            mark(symbol['value'],symbol['size'],('linked_function:' if symbol['info']&15==2 else 'linked_constant:')+name)
    mark(*sections[1],'runtime_pointer_relocations')
    mark(*sections[2],'unit_directory_offsets')
    assert raw[sections[3][0]:sum(sections[3])]==old[prior[3][0]:sum(prior[3])]
    mark(*sections[3],'unchanged_native_maps_shifted')
    mark(*sections[4],'unchanged_recipe_identity_banks_shifted')
    for u in range(3):
        bank=D.u32(raw,D.u32(raw,156)+64*u+16);before=D.u32(old,D.u32(old,156)+64*u+16)
        assert all(raw[bank+i]==old[before+i] for i in range(1056) if i not in (*range(16,20),*range(28,32)))
        mark(bank+16,4,'bank_generation_157');mark(bank+28,4,'bank_header_CRC')
    manifest,slots,looks=R.read_manifest(current['records']);provenance=[{} for _ in D.LENGTHS]
    for u in range(3):
        entries=[('builtin-'+str(s),r) for s,r in slots[u].items()]+[(n,r) for n,r,_ in looks[u]]
        for name,record in entries:
            for k,o in zip(D.KINDS,D.OFFSETS):provenance[k].setdefault(record[o:o+D.LENGTHS[k]],[]).append(C.UNITS[u]+':'+name)
    shared=D.u32(raw,192);mark(shared,80,'row_pool_counts_offsets_CRCS')
    for u in range(3):
        directory=D.u32(raw,156)+64*u;at=D.u32(raw,directory+20);n=raw[directory+30]
        mark(at,16,'builtin_descriptor_header_CRC');mark(at+16,20*n,'builtin_record_metadata_and_row_references')
    for k,size in enumerate(D.LENGTHS):
        at=shared+D.u32(raw,shared+20+12*k);n=D.u16(raw,shared+16+12*k)
        for i in range(n):
            data=raw[at+i*size:at+(i+1)*size];assert data in provenance[k]
            mark(at+i*size,size,'record_row:'+str(k)+':'+','.join(provenance[k][data]))
        mark(at+n*size,D.align4(n*size)-n*size,'zero_row_pool_padding')
    area,n=D.effect_area(raw);count=D.u16(raw,area+10);mark(area,32,'Look_counts_masks_row_pool_CRCS')
    for i in range(count):
        entry=raw[area+32+32*i:area+64+32*i];name=entry[20:].split(b'\0')[0].decode()
        mark(area+32+32*i,32,'Look_descriptor_name_mask_crc_refs:'+name)
    at=area+32+32*D.u16(raw,area+8)
    for k,size in enumerate(D.LENGTHS):
        count=raw[area+16+k]
        for i in range(count):
            data=raw[at+i*size:at+(i+1)*size];assert data in provenance[k]
            mark(at+i*size,size,'Look_row:'+str(k)+':'+','.join(provenance[k][data]))
        mark(at+count*size,D.align4(count*size)-count*size,'zero_Look_pool_padding');at+=D.align4(count*size)
    assert at==area+n
    test=R.frozen(Path('firmware/package_v310_g156_test/GXRCE.DAT'));s7=sections[6]
    assert raw[s7[0]:sum(s7)]==test[D.u32(test,204):]
    mark(*s7,'unchanged_knobs_and_three_test_users_shifted')
    assert raw[48:112]==old[48:112] and raw[212:228]==old[212:228]
    out=C.receipt('byte-audit-'+profile+'.tsv');out.parent.mkdir(parents=True,exist_ok=True)
    changed=Counter();total=0
    with out.open('w') as stream:
        stream.write('offset\told\tnew\tclass\n')
        for i,value in enumerate(raw):
            before=old[i] if i<len(old) else None
            if before==value:continue
            label=labels[i];assert label!='UNEXPLAINED',i
            changed[label.split(':')[0]]+=1;total+=1
            stream.write(f'{i}\t{before if before is not None else "ADD"}\t{value}\t{label}\n')
    result=dict(status='PASS',dataset=dataset,profile=profile,old_DAT_sha256=C.sha(old),DAT_sha256=C.sha(raw),changed_or_added_bytes=total,
        removed_bytes=max(0,len(old)-len(raw)),classes=dict(changed),unexplained_bytes=0,native_maps_equal=True,original04_equal=True,
        section7_equals_g156_test=True,body_resident_ABI_equal=True,source_manifest_sha256=C.sha(current['records'].read_bytes()))
    C.save(C.receipt('byte-audit-'+profile+'.json'),result)
    return result
def main():
    C.setup();C.compute_gate('all-byte-audits')
    Elf=C.load(C.ROOT/'firmware/stage2l_switch/tools/build.py','g157_audit_elf').Elf
    frozen=json.loads((C.LOCAL/'engine-freeze.json').read_text())
    assert all(C.sha((C.ENGINE/p).read_bytes())==sha for p,sha in frozen['source_C'].items())
    proofs=[]
    for profile in ('test','release'):
        control=C.artifact(profile,'control');model=C.artifact(profile,'model')
        old=control['dat'].read_bytes();new=model['dat'].read_bytes();delta=len(new)-len(old)
        expected,fixups=shifted_code(old,Elf(control['build']/'engine.elf'),delta)
        assert bytes(expected)==new[256:256+D.u32(new,136)],profile
        assert D.u32(old,136)==D.u32(new,136)
        proofs.append(dict(profile=profile,status='PASS',control_DAT_sha256=C.sha(old),model_DAT_sha256=C.sha(new),file_delta=delta,
            normalized_engine_bytes_equal=True,only_BSS_address_fixups=fixups,source_C_identical=True))
    C.save(C.LOCAL/'data-only-proof.json',dict(status='PASS',profiles=proofs))
    results=[]
    for dataset in ('control','model'):
        C.DATASET=dataset
        for profile in ('test','release'):results.append(byte_audit(dataset,profile,Elf))
    print(json.dumps(dict(status='PASS',audits=[{k:r[k] for k in ('dataset','profile','changed_or_added_bytes','unexplained_bytes')} for r in results],data_only_code_equivalence=True)))
if __name__=='__main__':main()
