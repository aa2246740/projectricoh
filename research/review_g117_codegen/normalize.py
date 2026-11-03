"""Decode packet order independently; retain every non-relocation constant."""
from pathlib import Path
import bisect, collections, difflib, json, re, sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from audit import OUT,ROOT,Elf,save,canonical

ES={g:Elf(OUT/f'engine{g}.elf') for g in (116,117)}
INV=json.loads((OUT/'inventory.json').read_text())
DEC={g:json.loads((OUT/f'decode{g}.json').read_text()) for g in ES}
ALIASES={}
for e in ES.values():
    for n,s in e.functions.items():ALIASES.setdefault(s['bytes'],set()).add(n)
ALIASES={n:min(names,key=lambda x:(len(x),x)) for names in ALIASES.values() for n in names}
def fname(n):return canonical(ALIASES.get(n,n))
RELOC={}
for g in ES:
    RELOC[g]={int(m[1],16):(m[2],m[3]) for m in re.finditer(r'^\s*([0-9a-f]+): (R_M32R_[A-Z0-9_]+)\s+(.+)$',(OUT/f'engine{g}.dis').read_text(),re.M)}
def atoms(g,n):
    s=ES[g].functions[n];ans=[]
    for a,r in sorted(DEC[g].items(),key=lambda t:int(t[0])):
        a=int(a)
        if not s['address']<=a<s['address']+s['size']:continue
        parts=re.split(r' -> | \|\| ',r['asm'])
        assert not (' || ' in r['asm'] and sum(p!='nop' for p in parts)>1),r
        for i,p in enumerate(parts):
            if p!='nop':ans.append(dict(pc=a+2*i,asm=p,relocation=RELOC[g].get(a)))
    return ans
def normalized(g,n):
    s=ES[g].functions[n];aa=atoms(g,n);pcs=[r['pc'] for r in aa];ans=[]
    for r in aa:
        a=r['asm']
        if r['relocation']:
            a=re.sub(r'#[^, ]+$','#'+r['relocation'][0],a)
        m=re.search(r'\b(bl|bra|bc|bnc|beqz|bnez|beq|bne|bgez|bltz|bgtz|blez)\s+.*?([0-9a-f]+) <([^>]+)>',a)
        if m:
            target=int(m[2],16)
            if s['address']<=target<s['address']+s['size']:
                t='self@'+str(bisect.bisect_left(pcs,target))
            else:t=fname(m[3])
            a=a[:m.start(2)]+t
        else:a=re.sub(r' <[^>]+>','',a)
        ans.append(a)
    return ans

def main():
    result=[];patch=[];calls=[]
    for r in INV:
        if r['status']!='changed':continue
        a=normalized(116,r['old_name']);b=normalized(117,r['name'])
        row=dict(name=r['name'],old_name=r['old_name'],equal=a==b,old_atoms=len(a),new_atoms=len(b))
        result.append(row)
        patch.extend(difflib.unified_diff(a,b,fromfile='116/'+r['old_name'],tofile='117/'+r['name'],lineterm=''))
        oldasm=[hex(t['pc'])+' '+t['asm'] for t in atoms(116,r['old_name'])]
        newasm=[hex(t['pc'])+' '+t['asm'] for t in atoms(117,r['name'])]
        (OUT/'side-by-side').mkdir(exist_ok=True)
        (OUT/'side-by-side'/ (r['name']+'.txt')).write_text('\n'.join(f'{a:<95} | {b}' for a,b in __import__('itertools').zip_longest(oldasm,newasm,fillvalue=''))+'\n')
    for n in ES[117].functions:
        for t in atoms(117,n):
            m=re.search(r'\b(bl|bra)\s+([0-9a-f]+) <([^>]+)>',t['asm'])
            if m:
                to=int(m[2],16)
                targets=[k for k,v in ES[117].functions.items() if v['address']==to]
                if targets:calls.append(dict(caller=n,pc=t['pc'],kind=m[1],targets=targets,asm=t['asm']))
    save('normalization.json',result);save('direct-calls.json',calls)
    (OUT/'normalized.patch').write_text('\n'.join(patch)+'\n')
    print('normalized_equal',sum(r['equal'] for r in result),'/',len(result))
    print('unequal',[r['name'] for r in result if not r['equal']])
    print('packets with only nop parallel, no general parallel pair')

if __name__=='__main__':main()
