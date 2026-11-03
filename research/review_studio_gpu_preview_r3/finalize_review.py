"""Check report evidence, write SHA256SUMS, and verify the final bytes."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent
report = (OUT/'REVIEW.md').read_text()
assert report.splitlines()[0] == '不能合并'
assert report.splitlines()[2].startswith('| 核实项目 |')
for word in ('attack','exploit','inject','bypass','hijack','payload','adversarial','malicious','注入','绕过','旁路','攻击','劫持','接管','恶意','外来','对抗'):
    assert word not in report.lower(), word
missing=[]
for target in re.findall(r'\]\(([^)]+)\)',report):
    if target.startswith(('https://','http://')):continue
    path = re.sub(r':\d+$','',target)
    full = Path(path) if path.startswith('/') else OUT/path
    if full == OUT/'SHA256SUMS':continue
    if not full.exists():missing.append(str(full))
assert not missing, missing
stable = json.loads((OUT/'source-stability.json').read_text())
assert stable['tracked_sources_unchanged'] and stable['tested_copy_sources_unchanged'] and stable['git_status']==''
before=json.loads((OUT/'source-before.json').read_text())
after=json.loads((OUT/'source-after.json').read_text())
assert before==after and len(before)==306
wt=Path('/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview')
assert all(hashlib.sha256((wt/name).read_bytes()).hexdigest()==digest for name,digest in before.items())
assert subprocess.check_output(['git','status','--short','--untracked-files=all'],cwd=wt,env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'},text=True)==''
cleanup=json.loads((OUT/'cleanup.json').read_text())
assert cleanup['temporary_root_removed'] and not Path(cleanup['temporary_root']).exists()
assert cleanup['browser_starts']==cleanup['browser_normal_closes']==2
assert cleanup['owned_browser_processes_remaining']==[] and cleanup['listeners_remaining']==''
s=ET.parse(OUT/'make-check.xml').getroot().find('testsuite')
assert {k:s.attrib[k] for k in ('tests','errors','failures','skipped')} == {'tests':'1704','errors':'0','failures':'0','skipped':'697'}
assert not any(c.find('rerunFailure') is not None for c in s.findall('testcase'))
receipt=json.loads((OUT/'make-check-final-receipt.json').read_text())
assert receipt['exit_code']==0 and receipt['nice']==10 and receipt['elapsed_seconds']<1800
for case in ('media_root_race','path_delete_race','card_reader_retarget','lut_reimport_probe','http_boundary_extra'):
    replay=json.loads((OUT/'r2-replay'/(case+'-input.json')).read_text())
    assert hashlib.sha256(Path(replay['original']).read_bytes()).hexdigest()==replay['original_sha256']
    assert hashlib.sha256((OUT/'r2-replay'/(case+'.py')).read_bytes()).hexdigest()==replay['replay_sha256']
push=json.loads((OUT/'ci-push-run-valid.log').read_text())
pr=json.loads((OUT/'ci-pr-run.log').read_text())
for run in (push,pr):assert run['headSha']==stable['head']
windows=lambda run:next(j for j in run['jobs'] if j['name']=='tests (windows-latest)')
assert windows(push)['conclusion']=='failure' and windows(pr)['conclusion']=='cancelled'
assert any('exceeded the maximum execution time of 40m0s' in a['message'] for a in json.loads((OUT/'ci-pr-windows-annotations.log').read_text()))
extra=json.loads((OUT/'extra-boundaries.json').read_text())
assert extra['ordinary_import_parent_change']['read_other_directory'] and extra['final_fd_growth']==0
selfcheck=json.loads((OUT/'independent-selfcheck-receipt.json').read_text())
assert selfcheck['exit_code']==0 and not selfcheck['tracked_sources_changed']
check={'verdict':'不能合并','p1':2,'p2':1,'head':stable['head'],'sources_unchanged':True,
       'report_links_valid':True,'wording_check_passed':True,'passed':1007,'skipped':697,
       'automatic_rerun_markers':0,'cleanup_complete':True,'independent_reproduction_selfcheck':True,
       'actual_sources_checked_after_cleanup':True,
       'windows_push':'failure','windows_pr':'40m timeout'}
(OUT/'delivery-check.json').write_text(json.dumps(check,indent=2,ensure_ascii=False)+'\n')
paths=sorted(p for p in OUT.rglob('*') if p.is_file() and p.name!='SHA256SUMS')
manifest=''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(OUT))+'\n' for p in paths)
(OUT/'SHA256SUMS').write_text(manifest)
for line in (OUT/'SHA256SUMS').read_text().splitlines():
    digest,name=line.split('  ',1)
    assert hashlib.sha256((OUT/name).read_bytes()).hexdigest()==digest,name
print(json.dumps({**check,'checksum_files_verified':len(paths),'report_sha256':hashlib.sha256((OUT/'REVIEW.md').read_bytes()).hexdigest(),'sums_sha256':hashlib.sha256((OUT/'SHA256SUMS').read_bytes()).hexdigest()},ensure_ascii=False))
