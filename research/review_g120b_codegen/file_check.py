"""Compare retained dispatcher directions with exact file-state offsets."""
from pathlib import Path
import collections
import itertools
import json
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
from review_scope import OUT,save,sha,record_inputs
from previous_runtime import services as s


def main():
    p=s.d.Pair()
    s.setup(p)
    rows,failures=[],[]
    seen={118:set(),119:set()}
    scenarios=[]
    for op in (1,2,4,6):
        scenarios.append((op,{}))
    for obj,module,key_slot,replica in itertools.product((1,2,3),range(4),(0,1,15),range(1,6)):
        scenarios.append((2,dict(object=obj,module=module,key_slot=key_slot,replica=replica)))
    for obj in (2,3):
        scenarios.append((2,dict(object=obj,root_flags=66)))
    for obj,slot in itertools.product((1,2,3),(0,1)):
        for op in (2,4,6):
            scenarios.append((op,dict(object=obj,file_slot=slot)))
        for amount,used,limit,end in itertools.product((-1,0,1,2,3),(0,15,16),(16,17),(0,1,2)):
            scenarios.append((4,dict(object=obj,file_slot=slot,file_result=amount,
                                     used=used,limit=limit,end=end)))
        for value in (-1,0,1):
            scenarios.append((6,dict(object=obj,file_slot=slot,close_result=value)))
    for op in (2,4,6):
        for native in ('open','close','read','sd'):
            for result in (-5,-1,0,1,3):
                scenarios.append((op,{native+'_result':result}))
        for field,values in {
            'root_flags':(0,1,2,4,16,64), 'io_epoch':(0,11,12,13),
            'file_epoch':(0,11,12,13), 'token':(0,0x99,0x98),
            'mode':(0,1), 'object':(1,2,3), 'sd_zero':(0,1),
            'sd_other':(0,1),'stored_sd_zero':(0,1),'no_files':(0,1),'token_end':(0,1),
            'session_none_at':tuple(range(1,6)),
        }.items():
            for value in values:
                scenarios.append((op,{field:value}))
    model={}
    def session(b,r):
        index=p.service_counts[r.g]['review_session']+1
        p.service_counts[r.g]['review_session']=index
        return 0 if index==model.get('session_none_at',0) else s.S
    s.replace(p,'es_session',session)
    for index,(op,case) in enumerate(scenarios):
        args=s.base(p,1,op,index)
        model.clear();model.update(case)
        p.mode['file_result']=case.get('file_result',1)
        p.mode['sd_result']=case.get('sd_result',0)
        p.mode['sd_bytes']=bytes(16) if case.get('sd_zero') else b'\x11'*16
        p.mode['returns']['rv_native_open']=[case.get('open_result',3)]
        p.mode['returns']['rv_native_close']=[case.get('close_result',0)]
        if 'read_result' in case:
            p.mode['file_result']=case['read_result']
        for r in p.rs:
            r.w32(s.R+212,case.get('root_flags',2))
            r.w32(s.R+52,12)
            r.w32(s.R+68,0xffffffff if case.get('token_end') else 100)
            r.w32(s.S+340,0xe7fff)
            r.write(s.S+440,bytes(16) if case.get('stored_sd_zero') else
                    (b'\x22' if case.get('sd_other') else b'\x11')*16)
            r.w32(s.S+280,0)
            r.w32(s.S+296,0)
            slot=case.get('file_slot',0)
            obj=case.get('object',1)
            if op in (4,6):
                f=s.S+280+16*slot
                r.w32(f,0 if case.get('no_files') else 0x99)
                r.w32(f+4,3)
                r.w32(f+8,case.get('file_epoch',12))
                r.w32(f+12,case.get('mode',0))
                r.w32(s.S+488+4*slot,case.get('used',0))
                r.w32(s.S+496+4*slot,case.get('limit',16))
                r.w32(s.S+504+4*slot,(obj<<24)|1)
                r.w32(s.S+512+4*slot,case.get('end',0))
                r.w32(s.Q+12,case.get('token',0x99))
                if op==4:
                    r.w32(s.Q+32,s.D+0x13000)
                    r.w32(s.Q+36,2)
            elif op==2:
                r.w32(s.Q+16,obj)
                r.w32(s.Q+20,case.get('module',1 if obj!=1 else 0))
                r.w32(s.Q+24,case.get('key_slot',0))
                r.w32(s.Q+28,case.get('replica',1 if obj==1 else 2))
            if op!=1:
                r.w32(s.Q+8,case.get('io_epoch',12))
        results=[]
        for r in p.rs:
            r.reset(0x120b2000+index)
            results.append(r.call('rv_call',args,steps=100000))
        old,new=results
        projections=[p.projection(r,x) for r,x in zip(p.rs,results)]
        ok=(old['stop']['reason']==new['stop']['reason']=='return' and
            old['result']==new['result'] and old['saved']==new['saved'] and
            old['abi_ok'] and new['abi_ok'] and projections[0]==projections[1])
        rows.append(dict(index=index,operation=op,case=case,ok=ok,
            results=[x['result'] for x in results],stops=[x['stop'] for x in results],
            edges={r.g:x['edges'] for r,x in zip(p.rs,results)}))
        for r,result in zip(p.rs,results):
            seen[r.g].update(map(tuple,result['edges']))
        if not ok:
            save('file-first-difference.json',dict(row=rows[-1],old=old,new=new,
                 old_projection=projections[0],new_projection=projections[1]))
            failures.append(index)
            break
        if index%500==0:
            print('file comparisons',index,'/',len(scenarios),flush=True)
    save('file-cases.json',rows)
    save('file-check.json',dict(status='PASS' if not failures else 'FAIL',cases=len(rows),
        requested=len(scenarios),failures=failures,edges={g:sorted(e) for g,e in seen.items()},
        artifacts={r.g:dict(dat_sha256=sha(r.original),elf_sha256=sha(r.e.raw)) for r in p.rs},
        offsets=dict(files=280,file_bytes=488,file_limit=496,file_object=504,file_end=512),
        capabilities='0x000e7fff',
        contracts='Final rv_call body; named file and session callees return specified values. Actual files, camera and card are not used.',
        comparison='Return, r8-r15/SP/LR and complete per-byte public write-value histories.'))
    record_inputs('file-inputs.json')
    assert not failures,failures
    print('PASS directed file comparisons',len(rows),flush=True)


if __name__=='__main__':
    main()
