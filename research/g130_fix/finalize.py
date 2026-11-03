#!/usr/bin/python3
"""Seal the stopped candidate with explicit incomplete checks."""
from pathlib import Path
import datetime
import hashlib
import json
import re
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'research/g130_fix'
ENGINE = ROOT / 'firmware/engine_v50_h07'
PACKAGE = ROOT / 'firmware/package_v36_g130'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

def main():
    frozen = json.loads((WORK / 'evidence/inputs-before.json').read_text())
    changes = [name for name, digest in frozen.items() if not (ROOT / name).is_file() or sha(ROOT / name) != digest]
    gate = dict(status='PASS' if not changes else 'FAIL', checked=len(frozen), changed=changes)
    save(WORK / 'evidence/final-input-gate.json', gate)
    assert not changes, changes
    dat = PACKAGE / 'local/SD_ROOT/GXRCE.DAT'
    current = dat.read_bytes()
    baseline = (ROOT / 'firmware/package_v36_g127/local/SD_ROOT/GXRCE.DAT').read_bytes()
    assert int.from_bytes(current[28:32], 'big') == 130
    last = struct.unpack_from('>III', current, 200)
    old_last = struct.unpack_from('>III', baseline, 200)
    assert last[2] == 1408 and old_last[2] == 3392
    package = json.loads((WORK / 'evidence/package.json').read_text())
    assert package['dat_sha256'] == sha(dat)
    files = sorted(path for path in (PACKAGE / 'local/SD_ROOT').rglob('*') if path.is_file())
    assert len(files) == 30
    fixed = []
    for path in files:
        relative = path.relative_to(PACKAGE / 'local/SD_ROOT')
        if path.name != 'GXRCE.DAT':
            assert path.read_bytes() == (ROOT / 'firmware/package_v36_g120b/SD_ROOT' / relative).read_bytes()
            fixed.append(str(relative))
    assert len(fixed) == 29
    save(WORK / 'evidence/final-package-gate.json', dict(status='PASS_PACKAGE_IDENTITY_ONLY', dat_sha256=sha(dat), generation=130, files=30, fixed_files_equal_g120b=len(fixed), section6_bytes=last[2], baseline_section6_bytes=old_last[2], product_acceptance=False))
    runs = [json.loads(line) for line in (WORK / 'evidence/runs.jsonl').read_text().splitlines() if line.strip()]
    assert len(runs) == 1 and runs[0]['returncode'] == 1 and runs[0]['dat_sha256'] == sha(dat)
    jobs = json.loads((WORK / 'queue.json').read_text())
    matrix = []
    for index, job in enumerate(jobs):
        matrix.append({**job, 'status': 'FAIL_BEFORE_TARGET_CUT' if index == 0 else 'NOT_RUN_SCOPE_STOPPED', 'returncode': 1 if index == 0 else None, 'late_s_stores': None, 'late_previews': None})
    save(WORK / 'evidence/acceptance.json', dict(status='INCOMPLETE_PRIORITY_STOP', dat_sha256=sha(dat), failed=1, not_run=28, jobs=matrix, preview_window='INHERITED_OPEN_NOT_RUN_SCOPE_STOPPED', h01_restore='NOT_RUN_SCOPE_STOPPED'))
    publication = WORK / 'local/checks/review_g127/publication-state.json'
    state = json.loads(publication.read_text())
    assert state['rows'] == 7 and state['root']['state'] == 6
    stop = dict(status='STOPPED_PRODUCT_ASSERTION', dat_sha256=sha(dat), failed_case='h07-parent-50mm', assertion='integration_native.py:154 published', native_state=6, physical_rows=7, section6_bytes=last[2], required_section6_bytes=3392, baseline_section6_bytes=old_last[2], missing_extension_bytes=old_last[2] - last[2], target_cut_reached=False, camera_evidence=False)
    save(WORK / 'evidence/stop.json', stop)
    scope_paths = [ROOT / 'research/g127_fix/local/release127/review_g126' / name for name in ('dependencies-ownership_settings---help.json', 'target-map-ownership_settings---help.json', 'commands.jsonl')]
    save(WORK / 'evidence/scope-exception.json', dict(status='PRE_FENCE_AUXILIARY_WRITE', action='曾调用旧 wrapper 查询接口，自动生成或更新旧 local 辅助文件。', paths=[str(path.relative_to(ROOT)) for path in scope_paths], prior_contents_verified=False, original_script_source_changed=False, later_execution='新系统写入限制只允许三个新目录，并禁止网络。'))
    codegen = json.loads((WORK / 'evidence/codegen-four-categories.json').read_text())
    assert codegen['dat_sha256'] == sha(dat)
    report = f'''有缺陷

gen 130 首次发布失败，未进入 H07 切点。已按“产品断言在真实产物上失败，定位修复后仍失败”的条件停止产品检查。当前产物保留供定位，不能视为通过聚焦验收的候选。

P1-01：封包的 sections[6] 只有 1,408 B；gen 127 为 3,392 B。当前 uv_validate 要求 generation=130 且该节为 3,392 B，因此返回失败。实际回放为 state=6、rows=7，AssertionError 位于 integration_native.py:154 的 published。本轮修正了三处代号比较后，首次发布仍失败；未继续修复封包扩展。

最终 DAT SHA256：`{sha(dat)}`。
最终 ELF SHA256：`{package['elf_sha256']}`。
DAT {len(current):,} B，engine {codegen['engine_bytes']:,} B，BSS 8,848 B。包内完整 30 个文件，29 个固定文件与 gen 120b 逐字相同。实际字节全部位于被忽略的 local/；SD_ROOT 是指向本包 local/SD_ROOT 的相对链接。

| 检查 | 结果 |
| --- | --- |
| h07-parent，50mm | FAIL_BEFORE_TARGET_CUT；未取得晚到 S store 计数。 |
| h07-parent，其余两个单元 | NOT_RUN_SCOPE_STOPPED。 |
| h07-parent-preview，三个单元 | NOT_RUN_SCOPE_STOPPED；未取得晚到预览计数。 |
| preview-window，三个单元 | 继承 P2-03 保持 OPEN；本轮 NOT_RUN_SCOPE_STOPPED。 |
| ownership_settings、cold_reentry、cold_exit、settings_cases，各三个单元 | NOT_RUN_SCOPE_STOPPED。 |
| batch 的 safety、locked、nested、cutpoints、exits，50mm | NOT_RUN_SCOPE_STOPPED。 |
| H01 首发及重开的 mode=1、WB=9/9 | NOT_RUN_SCOPE_STOPPED；失败后的原生 mode=1 不算配方恢复证据。 |
| 改动函数四类编译码检查 | PASS_STATIC；12 个函数、7 个 C/头文件，绑定最终 DAT/ELF。 |
| wrapper 的代号字段与 ASCII 上限自测 | PASS；ASCII 上限仍为 126，5 个断言。 |
| audit_records.py 通信复核 | 返回码 1；没有取得完整通信流，INCOMPLETE_NO_COMPLETE_RECORDS。 |

本轮队列共 29 项，首项失败，28 项未运行。没有运行完整 81 组回归。所有运行结果、未知计数和停止状态见 evidence/acceptance.json；不得把未到达切点解释为晚到写入为 0。

源码变化见 source-change-vs-g127.patch。服务层单独差异见 services-only.patch，便于后续合并。

服务层新增 rv_settings_entry，复用当前副本没有其他读写的 context.input_fields 和 input_sequence，记录入口号和 resident 的 entry_serial。公共 ingress 先设为 0，再由 H01/H06/H07/H08 的入口代码绑定自己的入口号。rv_settings_owned 要求 inflight=1、当前会话 nonce、相同 entry_serial 和有效入口号；H01 使用构造规则，其余三个入口使用严格规则。请求参数不携带可切换该规则的字段。返回后 inflight=0，下一入口也会重置绑定。这些是静态设计事实，未获目标切点的运行验收；合并 knobs 版本前需要确认那一版本对两个 context 字段的使用。

settings op 2 沿用原 IRQ 区间复核；preview op 1 的归属复核加入 IRQ 区间，恢复 IRQ 后到原生入口之间的继承窗口仍保留。tag 33 在两种规则下都要求 overlay=32。settings_pending、锁定、RPC 类型、S 地址、九行、T、文件操作及 4+2 补偿的相关函数正文保持原样。三处 build_number 比较仅从 127 改为 130；构建入口与目录 guard 同步到新目录。封包仍缺少上面的用户表扩展，功能结果未保持等价。

新 wrapper 按名称或已知 generation 字段重绑代号，没有整体递归替换整数。它为目标字段新增常量槽，只改对应指令；其他基线代号与 ASCII 126 保留。CRC 参数为 `--crc-implementation host|native`。停止运行使用 native，host 叶调用计数为 0。最终 wrapper 随后进一步收窄为只重绑脚本所属的代号，已过独立自测，但按停止条件未再跑产品。失败时的 wrapper 原文已按记录的 SHA256 归档到 local/wrapper-at-stop.py；版本对应见 evidence/runner-identity.json。

准备阶段还保留了代号校验失败、一次初始化跟踪过慢的作废运行，以及诊断回调寄存器错误造成的工具中止。诊断回调已移除；最终失败是移除回调后的首次发布断言。这些准备记录均不计为验收通过。

本轮冻结 {len(frozen)} 项输入，结束时全部未变。用户提供的 4,798 项核对作为已知前提，本轮没有重新宣称核对全部 4,798 项。没有访问相机、存储卡或网络，没有启动子代理。检查串行执行，超时为 1,200 秒或 3,600 秒，均超过所列历史用时的三倍。

流程例外：建立系统写入限制前，曾调用旧 wrapper 查询接口，它自动写入 research/g127_fix/local/release127/review_g126 下的 dependencies-ownership_settings---help.json、target-map-ownership_settings---help.json 和 commands.jsonl。未取得任务前这些辅助文件的内容，不能声称全过程只写了三个新目录。旧脚本源码没有修改；之后的构建、检查和封存均受 write-fence.sb 限定。详见 evidence/scope-exception.json。

静态已证：源码差异、编译码四类检查、最终 DAT/ELF 绑定、30 文件身份与封包节长度。
主机已证：首次发布失败，state=6、rows=7；wrapper 自测通过。
推断：sections[6] 长度不符解释了 uv_validate 的拒绝路径。
未知：H07 目标切点、继承 preview 窗口本轮表现、其余聚焦检查及任何相机端结果。
'''
    (WORK / 'REPORT.md').write_text(report)
    (PACKAGE / 'DELIVERY.md').write_text(f'gen 130 有缺陷\n\nDAT SHA256 `{sha(dat)}`。完整 30 个文件，29 个固定文件与 gen 120b 相同。首次发布失败，sections[6] 为 1,408 B，引擎要求 3,392 B。H07 聚焦验收未完成。详见 ../../research/g130_fix/REPORT.md。实际字节在被忽略的 local/SD_ROOT。\n')
    (ENGINE / 'STATUS.txt').write_text('gen 130 stopped candidate\n首次发布失败；H07 目标切点未到达。\n详见 research/g130_fix/REPORT.md。\n')
    local_files = [path for base in (ENGINE, PACKAGE, WORK) for path in base.rglob('*') if path.is_file() and not path.is_symlink() and 'local' in path.relative_to(base).parts]
    ignored = subprocess.run(['git', 'check-ignore', '--no-index', '--stdin'], input='\n'.join(str(path.relative_to(ROOT)) for path in local_files) + '\n', cwd=ROOT, capture_output=True, text=True, env={'PATH': '/usr/bin:/bin', 'GIT_OPTIONAL_LOCKS': '0'})
    ignored_names = set(ignored.stdout.splitlines())
    assert all(str(path.relative_to(ROOT)) in ignored_names for path in local_files)
    save(WORK / 'evidence/local-ignore-check.json', dict(status='PASS', files=len(local_files)))
    save(WORK / 'evidence/delivery.json', dict(status='有缺陷', stopped=True, dat_sha256=sha(dat), files=30, fixed_files=29, frozen_inputs=len(frozen), frozen_changes=0, requested_checks=29, failed=1, not_run=28, camera_evidence=False, utc=datetime.datetime.now(datetime.timezone.utc).isoformat()))
    engine_files = sorted(path for path in ENGINE.rglob('*') if path.is_file() and not path.is_symlink() and path.name != 'EVIDENCE_SHA256SUMS')
    (ENGINE / 'EVIDENCE_SHA256SUMS').write_text(''.join(sha(path) + '  ' + str(path.relative_to(ROOT)) + '\n' for path in engine_files))
    all_files = sorted(path for base in (ENGINE, PACKAGE, WORK) for path in base.rglob('*') if path.is_file() and not path.is_symlink() and path != WORK / 'SHA256SUMS')
    (WORK / 'SHA256SUMS').write_text(''.join(sha(path) + '  ' + str(path.relative_to(ROOT)) + '\n' for path in all_files))
    for path in all_files:
        assert path.is_relative_to(ENGINE) or path.is_relative_to(PACKAGE) or path.is_relative_to(WORK)
    print(json.dumps(dict(name='delivery-seal', returncode=0, counts=dict(files=len(all_files), requested=29, failed=1, not_run=28, frozen=len(frozen)))))

if __name__ == '__main__':
    main()
