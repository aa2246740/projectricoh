"""Controlled reentry on real engine instructions; no scheduler claim."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from review_common import HERE,save as original_save
exec(compile((HERE/'adversarial.py').read_text().split('selected=sys.argv')[0],str(HERE/'adversarial.py'),'exec'),globals())
def save(name,value):original_save('reachability-'+name,value)
POINTS[0x202be250]='H06_native'

def nested_hook(h,p,w,hook,entry):
    pc=p.symbol_pc(entry); injected=[False]
    def enter(b):
        if injected[0]:return False
        injected[0]=True
        context=dict(r=list(b.core.r),pc=b.pc,psw=b.core.psw,cr=dict(b.core.cr),acc=b.core.acc)
        before=snapshot(h,p); mark=w.mark(); wi=len(h.writes)
        b.running=False;b.set_reg('r15',0x206efff0)
        done=fr.move_key(h,0x1f) if hook==8 else fr.native(h,0x202be220)
        after=snapshot(h,p)
        reports[-1]['nested']=dict(hook=hook,result=done,before=before,after=after,hooks=w.since(mark),
          settings_writes=[x for x in h.writes[wi:] if h.settings<=int(x['address'],16)<h.settings+4096],
          limitation='Controlled input during real engine inflight; does not establish camera scheduling.')
        b.core.r[:]=context['r'];b.pc=context['pc'];b.core.psw=context['psw'];b.core.cr=context['cr'];b.core.acc=context['acc'];b.running=True
        return False
    h.b.add_breakpoint(pc,enter)
    out=fr.move_key(h,0x20) if entry=='ig_apply' else fr.press(h,0x23)
    out['injected']=injected[0];return out

which=sys.argv[1] if len(sys.argv)>1 else 'all'
if which in ('all','h08'):
    run('nested_H08_extended',[OPEN,ONE,OK,REOPEN,('inflight H08',lambda h,p,w:nested_hook(h,p,w,8,'ig_apply')),MENU])
if which in ('all','h06'):
    run('nested_H06_extended',[OPEN,ONE,OK,REOPEN,('inflight H06',lambda h,p,w:nested_hook(h,p,w,6,'ig_apply')),MENU])
if which in ('all','postok'):
    run('post_OK_H08',[OPEN,ONE,OK,SCROLL,('direct H08 after real abort',lambda h,p,w:fr.native(h,0x202bb968)),MENU])
    run('post_OK_H06',[OPEN,ONE,OK,('Fn2 after real abort',lambda h,p,w:fr.native(h,0x202be220)),MENU])
save('adversarial.json',reports)
assert all('error' not in r for r in reports)
