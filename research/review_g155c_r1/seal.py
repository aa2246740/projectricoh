"""Remove only review-owned temporary files, then seal and verify final receipts."""
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C

assert (C.HERE/'REVIEW.md').is_file()
assert json.loads((C.HERE/'evidence/cross-backend.json').read_text())['status']=='PASS'
after=json.loads((C.HERE/'evidence/inputs-after-scoped.json').read_text())
assert after['status']=='PASS' and not after['product_or_tool_mismatches']
others=[]
for line in subprocess.check_output(['ps','-axo','pid=,command='],text=True).splitlines():
    fields=line.strip().split(None,1)
    if len(fields)!=2:continue
    parts=fields[1].split()
    if int(fields[0])!=__import__('os').getpid() and parts and Path(parts[0]).name.lower().startswith('python') and any('research/review_g155c_r1/' in x for x in parts[1:5]):
        others.append(line.strip())
assert not others,others
removed=[]
for path in sorted(C.TMP.rglob('*'),key=lambda p:len(p.parts),reverse=True):
    if path.is_file():
        removed.append(dict(path=str(path.relative_to(C.HERE)),bytes=path.stat().st_size))
        path.unlink()
    elif path.is_dir():
        path.rmdir()
C.TMP.rmdir()
C.save('cleanup',dict(status='PASS',ended_utc=datetime.now(timezone.utc).isoformat(),
                       original_start_utc='2026-11-03T10:22:44+00:00',deadline_utc='2026-11-03T12:52:44+00:00',
                       other_review_processes=others,removed_temporary_files=len(removed),
                       removed_temporary_bytes=sum(r['bytes'] for r in removed),
                       retained='Only scripts, receipts, report and small reference logs remain in this new directory.',
                       process_deviation='Three processes overlapped around one second. Excluded/repeated work is recorded explicitly.'))

# Start with the verified, frozen product/tool paths. Collect every explicit
# snapshot/checker receipt too, without treating a pathname as a checksum.
baseline=json.loads((C.HERE/'evidence/inputs-before.json').read_text())
entries={row['path']:row['sha256'] for row in baseline['files'] if row['path']!='decisions.tsv'}
def collect(value):
    if isinstance(value,dict):
        if isinstance(value.get('path'),str) and isinstance(value.get('sha256'),str):
            path=C.ROOT/value['path']
            if value['path']!='decisions.tsv' and path.is_file() and len(value['sha256'])==64:
                assert C.digest(path.read_bytes())==value['sha256'],str(path)
                entries[value['path']]=value['sha256']
        if isinstance(value.get('snapshot'),str) and isinstance(value.get('snapshot_sha256'),str):
            path=C.ROOT/value['snapshot']
            assert C.digest(path.read_bytes())==value['snapshot_sha256']
            entries[value['snapshot']]=value['snapshot_sha256']
        for item in value.values():collect(item)
    elif isinstance(value,list):
        for item in value:collect(item)
for path in (C.HERE/'evidence').glob('*.json'):
    collect(json.loads(path.read_text()))
for name in ('artifacts/firmware/gxr-1.51/ilaunch3','artifacts/firmware/gxr-1.51/jlaunch3',
             'artifacts/firmware/gxr-1.51/qlaunch3','artifacts/firmware/gxr-1.51/l08firm3',
             'tools/native_harness/product_execute.py','research/emulator_feasibility_r1/prototype/boot_probe.py'):
    row=C.file_info(C.ROOT/name)
    entries[row['path']]=row['sha256']
excluded={'SHA256SUMS','evidence/sums-verification.json'}
for path in C.HERE.rglob('*'):
    if path.is_file() and str(path.relative_to(C.HERE)) not in excluded:
        row=C.file_info(path)
        entries[row['path']]=row['sha256']
sums=C.HERE/'SHA256SUMS'
assert not sums.exists()
sums.write_text(''.join(digest+'  '+name+'\n' for name,digest in sorted(entries.items())))
mismatches=[]
for name,digest in entries.items():
    if C.digest((C.ROOT/name).read_bytes())!=digest:
        mismatches.append(name)
C.save('sums-verification',dict(status='PASS' if not mismatches else 'FAIL',entries=len(entries),
                               SHA256SUMS_sha256=C.digest(sums.read_bytes()),mismatches=mismatches,
                               excluded_from_checksums=sorted(excluded),paths_relative_to_repository=True))
assert not mismatches
