"""Reentry after H01 first publication, across sampling and final publication."""
from pathlib import Path
import argparse
import json
import os
import sys
import traceback
sys.path.insert(0,str(Path(__file__).resolve().parent))
from cutpoints import *

H01_CUTS=('first_restore','before_sample','between_reads','after_sample','second_restore')


class H01Cut(Cut):
    def __init__(self,h,p,audit,cut,action_name=None,loss=None):
        super().__init__(h,p,audit,cut,action_name,loss)
        audit.bp(symbol(p,'capture'),self.at_capture)
        audit.capture_pass_hook=lambda:self.at_between(h.b)

    def eligible(self):
        return self.audit.active and not (self.fired or self.pending)

    def boundary(self,b,kind):
        if not self.eligible() or self.audit.ui_op!=1 or kind!='restore':return False
        number=len(self.audit.ui_entries)
        if self.cut=='first_restore' and number==1 or self.cut=='second_restore' and number==2:
            self.pending=True;caller=b.core.r[14]
            def restored(b):
                if self.pending and not self.fired:self.pending=False;self.inject(b)
                return False
            self.audit.bp(caller,restored)
        return False

    def at_capture(self,b):
        if not self.eligible():return False
        if self.cut=='before_sample':self.inject(b)
        elif self.cut=='after_sample':
            self.pending=True;caller=b.core.r[14]
            def done(b):
                if self.pending and not self.fired:self.pending=False;self.inject(b)
                return False
            self.audit.bp(caller,done)
        return False

    def at_between(self,b):
        if self.eligible() and self.cut=='between_reads':self.inject(b)


def run_h01(fixture,cut,act=None,loss=None):
    h,p,w,arm,audit=fixture
    controller=H01Cut(h,p,audit,cut,act,loss)
    h.b.core.psw|=0x40
    result=need(fr.native(h,0x20287080,steps=30000000))
    assert controller.fired,(cut,act,loss)
    assert controller.injection['before']['rows']==8
    assert controller.injection['psw']&0x40
    if controller.checking_loss:
        assert not controller.after_writes,controller.after_writes
        assert not controller.after_draws,controller.after_draws
    return dict(status='PASS',cut=cut,action=act,loss=loss,result=result,injection=controller.injection,
                late_DAT_UI=controller.after_writes,late_draws=controller.after_draws,
                after=snapshot(h,p),audit=audit.result())


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--unit',choices=('50mm','28mm','mount'),required=True)
    args=parser.parse_args()
    h,p,w,arm=setup(args.unit);audit=Audit(h,p,arm)
    # Same real loader and bootstrap/init as cold H01, shared once across forks.
    loaded=p.load();assert loaded['load']['ok'] and loaded['state']==3,loaded
    h.parent();fixture=(h,p,w,arm,audit)
    jobs=[(cut,act,None) for cut in H01_CUTS for act in ACTIONS]
    jobs += [(cut,None,loss) for cut in H01_CUTS for loss in ('activity','state')]
    results=[]
    for cut,act,loss in jobs:
        name=args.unit+'-h01-'+cut+'-'+(act or loss)
        sys.stdout.flush();pid=os.fork()
        if pid==0:
            record=dict(case=name,setup=loaded);code=0
            try:record.update(run_h01(fixture,cut,act,loss))
            except BaseException:record.update(status='FAIL',error=traceback.format_exc(),audit=audit.result(False));code=1
            save(OUT/'local/h01'/(name+'.json'),record)
            print(name,record['status'],record.get('error','')[-500:],flush=True)
            os._exit(code)
        _,status=os.waitpid(pid,0);results.append(dict(case=name,wait_status=status))
    save(OUT/'evidence'/f'h01-{args.unit}.json',dict(dat_sha256=sha(DAT),cases=results,
        status='PASS' if all(x['wait_status']==0 for x in results) else 'FAIL'))
    assert all(x['wait_status']==0 for x in results),results


if __name__=='__main__':main()
