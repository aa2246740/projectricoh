from pathlib import Path
import argparse
import datetime
import json

ROOT = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
OUT = ROOT / 'research/review_harness_c_switch'


def read(relative):
    return json.loads((OUT / relative).read_text())


def link(title, relative):
    return '[' + title + '](' + str(OUT / relative) + ')'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--draft', action='store_true')
    args = parser.parse_args()
    stored = read('stored/summary.json')
    checks = read('evidence/check-results.json')
    warm = read('warm-audit/summary.json')
    static = read('evidence/static-audit.json')
    before = read('evidence/manifest-before.json')
    intake = read('evidence/intake.json')
    records = read('paired/complete.json')
    if (OUT / 'retry/complete.json').exists():
        records += read('retry/complete.json')
    elif args.draft and (OUT / 'retry/progress.json').exists():
        records += read('retry/progress.json')
    by_job = {}
    for row in records:
        if row['returncode'] == 0:
            by_job.setdefault(row['job'], {})[row['side']] = row
    jobs = read('selected-queue.json')['jobs']
    labels = {'locked': 'MOUNT locked', 'transitions': '28mm transitions',
              'values': '28mm values', 'nested': 'MOUNT nested', 'half': '28mm half'}
    table = []
    completed = 0
    scalar_count = 0
    json_count = 0
    for job in jobs:
        name = job['name']
        file = OUT / 'comparisons' / (name + '.json')
        if file.is_file() and {'python', 'c'} <= by_job.get(name, {}).keys():
            proof = json.loads(file.read_text())
            py, c = by_job[name]['python'], by_job[name]['c']
            completed += 1
            scalar_count += proof['compared_values']
            json_count += proof['json_files']
            table.append(f"| {labels[job['group']]} | {py['wall_seconds']:.3f} | {c['wall_seconds']:.3f} | {py['cpu_seconds']:.3f} | {c['cpu_seconds']:.3f} | {proof['packets']['python']:,} | {'一致' if proof['equal'] else '存在差异'} |")
        else:
            table.append(f"| {labels[job['group']]} | 补跑中 | 补跑中 | | | | 尚未判定 |")
    if not args.draft:
        assert completed == 5
        assert all(read('comparisons/' + job['name'] + '.json')['equal'] for job in jobs)
        assert read('evidence/manifest-after.json')['passed'] == 13724
        assert read('evidence/tools-after.json')['unchanged'] is True
        assert read('evidence/cleanup.json')['remaining_review_processes'] == []
    elapsed = (datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(intake['started_utc'])).total_seconds()
    pin_c = 'a6c79c5bf3d1e9ee4838805e00d6ab919797e487895d66e39a7afe04e2e72058'
    body = f'''修改后再采用

本轮发现三项 P1。最直接的新目录反例是回调改变 `WriteEvent` 名称绑定后，Python 的写入验证函数抛错，C 却跳过该函数并通过。另有指定 g139 用例从 `OBSERVED_P1` 变成 `FAIL`，以及测试本体改变后复用旧 PASS。性能数字和通过的子集不能关闭这些差异。

本报告评审主机回归后端及其可选入口，不作固件 DAT 的上卡结论。全部工作在本机离线进行。

## 输入与证据身份

仓库根为 `{ROOT}`。外置卷为可写 APFS，UUID 为 `14BE04EB-AF49-497E-B36A-B078B2F7C5E8`。

| 输入 | SHA256 |
| --- | --- |
| 交付 SHA256SUMS，13,724 项 | `{before['manifest_sha256']}` |
| 正常 API5 C 库 | `{pin_c}` |
| g150 正式 DAT | `c4878f6600cec8b2dfe973c0888bc9c61bcd3a51e6d20a63e12c7dcceb3f9b78` |
| g139 锁忙用例 DAT | `aab6c4f8d525dfda94fd33861c0a632b16f4d0df5481c7d9423e2bf820399e21` |
| 原 Python 后端 | `ffe210bd2f1ed8abc062c0b455677c4d4aa922bcda3e1092cd249cf494131292` |

开始时 13,724 项全部通过，核对耗时 {before['wall_seconds']:.3f} 秒。{link('开始清单', 'evidence/manifest-before.json')} 保留逐文件的预期值和实际值。正式交付前还核对同一清单，并复核受保护工具目录的普通文件 SHA 和符号链接文本 SHA；目录基线采集于本轮 05:56 UTC，早先测试也受同一写入规则限制。候选、原工具和模拟器未由本轮改写。最终收据见 {link('结束清单', 'evidence/manifest-after.json')}、{link('工具目录复核', 'evidence/tools-after.json')}。

## 本轮 P1-01：指定锁忙用例的状态改变

原 `research/review_g139/independent_checks.py busy-settings-exit --unit 50mm` 使用独立复制件运行。测试本体只重定向仓库根和输出位置，未修改验收断言。两侧都使用 g139 正式包和同一机身模型初态。

| 后端 | 状态 | 退出码 | 墙钟秒 | CPU 秒 | 指令包 |
| --- | --- | --- | --- | --- | --- |
| Python | OBSERVED_P1 | 0 | 182.455 | 179.549 | 20,932,506 |
| C | FAIL | 1 | 12.114 | 11.561 | 20,932,506 |

C 完成原用例函数后，在复制件第 598 行失败：

```python
assert cam.h.b.__class__.__module__ == 'python_backend'
```

原 Python 的值是 `python_backend`，C 的值是 `ccore.backend`。C 适配器在 [backend.py]({ROOT}/tools/speedlab/harness_release/ccore/backend.py:385) 只设置 `__name__` 和 `__qualname__`，没有保持导出类的模块身份。错误为 `AssertionError`，原始错误消息为空，完整位置保留在 C 的结果 JSON 中。

这项差异来自工具导出身份。两侧 805 条 RPC、824 条文件调用记录相同。另以原用例函数作 C 诊断，其返回的 154 个持久化值与 Python 相同；诊断没有执行上述 reporter 断言，不计作该用例通过，也不关闭 P1。

应修复导出身份，然后用保留全部验收断言的复制件复验，要求两侧都得到 `OBSERVED_P1`。证据为 {link('复制来源及差异', 'evidence/copied-busy.json')}、{link('原始双跑收据', 'busy/complete.json')}、{link('Python 原始日志', 'busy/python/raw.log')}、{link('C 原始日志', 'busy/c/raw.log')}、{link('诊断的持久化比较', 'busy-diagnostic/comparison.json')}。首次诊断把内存中的 tuple 与 JSON list 直接比较而记为不等；原记录保留，后者按实际保存的 JSON 类型重新核对。

## 本轮 P1-02：改变测试本体后复用旧 PASS

入口的 [identity 构造]({ROOT}/tools/speedlab/host_regression_r3/run.py:58) 没有绑定实际测试本体及其全部依赖；[validate_prior]({ROOT}/tools/speedlab/host_regression_r3/run.py:77) 核对参数、环境和旧产物，未重新核对当前测试源码。

本轮在自己的目录中构造两指令包的 M32R 身份自检，并使用正式入口的 `--timeout-seconds 10800 --crc-implementation host <测试文件>` 形式运行。第一次断言 r0 为 7，C 得到 PASS。随后仅把该测试文件的期望值改为 8，当前输入的结果如下：

| 当前输入相同，期望 r0 为 8 | 入口退出码 | 保存的产品结论 |
| --- | --- | --- |
| C，同名续跑 | 0 | 复用旧 PASS，仍写 expected=7 |
| Python，新运行名 | 1 | FAIL，r0=7、expected=8 |
| C，新运行名 | 1 | FAIL，r0=7、expected=8 |

同名 C 的原成功收据 SHA 未变化，当前测试未执行。Python 和 C 的新目录 FAIL 产品 JSON，包括 `error` 字段，逐字节相同，SHA 为 `2636371529464c54c6b6becc4411a9bc3e568dc81abef76d902b67e23a629db3`。独立 `driver` 形式也复现同一问题。这是入口身份检查，不计入真实固件回归覆盖。

正常相同输入续跑、后端改变拒绝、产物改变拒绝、失败组拒绝恢复四个控制都符合预期；缺口只需改变测试本体即可复现。旧收据仍有非零指令数，因此只看计数不能确认当前断言已经执行。

恢复前应核对实际执行代码、依赖、完整输入及队列选择的当前身份；修复前应拒绝自动复用旧收据。证据为 {link('正式参数形式的完整记录', 'identity-args-r2/summary.json')}、{link('同名 C 的旧结果', 'identity-args-r2/c-after-driver-change.log')}、{link('新目录 FAIL 逐字节比较', 'identity-args-r2/fresh-error-comparison.json')}、{link('独立 driver 形式', 'identity/summary.json')}。第一次参数形式自检的缓存位置被保留运行器重定向，未完成，原目录保留；第二份使用指定 TMP 根。

## 本轮 P1-03：WriteEvent 全局绑定改变后漏掉调用和错误

使用真实 M32R 编码、对齐的 CPU store、正常 32 位地址和新输出目录，在执行前、断点回调中或写回调中把后端模块的 `WriteEvent` 名称改为记录函数。该函数保持相同参数，并返回原 `WriteEvent` 类型，没有修改类的构造方法。

| 名称改变时点 | Python 调用数 | C 调用数 | C 快速写次数 | 验收结果 |
| --- | --- | --- | --- | --- |
| call 前 | 2 | 0 | 2 | Python PASS，C FAIL |
| 第一条 store 前的断点 | 2 | 0 | 2 | Python PASS，C FAIL |
| 第一条 store 的写回调，随后移除该回调 | 1 | 0 | 1 | Python PASS，C FAIL |
| 断点修改，禁用快速写过滤作控制 | 2 | 2 | 0 | 一致 |

三次不一致时，C 都执行了两个指令包，fallback_calls=0，事后 `_c_compatible()` 仍为真。

进一步把同一名称绑定为写入验证函数，实际 store 到 `0x200000` 时抛出 `AssertionError('write event validation stopped')`。原 Python 实际调用该函数并 FAIL；C 没有调用，正常执行到返回并 PASS。禁用快速写过滤后，两侧都 FAIL，错误类型、消息及错误后的 CPU/映射内存状态相同。

再用交付入口的正式参数形式和新运行名执行同一验证，Python 入口实际退出 1、错误前完成指令包为 0；C 入口实际退出 0、完成 2 个原生指令包，产品包装结果为成功。这是当前输入下的 C 通过、Python 失败，不涉及续跑或旧产物，也不只是对拍脚本自行标记的状态。

根因在 [全局对象捕获]({ROOT}/tools/speedlab/harness_release/ccore/backend.py:396) 与 [快速写]({ROOT}/tools/speedlab/harness_release/ccore/trace_filter.inc.h:60)。实现保护了当时捕获的事件类及其构造方法，却没有保护 `base.write.__globals__['WriteEvent']` 的当前绑定。原类没有改变，兼容性检查仍放行，C 直接写内存并省去新的事件函数调用。

应把实际全局名称解析也纳入保护，在入口及回调返回后核对；变化时保留原调用顺序和错误，执行原 Python 写路径。只保护旧类的 `__init__` 不足以关闭这项 P1。证据为 {link('五个名称绑定样本', 'global-resolution/summary.json')}、{link('C 通过而 Python 失败的完整状态', 'event-validation/summary.json')}、{link('正式入口的实际退出码和产品', 'event-entry/summary.json')}、{link('记录函数检查脚本', 'resolution_globals.py')}、{link('错误路径检查脚本', 'event_validation.py')}。这些短检查不计入真实固件回归组数。

## 新增真实回归

已完成 {completed}/5 组。使用 g150 正式 DAT、原组内循环、断言和步数上限，两侧各用新运行名和独立产品目录，不复用已有结果。入口及路径适配差异保存在 {link('复制清单', 'evidence/copied-entry.json')}。计时是本轮单次运行的入口墙钟和子进程 CPU，单位为秒，包含入口身份核对；只报告实耗，不认证稳定提速倍数。

| 组 | Python 墙钟 | C 墙钟 | Python CPU | C CPU | 每侧指令包 | 验收比较 |
| --- | --- | --- | --- | --- | --- | --- |
{chr(10).join(table)}

已完成组共核对 {json_count} 份 JSON、{scalar_count:,} 个标量。状态、断言数据、S 区摘要、单元行、调用顺序及其他产品字段按类型和值严格比较。仅运行器包装结果的根 `/seconds` 排除；绑定依赖按实际文件 SHA 单独核对。独立目录造成的适配器路径、解码文件名和参考库 PID 元数据另列，原始文件 SHA 全部保留，没有排除产品中的错误或观察状态。逐组证据见 {link('新增双跑比较', 'comparisons/summary.json')}、{link('首次运行及准备失败', 'paired/complete.json')}、{link('新名称重跑', 'retry/complete.json')}。transitions、values 的第一次名字含 `+`，在模型启动前被拒绝，未计入回归覆盖。

## 审计过滤、错误路径及开关

静态已证：`audit_filter.inc.h` 只实现原 `watch` 的首个范围判断。命中七段范围时返回给原 Python 写回调；来源检查、计数和异常仍在原 `watch`。地址加长度用 64 位计算。该 `watch`、`touches_ui` 的代码或其 globals/builtins 版本变化时不作提前返回；这不包含前述 `WriteEvent` 名称绑定缺口。

主机已证如下，均读取结构化结果核对，没有把退出 0 单独当作通过：

| 检查 | 本轮结果 |
| --- | --- |
| 方法、接收对象、父类解析、属性访问及 trace | 15+4+6+6+19，共 50 项一致。先前父类 Cpu.op 改变的两个指定反例当前一致；它们没有覆盖上文新增的全局名称绑定。 |
| 实际编码逐条对拍 | 6,080 条和 40 个边界一致。 |
| 七段范围边缘 | 90 项一致。 |
| 原 UI watch 的 helper、代码、globals、范围及写来源变更 | 17 项一致，错误类型和消息保留。 |
| 先实际过滤一次，再在回调中改变依赖 | 6 项一致。控制实际快速写 3 次，改变依赖后实际快速写仅 1 次，余下两次正确计数。 |
| 实际 C 变异库 | 少报一次审计命中被检测；关闭方法解析保护后两个反例重新产生差异。后者采集脚本退出 0，但结构化 mismatches=2，已按差异处理。 |
| 受地址约定的停止与错误输入 | 20 项一致，覆盖未映射及未对齐读写、只读写入、MMIO 错误、回调异常、递归调用和参数错误，并比较错误后的完整寄存器及映射内存。 |
| 默认和损坏控制 | 12 项控制符合预期。默认及显式 python 不加载 C，与原 Python 的验收 JSON 逐字节相同。缺清单、缺库、ABI、API、库 SHA、源码 SHA 不符均明确失败，无静默回退。 |

API 版本控制使用真实编译库，只将当前 C 源码的 API 常量改为 4；有效源码及库身份核对通过后，加载器明确报 `C core API differs`。原库和原源码没有改动。运行时不兼容的方法或回调按 Python 语义回退，是另一条有统计记录的路径。

证据为 {link('逐项结构化汇总', 'evidence/check-results.json')}、{link('短检查耗时和命令', 'short/complete.json')}、{link('运行中变更', 'entry/local/gates/audit-changes.json')}、{link('先过滤后变更', 'warm-audit/summary.json')}、{link('实际变异', 'evidence/mutations.json')}、{link('开关与损坏控制', 'switch/summary.json')}、{link('错误及状态快照', 'errors/summary.json')}。

另测的三个 trace 配置含负端点或超过 64 位的端点，超出后端声明的无符号 32 位地址约定。Python 继续执行，C 抛出 `OverflowError`，差异已原样保留；不将它们计入上述 20 项受约定输入的通过数。

## 既存 15 组、性能与 tape 的独立复核

重新读取全部产品和进程收据，15 组各侧均执行 1,003,906,921 个指令包，全部正常 C 指令数相同，fallback_calls 和 fallback_steps 均为 0。总墙钟为 9,517.064717 对 1,537.792034 秒，即 158.62 对 25.63 分钟，比值 {stored['wall_ratio']:.4f}；CPU 为 8,973.515161 对 1,327.871509 秒，比值 {stored['cpu_ratio']:.4f}。报告的 6.19 和 6.76 算术成立。

534 份 JSON、1,787,616 个标量全部一致。这个数包含前置 user-tool 的 12 份 JSON、953 个值；15 个实测组本身是 522 份、1,786,663 个值。来源及非验收元数据按上述范围单列。逐组原始 SHA、全部差异表和复算值在 {link('既存产物复核', 'stored/summary.json')}。

这些是既存每侧一次的配对观测，不是本轮新增五次重复测量。原运行按组交替先后，实际 worker nice 为 20，采样一分负载范围为 5.71–21.26。交付中另存的剖析记录显示 C 循环和方法兼容性检查仍占主要开销；该剖析未计入普通速度表，本轮没有重做剖析或外推完整 81 组。

参考库逐库保留安装名、节地址及原始 SHA。执行代码、只读常量等节的字节多重集合一致；50mm safety 的 `__eh_frame`、`__unwind_info` 不同。来源身份与数量一致，不宣称整库逐字节相同。见 {link('参考库节级复核', 'stored/reference-sections.json')}。

独立读回并逐字节比较现有 tape，确认 CPU 写入为 141 文件、10,008,700 条、252,728,678 字节；审计为 71 文件、994 条、41,186 字节。完整组的少报变异为 993 条，差异可检出。这批 g150 tape 比较的是同一 C 核心审计过滤关闭与开启两侧，不是 Python 与 C 的 g150 全量写入对拍。本轮未重新执行该完整 70 子进程录制。见 {link('tape 逐文件计数和字节比较', 'stored/tapes.json')}。

## SWITCH_CHECKLIST.md 的判定

当前清单不足以支持正式采用。其新运行名、实际计数、完整产物、方法回退和后续全矩阵要求有用，但需要补齐：

1. 加入已知 OBSERVED 与 FAIL 基线，逐项比较状态和错误；不能只要求运行器退出 0。保留本次 g139 原断言作为固定门槛。
2. 在恢复前核对测试本体、helper、输入数据及完整队列选择的当前身份。修复前禁止复用旧成功收据，同时修正 README 的续跑说明。
3. 加入全局名称绑定改变的三个反例及验证函数抛错的门槛，要求调用轨迹、异常和错误后的状态相同；不能只保护捕获时的类和函数代码。
4. 将正常 C 库的实际 API、缺库及版本拒绝、新目录默认行为列为可执行控制，并核对结构化结果。
5. 保留完整 81 组尚未执行的边界，修复三项 P1 后，在主线空闲时按实际保留矩阵复核，包含预期的失败及观察结果。

三项 P1 分别位于导出身份、入口恢复逻辑和原生快速写的依赖保护。已完成真实组一致，不能覆盖事件函数调用和验证错误被省去的反例。

## 执行边界与交付

只写本目录和 `/Volumes/Workspace/Scratch/tmp/projectricoh/review-cswitch/`。测试子进程受 {link('离线写入规则', 'fence.sb')} 限制，未联网、未作 Git 写操作、未访问相机或存储卡，未启动子代理。入口使用 `nice -n 15 /usr/bin/python3 -I -B`，保留运行器再降低优先级后的 worker 为 nice 20。真实组及锁忙检查超时均为 10,800 秒，超过本次及历史用时三倍。

大部分时间仅一个真实回归负载，短检查顺序执行。一次产物核对与 half、锁忙诊断重叠约 0.72 秒，短时有三个本轮计算进程，违反两进程上限；此后辅助检查串行。三项 P1 来自该重叠之外的运行。准备失败和首轮比较器的 tuple/list 记录保留于 {link('执行说明', 'evidence/execution-notes.json')}，未改记为产品通过。

本轮截至报告生成已用 {elapsed / 60:.2f} 分钟。自己的测试进程已结束，TMP 已删除；收尾时核对没有残留本轮进程。交付 SHA256SUMS 覆盖最终报告、脚本及原始证据，路径相对仓库根。见 {link('收尾收据', 'evidence/cleanup.json')} 和 {link('SHA256SUMS', 'SHA256SUMS')}。完整 81 组、g150 Python/C 全量 CPU/写入录制及设备验收均未在本轮执行。
'''
    if args.draft:
        body = body.replace('本轮发现三项 P1。', '复审仍在补跑，本轮已发现三项 P1。', 1)
    (OUT / 'REVIEW.md').write_text(body)
    print(json.dumps({'draft': args.draft, 'completed_real_groups': completed, 'review_bytes': len(body.encode()), 'elapsed_minutes': elapsed / 60}))


if __name__ == '__main__':
    main()
