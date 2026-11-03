"""A labelled root-only ownership fault while the native list is still eight rows."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from review_common import HERE,save as original_save
exec(compile((HERE/'adversarial.py').read_text().split('selected=sys.argv')[0],str(HERE/'adversarial.py'),'exec'),globals())
def save(name,value):original_save('ownership-'+name,value)
def lose_restore(h,p,w):
    assert fr.u8(h,0x2022f5ac)==8
    h.put(R+156,0)
    return dict(ok=True,negative='Clear root ui_restore[0] only; not a model of successful rv_ui_abort, which restores seven rows.')
run('H08_not_owned_live8',[OPEN,ONE,OK,REOPEN,('negative: root ownership lost with live8',lose_restore),SCROLL,SCROLL])
save('adversarial.json',reports);r=reports[-1]
assert 'error' not in r and r['final']['mode']==1 and r['final']['native_visits']['H08_native']==0
assert r['final']['ui']['rows']==8 and not r['final']['root']['ui_restore0']
assert r['final']['deep_sha256']==r['steps'][2]['after']['deep_sha256']
print('PASS H08 !owned live8 skips native continuation; recipe mode and deep rows retained',flush=True)
