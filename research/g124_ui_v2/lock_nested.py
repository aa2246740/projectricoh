"""Send a native key while permanent ERR publication is still inflight."""
from pathlib import Path
import argparse
import json
import os
import sys
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parent))
from support import *
from run_cases import prepare
from safety_cases import shadow


def run(fixture, panel, cut, action, record):
    ux, m, fr, pe, v, h, p, w, prepared = fixture
    record.update(prepared)
    if panel:
        ux.need(fr.native(h, 0x202be220))
        ux.need(fr.native(h, 0x202be220))
        ux.need(fr.native(h, 0x202be220))
    layout = json.loads((OUT/'local/layout/current-adapter-layout.json').read_text())
    n, root = p.symbol_pc('n'), pe.ROOT_ADDR
    fired, injected = [False], [False]
    original = p.rpc.call
    settings = h.u(0x200c0dac)
    writes = []

    def watch(e):
        if injected[0]:
            writes.append(dict(pc=hex(e.pc), address=hex(e.address), offset=e.address-settings,
                               origin=e.origin, data=e.data.hex()))
    h.b.add_write_trace(settings, settings+0xc9e, watch)

    def inject(b):
        expected_rows = 8
        if injected[0] or not h.u(n+layout['failed'],1) or h.u(0x2022f5ac,1) != expected_rows:
            return False
        injected[0] = True
        before = ux.snap(h,p)
        s = h.b.read(settings,0xc9e)
        rpc = len(p.rpc.log)
        other = shadow(h,v)
        mark = w.mark()
        old = other.b.visits[0x202bb96c]
        if action in ('right','left'):
            result = fr.move_key(other,0x20 if action=='right' else 0x1f,steps=30000000)
        elif action == 'disp':
            result = fr.native(other,0x202be220,steps=30000000)
        else:
            result = fr.press(other,0x23 if action=='confirm' else 0x2b,steps=30000000)
        result = ux.need(result)
        after = h.b.read(settings,0xc9e)
        record['nested'] = dict(pc=hex(b.pc),psw=b.core.psw,before=before,after=ux.snap(h,p),
            result=result,S_changes=[dict(offset=i,before=a,after=z) for i,(a,z) in
                                    enumerate(zip(s,after)) if a!=z],
            extra_RPC=len(p.rpc.log)-rpc,native_H08_visits=other.b.visits[0x202bb96c]-old,
            resident_hooks=w.since(mark),writes=list(writes))
        return False

    if cut == 'record_failure_return':
        core = json.loads((OUT/'local/layout/layout.json').read_text())
        g = p.symbol_pc('g')
        armed = [False]
        def failed_return(b):
            if not armed[0] and h.u(g+core['uncertain'],1) and h.u(g+core['write_started'],1):
                armed[0] = True
                h.b.add_breakpoint(b.core.r[14],inject)
            return False
        h.b.add_breakpoint(p.symbol_pc('record_failure'),failed_return)
    elif cut == 'after_update_restore':
        ui = p.symbol_pc('ui_list')
        armed = [False]
        def restored(b):
            if armed[0] or not h.u(n+layout['failed'],1):
                return False
            caller = b.core.r[14]
            if ui <= caller < ui+1100 and h.u(b.core.r[15]+40)==2:
                armed[0] = True
                h.b.add_breakpoint(caller,inject)
            return False
        h.b.add_breakpoint(p.symbol_pc('rv_irq_restore'),restored)
    elif cut == 'before_redraw':
        h.b.add_breakpoint(p.symbol_pc('rv_native_draw'),inject)
    else:
        h.b.add_breakpoint(0x201ffb2c,inject)

    def fault(cmd,value):
        if not fired[0] and cmd==22:
            result=original(cmd,value)
            p.rpc.log[-1].update(device_result=result,result=-1,simulated=True)
            fired[0]=True
            return -1
        if fired[0]:
            p.rpc.log.append(dict(cmd=cmd,value=value,page=p.rpc.page,result=-1,t=p.rpc.t,simulated=True))
            return -1
        return original(cmd,value)
    p.rpc.call=fault
    h.b.core.psw |= 0x40
    record['outer_event']=ux.need(fr.move_key(h,0x20,steps=30000000))
    p.rpc.call=original
    record.update(unit=p.unit,panel=panel,cut=cut,action=action,injected=injected[0],
        after=ux.snap(h,p),S_writes_after_injection=writes,rpc_log=p.rpc.log,
        dat_sha256=sha(p.dat),native_UI=ui_audit(h),file_mutations=m.no_writes(p))
    assert injected[0], 'The nested event must hit its inflight cut'
    assert record['nested']['psw'] & 0x40
    assert not record['native_UI']['host_ui_writes']
    assert not record['nested']['native_H08_visits'], 'Native H08 continued on the ERR row'
    assert not record['nested']['S_changes'], record['nested']['S_changes']
    record['status']='PASS_NESTED_KEY_IGNORED'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--generation',type=int,choices=(121,124),default=124)
    parser.add_argument('--unit',choices=('50mm','28mm','mount'),default='50mm')
    parser.add_argument('--cuts',nargs='+',choices=('record_failure_return','after_update_restore','before_redraw','row_draw'),default=('before_redraw',))
    parser.add_argument('--actions',nargs='+',choices=('right','left','disp','confirm','adj'),default=('right','left','disp','confirm','adj'))
    args=parser.parse_args()
    fixture=prepare(argparse.Namespace(generation=args.generation,unit=args.unit,case='lock-nested'))
    results=[]
    for panel in (False,True):
        for cut in args.cuts:
            for action in args.actions:
                if cut=='after_update_restore':
                    results.append(dict(case=f'{args.unit}-{panel}-{cut}-{action}',wait_status=0,status='REMOVED_UPDATE_PATH',reason='The gen 124 adapter never calls list_bind(2); all physical lists remain eight rows.'))
                    continue
                name=(f'{args.generation}-' if args.generation != 124 else '')+f'{args.unit}-{"panel" if panel else "list"}-{cut}-{action}'
                sys.stdout.flush();pid=os.fork()
                if pid==0:
                    record=dict(case=name,unit=args.unit);code=0
                    try:run(fixture,panel,cut,action,record)
                    except BaseException:record.update(status='FAIL',error=traceback.format_exc());code=1
                    save('local/nested/'+name+'.json',record)
                    print(name,record['status'],record.get('error','')[-600:],flush=True)
                    os._exit(code)
                _,status=os.waitpid(pid,0);results.append(dict(case=name,wait_status=status))
    suffix = '-'.join(args.cuts)
    save('evidence/lock-nested-'+str(args.generation)+'-'+args.unit+'-'+suffix+'.json',dict(status='PASS' if all(x['wait_status']==0 for x in results) else 'FAIL',dat_sha256=file_sha(DAT),unit=args.unit,cases=results))
    assert all(x['wait_status']==0 for x in results),results


if __name__=='__main__':main()
