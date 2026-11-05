"""Attribute every byte to BOOT admission, generation, linking, or unchanged data."""
from collections import Counter
from pathlib import Path
import json,re,struct,sys
sys.path.insert(0,str(Path(__file__).resolve().parent));import common as C
C.setup();C.DATASET='model';C.compute_gate('g158-byte-audit');out=C.LOCAL
Elf=C.load(C.ROOT/'firmware/stage2l_switch/tools/build.py','g158_audit_elf').Elf
oldcode=(C.ROOT/'research/g157/fix_r1_audit.py').read_text()
helpers=oldcode[oldcode.index('def functions('):oldcode.index('audits=[]')]
helpers=helpers.replace("result[name]=C.sha(json.dumps(parts).encode())","result[name]=parts")
exec(compile(helpers,'g157-audit-helpers','exec'),globals())
frozen=json.loads((out/'freeze.json').read_text());changes=[]
expected={'adapter.c','boot_adapter.inc.c','diagnostic.c','diagnostic.h','pack.py','ui_v2_data.c','src/firmware/card_container_v2/gate.c','src/firmware/engine/core/eng_data.c'}
for name,digest in frozen['source_sha256'].items():
    old=(out/'before/source'/name).read_bytes();new=(C.PRODUCT/name).read_bytes();assert C.sha(old)==digest
    generation=re.sub(rb'\b157\b',b'158',old).replace(b'g157',b'g158').replace(b'G157',b'G158')
    if name!='boot_adapter.inc.c':assert new==generation,(name,'non-generation source delta')
    else:
        begin=lambda b:b.index(b'    /* ',b.index(b'if(RV_WORD(0x205d9bf8)'))
        end=lambda b:b.index(b'    if(RV_BYTE(0x205d9aa3))')
        assert new[:begin(new)]==generation[:begin(generation)] and new[end(new):]==generation[end(generation):]
    if new!=old:changes.append(dict(file=name,old_sha256=digest,new_sha256=C.sha(new)))
assert {r['file'] for r in changes}==expected
for p in (C.ENGINE/'resident').iterdir():
    if p.is_file():assert p.read_bytes()==(C.BASE/'resident'/p.name).read_bytes()
assert (C.PRODUCT/'src/firmware/engine/core/eng_core.c').read_bytes()==(out/'before/source/src/firmware/engine/core/eng_core.c').read_bytes()
assert (C.PRODUCT/'src/firmware/engine/core/eng_boot.inc.c').read_bytes()==(out/'before/source/src/firmware/engine/core/eng_boot.inc.c').read_bytes()
def generation_only(a,b):
    if len(a)!=len(b):return False
    for x,y in zip(a,b):
        if x==y:continue
        if x[:3]!=y[:3] or x[1]!='bytes':return False
        bx,by=bytes.fromhex(x[3]),bytes.fromhex(y[3])
        # GCC compares the build by add3 #-157 / #-158 before a zero test.
        if len(bx)==len(by) and len(bx)>=2 and bx[:-2]==by[:-2] and bx[-2:]==b'\xff\x63' and by[-2:]==b'\xff\x62':continue
        if any(u!=v and (u,v) not in ((157,158),(ord('7'),ord('8'))) for u,v in zip(bx,by)):return False
    return True
audits=[]
for profile in C.PACKAGES:
    oldpath=out/'before'/profile;old=(oldpath/'GXRCE.DAT').read_bytes();art=C.artifact(profile);raw=art['dat'].read_bytes()
    before=C.D.sections(old);after=C.D.sections(raw);oldelf=Elf(oldpath/'build/engine.elf');elf=Elf(art['build']/'engine.elf')
    oldmanifest=json.loads((oldpath/'records.json').read_text());manifest=json.loads(art['records'].read_text())
    oldmanifest['schema']='g158-record-manifest/1';oldmanifest['generation']=158;assert oldmanifest==manifest
    for i in (3,5,6):
        x,n=before[i];y,m=after[i];assert n==m and old[x:x+n]==raw[y:y+m],(profile,i)
    x,n=before[4];y,m=after[4];assert n==m==3168;bank=bytearray(raw[y:y+m])
    for u in range(3):
        assert C.D.u32(bank,1056*u+16)==158
        struct.pack_into('>I',bank,1056*u+16,157);struct.pack_into('>I',bank,1056*u+28,C.D.crc(bank[1056*u:1056*u+28]))
    assert bank==old[x:x+n],profile+' bank generation only'
    x,n=before[2];y,m=after[2];assert n==m;directory=bytearray(raw[y:y+m])
    for u in range(3):
        for field,index in ((12,3),(16,4),(20,5),(24,6)):
            struct.pack_into('>I',directory,64*u+field,C.D.u32(directory,64*u+field)+before[index][0]-after[index][0])
    assert directory==old[x:x+n]
    assert raw[48:112]==old[48:112] and raw[212:228]==old[212:228] and C.D.u32(raw,28)==158
    of,orr=functions(old,oldelf);nf,nrr=functions(raw,elf)
    oi=instruction_identity(old,oldelf,oldpath/'build/engine.elf',profile+'-g157',of,orr)
    ni=instruction_identity(raw,elf,art['build']/'engine.elf',profile+'-g158',nf,nrr)
    pairs=[]
    for name,new in nf.items():
        previous=of.get(name)
        kind='new' if previous is None else 'same-bytes' if new['raw_sha256']==previous['raw_sha256'] else 'relocation-only' if new['normalized_sha256']==previous['normalized_sha256'] else 'branch-and-relocation-only' if oi[name]==ni[name] else 'generation-only' if generation_only(oi[name],ni[name]) else 'BOOT-gate-logic'
        pairs.append(dict(name=name,classification=kind,old=previous,new=new))
    semantic=[r['name'] for r in pairs if r['classification'] in ('new','BOOT-gate-logic')]
    assert set(semantic)=={'boot_fail_bits'},semantic
    labels=['generation_header_lengths_offsets_CRC']*256+['UNEXPLAINED']*(max(len(raw),len(old))-256)
    def mark(at,n,label):labels[at:at+n]=[label]*n
    mark(*after[0],'linked_engine_constants_or_padding')
    classes={r['name']:r['classification'] for r in pairs};engine=next(s for s in elf.sections if s['name']=='.engine')
    for name,s in sorted(elf.symbols.items(),key=lambda r:r[1]['size'],reverse=True):
        if s['section']==engine['index'] and s['size']:mark(s['value'],s['size'],'function:'+classes.get(name,'generation_constant')+':'+name)
    for at,kind,target,addend in nrr:mark(at,4,'ELF_relocation:'+target)
    for section,label in zip(after[1:],('pointer_relocations','directory_offsets','identical_maps','bank_generation_and_CRC','identical_row_Look_pools','identical_UI_knobs_users')):mark(*section,label)
    if len(old)>len(raw):mark(len(raw),len(old)-len(raw),'removed_tail')
    counts=Counter();changed=0
    with (out/('byte-audit-'+profile+'.tsv')).open('w') as f:
        f.write('offset\told\tnew\texplanation\n')
        for i in range(max(len(raw),len(old))):
            a=old[i] if i<len(old) else None;b=raw[i] if i<len(raw) else None
            if a==b:continue
            assert labels[i]!='UNEXPLAINED',(profile,i)
            f.write(str(i)+'\t'+str(a)+'\t'+str(b)+'\t'+labels[i]+'\n');counts[labels[i].split(':')[0]]+=1;changed+=1
    for u in range(3):
        for s in range(1,9):assert C.D.expand(raw,u,s)==C.D.expand(old,u,s)
    a,_=C.D.effect_area(raw);b,_=C.D.effect_area(old);assert C.D.u16(raw,a+10)==C.D.u16(old,b+10)
    for i in range(C.D.u16(raw,a+10)):assert C.D.expand_effect(raw,i)==C.D.expand_effect(old,i)
    size=json.loads((art['build']/'size.json').read_text())
    for path,digest in {**size['sources'],**size['headers']}.items():assert C.sha((C.ROOT/path).read_bytes())==digest,path
    report=dict(status='PASS',profile=profile,DAT_sha256=C.sha(raw),old_DAT_sha256=C.sha(old),source_changes=changes,functions=pairs,
        semantic_changes=semantic,generation_function_classes=dict(Counter(r['classification'] for r in pairs)),changed_bytes=changed,size_delta=len(raw)-len(old),unexplained_bytes=0,
        all_records_552_identical=True,all_recipe_manifest_entries_identical=True,body_resident_ABI_identical=True,transaction_and_compensation_C_identical=True,classes=dict(counts))
    C.save(out/('byte-audit-'+profile+'.json'),report);audits.append({k:report[k] for k in ('profile','changed_bytes','size_delta','unexplained_bytes','semantic_changes','generation_function_classes')})
C.save(out/'audit-summary.json',dict(status='PASS',audits=audits,source_changes=changes));print(json.dumps(dict(status='PASS',audits=audits)))
