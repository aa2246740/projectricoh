"""Exercise final protected bodies. Explicit, common callee boundary models."""
from pathlib import Path
import collections,json,random,struct,sys,time
sys.path.insert(0,str(Path(__file__).resolve().parent))
from execute import Runner,BASE,DATA,STACK,SP,OUT,save

class Pair:
    def __init__(self):
        self.a,self.b=Runner(116),Runner(117);self.rs=(self.a,self.b)
        self.objects=json.loads((OUT/'object-map.json').read_text());self.calls=collections.Counter()
        self.memo={};self.mode={};self.g={r.g:BASE+r.e.symbols.get('g',r.e.symbols.get('g.lto_priv.0'))['address'] for r in self.rs}
    def pointer(self,r,v):
        for i,x in enumerate(self.objects):
            o=x['old' if r.g==116 else 'new']
            if BASE+o['base']<=v<BASE+o['base']+o['size']:return 0x50000000+0x10000*i+v-BASE-o['base']
        for n,s in r.e.functions.items():
            if v==BASE+s['address']:return 'function:'+__import__('re').sub(r'(?:\.lto_priv\.\d+)+$','',n)
        return v
    def projection(self,r,x):
        out=[]
        for a,d,pc in x['writes']:
            if STACK<=a<STACK+0x10000:continue
            value=int(d,16)
            if len(d)==8:value=self.pointer(r,value)
            out.append((self.pointer(r,a),len(d)//2,value))
        # A forward byte copy can serialize an actual pointer in four byte stores.
        # Keep each write and its order, but compare the reconstructed pointer under the object map.
        i=0
        while i+3<len(out):
            a0,z0,v0=out[i]
            if isinstance(a0,int) and a0%4==0 and all(out[i+j][0]==a0+j and out[i+j][1]==1 and isinstance(out[i+j][2],int) for j in range(4)):
                value=int.from_bytes(bytes(out[i+j][2] for j in range(4)),'big');logical=self.pointer(r,value)
                if logical!=value:
                    for j in range(4):out[i+j]=(a0+j,1,str(logical)+':byte'+str(j))
                i+=4
            else:i+=1
        return out
    def hook(self,name,key=None):
        key=key or name
        for r in self.rs:
            actual=name
            if actual not in r.e.functions:actual=name+'.lto_priv.0'
            if actual not in r.e.functions:continue
            def cb(b,key=key,r=r):
                self.calls[(r.g,key)]+=1
                return self.mode.get(key,0)
            r.hook(actual,cb)
    def result(self,name,args,i,extra=()):
        results=[]
        for r in self.rs:
            r.reset(i+0x661100);results.append(r.call(name,args,extra))
        a,b=results
        ok=a['stop']['reason']==b['stop']['reason']=='return' and a['result']==b['result'] and a['saved']==b['saved'] and a['abi_ok'] and b['abi_ok'] and self.projection(self.a,a)==self.projection(self.b,b)
        return a,b,ok

def run(which,count):
    p=Pair();rng=random.Random(0x111777);fail=[];cov={116:set(),117:set()};start=time.time();status=collections.Counter()
    if which=='es_range.constprop.0':p.hook('es_session.constprop.0')
    if which=='eng_current':p.hook('fresh')
    if which=='ig_apply':
        for n in ('ingress','a4_move','ui_finish','list_bind','finish'):p.hook(n)
    if which=='list_bind':
        for r in p.rs:r.b.map(0x2022f000,bytes(4096));r.b.map(0x205a2000,bytes(4096))
        for n in ('ig_bx_receipt','ig_bx_event','pn_call'):p.hook(n)
        # The full earlier run executes these identical helper bodies. This rerun
        # uses their exact register/store effects to focus time on list_bind itself.
        for r in p.rs:
            def copy_model(b):
                dest,src,n=b.core.r[:3]
                for j in range(n):b.write(dest+j,b.read(src+j,1))
                b.core.r[4]=n
                if n:b.core.r[5]=(dest+n-1)&0xffffffff;b.core.r[6]=b.read(dest+n-1,1)[0]
                return dest
            def zero_model(b):
                dest,n=b.core.r[:2]
                for j in range(n):b.write(dest+j,b'\0')
                b.core.r[1]=(dest+n)&0xffffffff;b.core.r[4]=0
                return (dest+n)&0xffffffff
            r.hook('ig_copy',copy_model);r.hook('ig_zero',zero_model)
    if which=='workspace_close':
        p.hook('pn_call')
        p.objects.extend([dict(old=dict(base=0x12c4c,size=64),new=dict(base=0xe3a8,size=64)),dict(old=dict(base=0x12c2c,size=32),new=dict(base=0xe388,size=32))])
    for i in range(count):
        extra=()
        if which=='es_range.constprop.0':
            session=DATA+0x10000;token=rng.getrandbits(32);base=rng.randrange(0x2000,0x4000)+DATA;length=rng.randrange(0,0x2001)
            valid=rng.randrange(3)!=0;p.mode['es_session.constprop.0']=session if rng.randrange(5) else 0
            mem=bytearray(300)
            for j in range(6):
                t=token if valid and j==i%6 else rng.getrandbits(32);lo=base-rng.randrange(0,0x1000);n=rng.randrange(0,0x4000)
                struct.pack_into('>5I',mem,160+20*j,t,t^0xffffffff,lo,n,0)
            for r in p.rs:r.write(session,mem)
            args=(token,base,length)
        elif which=='eng_current':
            mode=rng.randrange(4);p.mode['fresh']=rng.randrange(2)
            recipe=bytes(rng.getrandbits(8) for j in range(51));tweak=bytes(rng.getrandbits(8) for j in range(8))
            for r in p.rs:
                r.write(p.g[r.g]+184,recipe+tweak);r.write(p.g[r.g]+2467,bytes([mode&1,(mode>>1)&1]));r.write(DATA,bytes(80))
            args=(DATA,DATA+64)
        elif which=='ig_apply':
            active=rng.randrange(2);panel=rng.randrange(2);ready=rng.randrange(2);rows=rng.randrange(1,9);row=rng.choice([0,1,7,8,255,0xffffffff,rng.getrandbits(32)])
            p.mode.update(ingress=rng.randrange(2),a4_move=rng.choice([0,1,2,3,0xffffffff]),ui_finish=rng.randrange(5),list_bind=rng.choice([0,1,0xffffffff]),finish=rng.randrange(5))
            for r in p.rs:
                r.write(r.n+2072,bytes([active]));r.write(r.n+550,bytes([panel]));r.write(p.g[r.g]+805,bytes([ready]));r.write(p.g[r.g]+807,bytes([rows]));r.w32(DATA+40,row)
            args=(0,0,DATA,DATA+0x100)
        elif which=='workspace_close':
            token=rng.choice([0,1,0xffffffff,rng.getrandbits(32)]);released=rng.randrange(2)
            port=bytes(rng.getrandbits(8) for _ in range(48));lease=bytearray(rng.getrandbits(8) for _ in range(32));lease[8:12]=token.to_bytes(4,'big')
            p.mode['pn_call']=rng.choice([0,0xffffffff,0xfffffffd,0xfffffff5])
            for r in p.rs:
                r.write(r.n+380,port);r.write(r.n+2092,lease);r.write(r.n+2076,bytes([0,released]))
            args=()
        else:
            ctx=DATA+0x1000;cap=rng.choice([0,235,236,237,1024]);state=DATA+0x4000
            p.mode['pn_call']=rng.choice([0,0,0,0xffffffff]);rows=rng.randrange(1,9)
            for r in p.rs:
                r.write(r.n,bytes(3712));r.w32(r.n+4,ctx if i%10 else 0);r.write(ctx,bytes(128));r.w32(ctx+64,state);r.w32(ctx+72,cap)
                r.write(0x2022f71c,bytes([5])+bytes(31));r.w32(0x2022f720,0x2022f56c);r.write(0x2022f56c,bytes(72));r.write(state,bytes(236))
                r.write(p.g[r.g]+803,bytes([1,0,1,0,rows]));r.w32(r.n+428,r.n+380)
            args=()
        a,b,ok=p.result(which,args,i,extra)
        status[(a['result'],b['result'])]+=1
        for r,x in ((p.a,a),(p.b,b)):cov[r.g].update(x['edges'])
        if not ok and len(fail)<4:fail.append(dict(index=i,old=a,new=b,old_projection=p.projection(p.a,a),new_projection=p.projection(p.b,b)))
        if i%2000==0:print(which,i,flush=True)
    summary=dict(name=which,random=count,failures=fail,status_counts={str(k):v for k,v in status.items()},coverage={g:[(hex(pc),t) for pc,t in sorted(c)] for g,c in cov.items()},callee_calls={str(k):v for k,v in p.calls.items()},elapsed=time.time()-start)
    save(which.replace('.','_')+'-results.json',summary)
    print(which,'complete failures',len(fail),'elapsed',summary['elapsed'],flush=True)
if __name__=='__main__':run(sys.argv[1],int(sys.argv[2]) if len(sys.argv)>2 else 10000)
