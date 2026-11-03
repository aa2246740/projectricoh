"""Check the finished review, frozen sources and cleanup, then seal every evidence file."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import subprocess

OUT = Path(__file__).resolve().parent
WORKTREE = Path('/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview')
TMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-gpu-r5')
disk = plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil', 'info', '-plist', '/Volumes/Workspace']))
assert disk['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8' and disk['WritableVolume']
assert not TMP.exists()
source = json.loads((OUT/'source-before.json').read_text())
assert len(source) == 312
assert all(hashlib.sha256((WORKTREE/n).read_bytes()).hexdigest() == h for n, h in source.items())
prior = json.loads((OUT/'prior-input-hashes.json').read_text())
assert len(prior) == 755 and all(hashlib.sha256(Path(n).read_bytes()).hexdigest() == h for n, h in prior.items())
state = subprocess.check_output(['git', '--no-optional-locks', '-C', str(WORKTREE), 'status', '--porcelain=v1', '--untracked-files=all'], text=True)
assert state == (OUT/'worktree-before.log').read_text() == ''
head = subprocess.check_output(['git', '-C', str(WORKTREE), 'rev-parse', 'HEAD'], text=True).strip()
assert head == '652847c0ea570ba4bc1e5e635055e3a1543ec996'
remote = json.loads((OUT/'pr-metadata-final.json').read_text())
assert remote['headRefOid'] == head and remote['mergeStateStatus'] == 'CLEAN'
ci = json.loads((OUT/'ci-verification.json').read_text())
assert ci['head'] == head and ci['push']['conclusion'] == 'success'
checks = (OUT/'pr-checks-final.log').read_text()
assert '\tpending\t' not in checks and '\tfail\t' not in checks
assert checks.count('\tpass\t') == 8 and checks.count('\tskipping\t') == 2
first = json.loads((OUT/'debug-jobs-attempt1.json').read_text())['jobs']
second = json.loads((OUT/'debug-jobs-attempt2.json').read_text())['jobs']
for a in first:
    b = next(j for j in second if j['name'] == a['name'])
    if a['name'] != 'windows-probes':
        assert [(s.get('started_at'), s.get('completed_at')) for s in a['steps']] == [(s.get('started_at'), s.get('completed_at')) for s in b['steps']]
browsers = [json.loads(p.read_text()) for p in (OUT/'cases').glob('*/browser-receipt.json')]
assert len(browsers) == 3
assert all(b['browserClosed'] and b['nice'] == 10 and b['runtime']['playwrightVersion'] == '1.61.1' and b['runtime']['chromiumRevision'] == '1228' and '--single-process' in b['chromeArgs'] for b in browsers)
processes = subprocess.check_output(['ps', '-axo', 'pid,ppid,ni,args'], text=True)
remaining = [line for line in processes.splitlines() if str(TMP) in line]
assert not remaining, remaining
selfcheck = json.loads((OUT/'reproductions/independent-selfcheck/receipt.json').read_text())
assert selfcheck['error'] is None and selfcheck['temporary_root_removed'] and selfcheck['git_state_unchanged'] and not selfcheck['source_changes']
report = (OUT/'REVIEW.md').read_text()
assert report.splitlines()[0] == '可以合并'
assert report.rstrip().endswith('可以合并；P1 0 项；PR 上 652847c 的 Windows、macOS、Linux CI 均通过；任务临时文件与浏览器 profile 已清理。')
restricted = ['attack','exploit','inject','bypass','hijack','payload','adversarial','malicious','注入','绕过','旁路','攻击','劫持','接管','恶意','外来','对抗']
assert not any(word in report.lower() for word in restricted)
for target in re.findall(r'\]\(([^)]+)\)', report):
    if target.startswith(('https://', 'http://')) or target == 'SHA256SUMS':
        continue
    path = Path(re.sub(r':\d+$', '', target))
    if not path.is_absolute(): path = OUT/path
    assert path.is_file(), str(path)
(OUT/'source-after.json').write_text(json.dumps(source, indent=2)+'\n')
(OUT/'worktree-after.log').write_text(state)
cleanup = json.loads((OUT/'cleanup.json').read_text())
cleanup['final_verification_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
cleanup['fresh_reproduction_cleaned'] = True
cleanup['task_processes_remaining'] = remaining
(OUT/'cleanup.json').write_text(json.dumps(cleanup, indent=2)+'\n')
with (OUT/'df-after.log').open('w') as log:
    subprocess.run(['df', '-h', '/Volumes/Workspace'], stdout=log, check=True)
(OUT/'source-audit-environment-note.json').write_text(json.dumps({'initial_interpreter': 'system Python 3.9', 'initial_result': 'SyntaxError while parsing the Python 3.14 class ByteLRU[T] declaration', 'resolution': 'Unchanged source_audit.py rerun successfully with the project Python 3.14 interpreter', 'product_source_modified': False}, indent=2)+'\n')
entries = [p for p in sorted(OUT.rglob('*')) if p.is_file() and p.name not in ['SHA256SUMS', 'seal-receipt.json']]
receipt = {'head': head, 'finished_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
           'nice': os.getpriority(os.PRIO_PROCESS, 0), 'source_files_verified': len(source), 'prior_inputs_verified': len(prior),
           'worktree_clean': True, 'temporary_root_removed': True, 'browser_sessions_closed': len(browsers),
           'fresh_reproduction_passed': True, 'pr_ci_attempt': ci['attempt'], 'pr_three_platforms': 'success',
           'push_three_platforms': 'success', 'p1': 0, 'p2': 1, 'checksum_entries': len(entries)+1}
(OUT/'seal-receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
entries = [p for p in sorted(OUT.rglob('*')) if p.is_file() and p.name != 'SHA256SUMS']
assert len(entries) == receipt['checksum_entries']
sums = [(hashlib.sha256(p.read_bytes()).hexdigest(), p.relative_to(OUT).as_posix()) for p in entries]
(OUT/'SHA256SUMS').write_text(''.join(f'{h}  {name}\n' for h, name in sums))
assert all(hashlib.sha256((OUT/name).read_bytes()).hexdigest() == digest for digest, name in sums)
print(json.dumps({**receipt, 'all_checksums_verified': True, 'report_sha256': hashlib.sha256((OUT/'REVIEW.md').read_bytes()).hexdigest()}))
