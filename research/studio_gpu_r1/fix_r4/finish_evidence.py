"""Check final receipts, clean task state, and write the fourth-round delivery."""

from __future__ import annotations

from collections import Counter
import datetime
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess

OUT = Path(__file__).resolve().parent
RESEARCH = OUT.parent.parent
WORKTREE = Path('/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview')
SCRATCH = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/studio-gpu-fix-r3')
HEAD = '652847c0ea570ba4bc1e5e635055e3a1543ec996'


def write_json(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def main():
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=WORKTREE, text=True).strip() == HEAD
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=WORKTREE)
    ci = json.loads((OUT / 'ci-final.json').read_text())
    assert ci['headSha'] == HEAD and ci['conclusion'] == 'success'
    assert all(job['conclusion'] == 'success' for job in ci['jobs'])
    expected_jobs = {'tests (windows-latest)', 'tests (macos-latest)', 'check', 'windows-probes', 'security-report'}
    assert {job['name'] for job in ci['jobs']} == expected_jobs
    receipts = []
    for path in sorted(OUT.glob('final-r*-receipt.json')):
        row = json.loads(path.read_text())
        assert row['head'] == HEAD and row['exit_code'] == 0 and row['source_hashes_unchanged']
        assert row['automatic_reruns'] == 0 and row['nice'] == 10
        row['receipt'] = path.name
        row['case'] = row['command'][-1]
        row['kind'] = 'legacy_observation' if row['case'] == 'r4-original-extra' else 'current_behavior'
        receipts.append(row)
    assert len(receipts) == 30
    write_json('replay-receipts.json', receipts)
    check = json.loads((OUT / 'final-check-verified-receipt.json').read_text())
    assert check['head'] == HEAD and check['exit_code'] == 0 and check['source_hashes_unchanged']
    assert check['nice'] == 10 and check['automatic_reruns'] == 0
    totals = json.loads((OUT / 'coverage.json').read_text())['totals']
    dat_rows = json.loads((OUT / 'replays/r4-dat-variants/dat-root-variants.json').read_text())
    assert len(dat_rows) == 3
    assert all(row['status'] == 409 and row['read_count'] == 0 and not row['actual_opened_paths'] for row in dat_rows)
    assert all(row['identities'][0]['expect_passed'] == row['identities'][0]['before'] for row in dat_rows)
    assert len(json.loads((OUT / 'replays/r4-card-extra/additional-card-cases.json').read_text())) == 18
    inputs = json.loads((OUT / 'review-inputs-before.json').read_text())
    changed_inputs = [name for name, digest in inputs.items() if hashlib.sha256(Path(name).read_bytes()).hexdigest() != digest]
    assert not changed_inputs
    manifest = json.loads((OUT / 'final-source-manifest.json').read_text())
    changed_sources = [name for name, digest in manifest['files'].items()
                       if hashlib.sha256((WORKTREE / name).read_bytes()).hexdigest() != digest]
    assert not changed_sources
    write_json('source-stability.json', dict(head=HEAD, tracked_files=len(manifest['files']),
                                           review_inputs=len(inputs), changed_sources=changed_sources,
                                           changed_review_inputs=changed_inputs, checked_at=now))
    browser = [json.loads(line) for line in (OUT / 'browser-lifecycle.jsonl').read_text().splitlines()]
    starts = Counter(row['pid'] for row in browser if row['event'] == 'start')
    closed = Counter(row['pid'] for row in browser if row['event'] == 'closed')
    assert starts and starts == closed
    assert all(':49667/' not in row.get('url', '') for row in browser)
    disk = plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert disk['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert disk['FilesystemType'] == 'apfs' and disk['WritableVolume']
    process_text = subprocess.check_output(['ps', '-axo', 'pid,ppid,nice,etime,command'], text=True)
    (OUT / 'processes-before-cleanup.txt').write_text(process_text)
    remaining = []
    for line in process_text.splitlines()[1:]:
        fields = line.split(None, 4)
        if len(fields) != 5 or int(fields[0]) in {os.getpid(), os.getppid()}:
            continue
        command = fields[4]
        if str(SCRATCH) in command or str(OUT) in command or 'gh run watch 41595529400' in command:
            remaining.append(line)
    assert not remaining, remaining
    shutil.rmtree(SCRATCH)
    assert not SCRATCH.exists()
    cleanup = dict(checked_at=now, task_temporary_root=str(SCRATCH), temporary_root_exists=False,
                   task_processes=remaining, browser_starts=sum(starts.values()), browser_closed=sum(closed.values()),
                   pinned_playwright='1.61.1', pinned_chromium_revision='1228')
    write_json('cleanup.json', cleanup)
    write_json('interruption-recovery.json', dict(
        user_stop_at='2026-11-03T07:25:00Z', resumed_at='2026-11-03T07:47:41Z',
        renewed_deadline='2026-11-03T09:17:41Z',
        original_make_check='The test child finished, but the interrupted supervisor did not save an exit receipt.',
        accepted_make_check_receipt='final-check-verified-receipt.json',
        ci_full_jobs='All three full jobs passed on the first attempt.',
        diagnostic_job='Only windows-probes was manually run again once after its first 30-second browser timeout.',
    ))
    summary = dict(head=HEAD, verdict='可以交复审', ci_url=ci['url'],
                   ci_jobs={job['name']: job['conclusion'] for job in ci['jobs']},
                   local_tests=dict(passed=1033, skipped=706, automatic_reruns=0), coverage=totals,
                   replay_cases=len(receipts), current_behavior_cases=29, legacy_observations=1,
                   cleanup=cleanup)
    write_json('delivery-summary.json', summary)
    report = RESEARCH / 'studio_gpu_r1/FIX_R3.md'
    original = (OUT / 'FIX_R3-before.md').read_text()
    header, history = original.split('\n', 1)
    assert header == '可以交复审'
    introduction = f'\n\n第四轮最终提交为 `{HEAD}`，最新结果见本文“第四轮”。以下前半部分保留第三轮记录，原报告另存于 [FIX_R3-before.md](fix_r4/FIX_R3-before.md)。\n'
    section = f'''

## 第四轮

门槛结论：可以交复审。第四轮复审 P1-01 已关闭。最终本地提交 `{HEAD}`，工作树为 feat/gpu-preview，仅推送 ci/win-fix-r3。

DAT 读取原来只收到卡根路径，丢失了所选 MountSession 的根身份；open_rb 因而重新取当前路径的身份，可能接受已换过的根。现在显式 card_id 分支继续保留已解析的 session，自动单卡分支同时取出 session 和 scan。read_dat_from_card 的关键字参数 expect 为必需值，API 把 fingerprint.root_dev/root_ino 传入，再原样交给 open_rb；根句柄身份不符时，在打开 DAT 内容前返回 409。

全部生产 open_rb 调用共三处：DAT、照片暂存、照片哈希，均传 root 和 expect。导入与覆盖核对的上层仍在扫描前固定身份。[调用清单](fix_r4/card-read-call-sites.json)。改动文件为：

- src/gxr_studio/api/camdata_routes.py。
- src/gxr_studio/camdata/intake.py。
- tests/test_dat_card_identity.py。
- tests/test_clone_coverage.py。

先写回归，再修实现。[修前日志](fix_r4/before-fix.log)为 4 failed、4 passed：显式和自动选卡下，普通根替换与上级目录链接四项实际读取 OTHER-SYNTHETIC-DATA，返回 422。随后原测试通过；新增八项在 Windows 与 macOS 完整 CI 中全部通过，包含两项正常读取对照及两项根自身链接拒绝对照。[逐项 CI 记录](fix_r4/ci-dat-identity-results.json)、[回归源码](fix_r4/regression-test.py)。缺文件的旧 intake 测试也改为传原根身份，保留其读取失败断言。

复审的 DAT 原触发点已保留并重跑：[普通根替换](fix_r4/replays/r4-dat-root/card-root-dat.json)及[三种根变化](fix_r4/replays/r4-dat-variants/dat-root-variants.json)。三种变化均真实发生，expect 等于变化前的 dev/ino；全部返回 409，_read_limited 调用数为 0，实际内容打开路径为空。原输入未修改，路径和修后预期的调整分别保存在对应 adaptation.diff。

同一 SHA 的三平台 CI：

| 任务 | 结果 | 完整测试记录 |
| --- | --- | --- |
| [Windows tests](https://github.com/aa2246740/gxr-studio/actions/runs/41595529400/job/125781880490) | success | 1036 passed、703 skipped，1651.47 秒。 |
| [macOS tests](https://github.com/aa2246740/gxr-studio/actions/runs/41595529400/job/125781880345) | success | 1033 passed、706 skipped，335.57 秒。 |
| [Linux check](https://github.com/aa2246740/gxr-studio/actions/runs/41595529400/job/125781880527) | success | 1029 passed、710 skipped；DAST 另为 25 passed。 |

三个完整任务均首次通过，pytest 自动重跑为 0。[首次元数据](fix_r4/ci-attempt1.json)、[最终元数据](fix_r4/ci-final.json)、[Windows 原始日志](fix_r4/ci-windows-full.log)、[macOS 原始日志](fix_r4/ci-macos-full.log)、[check 原始日志](fix_r4/ci-linux-check.log)。

Windows 短任务首轮的软件显卡探针在 30 秒内没有返回，清理时 chrome.log 仍被子进程占用；具体首次启动延迟原因未定位。[首错](fix_r4/ci-first-windows-probes.log)已保留。只手动重跑这个任务一次，同一 SHA 在 7 分钟内通过，未改探针、上限或断言。Windows 原生句柄、事件循环、两个矩阵工作线程、两个逆矩阵工作线程、64 MiB 表、GPU API 和 14 项颜色测试均通过。[短任务日志](fix_r4/ci-windows-probes-final.log)。security-report 也通过，最终 workflow 为 success，run_attempt=2。

本机 make check 为 1033 passed、706 skipped，0 自动重跑，覆盖率 {totals['percent_covered']:.8f}%（{totals['covered_lines']}/{totals['num_statements']}，排除 {totals['excluded_lines']} 条）。机主停止后核对无残留进程，完整检查从头复跑，退出码为 0；所有最终检查均绑定本 SHA、nice 10、源码哈希稳定。[完整回执](fix_r4/final-check-verified-receipt.json)、[JUnit](fix_r4/final-check-verified.xml)、[覆盖率](fix_r4/coverage.json)。

复审入口共保存 30 次执行回执，其中 29 项为当前行为验证，1 项为原样旧接口诊断。五组 r2 边界、三组 r3 边界/事件循环/声明、r4 的 DAT、18 项读卡补充、边界、声明、两份全输入颜色入口、两份软件显卡入口，以及两份历史运行库入口各五种模式都已执行。[汇总](fix_r4/replay-receipts.json)。

原样 r3 extra_boundaries 的旧 open_rb 子类签名先得到 TypeError，单列保存于 [原样观察](fix_r4/replays/r4-original-extra/original-extra_boundaries.py.json)；保留原触发点的 r3-extra 与 r4-extra 适配版均通过。Windows 专用 windows_runtime.py 在本机不执行，其 io/loop/lut 行为由同 SHA Windows 原生短任务验证；历史运行库入口的本机复跑使用当前 macOS 依赖，不作为 Windows 旧轮子的再次 A/B 试验。准备环境、取 CI 日志、写报告和清理等辅助脚本按本轮隔离路径执行，没有运行指向机主 Studio 的旧入口。

r2 和 r4 的两组颜色入口分别穷举全部 16777216 个 RGB 输入，RGB 与 alpha 差异均为 0；两份合成 RAW/JPG 显卡对照 mean=0、max_code=0。[r2 穷举](fix_r4/replays/r2-exhaustive/exhaustive-lut.json)、[r4 穷举](fix_r4/replays/r4-exhaustive/exhaustive-lut.json)、[软件显卡结果](fix_r4/replays/r4-colour/synthetic-lut-counterexample-swiftshader.json)。45 个颜色与前端文件与复审输入逐字节一致，[清单](fix_r4/stable-colour-sources.json)。默认关闭开关与原颜色算法的现有测试全部保留。

312 个跟踪文件与提交后清单相同，324 个复审输入文件哈希未变。[稳定性回执](fix_r4/source-stability.json)。[SHA256SUMS](fix_r4/SHA256SUMS)覆盖本轮报告、进度、源码补丁、源清单、原始 CI 日志、回执和复跑文件。第三轮旧报告和旧清单已原样另存；旧清单代表第三轮交付时状态。

任务临时目录及 pytest basetemp 已删除，4 次浏览器启动均正常关闭，固定 Playwright 1.61.1 / Chromium Headless Shell 1228。实际[清理回执](fix_r4/cleanup.json)及[浏览器记录](fix_r4/browser-lifecycle.jsonl)已保存。未访问真实卡、机主 Studio、真实图库/导出/应用数据目录，未启动子代理；公开提交只含四个代码和测试文件。硬件显卡、真实读卡器/FAT32 与相机设备层未运行。

门槛结论：可以交复审。最终本地 SHA `{HEAD}`；ci/win-fix-r3 的 Windows tests、macOS tests、Linux check 均 success，Windows 短任务和 security-report 也 success。临时目录与浏览器 profile 已清理；调试分支保留给机主核对。
'''
    report.write_text(header + introduction + history + section)
    progress = RESEARCH / 'studio_gpu_r1/PROGRESS.md'
    progress.write_text(progress.read_text() + f'''

## 第四轮恢复后的最终结果

{now}。07:25 UTC 机主停止后，07:47:41 UTC 核对无残留任务进程、工作树干净，时间盒重置至09:17:41 UTC。最终提交仍为 `{HEAD}`，只推 ci/win-fix-r3。

- DAT 显式与自动选卡均传递所选 MountSession 的根 dev/ino；新回归先得到4 failed、4 passed，再在三平台完整套件通过。
- 三个完整CI首次通过：Windows 1036 passed、703 skipped；macOS 1033 passed、706 skipped；Linux check 1029 passed、710 skipped，DAST 25 passed。短诊断首轮30秒浏览器超时，保留首错后单独手动重跑一次通过，最终workflow为success。
- 恢复后的make check完整退出0，1033 passed、706 skipped、0自动重跑，覆盖率{totals['percent_covered']:.8f}%。30次复跑回执完成，其中29项当前行为验证、1项原样旧接口诊断。312个源文件与324个复审输入哈希稳定。
- 原DAT三种根变化均409且内容读取0；18项补充边界、全输入颜色及软件显卡对照通过。FIX_R3.md第四轮及fix_r4证据已生成。
- 实际清理已确认：任务临时根不存在，任务进程为零，4次浏览器全部正常关闭。调试分支保留供机主核对。
''')
    checksums = []
    for path in sorted(OUT.rglob('*')):
        if path.is_file() and path.name != 'SHA256SUMS':
            checksums.append((path, str(path.relative_to(OUT))))
    checksums += [(report, '../FIX_R3.md'), (progress, '../PROGRESS.md')]
    changed_names = subprocess.check_output(['git', 'diff', '--name-only', 'fb6bacc', HEAD], cwd=WORKTREE, text=True).splitlines()
    checksums += [(WORKTREE / name, str(WORKTREE / name)) for name in changed_names]
    lines = [hashlib.sha256(path.read_bytes()).hexdigest() + '  ' + label for path, label in checksums]
    (OUT / 'SHA256SUMS').write_text('\n'.join(lines) + '\n')
    for path, line in zip([item[0] for item in checksums], lines, strict=True):
        assert hashlib.sha256(path.read_bytes()).hexdigest() == line[:64]
    print(json.dumps(dict(head=HEAD, verdict='可以交复审', checksum_entries=len(lines),
                          current_behavior_cases=29, legacy_observations=1, temporary_root_exists=SCRATCH.exists(),
                          browser_starts=sum(starts.values()), browser_closed=sum(closed.values())), ensure_ascii=False))


if __name__ == '__main__':
    main()
