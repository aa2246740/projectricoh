"""Exercise each public ingress guard and every H01 UI-service failure cut."""
from native_support import *
from trace import Audit
import argparse
import os
import traceback

ENTRIES=('ig_bootstrap','ig_init','ig_menu','ig_event','ig_apply',
         'ig_panel_open','ig_panel_event','ig_panel_abort','ig_stop')
FAULTS=('api','version','bytes','flags','token','context_null','context_bytes')


def call_entry(h,p,name):
    q,reply=0x206d0000,0x206d0040
    h.b.write(q,bytes(96))
    return p.call(h.symbols['rv_engine'],(pe.ROOT_ADDR,p.elf.symbols[name],q,reply),30000000)


def ingress_case(h,p,audit,name,fault):
    fired=[False]
    def inject(b):
        if fired[0]:return False
        fired[0]=True
        q=b.core.r[2]
        if fault=='api':b.core.r[0]=1
        else:
            offset,value,width=dict(version=(0,2,2),bytes=(2,60,2),flags=(4,1,4),
                token=(8,b.core.r[1]^1,4),context_null=(48,0,4),context_bytes=(52,0,4))[fault]
            audit.external=True
            try:
                b.origin='review:request_fault'
                h.put(q+offset,value,width)
            finally:audit.external=False
        return False
    h.b.add_breakpoint(symbol(p,name),inject)
    result=call_entry(h,p,name)
    assert fired[0] and result.get('ok') and result['signed']==3, (fired[0],result)
    checked=audit.result()
    assert checked['settings_unchanged']
    return dict(status='PASS',entry=name,fault=fault,result=result,after=snapshot(h,p),audit=checked)


def service_case(h,p,audit,number):
    seen=[]
    def inject(b):
        seen.append(dict(id=b.core.r[0],op=b.core.r[1],rows=h.u(0x2022f5ac,1)))
        if len(seen)==number:
            b.core.r[0]=0xffffffff
            b.set_reg('pc',b.core.r[14])
        return False
    # Audit records the original service arguments before this fault model.
    h.b.add_breakpoint(symbol(p,'rv_call'),inject)
    result=need(fr.native(h,0x20287080,steps=30000000))
    assert len(seen)>=number,(number,len(seen))
    after=snapshot(h,p)
    assert after['opens']==1
    assert after['rows']==(7 if number<=17 else 8),after
    if number>17:
        action(h,p,'disp')
        assert text_rows(h,p)==['E0001 U','NO DATA','NOT ZERO','RAW ONLY','NO RPC','NO FILE','CLOSE','REOPEN']
    checked=audit.result()
    assert checked['settings_unchanged']
    return dict(status='PASS',service_failure_index=number,
        failed_service=seen[number-1],after_failure=after,after=snapshot(h,p),result=result,audit=checked)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--unit',choices=('50mm','28mm','mount'),required=True)
    args=parser.parse_args()
    h,p,w,arm=setup(args.unit)
    audit=Audit(h,p,arm)
    loaded=p.load()
    assert loaded['load']['ok'] and loaded['state']==3,loaded
    h.parent()
    jobs=[('ingress-'+entry+'-'+fault,('ingress',entry,fault)) for entry in ENTRIES for fault in FAULTS]
    jobs += [('service-'+str(number),('service',number)) for number in range(1,35)]
    results=[]
    for label,parameters in jobs:
        case=args.unit+'-'+label
        sys.stdout.flush()
        pid=os.fork()
        if pid==0:
            record=dict(case=case,unit=args.unit)
            code=0
            try:
                if parameters[0]=='ingress':record.update(ingress_case(h,p,audit,*parameters[1:]))
                else:record.update(service_case(h,p,audit,*parameters[1:]))
            except BaseException:
                record.update(status='FAIL',error=traceback.format_exc(),audit=audit.result(False))
                code=1
            save(OUT/'local/errors'/(case+'.json'),record)
            print(case,record['status'],record.get('error','')[-350:],flush=True)
            os._exit(code)
        _,status=os.waitpid(pid,0)
        results.append(dict(case=case,wait_status=status))
    save(OUT/'evidence'/f'errors-{args.unit}.json',dict(cases=results,
        status='PASS' if all(x['wait_status']==0 for x in results) else 'FAIL'))
    assert all(x['wait_status']==0 for x in results),results
