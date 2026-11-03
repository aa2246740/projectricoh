"""Independent final-ELF inventory. Writes only next to this script."""
from pathlib import Path
import collections, csv, difflib, hashlib, json, re, struct, subprocess

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
TC=ROOT/'research/tooling_m32r/prefix/bin'
BASE=0x21000000
def sha(b): return hashlib.sha256(b).hexdigest()
def save(n,x): (OUT/n).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
class Elf:
    def __init__(self,path):
        self.path=Path(path); self.raw=self.path.read_bytes()
        assert self.raw[:6]==b'\x7fELF\x01\x02'
        h=struct.unpack_from('>16sHHIIIIIHHHHHH',self.raw)
        ss=[struct.unpack_from('>10I',self.raw,h[6]+i*h[11]) for i in range(h[12])]
        sn=ss[h[13]]; names=self.raw[sn[4]:sn[4]+sn[5]]
        self.sections=[];self.symbols={}
        for s in ss:
            name=names[s[0]:].split(b'\0',1)[0].decode()
            self.sections.append(dict(name=name,type=s[1],base=s[3],size=s[5],offset=s[4],data=self.raw[s[4]:s[4]+s[5]] if s[1]!=8 else b''))
            if s[1]==2:
                st=ss[s[6]];strings=self.raw[st[4]:st[4]+st[5]]
                for off in range(s[4],s[4]+s[5],s[9]):
                    n,v,z,info,other,section=struct.unpack_from('>IIIBBH',self.raw,off)
                    n=strings[n:].split(b'\0',1)[0].decode()
                    if n:self.symbols[n]=dict(name=n,address=v,size=z,type=info&15,section=section)
        self.engine=next(s for s in self.sections if s['name']=='.engine')
        self.functions={n:s for n,s in self.symbols.items() if s['type']==2 and s['size']}
        for s in self.functions.values():s['bytes']=self.bytes(s['address'],s['size']).hex()
    def bytes(self,addr,n):
        for s in self.sections:
            if s['base']<=addr and addr+n<=s['base']+s['size'] and s['data']:
                return s['data'][addr-s['base']:addr-s['base']+n]
        raise ValueError(hex(addr))

def listing(path):
    return subprocess.check_output([str(TC/'m32r-elf-objdump'),'-dr',str(path)],text=True)
def rows(text):
    r={}
    for m in re.finditer(r'^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*(.*?)\s*$',text,re.M):
        a=int(m[1],16); b=bytes.fromhex(m[2]);asm=m[3]
        if len(b) in (2,4) and asm and not asm.startswith('.'):
            r[a]=dict(pc=a,raw=b.hex(),asm=asm)
    return r
def canonical(n):return re.sub(r'(?:\.lto_priv\.\d+)+$','',n)

def main():
    es={g:Elf(ROOT/f'firmware/{d}/candidate/local/full-r13/engine.elf') for g,d in ((116,'engine_v37'),(117,'engine_v38_ro'))}
    identities={}
    for g,e in es.items():
        (OUT/f'engine{g}.elf').write_bytes(e.raw)
        raw=(ROOT/('firmware/image_v35/local/package/SD_ROOT/GXRCE.DAT' if g==116 else 'firmware/package_v35_g117/SD_ROOT/GXRCE.DAT')).read_bytes()
        expected={116:'1e033dfbcc3ca0bec0e1e5befbdb5579950e9aa8aacfbfd56f8c7342b9a97864',117:'4f5eeaffdfc4df77d9482887b827fe8ec73e7857b13ea76348e3e49c874d0b5a'}[g]
        assert sha(raw)==expected
        codeoff,codesize=struct.unpack_from('>II',raw,132)
        assert raw[codeoff:codeoff+codesize]==e.engine['data']
        (OUT/f'container{g}.dat').write_bytes(raw)
        l=listing(e.path);(OUT/f'engine{g}.dis').write_text(l)
        save(f'symbols{g}.json',e.symbols);save(f'decode{g}.json',rows(l))
        identities[g]=dict(dat_sha256=sha(raw),elf_sha256=sha(e.raw),engine_sha256=sha(e.engine['data']),engine_offset=codeoff,engine_size=codesize,source=str(e.path.relative_to(ROOT)))
    old,new=es[116],es[117]
    previous={x['symbol']:x for x in csv.DictReader((ROOT/'research/review_g117_container/symbol-diff.tsv').open(),delimiter='\t')}
    inventory=[];used=set()
    for n,b in sorted(new.functions.items()):
        if n in old.functions:a=old.functions[n]
        elif n+'.lto_priv.0' in old.functions:a=old.functions[n+'.lto_priv.0']
        else:
            candidates=[s for nn,s in old.functions.items() if canonical(nn)==canonical(n)]
            exact=[s for s in candidates if s['bytes']==b['bytes']]
            a=(exact or candidates or [None])[0]
        if a:used.add(a['name'])
        status='added' if not a else 'identical' if a['bytes']==b['bytes'] else 'changed'
        inventory.append(dict(name=n,old_name=a['name'] if a else '',old_size=a['size'] if a else 0,new_size=b['size'],old_address=a['address'] if a else None,new_address=b['address'],status=status,reviewer_listed=n in previous,reviewer_status=previous.get(n,{}).get('status','missing')))
    for n,a in old.functions.items():
        if n not in used:inventory.append(dict(name=n,old_name=n,old_size=a['size'],new_size=0,status='removed',reviewer_listed=n in previous))
    save('identities.json',identities);save('inventory.json',inventory)
    with (OUT/'all-functions.tsv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=['name','old_name','old_size','new_size','old_address','new_address','status','reviewer_listed','reviewer_status'],delimiter='\t');w.writeheader();w.writerows(inventory)
    print('identities',identities)
    print('counts',dict(collections.Counter(x['status'] for x in inventory)))
    print('changed',[(x['name'],x['old_size'],x['new_size']) for x in inventory if x['status']=='changed'])
    print('missing from previous',[x['name'] for x in inventory if not x['reviewer_listed']])

if __name__=='__main__':main()
