"""Finite nice-15/load-admitted native, host, and S-replay repair acceptance."""
from pathlib import Path
import argparse, datetime, json, os, shutil, subprocess, sys, time
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');p.add_argument('--replays',action='store_true');a=p.parse_args()
C.setup();C.DATASET='model';out=C.LOCAL/'fix-r1';final=out/'final';queue=out/'queue.json';progress=out/'queue-progress.json'
def task(key,script,args,needs=()):return dict(id=key,script=str(script),args=list(map(str,args)),needs=list(needs),log=str(out/'logs'/(key+'.log')))
def fixture(profile):return final/'runs'/('fixed-'+profile+'-native')/'service-fixture/manifest.json'
def rank(t):
    key=t['id']
    if key.startswith('fast-ISA-smoke'):return 0
    if key.startswith('persistent-'):return 1
    if key.startswith('sweep-'):return 2
    if key in ('static','C-matrix','C-matrix-r2','byte-audit-r2','byte-audit-r3','byte-audit-r4','actual-service-ISA-r2') or key.startswith(('host-','service-','H52-')):return 3
    if key.startswith('ISA-'):return 4
    if 'session-' in key:return 5
    if key in ('prepare-S48','verify-S48') or 'replay-' in key:return 6
    return 7
if a.prepare:
    shutil.copyfile(C.HERE/'replay.py',final/'replay.py')
    shutil.copyfile(C.HERE/'reference_input.py',final/'reference_input.py')
    glyph=(C.HERE/'ui_text_evidence.py').read_text().replace('import accept_r2 as A',
        "from types import SimpleNamespace\nA=SimpleNamespace(read=lambda p:json.loads(Path(p).read_text()),EXPECTED={'test':json.loads(C.artifact('test')['manifest'].read_text())['dat_sha256']},DIR=C.LOCAL/'ui-text')")
    (final/'ui_text_evidence.py').write_text(glyph);(final/'ui-text').mkdir(exist_ok=True)
    tasks=[]
    tasks.append(task('fast-ISA-smoke',C.HERE/'fix_r1_isa_matrix.py',['--profile','test','--unit','mount','--backend','c','--smoke','--declared-services','--targets','HC+1,colour05','--fixture',fixture('test')]))
    for profile in ('test','release'):
        key='persistent-'+profile+'-native'
        tasks.append(task(key,final/'run.py',['--dataset','model','--version',profile,'--unit','mount','--backend','native','--label',key,'--action','menu','--fault','manual-persistent','--settings',final/'settings'/(profile+'-'+profile+'-mount-vivid09.bin')]))
    for profile in ('test','release'):
        for unit in C.UNITS:
            key='sweep-'+profile+'-'+unit+('-r2' if unit=='mount' else '')
            tasks.append(task(key,final/'run.py',['--dataset','model','--version',profile,'--unit',unit,'--backend','native','--label',key,'--action','sweep']))
    for profile in ('test','release'):
        for unit in C.UNITS:
            source='sweep-'+profile+'-'+unit+('-r2' if unit=='mount' else '');prep='prepare-reference-'+profile+'-'+unit;key='critical-'+profile+'-'+unit
            tasks.append(task(prep,final/'reference_input.py',['--dataset','model','--profile',profile,'--unit',unit,'--source-run',source],[source]))
            args=['--dataset','model','--version',profile,'--unit',unit,'--backend','reference','--reference-oracle','legacy','--label',key,'--action','menu','--settings',final/'reference-fixtures'/('model-'+profile+'-'+unit+'-S.bin')]
            if profile=='test':args+=['--expected',final/'reference-fixtures'/('model-'+profile+'-'+unit+'-expected552.bin')]
            tasks.append(task(key,final/'run.py',args,[prep]))
    tasks.append(task('glyph-diagnostic',final/'ui_text_evidence.py',['--run','fixed-test-reference','--name','diagnostic'],['fixed-test-reference']))
    tasks.append(task('glyph-normal',final/'ui_text_evidence.py',['--run','critical-test-mount','--name','normal'],['critical-test-mount']))
    tasks+=[task('C-matrix-r2',C.HERE/'fix_r1_c_matrix.py',[]),task('static',C.HERE/'static.py',['--dataset','model']),task('byte-audit-r4',C.HERE/'fix_r1_audit.py',[])]
    tasks.append(task('actual-service-ISA-r2',C.HERE/'fix_r1_isa_matrix.py',['--profile','test','--unit','mount','--backend','c','--smoke','--single-target','--label','r2','--fixture',fixture('test')]))
    for backend in ('c','python'):
        tasks.append(task('host-'+backend,C.HERE/'host_probe.py',['--backend',backend,'--dataset','model']))
        for profile in ('test','release'):
            tasks.append(task('service-'+profile+'-'+backend,C.HERE/'service_probe.py',['--backend',backend,'--profile',profile,'--dataset','model','--fixture',fixture(profile)]))
            tasks.append(task('H52-'+profile+'-'+backend,final/'shutter_probe.py',['--backend',backend,'--fixture',fixture(profile)]))
    # All W on HC+1 are mandatory in ISA, Acros/user use the same transaction
    # and are additionally checked in the C matrix and final native sweep.
    for profile in ('test','release'):
        for unit in C.UNITS:
            key='ISA-'+profile+'-'+unit
            tasks.append(task(key,C.HERE/'fix_r1_isa_matrix.py',['--profile',profile,'--unit',unit,'--backend','c','--fixture',fixture(profile),'--declared-services','--targets','HC+1,colour05']))
        tasks.append(task('ISA-'+profile+'-python',C.HERE/'fix_r1_isa_matrix.py',['--profile',profile,'--unit','mount','--backend','python','--fixture',fixture(profile),'--declared-services','--targets','HC+1,colour05']))
    # Prepared source captures must come from these new final DATs.
    subprocess.run([sys.executable,'-I','-B',str(final/'replay.py'),'--dataset','model','--tag','fix-r1','--sources'],check=True)
    directory=final/'persistence-fix-r1-model';sourcejobs=json.loads((directory/'sources.queue.json').read_text())
    for row in sourcejobs:tasks.append(task(row['label'],final/'run.py',row['args']))
    tasks.append(task('prepare-S48',Path(__file__),['--replays'],[r['label'] for r in sourcejobs]))
    C.save(queue,sorted(tasks,key=rank));print(json.dumps(dict(status='PREPARED',jobs=len(tasks))));sys.exit(0)
if a.replays:
    subprocess.run([sys.executable,'-I','-B',str(final/'replay.py'),'--dataset','model','--tag','fix-r1','--prepare-replays'],check=True)
    rows=json.loads((final/'persistence-fix-r1-model/replays.queue.json').read_text());tasks=json.loads(queue.read_text());known={t['id'] for t in tasks}
    for row in rows:
        if row['label'] not in known:tasks.append(task(row['label'],final/'run.py',row['args']))
    if 'verify-S48' not in known:tasks.append(task('verify-S48',final/'replay.py',['--dataset','model','--tag','fix-r1','--verify'],[r['label'] for r in rows]))
    C.save(queue,sorted(tasks,key=rank));print(json.dumps(dict(status='PREPARED',replays=len(rows))));sys.exit(0)
finished=json.loads(progress.read_text()).get('finished',{}) if progress.exists() else {};running={}
deadline=datetime.datetime.fromisoformat('2026-11-04T21:57:05+00:00').timestamp()
def externals():
    text=subprocess.check_output(['ps','-axo','pid=,state=,args='],text=True);rows=[]
    own={v[0].pid for v in running.values()}
    for line in text.splitlines():
        bits=line.strip().split(None,2)
        if len(bits)!=3:continue
        pid,state,args=bits
        if int(pid) in own or int(pid)==os.getpid() or 'T' in state:continue
        if ('Python -I -B research/g157/local/fix-r1/' in args and ('run.py ' in args or 'manual_' in args)) or 'Python -I -B research/g157/fix_r1_isa_matrix.py' in args:rows.append(int(pid))
    return rows
while time.time()<deadline:
    tasks=json.loads(queue.read_text())
    tasks=sorted(tasks,key=rank)
    for key in ('sweep-test-mount','sweep-release-mount','fixed-test-reference','fixed-release-reference'):
        path=final/'runs'/key/'result.json'
        if path.exists():
            doc=json.loads(path.read_text())
            if doc.get('status')=='OBSERVED':finished[key]=dict(returncode=0,external_receipt=str(path))
    for key,(child,t,stream) in list(running.items()):
        code=child.poll()
        if code is None:continue
        stream.close();del running[key];output=Path(t['log']).read_text()
        if code and 'LOAD_DEFERRED' in output:continue
        finished[key]=dict(returncode=code,log=t['log'],utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
        print(json.dumps(dict(task=key,returncode=code)),flush=True)
    load=os.getloadavg()[0];external=externals();cap=0 if load>10 else 2 if load>=5 else 6
    for t in tasks:
        if len(running)+len(external)>=cap:break
        key=t['id']
        if key in finished or key in running or any(finished.get(n,{}).get('returncode')!=0 for n in t.get('needs',[])):continue
        log=Path(t['log']);log.parent.mkdir(parents=True,exist_ok=True);stream=log.open('w')
        # A child inherits nice 15; never decreases it.
        child=subprocess.Popen([sys.executable,'-I','-B',t['script'],*t['args']],cwd=C.ROOT,stdout=stream,stderr=subprocess.STDOUT)
        running[key]=(child,t,stream)
        with (out/'queue-load.jsonl').open('a') as f:f.write(json.dumps(dict(task=key,pid=child.pid,load1=load,cap=cap,external=external,nice=os.getpriority(os.PRIO_PROCESS,0)))+'\n')
    C.save(progress,dict(finished=finished,running={k:v[0].pid for k,v in running.items()},external=external,load1=load,
        pending=[t['id'] for t in tasks if t['id'] not in finished and t['id'] not in running]))
    if not running and all(t['id'] in finished for t in tasks):break
    time.sleep(5)
stopped=[]
for key,(child,t,stream) in running.items():
    child.terminate()
    try:child.wait(timeout=5)
    except subprocess.TimeoutExpired:child.kill();child.wait()
    stream.close();stopped.append(dict(task=key,status='DEADLINE_OPEN'))
C.save(out/'queue-final.json',dict(finished=finished,stopped=stopped,deadline=time.time()>=deadline))
