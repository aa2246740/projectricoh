"""Executable translation-validation obligations for the frozen M32R engines.

No device use and no writes outside this directory. This checker preserves all
non-address immediates, instruction order, registers, and branch topology.
"""
from pathlib import Path
import bisect, collections, hashlib, json, re, struct, sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
R1 = ROOT / 'research/review_g117_codegen'
sys.path.insert(0, str(R1))
import normalize as previous
from audit import Elf, canonical
from calls_and_relocations import targets

G = (116, 117)
ES = {g: Elf(R1 / f'engine{g}.elf') for g in G}
LABEL = {g: Elf(OUT / f'labels{g}/engine.elf') for g in G}
INV = json.loads((R1 / 'inventory.json').read_text())
DEC = {g: json.loads((R1 / f'decode{g}.json').read_text()) for g in G}
BRANCH = {'bl','bra','bc','bnc','beqz','bnez','beq','bne','bgez','bltz','bgtz','blez'}
B = {'es_range.constprop.0','gate_validate.constprop.0','gxr2_crc32',
     'pn_address','pn_native_from_seed','ig_apply','list_bind','eng_current','workspace_close'}
FILES = {'io_close','io_open','io_read','io_write','io_remove','io_rename',
         'open_read','remember_load','remove_owned','verify'}
MIXED = {'finish','ig_event','ig_init','ig_menu','ui_finish'}


def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n')


def all_symbols(e):
    """Do not collapse duplicate .LC labels from different archive members."""
    h = struct.unpack_from('>16sHHIIIIIHHHHHH', e.raw)
    ss = [struct.unpack_from('>10I', e.raw, h[6]+i*h[11]) for i in range(h[12])]
    result = []
    for s in ss:
        if s[1] != 2:
            continue
        strings = ss[s[6]]
        names = e.raw[strings[4]:strings[4]+strings[5]]
        for off in range(s[4], s[4]+s[5], s[9]):
            n, a, z, info, other, section = struct.unpack_from('>IIIBBH', e.raw, off)
            name = names[n:].split(b'\0', 1)[0].decode()
            if name:
                result.append(dict(name=name,address=a,size=z,type=info&15,section=section))
    return result


SYMS = {g: all_symbols(LABEL[g]) for g in G}


def span(g, a, size=None):
    e = LABEL[g]
    section = next(s for s in e.sections if s['base'] <= a < s['base']+s['size'] and s['type'] in (1,8))
    index = e.sections.index(section)
    end = a+size if section['type'] == 8 else min(
        [s['address'] for s in SYMS[g] if s['section'] == index and s['address'] > a]
        + [section['base']+section['size']])
    data = bytes(end-a) if section['type'] == 8 else e.bytes(a, end-a)
    return dict(base=a,end=end,bytes=len(data),section=section['name'],
                labels=[s['name'] for s in SYMS[g] if s['address']==a and s['section']==index],
                hex=data.hex(),sha256=hashlib.sha256(data).hexdigest())


def table_ranges(g, n):
    if n != 'rv_call':
        return []
    s = ES[g].functions[n]
    return [(s['address']+3340,56),(s['address']+3584,52)]


def atoms(g, n):
    s = ES[g].functions[n]
    result = [];covered=set()
    for key, row in sorted(DEC[g].items(), key=lambda item:int(item[0])):
        pc = int(key)
        if not s['address'] <= pc < s['address']+s['size']:
            continue
        if any(lo <= pc < lo+z for lo,z in table_ranges(g,n)):
            continue
        raw = bytes.fromhex(row['raw'])
        assert ES[g].bytes(pc,len(raw)) == raw, (g,n,pc,'decoder mismatch')
        covered.update(range(pc,min(pc+len(raw),s['address']+s['size'])))
        parts = re.split(r' -> | \|\| ', row['asm'])
        assert not (' || ' in row['asm'] and sum(p!='nop' for p in parts)>1), (g,n,pc,'active parallel pair')
        if len(parts)==2:
            assert bool(raw[2]&128) == (' || ' in row['asm']), (g,n,pc,'mode bit')
        for i, asm in enumerate(parts):
            if asm == 'nop':
                code = int.from_bytes(raw[i*2:i*2+2], 'big') & 0x7fff
                assert code == 0x7000, (g,n,pc,'non-NOP filler')
                continue
            result.append(dict(pc=pc+2*i,asm=asm,relocation=previous.RELOC[g].get(pc),
                               raw=(raw[2*i:2*i+2] if len(parts)==2 else raw).hex(),
                               packet=pc,mode='parallel-nop' if ' || ' in row['asm'] else 'sequential'))
    expected=set(range(s['address'],s['address']+s['size']))
    for lo,z in table_ranges(g,n):expected.difference_update(range(lo,lo+z))
    assert expected<=covered,(g,n,'undecoded executable bytes',sorted(expected-covered))
    return result


def symbolic(g, n, aa):
    s=ES[g].functions[n]; pcs=[x['pc'] for x in aa]; result=[]; branches=[]
    for i, row in enumerate(aa):
        asm=row['asm']
        rel=row['relocation']
        if rel and rel[0] in {'R_M32R_GOTOFF_HI_SLO','R_M32R_GOTOFF_LO',
                              'R_M32R_GOTPC_HI_SLO','R_M32R_GOTPC_LO'}:
            asm=re.sub(r'#[^, ]+$','#'+rel[0],asm)
        m=re.search(r'\b(bl|bra|bc|bnc|beqz|bnez|beq|bne|bgez|bltz|bgtz|blez)\s+.*?([0-9a-f]+) <([^>]+)>',asm)
        if m:
            target=int(m[2],16)
            if s['address']<=target<s['address']+s['size']:
                logical='self@'+str(bisect.bisect_left(pcs,target))
            else:
                logical=previous.fname(m[3])
            branches.append(dict(atom=i,pc=row['pc'],opcode=m[1],target=target,logical=logical,
                                 return_atom=bisect.bisect_left(pcs,(row['pc']&~3)+4) if m[1]=='bl' else None))
            asm=asm[:m.start(2)]+logical
        else:
            asm=re.sub(r' <[^>]+>','',asm)
        result.append(asm)
    return result,branches


def gotpc(g, aa):
    checks=[]
    for i,row in enumerate(aa):
        if not row['relocation'] or row['relocation'][0]!='R_M32R_GOTPC_LO':
            continue
        hi=aa[i-1]
        assert hi['relocation'][0]=='R_M32R_GOTPC_HI_SLO'
        high=int(hi['asm'].split('#')[1],0)
        low=int(row['asm'].split('#')[1],0)
        if low>=32768: low-=65536
        call=next(x for x in reversed(aa[:i-1]) if x['asm'].startswith('bl '))
        lr=(call['pc']&~3)+4
        value=((high<<16)+low+lr)&0xffffffff
        checks.append(dict(high_pc=hi['pc'],low_pc=row['pc'],link_pc=call['pc'],image_got=value,ok=value==256))
    return checks


def data_check(x):
    rr=[]; dependency=[]
    for g,k in [(116,'old'),(117,'new')]:
        obj=x[k]['object'];a=x[k]['address']
        if a==0:
            rr.append(dict(base=0,end=0,bytes=0,hex='',section='image-base',labels=['__image_base']))
        elif obj and obj['type']==2:
            if obj['offset']==0:
                rr.append(dict(base=a,end=a,bytes=0,hex='',section='function',labels=[obj['name']]))
            else:
                assert obj['name']=='rv_call' and obj['offset'] in (3340,3584)
                z=56 if obj['offset']==3340 else 52
                rr.append(dict(base=a,end=a+z,bytes=z,hex=ES[g].bytes(a,z).hex(),section='switch',labels=['rv_call-switch']))
        else:
            base=obj['base'] if obj else a
            rr.append(span(g,base,obj['size'] if obj else None))
    if rr[0]['section']=='function':
        good=canonical(x['old']['object']['name'])==canonical(x['new']['object']['name'])
        dependency.append(canonical(x['new']['object']['name']))
    else:
        good=rr[0]['hex']==rr[1]['hex']
        if x['old']['object'] and x['old']['object']['name']=='rv_api':
            old=bytearray.fromhex(rr[0]['hex']);new=bytearray.fromhex(rr[1]['hex'])
            # This is the sole R_M32R_32_RELA data cell, and names an already
            # paired function. All other 156 bytes, plus padding, stay literal.
            oldtarget=int.from_bytes(old[16:20],'big');newtarget=int.from_bytes(new[16:20],'big')
            assert oldtarget==ES[116].functions['rv_call']['address']
            assert newtarget==ES[117].functions['rv_call']['address']
            assert previous.RELOC[116].get(rr[0]['base']+16)==('R_M32R_32_RELA','rv_call')
            kind,expr=previous.RELOC[117][rr[1]['base']+16]
            assert kind=='R_M32R_32_RELA'
            assert expr=='rv_call' or (expr.startswith('.engine+0x') and
                    ES[117].engine['base']+int(expr.split('+')[1],16)==newtarget)
            old[16:20]=new[16:20]=bytes(4)
            good=old==new
            dependency.append('rv_call')
    return dict(function=x['function'],atom=x['atom'],old=rr[0],new=rr[1],equal=good,dependencies=dependency)


def main():
    assert all(ES[g].engine['data']==LABEL[g].engine['data'] for g in G)
    records=[];packets=[];data=[]
    pairs=json.loads((R1/'relocation-pairs.json').read_text())
    init=next(x for x in INV if x['name']=='ig_init')
    init_targets={116:targets(116,init['old_name']),117:targets(117,init['name'])}
    assert set(init_targets[116])==set(init_targets[117])
    for i in sorted(init_targets[116]):
        pairs.append(dict(function='ig_init',atom=i,old=init_targets[116][i],new=init_targets[117][i]))
    for p in pairs:
        data.append(data_check(p))
    for inv in INV:
        if inv['status'] not in ('changed','identical'):
            continue
        n=inv['name'];oldname=inv['old_name']
        if inv['status']=='identical':
            records.append(dict(name=n,category='identity',local_ok=True,dependencies=[]))
            continue
        category='B-r1' if n in B else 'C-file' if n in FILES else 'C+A' if n=='ig_init' else 'C+B' if n in MIXED else 'A'
        if category not in ('A','C+A'):
            records.append(dict(name=n,category=category,local_ok=None,dependencies=[]))
            continue
        aa,bb=atoms(116,oldname),atoms(117,n)
        a,ab=symbolic(116,oldname,aa);b,bbra=symbolic(117,n,bb)
        diffs=[dict(atom=i,old=x,new=y) for i,(x,y) in enumerate(zip(a,b)) if x!=y]
        permitted = n=='ig_init' and len(diffs)==2 and all(x['old']=='ld24 r4,f0000' and x['new']=='ld24 r4,e0000' for x in diffs)
        branches_equal=[(x['atom'],x['opcode'],x['logical'],x['return_atom']) for x in ab]==[(x['atom'],x['opcode'],x['logical'],x['return_atom']) for x in bbra]
        deps=set(x['logical'] for x in bbra if not x['logical'].startswith('self@'))
        dd=[x for x in data if x['function']==n]
        assert len(dd)==sum(x['relocation'] is not None and x['relocation'][0]=='R_M32R_GOTOFF_LO' for x in bb),(n,'missing relocation target')
        for x in dd:deps.update(x['dependencies'])
        gc={str(g):gotpc(g,rs) for g,rs in [(116,aa),(117,bb)]}
        stack=lambda rows:[r['asm'] for r in rows if re.match(r'(?:push |pop |(?:add3|addi) sp,)',r['asm'])]
        stack_ok=stack(aa)==stack(bb)
        encoding_differences=[]
        for i,(x,y) in enumerate(zip(aa,bb)):
            rx,ry=bytes.fromhex(x['raw']),bytes.fromhex(y['raw'])
            if len(rx)==2:rx=(int.from_bytes(rx,'big')&0x7fff).to_bytes(2,'big')
            if len(ry)==2:ry=(int.from_bytes(ry,'big')&0x7fff).to_bytes(2,'big')
            if x['relocation'] and x['relocation'][0] in {'R_M32R_GOTOFF_HI_SLO','R_M32R_GOTOFF_LO','R_M32R_GOTPC_HI_SLO','R_M32R_GOTPC_LO'}:
                rx,ry=rx[:2],ry[:2]
            elif x['asm'].split(' ')[0] in BRANCH:
                continue
            if rx!=ry and not (permitted and i in {d['atom'] for d in diffs}):
                encoding_differences.append(dict(atom=i,old=x,new=y))
        local_ok=(len(a)==len(b) and (not diffs or permitted) and not encoding_differences and branches_equal and stack_ok
                  and all(x['equal'] for x in dd) and all(c['ok'] for v in gc.values() for c in v))
        records.append(dict(name=n,category=category,local_ok=local_ok,atoms=[len(a),len(b)],
                            non_address_differences=diffs,permitted_caps_change=permitted,
                            non_relocation_encoding_differences=encoding_differences,
                            branches_equal=branches_equal,old_branches=ab,new_branches=bbra,
                            stack_equal=stack_ok,stack_operations=stack(aa),gotpc=gc,
                            data_checks=len(dd),dependencies=sorted(deps)))
        for g,nn in [(116,oldname),(117,n)]:
            s=ES[g].functions[nn]
            for key,row in DEC[g].items():
                pc=int(key)
                if s['address']<=pc<s['address']+s['size'] and (' -> ' in row['asm'] or ' || ' in row['asm']):
                    if any(lo<=pc<lo+z for lo,z in table_ranges(g,nn)):continue
                    packets.append(dict(generation=g,function=n,pc=pc,raw=row['raw'],asm=row['asm'],
                                        parallel_bit=bool(bytes.fromhex(row['raw'])[2]&128)))
    save('translation-local.json',records)
    save('object-spans.json',data)
    save('packet-modes.json',packets)
    save('retained-symbols.json',{str(g):SYMS[g] for g in G})
    print('categories',dict(collections.Counter(x['category'] for x in records)))
    print('local failures',[(x['name'],x.get('non_address_differences'),x.get('branches_equal'),x.get('stack_equal')) for x in records if x['local_ok'] is False])
    print('data failures',[(x['function'],x['atom'],x['old']['base'],x['old']['bytes'],x['new']['bytes']) for x in data if not x['equal']])
    print('packet rows',len(packets))


if __name__=='__main__':
    main()
