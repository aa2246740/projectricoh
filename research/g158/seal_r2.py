"""Seal acceptance evidence and verify the immutable product identities."""
from pathlib import Path
import datetime,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parent));import common as C
C.setup();C.DATASET='model';out=C.LOCAL/'accept-r2'
final=json.loads((out/'FINAL.json').read_text());freeze=json.loads((out/'freeze.json').read_text())
assert final['final'] and final['DAT']==freeze['DAT']
queue=json.loads((out/'queue-final.json').read_text())
schedule=json.loads((out/'loadgate-transition/verification.json').read_text())
assert schedule['status']=='PASS' and not schedule['precision_changed']
assert schedule['loadgate_sha256']==C.sha((C.ROOT/'tools/loadgate.py').read_bytes())
progress=json.loads((out/'progress.json').read_text())
assert not progress['running'] and not progress['pending']
if not final['OPEN']:assert not queue['stopped']
paths={C.HERE/'REPORT.md',C.HERE/'OWNER_STEPS.md',C.HERE/'SLOT31.md',C.ENGINE/'README.md',C.LOCAL/'FINAL.json'}
paths.update(C.HERE.glob('*.py'))
paths.add(C.ROOT/'tools/native_harness/product_execute.py')
paths.add(C.ROOT/'tools/loadgate.py')
for model in ('strict_r4','fix_r1'):
    paths.update((C.ROOT/'tools/gxr_emulator_fast'/model).glob('*.py'))
for p in out.rglob('*'):
    if p.is_file() and p not in (out/'SEAL.json',out/'SHA256SUMS') and not p.name.endswith('.tmp'):paths.add(p)
for row in freeze['files']:
    p=out/'previous'/row['path'];assert C.sha(p.read_bytes())==row['sha256'],'previous evidence changed: '+row['path']
for pattern in ('byte-audit-*.json','byte-audit-*.tsv','audit-summary.json','C-matrix-*.json','BOOT-C-matrix.json','gate/result.json','ISA-full-interrupted.json','fast-isa/*-PASM*.json','fast-isa/*-driver.py','acceptance/model/*.json','persistence-r1-model/*.json','persistence-r1-model/*.bin','settings/*','runs/*/result.json','runs/*/driver.py','runs/*/common.py','runs/*/ui-*.json','runs/*/exposure-trace.json','runs/*/boundary-S.bin','runs/*/cold-S.bin','runs/*/final-S.bin','runs/*/service-fixture/*'):
    paths.update(p for p in C.LOCAL.glob(pattern) if p.is_file())
packages=[]
for profile,root in C.PACKAGES.items():
    m=json.loads((root/'MANIFEST').read_text());digest=freeze['DAT'][profile]
    assert m['dat_sha256']==digest and m['verdict']==final['verdict']
    for p in (C.artifact(profile)['dat'],root/'local/GXRCE.DAT',root/'local/SD_ROOT/GXRCE.DAT'):
        assert C.sha(p.read_bytes())==digest and p.stat().st_size==m['dat_bytes'];paths.add(p)
    paths.update(root/n for n in ('MANIFEST','README.md','SHA256SUMS'))
    sizepath=C.artifact(profile)['build']/'size.json';paths.add(sizepath);size=json.loads(sizepath.read_text())
    for name,digest in {**size['sources'],**size['headers']}.items():
        p=C.ROOT/name;assert C.sha(p.read_bytes())==digest,'linked source changed: '+name;paths.add(p)
    packages.append({k:m[k] for k in ('profile','dat_sha256','dat_bytes','code_bytes','main_request','main_headroom')})
rows=[dict(path=str(p.relative_to(C.ROOT)),bytes=p.stat().st_size,sha256=C.sha(p.read_bytes())) for p in sorted(paths)]
doc=dict(verdict=final['verdict'],utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),packages=packages,OPEN=final['OPEN'],model_boundaries=final['model_boundaries'],supplemental_OPEN=final['supplemental_OPEN'],queue_stopped=queue['stopped'],schedule_verification='local/accept-r2/loadgate-transition/verification.json',files=rows,product_changed=False,device_response_added=False,scope='Software acceptance with explicit model/field boundaries. No physical camera, NAND, first JPEG or pixel acceptance is implied.')
C.save(out/'SEAL.json',doc)
rows.append(dict(path=str((out/'SEAL.json').relative_to(C.ROOT)),sha256=C.sha((out/'SEAL.json').read_bytes())))
(out/'SHA256SUMS').write_text(''.join(row['sha256']+'  '+row['path']+'\n' for row in rows))
print(json.dumps(dict(verdict=doc['verdict'],files=len(rows),OPEN=doc['OPEN'],model_boundaries=doc['model_boundaries'],packages=packages),ensure_ascii=False))
