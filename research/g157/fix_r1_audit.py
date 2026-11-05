"""Audit the repaired artifacts against the exact reviewed g157, byte by byte."""
from collections import Counter
from pathlib import Path
import json, re, struct, sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
C.setup();C.DATASET='model';C.compute_gate('fix-r1-byte-audit')
out=C.LOCAL/'fix-r1';Elf=C.load(C.ROOT/'firmware/stage2l_switch/tools/build.py','fix_audit_elf').Elf
freeze=json.loads((out/'freeze.json').read_text());source=[]
for name,sha in freeze['source_sha256'].items():
    current=C.PRODUCT/name;newsha=C.sha(current.read_bytes())
    if newsha!=sha:source.append(dict(file=name,old_sha256=sha,new_sha256=newsha))
assert {r['file'] for r in source}=={'adapter.c','src/firmware/engine/core/eng_core.c','src/firmware/engine/core/eng_core.h'}
def functions(raw,elf):
    engine=next(s for s in elf.sections if s['name']=='.engine');assert elf.content(engine)==raw[256:256+engine['size']]
    masked=bytearray(raw);rel=[]
    for sec in elf.sections:
        if sec['type']!=4:continue
        table=elf.symbol_tables[sec['link']]
        for pos in range(0,sec['size'],12):
            patch,info,addend=struct.unpack_from('>IIi',elf.bytes,sec['offset']+pos)
            if 256<=patch<256+engine['size']:
                masked[patch:patch+4]=bytes(4);rel.append((patch,info&255,table[info>>8]['name'],addend))
    result={}
    for name,s in elf.symbols.items():
        if s['section']==engine['index'] and s['size'] and s['info']&15==2:
            at=s['value'];n=s['size'];result[name]=dict(address=at,bytes=n,raw_sha256=C.sha(raw[at:at+n]),
                normalized_sha256=C.sha(masked[at:at+n]),relocations=[r for r in rel if at<=r[0]<at+n])
    return result,rel
def instruction_identity(raw,elf,path,label,funcs,relocations):
    output=C.run([C.OBJDUMP,'-dr',path],'fix-r1-'+label).stdout;instructions={}
    masked=bytearray(raw)
    for patch,*_ in relocations:masked[patch:patch+4]=bytes(4)
    ranges=sorted((row['address'],row['address']+row['bytes'],name) for name,row in funcs.items())
    engine=next(s for s in elf.sections if s['name']=='.engine')
    anchors=sorted((s['value'],name) for name,s in elf.symbols.items() if s['section']==engine['index'] and not name.startswith('.'))
    def destination(address):
        matches=[(lo,hi,name) for lo,hi,name in ranges if lo<=address<hi]
        if matches:
            lo,hi,name=sorted(matches,key=lambda r:(r[1]-r[0],r[2]))[0];return name+'+'+str(address-lo)
        # Assembly bridge exports have no STT_FUNC size. Resolve their local
        # branches relative to the named bridge, including its interior labels.
        prior=[(lo,name) for lo,name in anchors if lo<=address]
        if prior and engine['va']<=address<engine['va']+engine['size']:
            lo,name=prior[-1];return name+'+'+str(address-lo)
        return 'ABS:'+hex(address)
    for line in output.splitlines():
        fields=line.split('\t')
        if len(fields)<3 or not re.fullmatch(r'\s*[0-9a-f]+:',fields[0]):continue
        address=int(fields[0].strip()[:-1],16)
        try:code=bytes.fromhex(fields[1])
        except ValueError:continue
        asm=fields[2].strip()
        branch=re.search(r'\b([0-9a-f]+) <[^>]+>',asm) if re.search(r'\b(?:bl|bra|bc|bnc|beqz|bnez|bltz|blez|bgtz|bgez|beq|bne)\s+',asm) else None
        if branch:
            target=int(branch.group(1),16);canonical=asm[:branch.start()]+'TARGET('+destination(target)+')'+asm[branch.end():]
            instructions[address]=('branch',len(code),canonical)
        else:instructions[address]=('bytes',len(code),bytes(masked[address:address+len(code)]).hex())
    result={}
    for name,row in funcs.items():
        lo=row['address'];hi=lo+row['bytes'];parts=[];covered=0
        for at,item in sorted(instructions.items()):
            if lo<=at<hi:
                n=min(item[1],hi-at)
                clipped=(item[0],n,item[2][:2*n] if item[0]=='bytes' else item[2])
                parts.append((at-lo,*clipped));covered+=n
        assert covered==row['bytes'],(name,covered,row['bytes'])
        result[name]=C.sha(json.dumps(parts).encode())
    return result
audits=[]
for profile in ('test','release'):
    oldpath=out/'before'/profile;prior=(oldpath/'GXRCE.DAT').read_bytes();artifact=C.artifact(profile)
    raw=artifact['dat'].read_bytes();before=C.D.sections(prior);after=C.D.sections(raw)
    oldelf=Elf(oldpath/'build/engine.elf');elf=Elf(artifact['build']/'engine.elf')
    assert (oldpath/'records.json').read_bytes()==artifact['records'].read_bytes()
    for i in range(3,7):
        x,n=before[i];y,m=after[i];assert n==m and prior[x:x+n]==raw[y:y+m],(profile,i)
    # Directory pointers move exactly with their unchanged destination sections.
    x,n=before[2];y,m=after[2];assert n==m;directory=bytearray(raw[y:y+m])
    for unit in range(3):
        for field,index in ((12,3),(16,4),(20,5),(24,6)):
            v=C.D.u32(directory,64*unit+field);struct.pack_into('>I',directory,64*unit+field,v+before[index][0]-after[index][0])
    assert directory==prior[x:x+n]
    assert raw[48:112]==prior[48:112] and raw[212:228]==prior[212:228]
    oldfun,oldrel=functions(prior,oldelf);newfun,newrel=functions(raw,elf);pairs=[]
    old_identity=instruction_identity(prior,oldelf,oldpath/'build/engine.elf',profile+'-before-disassembly',oldfun,oldrel)
    new_identity=instruction_identity(raw,elf,artifact['build']/'engine.elf',profile+'-after-disassembly',newfun,newrel)
    for name,f in newfun.items():
        old=oldfun.get(name);state='new' if not old else 'same-bytes' if old['raw_sha256']==f['raw_sha256'] else 'relocation-only' if old['normalized_sha256']==f['normalized_sha256'] else 'changed-linked-function'
        if state=='changed-linked-function' and old_identity.get(name)==new_identity[name]:state='resolved-branch-and-relocation-only'
        pairs.append(dict(name=name,classification=state,old=old,new=f,canonical_instruction_identity_equal=old_identity.get(name)==new_identity[name]))
    semantic_changes=[r['name'] for r in pairs if r['classification']=='changed-linked-function']
    assert set(semantic_changes)=={'apply_impl.constprop.0','recover_confirmed'},semantic_changes
    labels=['header_lengths_entries_offsets_CRC']*256+['UNEXPLAINED']*(max(len(raw),len(prior))-256)
    def mark(at,n,label):labels[at:at+n]=[label]*n
    mark(*after[0],'linked_engine_padding_or_constants')
    engine=next(s for s in elf.sections if s['name']=='.engine')
    status_by_name={r['name']:r['classification'] for r in pairs}
    for name,s in sorted(elf.symbols.items(),key=lambda row:row[1]['size'],reverse=True):
        if s['section']==engine['index'] and s['size']:
            mark(s['value'],s['size'],('function:'+status_by_name.get(name,'constant')+':' if s['info']&15==2 else 'linked_constant:')+name)
    for at,kind,target,addend in newrel:mark(at,4,'ELF_relocation:'+str(kind)+':'+target)
    names=('runtime_pointer_relocations','directory_pointer_shift','identical_native_maps_moved','identical_recipe_banks_moved','identical_row_and_Look_pools_moved','identical_UI_knobs_users_moved')
    for sec,label in zip(after[1:],names):mark(*sec,label)
    if len(prior)>len(raw):mark(len(raw),len(prior)-len(raw),'removed_tail_after_identical_data_shift')
    counts=Counter();changed=0
    with (out/('byte-audit-'+profile+'.tsv')).open('w') as f:
        f.write('offset\told\tnew\texplanation\n')
        for i in range(max(len(raw),len(prior))):
            a=prior[i] if i<len(prior) else None;b=raw[i] if i<len(raw) else None
            if a==b:continue
            assert labels[i]!='UNEXPLAINED',(profile,i)
            f.write(f'{i}\t{a if a is not None else "ADD"}\t{b if b is not None else "REMOVE"}\t{labels[i]}\n');changed+=1;counts[labels[i].split(':')[0]]+=1
    for unit in range(3):
        for slot in range(1,9):assert C.D.expand(raw,unit,slot)==C.D.expand(prior,unit,slot)
    a,_=C.D.effect_area(raw);b,_=C.D.effect_area(prior);assert C.D.u16(raw,a+10)==C.D.u16(prior,b+10)
    for i in range(C.D.u16(raw,a+10)):assert C.D.expand_effect(raw,i)==C.D.expand_effect(prior,i)
    report=dict(status='PASS',profile=profile,old_DAT_sha256=C.sha(prior),DAT_sha256=C.sha(raw),changed_including_removed_bytes=changed,
        size_delta=len(raw)-len(prior),removed_bytes=max(0,len(prior)-len(raw)),unexplained_bytes=0,classes=dict(counts),
        source_changes=source,source_files_unchanged=len(freeze['source_sha256'])-len(source),all_data_sections_identical_after_shift=True,
        all_552_records_identical=True,record_manifest_identical=True,body_resident_ABI_identical=True,
        functions=pairs,removed_functions=[k for k in oldfun if k not in newfun],
        normalized_function_classes=dict(Counter(r['classification'] for r in pairs)))
    C.save(out/('byte-audit-'+profile+'.json'),report);audits.append({k:report[k] for k in ('profile','changed_including_removed_bytes','size_delta','unexplained_bytes','normalized_function_classes')})
C.save(out/'audit-summary.json',dict(status='PASS',audits=audits,source_changes=source))
print(json.dumps(dict(status='PASS',audits=audits)))
