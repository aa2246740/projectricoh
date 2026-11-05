"""Freeze the accepted DATs and plan only missing cold-run evidence."""
from pathlib import Path
import datetime,json,shutil,sys
sys.path.insert(0,str(Path(__file__).resolve().parent));import common as C
C.setup();C.DATASET='model';out=C.LOCAL/'accept-r2';out.mkdir(exist_ok=False)
previous=out/'previous';previous.mkdir()
pins={'test':'6a40262c3fc5b94e7152012c655f5c7d2dc98bf6186cf3e80d2429b76f45fcee','release':'756d5840da9d0393f29411a4f8f61c7e2bb88fb546c814b316982ca8c7cb24f6'}
frozen=[]
paths=list(C.HERE.glob('*.py'))+[C.HERE/'REPORT.md',C.HERE/'OWNER_STEPS.md',C.HERE/'jobs.json']
paths += [C.LOCAL/n for n in ('FINAL.json','SEAL.json','SHA256SUMS','queue-closeout.json','persistence-r1-model/inputs.json','persistence-r1-model/verification-partial.json')]
for profile,root in C.PACKAGES.items():
    for path in (C.artifact(profile)['dat'],root/'local/GXRCE.DAT',root/'local/SD_ROOT/GXRCE.DAT'):
        assert C.sha(path.read_bytes())==pins[profile]
    size=json.loads((C.artifact(profile)['build']/'size.json').read_text())
    for name,digest in {**size['sources'],**size['headers']}.items():assert C.sha((C.ROOT/name).read_bytes())==digest
    paths += [root/n for n in ('MANIFEST','README.md','SHA256SUMS')]
for path in paths:
    target=previous/path.relative_to(C.ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
    frozen.append(dict(path=str(path.relative_to(C.ROOT)),sha256=C.sha(path.read_bytes())))
C.save(out/'freeze.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),DAT=pins,files=frozen,deadline='2026-11-05T08:03:27+00:00',product_code_unchanged=True))
old=json.loads((C.HERE/'jobs.json').read_text());byid={r['id']:r for r in old};jobs=[];aliases={}
def add(oldid,newid):
    row=dict(byid[oldid]);row['args']=list(row['args']);i=row['args'].index('--label')+1;row['args'][i]=newid
    row.update(id=newid,needs=[],log=str(out/'logs'/(newid+'.log')))
    jobs.append(row);aliases[oldid]=newid
jobs.append(dict(id='r2-slot31-static',script='research/g158/slot31_static.py',args=[],needs=[],log=str(out/'logs/slot31-static.log')))
for oldid in ('sweep-test-28mm','sweep-test-mount','sweep-release-50mm','sweep-release-28mm','sweep-release-mount','reference-P1-test-AUTO','reference-P1-release-AUTO'):
    add(oldid,'r2-'+oldid)
directory=C.LOCAL/'persistence-r1-model';inputs=json.loads((directory/'inputs.json').read_text());queue={r['label']:r for r in json.loads((directory/'replays.queue.json').read_text())}
for row in inputs:
    result=C.LOCAL/'runs'/row['label']/'result.json';doc=json.loads(result.read_text()) if result.exists() else None
    if doc and doc['status']=='OBSERVED':continue
    original=row['label'];label='r2-'+original;job=dict(queue[original]);args=list(job['args']);args[args.index('--label')+1]=label
    jobs.append(dict(id=label,script='research/g158/run.py',args=args,needs=[],log=str(out/'logs'/(label+'.log'))))
    row.update(label=label,previous_label=original)
C.save(directory/'inputs.json',inputs)
for oldid in ('critical-release-50mm-P','critical-release-28mm-P','reference-field-P'):
    add(oldid,'r2-'+oldid)
C.save(out/'aliases.json',aliases);C.save(out/'jobs.json',jobs)
print(json.dumps(dict(status='FROZEN_AND_PLANNED',DAT=pins,jobs=len(jobs))))
