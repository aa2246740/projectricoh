#!/usr/bin/env python3
"""Independent, read-only input audit. Outputs stay in this task's local/."""
import hashlib
import json
import pathlib
import re
import struct
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / 'local'
OBJDUMP = ROOT / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'


def save(name, value):
    (LOCAL / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def elf_parse(data):
    assert data[:7] == b'\x7fELF\x01\x02\x01'
    off = struct.unpack_from('>I', data, 32)[0]
    width, count, names = struct.unpack_from('>HHH', data, 46)
    raw = [struct.unpack_from('>10I', data, off+i*width) for i in range(count)]
    ns = data[raw[names][4]:raw[names][4]+raw[names][5]]
    def string(buf, i):
        return buf[i:buf.index(0, i)].decode()
    sections = {string(ns,s[0]):dict(type=s[1],flags=s[2],va=s[3],offset=s[4],size=s[5]) for s in raw}
    symbols = {}
    for s in raw:
        if s[1] != 2:
            continue
        st = raw[s[6]]
        strings = data[st[4]:st[4]+st[5]]
        for i in range(s[4],s[4]+s[5],16):
            n,v,z,inf,other,si = struct.unpack_from('>IIIBBH',data,i)
            if n:
                symbols[string(strings,n)] = dict(va=v,size=z,info=inf,section=si)
    return sections,symbols


def snapshot():
    paths = set()
    for d in ['firmware/resident_final/resident', 'firmware/resident_final/engine_services',
              'firmware/image_v2/local/candidate-final', 'artifacts/firmware/gxr-1.51',
              'artifacts/stage2l-switch-packages/stage2l-switch-efe6587190e8']:
        paths.update(p for p in (ROOT/d).rglob('*') if p.is_file())
    for d in ['firmware/resident_final/local/resident/build']:
        paths.update(p for p in (ROOT/d).iterdir() if p.is_file())
    for n in ['firmware/resident_final/local/hooks.json', 'firmware/resident_final/local/stack.json',
              'firmware/resident_final/local/patch-manifest.json','firmware/resident_final/local/resident/linked_hooks.S',
              'firmware/resident_final/REPORT.md','firmware/resident_slim/REPORT.md',
              'firmware/resident_v2/RESIDENT_SPEC.md','firmware/image_v2/local/audit-final.json',
              'firmware/image_v2/build.py','firmware/image_v2/audit.py','firmware/image_v2/policy.json',
              'research/unit_recovery/REPORT.md','firmware/stage2l_switch/hooks.json',
              str(OBJDUMP.relative_to(ROOT)),
              'research/tooling_m32r/src/binutils-2.43/cpu/m32r.cpu',
              'research/tooling_m32r/src/binutils-2.43/opcodes/m32r-opc.c']:
        paths.add(ROOT/n)
    records = {str(p.relative_to(ROOT)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(paths)}
    save('inputs-before.json',records)
    frozen = LOCAL/'frozen'
    for p in sorted(paths):
        rel = p.relative_to(ROOT)
        if str(rel).startswith(('firmware/resident_final/resident/','firmware/resident_final/engine_services/')) or str(rel) in [
                'firmware/resident_final/local/resident/build/resident.elf','firmware/resident_final/local/resident/build/resident.map',
                'firmware/resident_final/local/hooks.json','firmware/image_v2/policy.json',
                'firmware/resident_final/local/resident/linked_hooks.S',
                'artifacts/firmware/gxr-1.51/ilaunch3',
                'firmware/image_v2/local/candidate-final/candidate/SD_ROOT/ilaunch3']:
            dest = frozen/rel
            dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(p.read_bytes())
    return records


def collect():
    records=snapshot()
    frozen=LOCAL/'frozen'
    orig=(frozen/'artifacts/firmware/gxr-1.51/ilaunch3').read_bytes()
    cand=(frozen/'firmware/image_v2/local/candidate-final/candidate/SD_ROOT/ilaunch3').read_bytes()
    elfpath=frozen/'firmware/resident_final/local/resident/build/resident.elf'
    elf=elfpath.read_bytes()
    sections,symbols=elf_parse(elf)
    save('elf.json',dict(sections=sections,symbols=symbols))
    hooks=json.loads((frozen/'firmware/resident_final/local/hooks.json').read_text())
    rows=[]
    for i in range(16):
        src,va,size,bss,bsize=struct.unpack_from('>5I',orig,0x20+20*i)
        assert 512+src+size<=len(orig)
        rows.append(dict(index=i,offset=src+512,va=va,size=size,bss=bss,bss_size=bsize))
    save('segments.json',rows)
    disdir=LOCAL/'disasm';disdir.mkdir(exist_ok=True)
    commands=[]
    def dump(args,out):
        cmd=[str(OBJDUMP),*map(str,args)]
        with out.open('w') as fd:
            p=subprocess.run(cmd,stdout=fd,stderr=subprocess.PIPE,text=True)
        commands.append(dict(argv=cmd,output=str(out.relative_to(HERE)),returncode=p.returncode,stderr=p.stderr))
        assert p.returncode==0,p.stderr
    dump(['-d',elfpath],disdir/'resident.txt')
    for row in rows:
        path=disdir/f'official-{row["index"]:02}.bin'
        path.write_bytes(orig[row['offset']:row['offset']+row['size']])
        dump(['-D','-b','binary','-m','m32r','-EB',f'--adjust-vma={row["va"]}',path],path.with_suffix('.txt'))
    save('commands.json',commands)
    def weighted(raw):
        return sum(sum(raw[512+i::6])*(i+2) for i in range(6))&0xffffffff
    checks={}
    for name,raw in [('official',orig),('candidate',cand)]:
        checks[name]=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),
                         stored_checksum=struct.unpack_from('>I',raw,0x16c)[0],checksum=weighted(raw))
        assert checks[name]['stored_checksum']==checks[name]['checksum']
    stage=ROOT/'artifacts/stage2l-switch-packages/stage2l-switch-efe6587190e8/candidate/SD_ROOT/ilaunch3'
    if not stage.exists():
        stage=next((ROOT/'artifacts/stage2l-switch-packages/stage2l-switch-efe6587190e8').rglob('ilaunch3'))
    raw=stage.read_bytes()
    checks['stage2l']=dict(path=str(stage.relative_to(ROOT)),sha256=sha(stage),stored_checksum=struct.unpack_from('>I',raw,0x16c)[0],checksum=weighted(raw))
    assert checks['stage2l']['stored_checksum']==checks['stage2l']['checksum']
    def mapped(va,n):
        rr=[r for r in rows if r['va']<=va and va+n<=r['va']+r['size']]
        assert len(rr)==1,(hex(va),n)
        r=rr[0];return r['offset']+va-r['va']
    def long_at(raw,va):
        return struct.unpack_from('>I',raw,mapped(va,4))[0]
    inventory=[]
    for h in hooks:
        n=h['number'];a=int(h['va'],16);z=h['length'];off=mapped(a,z)
        assert orig[off:off+z].hex()==h['original_bytes']
        changed=orig[off:off+z]!=cand[off:off+z]
        item=dict(number=n,id=h['id'],va=a,length=z,offset=off,changed=changed,
                  original=orig[off:off+z].hex(),candidate=cand[off:off+z].hex())
        if changed:
            w=long_at(cand,a);assert w>>24==255
            delta=w&0xffffff
            if delta&0x800000:delta-=1<<24
            target=(a&~3)+delta*4
            item.update(target=target,delta_bytes=delta*4)
            assert target==symbols[f'rv_hook_{n:02}']['va']
            hook_off=sections['.payload']['offset']+target-sections['.payload']['va']
            replay=elf[hook_off+16:hook_off+16+z]
            item['replay']=replay.hex();assert replay==orig[off:off+z]
        inventory.append(item)
    for name in ['.payload','.root_pins']:
        s=sections[name];assert cand[mapped(s['va'],s['size']):mapped(s['va'],s['size'])+s['size']]==elf[s['offset']:s['offset']+s['size']]
    checks['root_initial']=cand[mapped(0x20054700,244):mapped(0x20054700,244)+244].hex()
    assert checks['root_initial']=='ff'*244
    checks['hook_count']=sum(h['changed'] for h in inventory)
    save('identity.json',checks);save('hooks.json',inventory)
    print(json.dumps(dict(input_files=len(records),hooks=checks['hook_count'],candidate=checks['candidate']['sha256'],disasm_segments=len(rows))))


def verify():
    before=json.loads((LOCAL/'inputs-before.json').read_text())
    changes=[]
    for name,r in before.items():
        p=ROOT/name
        if not p.is_file() or sha(p)!=r['sha256']:
            changes.append(name)
    save('inputs-verification.json',dict(files=len(before),unchanged=not changes,changed=changes))
    print(json.dumps(dict(verified_files=len(before),changed=changes)))
    return bool(changes)


def instructions(path):
    out=[]
    for line in path.read_text().splitlines():
        m=re.match(r'^([0-9a-f]+):\s*\t([0-9a-f ]+)\t(.+)$',line)
        if not m:
            continue
        addr=int(m[1],16);raw=bytes.fromhex(m[2]);asm=m[3].strip()
        pair=re.split(r' (->|\|\|) ',asm)
        if len(pair)==3:
            out.extend([dict(pc=addr,raw=raw[:2].hex(),asm=pair[0],pair=pair[1]),
                        dict(pc=addr+2,raw=raw[2:].hex(),asm=pair[2],pair=pair[1])])
        else:
            out.append(dict(pc=addr,raw=raw.hex(),asm=asm,pair='wide' if len(raw)==4 else 'single'))
    return out


def xref():
    rows=json.loads((LOCAL/'segments.json').read_text())
    hooks=json.loads((LOCAL/'hooks.json').read_text())
    raw=(LOCAL/'frozen/artifacts/firmware/gxr-1.51/ilaunch3').read_bytes()
    targets={h['va']+d:(h['number'],d) for h in hooks if h['changed'] for d in range(0,h['length'],2)}
    def fileva(off):
        for r in rows:
            if r['offset']<=off<r['offset']+r['size']:
                return r['va']+off-r['offset']
        return None
    ins=[]
    for row in rows:
        ins.extend(instructions(LOCAL/f'disasm/official-{row["index"]:02}.txt'))
    edges=[];direct_hits=[];constructs=[];call_targets=[];table_dispatch=[]
    const={};recent=[];previous_pc=None
    for t in ins:
        pc,asm=t['pc'],t['asm'];recent=(recent+[t])[-18:]
        if previous_pc is not None and pc-previous_pc not in (2,4):const={}
        previous_pc=pc
        m=re.match(r'^(b(?:ra|l|c|nc|cl|ncl|eqz|nez|gez|gtz|lez|ltz|eq|ne))\s+.*?(?:0x)?([0-9a-f]{7,8})(?:\s|$)',asm)
        if m:
            dest=int(m[2],16);edge=dict(source=pc,target=dest,kind=m[1],raw=t['raw'],asm=asm)
            edges.append(edge)
            if dest in targets:
                direct_hits.append(dict(**edge,hook=targets[dest][0],inner=targets[dest][1]))
        m=re.match(r'^(jl|jmp|jc|jnc)\s+(r\d+|fp|lr)$',asm)
        if m:
            reg=m[2]
            if reg in const:
                val,origin=const[reg]
                call_targets.append(dict(source=pc,target=val&~3,value=val,origin=origin,kind=m[1]))
            if any(re.match(r'ld\s+'+re.escape(reg)+r',',x['asm']) for x in recent[-8:-1]):
                table_dispatch.append(dict(source=pc,context=recent[-12:]))
        # A small constant evaluator. It records syntactic candidates, not proven reachability.
        m=re.match(r'^(seth|ld24|ldi)\s+(r\d+|fp|lr),#?(-?(?:0x)?[0-9a-f]+)$',asm)
        if m:
            op,reg,txt=m.groups();v=int(txt,16) if '0x' in txt else int(txt,10)
            const[reg]=((v<<16 if op=='seth' else v)&0xffffffff,pc)
        else:
            m=re.match(r'^(or3|add3|and3)\s+(r\d+|fp|lr),(r\d+|fp|lr),#(-?(?:0x)?[0-9a-f]+)$',asm)
            if m:
                op,dr,sr,txt=m.groups();v=int(txt,16) if '0x' in txt else int(txt,10)
                if sr in const:
                    base,origin=const[sr]
                    value=((base|v) if op=='or3' else (base&v) if op=='and3' else base+v)&0xffffffff
                    const[dr]=(value,origin)
                    constructs.append(dict(source=pc,origin=origin,value=value,register=dr,asm=asm))
                else:
                    const.pop(dr,None)
            else:
                m=re.match(r'^mv\s+(r\d+|fp|lr),(r\d+|fp|lr)$',asm)
                if m:
                    if m[2] in const:const[m[1]]=const[m[2]]
                    else:const.pop(m[1],None)
                else:
                    m=re.match(r'^addi\s+(r\d+|fp|lr),#(-?\d+)$',asm)
                    if m and m[1] in const:
                        v,o=const[m[1]];const[m[1]]=((v+int(m[2]))&0xffffffff,o)
                    elif (m:=re.fullmatch(r'(add|or|and) (r\d+|fp|lr),(r\d+|fp|lr)',asm)):
                        op,dr,sr=m.groups()
                        if dr in const and sr in const:
                            a,origin=const[dr];b,_=const[sr]
                            value=((a+b) if op=='add' else (a|b) if op=='or' else (a&b))&0xffffffff
                            const[dr]=(value,origin)
                            constructs.append(dict(source=pc,origin=origin,value=value,register=dr,asm=asm))
                        else:const.pop(dr,None)
                    elif not re.match(r'^(b\w+|st\w*|push|nop|cmp\w*|mvtc|trap|rte)\b',asm):
                        m=re.match(r'^\w+\s+(r\d+|fp|lr)',asm)
                        if m:const.pop(m[1],None)
        if re.match(r'^(bl|jl)\b',asm):
            for reg in ['r0','r1','r2','r3','r4','r5','r6','r7','lr']:
                const.pop(reg,None)
        if re.match(r'^(bra|jmp|rte)\b',asm):const={}
    # Scan every file byte, including header, gaps, literal pools and jump tables.
    pointers=[]
    for target,(h,inner) in targets.items():
        needle=struct.pack('>I',target);start=0
        while True:
            found=raw.find(needle,start)
            if found<0:break
            pointers.append(dict(offset=found,va=fileva(found),target=target,hook=h,inner=inner,alignment=found%4))
            start=found+1
    # Exhaustive branch encoding scan of each initialized byte range, including data.
    # The canonical objdump listing separately identifies decoded instructions.
    encoded=[]
    def signed(v,bits):return v-(1<<bits) if v&(1<<(bits-1)) else v
    for r in rows:
        data=raw[r['offset']:r['offset']+r['size']]
        for off in range(0,len(data)-3,2):
            pc=r['va']+off;w=struct.unpack_from('>I',data,off)[0];dest=None;kind=''
            if off%4==0 and w>>24 in [0xf8,0xf9,0xfc,0xfd,0xfe,0xff]:
                dest=pc+signed(w&0xffffff,24)*4;kind='branch24'
            elif off%4==0 and w>>28==0xb and ((w>>20)&15) in [0,1,8,9,10,11,12,13]:
                dest=pc+signed(w&65535,16)*4;kind='branch16'
            half=w>>16
            if off%4==2:half&=0x7fff
            if half>>8 in [0x78,0x79,0x7c,0x7d,0x7e,0x7f]:
                short=(pc&~3)+signed(half&255,8)*4
                if short in targets:
                    encoded.append(dict(source=pc,target=short,hook=targets[short][0],inner=targets[short][1],kind='branch8',offset=r['offset']+off))
            if dest in targets:
                encoded.append(dict(source=pc,target=dest,hook=targets[dest][0],inner=targets[dest][1],kind=kind,offset=r['offset']+off))
    construct_hits=[dict(**x,hook=targets[x['value']][0],inner=targets[x['value']][1]) for x in constructs if x['value'] in targets]
    save('direct-edges.json',edges)
    save('indirect-constant-calls.json',call_targets)
    save('jump-table-dispatch-candidates.json',table_dispatch)
    save('address-constructs.json',constructs)
    save('xrefs.json',dict(direct=direct_hits,pointers=pointers,constructed=construct_hits,encoding_candidates=encoded,
                           limitation='Linear decoding includes data. Computed targets from arbitrary RAM and unrecognized relative-table idioms remain unknown.'))
    windows=[]
    for h in hooks:
        if not h['changed']:continue
        a=h['va'];context=[t for t in ins if a-16<=t['pc']<a+max(h['length']+20,40)]
        windows.append(dict(hook=h['number'],va=a,original=context,
                            incoming=[e for e in edges if a<=e['target']<a+h['length']]))
    save('hook-contexts.json',windows)
    print(json.dumps(dict(decoded_instructions=len(ins),direct_edges=len(edges),direct_hook_refs=len(direct_hits),
                         inner_direct=[x for x in direct_hits if x['inner']],inner_pointer=[x for x in pointers if x['inner']],
                         inner_construct=[x for x in construct_hits if x['inner']],
                         inner_encoding=[x for x in encoded if x['inner']],dispatch_candidates=len(table_dispatch))))


def tables():
    rows=json.loads((LOCAL/'segments.json').read_text())
    raw=(LOCAL/'frozen/artifacts/firmware/gxr-1.51/ilaunch3').read_bytes()
    hooks=json.loads((LOCAL/'hooks.json').read_text())
    inner={h['va']+d:(h['number'],d) for h in hooks if h['changed'] for d in range(2,h['length'],2)}
    constructs=json.loads((LOCAL/'address-constructs.json').read_text())
    cs={x['source']:x for x in constructs}
    records=[];hits=[]
    def address(a,n):
        for r in rows:
            if r['va']<=a and a+n<=r['va']+r['size']:
                return r['offset']+a-r['va']
        return None
    for row in rows:
        ins=instructions(LOCAL/f'disasm/official-{row["index"]:02}.txt')
        for idx,t in enumerate(ins):
            m=re.fullmatch(r'jmp (r\d+|fp|lr)',t['asm'])
            if not m or m[1]=='lr':continue
            jr=m[1]
            adds=[(j,re.fullmatch(r'add '+re.escape(jr)+r',(r\d+|fp|lr)',ins[j]['asm']))
                  for j in range(max(0,idx-4),idx)]
            adds=[(j,k[1]) for j,k in adds if k]
            if not adds:continue
            ai,offset_reg=adds[-1]
            base=[cs[ins[j]['pc']] for j in range(max(0,ai-8),ai)
                  if ins[j]['pc'] in cs and cs[ins[j]['pc']]['register']==jr]
            if not base:continue
            jb=base[-1]['value']
            loads=[]
            for j in range(max(0,ai-15),ai):
                lm=re.fullmatch(r'(ldh|ldub|ldb|lduh|ld) '+re.escape(offset_reg)+r',@(r\d+|fp|lr)',ins[j]['asm'])
                if lm:loads.append((j,lm[1],lm[2]))
            if not loads:continue
            li,load_op,tr=loads[-1]
            tablebase=[cs[ins[j]['pc']] for j in range(max(0,li-24),li)
                       if ins[j]['pc'] in cs and cs[ins[j]['pc']]['register']==tr]
            if not tablebase:continue
            tb=tablebase[-1]['value']
            counts=[]
            for j in range(max(0,li-24),li):
                cm=re.fullmatch(r'cmpui (?:r\d+|fp|lr),#(0x[0-9a-f]+|\d+)',ins[j]['asm'])
                if cm:counts.append(int(cm[1],0))
            count=counts[-1] if counts and 0<counts[-1]<=2048 else None
            width=4 if load_op=='ld' else 2 if load_op in ('ldh','lduh') else 1
            signed=load_op in ('ldh','ldb','ld')
            rec=dict(jump=t['pc'],table=tb,base=jb,load=load_op,count_candidate=count,width=width,
                     bounds_verified=False,context=ins[max(0,li-18):idx+1],inner_hits=[])
            # Decode a conservative neighborhood even when a switch bound cannot be inferred.
            # This is a bounded scan, never a proof for arbitrary computed jumps.
            n=count+1 if count else 256
            off=address(tb,n*width)
            if off is not None:
                values=[]
                for k in range(n):
                    v=int.from_bytes(raw[off+k*width:off+(k+1)*width],'big',signed=signed)
                    dest=(jb+v)&0xfffffffc
                    values.append(dest)
                    if dest in inner:
                        hit=dict(jump=t['pc'],table=tb,entry=k,target=dest,hook=inner[dest][0],inner=inner[dest][1])
                        rec['inner_hits'].append(hit);hits.append(hit)
                rec['targets']=values
            records.append(rec)
    save('relative-tables.json',records)
    relevant=[dict(jump=x['jump'],table=x['table'],base=x['base'],load=x['load'],count_candidate=x['count_candidate'])
              for x in records if any(abs(x['base']-a)<32768 for a in inner if a%4==0)]
    save('relative-tables-summary.json',dict(candidates=len(records),inner_hits=hits,relevant=relevant,
         limitation='Pattern-recognized relative tables only. count+1 or 256 entries are scanned; bounds are not all validated. Absolute pointer tables were scanned at every file byte by xref.'))
    print(json.dumps(dict(candidates=len(records),inner_hits=hits,relevant=relevant)))


if __name__=='__main__':
    if sys.argv[1:] == ['collect']:
        collect()
    elif sys.argv[1:]==['verify']:
        sys.exit(verify())
    elif sys.argv[1:]==['xref']:
        xref()
    elif sys.argv[1:]==['tables']:
        tables()
    else:
        raise SystemExit('usage: review.py collect|xref|tables|verify')
