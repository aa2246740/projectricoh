"""Differential tests for compiler-changed small functions on real instructions."""
from pathlib import Path
import collections,json,random,struct,sys,time,zlib
sys.path.insert(0,str(Path(__file__).resolve().parent))
from execute import Runner,OUT,ROOT,BASE,DATA,SP,END,save,put

def projection(r):return [(a,d) for a,d,pc in r['writes']]
def compared(a,b,name,args,seed,extra=()):
    for r in (a,b):r.reset(seed)
    aa=a.call(name,args,extra);bb=b.call(name,args,extra)
    return aa,bb,aa['result']==bb['result'] and aa['saved']==bb['saved'] and aa['abi_ok'] and bb['abi_ok'] and projection(aa)==projection(bb) and aa['stop']['reason']==bb['stop']['reason']=='return'

def pn(count):
    a,b=Runner(116),Runner(117);rng=random.Random(117116);p=DATA+0x1000
    for r in (a,b):r.write(p,bytes(48));r.w32(p+40,BASE+r.e.functions['address']['address'])
    sites=[('0x0f48',4),('0x0f64',72),('0x0f70',44),('0x1534',None),('0x3e00',None),('0x4030',None),('0x4054',18),('0x413c',32),('0x4168',44),('0x417c',132)]
    results=[];start=time.time()
    for site,n in sites:
        failures=[]
        for i in range(count):
            length=n or (rng.randrange(1,257) if site=='0x1534' else rng.choice([9,40,48]) if site=='0x3e00' else rng.randrange(1,10))
            s=DATA+0x3000+rng.randrange(0x10000)
            aa,bb,ok=compared(a,b,'pn_address',(p,s,length),i+0x5000)
            if not ok:failures.append(dict(index=i,old=aa,new=bb))
        results.append(dict(site=site,random=count,failures=failures))
        print('pn_address site',site,'cases',count,'failures',len(failures),flush=True)
    boundaries=[]
    for s in (0,1,0xff,0xffffff00,0xfffffffe,0xffffffff):
        for n in (0,1,2,4,9,18,32,44,72,132,256,0x7fffffff,0xffffffff):
            aa,bb,ok=compared(a,b,'pn_address',(p,s,n),s^n)
            boundaries.append(dict(s=hex(s),n=n,equal=ok,result116=aa['result'],result117=bb['result']))
    # No mapper overflow calculation. These inputs are outside the camera's fixed address callback invariant.
    for r in (a,b):r.w32(p+40,0)
    fallback=[]
    for s in (0,1,0xffffff00,0xfffffffe,0xffffffff):
        for n in (0,1,2,255,256,257,0xffffffff):
            aa,bb,ok=compared(a,b,'pn_address',(p,s,n),s^n)
            fallback.append(dict(s=hex(s),n=n,equal=ok,result116=aa['result'],result117=bb['result']))
    aa,bb,ok=compared(a,b,'pn_address',(0,0,1),77)
    save('pn-results.json',dict(sites=results,boundaries=boundaries,no_mapper=fallback,outside_counterexample=dict(args=[0,0,1],old=aa,new=bb,reachable=False,reason='final callers have the nonnull static port or a validated port'),elapsed=time.time()-start))

def native(count):
    a,b=Runner(116),Runner(117);rng=random.Random(0xabcdef);p=DATA+0x1000;s=DATA+0x2000;n=DATA+0x3000;glyph=DATA+0x4000
    for r in (a,b):
        r.write(p,bytes(48));r.w32(p+40,BASE+r.e.functions['address']['address'])
        r.write(s,struct.pack('>6I',DATA+0x5000,DATA+0x6000,DATA+0x7000,32,72,132))
    failures=[];coverage={116:set(),117:set()};outdiff=0
    for i in range(count):
        state=bytearray(rng.getrandbits(8) for _ in range(32));state[0]=5
        desc=bytes(rng.getrandbits(8) for _ in range(72));details=bytes(rng.getrandbits(8) for _ in range(132));gg=struct.pack('>11I',*(DATA+0x10000+rng.randrange(1,0x1000) for j in range(11)))
        for r in (a,b):
            r.write(n,bytes(324));r.write(DATA+0x5000,state);r.write(DATA+0x6000,desc);r.write(DATA+0x7000,details);r.write(glyph,gg)
        aa,bb,ok=compared(a,b,'pn_native_from_seed',(s,p,n,glyph),i,(rng.randrange(11),))
        memory_equal=a.read(n,324)==b.read(n,324)
        # Link return addresses stored by nested calls differ after call relaxation; retain those separately.
        external=lambda x:[(ad,d) for ad,d,pc in x['writes'] if DATA<=ad<DATA+0x30000]
        ext=external(aa)==external(bb)
        good=aa['result']==bb['result'] and aa['abi_ok'] and bb['abi_ok'] and aa['saved']==bb['saved'] and ext and memory_equal and aa['stop']['reason']==bb['stop']['reason']=='return'
        for r,x in ((a,aa),(b,bb)):coverage[r.g].update(x['edges'])
        if not good and len(failures)<4:failures.append(dict(index=i,old=aa,new=bb,memory_equal=memory_equal))
        outdiff+=not ok
        if i%2000==0:print('pn_native_from_seed',i,flush=True)
    save('native-results.json',dict(random=count,failures=failures,raw_stack_differences=outdiff,edges={g:[(hex(pc),t) for pc,t in sorted(v)] for g,v in coverage.items()}))

def crc(count):
    a,b=Runner(116),Runner(117);rng=random.Random(0x123456)
    # Execute each actual CRC32 wrapper. The identical CRC_add callee is given its exact specified result.
    for r in (a,b):
        r.hook('gxr2_crc_add',lambda backend:zlib.crc32(backend.read(backend.core.r[1],backend.core.r[2]),backend.core.r[0]^0xffffffff)^0xffffffff)
    fails=[]
    for i in range(count):
        n=rng.choice([0,1,4,16,32,48,64,152,192,256,456,552,4096]);data=bytes(rng.getrandbits(8) for j in range(n))
        for r in (a,b):r.write(DATA,data)
        aa,bb,ok=compared(a,b,'gxr2_crc32',(DATA,n),i)
        if not (ok and aa['result']==zlib.crc32(data)) and len(fails)<4:fails.append(dict(index=i,old=aa,new=bb))
    save('crc-results.json',dict(random=count,failures=fails,boundary='CRC32 wrappers are real M32R; identical CRC_add is the zlib specification'))

if __name__=='__main__':
    which=sys.argv[1];count=int(sys.argv[2]) if len(sys.argv)>2 else 10000
    {'pn':pn,'native':native,'crc':crc}[which](count)
