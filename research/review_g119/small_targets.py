"""Close omitted retained-body branches with direct final-M32R pairs."""
from pathlib import Path
import itertools
import json
import random
import struct
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import misc_diff as m
from service_targets import replace
from common import save, sha

d = m.d


def execute(p, names, args, case, rows, extra=()):
    result = []
    for r, name in zip(p.rs, names):
        r.reset(0x119f0000 + len(rows))
        result.append(r.call(name, args, extra, steps=200000))
    a, b = result
    pa, pb = [p.projection(r, x) for r, x in zip(p.rs, result)]
    ok = (a['stop']['reason'] == b['stop']['reason'] == 'return' and
          a['result'] == b['result'] and a['saved'] == b['saved'] and
          a['abi_ok'] and b['abi_ok'] and pa == pb)
    row = dict(case=case, ok=ok, results=[a['result'], b['result']],
               edges={r.g: x['edges'] for r, x in zip(p.rs, result)})
    rows.append(row)
    if not ok:
        save('small-target-failure.json', dict(function=names, row=row, old=a, new=b,
                                              old_projection=pa, new_projection=pb))
        raise AssertionError((names, case, a['result'], b['result'], a['stop'], b['stop']))


def finish(name, p, rows):
    save(name+'-review-targeted.json', dict(status='PASS', cases=rows,
        artifacts={r.g: dict(elf=sha(r.e.raw), dat=sha(r.original)) for r in p.rs}))
    print('PASS small targeted', name, len(rows), flush=True)


def ingress():
    p=d.Pair();m.setup(p,'ingress');rows=[]
    m.seed(p,random.Random(1),0,True);p.mode['range']=1
    for r in p.rs:
        r.w32(m.Q+48,m.S+40);r.w32(m.Q+52,120)
        r.write(r.n+2072,bytes(6));r.w32(r.n+4,0)
    execute(p,('ingress','ingress'),(0,0x77,m.Q,m.REPLY),'first valid context, n.context=NULL',rows)
    finish('ingress',p,rows)


def core():
    p=d.Pair();m.setup(p,'core_call');rows=[]
    def reply(b,r):
        b.write(b.core.r[3],struct.pack('>HHiiIIIII',p.mode['version'],p.mode['bytes'],0,0,0,1,0,0,0))
        return 0
    replace(p,'rv_call',reply)
    for i,(version,size) in enumerate(itertools.product((0,1,2),(0,31,32,33))):
        args,extra,case=m.prepare(p,'core_call',random.Random(i),i,True)
        p.mode.update(version=version,bytes=size)
        execute(p,('core_call','core_call'),args,dict(version=version,bytes=size),rows,extra)
    finish('core_call',p,rows)


def preview():
    p=d.Pair();m.setup(p,'preview_cached');rows=[]
    for i,(loaded,ready,opened,slot,apply,recover) in enumerate(itertools.product(
            (0,1),(0,1),(0,1),(0,1,4,8,9),(0,1,3),(0,3))):
        m.prepare(p,'preview_cached',random.Random(i),i,True)
        p.mode.update(apply=apply,recover=recover)
        for r in p.rs:
            r.write(d.IMAGE_ADDR,d.IMAGE)
            bank=d.IMAGE_ADDR+int.from_bytes(d.IMAGE[int.from_bytes(d.IMAGE[156:160],'big')+16:][:4],'big')
            r.w32(p.g[r.g]+48,bank);r.write(p.g[r.g]+64,b'\0\x08')
            r.write(r.n+1484,bytes([loaded]));r.write(p.g[r.g]+2523,bytes([ready,1]))
            r.write(p.g[r.g]+864,bytes([opened,0,8]))
        execute(p,('preview_cached','preview_cached'),(slot,),
                dict(loaded=loaded,ready=ready,opened=opened,slot=slot,apply=apply,recover=recover),rows)
    finish('preview_cached',p,rows)


def panel_open():
    p=d.Pair();m.setup(p,'ig_panel_open');rows=[]
    def current(b,r):
        if not p.mode['current']:
            b.write(b.core.r[0],b'\0\x04'+bytes(49))
            b.write(b.core.r[1],bytes([p.mode['tweak']&255])+bytes(7))
        return p.mode['current']
    def parameter(b,r):
        if b.core.r[3]==p.mode['fail_parameter']:
            return 1
        for i,value in enumerate((-5,5,0)):
            at=int.from_bytes(b.read(b.core.r[15]+4*i,4),'big')
            b.write(at,struct.pack('>i',value))
        return 0
    replace(p,'eng_current',current);replace(p,'gxr2_parameter',parameter)
    replace(p,'eng_visible_rows',lambda b,r:8)
    cases=list(itertools.product((0,3),(-6,-5,0,5,6),(0,1,4),(0,1,2,3),(0,1)))
    for i,(current_status,tweak,fail_parameter,count,null_array) in enumerate(cases):
        args,extra,_=m.prepare(p,'ig_panel_open',random.Random(i),i,True)
        p.mode.update(current=current_status,tweak=tweak,fail_parameter=fail_parameter,callee=0,ingress=1)
        for r in p.rs:
            r.write(r.n+2072,b'\1\1');r.write(r.n+550,bytes(2));r.write(r.n+1501,bytes(range(6)))
            r.write(r.n+2078,bytes([i%2]));r.write(0x2022f726,b'\4')
            r.w32(0x205a27d8,0 if null_array else 0x205a2b00)
            r.write(0x205a27d4,bytes([count]))
            for j in range(3):
                r.write(0x205a2b00+8*j,bytes([33,0,0,0])+struct.pack('>I',m.D+0x7000))
        execute(p,('ig_panel_open','ig_panel_open'),args,
                dict(current=current_status,tweak=tweak,fail_parameter=fail_parameter,count=count,null_array=null_array),rows,extra)
    # Guarded native row, preview rejection, and reentrant open-after-preview.
    for row,callee in itertools.product((0,4,9),(0,1)):
        args,extra,_=m.prepare(p,'ig_panel_open',random.Random(row+callee),0,True)
        p.mode.update(current=3,tweak=0,fail_parameter=0,callee=callee,ingress=1)
        for r in p.rs:
            r.write(r.n+2072,b'\1\1');r.write(r.n+550,bytes(2));r.write(0x2022f726,bytes([row]))
        execute(p,('ig_panel_open','ig_panel_open'),args,dict(row=row,callee=callee),rows,extra)
    finish('ig_panel_open',p,rows)


def event():
    p=d.Pair();d.setup_event(p);rows=[]
    for i,(status,committed) in enumerate(itertools.product(range(6),(0,1))):
        args,case=d.prepare_event(p,random.Random(i),i,True)
        p.mode.update(ingress=1,eng_apply=status,eng_visible_rows=8,eng_current=3)
        for r in p.rs:
            r.write(r.n+2072,b'\1\1');r.write(r.n+550,bytes(2));r.write(r.n+1484,b'\1')
            r.write(p.g[r.g]+2526,bytes([committed,0]));r.write(p.g[r.g]+864,b'\1')
            r.write(0x2022f726,b'\4');r.w32(d.DATA+40,7)
        execute(p,('ig_event','ig_event'),args,dict(status=status,committed=committed),rows)
    finish('ig_event',p,rows)


def menu():
    p=d.Pair();d.setup_menu(p);rows=[]
    for i,(committed,previewing,opened,loaded,confirmed) in enumerate(itertools.product((0,1),repeat=5)):
        args,case=d.prepare_menu(p,random.Random(i),i,True)
        p.mode.update(ingress=1,eng_visible_rows=8,fresh=1,list_bind=0,lease_status=0)
        for r in p.rs:
            r.write(r.n+2072,b'\1\1\1\0\0\0');r.w32(r.n+2100,0x118)
            r.write(r.n+1484,bytes([loaded]));r.write(p.g[r.g]+2523,bytes([1,1,0,committed,0,0,0]))
            r.write(p.g[r.g]+2535,bytes([confirmed,previewing]))
            r.write(p.g[r.g]+864,bytes([opened,0,8]))
            r.write(p.g[r.g]+184,b'\0\4'+bytes(49));r.write(p.g[r.g]+235,b'\0\4'+bytes(49))
        execute(p,('ig_menu','ig_menu'),args,dict(committed=committed,previewing=previewing,opened=opened,loaded=loaded,confirmed=confirmed),rows)
    finish('ig_menu',p,rows)


def apply():
    p=d.Pair();d.setup_apply(p);rows=[]
    p.hook('list_bind');p.hook('finish')
    def preview_call(b,r):
        target=b.core.r[0]
        if p.mode['fallback']:
            r.write(p.g[r.g]+862,b'\4')
        else:
            r.write(p.g[r.g]+862,bytes([target&255]))
        r.write(0x2022f726,bytes([p.mode['last_row']]))
        return p.mode['preview_status']
    p.hook('preview_cached',preview_call)
    for i,(slot,last_row,preview_status,fallback) in enumerate(itertools.product((0,1,4,8,9),(0,1,4,8,9),(0,1),(0,1))):
        args,case=d.prepare_apply(p,random.Random(i),i,True)
        p.mode.update(ingress=1,list_bind=0,finish=1,preview_status=preview_status,last_row=last_row,fallback=fallback)
        # Error plus a changed native row is the intentionally changed
        # coalescing/retry domain, not an equivalence claim.
        if preview_status and last_row != slot:
            continue
        for r in p.rs:
            r.write(p.g[r.g],bytes(r.e.symbols['g']['size']))
            r.write(r.n+2072,b'\1\1');r.write(r.n+550,b'\0')
            r.write(p.g[r.g]+2523,b'\1\1');r.write(p.g[r.g]+864,b'\1\0\x08')
            r.write(p.g[r.g]+64,b'\0\x08');r.w32(d.DATA+40,(slot-1)&0xffffffff)
            r.write(0x2022f726,bytes([slot]))
        execute(p,('ig_apply','ig_apply'),args,dict(slot=slot,last_row=last_row,preview_status=preview_status,fallback=fallback),rows)
    finish('ig_apply',p,rows)


if __name__=='__main__':
    for name in sys.argv[1:] or ['ingress','core','preview','panel_open','event','menu','apply']:
        globals()[name]()
