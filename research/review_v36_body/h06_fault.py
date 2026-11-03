"""H06 retire transition must skip its native writeback while eight rows are live."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from review_common import HERE,save as original_save
exec(compile((HERE/'adversarial.py').read_text().split('selected=sys.argv')[0],str(HERE/'adversarial.py'),'exec'),globals())
def save(name,value):original_save('h06-fault-'+name,value)
POINTS[0x202be250]='H06_native'
run('H06_check_retire_live8',[OPEN,ONE,OK,REOPEN,('negative: corrupt snapshot',corrupt_ui),FN2,MENU])
save('adversarial.json',reports);r=reports[-1]
assert 'error' not in r and r['final']['mode']==1 and r['final']['native_visits']['H06_native']==0
assert r['final']['root']['state']==6 and r['final']['ui']['rows']==7
assert r['final']['deep_sha256']==r['steps'][2]['after']['deep_sha256']
print('PASS H06 retire transition skips native writeback',flush=True)
