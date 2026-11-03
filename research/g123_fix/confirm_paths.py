"""Use the native keep flag setter before the real OK and ADJ handlers."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import run_native as n
from common import save,sha
unit=sys.argv[1];n.configure(unit,'confirm-paths');ux,m,fr=n.ux,n.m,n.fr
h,p,w=m.boot(unit);m.published(h,p,w);ins=ux.instrument(h,p);ux.arm_entries(h,p,ins)
rows=[]
moving=[False];dot_checks=dict(rpc_observations=0,selected_rows=[],mismatches=[]);original_rpc=p.rpc.call
def check_cursor(cmd,value):
    if moving[0]:
        dot=h.u(0x2022f725,1);cursor=h.u(0x2022f726,1)
        dot_checks['rpc_observations']+=1
        if cursor not in dot_checks['selected_rows']:dot_checks['selected_rows'].append(cursor)
        if dot!=cursor:dot_checks['mismatches'].append(dict(dot=dot,cursor=cursor,cmd=cmd))
        assert dot==cursor,'Dot must follow the selected row before every communication.'
    return original_rpc(cmd,value)
p.rpc.call=check_cursor
for keep in (0,1):
    for event in (0x23,0x2b):
        target=(3,5,1,2)[len(rows)]
        m.reopen(h,p,w);moving[0]=True
        ux.move_to(h,p,target,ins);moving[0]=False
        ux.need(fr.native(h,0x20265818,(keep,)));assert h.u(0x2037f2fe,1)==keep
        at=len(ins['events']);rpc=len(p.rpc.log);before=ux.snap(h,p)
        assert before['list']['previewing']==1 and before['list']['current_slot']==target
        result=ux.need(fr.press(h,event));after=ux.snap(h,p);events=ins['events'][at:]
        assert len(events)==1 and events[0]['keep']==keep and int(events[0]['raw'],16)==event,events
        assert events[0]['caller']==('0x202c2d74' if keep else '0x202c2d84'),events
        assert after['list']['confirmed_valid']==1 and after['list']['confirmed_slot']==target
        assert len(p.rpc.log)==rpc
        if keep:assert after['list']['opened']==1 and after['rows']==8
        else:assert after['list']['opened']==0 and after['native_overlay']==0
        rows.append(dict(keep=keep,event=hex(event),target=target,before=before,after=after,events=events,result=result,extra_rpc=0,actual=ux.matches(h,p,target)))
        ux.need(fr.native(h,0x20265818,(0,)))
        print('PASS native confirmation',unit,'keep',keep,'event',hex(event),flush=True)
save('local/native/confirm-paths-'+unit+'.json',dict(status='PASS',unit=unit,dat_sha256=sha(m.DAT.read_bytes()),cases=rows,dot_checks=dot_checks,file_mutations=m.no_writes(p),
    native_ui_hand_seeded=False,getter_fixed_return_stub_removed=True))
