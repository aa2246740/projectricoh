"""Record the round-3 compile stop without repairing or retrying acceptance."""
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c
import verify_round2 as review


def main():
    out = review.ROUND3
    assert not (out / 'verification.json').exists()
    failure = json.loads((out / 'failure.json').read_text())
    assert failure['status'] == 'FAILED_STOPPED' and not failure['card_files_staged']
    commands = [json.loads(line) for line in (out / 'commands.jsonl').read_text().splitlines()]
    assert len(commands) == 1 and commands[0]['label'] == 'round3-host-compile'
    assert commands[0]['returncode'] == 1
    compile_log = (out / 'logs/round3-host-compile.log').read_text()
    assert "error: conflicting types for 'tweak_path'" in compile_log
    assert '7 errors generated.' in compile_log
    assert not (out / 'host/host_checks').exists()
    assert not (out / 'host-evidence').exists()
    assert not (c.HERE / 'local/card_update/GXRCE.DAT').exists()
    protected = json.loads((out / 'protected-inputs.json').read_text())
    current = review.protected_snapshot()
    differences = [dict(path=p, before=protected.get(p), after=current.get(p))
                   for p in sorted(protected.keys() | current.keys()) if protected.get(p) != current.get(p)]
    assert len(protected) == 480 and not differences
    preserved_round1 = review.round1_unchanged()
    preserved_prior = review.prior_unchanged()
    candidate = c.OUT / 'GXRCE.DAT'
    assert c.sha(candidate) == review.EXPECTED_SHA
    summary = dict(status='FAILED_STOPPED', round=3, failed_gate='host fixture compilation',
                   root_cause='tweak_path in host_round2.c conflicts with the function included from extra_checks.inc.c',
                   compiler_errors=7, compile_attempts=1, host_link_run=False, validator_rerun=False,
                   host_cases=0, iv_a='NOT_RUN', iv_b='NOT_RUN', GXTS_update='NOT_RUN',
                   units_not_run=['50mm', '28mm', 'Mount'],
                   card_files_staged=False, card_manifest_status='BLOCKED_NOT_STAGED', camera_acceptance=False,
                   candidate_sha256=c.sha(candidate), candidate_generation=106,
                   candidate_bytes=candidate.stat().st_size, protected_inputs=480,
                   protected_inputs_unchanged=True, round1_files_preserved=preserved_round1,
                   prior_files_preserved=len(preserved_prior),
                   compile_log='logs/round3-host-compile.log', invocation_log='logs/verify-round3.log',
                   next_round_fix='Rename only the new fixture helper and its calls, then compile in a new evidence directory')
    c.save(out / 'verification.json', summary)
    c.save(out / 'scope-after.json', dict(status='PASS', protected_inputs=480, differences=differences,
           protected_inputs_unchanged=True, decisions_excluded=True,
           decisions_informational_sha256=c.sha(c.ROOT / 'decisions.tsv'),
           all_round1_files_preserved=True, all_prior_files_preserved=True))
    manifest_path = c.HERE / 'local/card_update/manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest.update(status='BLOCKED_NOT_STAGED', files=[],
                    reason='Round 3 host fixture compile failed: conflicting types for tweak_path; behavior and GXTS tests not run',
                    round=3, actual_card_access=False,
                    prepare_card=['power off', 'take the card out', 'delete GXRCE.OK',
                                  'delete any GXRCE.DAT', 'copy only the new container as GXRCE.DAT after acceptance',
                                  'leave every other file'])
    c.save(out / 'blocked-card-manifest.json', manifest)
    # common.write is intentionally confined to local/round3 in this run.
    assert manifest_path.read_bytes() == (out / 'prior/local/card_update/manifest.json').read_bytes()
    report = f'''# full-r4 第三轮报告

第三轮在主机夹具编译时失败，按规则停止，没有修复后重试。卡包仍为 BLOCKED_NOT_STAGED，没有 GXRCE.DAT 暂存文件。

已核实：按本轮批准，仅把 decisions.tsv 排除出冻结输入，摘要保留作参考；其余 480 个输入在开始与收尾时均与第一轮一致。现有 313 项校验全部通过，第一轮 298 个文件与本轮开始时的 314 个文件均保留。第二轮报告、旧清单和原脚本副本在 [round3/prior/](local/round3/prior/)，第一轮与第二轮的失败记录仍在原位。

编译使用原有 clang、-Werror 和 ASan/UBSan 选项，只尝试一次，返回码为 1。根因是 [host_round2.c:25](host_round2.c#L25) 定义三参数 tweak_path，而 host_checks.c:434 包含的 extra_checks.inc.c:1 已定义同名单参数函数。clang 报 7 个错误，首条为：

```text
error: conflicting types for 'tweak_path'
```

完整错误见 [编译日志](local/round3/logs/round3-host-compile.log)，调用与真实 traceback 见 [运行日志](local/round3/logs/verify-round3.log)。本轮审查漏掉了间接包含文件里的同名函数；未改引擎、resident、body 或原夹具，也未放宽断言。下一轮只需先处理新夹具的函数名冲突，再在新目录编译验证。

未运行：(iv-a)、(iv-b) 的三单元场景，以及 (d) 四槽微调保存、更新和冷加载。不能据本轮报告 16 行显示、SaveFail、停用、GXTS 保留或重置结果。

full-r4 候选未变，generation 106，59,516 B，SHA-256：

```text
{summary['candidate_sha256']}
```

只改三条目、引擎仅 type-64 BSS 重定位低半部不同等第一轮证据仍保留，见 [第一轮报告](local/round2/round1/REPORT.md)。本轮再次核对批准映像 05b46ee65f4861f2e09e9b7c519cbcc2dffb195158a40c3bb033540b36a98d8c 与 resident ELF f25899258471d0652a8fef8980b9f0a83a0ca7cd4ddc6bbe8fcc337467362b58 的摘要。

验收通过后的卡流程仍为：关机、取卡、删除 GXRCE.OK、删除任何 GXRCE.DAT，只把新容器复制为 GXRCE.DAT，其它文件全部保留。本轮没有执行这些步骤。当前卡包 manifest 保留原样，本轮阻断状态另记在 [blocked-card-manifest.json](local/round3/blocked-card-manifest.json)。

未知：本轮所有行为与 GXTS 结果、相机 UI、实际 M32R 执行、rename 和掉电持久化。写入只在 firmware/full_r4/；未访问相机卡或刷机，未启动子代理、sleep、轮询、安装包、commit 或 push。清单覆盖原证据、新日志及本报告。
'''
    (c.HERE / 'REPORT.md').write_text(report)
    preserved_prior = review.prior_unchanged()
    c.save(out / 'prior-preservation.json', dict(status='PASS', files=len(preserved_prior), preserved=preserved_prior))
    assert review.round1_unchanged() == preserved_round1
    c.write(out / 'volume-after.txt', subprocess.check_output(['/bin/df', '-h', '/Volumes/Workspace']))
    checksum = c.HERE / 'SHA256SUMS'
    files = [p for p in sorted(c.HERE.rglob('*')) if p.is_file() and p != checksum]
    checksum.write_text(''.join(f'{c.sha(p)}  {p.relative_to(c.HERE).as_posix()}\n' for p in files))
    print(json.dumps(dict(status='FAILED_STOPPED', compiler_errors=7, host_cases=0, card_files_staged=False,
                          protected_inputs=480, prior_files_preserved=len(preserved_prior),
                          checksum_files=len(files), candidate_sha256=summary['candidate_sha256']), ensure_ascii=False))


if __name__ == '__main__':
    main()
