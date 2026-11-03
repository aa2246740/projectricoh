"""Probe native arrows during the very first DAT publication, before/after eight rows."""
from pathlib import Path
import argparse
import os
import sys
import traceback
sys.path.insert(0,str(Path(__file__).resolve().parent))
from support import *
from safety_cases import shadow
from static_audit import symbols

def case(fixture,cut,action,record):
    ux,m,fr,pe,v,h,p,w=fixture
    fired=[False];armed=[False];setters=[];mode_writes=[]
    settings=h.u(0x200c0dac)
    spans=symbols(pe.ENGINE_ELF)
    def inject(b):
        if fired[0]:return False
        assert b.core.psw&0x40
        assert h.u(pe.ROOT_ADDR+6,1)==1
        fired[0]=True;before=ux.snap(h,p);S=h.b.read(settings,0xc9e);at=len(p.rpc.log);mark=w.mark()
        other=shadow(h,v)
        for pc in (0x202bb96c,0x202871dc,0x20268768,0x20268774,0x202688d4):
            other.b.add_breakpoint(pc,lambda bb,pc=pc:setters.append(hex(pc)) or False)
        other.b.add_write_trace(settings+0x36e,settings+0x36f,
            lambda e:mode_writes.append(dict(pc=hex(e.pc),origin=e.origin,data=e.data.hex())))
        event=ux.need(fr.move_key(other,0x20 if action=='right' else 0x1f,steps=30000000))
        after=h.b.read(settings,0xc9e)
        record['nested']=dict(pc=hex(b.pc),psw=b.core.psw,before=before,after=ux.snap(h,p),
            S_changes=[dict(offset=i,before=a,after=z) for i,(a,z) in enumerate(zip(S,after)) if a!=z],
            setters=setters,Image_mode_stores=mode_writes,event=event,resident_hooks=w.since(mark),extra_RPC=len(p.rpc.log)-at)
        return False
    def entering(b):
        if armed[0]:return False
        block=h.u(pe.ROOT_ADDR+56)
        if not block:return False
        p.image_base=h.u(block+312)
        if not p.image_base:return False
        armed[0]=True
        if cut=='before_publish':h.b.add_breakpoint(p.symbol_pc('list_bind'),inject)
        elif cut=='after_publish_restore':
            found=[(name,item) for name,item in spans.items() if name=='ui_list' or name.startswith('ui_list.')]
            # gen 121 inlines ui_list into the service dispatcher.
            name,span=found[0] if found else next((name,item) for name,item in spans.items() if name=='rv_call' or name.startswith('rv_call.'))
            ui=p.image_base+span['address'];end=ui+span['size'];once=[False]
            def restoring(bb):
                caller=bb.core.r[14]
                if not once[0] and ui<=caller<end and h.u(0x2022f5ac,1)==8:
                    once[0]=True;h.b.add_breakpoint(caller,inject)
                return False
            h.b.add_breakpoint(p.symbol_pc('rv_irq_restore'),restoring)
        return False
    h.b.add_breakpoint(h.symbols['rv_invoke'],entering)
    h.b.core.psw|=0x40
    record['published']=m.published(h,p,w)
    assert cut=='control' or fired[0],(cut,armed,fired)
    try:record['stock04']=ux.matches(h,p,4);matches=True
    except AssertionError as error:record['stock04']=dict(matches=False,error=str(error));matches=False
    record.update(cut=cut,action=action,fired=fired[0],final=ux.snap(h,p),final_matches04=matches,
        dat_sha256=sha(p.dat),unit=p.unit,rpc_log=p.rpc.log,native_UI=ui_audit(h),file_mutations=m.no_writes(p))
    if record['generation']==124:
        layout=json.loads((OUT/'local/layout/current-adapter-layout.json').read_text());adapter=p.symbol_pc('n')
        record['published_labels']=[h.b.read(adapter+layout['ui.text']+9*i,9).split(b'\0',1)[0].decode('ascii') for i in range(8)]
    bad=bool(mode_writes)
    if bad:
        at=len(p.rpc.log)
        record['confirm_exit']=ux.need(fr.press(h,0x23,steps=30000000))
        record['after_confirm_exit']=ux.snap(h,p)
        record['confirm_RPC']=len(p.rpc.log)-at
        try:record['after_exit_stock04']=ux.matches(h,p,4)
        except AssertionError as error:record['after_exit_stock04']=dict(matches=False,error=str(error))
    record['status']='COUNTEREXAMPLE' if bad else 'PASS'
    return bad

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--generation',type=int,choices=(121,124),default=124)
    parser.add_argument('--case',choices=('all','before_publish','after_publish_restore'),default='all')
    parser.add_argument('--tag',default='')
    args=parser.parse_args();ux,m,fr,pe,v=setup(args.generation,'50mm','cold-reentry')
    h,p,w=m.boot('50mm');fixture=ux,m,fr,pe,v,h,p,w;results=[]
    for cut,action in (('control','right'),('before_publish','right'),('before_publish','left'),('after_publish_restore','right')):
        if args.case!='all' and cut!=args.case:continue
        label=f'{args.generation}-50mm-{cut}-{action}';sys.stdout.flush();pid=os.fork()
        if pid==0:
            record=dict(case=label,generation=args.generation);code=0
            try:code=int(case(fixture,cut,action,record))
            except BaseException:record.update(status='HARNESS_ERROR',error=traceback.format_exc());code=2
            save('local/cold-reentry'+args.tag+'/'+label+'.json',record)
            print(label,record['status'],record.get('stock04'),record.get('error','')[-600:],flush=True);os._exit(code)
        _,status=os.waitpid(pid,0);results.append(dict(case=label,wait_status=status))
    save('evidence/cold-reentry-'+str(args.generation)+args.tag+'.json',dict(generation=args.generation,cases=results))
    assert all(x['wait_status']==0 for x in results),results
if __name__=='__main__':main()
