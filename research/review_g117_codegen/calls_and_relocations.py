"""All direct/indirect references and real encoded relocation target pairing."""
from pathlib import Path
import collections,json,re,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from normalize import ES,INV,OUT,RELOC,atoms,normalized
from audit import save,canonical

def object_at(g,a):
    ss=[s for s in ES[g].symbols.values() if s['size'] and s['address']<=a<s['address']+s['size']]
    if not ss:return None
    s=min(ss,key=lambda s:s['size'])
    return dict(name=s['name'],base=s['address'],size=s['size'],offset=a-s['address'],type=s['type'])
def targets(g,name):
    regs={};ans={}
    for i,t in enumerate(atoms(g,name)):
        s=t['asm'];m=re.fullmatch(r'seth (\w+),#(.*)',s)
        if m:regs[m[1]]=int(m[2],0)<<16
        m=re.fullmatch(r'add3 (\w+),(\w+),#(-?\w+)',s)
        if m and m[2] in regs:
            v=int(m[3],0)
            if 0x8000<=v<=0xffff:v-=65536
            regs[m[1]]=(regs[m[2]]+v)&0xffffffff
            if t['relocation'] and t['relocation'][0]=='R_M32R_GOTOFF_LO':
                a=(regs[m[1]]+256)&0xffffffff
                ans[i]=dict(address=a,object=object_at(g,a),asm=s,pc=t['pc'])
    return ans
def main():
    norms=json.loads((OUT/'normalization.json').read_text());pairs=[];mapping={};issues=[]
    for r in norms:
        if not r['equal']:continue
        a,b=targets(116,r['old_name']),targets(117,r['name'])
        for i in sorted(set(a)|set(b)):
            x,y=a.get(i),b.get(i);row=dict(function=r['name'],atom=i,old=x,new=y)
            if not x or not y:row['ok']=False
            elif x['object'] and y['object']:
                aa,bb=x['object'],y['object'];names=canonical(aa['name'])==canonical(bb['name'])
                row['ok']=aa['type']==bb['type'] and aa['size']==bb['size'] and aa['offset']==bb['offset']
                if aa['type']==bb['type']==2:
                    row['ok']=names and aa['offset']==bb['offset']==0
                    row['note']='same logical function entry; callee equivalence is a separate obligation'
                    if aa['name']==bb['name']=='rv_call' and aa['offset']==bb['offset'] and aa['offset'] in (3340,3584):
                        n=56 if aa['offset']==3340 else 52
                        ab=ES[116].bytes(x['address'],n);bc=ES[117].bytes(y['address'],n)
                        row['switch_table_bytes']=n;row['switch_table_equal']=ab==bc
                        row['ok']=ab==bc;row['note']='identical bounded relative switch table in rv_call, 14 or 13 entries'
                row['same_named_object']=names
                if aa['type']==1:
                    key=(aa['base'],bb['base']);mapping[key]=(aa,bb)
                    # Initialized objects must also have identical byte contents.
                    try:
                        ab=ES[116].bytes(aa['base'],aa['size']);bc=ES[117].bytes(bb['base'],bb['size'])
                        row['initialized_equal']=ab==bc
                        if aa['name']==bb['name']=='rv_api':
                            cells=[];equal=True
                            for off in range(0,len(ab),4):
                                av,bv=int.from_bytes(ab[off:off+4],'big'),int.from_bytes(bc[off:off+4],'big')
                                if av==bv:continue
                                an=[canonical(n) for n,s in ES[116].functions.items() if s['address']==av]
                                bn=[canonical(n) for n,s in ES[117].functions.items() if s['address']==bv]
                                good=bool(set(an)&set(bn));equal &=good;cells.append(dict(offset=off,old_targets=an,new_targets=bn,logical_target_equal=good))
                            row['pointer_cells']=cells;row['ok'] &= equal
                        else:row['ok'] &= ab==bc
                    except ValueError:row['initialized_equal']='both BSS'
            else:
                ax,by=x['address'],y['address']
                if ax==by==0:
                    row['ok']=True;row['note']='__image_base=0 in both original linked ELFs'
                else:
                    try:
                        ab=ES[116].bytes(ax,64);bc=ES[117].bytes(by,64)
                        need=8 if ab[0]==0 else ab.index(0)+1
                        row['constant_bytes_compared']=need;row['constant_hex']=ab[:need].hex()
                        row['ok']=ab[:need]==bc[:need]
                        row['note']='anonymous constant identity only; read bounds must follow the caller contract'
                    except (ValueError,IndexError):row['ok']=False
            pairs.append(row)
            if not row['ok']:issues.append(row)
    save('relocation-pairs.json',pairs);save('object-map.json',[dict(old=x,new=y) for x,y in mapping.values()])
    save('relocation-unresolved.json',issues)
    refs=[]
    funcs=ES[117].functions
    # Explicit ELF relocation references, including taken function addresses.
    for pc,(kind,expr) in RELOC[117].items():
        target=re.sub(r'\+0x[0-9a-f]+$','',expr)
        if target in funcs:
            owner=next((n for n,s in funcs.items() if s['address']<=pc<s['address']+s['size']),None)
            refs.append(dict(pc=hex(pc),kind=kind,target=target,owner=owner,expression=expr))
    # Taken function addresses can use section-relative relocations. Recover their encoded values as above.
    for n in funcs:
        for i,t in targets(117,n).items():
            names=[k for k,s in funcs.items() if s['address']==t['address']]
            for target in names:refs.append(dict(pc=hex(t['pc']),kind='encoded GOTOFF function address',target=target,owner=n))
    exports=['ig_bootstrap','ig_init','ig_menu','ig_event','ig_panel_open','ig_panel_event','ig_panel_abort','ig_apply','ig_stop']
    for n in exports:refs.append(dict(pc=hex(funcs[n]['address']),kind='resident entry offset, DAT/bootstrap exports',target=n,owner='resident'))
    indirect=[]
    for n in funcs:
        for t in atoms(117,n):
            if re.match(r'j(?:l|mp)\b',t['asm']) and t['asm']!='jmp lr':indirect.append(dict(caller=n,pc=hex(t['pc']),asm=t['asm']))
    save('function-address-references.json',refs);save('indirect-transfers.json',indirect)
    calls=json.loads((OUT/'direct-calls.json').read_text());summary=[]
    for r in INV:
        if r['status']!='changed':continue
        n=r['name'];summary.append(dict(name=n,direct=[dict(caller=c['caller'],pc=hex(c['pc']),kind=c['kind']) for c in calls if n in c['targets']],address_taken=[x for x in refs if x['target']==n]))
    save('callsite-inventory.json',summary)
    print('relocation pairs',len(pairs),'unresolved',len(issues),'mapped objects',len(mapping),'function refs',len(refs),'indirect transfers',len(indirect))
    print('unresolved functions',sorted({r['function'] for r in issues}))
if __name__=='__main__':main()
