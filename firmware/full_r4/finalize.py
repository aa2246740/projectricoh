"""Record the stopped run and checksums, without executing further acceptance."""
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c


def main():
    c.guard()
    manifest = json.loads((c.OUT / 'manifest.json').read_text())
    commands = [json.loads(line) for line in (c.LOCAL / 'commands.jsonl').read_text().splitlines()]
    flows = [row for row in commands if row['label'].startswith('flow-')]
    successes = [row for row in flows if row['returncode'] == 0]
    failures = [row for row in flows if row['returncode'] != 0]
    results = []
    for row in flows:
        output = (c.LOCAL / 'logs' / (row['label'] + '.log')).read_text()
        count = re.search(r'assertions=(\d+)', output)
        results.append(dict(label=row['label'], returncode=row['returncode'], output=output,
                            assertions=int(count[1]) if count else None,
                            expected_collision='EXPECTED_OK_COLLISION' in output))
    c.save(c.LOCAL / 'partial-host-results.json', results)
    before = json.loads((c.LOCAL / 'inputs-before.json').read_text())
    after = c.snapshot()
    changed = [path for path, digest in before.items() if after.get(path) != digest]
    c.save(c.LOCAL / 'scope-after.json', dict(protected_files=len(before), changed=changed,
                                             unchanged=not changed))
    summary = dict(status='FAILED_STOPPED', host_cases_attempted=len(flows),
                   host_cases_completed=len(successes), expected_collision_cases=sum(r['expected_collision'] for r in results),
                   failures=failures, completed_case_assertions=sum(r['assertions'] or 0 for r in results),
                   validator_units=3, expanded_slots=48, changed_entries=3, unchanged_entries=45,
                   identical_records=48, golden_slots=48, GXTS_host_tests='NOT_RUN',
                   remaining_downgrade_units='qlaunch,l08firm NOT_RUN',
                   card_files_staged=False, camera_acceptance=False, protected_inputs_changed=changed)
    c.save(c.LOCAL / 'verification.json', summary)
    card = dict(status='BLOCKED_NOT_STAGED', files=[], intended_generation=106,
                intended_sha256=manifest['sha256'], source='../full-r4/GXRCE.DAT',
                reason='r4-downgrade-0 failed; GXTS end-to-end tests not run',
                prepare_card=['delete existing GXRCE.OK', 'delete existing GXRCE.DAT',
                              'copy only the new container as GXRCE.DAT after acceptance'],
                actual_card_access=False)
    c.save(c.LOCAL / 'card_update/manifest.json', card)
    proof = manifest['engine_proof']
    report = f'''# full-r4 主机构建报告

full-r4 已构建，但降级场景检查失败；按要求停止，未暂存可用卡包。没有放宽断言或继续运行 GXTS 测试。

已核实：容器为 [local/full-r4/GXRCE.DAT](local/full-r4/GXRCE.DAT)，generation 106，{manifest['file_bytes']:,} B。SHA-256：

```text
{manifest['sha256']}
```

只替换 50mm 01、02 和 Mount 01。三条展开后与指定源重绑结果全等；其余 45 条与 full-r3 的 C 展开和 expanded/ 全等。48 条 record 全等，50mm 09/10 保留，02 与 10 的色彩数据相同。三单元完整 C 校验通过，48 槽 effective-rows golden 全等。详见 [逐槽证据](local/slot-checks.json)。

引擎 {manifest['engine_bytes']:,} B，BSS {manifest['bss_bytes']:,} B，数据段 {manifest['data_section_bytes']:,} B，容器重定位表 8 B。主块 request 为 7,504 + align4(59,516 + 11,172) = {manifest['main_heap_request']:,} B；会话工作区沿用 912 B，每块原生头另计 12 B。这些不是相机连续可用堆的测量值。

引擎与 full-r3 有 {proof['different_bytes']} B 差异，全部落在 {proof['type64_BSS_sites']} 个 type-64 BSS 重定位的低半部。逐项差值均为 BSS 基址偏移 −188 B；清零这些低半部后，其余字节全等。各 ELF 的 .engine 与对应容器、engine.bin 全等，平移链接审计通过。源码、工具链和服务归档摘要匹配 full-r3，见 [引擎证明](local/engine-proof.json)。

绑定沿用批准映像 05b46ee65f4861f2e09e9b7c519cbcc2dffb195158a40c3bb033540b36a98d8c、resident ELF f25899258471d0652a8fef8980b9f0a83a0ca7cd4ddc6bbe8fcc337467362b58。80 B trust 相同，7,772 B resident payload 与批准映像相同。build ID 为 2eea6eb324790b035d37d33395d60880a1909b4e693414a939dee45f96bfbae7，ABI 为 9583fdd751bebc36f3af305595559643，pins 为 DF2BCAF5 / 6700E6FF / 1B3C7000。未修改或重建 body、resident。

已核实的 host 结果均使用真实 full-r3 生产容器作为 105 前件，并从成功安装后留下的 IROM/OK 状态继续；缺文件确实返回 −1，启用 ASan/UBSan。共执行 19 例，18 例跑完，其中 15 例成功、3 例为预期的旧 OK 冲突反例；第 19 例失败，后续 4 例未跑。

- 空 IROM 首装 106，在替换式和拒绝式 rename 下共 6 例成功，16 行、DAT→OK、IROM 冷加载通过。
- 保留旧 OK 更新，在替换式 rename 下 3 例成功；拒绝式下 3 例确认 DAT→OK 返回 RV_UNCERTAIN 并停用。IROM 的 A=105、B=106 和旧 OK=105 均逐字节核对。冲突例随后在 double 中移除 DAT，单独核实 IROM 可冷加载 106，这不算原更新流程成功。
- 先删旧 OK 更新，在两种 rename 下共 6 例成功，A=105、B=106、OK=106，随后 IROM 冷加载 106。
- 降级场景在 50mm 首例失败，28mm、Mount 尚未运行。失败断言要求旧 DAT=105 存在时仍保持加载 106。原始日志如下，见 [完整失败日志](local/logs/flow-r4-downgrade-0.log)。

```text
FAIL scenario=r4-downgrade unit=0 line=86 rv_load(&root,&rv_trust)==RV_OK&&session()->generation==106 state=3 fault=0 flags=34 install=2
```

state=3 是 READY。源码 resident/loader.c 在成功读取有效卡 DAT 后直接 accepted，尚未扫描 IROM。推断：此次加载了卡上 105，导致 generation==106 失败。原日志没有单独打印返回值、实际 generation 和 source；未加探针或重跑。该断言位于 menu()/安装之前，IROM 是否被旧版写入的后续断言未执行，不能声称持久副本已降级。

GXTS 未验收：四个指定槽位的真实保存、更新、冷加载场景都尚未运行。C 绑定比较显示 50mm 01、02 与 Mount 01 的绑定已变，预计旧微调退回默认；50mm 05 绑定相同，预计保留。这只是源码与绑定推断，不能声明没有 SaveFail、停用或丢值。

卡侧文件规则已由上述更新测试确定，但目前不可交付上卡。待阻断项处理且验收通过后，关机取卡，在卡根目录先删除旧 GXRCE.OK，再删除任何旧 GXRCE.DAT，然后只把新容器复制为 GXRCE.DAT。其它文件保留。成功安装应把 DAT 改为 OK；旧 OK 不能留下，因为真实相机对已有目标的 rename 语义未证明。当前 [card_update/manifest.json](local/card_update/manifest.json) 明确标记 BLOCKED_NOT_STAGED，目录没有 GXRCE.DAT。

未知仍包括相机 rename、持续 open(−1) 的既有 F02 风险、掉电持久化、实际堆、UI 和 M32R 执行。本轮只用主机 doubles，没有相机验收。先由父任务处理“有效卡 DAT 优先于更高代 IROM”与禁止改 resident 的范围冲突，不能靠放宽检查宣称通过。

输出只在 firmware/full_r4/；{len(before)} 个保护输入摘要复核结果为 {'未变' if not changed else '有变化，见 scope-after.json'}。local/ 由 .gitignore 的 /local/ 忽略，见 [preflight](local/preflight.json)。未访问相机卡、刷机、启动子代理、安装包、commit 或 push。失败日志和全部证据由 [SHA256SUMS](SHA256SUMS) 覆盖。

复跑入口如下；当前 verify.py 会在原失败断言停止。

```sh
/usr/bin/python3 -I -B firmware/full_r4/build.py
/usr/bin/python3 -I -B firmware/full_r4/verify.py
/usr/bin/python3 -I -B firmware/full_r4/finalize.py
```
'''
    (c.HERE / 'REPORT.md').write_text(report)
    files = [p for p in sorted(c.HERE.rglob('*')) if p.is_file() and p.name != 'SHA256SUMS']
    text = ''.join(f'{c.sha(p)}  {p.relative_to(c.HERE).as_posix()}\n' for p in files)
    (c.HERE / 'SHA256SUMS').write_text(text)
    print(json.dumps(dict(status=summary['status'], host_cases=len(flows), completed=len(successes),
                          failed=len(failures), protected_inputs=len(before), scope_unchanged=not changed,
                          checksum_files=len(files), card_files_staged=False), ensure_ascii=False))


if __name__ == '__main__':
    main()
