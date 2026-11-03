"""Independent missing-cut probes against the supplied final DAT."""
from native_support import *
from trace import Audit
import argparse
import os
import traceback


class BeforePublish:
    def __init__(self, h, p, audit, cut, key):
        self.h, self.p, self.audit = h, p, audit
        self.cut, self.key, self.record = cut, key, None
        audit.bp(symbol(p, 'ig_menu'), lambda b: self.at(b, 'menu_entry'))
        audit.bp(symbol(p, 'rv_call'), self.service)
        audit.bp(symbol(p, 'ui_list'), lambda b: self.at(b, 'ui_list_entry'))
        audit.bp(symbol(p, 'rv_irq_save'), self.irq)

    def service(self, b):
        if b.core.r[0] == 11 and b.core.r[1] == 2:
            return self.at(b, 'first_text_service')
        return False

    def irq(self, b):
        if self.audit.ui_op == 1:
            return self.at(b, 'first_publish_irq')
        return False

    def at(self, b, point):
        if self.record is not None or point != self.cut:
            return False
        before = snapshot(self.h, self.p)
        self.record = dict(cut=point, key=self.key, pc=hex(b.pc), psw=b.core.psw, before=before)
        assert b.core.psw & 0x40, 'Probe requires a real IRQ-enabled boundary'
        other = shadow(self.h)
        self.audit.external = True
        try:
            self.record['event'] = action(other, self.p, self.key)
        finally:
            self.audit.external = False
        self.record['after_injection'] = snapshot(self.h, self.p)
        return False


def prepublish(unit, warm=False):
    h,p,w,arm = setup(unit)
    audit = Audit(h,p,arm)
    loaded = p.load()
    assert loaded['load']['ok'] and loaded['state'] == 3, loaded
    if warm:
        open_menu(h,p)
        action(h,p,'ok')
    h.parent()
    results=[]
    for cut in ('menu_entry', 'first_text_service', 'ui_list_entry', 'first_publish_irq'):
        for key in ('up','down','disp','ok','adj','half'):
            name=f'{unit}-' + ('reopen-' if warm else 'prepublish-') + f'{cut}-{key}'
            sys.stdout.flush()
            pid=os.fork()
            if pid==0:
                record=dict(case=name, unit=unit, cut=cut, key=key)
                code=0
                try:
                    probe=BeforePublish(h,p,audit,cut,key)
                    h.b.core.psw |= 0x40
                    record['outer']=fr.native(h,0x20287080,steps=30000000)
                    record['injection']=probe.record
                    record['after']=snapshot(h,p)
                    record['audit']=audit.result(False)
                    record['status']='OBSERVED' if probe.record else 'NOT_FIRED'
                except BaseException:
                    record.update(status='ERROR',error=traceback.format_exc(),audit=audit.result(False))
                    code=1
                save(OUT/'local/probes'/(name+'.json'),record)
                print(name,record['status'],record.get('audit',{}).get('native_setters'),
                    'S_unchanged',record.get('audit',{}).get('settings_unchanged'),
                    record.get('error','')[-350:],flush=True)
                os._exit(code)
            _,status=os.waitpid(pid,0)
            results.append(dict(case=name,wait_status=status))
    save(OUT/'evidence'/(('reopen-' if warm else 'prepublish-')+f'{unit}.json'),results)


def reopen(unit):
    prepublish(unit, warm=True)


def first_service_failure(unit):
    h,p,w,arm=setup(unit)
    audit=Audit(h,p,arm)
    loaded=p.load()
    assert loaded['load']['ok'] and loaded['state']==3
    fired=[False]
    def failure(b):
        if not fired[0] and b.core.r[0]==11 and b.core.r[1]==2:
            fired[0]=True
            b.core.r[0]=0xffffffff
            b.set_reg('pc',b.core.r[14])
        return False
    h.b.add_breakpoint(symbol(p,'rv_call'),failure)
    h.parent()
    result=fr.native(h,0x20287080,steps=30000000)
    record=dict(unit=unit,fault='first UI_TEXT language service returns RV_IO',
        injected=fired[0],result=result,after=snapshot(h,p),audit=audit.result(False))
    save(OUT/'local/probes'/f'{unit}-first-service-failure.json',record)
    print('first_service_failure',unit,'opens',record['after']['opens'],'rows',record['after']['rows'],
        'menu_entries',[e for e in record['audit']['entries'] if 'ig_menu' in e['names']],flush=True)


def preserve(unit):
    h,p,w,arm=setup(unit)
    entry,mapping=m.unpack(p.dat,m.INDEX[unit],5)
    stock,_=m.unpack(p.dat,m.INDEX[unit],4)
    for row in range(9):
        descriptor=mapping[32+12*row:44+12*row]
        address,length,offset=struct.unpack_from('>IHH',descriptor)
        source=stock if descriptor[10] and not entry[1]&descriptor[10] else entry
        for index,value in enumerate(source[offset:offset+length]):
            at=address+index
            word=at&~1
            prior=p.rpc.half(word)
            assert prior is not None,hex(word)
            shift=0 if at&1 else 8
            p.rpc.overlay[word]=(prior&~(255<<shift))|(value<<shift)
    p.rpc.t=int.from_bytes(entry[445:447],'big')
    before=m.deep(p,5)
    overlay=dict(p.rpc.overlay)
    settings=h.b.read(h.settings,0xc9e)
    audit=Audit(h,p,arm)
    opened=open_menu(h,p)
    for _ in range(5):action(h,p,'disp')
    action(h,p,'up')
    action(h,p,'down')
    action(h,p,'ok')
    open_menu(h,p)
    action(h,p,'adj')
    open_menu(h,p)
    action(h,p,'half')
    assert p.rpc.overlay==overlay
    assert h.b.read(h.settings,0xc9e)==settings
    after=m.deep(p,5)
    record=dict(status='PASS',unit=unit,
        fixture='Host model expands retained gen121 slot 05 into RpcEdge overlay before auditing; no native UI fields are preset and no real lens is used.',
        before=before,after=after,opened=opened,audit=audit.result(),
        settings_unchanged=True,lens_overlay_unchanged=True,
        power_cycle_observed=False)
    save(OUT/'local/probes'/f'{unit}-preserve.json',record)
    print(unit,'preserve',record['status'],'rows',len(before['rows']),'lens bytes',before['bytes'],flush=True)


def withdrawal(unit):
    h,p,w,arm=setup(unit)
    audit=Audit(h,p,arm)
    open_menu(h,p)
    results=[]
    for close_key in ('ok','adj'):
        for cut in ('abort_restore','abort_return'):
            for key in ('up','down','disp','ok','adj','half'):
                name=f'{unit}-withdrawal-{close_key}-{cut}-{key}'
                sys.stdout.flush()
                pid=os.fork()
                if pid==0:
                    record=dict(case=name,unit=unit,cut=cut,key=key,close_key=close_key)
                    fired=[False]
                    pending=[False]
                    s_writes=[]
                    code=0
                    def s_write(event):
                        if fired[0]:
                            s_writes.append(dict(address=hex(event.address),bytes=len(event.data),
                                pc=hex(event.pc) if event.pc is not None else None,
                                origin=event.origin,data=event.data.hex()))
                    h.b.add_write_trace(h.settings,h.settings+0xc9e,s_write)
                    def inject(b):
                        if fired[0]:return False
                        fired[0]=True
                        before=snapshot(h,p)
                        record['injection']=dict(pc=hex(b.pc),psw=b.core.psw,before=before)
                        assert b.core.psw&0x40
                        other=shadow(h)
                        audit.external=True
                        try:record['injection']['event']=action(other,p,key)
                        finally:audit.external=False
                        record['injection']['after_injection']=snapshot(h,p)
                        return False
                    def restoring(b):
                        if cut=='abort_restore' and not pending[0] and h.u(0x2022f5ac,1)==7:
                            pending[0]=True
                            audit.bp(b.core.r[14],inject)
                        return False
                    def aborting(b):
                        if cut=='abort_return' and not pending[0]:
                            pending[0]=True
                            audit.bp(b.core.r[14],inject)
                        return False
                    h.b.add_breakpoint(h.symbols['rv_irq_restore'],restoring)
                    h.b.add_breakpoint(h.symbols['rv_ui_abort'],aborting)
                    try:
                        h.b.core.psw|=0x40
                        record['outer']=action(h,p,close_key)
                        record.update(status='OBSERVED' if fired[0] else 'NOT_FIRED',
                            after=snapshot(h,p),audit=audit.result(False),S_writes_after_cut=s_writes)
                    except BaseException:
                        record.update(status='ERROR',error=traceback.format_exc(),audit=audit.result(False),S_writes_after_cut=s_writes)
                        code=1
                    save(OUT/'local/probes'/(name+'.json'),record)
                    print(name,record['status'],'setters',record['audit']['native_setters'],
                        'S_unchanged',record['audit']['settings_unchanged'],record.get('error','')[-300:],flush=True)
                    os._exit(code)
                _,status=os.waitpid(pid,0)
                results.append(dict(case=name,wait_status=status))
    save(OUT/'evidence'/f'withdrawal-{unit}.json',results)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--unit',choices=('50mm','28mm','mount'),required=True)
    parser.add_argument('--kind',choices=('prepublish','reopen','first_service_failure','preserve','withdrawal'),required=True)
    args=parser.parse_args()
    globals()[args.kind](args.unit)
