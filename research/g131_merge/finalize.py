"""Freeze the verified delivery and write its review report."""
from pathlib import Path
import datetime
import hashlib
import json
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'research/g131_merge'
ENGINE = ROOT / 'firmware/engine_v51_g131'
PACKAGE = ROOT / 'firmware/package_v36_g131'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    sys.path.insert(0, str(WORK))
    from fences import enable, check_inputs
    enable()
    frozen = check_inputs()
    for name in ('verify_delivery', 'verify_source', 'verify_wrapper'):
        runpy.run_path(str(WORK / (name + '.py')), run_name='__main__')
    acceptance = runpy.run_path(str(WORK / 'collect.py'))['main']()
    ledger = WORK / 'evidence/runs.jsonl'
    lines = ledger.read_text().splitlines() if ledger.exists() else []
    for path in sorted((WORK / 'local/checks').glob('*/runs.jsonl')):
        for line in path.read_text().splitlines():
            if line not in lines:
                lines.append(line)
    ledger.write_text('\n'.join(lines) + '\n')
    delivery = json.loads((WORK / 'evidence/delivery.json').read_text())
    codegen = json.loads((WORK / 'evidence/codegen-four-categories.json').read_text())
    host = json.loads((WORK / 'host-results.json').read_text())
    rpc_path = WORK / 'evidence/rpc-summary.json'
    rpc = json.loads(rpc_path.read_text()) if rpc_path.exists() else {}
    target = [json.loads((WORK / ('target-' + str(i) + '.json')).read_text())
              if (WORK / ('target-' + str(i) + '.json')).exists() else {} for i in range(3)]
    target_counts = [str(item.get('cases', 'INCOMPLETE')) for item in target]
    windows = acceptance['inherited_windows']
    window_rows = []
    for item in windows:
        observed = item['observation']
        window_rows.append('| ' + item['unit'] + ' | ' + str((item.get('legacy') or {}).get('returncode', 'INCOMPLETE')) +
            ' | ' + str(observed.get('cut_hits', 'INCOMPLETE')) + ' | ' +
            str(observed.get('late_settings_stores', 'INCOMPLETE')) + ' | ' +
            str(observed.get('late_native_previews', 'INCOMPLETE')) + ' | ' + observed['status'] + ' |')
    queue_review = runpy.run_path(str(WORK / 'resume_review.py'))['main']()
    queue_rows = ['| ' + str(row['index']) + ' | ' + row['name'] + ' | ' + str(row['returncode']) + ' | ' + str(row['seconds']) + ' | ' + ('本轮重跑' if row['origin'] == 'resumed' else '沿用上一轮') + ' | ' + row['status'] + ' |' for row in queue_review['rows']]
    compile_rows = ['| ' + row['function'] + ' | ' + row['file'] + ':' + str(row['line']) + ' | ' + ', '.join(row['compiled']) + ' | 四类均通过 |' for row in codegen['reviews']]
    status = acceptance['status']
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec='seconds')
    report = f'''{status}

gen 131 将 g130 服务层的 H07 归属规则合入 gen 129 的 knobs v2 底版。本轮续跑第 19 至 37 项，没有改动产品源码或重建包。38 项队列均有完整记录，其中 31 项返回 0，7 项是已知 P2-03 窗口，返回 1 并保持 OPEN。指定非退步检查全部返回 0。

DAT SHA256：`{delivery['dat_sha256']}`。
ELF SHA256：`{codegen['elf_sha256']}`。

| 尺寸或包检查 | 最终值 |
| --- | --- |
| DAT | {delivery['dat_bytes']:,} B，generation=131 |
| BSS | {delivery['bss_bytes']:,} B |
| 主请求 | {delivery['loader_request']:,} B，上限 108,124 B，余量 {108124-delivery['loader_request']} B |
| 主请求计算 | 7,504 + align4(89,556 + 10,684) = 107,744 B |
| 第七段 | 20,776 B，与 gen 129 逐字相同 |
| 第七段组成 | GXTM 1,408 B、GXUI 1,984 B、GXKV2R2 17,384 B |
| 包内文件 | 30 个，29 个固定文件与 gen 120b 逐字相同 |

相对 gen 129，共九个同名文件变化，构建入口另从 `candidate/build129.py` 改名为 `candidate/build131.py`。91 个文件逐字相同，含 knobs 数学、数据、菜单模块及整个 resident 树。

| 源码差异 | 内容 |
| --- | --- |
| candidate/engine_services/services.c | 增加入口绑定与归属复核，settings 和 preview 按入口规则检查。 |
| candidate/engine_services/engine_services.h | 声明入口绑定接口。 |
| candidate/engine_services/native_seed.c | 收紧 tag 33 的 overlay 规则。 |
| candidate/containers/product/adapter.c | ingress 清零绑定，H01、H06、H07、H08 绑定当前入口。 |
| candidate/containers/product/src/firmware/card_container_v2/gate.c | generation 改为 131。 |
| candidate/containers/product/src/firmware/engine/core/eng_data.c | generation 改为 131。 |
| candidate/containers/product/ui_v2_data.c | generation 改为 131。 |
| candidate/common.py | 指向 gen 131 路径。 |
| candidate/containers/product/pack.py | 识别 generation 131。 |
| candidate/build129.py 改名为 candidate/build131.py | 构建身份改为 131。 |

三个服务源文件与 g130 冻结清单逐字相同。context.input_fields 与 input_sequence 在 knobs 底版中仅有定义及布局表，没有其他语义读写。rv_settings_owned 要求 inflight=1、当前 nonce、相同 entry_serial 和有效入口号；H01 用构造规则，H06、H07、H08 用严格规则；tag 33 总要求 overlay=32。preview op 1 在 IRQ 区间复核，恢复 IRQ 后到原生入口的 P2-03 窗口仍在。

settings、storage、make_plan、settings_match、eng_check_settings、apply_impl、write_word、recover_confirmed、ig_init、ig_stop、list_bind_impl 的函数正文未变。settings_pending、锁定、RPC 类型、S 地址、九行与 T、4+2 补偿未改。完整差异见 `source-change-vs-g129.patch`，服务差异见 `services-only.patch`。

| 补充验收 | 结果 |
| --- | --- |
| h07-parent，三个单元 | 首发达到八行菜单、mode=1、WB=9/9；晚到 S store 与预览全部为 0。 |
| h07-parent-preview，三个单元 | 晚到 S store 与预览全部为 0。 |
| ownership_settings、cold_reentry、cold_exit、settings_cases | 各三个单元，共 12 项全部返回 0。 |
| 50mm safety、locked、nested、cutpoints、exits | 五项全部返回 0。 |
| 主机金标准 | {host['golden']:,} 例与 {host['domain']:,} 例扩展检查通过。 |
| 全菜单点 S 计划 | 共 {host['plans']:,} 项与 gen 127 逐字相同，三个单元分别 1,133、1,134、1,163 项。 |
| 最终 M32R 计算 | 三个单元分别 {', '.join(target_counts)} 例通过，使用最终目标 CRC 与整数辅助函数。 |
| H01 首发与重开 | 三个单元均为 mode=1、WB=9/9。重开检查先建立八行原生构造前提，再把模拟 S 改为 mode=3、WB=1/17，随后核对恢复。 |
| 四类编译码 | 12 个改动函数均检查地址与长度、文件操作、原生 UI、循环与内存；绑定最终 DAT 和 ELF。 |
| audit_records.py 通信复核 | 共 {rpc.get('complete_records', 'INCOMPLETE')} 条完整记录，最终 DAT 为 {rpc.get('final_dat_records', 'INCOMPLETE')} 条，全部 DAT 组状态 {rpc.get('status', 'INCOMPLETE')}。 |
| wrapper 自检 | 七项通过，ASCII 上限仍为 126，未整体替换整数。 |
| knobs v2 参考接口 | 3,430 点逐字一致；旧 settings 与批组继续执行原有比较断言。 |

以下编号按 queue.json 的零基下标。每行的 DAT 身份、结果路径和阶段名称保存在 `evidence/queue-complete.json`；原始账本保留在 `evidence/runs.jsonl` 和 `evidence/stage-runs.jsonl`。阶段项的用时为其步骤之和。同名重复执行共享结果路径，历史用时和返回码以账本为准，最终状态由末次完整结果复核。

| 编号 | 队列项目 | 返回码 | 秒 | 记录来源 | 状态 |
| --- | --- | --- | --- | --- | --- |
{chr(10).join(queue_rows)}

P2-03 保持 OPEN。旧 preview-window 在三个单元上均因切点未到达而返回 1，其中的普通预览不能计作失去归属后的预览。七次队列执行的返回码全部原样保留。补充观察在最终 ELF 的 rv_native_preview 桥接入口切换模拟父视图，保留原生入口的既有模型回调，再统计后续原生预览和 S 写入。

| 单元 | 旧检查返回码 | 补充切点次数 | 晚到 S store | 晚到预览 | 状态 |
| --- | --- | --- | --- | --- | --- |
{chr(10).join(window_rows)}

| 改动函数 | 源码位置 | 最终编译码承载函数 | 四类检查 |
| --- | --- | --- | --- |
{chr(10).join(compile_rows)}

settings_cases-50mm 首次运行在旧 Algorithm.compute 中报 ValueError，旧接口把 knobs v2 的旋钮向量按旧 tone 等级解释。新目录内增加 reference_v2.py，按传入的 552 B stock、base 与十维向量计算，配方元数据按完整 base 或旧解码器清零的 36 个未映射字节后的 base 逐字定位，使用已通过金标准的 knobs v2 主机接口，返回 552 B；旧默认向量 Tone=0、Amount=100 与其余零值明确转换为新的十维默认向量。旧检查的比较断言保留。适配接口另与全部 3,430 个已核对菜单点及 24 个旧解码默认值逐字比较通过。旧参考失败和适配固定 stock 假设的检查记录保存在 local/preparation，账本保留该次返回码；只采用重跑完成结果。wrapper 的两个版本及适用范围见 evidence/runner-revisions.json，早先通过结果仍绑定原执行版本。

上一轮中断后遗留的两个 cold_reentry-50mm 进程由用户停止。本轮开始时没有接续这些进程；旧残留不算第 24 项结果。第 19 至 37 项全部重新执行，第 24 项仅采用本轮完整返回码为 0 的结果。证据见 `evidence/resume-start.json` 和 `evidence/queue-complete.json`。

沿用的上一轮记录都核对最终 DAT 身份。早期辅助模块、布局及 H01 驱动的准备记录留在 `local/preparation`，不计作最终通过结果。H01 驱动建立原生构造前提后重跑，未更改原归属检查或产品代码。本轮只按路径执行受限旧脚本。接口诊断经新 wrapper 和系统围栏执行，仅记录签名、实例字段类型和返回类型，未查看或复制旧脚本源码。日志只汇总名称、返回码和计数。

写入围栏只允许本任务三个目录，并拒绝网络。理光字节均在被忽略的 local/，SD_ROOT 为指向本包 local/SD_ROOT 的相对链接。冻结输入共 {frozen:,} 项，结束复核全部未变。检查顺序执行；常规单项超时 3,600 秒，阶段项 7,200 秒，已有内部构建和目标执行器沿用原有限制。开工可核对的上一轮归属检查最高约 146 秒，3,600 秒超过其三倍；本轮逐项用时见上表。未访问相机、存储卡或网络，未启动子代理。

静态已证：源码范围、字段布局、四类编译码、固定文件、第七段及 DAT 与 ELF 身份。
主机已证：指定切点计数、金标准、最终 M32R 指令计算、菜单点 S 计划、H01 恢复、指定非退步检查及完整通信记录。
推断：入口绑定限制 H07 按 H01 构造规则认领原生父视图，观测计数与该规则一致。
未知：相机端调度、实际显示、拍摄、存储持久性及物理断电后的表现。

完整 81 组回归本轮未运行，交后续复审。本报告仅给出本轮指定范围的交付结论。

报告时间：{now}。
'''
    if status != '可以交复审':
        report = status + '\n\n尚有未收齐或失败的聚焦项目。\n\n' + '\n'.join([
            'DAT SHA256：`' + delivery['dat_sha256'] + '`。',
            '缺少检查：' + ', '.join(acceptance['missing']),
            '失败检查：' + ', '.join(acceptance['failed']),
            '未完成项目：' + ', '.join(acceptance['incomplete']),
            '详细计数见 evidence/acceptance.json。完整 81 组回归交后续复审。']) + '\n'
    (WORK / 'REPORT.md').write_text(report)
    (PACKAGE / 'DELIVERY.md').write_text('gen 131\n\nDAT SHA256：`' + delivery['dat_sha256'] +
        '`。\n\n30 个文件中，29 个固定文件与 gen 120b 相同。聚焦结果及继承窗口见 research/g131_merge/REPORT.md。\n')
    runpy.run_path(str(WORK / 'verify_words.py'), run_name='__main__')
    assert check_inputs() == frozen
    paths = sorted(p for base in (ENGINE, PACKAGE, WORK) for p in base.rglob('*')
                   if p.is_file() and not p.is_symlink() and p != WORK / 'SHA256SUMS')
    (WORK / 'SHA256SUMS').write_text(''.join(sha(path) + '  ' + str(path.relative_to(ROOT)) + '\n' for path in paths))
    print(json.dumps(dict(name='finalize', returncode=int(status != '可以交复审'),
        counts=dict(files=len(paths), frozen_inputs=frozen))))

if __name__ == '__main__':
    main()
