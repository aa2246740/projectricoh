"""Expand finite acceptance jobs after linked artifacts and drivers exist."""
from pathlib import Path
import json,sys
sys.path.insert(0,str(Path(__file__).resolve().parent));import common as C
C.setup();C.DATASET='model';C.compute_gate('prepare-finite-jobs')
path=C.HERE/'jobs.json';jobs=json.loads(path.read_text());known={r['id'] for r in jobs}
def add(key,script,args,needs=()):
    if key not in known:
        jobs.append(dict(id=key,script='research/g158/'+script,args=list(map(str,args)),needs=list(needs),log=str(C.LOCAL/'logs'/(key+'.log'))));known.add(key)
def main(key,profile='test',unit='mount',dial='AUTO',action='menu',backend='native',extra=(),needs=()):
    args=['--dataset','model','--version',profile,'--unit',unit,'--backend',backend,'--label',key,'--action',action,'--dial',dial,*extra]
    if backend=='reference':args+=['--reference-oracle','legacy']
    add(key,'run.py',args,['static','acceptance-prepare-r2',*needs])
for p in ('test','release'):
    main('fixture-'+p+'-AUTO',profile=p,extra=['--settings',C.LOCAL/'settings'/(p+'-mount-Acros.bin')])
for p in ('test','release'):
    for unit in C.UNITS:main('sweep-'+p+'-'+unit,profile=p,unit=unit,action='sweep')
for dial,name in (('P','Acros'),('A','HC1'),('M','LowSat'),('S','Acros')):
    expected=C.LOCAL/'settings'/('test-mount-'+name+('.record552' if name=='HC1' else '.expected552'))
    main('field-'+dial+'-native',dial=dial,extra=['--settings',C.LOCAL/'settings'/('test-mount-'+name+'.bin'),'--expected',expected])
for key,extra in [('SCENE-domain',['--raw-mode','1','--submode','0','--selection','0x8001']),('MY-domain',['--my','1']),('unknown-submode',['--raw-mode','4','--submode','255','--selection','0x8001'])]:
    main(key,extra=['--settings',C.LOCAL/'settings/test-mount-Acros.bin',*extra])
for p in ('test','release'):
    main('reject-g157-'+p,profile=p,extra=['--settings',C.LOCAL/'settings'/(p+'-mount-old-g157.bin')])
for backend in ('c','python'):
    add('host-'+backend,'host_probe.py',['--dataset','model','--backend',backend],['static'])
    for p in ('test','release'):
        add('op5-'+p+'-'+backend,'service_probe.py',['--dataset','model','--profile',p,'--backend',backend,'--fixture',C.LOCAL/'runs'/('fixture-'+p+'-AUTO')/'service-fixture/manifest.json'],['fixture-'+p+'-AUTO'])
sources=C.LOCAL/'persistence-r1-model/sources.queue.json'
if not sources.exists():
    C.run([sys.executable,'-I','-B',C.HERE/'replay.py','--dataset','model','--tag','r1','--sources'],'prepare-S-sources')
for row in json.loads(sources.read_text()):
    add(row['label'],'run.py',[*row['args'],'--dial','AUTO'],['static'])
add('prepare-S48','replay_plan.py',[],[r['label'] for r in json.loads(sources.read_text())])
C.save(path,jobs);print(json.dumps(dict(status='PREPARED',jobs=len(jobs))))
