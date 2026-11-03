"""Repeat the menu write checks with complete native UI object spans."""
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import OUT,ROOT,save
unit=sys.argv[1];assert unit in ('50mm','28mm','mount')
jobs=[('other_menu-at'+str(at),'concurrent_menu.py','other_menu',unit,'--at',str(at),'--reopen-fn2') for at in (1,6,16,17,140)]
jobs += [('ui-'+point,'ui_cutpoints.py',point,unit) for point in ('redraw','cache')]
jobs += [('entry-'+entry,'entry_switch.py',unit,entry) for entry in ('fn2','ok','adj')]
jobs += [('confirm-paths','confirm_paths.py',unit)]
rows=[]
for label,script,*args in jobs:
    print('BEGIN UI SCOPE',unit,label,flush=True)
    rc=subprocess.call(['/usr/bin/python3','-I','-B',str(OUT/'run_recorded.py'),unit+'-'+label+'-u2','/usr/bin/python3','-I','-B',str(OUT/script),*args],cwd=ROOT)
    rows.append(dict(label=label,returncode=rc));save('ui-scope-queue-'+unit+'.json',rows)
    print('END UI SCOPE',unit,label,'exit',rc,flush=True)
print('COMPLETE UI SCOPE',unit,'failures',[x for x in rows if x['returncode']],flush=True)
raise SystemExit(any(x['returncode'] for x in rows))
