"""Seal all review files, check links and vocabulary, then verify every hash."""
from pathlib import Path
import hashlib
import json
import re
import sys
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import ROOT,OUT,save,file_sha
from neutral_terms import pattern

def read(name):return json.loads((OUT/name).read_text())
assert (OUT/'REVIEW.md').read_text().splitlines()[0]=='不可以上卡。'
assert read('acceptance.json')['status']=='REVIEW_COMPLETE_WITH_FINDINGS'
assert read('input-integrity.json')['ok'] and read('runtime-input-integrity.json')['ok']
assert read('codegen-baseline-chain.json')['status']=='PASS_BASELINE_BOUND'
baseline_queue=read('baseline-scope-queue.json')
assert len(baseline_queue)==3 and all(x['returncode']==0 for x in baseline_queue)
for unit in ('50mm','28mm','mount'):
    queue=read('queue-'+unit+'.json')
    assert len(queue)==17 and all(x['returncode']==0 for x in queue),(unit,queue)
    ui_queue=read('ui-scope-queue-'+unit+'.json')
    assert len(ui_queue)==11 and all(x['returncode']==0 for x in ui_queue),(unit,ui_queue)
manifest=OUT/'SHA256SUMS'
manifest.write_text('')
save('checksum-selfcheck.json',dict(status='CHECKING'))
save('report-validation.json',dict(status='CHECKING'))
files=sorted(p for p in OUT.rglob('*') if p.is_file() and p!=manifest)
bad=[];text_count=0
for p in files:
    if pattern.search(p.name):bad.append(str(p.relative_to(OUT)).encode().hex())
    try:s=p.read_text()
    except (UnicodeDecodeError,ValueError):continue
    text_count+=1
    if pattern.search(s):bad.append(str(p.relative_to(OUT)).encode().hex())
assert not bad,'Neutral vocabulary check did not pass.'
links=[];missing=[]
report=(OUT/'REVIEW.md').read_text()
for target in re.findall(r'\]\(([^)]+)\)',report):
    if target.startswith(('http:','https:')):continue
    p=(OUT/target).resolve();links.append(target)
    if not p.is_file():missing.append(target)
assert not missing,missing
save('report-validation.json',dict(status='PASS',links=len(links),missing=[],neutral_text_files=text_count))
save('checksum-selfcheck.json',dict(status='PASS',files=len(files),ok=len(files),failed=[],
    includes_every_regular_file_except_manifest=True,algorithm='SHA-256',
    procedure='The seal script writes the manifest, reopens every listed file and verifies every digest; failure prevents successful exit.',
    completed_utc=datetime.now(timezone.utc).isoformat()))
files=sorted(p for p in OUT.rglob('*') if p.is_file() and p!=manifest)
assert len(files)==read('checksum-selfcheck.json')['files']
manifest.write_text(''.join(file_sha(p)+'  '+p.relative_to(OUT).as_posix()+'\n' for p in files))
fail=[];checked=0
for line in manifest.read_text().splitlines():
    digest,name=line.split('  ',1);checked+=1
    if file_sha(OUT/name)!=digest:fail.append(name)
assert not fail,fail
assert checked==len(files)
actual={p.relative_to(OUT).as_posix() for p in OUT.rglob('*') if p.is_file() and p!=manifest}
listed={line.split('  ',1)[1] for line in manifest.read_text().splitlines()}
assert actual==listed
print('SHA256SUMS',checked,'/',checked,'OK; all files covered; report links',len(links),'OK; neutral vocabulary OK',flush=True)
