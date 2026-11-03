"""Run every requested ASan/UBSan stage and preserve actual stdout/stderr."""
from pathlib import Path
import json,subprocess,sys,os,time
HERE=Path(__file__).resolve().parent;ROOT=Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
C=HERE/'isolated/candidate';OUT=HERE/'runs';LOG=OUT/'host-stages';LOG.mkdir(exist_ok=True)
STAGES=('vectors','basic','first','blackbox','neighbour','t','iso','ctl','rpc-faults','conflict','accepted-f02','same-conflict','log-fault','service-quarantine','publish-failure','store-fault','daily','rejected','r33','quarantine','irom','legacy')
env=dict(os.environ,TMPDIR=str(C/'local/tmp'),PYTHONDONTWRITEBYTECODE='1',ASAN_OPTIONS='detect_leaks=0:halt_on_error=1',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
results=[]
def run(name,args):
 start=time.monotonic();p=subprocess.run([str(a) for a in args],cwd=ROOT,env=env,capture_output=True,text=True,timeout=600)
 (LOG/(name+'.stdout')).write_text(p.stdout);(LOG/(name+'.stderr')).write_text(p.stderr)
 row=dict(stage=name,argv=[str(a) for a in args],returncode=p.returncode,seconds=round(time.monotonic()-start,3),stdout=p.stdout,stderr=p.stderr)
 results.append(row);(OUT/'host-stages.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
 print(name,'PASS' if p.returncode==0 else 'FAIL',p.stdout.strip(),p.stderr[-1800:] if p.returncode else '',flush=True)
for phase in STAGES:run(phase,['/usr/bin/python3','-I','-B',C/'verify_v34c.py',phase])
run('history',['/usr/bin/python3','-I','-B',C/'verify_history34c.py'])
for unit in range(3):run('gen117-'+str(unit),[C/'local/v34c-host/host','gen117',unit,C/'local/full-r13/GXRCE.DAT',C/'local/full-r13/trust.bin',C/'local/full-r13/effective-rows.bin',ROOT/'firmware/engine_v36_r28/candidate/local/full-r13/GXRCE.DAT','0'])
failed=[r['stage'] for r in results if r['returncode']]
print('HOST_RESULT','FAIL' if failed else 'PASS','stages=22 extra=history+three_units','failed=',failed,flush=True)
sys.exit(bool(failed))
