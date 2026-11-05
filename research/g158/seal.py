"""Seal the concrete handoff, including truthful OPEN and interrupted evidence."""
from pathlib import Path
import datetime,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parent));import common as C
C.setup();C.DATASET='model';out=C.LOCAL
final=json.loads((out/'FINAL.json').read_text());assert final['final']
paths={out/'FINAL.json',out/'EVIDENCE.md',out/'freeze.json',C.HERE/'REPORT.md',C.HERE/'OWNER_STEPS.md',C.ENGINE/'README.md'}
paths.update(C.HERE.glob('*.py'))
paths.add(C.HERE/'jobs.json')
for pattern in ('byte-audit-*.json','byte-audit-*.tsv','audit-summary.json','C-matrix-*.json','BOOT-C-matrix.json','gate/result.json','ISA-full-interrupted.json','*-interruption.json','fast-isa/*-PASM*.json','fast-isa/*-PASM*-driver.py','runs/*/result.json','runs/*/driver.py','runs/*/common.py','runs/*/service-fixture/manifest.json','runs/*/ui-*.json','persistence-r1-model/*.json','settings/manifest.json','queue-*.json','queue-load.jsonl','commands.jsonl','load.jsonl'):
    paths.update(out.glob(pattern))
paths.update(C.receipt(n) for n in ('static.json','host-c.json','host-python.json','service-test-c.json','service-release-c.json','service-test-python.json','service-release-python.json'))
packages=[]
for profile,root in C.PACKAGES.items():
    m=json.loads((root/'MANIFEST').read_text());expected=final['DAT'][profile]
    assert m['dat_sha256']==expected and m['verdict']==final['verdict']
    for p in (root/'local/GXRCE.DAT',root/'local/SD_ROOT/GXRCE.DAT',C.artifact(profile)['dat']):assert C.sha(p.read_bytes())==expected and p.stat().st_size==m['dat_bytes'];paths.add(p)
    paths.update(root/n for n in ('README.md','MANIFEST','SHA256SUMS'));paths.add(C.artifact(profile)['build']/'size.json')
    size=json.loads((C.artifact(profile)['build']/'size.json').read_text())
    for name,digest in {**size['sources'],**size['headers']}.items():
        path=C.ROOT/name;assert C.sha(path.read_bytes())==digest, 'source changed since link: '+name;paths.add(path)
    packages.append({k:m[k] for k in ('profile','dat_sha256','dat_bytes','code_bytes','main_request','main_headroom')})
rows=[]
for p in sorted(paths):
    if p.is_file():rows.append(dict(path=str(p.relative_to(C.ROOT)),bytes=p.stat().st_size,sha256=C.sha(p.read_bytes())))
doc=dict(verdict=final['verdict'],utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),packages=packages,passed=sum(x['status']=='PASS' for x in final['checks']),required=len(final['checks']),OPEN=final['OPEN'],files=rows,scope='Implementation evidence and preserved limitations; not independent review, physical camera, JPEG or pixel acceptance.')
C.save(out/'SEAL.json',doc);rows.append(dict(path=str((out/'SEAL.json').relative_to(C.ROOT)),sha256=C.sha((out/'SEAL.json').read_bytes())))
(out/'SHA256SUMS').write_text(''.join(x['sha256']+'  '+x['path']+'\n' for x in rows))
print(json.dumps(dict(verdict=doc['verdict'],files=len(rows),passed=doc['passed'],required=doc['required'],packages=packages)))
