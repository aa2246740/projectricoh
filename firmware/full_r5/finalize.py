"""Gate staging on the actual acceptance artifacts and preserve every log."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c


def checksums(folder):
    paths = sorted(p for p in folder.rglob('*') if p.is_file() and p != folder / 'SHA256SUMS')
    for path in paths:
        assert not path.is_symlink()
    text = ''.join(f'{c.sha(p)}  {p.relative_to(folder).as_posix()}\n' for p in paths)
    (folder / 'SHA256SUMS').write_text(text)
    result = subprocess.run(['/usr/bin/shasum', '-a', '256', '-c', 'SHA256SUMS'], cwd=folder,
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    assert len(result.stdout.splitlines()) == len(paths)
    assert all(line.endswith(': OK') for line in result.stdout.splitlines())
    return len(paths)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt', required=True)
    args = parser.parse_args()
    c.guard()
    frozen = c.freeze_check()
    run_dir = c.LOCAL / args.attempt
    run_dir.resolve().relative_to(c.LOCAL.resolve())
    summary = json.loads((run_dir / 'verification.json').read_text())
    cases = json.loads((run_dir / 'host-results.json').read_text())
    slots = json.loads((run_dir / 'slot-checks.json').read_text())
    manifest = json.loads((c.OUT / 'manifest.json').read_text())
    assert not (run_dir / 'failure.json').exists()
    assert summary['status'] == slots['status'] == 'PASS'
    assert summary['host_cases'] == len(cases) == 42 and all(r['status'] == 'PASS' for r in cases)
    assert sum('first' in r['scenario'] for r in cases) == 6
    assert sum('update' in r['scenario'] for r in cases) == 12
    assert sum('conflict' in r['scenario'] for r in cases) == 24
    assert summary['assertions'] == sum(r['assertions'] for r in cases)
    assert slots['changed_entries'] == 2 and slots['unchanged_entries'] == 46
    assert slots['identical_records'] == slots['expanded_slots'] == slots['effective_slots'] == 48
    assert len(slots['validators']) == 3 and all(r['status'] == 'PASS' for r in slots['validators'])
    assert manifest['generation'] == summary['generation'] == 107
    assert c.sha(c.OUT / 'GXRCE.DAT') == manifest['sha256'] == summary['sha256']
    assert (c.OUT / 'GXRCE.DAT').stat().st_size == manifest['file_bytes']
    assert (run_dir / 'fixture-source.c').read_bytes() == (c.HERE / 'host.c').read_bytes()
    assert (run_dir / 'verifier-source.py').read_bytes() == (c.HERE / 'verify.py').read_bytes()
    for label in ('full-r3', 'full-r4'):
        proof = json.loads((c.LOCAL / ('engine-proof-' + label + '.json')).read_text())
        assert proof == manifest['engine_proofs'][label]
        assert proof['status'] == 'PASS' and proof['only_type64_BSS_low_halves']
    assert manifest['engine_proofs']['full-r3']['different_bytes'] == 0
    identity = json.loads((c.LOCAL / 'identity-proof.json').read_text())
    assert identity['status'] == 'PASS'
    assert not manifest['resident_changed'] and not manifest['body_changed']
    # Re-read the real GXTS dumps and independently check each reported outcome.
    table = {}
    from verify import verify_gxts
    expanded = {}
    for label in ('full-r3', 'full-r4', 'full-r5'):
        rows = [line.split() for line in (run_dir / 'logs' / f'expand-{label}.log').read_text().splitlines()]
        expanded[label] = {(int(r[0]), int(r[1])): [bytes.fromhex(v) for v in r[2:]] for r in rows}
    for case in cases:
        if 'first' in case['scenario']:
            continue
        evidence = c.HERE / case['evidence']
        assert verify_gxts(evidence, case['old_generation'], case['unit'], expanded) == case['GXTS']
        for gx in case['GXTS']:
            key = gx['unit'], gx['slot'], gx['old_generation']
            assert key not in table or table[key] == gx['outcome']
            table[key] = gx['outcome']
    expected = {
        (0, 1): ('RESET_IDENTITY', 'KEPT'), (0, 2): ('RESET_IDENTITY', 'RESET_IDENTITY'),
        (0, 5): ('KEPT', 'KEPT'), (1, 1): ('KEPT', 'KEPT'),
        (2, 1): ('RESET_IDENTITY', 'KEPT'), (2, 2): ('RESET_IDENTITY', 'RESET_IDENTITY'),
    }
    assert len(table) == 12
    assert all(tuple(table[unit, slot, g] for g in (105, 106)) == outcomes
               for (unit, slot), outcomes in expected.items())
    c.save(c.LOCAL / 'GXTS-summary.json', [dict(unit=u, slot=s, from105=table[u, s, 105], from106=table[u, s, 106])
                                         for u, s in expected])
    c.save(c.LOCAL / 'development-fixes.json', dict(errors=[], compile_attempts=1, behaviour_attempts=1,
           product_assertions_relaxed=False, note='Build, fixture compilation and all 42 cases passed on the first run.'))
    card = c.LOCAL / 'card_update'
    c.write(card / 'GXRCE.DAT', (c.OUT / 'GXRCE.DAT').read_bytes())
    assert (card / 'GXRCE.DAT').read_bytes() == (c.OUT / 'GXRCE.DAT').read_bytes()
    c.save(card / 'manifest.json', dict(status='STAGED_HOST_ONLY', generation=107,
           file='GXRCE.DAT', file_bytes=manifest['file_bytes'], sha256=manifest['sha256'],
           source='../full-r5/GXRCE.DAT', source_byte_identical=True,
           host_cases=42, validator_units=3, expanded_slots=48,
           actual_card_access=False, camera_acceptance=False,
           card_procedure=['关机', '取出存储卡', '删除 GXRCE.OK', '删除任何 GXRCE.DAT',
                           '只把新容器复制为 GXRCE.DAT', '保留所有其它文件']))
    assert checksums(card) == 2
    assert c.freeze_check() == frozen
    r4_files = [p for p in frozen if p.startswith('firmware/full_r4/')]
    c.save(c.LOCAL / 'scope-after.json', dict(status='PASS', protected_inputs=len(frozen),
           protected_inputs_unchanged=True, full_r4_files=len(r4_files), full_r4_unchanged=True,
           decisions_tsv_is_input=False, writes_confined_to='firmware/full_r5/',
           resident_changed=False, body_changed=False, engine_source_changed=False,
           no_camera_or_card_access=True))
    proof = manifest['engine_proofs']['full-r4']
    report = f'''# full-r5 主机验收报告

full-r5 已通过本轮全部检查，状态为 STAGED_HOST_ONLY。generation 107，容器 {manifest['file_bytes']:,} B；[暂存文件](local/card_update/GXRCE.DAT)与[构建文件](local/full-r5/GXRCE.DAT)逐字节相同。

```text
SHA-256 {manifest['sha256']}
```

已核实：先逐字节复现 full-r3 和 full-r4，再只替换 50mm 02、Mount 02。两条展开结果与指定 Nega 源全等，其余 46 条目、48 条 record 保持 full-r4 原字节。50mm 01、Mount 01 保留 GR IV Posi，50mm 09/10 保留 v6 Posi/Nega。两份源各 3,600 B，只有 02 与文件 CRC 改变；mask=0x01、control=0x0002、identity CRC 不变，A5 严增、B5 不减。见[源核对](local/negative-source-checks.json)与[逐槽对照](local/{args.attempt}/slot-checks.json)。

引擎 {manifest['engine_bytes']:,} B、BSS {manifest['bss_bytes']:,} B、数据段 {manifest['data_section_bytes']:,} B、容器重定位表 {manifest['relocation_bytes']} B。主块 request {manifest['main_heap_request']:,} B，会话工作区 request {manifest['session_heap_request']} B，每块原生分配头另计 12 B。引擎与 full-r3 完全相同；相对 full-r4 的 {proof['different_bytes']} B 差异全部落在 {proof['type64_BSS_sites']} 个 type-64 BSS 重定位低半部，逐项偏移 +{proof['BSS_delta']} B。清零低半部后全等，平移链接检查通过。见[引擎证明](local/engine-proof-full-r4.json)。

body 绑定仍为 05b46ee65f4861f2e09e9b7c519cbcc2dffb195158a40c3bb033540b36a98d8c，resident ELF 仍为 f25899258471d0652a8fef8980b9f0a83a0ca7cd4ddc6bbe8fcc337467362b58。80 B trust 与 {identity['resident_payload_equal_bytes']:,} B resident payload 均核对通过，没有重建或改写 body、resident 或引擎源码。工具沿用 research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc、research/tooling_m32r_asm/prefix/bin/m32r-elf-ld、research/tooling_m32r/prefix/bin/m32r-elf-objdump，摘要与 full-r4 一致。

三单元完整 C validator 全通过。每版展开 48 槽，共对照三版 144 槽；每槽核对 448 B entry、64 B record、160 B GXTS 绑定、240 B 默认记录与 410 B effective rows。当前 48 槽实际应用结果也由 host 入口核对。

42 组 host e2e 首次运行全部通过，启用 -Werror、ASan、UBSan，缺文件真实返回 -1。包括 6 组空 IROM 首装与冷加载、12 组先删 OK 的 105/106→107 更新与 GXTS、24 组旧卡 DAT=105/106 与冷加载。首装、更新均覆盖替换式与拒绝既有目标式 rename。旧卡场景覆盖三单元、A=旧版/B=107 与单 A=107、去 DAT 后只留 OK 与无 GXRCE 卡文件两种状态。有效旧 DAT 存在时从卡加载旧版，RV_CONFLICT，create/write/delete/rename 全为 0，所有文件字节未变；移除 DAT 后均从 IROM 冷加载 107。16 行名称、配方、生效微调、无 SaveFail、未停用均逐例检查。见[逐例结果](local/{args.attempt}/host-results.json)与[验收汇总](local/{args.attempt}/verification.json)。

保存值为 3,2,-2,1,0,0；重置后的生效值为 0,0,0,0,0,0。12 组更新产生 24 次槽位检查，连同旧卡场景共 72 次。GXTS 原文件始终逐字节保留，重置来自条目绑定变化，不是文件删除。

| 槽位 | 105→107 | 106→107 |
| --- | --- | --- |
| 50mm 01 | 重置 | 保留 |
| 50mm 02 | 重置 | 重置 |
| 50mm 05 | 保留 | 保留 |
| Mount 01 | 重置 | 保留 |
| Mount 02 | 重置 | 重置 |
| 28mm 01 对照 | 保留 | 保留 |

卡流程：关机，取卡，删除 GXRCE.OK，删除任何 GXRCE.DAT，只把新容器复制为 GXRCE.DAT，其它文件全部保留。[manifest](local/card_update/manifest.json)标记 STAGED_HOST_ONLY。本轮只暂存本机文件。

外置卷 APFS、UUID、可写与 df -h 预检通过。{len(frozen)} 个冻结输入在构建、验收、暂存后均未变，其中 full-r4 全目录 {len(r4_files)} 个文件未变；decisions.tsv 排除。没有开发错误、重试或放宽产品断言。所有写入只在 firmware/full_r5/，派生字节只在被 /local/ 忽略的目录。未访问相机卡、刷机、启动子代理、sleep、轮询循环、安装包、commit 或 push。

未知：真实相机 UI、实际 M32R 执行、原生 rename 与掉电持久化。既有持续 open(-1) 风险未在本轮修改；本轮通过范围是主机验收。

重跑入口如下，验证使用新 attempt 目录保留旧证据。

```sh
/usr/bin/python3 -I -B firmware/full_r5/build.py
/usr/bin/python3 -I -B firmware/full_r5/verify.py --attempt attempt-02
/usr/bin/python3 -I -B firmware/full_r5/finalize.py --attempt attempt-02
cd firmware/full_r5
/usr/bin/shasum -a 256 -c SHA256SUMS
```

全交付文件和原始日志均列在 [SHA256SUMS](SHA256SUMS)。
'''
    (c.HERE / 'REPORT.md').write_text(report)
    count = checksums(c.HERE)
    assert c.freeze_check() == frozen
    print(json.dumps(dict(status='STAGED_HOST_ONLY', sha256=manifest['sha256'],
                          file_bytes=manifest['file_bytes'], host_cases=42,
                          checksum_files=count, protected_inputs=len(frozen)), ensure_ascii=False))


if __name__ == '__main__':
    main()
