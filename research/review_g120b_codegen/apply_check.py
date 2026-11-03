"""Directed old/new apply comparisons across mapping and recovery paths."""
from pathlib import Path
import collections
import hashlib
import json
import random
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from review_scope import SOURCE, OUT, load, save, sha, record_inputs
from current_runtime import differential as d


def main():
    a=load(SOURCE/'apply_pairs.py','review_apply_pairs')
    p=a.p
    maps=json.loads((OUT/'maps.json').read_text())['units']
    remote_counts=collections.Counter()
    remote_examples=[]
    current_index=[0]
    cross_sites=[]
    def monitored(b,r):
        sid,op,value=b.core.r[1:4]
        if sid==4 and op in (2,3,4):
            unit=maps[a.config['unit']]
            model=a.models[r.g]
            t=(unit['t_page']<<16)|unit['t_offset']
            if op==4:
                assert value in {unit['t_page']}|{row['address']>>16 for row in unit['rows']}
                remote_counts[(r.g,'X')]+=1
            else:
                address=t if model['page']==unit['t_page'] else (
                    (model['page']<<16)|(value&0xfffe) if op==2 else model['cursor'])
                row=next((row for row in unit['rows'] if row['word_begin']<=address
                          and address+2<=row['word_end']),None)
                assert address==t or row is not None,(r.g,op,hex(address))
                label='V' if op==2 else 'W'
                remote_counts[(r.g,label)]+=1
                if op==3 and row:
                    blob=value.to_bytes(2,'big')
                    for offset,byte in enumerate(blob):
                        at=address+offset
                        if not row['address']<=at<row['address']+row['length']:
                            assert byte==model['memory'][at],(hex(at),byte,model['memory'][at])
                            remote_counts[(r.g,'preserved_byte')]+=1
                            if r.g==120 and len(remote_examples)<12:
                                remote_examples.append(dict(case=current_index[0],address=hex(at),
                                    byte=byte,row=row['label'],word_address=hex(address)))
        return a.call(b,r)
    for r in p.rs:
        r.b.breakpoints.pop(d.BASE+r.e.functions['core_call']['address'],None)
        cross_pc=0x4fd0 if r.g==119 else 0x5190
        def cross(b,r=r,cross_pc=cross_pc):
            if a.config.get('fail_cross_page'):
                a.config['fail_rpc']=a.models[r.g]['rpc']+1
                cross_sites.append(dict(case=current_index[0],generation=r.g,pc=hex(cross_pc),
                                        rpc_index=a.config['fail_rpc']))
            return False
        r.b.add_breakpoint(d.BASE+cross_pc,cross)
    p.hook('core_call',monitored)
    rng=random.Random(0x120b120)
    rows, failures=[],[]
    seen={119:set(),120:set()}
    digest=hashlib.sha256()
    scenarios=[]
    for unit in range(3):
        for slot in range(1,9):
            for recovery in (0,1):
                scenarios.append(dict(unit=unit,slot=slot,recovery=recovery,fail_service=0,fail_rpc=0,level=0))
    for recovery in (0,1):
        for fail in list(range(1,45))+[64,96,128,192,256,384,512]:
            scenarios.append(dict(unit=0,slot=6,recovery=recovery,fail_service=0,fail_rpc=fail,level=0))
        for service in range(1,10):
            scenarios.append(dict(unit=1,slot=5,recovery=recovery,fail_service=service,fail_rpc=0,level=0))
    for unit in range(3):
        for slot in range(1,9):
            for level in (-1,1):
                scenarios.append(dict(unit=unit,slot=slot,recovery=0,fail_service=0,fail_rpc=0,level=level))
    for pending,uncertain in ((0,1),(1,0),(1,1)):
        scenarios.append(dict(unit=0,slot=6,recovery=1,fail_service=0,fail_rpc=0,level=0,
                              pending=pending,uncertain=uncertain))
    for target in (4,5,6):
        scenarios.append(dict(unit=0,slot=target,recovery=0,fail_service=0,fail_rpc=0,level=0,
                              live_slot=6,initial_t=0))
    scenarios.extend([
        dict(unit=0,slot=5,recovery=0,fail_service=0,fail_rpc=3,level=0,live_slot=6,initial_t=0),
        dict(unit=0,slot=6,recovery=0,fail_service=0,fail_rpc=3,level=0,live_slot=6,initial_t=0,saturation=1),
        dict(unit=0,slot=5,recovery=0,fail_service=0,fail_rpc=0,level=0,wrong_neighbor=True),
        dict(unit=0,slot=6,recovery=1,fail_service=0,fail_rpc=0,level=0,fail_cross_page=True),
        dict(unit=0,slot=4,recovery=1,fail_service=0,fail_rpc=0,level=0,initial_t=0,uncertain=1)])
    for index,case in enumerate(scenarios):
        current_index[0]=index
        unit,slot=case['unit'],case['slot']
        seed_index=unit+3*((slot-unit-1)*3%8)
        assert seed_index%3==unit and seed_index%8+1==slot
        args,_=a.prepare(rng,seed_index,True)
        assert a.config['unit']==unit and a.config['slot']==slot
        a.config.update(fail_service=case['fail_service'],fail_rpc=case['fail_rpc'],
                        fail_cross_page=case.get('fail_cross_page',False))
        directory=int.from_bytes(d.IMAGE[156:160],'big')+64*unit
        meta=int.from_bytes(d.IMAGE[directory+24:directory+28],'big')+28*(slot-1)
        tweak=[]
        for param in range(8):
            lo,hi=d.IMAGE[meta+3*param:meta+3*param+2]
            lo=lo if lo<128 else lo-256
            hi=hi if hi<128 else hi-256
            tweak.append(lo if case['level']<0 else hi if case['level']>0 else 0)
        if 'saturation' in case:
            params=json.loads((OUT/'calculation-contract.json').read_text())['parameters']
            tweak[params.index(2)]=case['saturation']
        for r in p.rs:
            g=p.g[r.g]
            live_slot=case.get('live_slot',4)
            r.write(g+2523,bytes([1,1,0,1,case.get('uncertain',0)]))
            r.write(g+2528,bytes([int(live_slot!=4),0,case.get('pending',0)]))
            r.write(g+2537,b'\0')
            r.write(a.TWEAK,bytes(v&255 for v in tweak))
            for row in maps[unit]['rows']:
                for at in range(row['word_begin'],row['word_end']):
                    a.models[r.g]['memory'].setdefault(at,(at+index*37)&255)
            if live_slot!=4:
                live=d.EXPAND[unit]['entries'][live_slot-1]
                r.write(g+1419,live)
                bank=int.from_bytes(d.IMAGE[directory+16:directory+20],'big')
                record=d.IMAGE[bank+32+64*(live_slot-1):bank+96+64*(live_slot-1)]
                identity=record[2:3]+record[4:36]+record[3:4]+record[36:51]
                r.write(g+184,bytes([unit,live_slot])+identity)
                for row in maps[unit]['rows']:
                    for offset,byte in enumerate(live[row['entry_offset']:row['entry_offset']+row['length']]):
                        a.models[r.g]['memory'][row['address']+offset]=byte
            a.models[r.g]['t']=case.get('initial_t',2)
            if case.get('wrong_neighbor'):
                at=maps[unit]['neighbor']
                a.models[r.g]['memory'][at]^=1
        args=(a.REF,a.TWEAK,case['recovery'],0)
        results=[]
        for r,name in zip(p.rs,('apply_impl','apply_impl.constprop.0')):
            r.reset(0x120b0000+index)
            results.append(r.call(name,args,steps=900000))
        old,new=results
        projections=[p.projection(r,x) for r,x in zip(p.rs,results)]
        ok=(old['stop']['reason']==new['stop']['reason']=='return' and
            old['result']==new['result'] and old['saved']==new['saved'] and
            old['abi_ok'] and new['abi_ok'] and projections[0]==projections[1] and
            a.models[119]==a.models[120])
        for r,x in zip(p.rs,results):
            seen[r.g].update(map(tuple,x['edges']))
        rows.append(dict(index=index,case=case,tweak=tweak,ok=ok,
            results=[x['result'] for x in results],stops=[x['stop'] for x in results],
            rpc=a.models[120]['rpc'],edges={r.g:x['edges'] for r,x in zip(p.rs,results)}))
        if not ok:
            save('apply-first-difference.json',dict(case=case,old=old,new=new,
                old_projection=projections[0],new_projection=projections[1],models=a.models))
            failures.append(index)
            break
        digest.update(json.dumps(projections[0],sort_keys=True).encode())
        if index%50==0:
            print('apply comparisons',index,'/',len(scenarios),flush=True)
    save('apply-cases.json',rows)
    save('apply-cross-sites.json',cross_sites)
    save('apply-check.json',dict(status='PASS' if not failures else 'FAIL',
        cases=len(rows),requested=len(scenarios),failures=failures,
        edges={g:sorted(s) for g,s in seen.items()},
        comparison='Return, r8-r15/SP/LR, complete per-byte public write-value histories and complete communication model state.',
        projection_sha256=digest.hexdigest(),
        artifacts={r.g:dict(dat_sha256=sha(r.original),elf_sha256=sha(r.e.raw)) for r in p.rs},
        contracts='fresh returns a valid epoch; final data expansion supplies entry552; core_call models documented settings and X/V/W replies. The apply body and its RPC helpers execute final M32R instructions.'))
    save('rpc-directed-check.json',dict(status='PASS_WORD_ENVELOPE_AND_PRESERVED_BYTES',
        counts={str(k):v for k,v in remote_counts.items()},examples=remote_examples,
        contract='Every requested X page and V/W halfword is derived from the frozen map word interval or T. Every requested W byte outside the exact row interval equals its current model byte.',
        limitation='A preserved adjacent byte is still part of a physical halfword access; this check does not redefine a row length of 33 as 34.'))
    record_inputs('apply-inputs.json')
    assert not failures,failures
    print('PASS directed apply comparisons',len(rows),flush=True)


if __name__=='__main__':
    main()
