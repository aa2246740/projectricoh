"""Measure all CPU stores after a real native view switch at the draw bridge."""
from pathlib import Path
import argparse
import os
import sys
import traceback
sys.path.insert(0,str(Path(__file__).resolve().parent))
from support import *
from safety_cases import shadow
from ui_trace_scope import touches_ui

def case(fixture, generation, panel, switch_kind, record):
    ux,m,fr,pe,v,h,p,w=fixture
    if panel:
        for _ in range(3 if generation==126 else 1):
            ux.need(fr.native(h,0x202be220,steps=30000000))
    switched=[False];stores=[];setters=[];paint=[]
    settings=h.u(0x200c0dac);old_S=h.b.read(settings,0xc9e)
    old_UI=h.b.read(0x2022f71c,32)
    def switch(b):
        if switched[0]:return False
        assert b.core.psw&0x40
        other=shadow(h,v)
        before=ux.snap(h,p)
        if switch_kind=='activity':
            other.run_slice(0x202ba380,0x202ba3c8)
            other.leave_other_list()
        else:
            ux.need(fr.native(other,0x202b0a74,(55,)))
        record['switch']=dict(pc=hex(b.pc),psw=b.core.psw,before=before,after=ux.snap(h,p),
            S_sha_after_switch=sha(h.b.read(settings,0xc9e)),
            native_UI_after_switch=h.b.read(0x2022f71c,32).hex())
        switched[0]=True
        return False
    def store(e):
        if switched[0] and e.origin=='cpu':
            stores.append(dict(pc=hex(e.pc),address=hex(e.address),size=len(e.data),data=e.data.hex(),
                watched_UI=touches_ui(e),in_S=e.address<settings+0xc9e and e.address+len(e.data)>settings))
    h.b.add_write_trace(0,2**32,store)
    h.b.add_breakpoint(p.symbol_pc('rv_native_draw'),switch)
    h.b.add_breakpoint(0x201ffb2c,lambda b:paint.append(dict(after_switch=switched[0],state=hex(b.core.r[13]))) or False)
    for pc in (0x202871dc,0x20268768,0x20268774,0x202688d4):
        h.b.add_breakpoint(pc,lambda b,pc=pc:setters.append(dict(pc=hex(pc),after_switch=switched[0])) or False)
    h.b.core.psw|=0x40
    record['event']=ux.need(fr.move_key(h,0x20,steps=30000000))
    record.update(generation=generation,panel=panel,switch_kind=switch_kind,unit=p.unit,
        dat_sha256=sha(p.dat),switched=switched[0],after=ux.snap(h,p),
        native_state=h.u(0x205d9c00),all_CPU_stores_after_switch=stores,
        late_watched_UI=[r for r in stores if r['watched_UI']],late_S=[r for r in stores if r['in_S']],
        setters=setters,painted=paint,final_S_sha=sha(h.b.read(settings,0xc9e)),
        native_UI_final=h.b.read(0x2022f71c,32).hex(),file_mutations=m.no_writes(p),
        native_UI=ui_audit(h),rpc_log=p.rpc.log)
    assert switched[0] and any(x['after_switch'] for x in paint)
    assert not [x for x in setters if x['after_switch']]
    record['status']='OBSERVED_REMAINING_WINDOW'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--generation',type=int,choices=(121,126),default=126)
    parser.add_argument('--unit',choices=('50mm','28mm','mount'),default='50mm')
    args=parser.parse_args()
    ux,m,fr,pe,v=setup(args.generation,args.unit,'window-consequences')
    h,p,w=m.boot(args.unit);m.published(h,p,w);ux.need(fr.move_key(h,0x20,steps=30000000))
    fixture=ux,m,fr,pe,v,h,p,w
    results=[]
    for panel in (False,True):
        for kind in ('activity','state'):
            name=f'{args.generation}-{args.unit}-'+('panel' if panel else 'list')+'-'+kind
            sys.stdout.flush();pid=os.fork()
            if pid==0:
                record=dict(case=name);code=0
                try:case(fixture,args.generation,panel,kind,record)
                except BaseException:record.update(status='FAIL',error=traceback.format_exc());code=1
                save('local/window-consequences/'+name+'.json',record)
                print(name,record['status'],'late UI',len(record.get('late_watched_UI',[])),
                    'late S',len(record.get('late_S',[])),record.get('error','')[-600:],flush=True)
                os._exit(code)
            _,status=os.waitpid(pid,0);results.append(dict(case=name,wait_status=status))
    save(f'evidence/window-consequences-{args.generation}-{args.unit}.json',dict(generation=args.generation,unit=args.unit,cases=results))
    assert not any(x['wait_status'] for x in results)

if __name__=='__main__':main()
