"""Non-blocking randomized support for A, with explicit common call boundaries.

This is not used as the translation proof. Unsupported caller setups are
retained as harness limitations, never promoted to product counterexamples.
"""
from pathlib import Path
import collections,json,random,struct,sys,time
OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(OUT))
import differential as d
ex=d.ex


def main():
    records=json.loads((OUT/'function-closure.json').read_text())
    results=[];start=time.time()
    for row in records:
        if row['category']!='A':continue
        name=row['function'];p=d.Pair();rng=random.Random(0xa117+sum(map(ord,name)))
        # Keep byte/word primitives real. Replace every other callee by the same
        # pure return boundary, so differences must come from the target body.
        keep={'ig_copy','ig_equal','ig_zero','memcpy','es_memcpy','es_equal','p32','get32','b32','last_u32','gxr2_crc_add'}
        primitive_bytes={s['bytes'] for r in p.rs for n,s in r.e.functions.items()
                         if n in keep or n.startswith(('be32.','put32.','zero.'))}
        for r in p.rs:
            target=r.e.functions[p.name(r,name)]['address'];hooked=set()
            for nn,ss in r.e.functions.items():
                if ss['address']==target or ss['bytes'] in primitive_bytes:continue
                if ss['address'] in hooked:continue
                hooked.add(ss['address']);r.hook(nn,lambda b:0)
            for native in json.loads((d.R1/'untyped-assembly-functions.json').read_text()):
                pc=native['old_address' if r.g==116 else 'new_address']+ex.BASE
                def native_zero(b):
                    b.core.r[0]=0;b.set_reg('pc',b.core.r[14]&~3);return False
                r.b.add_breakpoint(pc,native_zero)
        failures=[];seen={116:set(),117:set()};calls=0
        for i in range(1000):
            blob=bytes(rng.getrandbits(8) for _ in range(128));scalar=rng.randrange(0x10000)
            args=(ex.DATA+0x400,ex.DATA+0x800,ex.DATA+0x1000,0);extra=(0,ex.DATA+0x1400,16,0,ex.DATA+0x1800)
            for r in p.rs:
                r.write(r.n,bytes(3712));r.write(p.g[r.g],bytes(2476));r.write(ex.DATA,bytes(0x3000))
                r.write(d.IMAGE_ADDR,d.IMAGE);r.write(ex.DATA+0x400,blob);r.write(ex.DATA+0x800,blob)
                view=bytearray(84);struct.pack_into('>5I',view,0,d.IMAGE_ADDR,len(d.IMAGE),117,256,9652)
                for j in range(7):view[20+8*j:28+8*j]=d.IMAGE[132+12*j:140+12*j]
                struct.pack_into('>HH',view,76,8,28);view[80:83]=bytes([i%3,1,1]);r.write(ex.DATA+0x800,view)
                r.w32(r.n+4,d.CTX);r.w32(d.CTX+8,d.ROOT_ADDR);r.w32(d.CTX+16,d.SESSION)
                r.w32(ex.BASE+r.e.symbols['ctx']['address'],d.CTX)
                r.write(d.ROOT_ADDR,bytes(216));r.write(d.SESSION,bytes(1024))
                direct=int.from_bytes(d.IMAGE[156:160],'big')+64*(i%3)
                r.w32(p.g[r.g]+44,d.IMAGE_ADDR+int.from_bytes(d.IMAGE[direct+12:direct+16],'big'))
                r.w32(p.g[r.g]+48,d.IMAGE_ADDR+int.from_bytes(d.IMAGE[direct+16:direct+20],'big'))
                r.write(r.n+2072,bytes([i%2]));r.write(r.n+550,b'\1\1')
                r.write(p.g[r.g]+2467,bytes([0,i%2]));r.write(p.g[r.g]+2465,bytes([(i//2)%2]))
                # A valid callback slot is needed even with a pure call boundary.
                r.w32(r.n,ex.DATA+0x1200);r.w32(ex.DATA+0x1200+16,ex.BASE+r.e.functions['rv_call']['address'])
                r.w32(ex.DATA+0x400,ex.DATA+0x1200)
                r.w32(p.g[r.g],ex.BASE+r.e.functions['core_call']['address'])
            if name in ('a4_move','eng_entry.constprop.0','select_cached','pn_ui_render.constprop.0','write_word','t_store'):
                args=(scalar if name in ('write_word','t_store') else rng.randrange(18),)
            elif name in ('descriptor.lto_priv.0','descriptor.lto_priv.1','descriptor.lto_priv.2','descriptor.lto_priv.3','descriptor.lto_priv.4',
                          'metadata.lto_priv.0','metadata.lto_priv.1','metadata.lto_priv.2','slot_descriptor'):
                args=(ex.DATA+0x800,rng.randrange(3),rng.randrange(1,9))
            elif name=='eng_identity':args=(ex.DATA+0x400,ex.DATA+0x1000)
            elif name in ('gxr2_expand.constprop.0','gxr2_semantic_validate','gxr2_parameter'):
                args=(0,rng.randrange(4),rng.randrange(18),rng.randrange(8));extra=(ex.DATA+0x1400,ex.DATA+0x1500,ex.DATA+0x1600)
            elif name=='gxr2_raw_row':args=(ex.DATA+0x1000,ex.DATA+0x800,ex.DATA+0x400,rng.randrange(10))
            elif name=='gxr2_crc_zeroed.constprop.0':args=(ex.DATA+0x400,rng.randrange(4,65),0)
            elif name=='mapped':args=(rng.choice([0,1,2,0xffffffff,0xfffffffd,0xfffffff5]),)
            elif name=='pn_request':args=(ex.DATA+0x400,ex.DATA+0x1000,scalar)
            elif name=='pn_call':args=(ex.DATA+0x400,rng.randrange(13),rng.randrange(8),ex.DATA+0x1000);extra=(ex.DATA+0x1800,)
            elif name=='core_call':args=(0,rng.randrange(13),rng.randrange(8),scalar);extra=(0,ex.DATA+0x1000,rng.randrange(81),0,ex.DATA+0x1800)
            elif name.startswith('ig_') and name not in ('ig_bx_apply','ig_bx_event','ig_bx_receipt','ig_bx_unit'):
                args=(0,scalar,0,ex.DATA+0x1000)
            elif name in ('read_exact',):args=(scalar,ex.DATA+0x1000,rng.randrange(1,65))
            elif name=='rv_call':args=(rng.randrange(17),rng.randrange(16),ex.DATA+0x1000,ex.DATA+0x1800)
            rows=[]
            for r in p.rs:
                r.reset(0x117a0000+i);x=r.call(p.name(r,name),args,extra,steps=15000);rows.append(x);seen[r.g].update(map(tuple,x['edges']))
            a,b=rows
            ok=a['stop']['reason']==b['stop']['reason']=='return' and p.pointer(p.a,a['result'])==p.pointer(p.b,b['result']) and a['saved']==b['saved'] and a['abi_ok'] and b['abi_ok'] and p.projection_bytes(p.a,a)==p.projection_bytes(p.b,b)
            if not ok:
                failures.append(dict(index=i,args=args,extra=extra,stops=[x['stop'] for x in rows],results=[x['result'] for x in rows],abi=[x['abi_ok'] for x in rows]))
                (OUT/('support-'+name+'-limitation.json')).write_text(json.dumps(dict(case=failures[0],old=a,new=b),indent=2)+'\n')
                break
            calls+=1
        result=dict(function=name,completed=calls,requested=1000,pass_=calls==1000,limitations=failures,
                    boundary='all other non-primitive callees return 0; null and rejected ingress paths are included; this is supporting evidence only',
                    branch_coverage=d.coverage(p,name,seen))
        results.append(result)
        (OUT/'support-results.json').write_text(json.dumps(results,indent=2)+'\n')
        print(name,calls,'PASS' if calls==1000 else 'HARNESS_LIMITATION',flush=True)
    print('summary',sum(x['pass_'] for x in results),'/',len(results),'elapsed',round(time.time()-start,1),flush=True)


if __name__=='__main__':main()
