"""Full requested matrix, sequential foreground execution; no sleep or devices."""
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import OUT,ROOT,save

unit=sys.argv[1];assert unit in ('50mm','28mm','mount')
jobs=[('matrix','run_native.py','matrix',unit),('ah','run_native.py','ah',unit),
      ('persistent','run_native.py','persistent',unit),('exits','run_native.py','exits',unit)]
jobs += [('other_menu-at'+str(at),'concurrent_menu.py','other_menu',unit,'--at',str(at),'--reopen-fn2') for at in (1,6,16,17,140)]
jobs += [(group,'concurrent_menu.py',group,unit) for group in ('recovery','fallback','nested')]
jobs += [('ui-'+point,'ui_cutpoints.py',point,unit) for point in ('redraw','cache')]
jobs += [('entry-'+entry,'entry_switch.py',unit,entry) for entry in ('fn2','ok','adj')]
rows=[]
for label,script,*args in jobs:
    print('BEGIN',unit,label,flush=True)
    rc=subprocess.call(['/usr/bin/python3','-I','-B',str(OUT/'run_recorded.py'),unit+'-'+label+'-n2',
                        '/usr/bin/python3','-I','-B',str(OUT/script),*args],cwd=ROOT)
    rows.append(dict(label=label,returncode=rc))
    save('queue-'+unit+'.json',rows)
    print('END',unit,label,'exit',rc,flush=True)
print('COMPLETE',unit,'failures',[x for x in rows if x['returncode']],flush=True)
raise SystemExit(any(x['returncode'] for x in rows))
