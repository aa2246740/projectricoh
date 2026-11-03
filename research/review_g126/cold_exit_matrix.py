"""Repeat every first-publication cut with OK, ADJ and raw half-shutter exits."""
from pathlib import Path
import argparse
import inspect
import os
import sys
import traceback
sys.path.insert(0,str(Path(__file__).resolve().parent))
from support import *
import cold_reentry as cold

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--unit',choices=('50mm','28mm','mount'),required=True)
    parser.add_argument('--tag',default='')
    args=parser.parse_args()
    ux,m,fr,pe,v=setup(126,args.unit,'cold-exit-matrix')
    h,p,w=m.boot(args.unit)
    sequence=load(MATERIALS/'native_sequence.py','cold_exit_sequence')
    source=inspect.getsource(cold.case)
    old='ux.need(fr.press(h,0x23,steps=30000000))'
    assert source.count(old)==1
    source=source.replace(old,'exit_event(h,p,w,fr,ux,record)')
    fixture=ux,m,fr,pe,v,h,p,w
    results=[]
    for cut,direction in (('control','right'),('before_publish','right'),('before_publish','left'),('after_publish_restore','right')):
        for key in ('OK','ADJ','HALF'):
            label='-'.join((args.unit,cut,direction,key))
            sys.stdout.flush()
            pid=os.fork()
            if pid==0:
                record=dict(case=label,generation=126,exit_key=key)
                code=0
                def exit_event(h,p,w,fr,ux,record):
                    mark=w.mark()
                    if key=='HALF':
                        sequence.device_edges(h,p)
                        sequence.prepare_input(h)
                        h.stub(0x0500c6ec,'review_normal_task_context',value=0)
                        def task_id(b):
                            b.write(b.core.r[4],(6).to_bytes(2,'big'))
                            return 0
                        h.stub(0x0500c574,'review_task_id',task_id)
                        h.stub(0x2005e034,'review_RTOS_message_submit',value=0)
                        result=sequence.key(h,fr,0x0d)
                        assert result['logical']==0x29 and all(x['ok'] for x in result['dispatch'])
                    else:
                        result=ux.need(fr.press(h,0x23 if key=='OK' else 0x2b,steps=30000000))
                    record['exit_hooks']=w.since(mark)
                    return result
                namespace=dict(cold.__dict__,exit_event=exit_event)
                exec(compile(source,__file__,'exec'),namespace)
                try:
                    namespace['case'](fixture,cut,direction,record)
                    assert record['exit_plan']['matches']
                    m.no_writes(p)
                except BaseException:
                    record.update(status='FAIL',error=traceback.format_exc())
                    code=1
                save('local/cold-exit-matrix'+args.tag+'/'+label+'.json',record)
                print(label,record.get('status'),record.get('error','')[-500:],flush=True)
                os._exit(code)
            _,status=os.waitpid(pid,0)
            results.append(dict(case=label,wait_status=status))
    save('evidence/cold-exit-matrix-'+args.unit+args.tag+'.json',dict(status='PASS' if all(r['wait_status']==0 for r in results) else 'FAIL',
        dat_sha256=PIN,unit=args.unit,cases=results))
    assert all(r['wait_status']==0 for r in results)

if __name__=='__main__':main()
