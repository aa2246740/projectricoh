"""Preserve the reviewed g157 bytes and exact counterexample before P1 repair."""
from pathlib import Path
import json
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
C.setup();C.compute_gate('fix-r1-freeze')
out=C.LOCAL/'fix-r1';out.mkdir(exist_ok=True);before=out/'before';before.mkdir(exist_ok=True)
expected={'test':'3478b9954c122142a0711ff07cc7251a50abb442f7069cc2c558d1ca61f882a3','release':'488943d2a3b0303cc5cbec6d3c85a96e539fd19a71c3596968c40cda619dbf88'}
files=[]
for profile in expected:
    a=C.artifact(profile,'model');dest=before/profile
    if not dest.exists():
        shutil.copytree(a['build'],dest/'build')
        shutil.copyfile(a['dat'],dest/'GXRCE.DAT');shutil.copyfile(a['manifest'],dest/'MANIFEST')
        shutil.copyfile(a['records'],dest/'records.json')
    raw=(dest/'GXRCE.DAT').read_bytes();assert C.sha(raw)==expected[profile]
    files.append(dict(profile=profile,sha256=C.sha(raw),bytes=len(raw)))
sources={}
for p in C.PRODUCT.rglob('*'):
    if p.is_file() and p.suffix in ('.c','.h','.py','.S','.ld') and 'local' not in p.relative_to(C.PRODUCT).parts:
        rel=p.relative_to(C.PRODUCT);q=before/'source'/rel
        if not q.exists():q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
        sources[str(rel)]=C.sha(q.read_bytes())
for name in ('REPORT.md','local/layout.json','local/engine-freeze.json'):
    source=C.HERE/name;dest=before/Path(name).name
    if not dest.exists():shutil.copyfile(source,dest)
shutil.copyfile(C.LOCAL/'layout.json',out/'layout.json')
review=C.ROOT/'research/review_g157_r1/local'
if not (out/'settings').exists():shutil.copytree(review/'settings',out/'settings')
for name in ('manual_true_once_run.py','manual_standby_run.py'):
    target=out/name
    if not target.exists():shutil.copyfile(review/name,target)
text=(review/'common.py').read_text()
text=text.replace("LOCAL=ROOT/'research/review_g157_r1/local'","LOCAL=ROOT/'research/g157/local/fix-r1'")
start=text.index('def artifact(profile,dataset=None):');end=text.index('\ndef receipt',start)
text=text[:start]+'''def artifact(profile,dataset=None):
    old=LOCAL/'before'/profile
    return dict(dat=old/'GXRCE.DAT',manifest=old/'MANIFEST',build=old/'build',records=old/'records.json')
'''+text[end:]
text=text.replace("target.is_relative_to(LOCAL)","target.is_relative_to(LOCAL)")
(out/'common.py').write_text(text)
(out/'tmp').mkdir(exist_ok=True)
C.save(out/'freeze.json',dict(status='PASS',files=files,source_sha256=sources,deadline_utc='2026-11-04T21:57:05+00:00'))
report=C.HERE/'REPORT.md';content=report.read_text();lines=content.splitlines();lines[0]='有缺陷';report.write_text('\n'.join(lines)+'\n')
print(json.dumps(dict(status='PASS',old_DAT=files,source_files=len(sources))))
