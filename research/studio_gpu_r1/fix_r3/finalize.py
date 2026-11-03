"""Validate final receipts, remove task-owned temporary files, and hash the delivery."""

from pathlib import Path
import collections
import datetime
import hashlib
import json
import os
import shutil
import subprocess

OUT = Path(__file__).resolve().parent
ROOT = Path('/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview')
SCRATCH = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/studio-gpu-fix-r3')


def main():
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip()
    summary = json.loads((OUT / 'verification-summary.json').read_text())
    assert summary['head'] == head and summary['gate'] == '可以交复审'
    assert all(job['result'] == 'success' for job in summary['jobs'].values())
    manifest = json.loads((OUT / 'final-source-manifest.json').read_text())
    assert manifest['head'] == head
    assert all(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == value for name, value in manifest['files'].items())
    frozen = json.loads((OUT / 'review-inputs.json').read_text())['frozen_review_inputs']
    assert all(hashlib.sha256(Path(name).read_bytes()).hexdigest() == value for name, value in frozen.items())
    rows = [json.loads(line) for line in (OUT / 'browser-lifecycle.jsonl').read_text().splitlines()]
    starts = collections.Counter(row['pid'] for row in rows if row['event'] == 'start')
    closed = collections.Counter(row['pid'] for row in rows if row['event'] == 'closed')
    assert starts == closed, (starts, closed)
    volume = subprocess.check_output(['diskutil', 'info', '/Volumes/Workspace'], text=True)
    assert '14BE04EB-AF49-497E-B36A-B078B2F7C5E8' in volume and 'APFS' in volume
    raw = subprocess.check_output(['ps', '-axo', 'pid=,ppid=,command='], text=True)
    processes = {}
    for line in raw.splitlines():
        pid, parent, command = line.strip().split(None, 2)
        processes[int(pid)] = (int(parent), command)
    ancestors = {os.getpid()}
    parent = os.getppid()
    while parent in processes and parent not in ancestors:
        ancestors.add(parent)
        parent = processes[parent][0]
    markers = (str(SCRATCH), str(OUT / 'verify.py'), str(OUT / 'pinned_chrome.mjs'), 'gh run watch 41581601112')
    active = {pid: command for pid, (_, command) in processes.items() if pid not in ancestors and any(marker in command for marker in markers)}
    assert not active, active
    assert SCRATCH.parent == Path('/Volumes/Workspace/Scratch/tmp/projectricoh') and not SCRATCH.is_symlink()
    existed = SCRATCH.exists()
    if existed:
        shutil.rmtree(SCRATCH)
    assert not SCRATCH.exists()
    record = dict(head=head, time_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  temporary_root=str(SCRATCH), existed_before=existed, temporary_root_removed=True,
                  task_processes=active, browser_starts=dict(starts), browser_closed=dict(closed),
                  frozen_review_inputs_unchanged=len(frozen), tracked_sources_unchanged=True,
                  worktree_clean=True, debug_branch_retained=True)
    (OUT / 'cleanup.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    report_path = OUT.parent / 'FIX_R3.md'
    report = report_path.read_text(encoding='utf-8')
    report = report.replace('清理结果以附带实际回执为准；', '任务临时目录已清理，结果见附带实际回执；')
    assert '任务临时目录已清理，结果见附带实际回执；' in report
    report_path.write_text(report, encoding='utf-8')
    with (OUT.parent / 'PROGRESS.md').open('a', encoding='utf-8') as progress:
        progress.write('\n最终清理确认：' + record['time_utc'] + '，任务临时目录已删除，任务进程为零，浏览器均正常关闭。\n')
    (OUT / 'STATE.md').write_text(
        '最终状态：可以交复审\n\n最终本地 SHA ' + head + '，本地 feat/gpu-preview，仅推 ci/win-fix-r3。\n'
        'CI41581601112 的完整 Windows、macOS、check、原生短任务和 security-report 均成功，attempt1。\n'
        '本机1025 passed、706 skipped、0自动重跑、覆盖率89.88393977415308%；8个复审脚本同SHA通过，34个冻结输入未变。\n'
        '任务临时目录已删除，任务进程为零，所有本机浏览器均正常关闭。FIX_R3.md 和 cleanup.json 已写好，SHA256SUMS由本次收尾入口生成。\n'
        '工作树干净，产品源已冻结。机主核对后再推 feat/gpu-preview 并删除调试分支；本轮不做这两步。\n',
        encoding='utf-8',
    )
    paths = sorted([p for p in OUT.rglob('*') if p.is_file() and p.name != 'SHA256SUMS'] +
                   [OUT.parent / 'FIX_R3.md', OUT.parent / 'PROGRESS.md'])
    assert all(not p.is_symlink() for p in paths)
    checksums = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    (OUT / 'SHA256SUMS').write_text(''.join(value + '  ' + str(path.relative_to(OUT.parent)) + '\n'
                                           for path, value in checksums.items()), encoding='utf-8')
    assert all(hashlib.sha256(path.read_bytes()).hexdigest() == value for path, value in checksums.items())
    print(json.dumps(dict(head=head, hashed_files=len(checksums), cleanup=record)))


if __name__ == '__main__':
    main()
