"""Native case checkpoints and complete communication-boundary coverage.

A checkpoint is produced by the official constructors and keys. Forked case
processes inherit that entire machine, file model and unit RAM unchanged.
No individual menu, cursor, resident or engine field is assigned by a test.
The parent waits for each foreground case process before the next case.
"""
from pathlib import Path
import argparse,copy,hashlib,json,os,sys,traceback
sys.path.insert(0,str(Path(__file__).resolve().parent))
import run_native as n
from common import OUT,save,sha
from ui_trace_scope import touches_ui,scope_records
ux,m,fr,pe,v=n.ux,n.m,n.fr,n.pe,n.v

def stamp(h,p):
    digest=hashlib.sha256()
    for base,data,writable in h.b.regions:
        digest.update(base.to_bytes(4,'big'));digest.update(len(data).to_bytes(4,'big'));digest.update(data)
    return dict(ram_sha256=digest.hexdigest(),regions=len(h.b.regions),registers=list(h.b.core.r),
        pc=hex(h.b.pc),psw=h.b.core.psw,unit_ram_sha256=sha(json.dumps(p.rpc.overlay,sort_keys=True).encode()),
        origin='Complete process checkpoint after genuine native constructors and events.',
        native_ui_hand_seeded=False,getter_fixed_return_stub_removed=True)

def case(label,fn,context):
    sys.stdout.flush();sys.stderr.flush()
    pid=os.fork()
    if pid==0:
        r=dict(case=label,checkpoint=context)
        status=0
        try:
            fn(r);r['status']='PASS'
        except BaseException:
            r.update(status='FAIL',error=traceback.format_exc());status=1
        finally:
            save('native/cases/'+label+'.json',r)
            print(r['status'],label,flush=True)
        os._exit(status)
    _,state=os.waitpid(pid,0)
    assert os.WIFEXITED(state) and os.WEXITSTATUS(state)==0,('Native case failed',label,state)
    result=json.loads((OUT/'native/cases'/ (label+'.json')).read_text())
    assert result['status']=='PASS'
    return result

def no_cost(h,p):
    op=h.b.core.op;ins=ux.instrument(h,p);h.b.core.op=op
    for name in ('ig_event','ig_apply','ig_panel_open'):h.b.add_breakpoint(p.symbol_pc(name),ins['entry_callback'])
    return ins

def move_to(h,p,target):
    for _ in range(8):
        if h.u(0x2022f726,1)==target:return
        ux.need(fr.move_key(h,0x20))
    raise AssertionError(('native target not reached',target))

def other_list(h):
    h.b.map(0x206a0000,bytes(0x10000))
    b=v.PythonBackend();b.regions=h.b.regions;b.mmio=h.b.mmio;b.traces=h.b.traces
    b.breakpoints={k:list(c) for k,c in h.b.breakpoints.items()};b.core.r=list(h.b.core.r)
    b.core.psw=h.b.core.psw;b.core.cr=dict(h.b.core.cr);b.core.bpsw=h.b.core.bpsw
    b.core.bbpsw=h.b.core.bbpsw;b.core.acc=h.b.core.acc;b.set_reg('r15',0x206afff0)
    shadow=copy.copy(h);shadow.b=b
    shadow.run_slice(0x202ba380,0x202ba3c8);shadow.leave_other_list()
    return dict(activity=h.u(0x205d9bf8),overlay=h.u(0x2037f3bc),cursor=h.u(0x2022f726,1),dot=h.u(0x2022f725,1))

def persistent(h,p,at):
    actual=p.rpc.call;count=0
    def failed(cmd,value):
        nonlocal count
        count+=1
        if count<at:return actual(cmd,value)
        if count==at:
            actual(cmd,value);p.rpc.log[-1].update(device_result=p.rpc.log[-1]['result'],result=-1,simulated=True)
        else:p.rpc.log.append(dict(cmd=cmd,value=value,page=p.rpc.page,result=-1,t=p.rpc.t,simulated=True))
        return -1
    p.rpc.call=failed
    ux.need(fr.move_key(h,0x20))
    p.rpc.call=actual
    return count

def notice(h,p,w):
    texts=[];draws=[]
    def text(b):texts.append(b.read(b.core.r[0],b.core.r[1]).decode('ascii'));return False
    def draw(b):draws.append(hex(b.pc));return False
    h.b.add_breakpoint(p.symbol_pc('rv_native_ascii'),text)
    h.b.add_breakpoint(0x201d7170,draw)
    ux.need(fr.press(h,0x2b));h.parent()
    opened,_,error=fr.publish(h,p,w);ux.need(opened);assert error is None,error
    assert h.u(0x2022f5ac,1)==1 and texts and all(t.startswith('ERR ') and len(t)<=14 for t in texts)
    assert ux.snap(h,p)['native_snapshot_rows']==[1,1]
    assert draws
    return dict(text=texts,draws=draws,state=ux.snap(h,p))

def h07(unit):
    summary=[]
    states=['cold04','h08','compensated','fn2_live','fn2_open','busy_before_W','locked_after_W']
    if unit=='28mm':states.append('first_unready')
    n.configure(unit,'h07-all-states')
    template_h,template_p,template_w=m.boot(unit,ready=1,link=1)
    m.published(template_h,template_p,template_w)
    template=stamp(template_h,template_p)
    def state_cases(record,state):
        local_summary=[]
        if state=='first_unready':
            h,p,w=m.boot(unit,ready=0,link=1)
        else:
            h,p,w=template_h,template_p,template_w
        ins=no_cost(h,p)
        if state=='first_unready':ux.need(fr.open_settings(h));assert h.u(0x2022f5ac,1)==7
        if state in ('h08','compensated','fn2_live','fn2_open'):
            move_to(h,p,5);ux.matches(h,p,5)
        if state=='compensated':
            ux.need(fr.press(h,0x2b));m.reopen(h,p,w)
            original=p.rpc.call;fired=False;count=0
            def failed(cmd,value):
                nonlocal count,fired
                count+=1;result=original(cmd,value)
                if count==16:fired=True;p.rpc.log[-1].update(device_result=result,result=-1,simulated=True);return -1
                return result
            p.rpc.call=failed;ux.need(fr.move_key(h,0x20));p.rpc.call=original
            assert fired;ux.matches(h,p,5)
        if state in ('fn2_live','fn2_open'):
            ux.need(fr.native(h,0x202be220));assert h.u(0x2022f5ac,1)==11
            if state=='fn2_live':ux.need(fr.move_key(h,0x20));ux.matches(h,p,5,contrast=1)
        if state in ('busy_before_W','locked_after_W'):
            persistent(h,p,1 if state=='busy_before_W' else 16)
            if state=='locked_after_W':
                shown=notice(h,p,w)
                assert shown['state']['root']['state']==3
            else:
                m.reopen(h,p,w)
                assert h.u(p.symbol_pc('n')+3712,1)==0 and h.u(0x2022f5ac,1)==8
        context=stamp(h,p)
        for keep in (0,1):
            for key in (0x23,0x2b):
                label='h07-'+unit+'-'+state+'-k'+str(keep)+'-'+hex(key)
                def run(r,keep=keep,key=key):
                    ux.need(fr.native(h,0x20265818,(keep,)))
                    before=ux.snap(h,p);rpc=len(p.rpc.log);pr=h.stub_hits.get('preview',0)
                    event=len(ins['events']);result=ux.need(fr.press(h,key));after=ux.snap(h,p)
                    calls=p.rpc.log[rpc:]
                    r.update(unit=unit,state=state,keep=keep,key=hex(key),before=before,after=after,result=result,
                        events=ins['events'][event:],RPC=len(calls),W=sum(x['cmd']==22 for x in calls),
                        preview=h.stub_hits.get('preview',0)-pr,file_mutations=m.no_writes(p))
                    assert r['RPC']==r['W']==r['preview']==0,r
                    if state not in ('first_unready','busy_before_W','locked_after_W'):
                        assert after['list']['confirmed_valid'] and after['list']['confirmed_slot']==(4 if state=='cold04' else 5)
                        ux.matches(h,p,4 if state=='cold04' else 5,contrast=1 if state=='fn2_live' else 0)
                r=case(label,run,context)
                local_summary.append(dict(case=label,RPC=r['RPC'],W=r['W'],preview=r['preview']))
        record['cases']=local_summary
    for state in states:
        record=case('h07-state-'+unit+'-'+state,lambda row,state=state:state_cases(row,state),template)
        summary.extend(record['cases'])
    save('native/h07-all-'+unit+'.json',dict(status='PASS',cases=summary,dat_sha256=sha(m.DAT.read_bytes()),states=states))

def fn2_step(unit,all_points=True):
    n.configure(unit,'fn2-communication')
    h,p,w=m.boot(unit);m.published(h,p,w);move_to(h,p,5)
    ux.need(fr.native(h,0x202be220));ux.matches(h,p,5)
    ins=no_cost(h,p);context=stamp(h,p)
    def reference(r):
        rpc=len(p.rpc.log);preview=h.stub_hits.get('preview',0)
        ux.need(fr.move_key(h,0x20));actual=ux.matches(h,p,5,contrast=1)
        calls=p.rpc.log[rpc:]
        r.update(RPC=len(calls),W=sum(x['cmd']==22 for x in calls),write_bytes=2*sum(x['cmd']==22 for x in calls),
            preview=h.stub_hits.get('preview',0)-preview,actual=actual,rpc_log=calls,file_mutations=m.no_writes(p))
    reference_row=case('fn2-reference-'+unit,reference,context)
    total=reference_row['RPC'];summary=[]
    points=list(range(1,total+1)) if all_points else sorted({1,6,16,17,total})
    for point in points+['preview']:
        label='fn2-switch-'+unit+'-'+str(point)
        def run(r,point=point):
            original=p.rpc.call;count=0;switched=False;writes=[];opened=None
            rpc_at=len(p.rpc.log)
            def switch():
                nonlocal switched,opened
                opened=other_list(h);switched=True
                assert opened['activity']==7 and opened['overlay']==21
            def rpc(cmd,value):
                nonlocal count
                count+=1
                if count==point:switch()
                return original(cmd,value)
            def preview(b):
                if point=='preview' and not switched:switch()
                return False
            def watch(ev):
                if switched and touches_ui(ev):writes.append(dict(address=hex(ev.address),pc=hex(ev.pc),data=ev.data.hex()))
            h.b.add_write_trace(0,2**32,watch)
            h.b.breakpoints[0x202d6f38].insert(0,preview)
            p.rpc.call=rpc;result=ux.need(fr.move_key(h,0x20));p.rpc.call=original
            assert switched,('communication boundary not reached',point,count)
            complete=[]
            for contrast in (0,1):
                try:ux.matches(h,p,5,contrast=contrast)
                except AssertionError:continue
                complete.append(dict(slot=5,contrast=contrast))
            after=ux.snap(h,p)
            r.update(unit=unit,point=point,reference_rpc=total,seen=count,other_menu=opened,after=after,
                writes_after_switch=writes,complete=complete,result=result,scope=scope_records(),
                rpc_log=p.rpc.log[rpc_at:],file_mutations=m.no_writes(p))
            assert not writes and after['native_activity']==7 and after['native_overlay']==21,r
            assert len(complete)==1,r
        record=case(label,run,context)
        summary.append(dict(point=point,late_writes=len(record['writes_after_switch']),complete=record['complete']))
    save('native/fn2-all-points-'+unit+'.json',dict(status='PASS',dat_sha256=sha(m.DAT.read_bytes()),
        reference=reference_row,points=summary,complete_communication_points=all_points))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('group',choices=('h07','fn2'))
    parser.add_argument('unit',choices=('50mm','28mm','mount'));parser.add_argument('--selected',action='store_true')
    args=parser.parse_args()
    if args.group=='h07':h07(args.unit)
    else:fn2_step(args.unit,not args.selected)
