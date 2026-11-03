"""Verify live Fn2 exits, compensation, nested events and per-step wire cost."""
from pathlib import Path
import argparse,collections,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import native_cases as nc
from common import OUT,save,sha
n,ux,m,fr=nc.n,nc.ux,nc.m,nc.fr

def live_rows(h,p):
    offsets=json.loads((OUT/'local/layout/layout.json').read_text());g=p.symbol_pc('g')
    live=h.b.read(g+offsets['live'],552);unit=m.INDEX[p.unit]
    directory=m.u32(p.dat,156)+64*unit;mapping=p.dat[m.u32(p.dat,directory+12):][:152]
    proofs=[]
    for i in range(9):
        row=mapping[32+12*i:44+12*i];address,size,off=m.u32(row,0),m.u16(row,4),m.u16(row,6)
        actual=bytes((p.rpc.half(at&~1)>>(0 if at&1 else 8))&255 for at in range(address,address+size))
        expected=live[off:off+size];assert actual==expected,(p.unit,i)
        proofs.append(sha(actual))
    assert p.rpc.t==m.u16(live,445)
    return dict(nine_rows_sha256=proofs,T=p.rpc.t,live_entry_sha256=sha(live))

def retained(unit):
    n.configure(unit,'fn2-retained')
    h,p,w=m.boot(unit);m.published(h,p,w);nc.move_to(h,p,5)
    ux.need(fr.press(h,0x2b));m.reopen(h,p,w);ux.need(fr.native(h,0x202be220));ux.need(fr.move_key(h,0x20))
    ux.matches(h,p,5,contrast=1);context=nc.stamp(h,p);rows=[]
    for label,key in (('ok',0x23),('adj',0x2b),('half',0x29)):
        def run(r,key=key):
            rpc=len(p.rpc.log);pr=h.stub_hits.get('preview',0);before=ux.snap(h,p)
            if key==0x29:
                first=ux.need(fr.native(h,0x2029fdc4,(key,0),steps=8000000))
                second=ux.need(fr.native(h,0x202bd724,(key,0),steps=8000000));result=[first,second]
            else:result=ux.need(fr.press(h,key))
            after=ux.snap(h,p);actual=ux.matches(h,p,5,contrast=1)
            assert len(p.rpc.log)==rpc and h.stub_hits.get('preview',0)==pr
            m.reopen(h,p,w);assert h.u(0x2022f726,1)==5
            ux.need(fr.native(h,0x202be220));assert h.u(0x2022f726,1)==7
            r.update(before=before,after=after,result=result,actual=actual,RPC=0,W=0,preview=0,reopened=ux.snap(h,p),file_mutations=m.no_writes(p))
        rows.append(nc.case('fn2-retain-'+unit+'-'+label,run,context))
    save('native/fn2-retain-'+unit+'.json',dict(status='PASS',dat=sha(m.DAT.read_bytes()),unit=unit,cases=rows,
        behavior_change='Approved 2026-10-27 21:45: half shutter keeps the currently displayed live value.'))

def failures(unit):
    n.configure(unit,'fn2-failures')
    h,p,w=m.boot(unit);m.published(h,p,w);nc.move_to(h,p,3)
    ux.need(fr.native(h,0x202be220));ux.need(fr.move_key(h,0x20));ux.need(fr.press(h,0x2b))
    ux.matches(h,p,3,contrast=1);m.reopen(h,p,w);nc.move_to(h,p,5);ux.need(fr.native(h,0x202be220))
    context=nc.stamp(h,p);rows=[]
    for label,at,extra,persistent in (('before_W_once',1,(),False),('after_W_once',16,(),False),('fallback04',16,(22,),False),('before_W_continued',1,(),True),('after_W_continued',16,(),True)):
        def run(r,at=at,extra=extra,persistent=persistent,label=label):
            original=p.rpc.call;count=0;events=[]
            def call(cmd,value):
                nonlocal count
                count+=1
                failed=count==at or count in extra or persistent and count>at
                if failed:
                    if count==at or count in extra:
                        result=original(cmd,value);p.rpc.log[-1].update(device_result=result,result=-1,simulated=True)
                    else:p.rpc.log.append(dict(cmd=cmd,value=value,page=p.rpc.page,result=-1,t=p.rpc.t,simulated=True))
                    events.append(dict(index=count,cmd=cmd));return -1
                return original(cmd,value)
            before=ux.snap(h,p);p.rpc.call=call;result=ux.need(fr.move_key(h,0x20));p.rpc.call=original
            after=ux.snap(h,p);complete=[]
            for slot,contrast in ((3,1),(4,0),(5,0),(5,1)):
                try:actual=ux.matches(h,p,slot,contrast=contrast)
                except AssertionError:continue
                complete.append(dict(slot=slot,contrast=contrast,actual=actual))
            locked=bool(h.u(p.symbol_pc('n')+3712,1));shown=None
            if persistent and at>1:
                assert locked and after['list']['uncertain']==1
                saved_rpc=len(p.rpc.log);saved_preview=h.stub_hits.get('preview',0)
                shown=nc.notice(h,p,w)
                assert len(p.rpc.log)==saved_rpc and h.stub_hits.get('preview',0)==saved_preview
            else:
                assert not locked and len(complete)==1
                expected=5 if at==1 else 3
                assert complete[0]['slot']==expected
                assert complete[0]['contrast']==(0 if at==1 else 1)
                live_rows(h,p)
                m.reopen(h,p,w)
                assert h.u(0x2022f5ac,1)==8
            r.update(unit=unit,label=label,before=before,after=after,result=result,events=events,complete=complete,locked=locked,notice=shown,
                file_mutations=m.no_writes(p))
        rows.append(nc.case('fn2-failure-'+unit+'-'+label,run,context))
    save('native/fn2-failures-'+unit+'.json',dict(status='PASS',unit=unit,dat=sha(m.DAT.read_bytes()),cases=rows))

def measure(unit):
    n.configure(unit,'fn2-step-counts')
    h,p,w=m.boot(unit);m.published(h,p,w);nc.move_to(h,p,5)
    labels=[]
    def text_record(b):
        labels.append(b.read(b.core.r[4],b.core.r[5]).decode('ascii'))
        return False
    h.b.add_breakpoint(0x201d73e0,text_record)
    ux.need(fr.native(h,0x202be220))
    layout=json.loads((OUT/'local/layout/current-adapter-layout.json').read_text());base=p.symbol_pc('n');rows=[]
    for parameter in range(4):
        assert h.u(base+layout['panel.parameter'],1)==parameter
        assert len(labels)>=11 and set(t[:4] for t in labels[-11:])=={('Cont','Satu','HiLt','Shad')[parameter]},labels[-11:]
        for key in [0x20]*5+[0x1f]*10+[0x20]*5:
            before=len(p.rpc.log);preview=h.stub_hits.get('preview',0)
            old_value=h.u(base+layout['panel.draft']+parameter,1);old_value=old_value-256 if old_value&128 else old_value
            result=ux.need(fr.move_key(h,key));calls=p.rpc.log[before:]
            value=h.u(base+layout['panel.draft']+parameter,1);value=value-256 if value&128 else value
            assert value==old_value+(1 if key==0x20 else -1)
            assert h.b.read(base+layout['panel.draft'],8)==h.b.read(p.symbol_pc('g')+286,8)
            actual=live_rows(h,p)
            if parameter==0:ux.matches(h,p,5,contrast=value)
            count=len(calls);writes=sum(c['cmd']==22 for c in calls)
            rows.append(dict(parameter=parameter+1,label=('Cont','Satu','HiLt','Shad')[parameter],key=hex(key),before=old_value,after=value,RPC=count,W=writes,write_bytes=2*writes,
                preview=h.stub_hits.get('preview',0)-preview,tick_ms=1,estimated_rpc_wait_ms=[count,3*count],result=result,actual=actual))
        assert value==0
        ux.need(fr.native(h,0x202be220))
        print('MEASURED native Fn2',unit,'parameter',parameter+1,'20 steps',flush=True)
    save('native/fn2-step-counts-'+unit+'.json',dict(status='PASS',unit=unit,dat=sha(m.DAT.read_bytes()),steps=rows,native_ascii_labels=labels,
        assumptions='One tick is 1 ms and each RPC occupies 1-3 ms; the estimate covers communication waiting only. CPU, drawing and real device latency are not measured.',
        file_mutations=m.no_writes(p)))
    print('PASS Fn2 per-step wire counts',unit,len(rows),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('group',choices=('retain','failures','measure'));parser.add_argument('unit',choices=('50mm','28mm','mount'));args=parser.parse_args()
    {'retain':retained,'failures':failures,'measure':measure}[args.group](args.unit)
