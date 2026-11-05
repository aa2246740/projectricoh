"""Audit final bytes independently of g156's build/report/selection receipts."""
from pathlib import Path
import difflib
import dataclasses
import json
import struct
import sys
import zlib
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
C.setup()
D=C.DF
reader=C.load(C.ROOT/'firmware/stage2l_switch/tools/build.py','review_g156_elf')

def source_files(folder):
    return {str(p.relative_to(folder)):p for p in folder.rglob('*')
            if p.is_file() and 'local' not in p.relative_to(folder).parts
            and p.suffix in ('.c','.h','.S','.ld')}

a,b=source_files(C.BASE),source_files(C.ENGINE)
assert a.keys()==b.keys(),('source file set differs',a.keys()^b.keys())
source_changes=[]
patch=[]
for name in sorted(a):
    before,after=a[name].read_bytes(),b[name].read_bytes()
    if before!=after:
        source_changes.append(name)
        assert before.replace(b'build_number==155',b'build_number==156').replace(b'build_number!=155',b'build_number!=156')==after,name
        patch.extend(difflib.unified_diff(before.decode().splitlines(True),after.decode().splitlines(True),fromfile='g155c/'+name,tofile='g156/'+name))
assert len(source_changes)==3,source_changes
(C.HERE/'evidence/source-delta.patch').write_text(''.join(patch))
registry=json.loads((C.RECORDS/'candidate_registry.json').read_text())
reg={(r['unit'],r['name']):r for r in registry['profiles']}
capacity=json.loads((C.RECORDS/'capacity_safe_profile.json').read_text())
start={(r['unit'],r['name']) for r in capacity['selected']}
extras={('a12-50',n) for n in ('03 HC BW','07 L-Chr','08 L-Viv','Tri-X 400','HNCS HiCon')}
trust=json.loads((C.ROOT/'firmware/resident_v310_g155/local/resident/trust.json').read_text())
codec=C.load(C.ROOT/'studio/src/gxr_studio/camdata/datcodec.py','review_g156_codec')
all_rows=[]
all_records=[]

def entries(raw,unit):
    rows=[]
    for slot,name in enumerate(C.BUILTINS,1):
        rows.append(dict(kind='builtin',slot=slot,name=name,data=D.expand(raw,unit,slot)))
    area,_=D.effect_area(raw)
    visible=0
    for idx in range(D.u16(raw,area+10)):
        at=area+32+32*idx;e=raw[at:at+32]
        if e[18]>>unit&1:
            visible+=1
            rows.append(dict(kind='look',slot=visible,base=e[0],name=e[20:].split(b'\0')[0].decode(),
                             data=D.expand_effect(raw,idx),global_index=idx,mask=e[18]))
    assert visible==10
    return rows

for profile in ('release','test'):
    build='boot-on' if profile=='test' else 'boot-off'
    folder=C.PACKAGES[profile]
    raw=(folder/'GXRCE.DAT').read_bytes()
    old=(C.ROOT/('firmware/package_v310_g155c'+('_test' if profile=='test' else ''))/'GXRCE.DAT').read_bytes()
    sections,previous=D.sections(raw),D.sections(old)
    delta=len(raw)-len(old)
    assert raw[32:112]==old[32:112] and raw[212:228]==old[212:228]
    assert raw[80:112].hex()==trust['resident_build_id'] and raw[212:228].hex()==trust['resident_abi_id']
    assert raw[48:80].hex()==trust['body_sha256']
    assert D.u32(raw,28)==156 and D.u32(old,28)==155
    assert sections[0]==previous[0]
    same_parts=[]
    for idx in (1,3,4,6):
        at,n=sections[idx];old_at,old_n=previous[idx]
        assert n==old_n and raw[at:at+n]==old[old_at:old_at+old_n],(profile,idx+1)
        same_parts.append(idx+1)
    current=reader.Elf(C.ENGINE/'candidate/local'/build/'engine.elf')
    baseline=reader.Elf(C.BASE/'candidate/local'/build/'engine.elf')
    eng=next(s for s in baseline.sections if s['name']=='.engine')
    bss=next(s for s in baseline.sections if s['name']=='.bss')
    neweng=next(s for s in current.sections if s['name']=='.engine')
    newbss=next(s for s in current.sections if s['name']=='.bss')
    assert eng['size']==neweng['size']==D.u32(raw,136)
    assert current.content(neweng)==(C.ENGINE/'candidate/local'/build/'engine.bin').read_bytes()==raw[256:256+eng['size']]
    assert baseline.content(eng)==old[256:256+eng['size']]
    assert bss['va']==len(old) and newbss['va']==len(raw) and bss['size']==newbss['size']==D.u32(raw,116)
    allowed=set();bss_relocations=[]
    expected=bytearray(old)
    for sec in baseline.sections:
        if sec['type']!=4:continue
        syms=baseline.symbol_tables[sec['link']]
        newsec=next(s for s in current.sections if s['name']==sec['name'])
        assert baseline.content(sec)==current.content(newsec)
        for pos in range(0,sec['size'],12):
            at,info,addend=struct.unpack_from('>IIi',baseline.bytes,sec['offset']+pos)
            sym=syms[info>>8];kind=info&255
            if sym['section']!=bss['index']:continue
            value=sym['value']+addend-(eng['va'] if kind in (63,64) else 0)
            before=D.u32(old,at);after=D.u32(raw,at)
            if kind==63:
                assert before&65535==((value+32768)>>16)&65535
                wanted=(before&0xffff0000)|(((value+delta+32768)>>16)&65535)
            elif kind==64:
                assert before&65535==value&65535
                wanted=(before&0xffff0000)|((value+delta)&65535)
            else:raise AssertionError(('unexpected BSS relocation',kind,at))
            assert after==wanted,(profile,hex(at),hex(after),hex(wanted))
            struct.pack_into('>I',expected,at,wanted)
            allowed.update(range(at,at+4))
            bss_relocations.append(dict(DAT_offset=at,kind=kind,old_word=hex(before),new_word=hex(after),symbol=sym['name']))
    residual=[i for i in range(256,256+eng['size']) if expected[i]!=raw[i]]
    engine_offsets=[0xffc,0x9f5c,0xa3a0] if profile=='release' else [0x11ec,0xaab8,0xaefc]
    assert residual==[x+259 for x in engine_offsets],(profile,residual)
    for off in residual:
        assert old[off]==0x65 and raw[off]==0x64
    alloc=7628+((len(raw)+newbss['size']+3)&~3)
    assert alloc<=107612 and eng['size']<=69632
    manifest=json.loads((folder/'MANIFEST').read_text())
    assert alloc==manifest['main_request'] and manifest['dat_sha256']==C.sha(raw)
    assert (folder/'SD_ROOT/GXRCE.DAT').read_bytes()==raw
    effects=D.strict_effects(raw)
    old_fx,_=D.effect_area(old);new_fx,_=D.effect_area(raw)
    collisions=[]
    for i in range(min(D.u16(old,old_fx+10),D.u16(raw,new_fx+10))):
        x=old[old_fx+32+32*i:old_fx+64+32*i]
        y=raw[new_fx+32+32*i:new_fx+64+32*i]
        old_name=x[20:].split(b'\0')[0].decode();new_name=y[20:].split(b'\0')[0].decode()
        if old_name!=new_name:
            for unit in range(3):
                if x[18]&y[18]&(1<<unit):
                    collisions.append(dict(unit=C.UNITS[unit],record_index=hex(0x40+i),old_name=old_name,new_name=new_name,
                        old_DAT_CRC_pair=old[20:28].hex(),new_DAT_CRC_pair=raw[20:28].hex()))
    assert C.sha((C.ORIGINAL/'local/inputs/research/recipe_redo_r1/candidate_registry.json').read_bytes())==C.sha((C.RECORDS/'candidate_registry.json').read_bytes())
    changed=set();kept=0;identity_only=0
    for unit,unit_name in enumerate(C.UNITS):
        before,after=entries(old,unit),entries(raw,unit)
        assert [(r['kind'],r['slot'],r['name']) for r in before]==[(r['kind'],r['slot'],r['name']) for r in after]
        for x,y in zip(before,after):
            olddata,newdata=x['data'],y['data']
            row={k:v for k,v in y.items() if k!='data'}
            row.update(profile=profile,unit=unit_name,old_sha256=C.sha(olddata),sha256=C.sha(newdata))
            if olddata==newdata:
                row['action']='identical';kept+=1
            elif olddata[:4]+olddata[8:]==newdata[:4]+newdata[8:]:
                row['action']='identity_CRC_only';identity_only+=1
                row['changed_offsets']=[i for i,(a,b) in enumerate(zip(olddata,newdata)) if a!=b]
                assert set(row['changed_offsets'])<=set(range(4,8))
            else:
                key=unit_name,y['name'];changed.add(key);r=reg[key]
                original=(C.RECORDS/r['record_file']).read_bytes()
                frozen=(C.ORIGINAL/'local/inputs/research/recipe_redo_r1'/r['record_file']).read_bytes()
                assert len(original)==552 and original==frozen==newdata,(profile,key)
                assert C.sha(original)==r['record_sha256']
                row.update(action='replace',registry_file=r['record_file'],registry_sha256=r['record_sha256'])
            if y['kind']=='look':
                base=D.descriptor(raw,unit,y['base'])
                assert newdata[1]==base[1],(profile,unit_name,y['name'],'flags')
                row.update(flags=newdata[1],base_flags=base[1])
            all_records.append(row)
        assert D.expand(raw,unit,4)==D.expand(old,unit,4)
    assert changed==(start|extras if profile=='release' else start),(profile,changed)
    try:
        codec.parse(raw)
    except codec.UnsupportedGeneration as exc:
        studio=dict(status='REJECT',exception=type(exc).__name__,message=str(exc))
    else:raise AssertionError('Studio unexpectedly supports generation 156')
    assert codec.pack(codec.parse(old))==old
    codec.PROFILES[156]=dataclasses.replace(codec.PROFILES[155],generation=156)
    try:
        codec.parse(raw)
    except codec.DatError as exc:
        studio['register_156_only']=dict(status='REJECT',exception=type(exc).__name__,message=str(exc))
    else:raise AssertionError('registering generation alone unexpectedly suffices')
    finally:
        del codec.PROFILES[156]
    all_rows.append(dict(profile=profile,DAT_sha256=C.sha(raw),bytes=len(raw),growth=delta,
        code_bytes=eng['size'],BSS_bytes=newbss['size'],BSS_start=newbss['va'],main_request=alloc,headroom=107612-alloc,
        identical_parts=same_parts,sections=sections,old_sections=previous,
        BSS_relocation_count=len(bss_relocations),changed_BSS_words=sum(x['old_word']!=x['new_word'] for x in bss_relocations),
        BSS_relocations=bss_relocations,generation_instruction_engine_offsets=[hex(x)for x in engine_offsets],
        generation_changed_DAT_byte_offsets=[hex(x)for x in residual],other_code_changes=0,swapped=len(changed),
        retained_exact=kept,retained_identity_CRC_only=identity_only,effect_pool=effects,Studio=studio,
        old_index_collisions=collisions,
        manifest_acceptance_verdict=manifest.get('acceptance_verdict'),manifest_status=manifest.get('status')))
C.save(C.HERE/'evidence/static.json',dict(status='PASS',source_files=len(a),source_changes=source_changes,packages=all_rows))
C.save(C.HERE/'evidence/records.json',dict(status='PASS',rows=all_records))
print(json.dumps(dict(status='PASS',source_changes=source_changes,packages=[{k:r[k]for k in ('profile','growth','swapped','retained_exact','retained_identity_CRC_only','main_request','headroom','BSS_relocation_count','changed_BSS_words','Studio')}for r in all_rows]),ensure_ascii=False))
