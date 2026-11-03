不可以切换

主机已证 P1-01 仍有漏执行路径。普通转发钩子通过 `__getattr__` 转发内层 `StepHook` 的属性后，会被误当作已声明钩子，自己的 `__call__` 被批量执行跳过。八步负载使原版得到 RAM/r0=`0x55`，批量版得到 `0`，两边仍返回 `max_steps`。真实冷启动 `storage_run.Machine` 也复现了内存和完整快照差异。P1-02 的设备缺声明传播已通过本轮检查。

本结论针对 fast 档离线模拟器的替换资格。没有修改被审对象，没有切换任何工具，也没有访问网络、相机或存储卡。以下通过项均为主机模型证据，不能作为诊断程序上测试卡的独立放行结论。

## 复审身份与边界

- 仓库根为 `/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh`。写入仅限本复审目录及指定 TMPDIR。没有 git 写操作，没有开子代理。
- 原库 SHA-256 为 `ba1efa53ce71dbd5632b2a540d0ca3ad02c395498688ce90089a41d85e8c07ff`。
- 批量库 SHA-256 为 `018a6d9731d54b6b27e6729d4a8903a4cab5b8763a0ce92467ad91e02d2d8c95`。
- 被审 `backend.py` SHA-256 为 `430c7b908f035baf2384b59254c12736e62fb7cb669d9d2e9fab960beb832c3b`；`outputs.py` 为 `9aeeca7850b1ea71f3ac187221845aaa64f89a8d448f64f52bbdfabdfa8372a5`。
- 开始时复核实现清单 386/386、原版清单 45/45、速度研究清单 190/190、上轮复审清单 101/101。另记录八个受保护目录内 110,751 个既存文件的哈希。见 [inputs-before.json](local/inputs-before.json) 和 [prepare.log](local/prepare.log)。
- 模拟入口均由 [run_check.py](run_check.py) 使用 `nice -n 10 /usr/bin/python3 -I -B` 启动；脚本的串行子进程继承 nice 值。本轮最多两个模拟进程同时运行，全部以前台 `subprocess.run(timeout=...)` 等待。状态比较每侧超时 7200 秒，M2b 10800 秒，短用例 1800 秒，均超过相关实测耗时的三倍。命令、退出码、耗时见 `local/*-process.json`。
- [scope_guard.py](scope_guard.py) 限制 Python 写入路径，拒绝网络和其他外置介质访问。指定 TMPDIR 为 `/Volumes/Workspace/Scratch/tmp/projectricoh/review-emulator-batch-r2`，交付前删除。

结束时全目录冻结复核为 `INCOMPLETE`。两个既存文件发生变化，另有四个文件新增，详见下文“输入复核”。不能宣称整个仓库在本轮期间保持冻结。

## P1-01：普通转发钩子仍被静默跳过，OPEN

静态位置为 `tools/gxr_emulator_batch/backend.py:453` 和 `backend.py:61`。根层和前驱层都用 `getattr(..., 'batch_plan', ...)` 取计划，没有确认这一层是否为 `StepHook`。`README.md:29` 明确承诺“钩子不是 StepHook，链里有一层不是”时整条链逐条执行，实际代码不满足这项承诺。

反例使用普通可调用对象，新增观察逻辑后转发已有钩子的属性：

```python
class ForwardingHook:
    def __getattr__(self, name):
        return getattr(self.wrapped, name)

    def __call__(self, cpu):
        self.calls.append(cpu.steps)
        if cpu.steps == 3:
            cpu.write(0x4000, bytes.fromhex('00000055'))
        self.wrapped(cpu)
```

这个对象不是 `StepHook`，没有为自己的观察逻辑声明计划或补推进。内层 `StepHook` 的计数计划本身正确，没有新增设备或错误截止数字。批量执行却取到了内层方法，只补推进内层，漏掉外层观察逻辑。

[forwarding_hooks.py](forwarding_hooks.py) 分别测试运行中安装在根层，以及放在 `StepHook` 链中间。

| 接入方式与实现 | 观察钩子调用 step | RAM `0x4000` | r0 | 停止结果 |
| --- | --- | --- | --- | --- |
| 根层，原版 / 副本逐条 | 0 至 7 | `00000055` | 85 | `max_steps`，8 步 |
| 根层，副本批量 | 只有 0 | `00000000` | 0 | `max_steps`，8 步 |
| 中间层，原版 / 副本逐条 | 0 至 7 | `00000055` | 85 | `max_steps`，8 步 |
| 中间层，副本批量 | 无调用 | `00000000` | 0 | `max_steps`，8 步 |

两项批量结果都没有 `undeclared-hook-steps`。完整寄存器、RAM、计数和停止结果见 [forwarding-hooks.json](local/forwarding-hooks.json)、[forwarding-hooks.log](local/forwarding-hooks.log)。

[machine_forwarding.py](machine_forwarding.py) 再从原厂 MAIN 构造实际 `storage_run.Machine`，以普通转发钩子记录次数，并写入映射 RAM `0x27fff000`。三方均执行 1000 步并返回 `max_steps`，原版和副本逐条的次数及 RAM 值均为 1000，批量版均为 5。批量统计为 995 步在 C 中执行。三方 CPU 寄存器和原有设备状态相同，内存及完整快照不同。见 [machine-forwarding.json](local/machine-forwarding.json)。这是当前 fast 运行方式的可复现差异，不能按未来新增设备的流程问题降为 P2。

最小修复方向是在 `_run_batch` 根层和 `StepHook.batch_plan` 前驱层检查真实钩子类型；任一普通层都报告未声明，整条链逐条执行。不能用转发出来的内层方法代表外层声明。修复后应保留上述根层、中间层和真实 Machine 三项回归，再复核本轮通过项。本轮没有改被审代码。

## 1. 原反例与新增钩子用例

- 上轮 `reproduce_hooks.py` 原样复制后执行，三方均在 step 0 至 7 调用普通钩子，RAM/r0=`0x55`，`max_steps`。见 [reproduce-hooks.log](local/reproduce-hooks.log)。简单普通函数的运行中安装问题已修复。
- 实现方 `hook_cases.py` 原样复制后执行，6/6 三方一致，包含 30 万步的启动设备缺声明情形。见 [hook-cases.json](local/hook-cases.json)。
- 新写 [extended_hooks.py](extended_hooks.py)，四项均三方一致。一次 MMIO 写回调及同一步写观察回调分别换钩子，覆盖同一批次、同一条指令内两次替换；另测单个回调内连续两次替换。中间钩子层分别失去 `batch_plan`、失去 `batch_skip` 后再恢复，两项都记录 5 步 `undeclared-hook-steps`，恢复后继续批量。比较完整 CPU 快照、各层计数和回调时序。见 [extended-hooks.json](local/extended-hooks.json)。

这些通过项不覆盖上述普通转发层。P1-01 因此仍为 OPEN。

## 2. 四个补声明设备

[device_cases.py](device_cases.py) 在原版、副本逐条、副本批量各执行短负载，保存 123 份完整快照，逐值比较 41 个对应状态点。快照包括全部 CPU 寄存器、映射内存、已接入设备的全部快照字段；面板另含所有自身字段。41/41 相同。原始文件在 [device-cases/](local/device-cases/)，逐点结果见 [device-comparison.json](local/device-comparison.json)。

| 设备及静态位置 | 状态边界与结果 |
| --- | --- |
| SIO2，`board.py:108`、`:119` | 测试排队、deadline 前一拍、到期点、实际完成，随后使能 TX IRQ，以及 IRQ91 在服务期间的延迟与 EOI。`pending` 是绝对 step，安全区间内无计数需要补，新增空 `batch_skip` 正确。 |
| I2C，`board.py:230`、`:237` | 测试 START、寄存器选择、写入、读方向 START、接收、实际读值、错误方向和 STOP；包含 IRQ103 服务期间到期后等待 EOI。绝对截止不需补计数，状态变化在逐条截止步执行。错误方向的停止原因和完整快照也相同。 |
| 中断控制器，`devices.py:351`、`:355`、`:359` | 测试 IE 关闭、右半字暂不进入、下一字边界进入、已有在服务 IRQ 延迟新 IRQ、EOI 后进入。空补推进与 `NEVER` 计划成立的前提是聚合层传递 `batch_armed()`；`devices.install` 已传递，C 在可进入点退出。 |
| 面板，`panel.py:65`、`:87` | 测试 ADJ 按下、GPIO 扫描行升高/降低前后、HALF/FULL 按下和释放。输入将变化时计划为 0，其余步没有状态变化，空补推进正确。 |

中断控制器的 `NEVER` 不是可脱离中断停点单独使用的保证。本轮独立设备负载和现有入口都保留了 `irq_armed`。

## 3. `devices=` 覆盖与 P1-02

静态枚举全部五处 `StepHook(...)`，逐项对照 `tick` / `advance`。再用 [entry_coverage.py](entry_coverage.py) 包装实际 `advance` 调用，记录对象并与整条链的声明集合比较；逐个移除实际推进对象的 `batch_skip`，共 37 次验证顶层计划返回 `None`。五个接入变体均无漏列，见 [entry-coverage.json](local/entry-coverage.json)。

| 入口 / 层 | 实际推进并已声明的对象 |
| --- | --- |
| `devices.install`，`devices.py:564` | Timer、BootSerial、InterruptController。BootSerial 的 `advance_irq` 内部调用同一个对象的 `advance`。 |
| `storage_run.Machine`，`storage_run.py:97` | StartupRegisters、DmaReceive、Board、SdHost；Board 内部实际推进 SioTransmit、I2cRegisters，二者也单列在该层 `devices=`。前驱层包含基础设备。 |
| `m2.run`，`m2.py:176` | 无 board 时为 StartupRegisters、DmaReceive；有 board 时增加 Board、SioTransmit、I2cRegisters。idle 选项引用的 Timer 由基础层声明。 |
| `m2_checks.restored`，`m2_checks.py:77` | StartupRegisters、DmaReceive，基础设备由前驱层声明。 |
| `Panel.chain`，`panel.py:90` | Panel。输入运行和快照入口均调用该方法接入；前驱链覆盖 Machine 设备。 |

结合 6/6 原钩子用例和中间层缺声明再恢复用例，P1-02 为 PASS。当前入口没有发现漏列设备的 P1。

P2-01，未来新增设备的声明仍依赖手工列表及正确计划。执行器不能自动发现未列入列表的推进对象，也不能识别错误截止数字。本轮没有发现既有入口漏列；继续要求新设备附带可执行等价用例。该项依本次门槛不阻断。

## 4. 独立全状态比较、M2b 和变异

[state_check.py](state_check.py) 从 MAIN 无卡冷启动，fast，相同面板与拨盘输入。原版与修复后批量版在 100 万步、1000 万步的 CPU、全部映射内存、全部设备状态、完整 `cpu.snapshot()`、面板全部状态及观察哈希均相同。

| 步数 | 两侧相同的标准全状态 SHA-256 |
| --- | --- |
| 1,000,000 | `9961a47ff91e318e972a3a712ea2448a51fe0ebd5faa396ee2ce6ab0e2eb88f7` |
| 10,000,000 | `84e51c8b3fb0f8b09c0d82c1d63d423fb55b339d001689bf84af7f2e6752f357` |

完整字段及内存分区哈希见 [state-step.json](local/state-step.json)、[state-batch.json](local/state-batch.json)。原版运行 198.1 秒，批量运行 14.9 秒，这些耗时仅用于执行记录与超时核对，本轮没有独立重测报告中的速度倍率。

[m2b_run.py](m2b_run.py) 独立执行无卡 5000 万步、续跑 500 万步、有卡 5500 万步，并重跑 board、M2、RPC、conformance 四组既有检查。结果 M2b 22/22，native tick 从 13742 增至 15409，有卡 Task8/28 等待状态及 native ready 符合检查。三个 Machine 长运行确实使用 fast 加批量；四组既有检查保留默认 debug 逐条模式。见 [m2b-review.json](local/m2b/m2b-review.json) 和 [m2b.log](local/m2b.log)。

入口副本仅调整复审目录、使用新 `declare_media` API，并选择实现方的批量回归适配器。M2b 断言规则未改，校验器身份记录在结果中。原样复制的脚本及路径改动见 [entry-copies.diff](local/entry-copies.diff)。

定时器变异在本轮修复后的 `devices.py` 上新建本地副本，仅把 `Timer.batch_plan` 改为 `return NEVER`。仍使用最终批量动态库。100 万步相同，1000 万步时 CPU、内存、设备、完整快照及观察哈希全部不同，标准全状态变为 `c3e1c405d748ccc0a3fa84b9e45fc76a26b19eb5fb95df14e0f0976726363658`，检查确实抓到错误。见 [timer-variant.json](local/timer-variant.json) 和 [变异源文件](local/timer-variant/devices.py)。该结果不再依赖 r1 的变异记录。

本轮没有重跑 M2c、g145/g146 文件回放或性能基准。它们不计为本轮新增主机证据。

## 5. 输出目录正常使用

原样复制执行 `output_cases.py`，11/11 符合预期。缺省输出、冻结输出、未声明或冻结介质均拒绝；快照重建提示指向批量副本。见 [output-cases.json](local/output-cases.json)。

[output_positive.py](output_positive.py) 不使用介质许可适配器，显式设置自己的 `storage_run.OUT` 并调用 `outputs.declare_media`，复制冻结卡种子到本复审目录。`BlockImage` 写入一扇区后重新打开读回相同，fast 加批量执行 10000 步返回 `max_steps`，正常生成结果和检查点。M2 覆盖检查也通过真实 `--output-dir` 写出三次短运行结果。见 [output-positive.json](local/output-positive.json) 及 [实际输出](local/output-positive/explicit-output.json)。未发现 `outputs.py` 误伤这些正常路径。

首次正向脚本尝试直接生成 FAT，遇到 `fat_image.create` 原有的 `git check-ignore` 要求，因为本复审目录未被忽略。没有改 Git 配置或取消该检查；正向运行改用实际回放所用的卡种子复制路径。首次记录保留在 [output-positive-initial.log](local/output-positive-initial.log)。调用 FAT 生成器时，显式声明介质目录之外仍须满足该原有要求。

## 输入复核与切换事项

全目录结束复核的 110,751 个既存文件中，110,749 个未变。变化文件为 `research/unit28_stock/REPORT.md` 和 `research/unit28_stock/emu_g146_trace.py`。另新增 `research/emulator_m2d/local/unit28-g146/final6/` 下的 DONE、GXRTRACE-final.bin、result.json，以及 `final7/card.img`。没有删除文件，符号链接未变。完整前后哈希见 [inputs-after.json](local/inputs-after.json)，复核进程退出码为 1，保留为 `INCOMPLETE`。

本轮没有写这些路径，Python 写入审计也禁止这些路径。推断存在并发任务，具体写入来源未确认。没有回写、删除或重新固定这些变化来抹平差异。上述两个 stock 文件及新增 final6/final7 结果没有用于本轮反例或通过项；不能沿用它们先前的冻结身份来报告当前 g146 回放等价。

被审工具、原版、实现研究、上轮复审和速度研究这五个目录的单独末次身份核对为 PASS，31,763/31,763 个文件未变，也没有新增或删除。见 [reviewed-inputs-after.json](local/reviewed-inputs-after.json)。它与全目录冻结复核分别记录，不替代后者。

P1-01 修复并重新复审前继续保留原版。以后切换时，fast 需显式启用批量；依赖逐条轨迹、MMIO 记录的检查继续使用 debug。调用方须显式设置输出及介质目录；旧速度候选快照必须按最终库和源码重新生成，保留 accepted/quiet 门槛。普通冻结检查点继续核实相邻 JSON、MAIN、设备拓扑及介质身份。

## 交付复核

[compare_results.py](compare_results.py) 从原始 JSON 及 123 份设备快照重新比较，生成 [comparisons.json](local/comparisons.json)。反例脚本返回 0 表示执行完毕，等价结论读取其中 `equivalent: false`，不能按进程退出码判为通过。

自写测试初轮的 I2C 事件顺序断言、状态 JSON 的 tuple 键序列化问题已修正后重跑，初轮日志仍保留，均未算作被审对象缺陷。输入冻结复核的退出码 1 则作为真实环境缺口保留。

从仓库根可重跑核心反例和比较：

```sh
TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/review-emulator-batch-r2 \
  nice -n 10 /usr/bin/python3 -I -B research/review_emulator_batch_r2/forwarding_hooks.py
nice -n 10 /usr/bin/python3 -I -B research/review_emulator_batch_r2/compare_results.py
nice -n 10 /usr/bin/python3 -I -B research/review_emulator_batch_r2/delivery.py verify
```

`SHA256SUMS` 使用仓库根相对路径，覆盖本复审目录的报告、脚本和证据，不包含清单自身。交付前清理指定 TMPDIR，并确认本轮模拟进程全部退出。
