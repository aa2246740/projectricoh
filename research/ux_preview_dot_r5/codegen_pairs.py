"""Compare final M32R bodies with explicit source-change projections.

Direct function fixtures are compiler evidence. Native acceptance uses the
separate constructors, keys and complete communication-boundary suite.
"""
from pathlib import Path
import collections,json,random,struct,sys,time
sys.path.insert(0,str(Path(__file__).resolve().parent))
import differential as d
from common import OUT,save,sha,load
m=load(OUT/'misc_diff.py','quality_current_misc')

NAMES={
 'core_call':('core_call','core_call'),'finish':('finish','finish'),
 'ui_finish':('ui_finish','ui_finish'),'ig_apply':('ig_apply','ig_apply'),
 'ig_event':('ig_event','ig_event'),'ig_init':('ig_init','ig_init'),
 'ig_panel_open':('ig_panel_open','ig_panel_open'),
 'ig_panel_event':('ig_panel_event','ig_panel_event'),
 'ig_panel_abort':('ig_panel_abort','ig_panel_abort'),
 'view_owned':('view_owned','view_owned'),'release_view':('release_view','release_view'),
 'a4_move':('a4_move','a4_move'),'eng_current':('eng_current','eng_current.constprop.0'),
 'preview_cached':('preview_cached','preview_cached'),
}

def setup(name):
    p=d.Pair();p.ignored={g:{p.g[g]+2537} for g in (119,120)};p.contexts={119:[],120:[]}
    if name=='ig_init':
        d.setup_init(p)
        for r in p.rs:p.ignored[r.g].update(range(p.g[r.g]+184,p.g[r.g]+235))
    elif name=='ig_apply':d.setup_apply(p)
    elif name=='ig_event':
        d.setup_event(p);p.hook('view_owned',lambda b,r:1)
    elif name in ('ig_panel_open','ig_panel_event','ig_panel_abort'):
        m.setup(p,'ig_panel_open');p.hook('view_owned',lambda b,r:1)
    elif name in ('core_call','finish','ui_finish'):
        m.setup(p,name)
    elif name=='a4_move':
        m.setup(p,'ig_panel_event');p.hook('panel_render.constprop.0',lambda b,r:p.mode['render'])
    elif name=='view_owned':
        p.hook('rv_view_owned',lambda b,r:p.mode['owned'])
    elif name=='eng_current':p.hook('fresh',lambda b,r:p.mode['fresh'])
    elif name=='preview_cached':
        m.setup(p,'ig_panel_event')
        for r in p.rs:
            for n in ('preview_cached','recover_confirmed','eng_current.constprop.0'):
                if n in r.e.functions:r.b.breakpoints.pop(d.BASE+r.e.functions[n]['address'],None)
        for r in p.rs:
            actual='apply_impl' if r.g==119 else 'apply_impl.constprop.0'
            def apply(b,r=r):
                index=len(p.contexts[r.g]);seq=p.mode['apply_sequence']
                p.contexts[r.g].append(dict(recovery=b.core.r[2],recipe=list(b.read(b.core.r[0],51)),tweak=list(b.read(b.core.r[1],8))))
                return seq[min(index,len(seq)-1)]
            r.hook(actual,apply)
    elif name=='release_view':
        for r in p.rs:p.ignored[r.g].update((r.n+550,r.n+551))
    else:raise ValueError(name)
    for r,fn in zip(p.rs,NAMES[name]):r.b.breakpoints.pop(d.BASE+r.e.functions[fn]['address'],None)
    return p

def prepare(p,name,rng,i,boundary):
    extra=();args_by=None
    if name=='ig_init':args,case=d.prepare_init(p,rng,i,boundary)
    elif name=='ig_apply':args,case=d.prepare_apply(p,rng,i,boundary)
    elif name=='ig_event':
        args,case=d.prepare_event(p,rng,i,boundary)
        for r in p.rs:r.w32(d.DATA+40,0)
        case['event']=0
    elif name in ('core_call','finish','ui_finish','ig_panel_open','ig_panel_event','ig_panel_abort'):
        args,extra,case=m.prepare(p,'ig_panel_open' if name=='ig_panel_abort' else name,rng,i,boundary)
        if name=='finish':
            value=(0,1,3,5)[i%4] if boundary else rng.choice((0,1,3,5));args=(m.REPLY,value)
            case['result']=value;case['C_domain']='I/O lock branch is covered as an intentional change by native failure cases.'
        if name=='ui_finish':
            value=i%3 if boundary else rng.randrange(3);args=(m.REPLY,value);case['result']=value
        if name=='ig_panel_event':
            for r in p.rs:r.write(r.n+3712,b'\0')
    else:
        for r in p.rs:
            r.write(r.n,bytes(r.e.symbols['n']['size']));r.write(p.g[r.g],bytes(r.e.symbols['g']['size']))
            r.write(m.Q,bytes(64));r.write(m.REPLY,bytes(32))
        if name=='a4_move':
            opened=int(i%3!=0);row=rng.choice((0,1,2,8,9,10,11,255,0xffffffff));parameter=rng.randrange(4)
            values=bytes(rng.randrange(11)-5&255 for _ in range(8));render=rng.choice((0,0xffffffff))
            p.mode['render']=p.mode['callee']=render
            for r in p.rs:
                r.write(r.n+549,bytes([parameter,opened,1]));r.write(r.n+519,bytes(range(6)))
                r.write(r.n+511,values);r.write(r.n+1507,bytes([254]*4+[2]*4))
            args=(row,);case=dict(opened=opened,row=row,parameter=parameter,render=render,domain='Retained rejection and out-of-range render branches; live transaction region is C.')
        elif name=='view_owned':
            panel=rng.randrange(2);owned=rng.randrange(2);p.mode['owned']=owned
            for r in p.rs:r.w32(r.n+4,d.CTX);r.w32(d.CTX+8,d.ROOT_ADDR);r.write(r.n+550,bytes([panel]))
            args=();case=dict(panel=panel,owned=owned,watch=0)
        elif name=='release_view':
            for r in p.rs:
                r.write(r.n+2073,b'\1');r.write(r.n+2082,bytes([rng.randrange(2),rng.randrange(4)]))
                r.write(p.g[r.g]+864,b'\1');r.write(p.g[r.g]+2533,bytes([i%7]))
            p.b.write(p.b.n+2082,p.a.read(p.a.n+2082,2))
            args=(m.REPLY,);case=dict(stage=i%7,C_projection='Only the two new panel-close stores are projected; all other RAM histories are compared.')
        elif name=='eng_current':
            uncertain=rng.randrange(2);committed=rng.randrange(2);fresh=rng.randrange(2);p.mode['fresh']=fresh
            recipe=bytes([rng.randrange(3),rng.randrange(1,9)])+rng.randbytes(49);tweak=rng.randbytes(8)
            for r in p.rs:
                r.write(p.g[r.g]+184,recipe);r.write(p.g[r.g]+286,tweak)
                r.write(p.g[r.g]+2526,bytes([committed,uncertain]));r.write(m.BUF,bytes(8))
            args_by=[(p.a.n+452,m.BUF),(m.BUF,)]
            args=();case=dict(uncertain=uncertain,committed=committed,fresh=fresh,specialization='New recipe output is fixed to n.panel.recipe; only tweak remains an argument.')
        else:
            m.seed(p,rng,i,boundary)
            loaded=rng.randrange(2);opened=rng.randrange(2);slot=rng.choice((0,1,4,5,8,9,255));confirmed=rng.randrange(2)
            seq=rng.choice(((0,),(1,0),(2,0),(3,0),(4,0),(5,0),(1,1,0),(1,1,3)))
            lost=rng.randrange(2);uncertain=rng.randrange(2);bound=rng.randrange(2)
            p.mode['apply_sequence']=seq
            for r in p.rs:
                r.b.breakpoints.pop(d.BASE+r.e.functions['eng_visible_rows']['address'],None)
                r.write(d.IMAGE_ADDR,d.IMAGE)
                directory=int.from_bytes(d.IMAGE[156:160],'big');bank=d.IMAGE_ADDR+int.from_bytes(d.IMAGE[directory+16:directory+20],'big')
                meta=d.IMAGE_ADDR+int.from_bytes(d.IMAGE[directory+24:directory+28],'big');pool=d.IMAGE_ADDR+int.from_bytes(d.IMAGE[directory+20:directory+24],'big')
                r.w32(p.g[r.g]+48,bank);r.w32(p.g[r.g]+52,pool);r.w32(p.g[r.g]+56,meta)
                r.write(p.g[r.g]+64,b'\0\x08');r.write(r.n+1484,bytes([loaded]))
                r.write(p.g[r.g]+864,bytes([opened,0,8]));r.write(p.g[r.g]+2523,bytes([1,bound,0,1,uncertain]))
                r.write(p.g[r.g]+2535,bytes([confirmed,0,lost]))
                r.write(p.g[r.g]+235,b'\0\x04'+bytes(49));r.write(p.g[r.g]+294,bytes(8));p.contexts[r.g].clear()
            args=(slot,);case=dict(slot=slot,loaded=loaded,opened=opened,confirmed=confirmed,lost=lost,uncertain=uncertain,bound=bound,sequence=seq)
    return args,extra,case,args_by

def project(p,r,result):
    filtered=dict(result,writes=[])
    ignored=p.ignored[r.g]
    for address,data,pc in result['writes']:
        blob=bytes.fromhex(data)
        for j,value in enumerate(blob):
            if address+j not in ignored:filtered['writes'].append((address+j,bytes([value]).hex(),pc))
    return p.projection(r,filtered)

def run(name,count=10000):
    p=setup(name);rng=random.Random(0x120f5);seen={119:set(),120:set()};rows=[];started=time.monotonic();projection_hash=hashlib.sha256()
    failures=[];c_cases=0
    for i in range(count+64):
        args,extra,config,args_by=prepare(p,name,rng,i,i>=count)
        results=[]
        for j,(r,fn) in enumerate(zip(p.rs,NAMES[name])):
            r.reset(0x120f5000+i);results.append(r.call(fn,args_by[j] if args_by else args,extra,steps=250000))
        pa,pb=[project(p,r,x) for r,x in zip(p.rs,results)]
        a,b=results;expected_b=a['result']
        if name=='preview_cached' and len(p.contexts[120])==3 and p.mode['apply_sequence'][-1]==0:
            expected_b=4;c_cases+=1
        ok=(a['stop']['reason']==b['stop']['reason']=='return' and b['result']==expected_b and a['saved']==b['saved'] and a['abi_ok'] and b['abi_ok'] and pa==pb)
        for r,x in zip(p.rs,results):seen[r.g].update(map(tuple,x['edges']))
        config=json.loads(json.dumps(config,default=lambda value:dict(bytes_hex=value.hex())))
        row=dict(index=i,kind='boundary' if i>=count else 'random',configuration=config,ok=ok,results=[a['result'],b['result']])
        rows.append(row)
        if not ok:
            save('pairs/'+name+'-failure.json',dict(row=row,old=a,new=b,old_projection=pa,new_projection=pb,contexts=p.contexts));failures.append(row);break
        projection_hash.update(json.dumps(pa,sort_keys=True).encode())
        if i%2000==0:print('B',name,i,'/',count,flush=True)
    coverage={}
    for r,fn in zip(p.rs,NAMES[name]):
        pcs={x['pc'] for x in d.cg.atoms(r.g,fn)[0] if x['asm'].split(' ')[0] in d.ex.COND}
        observed={(pc,b) for pc,b in seen[r.g] if pc in pcs}
        coverage[r.g]=dict(observed=len(observed),possible=2*len(pcs),uncovered=[dict(pc=hex(pc),taken=b) for pc in sorted(pcs) for b in (False,True) if (pc,b) not in observed])
    target=OUT/'pairs';target.mkdir(exist_ok=True)
    (target/(name+'-cases.jsonl')).write_text(''.join(json.dumps(row)+'\n' for row in rows))
    save('pairs/'+name+'-results.json',dict(status='PASS' if not failures else 'FAIL',function=name,names=NAMES[name],random=min(count,len(rows)),boundary=max(0,len(rows)-count),
        failures=failures,coverage=coverage,edges={g:sorted(s) for g,s in seen.items()},
        artifacts={r.g:dict(elf=sha(r.e.raw),dat=sha(r.original)) for r in p.rs},
        comparison='Return, preserved r8-r15/SP/LR, and per-byte public write-value histories with declared object mapping.',
        C_projected_addresses={g:sorted(a) for g,a in p.ignored.items()},fallback_lock_return_cases=c_cases,projection_sha256=projection_hash.hexdigest(),seconds=time.monotonic()-started))
    assert not failures,('Compiler comparison failed',name,failures[0]['index'])
    print('PASS B',name,count,'+64',flush=True)

if __name__=='__main__':
    import hashlib
    run(sys.argv[1],int(sys.argv[2]) if len(sys.argv)>2 else 10000)
