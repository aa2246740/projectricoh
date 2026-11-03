"""Compare gen 121/123 unchecked H01 fallback with native list keys."""
from pathlib import Path
import argparse
import json
import os
import sys
import traceback

sys.path.insert(0,str(Path(__file__).resolve().parent))
from support import *
from run_cases import prepare


def run(fixture, condition, action, record):
    ux,m,fr,pe,v,h,p,w,prepared=fixture
    record.update(prepared)
    ux.need(fr.press(h,0x2b))
    p.rpc.overlay.clear();p.rpc.t=2
    original=p.rpc.call;calls=[0]
    def fail(cmd,value):
        calls[0]+=1
        if condition=='busy' or calls[0]==7:
            p.rpc.log.append(dict(cmd=cmd,value=value,page=p.rpc.page,result=-1,t=p.rpc.t,simulated=True))
            return -1
        return original(cmd,value)
    if condition=='ready':
        p.ready=0
        ux.need(fr.native(h,0x200935b4,(0,)))
    else:
        p.rpc.call=fail
    at=len(p.rpc.log)
    h.parent();opened,_,error=fr.publish(h,p,w);ux.need(opened);assert error is None,error
    pending=ux.snap(h,p)
    assert pending['rows']==7 and not pending['root']['ui_restore0'],pending
    end_h01=len(p.rpc.log)
    assert not any(x['cmd']==22 for x in p.rpc.log[at:end_h01])
    entries=[]
    for name in ('ig_event','ig_apply','ig_panel_open'):
        h.b.add_breakpoint(p.symbol_pc(name),lambda b,name=name:entries.append(name) or False)
    if action=='direction':result=fr.move_key(h,0x20,steps=30000000)
    else:result=fr.press(h,0x23 if action=='confirm' else 0x2b,steps=30000000)
    ux.need(result)
    after=ux.snap(h,p)
    assert after['rows']!=8 and not after['root']['ui_restore0']
    assert not entries and len(p.rpc.log)==end_h01
    p.rpc.call=original
    base=h.u(0x200c0dac)
    record.update(condition=condition,action=action,pending=pending,after=after,
        H01_RPC=end_h01-at,H01_W=sum(x['cmd']==22 for x in p.rpc.log[at:end_h01]),
        event_RPC=len(p.rpc.log)-end_h01,event_W=0,DAT_entries=entries,
        S_sha256=sha(h.b.read(base,0xc9e)),rpc_log=p.rpc.log,dat_sha256=sha(p.dat),
        file_mutations=m.no_writes(p),native_UI=ui_audit(h),status='PASS_NATIVE_FALLBACK_NO_NEW_W')
    assert not record['native_UI']['host_ui_writes'] and not record['native_UI']['getter_callback_present']


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--generation',type=int,choices=(121,123),default=123)
    args=parser.parse_args();fixture=prepare(argparse.Namespace(generation=args.generation,unit='50mm',case='h01-compare'))
    results=[]
    for condition in ('busy','read_cut','ready'):
        for action in ('direction','confirm','adj'):
            name=f'{args.generation}-50mm-{condition}-{action}'
            sys.stdout.flush();pid=os.fork()
            if pid==0:
                record=dict(unit='50mm',generation=args.generation,case=name);code=0
                try:run(fixture,condition,action,record)
                except BaseException:record.update(status='FAIL',error=traceback.format_exc());code=1
                save('local/h01-compare/'+name+'.json',record)
                print(name,record['status'],record.get('error','')[-500:],flush=True);os._exit(code)
            _,status=os.waitpid(pid,0);results.append(dict(case=name,wait_status=status))
    save('evidence/h01-'+str(args.generation)+'.json',dict(status='PASS' if all(x['wait_status']==0 for x in results) else 'FAIL',cases=results))
    assert all(x['wait_status']==0 for x in results),results


if __name__=='__main__':main()
