"""Exercise H07 with committed=0 and recheck=0 after a matching first publication."""
from pathlib import Path
import argparse
import os
import sys
import traceback
sys.path.insert(0,str(Path(__file__).resolve().parent))
from support import *
from cold_reentry import full_plan

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--unit',choices=('50mm','28mm','mount'),default='50mm')
    args=parser.parse_args()
    ux,m,fr,pe,v=setup(126,args.unit,'cold-exit')
    h,p,w=m.boot(args.unit)
    settings=h.u(0x200c0dac)
    h.phase='model:settings_input'
    h.put(settings+0x6dd,9,1);h.put(settings+0x6de,9,1)
    h.phase='cpu'
    m.published(h,p,w)
    core=json.loads((OUT/'local/layout/layout.json').read_text())
    base=p.symbol_pc('g')
    assert h.u(base+core['committed'],1)==h.u(base+core['recheck'],1)==0
    assert full_plan(h,p)['matches']
    results=[]
    for action,key in (('OK',0x23),('ADJ',0x2b)):
        sys.stdout.flush();pid=os.fork()
        if pid==0:
            record=dict(unit=args.unit,action=action,dat_sha256=sha(p.dat));code=0
            try:
                record['before']=ux.snap(h,p)
                h.phase='model:settings_input';h.put(settings+0x36e,5,1);h.phase='cpu'
                record['simulated_input']=full_plan(h,p)
                entries=[];previews=[]
                h.b.add_breakpoint(p.symbol_pc('eng_check_settings'),lambda b:entries.append(dict(
                    committed=h.u(base+core['committed'],1),recheck=h.u(base+core['recheck'],1),
                    inflight=h.u(pe.ROOT_ADDR+6,1))) or False)
                h.b.add_breakpoint(0x202d6f38,lambda b:previews.append(full_plan(h,p)) or False)
                record['result']=ux.need(fr.press(h,key,steps=30000000))
                assert entries and entries[0]==dict(committed=0,recheck=0,inflight=1),entries
                record['after']=ux.snap(h,p);record['final_plan']=full_plan(h,p)
                assert record['final_plan']['matches'] and previews and previews[-1]['matches']
                assert h.u(0x2037f3bc)==0 and h.u(0x2022f5ac,1)==7
                record.update(status='PASS',check_entries=entries,preview_plans=previews,
                    complete_recipe=ux.matches(h,p,4),rpc_log=p.rpc.log,
                    native_UI=ui_audit(h),file_mutations=m.no_writes(p))
            except BaseException:
                record.update(status='FAIL',error=traceback.format_exc());code=1
            save('local/cold-exit/'+args.unit+'-'+action+'.json',record)
            print(args.unit,action,record['status'],record.get('error','')[-600:],flush=True)
            os._exit(code)
        _,status=os.waitpid(pid,0)
        results.append(dict(action=action,wait_status=status))
    save('evidence/cold-exit-'+args.unit+'.json',dict(status='PASS' if all(r['wait_status']==0 for r in results) else 'FAIL',
        unit=args.unit,dat_sha256=PIN,cases=results))
    assert all(r['wait_status']==0 for r in results)

if __name__=='__main__':
    main()
