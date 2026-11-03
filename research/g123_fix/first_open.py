"""H01 failures through native arrows, DISP and confirmation, then re-open."""
from pathlib import Path
import json,struct,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import native_cases as nc
from common import OUT,save,sha

CONDITIONS=('communication','communication_row_reset','ready','ready_row_reset',
    'settings_epoch_busy','mode_epoch_busy','settings_epoch_during_read','mode_epoch_during_read')

def main(unit):
    n,ux,m,fr,pe=nc.n,nc.ux,nc.m,nc.fr,nc.pe
    n.configure(unit,'first-open-final')
    h,p,w=m.boot(unit);m.published(h,p,w)
    nc.move_to(h,p,5);ux.matches(h,p,5);ux.need(fr.press(h,0x2b))
    checkpoint=nc.stamp(h,p)
    layout=json.loads((OUT/'local/layout/current-adapter-layout.json').read_text())
    summaries=[]
    for condition in CONDITIONS:
        for entry in ('direction','disp','confirm'):
            for recovered in (False,True):
                label='first-open-'+unit+'-'+condition+'-'+entry+('-recovered' if recovered else '-busy')
                def run(record,condition=condition,entry=entry,recovered=recovered):
                    original=p.rpc.call;before=ux.snap(h,p);at=len(p.rpc.log)
                    drawn=[];menus=[];entries=[]
                    def draw(b):
                        drawn.append(dict(rows=h.u(0x2022f5ac,1),marker=h.u(0x2022f725,1),cursor=h.u(0x2022f726,1)));return False
                    h.b.add_breakpoint(0x201ffb2c,draw)
                    h.b.add_breakpoint(p.symbol_pc('ig_menu'),lambda b:menus.append(hex(b.pc)) or False)
                    for symbol in ('ig_apply','ig_panel_open','ig_event'):
                        h.b.add_breakpoint(p.symbol_pc(symbol),lambda b,symbol=symbol:entries.append(symbol) or False)
                    if condition!='communication' and condition!='ready':
                        p.rpc.overlay.clear();p.rpc.t=2
                    def epoch():
                        index=7 if condition.startswith('settings') else 8
                        address=pe.ROOT_ADDR+8+4*index
                        h.b.origin='model:explicit_epoch_transition'
                        h.b.write(address,struct.pack('>I',h.u(address)+1))
                    if condition.endswith('_busy'):epoch()
                    if condition.startswith('ready'):
                        p.ready=0;ux.need(fr.native(h,0x200935b4,(0,)))
                    else:
                        fired=[False]
                        def fault(command,value):
                            if condition.endswith('_during_read'):
                                result=original(command,value)
                                if not fired[0]:epoch();fired[0]=True
                                return result
                            p.rpc.log.append(dict(cmd=command,value=value,page=p.rpc.page,result=-1,t=p.rpc.t,simulated=True));return -1
                        p.rpc.call=fault
                    h.parent();opened,_,error=fr.publish(h,p,w);ux.need(opened);assert error is None,error
                    pending=ux.snap(h,p);adapter=p.symbol_pc('n')
                    assert len(menus)==1 and pending['rows']==7 and not pending['root']['ui_restore0'],pending
                    assert not h.u(adapter+layout['failed'],1) and not h.u(adapter+layout['retry'],1)
                    assert pending['W']==before['W']
                    assert drawn and all(x['rows']==7 for x in drawn),drawn
                    def recover():
                        p.rpc.call=original
                        if condition.startswith('ready'):
                            p.ready=1;ux.need(fr.native(h,0x200935b4,(1,)))
                    if recovered:recover()
                    event_at=len(p.rpc.log)
                    result=(fr.move_key(h,0x20,steps=30000000) if entry=='direction' else
                        fr.native(h,0x202be220,steps=30000000) if entry=='disp' else fr.press(h,0x23,steps=30000000))
                    ux.need(result);after=ux.snap(h,p)
                    assert after['rows']!=8 and not after['root']['ui_restore0'],after
                    assert not entries,entries
                    recover();reopen_at=len(p.rpc.log)
                    reopened=m.reopen(h,p,w);actual=ux.matches(h,p,5)
                    assert reopened['rows']==8 and reopened['cursor']==5
                    assert len(p.rpc.log)>reopen_at
                    record.update(unit=unit,condition=condition,entry=entry,recovered_before_entry=recovered,
                        dat_sha256=sha(p.dat),before=before,pending=pending,first_draws=drawn,
                        event=result,after=after,entry_RPC=reopen_at-event_at,reopen_RPC=len(p.rpc.log)-reopen_at,
                        reopened=ux.snap(h,p),actual=actual,rpc_log=p.rpc.log[at:],
                        native_entries=entries,file_mutations=m.no_writes(p),native_UI_built_by_official_constructors=True)
                result=nc.case(label,run,checkpoint)
                summaries.append(dict(case=label,reopen_RPC=result['reopen_RPC'],entry_RPC=result['entry_RPC']))
    save('evidence/first-open-'+unit+'.json',dict(status='PASS',unit=unit,dat_sha256=sha(p.dat),cases=summaries,
        scope='Warm loaded sessions and explicit unit/epoch faults. H01 falls back to native rows; next H01 restores the verified recipe.'))
    print('PASS H01 fallback',unit,len(summaries),flush=True)
if __name__=='__main__':main(sys.argv[1])
