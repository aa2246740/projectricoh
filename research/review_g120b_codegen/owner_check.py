"""Compare the remaining lease-search direction with two owned blocks."""
from pathlib import Path
import json
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
from review_scope import OUT,save,sha,record_inputs
from previous_runtime import services as s


def main():
    p=s.d.Pair();s.setup(p)
    def free(b,r):
        b.write(b.core.r[0]-8,b'\0')
        return 0
    s.replace(p,'rv_native_free',free)
    rows=[];seen={118:set(),119:set()}
    for index,selected in enumerate((1,2,3,4,5)):
        args=s.base(p,2,2,index)
        for r in p.rs:
            r.w32(s.R+136,0)
            r.w32(s.R+148,123)
            r.w32(s.Q+12,0x80+selected)
            r.write(s.UI-8,b'\1')
            for lease in range(1,6):
                at=s.S+160+20*lease
                r.w32(at,0x80+lease)
                r.w32(at+4,~(0x80+lease))
                r.w32(at+8,s.UI if lease==selected else s.D+0x10000+0x1000*lease)
                r.w32(at+12,1460)
                r.w32(at+16,2)
                r.w32(s.S+620+4*lease,123)
        results=[]
        for r in p.rs:
            r.reset(0x120b4000+index)
            results.append(r.call('rv_call',args,steps=50000))
        old,new=results
        projections=[p.projection(r,x) for r,x in zip(p.rs,results)]
        ok=(old['stop']['reason']==new['stop']['reason']=='return' and old['result']==new['result']
            and old['saved']==new['saved'] and old['abi_ok'] and new['abi_ok'] and projections[0]==projections[1])
        row=dict(index=index,selected_lease=selected,ok=ok,results=[x['result'] for x in results],
            stops=[x['stop'] for x in results],edges={r.g:x['edges'] for r,x in zip(p.rs,results)})
        rows.append(row)
        assert ok,row
        for r,x in zip(p.rs,results):seen[r.g].update(map(tuple,x['edges']))
    assert (0x9f60,True) in seen[118] and (0xa4f4,True) in seen[119]
    save('owner-cases.json',rows)
    save('owner-check.json',dict(status='PASS',cases=len(rows),edges={g:sorted(e) for g,e in seen.items()},
        artifacts={r.g:dict(dat_sha256=sha(r.original),elf_sha256=sha(r.e.raw)) for r in p.rs},
        contract='Allocated-block and session helpers use the retained common contracts. The native free boundary clears only the specified block header in the model.',
        comparison='Final dispatcher return, r8-r15/SP/LR and complete public per-byte write-value histories.'))
    record_inputs('owner-inputs.json')
    print('PASS lease-search comparisons',len(rows))


if __name__=='__main__':
    main()
