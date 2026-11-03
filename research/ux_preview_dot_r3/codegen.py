"""Strict final-ELF translation inventory for gen119 -> gen120, without relinking."""
from pathlib import Path
import bisect
import functools
import collections
import difflib
import json
import re
import struct
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from common import ROOT, OUT, load, save, sha
audit=load(ROOT/'research/review_g117_codegen/audit.py','g120_codegen_elf')
ES={g:audit.Elf(ROOT/f'firmware/{tree}/candidate/local/full-r13/engine.elf')
    for g,tree in ((119,'engine_v40_ux'),(120,'engine_v41_ux'))}
DEC={g:{int(pc):r for pc,r in json.loads((OUT/f'decode{g}.json').read_text()).items()} for g in ES}
RELOC={g:{int(m[1],16):(m[2],m[3]) for m in re.finditer(
    r'^\s*([0-9a-f]+): (R_M32R_[A-Z0-9_]+)\s+(.+)$',(OUT/f'engine{g}.asm').read_text(),re.M)} for g in ES}
BRANCH={'bl','bra','bc','bnc','beqz','bnez','beq','bne','bgez','bltz','bgtz','blez'}
COMMON=set(ES[119].functions)&set(ES[120].functions)
OLD_LABEL=audit.Elf(OUT/'labels119/engine.elf')
assert OLD_LABEL.engine['data']==ES[119].engine['data']

def retained_labels():
    raw=OLD_LABEL.raw;h=struct.unpack_from('>16sHHIIIIIHHHHHH',raw)
    ss=[struct.unpack_from('>10I',raw,h[6]+i*h[11]) for i in range(h[12])];out=[]
    for s in ss:
        if s[1]!=2:continue
        st=ss[s[6]];strings=raw[st[4]:st[4]+st[5]]
        for p in range(s[4],s[4]+s[5],s[9]):
            n,a,z,t,_,section=struct.unpack_from('>IIIBBH',raw,p)
            name=strings[n:].split(b'\0',1)[0].decode()
            if name:out.append(dict(name=name,address=a,size=z,type=t&15,section=section))
    return out

LABELS=retained_labels()

def canon(g,n):
    names=[k for k,s in ES[g].symbols.items() if s['address']==ES[g].symbols[n]['address']] if n in ES[g].symbols else [n]
    candidates=sorted(set(names)&COMMON)
    return candidates[0] if candidates else audit.canonical(n)

@functools.lru_cache(maxsize=None)
def table_ranges(g,n):
    if n!='rv_call':return []
    f=ES[g].functions[n];regs={};targets=[]
    for pc,row in sorted(DEC[g].items()):
        if not f['address']<=pc<f['address']+f['size']:continue
        for asm in re.split(r' -> | \|\| ',row['asm']):
            m=re.fullmatch(r'seth (\w+),#(.*)',asm)
            if m:regs[m[1]]=int(m[2],0)<<16
            m=re.fullmatch(r'add3 (\w+),(\w+),#(-?\w+)',asm)
            if m and m[2] in regs:
                value=int(m[3],0)
                if value>=32768:value-=65536
                regs[m[1]]=(regs[m[2]]+value)&0xffffffff
                if RELOC[g].get(pc,('',''))[0]=='R_M32R_GOTOFF_LO':
                    target=(regs[m[1]]+256)&0xffffffff
                    if f['address']<=target<f['address']+f['size']:targets.append(target)
    assert len(set(targets))==2,(g,targets)
    return list(zip(sorted(set(targets)),(56,52)))

@functools.lru_cache(maxsize=None)
def atoms(g,n):
    f=ES[g].functions[n];aa=[];covered=set();packets=[]
    for pc,row in sorted(DEC[g].items()):
        if not f['address']<=pc<f['address']+f['size']:continue
        if any(a<=pc<a+z for a,z in table_ranges(g,n)):continue
        raw=bytes.fromhex(row['raw']);assert raw==ES[g].bytes(pc,len(raw)),(g,n,pc)
        covered.update(range(pc,pc+len(raw)))
        parts=re.split(r' -> | \|\| ',row['asm'])
        if ' || ' in row['asm']:assert sum(x!='nop' for x in parts)==1,(g,n,row)
        if len(parts)==2:
            assert bool(raw[2]&128)==(' || ' in row['asm'])
            packets.append(dict(pc=pc,asm=row['asm'],raw=raw.hex()))
        for i,asm in enumerate(parts):
            b=raw[2*i:2*i+2] if len(parts)==2 else raw
            if asm=='nop':assert int.from_bytes(b,'big')&0x7fff==0x7000;continue
            aa.append(dict(pc=pc+2*i,asm=asm,raw=b.hex(),relocation=RELOC[g].get(pc),packet=pc))
    expected=set(range(f['address'],f['address']+f['size']))
    for a,z in table_ranges(g,n):expected.difference_update(range(a,a+z))
    assert expected<=covered,(g,n,'undecoded',sorted(expected-covered))
    return aa,packets

def symbolic(g,n,aa):
    f=ES[g].functions[n];pcs=[x['pc'] for x in aa];out=[];branches=[];gotpc=[]
    for i,row in enumerate(aa):
        asm=row['asm'];rel=row['relocation']
        if rel and rel[0] in {'R_M32R_GOTOFF_HI_SLO','R_M32R_GOTOFF_LO','R_M32R_GOTPC_HI_SLO','R_M32R_GOTPC_LO'}:
            asm=re.sub(r'#[^, ]+$','#'+rel[0],asm)
        m=re.search(r'\b(bl|bra|bc|bnc|beqz|bnez|beq|bne|bgez|bltz|bgtz|blez)\s+.*?([0-9a-f]+) <([^>]+)>',asm)
        if m:
            target=int(m[2],16)
            if f['address']<=target<f['address']+f['size']:
                logical='self@'+str(bisect.bisect_left(pcs,target))
            else:logical=canon(g,m[3])
            branches.append(dict(atom=i,opcode=m[1],logical=logical,pc=row['pc'],target=target,
                return_atom=bisect.bisect_left(pcs,(row['pc']&~3)+4) if m[1]=='bl' else None))
            asm=asm[:m.start(2)]+logical
        else:asm=re.sub(r' <[^>]+>','',asm)
        out.append(asm)
        if rel and rel[0]=='R_M32R_GOTPC_LO':
            hi=aa[i-1];assert hi['relocation'][0]=='R_M32R_GOTPC_HI_SLO'
            high=int(hi['asm'].split('#')[1],0);low=int(row['asm'].split('#')[1],0)
            if low>=32768:low-=65536
            call=next(x for x in reversed(aa[:i-1]) if x['asm'].startswith('bl '))
            value=((high<<16)+low+(call['pc']&~3)+4)&0xffffffff
            assert value==256,(g,n,i,value)
            gotpc.append(dict(atom=i,value=value))
    return out,branches,gotpc

def data_targets(g,n,aa):
    regs={};out={}
    for i,row in enumerate(aa):
        m=re.fullmatch(r'seth (\w+),#(.*)',row['asm'])
        if m:regs[m[1]]=int(m[2],0)<<16
        m=re.fullmatch(r'add3 (\w+),(\w+),#(-?\w+)',row['asm'])
        if m and m[2] in regs:
            value=int(m[3],0)
            if value>=32768:value-=65536
            regs[m[1]]=(regs[m[2]]+value)&0xffffffff
            if row['relocation'] and row['relocation'][0]=='R_M32R_GOTOFF_LO':
                out[i]=(regs[m[1]]+256)&0xffffffff
    return out

def g_offset(old):
    return old

def object_info(g,a):
    ss=[s for s in ES[g].symbols.values() if s['size'] and s['address']<=a<s['address']+s['size']]
    if ss:
        s=min(ss,key=lambda s:s['size']);return dict(name=s['name'],base=s['address'],size=s['size'],offset=a-s['address'],type=s['type'],section=s['section'])
    named=[s for s in ES[g].symbols.values() if s['address']==a]
    if named:return dict(name=sorted(named,key=lambda s:s['name'])[0]['name'],base=a,size=0,offset=0,type=named[0]['type'],section=named[0]['section'])
    return None

def object_bytes(g,obj,a):
    if obj and obj['size']:base,n=obj['base'],obj['size']
    else:
        base=a;sec=next(s for s in ES[g].sections if s['base']<=a<s['base']+s['size'] and s['data'])
        ends=[s['address'] for s in ES[g].symbols.values() if s['section']==ES[g].sections.index(sec) and s['address']>a]
        n=min(ends+[sec['base']+sec['size']])-a
    try:b=ES[g].bytes(base,n)
    except ValueError:b=bytes(n)
    return base,b

def check_data(a,b):
    x,y=object_info(119,a),object_info(120,b);r=dict(old_address=a,new_address=b,old=x,new=y,equal=False,dependencies=[])
    if a==b==0:r['equal']=True;return r
    if x and y and x['type']==y['type']==2 and x['offset']==y['offset']==0:
        r['equal']=canon(119,x['name'])==canon(120,y['name']);r['dependencies']=[canon(120,y['name'])];return r
    if x and y and x['name']==y['name'] and x['name'] in ('g','n') and x['offset']==y['offset'] and x['offset']<min(x['size'],y['size']):
        r['equal']=g_offset(x['offset'])==y['offset'];r['layout_mapping']='existing fields retain their offsets; new flags use tail padding or append after the seed';return r
    if x and y and (x['type']!=y['type'] or x['size']!=y['size'] or x['offset']!=y['offset']):
        return r
    if x and y and x['name']==y['name']=='rv_call':
        ranges_a=table_ranges(119,'rv_call');ranges_b=table_ranges(120,'rv_call')
        ix=next((i for i,(p,z) in enumerate(ranges_a) if p==a),None)
        if ix is None or ranges_b[ix][0]!=b:return r
        n=ranges_a[ix][1];aa=ES[119].bytes(a,n);bb=ES[120].bytes(b,n)
    else:
        if x is None and y is None:
            # Use the entire old GAS object span including padding. Its new
            # image is compared literally. No string prefix or guessed read
            # length is used. The only new anonymous 8 B object is accounted
            # for separately below, between the mapped old spans.
            labels=[s for s in LABELS if s['address']==a]
            if not labels:return r
            section=labels[0]['section'];end=min(s['address'] for s in LABELS if s['section']==section and s['address']>a)
            aa=ES[119].bytes(a,end-a);bb=ES[120].bytes(b,end-a)
            r['old_GAS_labels']=[s['name'] for s in labels]
            r['old_full_extent_including_padding']=[a,end]
            r['new_mapped_extent']=[b,b+len(bb)]
        else:
            _,aa=object_bytes(119,x,a);_,bb=object_bytes(120,y,b)
    if x and y and x['name']==y['name']=='rv_api':
        aa,bb=bytearray(aa),bytearray(bb)
        assert int.from_bytes(aa[16:20],'big')==ES[119].functions['rv_call']['address']
        assert int.from_bytes(bb[16:20],'big')==ES[120].functions['rv_call']['address']
        for g,obj in ((119,x),(120,y)):assert RELOC[g][obj['base']+16][0]=='R_M32R_32_RELA'
        aa[16:20]=bb[16:20]=bytes(4);r['dependencies']=['rv_call']
    r.update(equal=aa==bb,old_bytes=len(aa),new_bytes=len(bb),old_sha256=sha(aa),new_sha256=sha(bb))
    return r

def pointer_states(g,n,aa,branches):
    """Forward must-analysis of register addresses; joins discard conflicts."""
    targets=data_targets(g,n,aa);br={r['atom']:r for r in branches};states={0:{}};todo=[0]
    def tag(a):
        obj=object_info(g,a)
        return ('relative',obj['name'],obj['offset']) if obj else None
    while todo:
        i=todo.pop();before=states[i];after=dict(before);row=aa[i]
        asm=re.sub(r' <[^>]+>','',row['asm']);op,*rest=asm.split(' ',1)
        args=rest[0].split(',') if rest else [];dest=args[0] if args else ''
        def kill():after.pop(dest,None)
        rel=row['relocation']
        if rel and rel[0]=='R_M32R_GOTOFF_LO':
            kill();t=tag(targets[i])
            if t:after[dest]=t
        elif rel and rel[0]=='R_M32R_GOTPC_LO':after[dest]=('got-unadjusted','got',0)
        elif op=='mv':
            kill()
            if len(args)==2 and args[1] in before:after[dest]=before[args[1]]
        elif op=='add' and len(args)==2:
            a,b=before.get(dest),before.get(args[1]);kill()
            if a and a[0]=='got-unadjusted' and args[1]=='lr':after[dest]=('got','got',0)
            elif a and b and a[0]=='relative' and b[0]=='got':after[dest]=('address',a[1],a[2])
        elif op in ('addi','add3'):
            src=dest if op=='addi' else args[1];value=args[-1]
            t=before.get(src);kill()
            if t and value.startswith('#'):
                value=int(value[1:],0)
                if value>=32768:value-=65536
                after[dest]=(t[0],t[1],t[2]+value)
        elif op in ('bl','jl'):
            b=br.get(i)
            if not b or not b['logical'].startswith('self@'):
                for reg in [f'r{k}' for k in range(8)]+['lr']:after.pop(reg,None)
        elif op not in ('push','st','stb','sth','cmp','cmpu','cmpeq','cmpz','nop','bra','bc','bnc','beqz','bnez','beq','bne','bgez','bltz','bgtz','blez','jmp'):
            kill()
        b=br.get(i);nexts=[]
        if b and b['opcode']!='bl':
            if b['logical'].startswith('self@'):nexts.append(int(b['logical'].split('@')[1]))
            if b['opcode']!='bra':nexts.append(i+1)
        elif b and b['opcode']=='bl':nexts.append(b['return_atom'])
        elif op!='jmp':nexts.append(i+1)
        for j in nexts:
            if j>=len(aa):continue
            merged=after if j not in states else {k:v for k,v in states[j].items() if after.get(k)==v}
            if j not in states or merged!=states[j]:states[j]=dict(merged);todo.append(j)
    return states

def layout_change(a,b,sa,sb):
    """Accept only a proved g-field relocation, retaining opcode and registers."""
    ma=re.fullmatch(r'(ld(?:ub|b|uh|h)?|st(?:b|h)?) (\w+),@\((-?\d+),(\w+)\)',a)
    mb=re.fullmatch(r'(ld(?:ub|b|uh|h)?|st(?:b|h)?) (\w+),@\((-?\d+),(\w+)\)',b)
    if ma and mb and ma.group(1,2)==mb.group(1,2) and ma[4]==mb[4]:
        ta,tb=sa.get(ma[4]),sb.get(mb[4])
        if ta and tb and ta[:2]==tb[:2]==('address','g'):
            x,y=ta[2]+int(ma[3]),tb[2]+int(mb[3])
            if g_offset(x)==y:return dict(kind='g-field-memory',old_offset=x,new_offset=y,base_register=ma[4])
    ma=re.fullmatch(r'add3 (\w+),(\w+),#(-?\d+)',a);mb=re.fullmatch(r'add3 (\w+),(\w+),#(-?\d+)',b)
    if ma and mb and ma.group(1,2)==mb.group(1,2):
        ta,tb=sa.get(ma[2]),sb.get(mb[2])
        if ta and tb and ta[:2]==tb[:2]==('address','g'):
            x,y=ta[2]+int(ma[3]),tb[2]+int(mb[3])
            if g_offset(x)==y:return dict(kind='g-field-pointer',old_offset=x,new_offset=y,base_register=ma[2])
    return None

def main():
    result=[];packets=[];patch=[]
    for n in sorted(set(ES[119].functions)|set(ES[120].functions)):
        old,new=ES[119].functions.get(n),ES[120].functions.get(n)
        if not old or not new:
            result.append(dict(name=n,status='added' if new else 'removed',old_size=old['size'] if old else 0,new_size=new['size'] if new else 0))
            continue
        aa,pa=atoms(119,n);bb,pb=atoms(120,n)
        na,ba,ga=symbolic(119,n,aa);nb,bbr,gb=symbolic(120,n,bb)
        sa,sb=pointer_states(119,n,aa,ba),pointer_states(120,n,bb,bbr)
        layout=[]
        if len(na)==len(nb):
            for i,(x,y) in enumerate(zip(na,nb)):
                if x==y:continue
                proof=layout_change(x,y,sa.get(i,{}),sb.get(i,{}))
                if proof:
                    layout.append(dict(atom=i,old=x,new=y,**proof))
                    na[i]=nb[i]='LAYOUT '+str(proof['old_offset'])+' '+re.sub(r'[-#]?\d+(?=[,) ]|$)','FIELD',x)
        ta,tb=data_targets(119,n,aa),data_targets(120,n,bb)
        dd=[dict(atom=i,**check_data(ta[i],tb[i])) if i in ta and i in tb else dict(atom=i,equal=False,reason='unpaired target') for i in sorted(set(ta)|set(tb))]
        assert len(ta)==sum(x['relocation'] is not None and x['relocation'][0]=='R_M32R_GOTOFF_LO' for x in aa)
        assert len(tb)==sum(x['relocation'] is not None and x['relocation'][0]=='R_M32R_GOTOFF_LO' for x in bb)
        branchkey=lambda br:[(x['atom'],x['opcode'],x['logical'],x['return_atom']) for x in br]
        stack=lambda rows:[r['asm'] for r in rows if re.match(r'(?:push |pop |(?:add3|addi) sp,)',r['asm'])]
        rawbad=[]
        for i,(x,y) in enumerate(zip(aa,bb)):
            rx,ry=bytes.fromhex(x['raw']),bytes.fromhex(y['raw'])
            if len(rx)==2:rx=(int.from_bytes(rx,'big')&0x7fff).to_bytes(2,'big')
            if len(ry)==2:ry=(int.from_bytes(ry,'big')&0x7fff).to_bytes(2,'big')
            if x['relocation'] and x['relocation'][0] in {'R_M32R_GOTOFF_HI_SLO','R_M32R_GOTOFF_LO','R_M32R_GOTPC_HI_SLO','R_M32R_GOTPC_LO'}:rx,ry=rx[:2],ry[:2]
            elif x['asm'].split(' ')[0] in BRANCH:continue
            elif i in {p['atom'] for p in layout}:rx,ry=rx[:2],ry[:2]
            if rx!=ry:rawbad.append(dict(atom=i,old=x,new=y))
        dependencies={x['logical'] for x in bbr if not x['logical'].startswith('self@')}
        for d in dd:dependencies.update(d.get('dependencies',[]))
        ok=na==nb and not rawbad and branchkey(ba)==branchkey(bbr) and stack(aa)==stack(bb) and all(d['equal'] for d in dd)
        row=dict(name=n,status='identical' if old['bytes']==new['bytes'] else 'changed',old_size=old['size'],new_size=new['size'],
            local_A=ok,old_atoms=len(aa),new_atoms=len(bb),symbolic_equal=na==nb,branches_equal=branchkey(ba)==branchkey(bbr),
            stack_equal=stack(aa)==stack(bb),data_checks=dd,raw_differences=rawbad,
            gotpc_checks=dict(old=ga,new=gb),dependencies=sorted(dependencies))
        row['g_layout_translation']=layout
        save('codegen/'+n+'.json',row);result.append(row)
        if old['bytes']!=new['bytes']:
            patch.extend(difflib.unified_diff(na,nb,fromfile='119/'+n,tofile='120/'+n,lineterm=''))
            packets.extend(dict(generation=g,function=n,**p) for g,pp in ((119,pa),(120,pb)) for p in pp)
    switches=[]
    for i in range(2):
        rows=[]
        for g in ES:
            a,z=table_ranges(g,'rv_call')[i];pcs=[x['pc'] for x in atoms(g,'rv_call')[0]]
            rel=struct.unpack('>'+str(z//4)+'i',ES[g].bytes(a,z));targets=[a+x for x in rel]
            assert all(t in pcs for t in targets)
            rows.append(dict(generation=g,base=a,offsets=rel,atoms=[bisect.bisect_left(pcs,t) for t in targets]))
        # rv_call has an intentional guard insertion; independently validate every target.
        equivalent=rows[0]['offsets']==rows[1]['offsets'] and rows[0]['atoms']==rows[1]['atoms']
        switches.append(dict(index=i,pair=rows,all_targets_valid=True,literal_equivalent=equivalent))
    leaves=[]
    prior=json.loads((ROOT/'research/review_g117_codegen/untyped-assembly-functions.json').read_text())
    for r in prior:
        n=r['name'];a=ES[119].symbols[n]['address'];b=ES[120].symbols[n]['address'];z=r['size117']
        x,y=ES[119].bytes(a,z),ES[120].bytes(b,z);assert x==y,n
        leaves.append(dict(name=n,old=a,new=b,bytes=z,sha256=sha(x),equal=True))
    save('codegen-inventory.json',result);save('packet-modes.json',packets);save('switch-tables.json',switches);save('assembly-leaves.json',leaves)
    save('anonymous-data-pool.json',dict(old_retained_GAS_engine_equal=True,
        labels=[s for s in LABELS if s['name'].startswith('.LC')],
        compared_by_each_full_object_extent=True))
    (OUT/'normalized.patch').write_text('\n'.join(patch)+'\n')
    print('COUNTS',dict(collections.Counter(x['status'] for x in result)))
    print('A_PASSED',sum(x.get('local_A',False) for x in result))
    print('A_OPEN',[(x['name'],x.get('symbolic_equal'),x.get('stack_equal'),[d['atom'] for d in x.get('data_checks',[]) if not d['equal']]) for x in result if x.get('local_A') is False])

if __name__=='__main__':main()
