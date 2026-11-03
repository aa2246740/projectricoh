不可以切换

主机已证两个 P1：运行中安装普通钩子会静默漏推进；被推进的设备缺少批量声明时不会自动退回逐条执行。前一个反例已经改变 CPU 寄存器和 RAM，且仍返回 `max_steps`。按本次门槛，不能用这个版本替换原版来支撑诊断程序上测试卡的判断。

本轮只复审本机离线模型，没有改被审目录、固件或既有证据，没有访问网络、相机或存储卡，也没有做 git 写操作或开子代理。通过的主机测试不代表相机、物理卡或诊断程序放行。

## 复审身份和执行范围

- 原库 SHA-256：`ba1efa53ce71dbd5632b2a540d0ca3ad02c395498688ce90089a41d85e8c07ff`。
- 批量库 SHA-256：`018a6d9731d54b6b27e6729d4a8903a4cab5b8763a0ce92467ad91e02d2d8c95`。
- 开始时从仓库根复核实现清单 231/231、原版清单 45/45、速度研究清单 190/190。输入身份见 [inputs-before.json](local/inputs-before.json)，结束复核见 [inputs-after.json](local/inputs-after.json)。
- 模拟器入口均使用 `/usr/bin/python3 -I -B` 和 `nice -n 10`。最多同时两个模拟进程，使用前台 `subprocess.run(timeout=...)` 等待。g146 每侧超时 10800 秒，状态比较每侧 3600 秒，M2b 7200 秒，均高于相应实测耗时的三倍。命令、退出码和耗时保存在 `local/*-process.json`。
- `TMPDIR` 为 `/Volumes/Workspace/Scratch/tmp/projectricoh/review-emulator-batch`。Python 写入审计限定在本审查目录和该临时目录，禁止网络；介质许可只在审查进程内增加本目录。没有修改介质读写、CPU 或设备实现。

## P1 发现

### P1-01：一次 run 内更换钩子后，未声明钩子可以被静默跳过

位置：[backend.py:430](../../tools/gxr_emulator_batch/backend.py#L430)，尤其是入口处的 `hook = self.step_hook`、循环内继续使用旧 `hook`，以及结束批次时的 `if hook is not None`。

最小负载从普通 RAM 执行八步。入口断点返回 `False`，同时安装一个没有 `batch_plan` 的普通钩子。这个钩子计划在第 3 步把 RAM `0x4000` 写成 `0x55`；第 6 步的原生 `ld r0,@r1` 读取它。

| 实现 | 钩子调用的 step | 最终 RAM | 最终 r0 | 停止原因 |
| --- | --- | --- | --- | --- |
| 原版 fast | 0 至 7 | `00000055` | `0x55` | `max_steps`，8 步 |
| 批量副本 fast，批量关闭 | 0 至 7 | `00000055` | `0x55` | `max_steps`，8 步 |
| 批量副本 fast，批量开启 | 只有 0 | `00000000` | `0` | `max_steps`，8 步 |

入口时旧钩子为 `None`。断点在逐条路径安装新钩子后，后续循环仍把计划当作 `NEVER`，既不检查新钩子是否声明，也不补推进它。批量统计没有 `undeclared-hook-steps`，因此调用方拿不到错误提示。这属于 fast 执行语义差异，不依赖 debug 轨迹。

证据：[hooks.log](local/hooks.log)、[probes-step.json](local/probes-step.json) 和 [probes-batch.json](local/probes-batch.json) 的 `dynamic_plain_hook`。独立小脚本再次得到同样结果，并包含批量关闭的对照。可直接重跑，脚本不写输出文件：

```sh
cd /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh
TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/review-emulator-batch \
  nice -n 10 /usr/bin/python3 -I -B research/review_emulator_batch/reproduce_hooks.py
```

最小修复方向：每次准备新批次时重新读取当前钩子；钩子更换后重新判断声明，缺少声明就逐条执行。批次的补推进也应绑定生成该批计划的钩子。增加上述动态安装和动态替换用例后再复审。

### P1-02：新设备缺少声明时，既有入口直接抛异常

位置：[storage_run.py:101](../../tools/gxr_emulator_batch/storage_run.py#L101)、[m2.py:193](../../tools/gxr_emulator_batch/m2.py#L193)、[backend.py:437](../../tools/gxr_emulator_batch/backend.py#L437)。聚合计划直接调用设备的 `batch_plan()`；异常从批量循环抛出，没有转入逐条路径。

测试在 `storage_run.Machine` 中，用一个转发原启动设备普通功能、但没有 `batch_plan/batch_skip` 的适配对象替换 `devices['startup']`。原版正常执行四步；批量版在第 0 步抛 `AttributeError: device has no batch declaration`。这是明确报错，没有静默成功，但报告所说的自动逐条兜底并不存在。

证据见两份 `probes-*.json` 的 `undeclared_device` 和 [comparisons.json](local/comparisons.json)。最小修复方向：聚合计划先核对所有会被 `tick` 推进的设备是否提供两项声明；缺失时让整条钩子走未声明路径，并在 `StepHook` 各层传播这个结果。

未发现仅影响速度的 P2 缺陷。本轮没有重新测定 15.1 倍等速度倍率；记录的耗时只用于确认工作实际执行及超时是否充足。

## 1. 独立重跑状态哈希和 M2b

[state_compare.py](state_compare.py) 分别加载原版和批量版，从 MAIN 冷启动，无卡、fast、相同面板及拨盘输入。在第 100 万步和第 1000 万步比较 CPU、全部映射内存、设备字段、面板状态和观察器字段；另对完整 `cpu.snapshot()` 求哈希，不只比较报告摘出的总哈希。

| 步数 | 两版 state_hash.all | 完整快照及观察器 |
| --- | --- | --- |
| 1,000,000 | `9961a47ff91e318e972a3a712ea2448a51fe0ebd5faa396ee2ce6ab0e2eb88f7` | 相同 |
| 10,000,000 | `84e51c8b3fb0f8b09c0d82c1d63d423fb55b339d001689bf84af7f2e6752f357` | 相同 |

两点也与实现报告的归档状态相同。证据见 [state-step.json](local/state-step.json)、[state-batch.json](local/state-batch.json) 和 `comparisons.json/state`。没有据这两个点推断所有 fast 运行方式都等价；P1-01 就是这两个固定负载未覆盖的情形。

[m2b_run.py](m2b_run.py) 重新执行无卡 5000 万步、从本轮检查点续行 500 万步、有卡 5500 万步，以及四组原检查函数。M2b 22/22，证据见 [m2b-review.json](local/m2b/m2b-review.json)。三段 Machine 运行使用 fast 加批量；四组直接构造 Backend 的既有检查保持其 debug 默认值。验收断言沿用原 M2b，仅把源码前缀和库身份绑定到批量副本，并记录检查器 SHA。

M2c 21/21、本次未重跑的候选点和 ADJ 长段，只核对了原证据清单，不计作本轮独立重跑结果。

## 2. 实现者没有选择的 g146 负载

选择最新的 `research/emulator_m2d/local/unit28-g146/final5/`。该存档本来就是 `INCOMPLETE`，错误是 `'Dat' object has no attribute 'image'`，不能把这个错误归给批量实现。

复制当前 `research/unit28_stock/emu_g146_trace.py` 的 `final` 启动方式，输出改到本目录；把 `final5/card.img` 的相同副本分别作为两版初始介质，沿用存档的 placement。没有修复或越过原脚本失败分支。具体改动和原脚本身份见 [g146-entry.diff](local/g146-entry.diff) 及 `inputs-before.json`。

- 两边都在第 38,497,518 步到达 Task 8 的挂载返回点，随后 20 次原生调用的返回值、调用步数、任务及锁记录全部相同。
- `result.json` 仅删除顶层 `/seconds` 和 `/calls/0/boot/seconds`，其余字段完全相同；两边都在原有 `Dat.image` 错误处结束。
- 相对冻结初始镜像，两边均无扇区改变，改动表都是空表；最终镜像逐字节相同，SHA-256 均为 `9f484766670850b4b3c6fd05b135e2f824752641fe17f71ef04cb50e5f96623c`。

证据见 [逐条结果](local/g146/step/result.json)、[批量结果](local/g146/batch/result.json)、[扇区改动表](local/g146-sector-changes.json) 和 `comparisons.json/g146`。初始镜像已经包含 final5 留下的文件系统内容，因此启动步数不等于 final5 当年从新建镜像开始的步数。本次证明覆盖这个额外负载实际到达的路径；没有取得 g146 写入、第二次开机或完整诊断流程通过的证据。

## 3. 设备截止步数

逐项对照各设备的 `advance()` 与 `batch_plan/batch_skip`，并跑了九组安全区间和十组原生 CPU 完成边界负载。除 P1 的声明缺失情况外，已检查的现有设备计划没有发现漏掉状态变化的截止步。短负载在两版比较完整快照哈希、事件 step/PC、IRQ 队列及介质内容。

| 设备或路径 | 截止规则与核实结果 |
| --- | --- |
| Timer | 安全步数为 reload 减 counter。真正到期条件是加一后大于 reload。reload 为 0 和 3 的原生运行均相同。 |
| BootSerial | 首个 pending 时间减 clock 再减一；可以新拉起 IRQ94/95 时返回 0。完成两次收包及 IRQ 队列相同。MMIO 读自身多推进一次后会退出批次，再计算计划。 |
| InterruptController | pending 且未在服务时声明 armed；C 在 IE=1 且 PC 字对齐处停下，实际进入仍由原 `inject_interrupt()` 判定。顺序双半字的右半步不进入中断。 |
| HSP | 入队可以转 pending 时返回 0；倒计时安全长度为 delay 减一。到达时写接收寄存器并拉 IRQ87，两版一致。 |
| 单元 DMA | pending 减一；到期写 RAM、设置 completed、拉 IRQ123。原生短负载完整快照相同。 |
| SIO2、I2C | 用绝对 `backend.steps` 截止；到期状态变化、IRQ91/103、I2C 选择寄存器事件均一致。I2C 在 IRQ103 已服务时保持等待。 |
| MX | 新请求立即返回 0；pending 减一。完成时的寄存器、事件和 IRQ104 一致。 |
| 单元就绪包 | 两段 DMA 长度、最后短回复 11、无未完成请求等条件满足即返回 0；排三个包并只置一次 ready_sent。短负载及 M2b readiness 检查通过。 |
| SD 命令、停止 | 倒计时减一；错误收尾条件和卡中断电平变化立即返回 0。命令无卡错误及 stop-complete 的 step、PC、IRQ97 一致。 |
| SD DMA | arm 条件立即返回 0；现有 dma_delay 次推进只减计数，下一步才搬数据，因此安全长度是 delay。本轮读、写各 512 字节，数据、完成 step=5、IRQ126/97 顺序及最终介质哈希一致。 |
| Panel | 下一次 advance 会改变输入电平时返回 0。原生 stb 改变 ADJ 扫描行后，写回调仍看见旧列电平，下一步变为新电平；两版一致。 |
| m2 detail/idle | 实际调用 `m2.run()`，`detail_after=5` 时两边都记录 step 5 至 11；idle 测试在原生 idle PC 放短 NOP 窗口，`idle_tick` 均跳一次、补 8 个计数单位。这是选项逻辑测试，未当作真实启动证明。 |

代码位置：`devices.py:127–156, 348–419`，`peripherals.py:255–280, 412–438`，`board.py:108–137, 227–253, 392–454`，`sdcard.py:368–426, 454–510`，`panel.py:65–94`，`m2.py:176–204`。证据见 `probes-*.json` 的 `device_*`、`device_windows`、`irq_boundary`、`panel_transition`，以及 [m2-options-step.json](local/m2-options-step.json)、[m2-options-batch.json](local/m2-options-batch.json)。

## 4. 同一步 MMIO 的推进顺序

静态已证：[backend.py:250](../../tools/gxr_emulator_batch/backend.py#L250) 在转发总线访问时，先把 step 设到该指令起点，再 `_catch_up(self.steps + 1)`，之后才执行 read/write 回调。C 的 `info[0]` 在指令完成后更新，因此回调内看见的当前 step 与原版一致。普通内存只在计划允许的计数区间内直接访问。

主机已证：读、写 MMIO 的回调都在 step=6 看见设备 clock=7；普通 RAM 取指与同一步 MMIO 数据访问后的寄存器、内存和访问记录相同。

另外尝试了“普通 RAM store 与 MMIO load 并行”及反向组合。两版均以 GNU stop=304 拒绝，且没有数据回调。GNU `sim/m32r/mloop.in:182–185` 明确拒绝该核的非 NOP 并行右槽，故这两项只算错误路径一致，不算成功执行双数据访问的证据。被审默认 M32R 核仍由 GNU 解释指令，批量桥没有自行拆解或重排它们。

## 5. 解码缓存与自修改代码

静态已证：`bridge.c:164` 的每个 `gxr_step` 调用一次 `sim_resume(sd, 1, 0)`；`gxr_run` 每步仍走这条路径。GNU `sim/common/cgen-run.c:98–100` 在进入执行引擎前清缓存。构建配置的 `WITH_SCACHE=16384` 非零，运行参数把实际大小设为 256，`USING_SCACHE_P` 因实际大小大于零而成立。原来的额外逐步 flush 因此不承担跨步正确性。

实际交付动态库的 `_sim_resume` 中也有 `_scache_flush` 调用，批量结束处仍清缓存。见 [cache-run-disassembly.txt](local/cache-run-disassembly.txt) 和 [static-inputs.json](local/static-inputs.json)。

主机已证：原生 store 修改下一条可执行指令后，两版都执行新值 `r2=7`；再通过公开 write 修改已执行代码并重跑，两版都得到 `r2=9`。证据为 `probes-*.json/self_change`。本轮没有发现缓存缩小造成的语义差异。

## 6. RTE 寄存器组修正

对照原版 Python 条件与 `bridge.c:300–314`，两者都只在当前原始指令是 `10d6` 时保存 SM、SPI、SPU，并且只在该 RTE 执行后 SM 改变时补回两组栈。

独立跑 SM 与备份 SM 的四种组合：0→0、0→1、1→0、1→1。CPU 全寄存器和停止结果均相同；C 修正计数依次为 0、1、1、0。另跑非 RTE 的 `mvtc r0,psw`，它正确切换活动栈，C RTE 修正计数为 0。`banked_snapshot` 也随 M2b 原检查重新通过。证据见 `probes-*.json/rte_*`、`psw_change` 和 `local/m2b/regression-review.json`。

## 7. 漏声明兜底的实际边界

在 run 开始前已经安装的普通钩子，以及 `StepHook` 下链里的普通钩子，本轮都逐步执行，与原版相同。这部分兜底成立。

运行中改变钩子不成立，见 P1-01。被聚合入口直接推进的新设备缺少方法时也不成立，见 P1-02。已有设备若提供错误截止数字，执行器本身无法识别错误声明；实现报告的两个 Timer 变异只证明那两种错误能被其选定负载抓到，不能替代遗漏设备或运行中换钩子的检查。

最终短负载有 29 项两版直接对照，其中 27 项相同、上述两项不同；另有九组仅批量副本提供的安全区间检查，均与实际逐次 advance 的完整状态相同。首轮审查脚本遇到 tuple 键的 JSON 序列化错误，修正审查脚本后重跑；最终采用 `probes-*-r3-process.json`，没有把首轮脚本错误算作被审工具缺陷。

## 8. 后续修复通过后的切换事项

- fast 加 `GXR_EMULATOR_BATCH=1` 或 `set_batch(True)` 才启用批量；debug 依旧逐条。需要逐条轨迹、MMIO 日志或覆盖计数的检查继续使用 debug。
- 旧 `emulator_speed` 候选快照绑定源码、库、配置及运行身份。本轮复制无卡候选到审查目录，放行审查输出路径后实际调用加载器，得到 `boot identity differs`。修复后须用最终库和最终源码重建候选，保留原 accepted/quiet 门槛，不能只改元数据中的 SHA。错误消息的重建命令仍指向 `tools/gxr_emulator/speed_snapshot.py`，切换时要改用最终选定入口；本轮没有执行该命令。
- 原冻结库的普通检查点可以载入。本轮复制 `cold-speed-r1-stop.pkl/json` 后，批量副本的 `storage_run.Machine` 成功恢复到 50,000,000 步，恢复后的完整快照哈希与冻结检查点相同；M2b 原检查也经 `m2.restore` 使用了冻结库检查点。此类检查点仍须验证相邻 JSON、MAIN、设备拓扑和介质身份。证据见 [checkpoints.json](local/checkpoints.json)。
- 本副本默认输出和虚拟介质许可仍指向实现研究目录。迁移真实检查脚本时要显式迁移输出目录、介质副本许可和输入清单，防止覆盖被冻结的历史结果。本轮这些路径只在复审进程内重定向。
- 修复后先重跑两个 P1 反例，再跑状态、M2、真实文件回放；新设备和自定义钩子必须有可执行的声明缺失检查。

## 交付复核

[compare_results.py](compare_results.py) 从原始结果重新生成 `local/comparisons.json`，只删除明确的计时字段；g146 扇区表按全部 512 字节扇区逐项生成，最终镜像另做字节比较。原始快照、介质、命令记录及未通过的审查脚本首轮日志均保留。

```sh
cd /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh
nice -n 10 /usr/bin/python3 -I -B research/review_emulator_batch/delivery.py verify
```

`SHA256SUMS` 使用仓库根相对路径，覆盖本目录的报告、脚本和证据，不包含清单自身。结束时核对原先固定的 2337 个输入，清理指定 TMPDIR，并确认本轮模拟进程全部退出。
