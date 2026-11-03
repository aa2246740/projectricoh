"""Directed error boundaries omitted by the random common-callee distributions."""
from pathlib import Path
import collections
import itertools
import random
import struct
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from common import OUT, save
import differential as d

def remove(p,name):
    for r in p.rs:
        if name in r.e.functions:r.b.breakpoints.pop(d.BASE+r.e.functions[name]['address'],None)

def run_bind():
    p=d.Pair();d.setup_bind(p);remove(p,'pn_call');count={118:0,119:0};model={}
    def call(b,r):
        count[r.g]+=1
        return 0xffffffff if count[r.g]==model.get('fail_at',0) else 0
    p.hook('pn_call',call)
    cases=[];seen={118:set(),119:set()};rng=random.Random(0x119b1d)
    configurations=[dict(log=log,log_seed=seed,kind=kind,table=table,length=length,fail_at=fail)
        for log,seed,kind,table,length,fail in itertools.product((0,1),(0,1),(2,5),(0x2022f56c,0x2022f570,0x20704800),(7,32),(0,1,2,16,17))]
    for i,config in enumerate(configurations):
        _,base=d.prepare_bind(p,rng,i,True);model.update(config)
        for r in p.rs:
            count[r.g]=0;r.w32(r.n+4,d.CTX);r.w32(d.CTX+72,236)
            r.write(0x2022f71c,bytes([config['kind']]));r.w32(0x2022f720,config['table'])
            log=d.DATA+0x27000;r.write(log,bytes(4096));r.write(log+2496,bytes([config['log_seed']]))
            r.w32(d.BASE+r.e.symbols['log_bytes']['address'],log if config['log'] else 0)
            r.w32(d.BASE+r.e.symbols['ctx']['address'],d.CTX)
            off=302
            for row in range(8):r.write(p.g[r.g]+off+35*row+2,b'A'*config['length']+bytes(33-config['length']))
            r.write(p.g[r.g]+off+560,bytes([4,0,1,0,8]))
        results,ok,a,b=p.run(('list_bind','list_bind'),(1,),0x119b100+i)
        for r,x in zip(p.rs,results):seen[r.g].update(map(tuple,x['edges']))
        expected=[4] if results[1]['result']==0 else []
        ok=ok and p.c_calls[119]==expected
        row=dict(index=i,configuration=config,ok=ok,results=[x['result'] for x in results]);cases.append(row)
        if not ok:
            save('list_bind-targeted-failure.json',dict(case=row,old=results[0],new=results[1],old_projection=a,new_projection=b));raise AssertionError(row)
    save('list_bind-targeted.json',dict(status='PASS',cases=cases,edges={g:sorted(x) for g,x in seen.items()},
        scope='Full RAM blackbox seed; native kinds 2/5; table rejection; 32-character labels; late glyph/list service errors'))
    print('PASS list_bind directed',len(cases),'cases',flush=True)

def run_render():
    p=d.Pair();d.setup_render(p);model={};counts={118:0,119:0};addresses={118:0,119:0}
    remove(p,'pn_call');remove(p,'pn_native_from_seed')
    def call(b,r):
        counts[r.g]+=1;at=counts[r.g];sid,op,q=b.core.r[1:4]
        reply=int.from_bytes(b.read(b.core.r[15],4),'big');buf=int.from_bytes(b.read(q+48,4),'big')
        status=0xffffffff if at==model.get('fail_at',0) else 0
        native=-1 if at==model.get('negative_at',0) else 0
        out=bytearray(32);struct.pack_into('>HHII',out,0,1,32,status,native&0xffffffff)
        struct.pack_into('>I',out,16,model.get('reply_token',0x77));b.write(reply,out)
        if sid==11 and op==1:b.write(buf+36,(8).to_bytes(4,'big'))
        if sid==12 and op==1:b.write(buf+8,model.get('buffer_token',0).to_bytes(4,'big'))
        if at==model.get('stop_at',0):b.write(r.n+562,b'\1')
        return status
    def build(b,r):
        b.write(b.core.r[2],bytes(324))
        if model.get('stop_after_build'):b.write(r.n+562,b'\1')
        return 0
    def address(b,r):
        addresses[r.g]+=1
        return 0 if addresses[r.g]==model.get('bad_address_at',0) else b.core.r[1]
    p.hook('pn_call',call);p.hook('pn_native_from_seed',build);p.hook('address',address)
    configurations=[dict(initial=initial,**kind) for initial in (0,1) for kind in
        ([{}]+[dict(fail_at=n) for n in range(1,17)]+[dict(stop_at=n) for n in range(1,17)]+
         [dict(negative_at=2),dict(stop_after_build=1)]+
         [dict(reply_token=a,buffer_token=b) for a,b in itertools.product((0,0x77,0x88),(0,0x77,0x88))]+
         [dict(bad_address_at=n) for n in (1,2,3,34,35,36)])]
    cases=[];seen={118:set(),119:set()};rng=random.Random(0x119beef)
    for i,config in enumerate(configurations):
        _,base=d.prepare_render(p,rng,0,True);model.clear();model.update(config)
        for r in p.rs:counts[r.g]=addresses[r.g]=0
        results,ok,a,b=p.run(('panel_render.constprop.0','panel_render.constprop.0'),(config['initial'],),0x119bb00+i)
        for r,x in zip(p.rs,results):seen[r.g].update(map(tuple,x['edges']))
        ok=ok and p.c_calls[119]==([base['cursor']+1] if results[1]['result']==0 else [])
        row=dict(index=i,configuration=config,ok=ok,results=[x['result'] for x in results]);cases.append(row)
        if not ok:
            save('panel_render-targeted-failure.json',dict(case=row,old=results[0],new=results[1],old_projection=a,new_projection=b));raise AssertionError(row)
    save('panel_render-targeted.json',dict(status='PASS',cases=cases,edges={g:sorted(x) for g,x in seen.items()},
        scope='Errors at every actual UI call, glyph negative results, stop timing, view token conflicts, and null callback address results'))
    print('PASS panel_render directed',len(cases),'cases',flush=True)

def run_event():
    p=d.Pair();d.setup_event(p);rng=random.Random(0x119e);cases=[];seen={118:set(),119:set()}
    for i,(slot,rows,committed,status,keep) in enumerate(itertools.product((1,4,8,16),(1,8,16),(0,1),range(6),(0,1))):
        args,base=d.prepare_event(p,rng,i,True)
        p.mode.update(ingress=1,eng_apply=status,eng_current=3,eng_visible_rows=8)
        for r in p.rs:
            at=d.cg.g_offset if r.g==119 else lambda x:x
            r.write(r.n+2072,b'\1\1');r.write(r.n+1484,b'\1');r.write(r.n+550,bytes(2))
            r.write(p.g[r.g]+at(864),b'\1');r.write(p.g[r.g]+at(866),bytes([rows]))
            r.write(p.g[r.g]+at(2526),bytes([committed]));r.write(p.g[r.g]+185,b'\4')
            r.write(0x2022f726,bytes([slot]));r.w32(d.DATA+40,7);r.w32(d.DATA+44,keep)
        results,ok,a,b=p.run(('ig_event','ig_event'),args,0x119e000+i)
        for r,x in zip(p.rs,results):seen[r.g].update(map(tuple,x['edges']))
        row=dict(index=i,slot=slot,list_rows=rows,committed=committed,apply_status=status,keep=keep,ok=ok,results=[x['result'] for x in results]);cases.append(row)
        if not ok:
            save('ig_event-targeted-failure.json',dict(case=row,old=results[0],new=results[1],old_projection=a,new_projection=b));raise AssertionError(row)
    save('ig_event-targeted.json',dict(status='PASS',cases=cases,edges={g:sorted(x) for g,x in seen.items()},
        scope='Retained ordinary-list fallback, successful/error eng_apply, cursor restoration, keep=0/1 and range rejections; direct function fixture'))
    print('PASS ig_event directed',len(cases),'cases',flush=True)

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='event':run_event()
    elif len(sys.argv)>1 and sys.argv[1]=='bind':run_bind()
    else:run_bind();run_render()
