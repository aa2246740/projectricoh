"""Close the published Image list using native item-8 and shutter handlers.

The parent item arm is native code, just as in the repository's ADJ/OK
helper. No native state byte is supplied by the host.
"""
import argparse
import json
from pathlib import Path
import sys
import traceback

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import native_ux as ux

def activity(h):return h.u(0x205d9bf8)

def run(unit,report):
    m,fr=ux.m,ux.fr
    h,p,w=m.boot(unit);ins=ux.instrument(h,p)
    m.published(h,p,w);ux.arm_entries(h,p,ins)
    report['cases']=[]
    for key in (0x29,0x63):
        moves=ux.move_to(h,p,3,ins)
        # The normal outer ADJ handler executes this same item-8 arm before
        # dispatching keys. Executing the native arm supplies that path here.
        h.select_item_8()
        assert activity(h)==8
        at=len(ins['events']);before=ux.snap(h,p)
        before['native_image_activity']=activity(h)
        first=ux.need(fr.native(h,0x2029fdc4,(key,0),steps=8000000))
        second=ux.need(fr.native(h,0x202bd724,(key,0),steps=8000000))
        after=ux.snap(h,p);after['native_image_activity']=activity(h)
        events=ins['events'][at:]
        actual=ux.matches(h,p,3)
        report['cases'].append(dict(key=hex(key),moves=moves,before=before,
            first_column=first,second_column=second,after=after,events=events,actual=actual))
        assert before['native_overlay']==32 and after['native_overlay']==0,report['cases'][-1]
        if any(e['caller'] in ('0x202bd890','0x202bea54') for e in events):
            assert after['list']['confirmed_valid']==1 and after['list']['confirmed_slot']==3
            assert after['list']['previewing']==0
            report['cases'][-1]['acceptance']='H07'
        else:
            # This native shutter branch withdraws the overlay without H07.
            # The complete live recipe stays applied immediately; the next
            # native constructor accepts it before choosing its highlight.
            assert after['list']['current_slot']==3 and after['list']['previewing']==1
            report['cases'][-1]['acceptance']='live retained; next H01 accepts'
        m.reopen(h,p,w)
        assert h.u(0x2022f726,1)==3
        report['cases'][-1]['reopened']=ux.snap(h,p)
        assert report['cases'][-1]['reopened']['list']['confirmed_slot']==3
        assert report['cases'][-1]['reopened']['list']['confirmed_valid']==1
        ux.matches(h,p,3)
        # Make the next shutter case accept a genuinely pending preview too.
        ux.move_to(h,p,4,ins)
        ux.need(fr.press(h,0x2b));m.reopen(h,p,w)
        print('PASS native shutter exit',unit,hex(key),flush=True)
    report['events']=ins['events'];report['native_log']=p.native_log
    report['file_mutations']=m.no_writes(p);report['status']='PASS'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('unit',choices=('50mm','28mm','mount'))
    args=parser.parse_args()
    dat,elf=ux.configure(False,args.unit+'-exits')
    report=dict(unit=args.unit,dat_sha256=ux.m.sha(dat.read_bytes()),
                engine_elf_sha256=ux.m.sha(elf.read_bytes()),body_sha256=ux.v.BODY_SHA,
                activity_address='0x205d9bf8',native_state_assignments_by_host=0)
    try:run(args.unit,report)
    except Exception:
        report['status']='FAIL';report['error']=traceback.format_exc()
        ux.save('exits-'+args.unit+'.json',report);raise
    ux.save('exits-'+args.unit+'.json',report)

if __name__=='__main__':main()
