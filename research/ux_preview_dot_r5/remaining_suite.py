"""Run the remaining complete reviewed regression groups for one final unit."""
from pathlib import Path
import sys,subprocess
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import ROOT,OUT,save
unit=sys.argv[1]
resume=sys.argv[2] if len(sys.argv)>2 else None
commands=[]
commands += [('fn2-open','entry_switch.py',[unit,'fn2','--at','1'])]
commands += [('early-'+str(at),'failure_boundaries.py',[unit,str(at)]) for at in (1,6,7)]
commands += [(group,'run_native.py',[group,unit]) for group in ('ah','exits','persistent')]
commands += [('confirm','confirm_paths.py',[unit]),('latch','latch_paths.py',[unit])]
commands += [('h08-'+str(at),'concurrent_menu.py',['other_menu',unit,'--at',str(at),'--reopen-fn2']) for at in (1,6,16,17,140)]
commands += [(group,'concurrent_menu.py',[group,unit]) for group in ('recovery','fallback','nested')]
commands += [('ui-'+point,'ui_cutpoints.py',[point,unit]) for point in ('redraw','cache')]
commands += [('coalescing-'+str(at),'coalescing.py',['120',unit,'--at',str(at)]) for at in (1,16)]
rows=[]
prior=OUT/('remaining-suite-'+unit+'.json')
if resume and prior.exists():rows=[r for r in __import__('json').loads(prior.read_text())['commands'] if r['returncode']==0]
started=not bool(resume)
for label,script,extra in commands:
 if not started and label==resume:started=True
 if not started:continue
 full='final-'+unit+'-'+label+('-resumed' if resume else '')
 command=['/usr/bin/python3','-I','-B',str(OUT/'run_recorded.py'),full,'/usr/bin/python3','-I','-B',str(OUT/script),*extra]
 print('BEGIN',full,flush=True)
 code=subprocess.call(command,cwd=ROOT)
 rows.append(dict(label=label,script=script,args=extra,returncode=code))
 save('remaining-suite-'+unit+'.json',dict(status='RUNNING' if not code else 'FAIL',unit=unit,commands=rows))
 if code:raise SystemExit(code)
save('remaining-suite-'+unit+'.json',dict(status='PASS',unit=unit,commands=rows))
print('PASS remaining reviewed regression',unit,len(rows),'groups',flush=True)
