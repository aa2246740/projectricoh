#!/usr/bin/python3
"""Check frozen inputs, remove only the assigned temp tree, and hash delivery."""
import datetime,hashlib,json,re,shutil
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
TEMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-body-reclaim-r2')
assert HERE==ROOT/'research/review_body_reclaim_r2'
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
accepted_change=json.loads((HERE/'local/input-change-check.json').read_text())
shared_log_appends=[]
def unchanged(files,base=ROOT):
    changed=[];accepted=0
    for name,value in files.items():
        path=base/name
        if path.is_file() and digest(path)==value:continue
        if name=='decisions.tsv' and path.is_file():
            raw=path.read_bytes();prefix_bytes=accepted_change['initial_decisions_bytes']
            assert digest(path)==accepted_change['current_decisions_sha256']
            assert hashlib.sha256(raw[:prefix_bytes]).hexdigest()==value
            shared_log_appends.append(dict(file=name,before=value,after=digest(path),initial_lines_preserved=803,
                                           appended_lines=1,classification='Unrelated Studio review record appended to the shared log.'))
            accepted+=1
        else:changed.append(name)
    assert not changed,changed
    return dict(unchanged=len(files)-accepted,shared_log_append=accepted)
initial=json.loads((HERE/'inputs-before.json').read_text())
extra=json.loads((HERE/'inputs-extra.json').read_text())
history=json.loads((HERE/'historical-inputs.json').read_text())
tools=json.loads((HERE/'local/tools-used.json').read_text())
counts=dict(initial=unchanged(initial['files']),extra=unchanged(extra),historical=unchanged(history['files']),tools=unchanged(tools['files']))
assert digest(Path(history['archive']['path']))==history['archive']['sha256']
manifest=[]
for line in (ROOT/'research/body_next_steps/SHA256SUMS').read_text().splitlines():
    value,name=line.split(None,1);name=name.strip()
    assert digest(ROOT/name)==value,name
    manifest.append(name)
assert len(manifest)==37
workloads=[json.loads(line) for line in (HERE/'local/workloads.jsonl').read_text().splitlines()]
required=['rebuild2','host-original','layout-compile','layout','replay-original','host-boundaries',
          'previous-counterexamples','static-audit','machine-boundaries3','inline-comparison','discard-inline-comparison']
for name in required:
    row=next(r for r in workloads if r['name']==name)
    assert row['returncode']==0 and row['timeout_seconds']>=3*row['elapsed_seconds'],row
assert len((HERE/'local/host-original.jsonl').read_text().splitlines())==38
assert len(json.loads((HERE/'local/replay-original.json').read_text())['cases'])==14
machine=json.loads((HERE/'local/machine-boundaries.json').read_text())
assert len(machine['arguments'])==15 and len(machine['disabled'])==18
assert json.loads((HERE/'local/inline-result.json').read_text())['comparisons']==132
assert json.loads((HERE/'local/discard-inline-result.json').read_text())['comparisons']==3
binary=HERE/'local/rebuild/v/r7/build/resident.bin'
assert binary.stat().st_size==8040 and digest(binary)=='a6cd3c09c48efd3c08be02278fc0c5074a8aa6232ac63437340a745680360ae1'
text=(HERE/'REVIEW.md').read_text()
assert text.splitlines()[0]=='可以实现'
assert not TEMP.is_symlink() and TEMP.parent==Path('/Volumes/Workspace/Scratch/tmp/projectricoh')
temp_files=list(p for p in TEMP.rglob('*') if p.is_file()) if TEMP.exists() else []
temp_count=len(temp_files);temp_bytes=sum(p.stat().st_size for p in temp_files)
if TEMP.exists():shutil.rmtree(TEMP)
assert not TEMP.exists()
receipt=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
             unchanged_inputs=counts,original_manifest_items_verified=37,archive_unchanged=True,
             shared_log_append=shared_log_appends,
             required_workloads_passed=required,initial_failure_logs_retained=[r['log'] for r in workloads if r['returncode']],
             temporary_path=str(TEMP),temporary_files_removed=temp_count,temporary_bytes_removed=temp_bytes,
             temporary_path_absent=True,write_fence='read_scope.sb',
             scope='Review outputs only; no camera/card access, network, Git writes, subagents or body-image generation.',
             verdict='可以实现',r7_sha256=digest(binary))
(HERE/'cleanup.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
for target in re.findall(r'\]\(([^)]+)\)',text):assert (HERE/target.split('#',1)[0]).exists(),target
files=sorted(p for p in HERE.rglob('*') if p.is_file() and p.name!='SHA256SUMS')
assert all(not p.is_symlink() for p in files)
lines=[digest(p)+'  '+str(p.relative_to(ROOT)) for p in files]
(HERE/'SHA256SUMS').write_text('\n'.join(lines)+'\n')
for line in lines:
    value,name=line.split(None,1);assert digest(ROOT/name.strip())==value
print(json.dumps(dict(verdict=receipt['verdict'],unchanged_inputs=counts,manifest_files=len(lines),
                      temporary_path_absent=True,report_sha256=digest(HERE/'REVIEW.md')),ensure_ascii=False,indent=2))
