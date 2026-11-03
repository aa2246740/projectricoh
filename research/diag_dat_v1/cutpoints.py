"""Native key reentry and ownership loss around publication and IRQ restore."""
from pathlib import Path
import argparse
import json
import os
import sys
import traceback
sys.path.insert(0,str(Path(__file__).resolve().parent))
from trace import *

CUTS=('before_update_irq','after_update_restore','before_redraw_irq','after_redraw_restore',
      'before_draw','row_draw')
ACTIONS=('up','down','disp','ok','adj','half')


class Cut:
    def __init__(self,h,p,audit,cut,action_name=None,loss=None):
        self.h,self.p,self.audit=h,p,audit
        self.cut,self.action_name,self.loss=cut,action_name,loss
        self.fired=False;self.pending=False;self.injection=None
        self.checking_loss=False
        self.saves=0;self.restores=0;self.after_writes=[];self.after_draws=[]
        audit.bp(symbol(p,'rv_irq_save'),lambda b:self.boundary(b,'save'))
        audit.bp(symbol(p,'rv_irq_restore'),lambda b:self.boundary(b,'restore'))
        audit.bp(symbol(p,'rv_native_draw'),lambda b:self.draw(b))
        audit.bp(0x201ffb2c,lambda b:self.row(b))
        h.b.add_write_trace(0,2**32,self.write)

    def eligible(self):
        return self.audit.active and self.audit.ui_op==3 and not (self.fired or self.pending)

    def boundary(self,b,kind):
        if not self.eligible():return False
        if kind=='save':self.saves+=1
        else:self.restores+=1
        wanted=(self.cut=='before_update_irq' and kind=='save' and self.saves==1 or
                self.cut=='before_redraw_irq' and kind=='save' and self.saves==2)
        if wanted:self.inject(b)
        if kind=='restore' and (
                self.cut=='after_update_restore' and self.restores==1 or
                self.cut=='after_redraw_restore' and self.restores==2):
            self.pending=True;caller=b.core.r[14]
            def restored(b):
                if self.pending and not self.fired:self.pending=False;self.inject(b)
                return False
            self.audit.bp(caller,restored)
        return False

    def draw(self,b):
        if self.eligible() and self.cut=='before_draw':self.inject(b)
        if self.fired and self.checking_loss:self.after_draws.append(dict(pc=hex(b.pc),psw=b.core.psw))
        return False

    def row(self,b):
        if self.eligible() and self.cut=='row_draw':self.inject(b)
        return False

    def inject(self,b):
        self.fired=True
        before=snapshot(self.h,self.p)
        assert before['rows']==8,before
        settings=self.h.b.read(self.h.settings,0xc9e)
        other=shadow(self.h)
        self.audit.external=True
        try:
            if self.loss=='activity':
                other.run_slice(0x202ba380,0x202ba3c8)
                other.leave_other_list()
                result=dict(native_constructor='0x20285e00')
            elif self.loss=='state':result=need(fr.native(other,0x202b0a74,(55,)))
            else:result=action(other,self.p,self.action_name)
        finally:
            self.audit.external=False
        self.injection=dict(pc=hex(b.pc),psw=b.core.psw,before=before,after=snapshot(self.h,self.p),
                            result=result,settings_unchanged=self.h.b.read(self.h.settings,0xc9e)==settings)
        after=self.injection['after']
        self.checking_loss=bool(self.loss) or bool(b.core.psw&0x40) and (
            after['activity']!=8 or after['native_state']!=56 or after['overlay']!=32)
        assert self.injection['settings_unchanged']
        if self.loss:
            assert b.core.psw&0x40,'Ownership-loss preemption must occur with IRQ enabled'

    def write(self,e):
        if not self.fired or not self.checking_loss or self.audit.external:return
        low=self.p.image_base+256
        length=int.from_bytes(self.p.dat[136:140],'big')
        block=self.h.u(pe.ROOT_ADDR+56)
        context=block+40
        ui_source=self.h.u(context+64)
        ui_snapshot=self.h.u(context+24)
        watched=(*UI_RANGES,(ui_source,ui_source+256),(ui_snapshot,ui_snapshot+1968))
        if e.pc is not None and low<=e.pc<low+length and (
                any(e.address<hi and e.address+len(e.data)>lo for lo,hi in watched)):
            self.after_writes.append(dict(pc=hex(e.pc),address=hex(e.address),data=e.data.hex()))


def run_case(fixture,cut,action_name=None,loss=None):
    h,p,w,arm,audit=fixture
    controller=Cut(h,p,audit,cut,action_name,loss)
    h.b.core.psw|=0x40
    result=action(h,p,'disp')
    assert controller.fired,(cut,action_name,loss,controller.saves,controller.restores)
    if controller.checking_loss:
        assert not controller.after_writes,controller.after_writes
        assert not controller.after_draws,controller.after_draws
    record=dict(cut=cut,action=action_name,loss=loss,injection=controller.injection,
                outer=result,after=snapshot(h,p),late_DAT_UI=controller.after_writes,
                late_draws=controller.after_draws,audit=audit.result())
    record['status']='PASS'
    return record


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--unit',choices=('50mm','28mm','mount'),required=True)
    parser.add_argument('--kind',choices=('nested','loss'),required=True)
    parser.add_argument('--error',action='store_true')
    args=parser.parse_args()
    h,p,w,arm=setup(args.unit);audit=Audit(h,p,arm)
    fired=audit.arm_error_page(arm) if args.error else None
    open_menu(h,p)
    if args.error:
        assert fired[0]
        action(h,p,'disp')
        assert text_rows(h,p)[0]=='E0001 U'
    fixture=(h,p,w,arm,audit)
    jobs=[(cut,act,None) for cut in CUTS for act in ACTIONS] if args.kind=='nested' else [
        (cut,None,loss) for cut in CUTS[:4] for loss in ('activity','state')]
    results=[]
    for cut,act,loss in jobs:
        name=args.unit+'-'+args.kind+('-error' if args.error else '')+'-'+cut+'-'+(act or loss)
        sys.stdout.flush();pid=os.fork()
        if pid==0:
            record=dict(case=name);code=0
            try:record.update(run_case(fixture,cut,act,loss))
            except BaseException:
                record.update(status='FAIL',error=traceback.format_exc(),audit=audit.result(False));code=1
            save(OUT/'local/cutpoints'/(name+'.json'),record)
            print(name,record['status'],record.get('error','')[-450:],flush=True)
            os._exit(code)
        _,status=os.waitpid(pid,0)
        results.append(dict(case=name,wait_status=status))
    save(OUT/'evidence'/f'{args.kind}-{args.unit}{"-error" if args.error else ""}.json',dict(status='PASS' if all(r['wait_status']==0 for r in results) else 'FAIL',
        dat_sha256=sha(DAT),cases=results))
    assert all(r['wait_status']==0 for r in results),results


if __name__=='__main__':main()
