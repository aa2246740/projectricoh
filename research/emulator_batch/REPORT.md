可以切换

本报告只覆盖主机上的离线模型。没有访问相机、存储卡或网络，没有做 git 写操作，没有开子代理，也没有切换任何现有工具、脚本或检查点。批量副本在 `tools/gxr_emulator_batch/`，用法见其 [README](../../tools/gxr_emulator_batch/README.md)。

r2 修复了第一轮复审（`research/review_emulator_batch/REVIEW.md`）提出的两个 P1 和两点附带问题，并在修复后的代码上重跑了全部等价证据。r3 修复了第二轮复审（`research/review_emulator_batch_r2/REVIEW.md`）指出的转发钩子漏执行路径，并重跑了钩子反例、第 100 万步全状态哈希和 M2b/M2c（见最后两节）。除特别注明外，下面各节的数字来自 r2 代码；r3 只改了钩子类型判断，正式运行里的钩子全是 StepHook，执行路径不变。第一轮和第二轮的原始输出分别在 `local/superseded-r1/`、`local/superseded-r2/`。

## 结论

- 五项等价证据全部取得：全状态哈希、M2b 22/22 与 M2c 21/21、g145 真实文件路径回放、变异自检、速度表。
- 速度：从 MAIN 冷启动到 500 万步（无卡，交替各 3 次），逐条版中位数 49,489 步/秒，批量版 741,230 步/秒，**15.0 倍**。5000 万步冷启动：逐条版 1039.8 秒（emulator_speed 存档），批量版 78.9 秒，约 13.2 倍。
- 默认仍逐条执行。批量只在 fast 档、调用 `set_batch(True)` 或设置 `GXR_EMULATOR_BATCH=1` 后生效。debug 档始终逐条执行并记录。

## 做了什么

1. **C 侧批量接口** `gxr_run(handle, budget, info, irq_armed)`（`bridge.c`）。每一步与 `Backend.run` 的一步相同：`gxr_step`，加上 RTE 寄存器组修正（已搬进 C，条件和动作完全照搬）。出现以下任一情况就停：下一步 PC 命中断点（集合在 C 侧，含设备钩子声明的 PC）；到达设备截止步数；一步内访问了 MMIO、写追踪范围或未映射地址（做完这一步再停）；有挂起中断且 IE=1、PC 在字边界；取指不在普通 RAM；GNU 出错；预算用完。
2. **普通内存留在 C 侧。** C 直接读写 `Backend.regions` 里同一批 bytearray，所以每次回到 Python 时，Python 看到的内存就是当前内容。`0x80000000` 视图只有在映射的确实是 RamView 时，才在 C 里转换。写追踪范围、只读区和未映射访问照旧回到 Python。
3. **设备截止步数。** 每个设备的 `batch_plan()` 给出“接下来有几次推进只是计数”，`batch_skip(n)` 一次补上：定时器、启动串口、中断控制器、HSP 收包、单元 DMA、SIO2、I2C、MX 启动、SD 命令/停止/DMA、卡中断电平、面板输入。一步内碰到 MMIO 时，先补推进到这一步，再调设备回调，与逐条版的顺序相同。
4. **需要逐步观察的情形**（截止设为 0，回到逐条执行）：中断控制器有挂起中断时（由 C 在可进入点停下）；任何设备下一次推进会改变状态时（中断拉起、DMA 或卡传输完成、HSP 包装入或到达、MX 请求或完成、SD 错误收尾、卡中断电平翻转、单元就绪包排队）；面板输出扫描电平变化时；`m2.py --detail-after` 之后的每一步；`m2.py --idle-tick` 的空闲 PC。钩子或其推进的任何设备没有声明时，回到逐条执行（本轮正式运行中这类步数为 0；第 r2 节的用例专门覆盖这条路径）。
5. **解码缓存。** GNU 的 `sim_resume` 每次调用都会清空解码缓存，而每次调用只跑一步，所以缓存大小不影响行为。原来的 16384 项每步都要清一张空表，占了批量运行的大部分时间，改为 256 项。批量循环里不再额外调用 `gxr_flush`：每步开头 `sim_resume` 自己会清一次，批量结束时再清一次。批量副本的逐条模式也因此快了约 1.3 倍（65,056 步/秒），状态与原版相同（见第一节末）。

## 证据一：全状态哈希

哈希口径与 `research/emulator_speed` 相同（`speed_snapshot.state_hash` 加观察记录哈希；ADJ 段另加调用轨迹哈希）。覆盖 CPU、全部映射内存、全部设备字段、面板按键，以及观察记录和调用轨迹。两边都从 MAIN 冷启动。逐条版是未修改的 `tools/gxr_emulator`（原库 `ba1efa53…`），批量版是本副本。见 `local/equivalence.json`、`local/eq-*.json`。

| 情形 | 第 100 万步 | 第 1000 万步 | 开机候选点 | ADJ 序列结束（按 12 万步，放 300 万步） |
| --- | --- | --- | --- | --- |
| 无卡 | 相同 `9961a47f…` | 相同 `84e51c8b…` | 第 33,004,041 步相同 `57355a70…` | 第 36,124,041 步：状态、观察、调用轨迹、未完成调用、面板事件都相同 `44622fb7…` |
| 有卡 | 相同 `0d0af170…` | 相同 `aea3c1b1…` | 第 42,572,307 步相同 `2c3bf995…` | 第 45,692,307 步：同上全部相同 `e9b6b893…`；卡镜像字节相同 |

另外三项独立对照：

- 两种情形下，批量版在候选点的哈希都等于 `tools/gxr_emulator/local/speed/*.snap.json` 里的 `state_hash`。ADJ 结束时的状态、观察和调用轨迹，也等于 emulator_speed 存档的冷启动 debug 结果（`*-adj-cold-debug.json`）。
- 批量副本关闭批量后，第 100 万、500 万步与原版相同（`local/eq-copystep-no-card.json`）。
- 交替测速的 6 次运行（两种实现各 3 次），第 500 万步状态完全相同。

## 证据二：累计检查

M2b **22/22**，M2c **21/21**，含从 MAIN 重新启动后读回：读回 4099 字节，SHA-256 `47bbc5ee…`。重新启动在第 31,468,582 步到达 `0x2010E23C`。见 `local/m2b-batch-r1.json`、`local/m2c-batch-r1.json`。

- 入口脚本复制为 `m2d_*.py`，标记了 `BATCH-COPY`，只把路径改到批量副本；`file_regression` 的面板钩子改用 `panel.chain`。检查规则未改。`acceptance` 里的“同一冻结库”这一项，改为绑定本副本重建的库。
- 所有 Machine 运行都是 fast 加批量（与 emulator_speed 一样用 fast）。四组既有检查（board_checks、m2_checks、rpc_check、conformance）按原样直接构造 `Backend()`，默认是 debug 档，所以这四组是逐条执行的，全部通过。
- 另把这四组强制改成 fast 加批量跑了一遍，作为额外记录，不计入 M2b（`local/existing-checks-fast-batch-batch-r1.json`）。13 个用例中 11 个通过。`native_serial` 和 `native_unit_info` 失败，原因是它们读取只在 debug 档才有的 MMIO 记录，属于设计如此。这一轮里 C 侧 RTE 寄存器组修正发生了 2 次（`banked_snapshot`）。
- **与 emulator_speed 逐条存档逐项比较**（`local/crosscheck.json`）：cold、stable、cold-card、reboot、files、full、read-error、write-error、no-card、readback 共十项。结果 JSON 除计时、源码身份、运行名和私有路径外全部相同。检查点状态全部相同；无卡的三份 pickle 逐字节相同（5000 万、5500 万步，以及 no-card 文件用例）。介质字节全部相同。
- 输入守卫（`local/final-input-guard.json`）：冻结输入未变；`tools/gxr_emulator`、`research/emulator_speed` 按各自 SHA256SUMS 未变；CHANGES 前缀未变。

## 证据三：真实文件路径回放（g145）

run2 的启动方式是 `research/unit28_stock/emu_g145_trace.py`（只读）。它从 MAIN 冷启动到 Task 8 挂载返回，在 Task 8 里按 diag.c 的 `trace_load/trace_flush` 发起原厂文件调用：load；flush 28mm 槽、50mm 槽、50mm 槽各一次；再从 MAIN 冷启动一次后读回。每个调用的步数上限是 1.5 亿。

脚本复制为 `g145_replay.py`，改动标记为 `BATCH-COPY`，只改了三处：实现选择、输出和 TMPDIR 路径、卡镜像来源。放好 GXRTRACE.BIN 的卡镜像只生成一次，SHA 与 run2 的 `card-0-placed.sha256` 相同，再分别复制给两次运行。

| 比较 | result.json 非计时字段 | 每个调用的返回值与步数 | 扇区改动表 | 读回内容 | 最终卡镜像 |
| --- | --- | --- | --- | --- | --- |
| 本轮逐条版 vs 批量版（r2） | 全部相同 | 相同（71 次调用） | 相同 | 相同 | 相同 `2674f99d…` |
| run2 存档 vs 批量版 | 全部相同 | 相同 | 相同 | 相同 | 相同 |
| run2 存档 vs 本轮逐条版 | 全部相同 | 相同 | 相同 | 相同 | 相同 |

两边状态都是 PASS。只有计时字段不同（顶层 `seconds` 和开机记录里的 `seconds`）。见 `local/g145-step-vs-batch.json`、`local/g145-run2-vs-batch.json`、`local/g145/run-*/result.json`。

## 证据四：变异自检

草稿副本只复制了 `devices.py`，放在 TMPDIR，通过 `compare.py --shadow` 遮盖副本里的同名模块。用完已删除；文件 SHA 记录在结果 JSON 里。

| 变异 | 第 100 万步 | 第 1000 万步 |
| --- | --- | --- |
| 定时器 `batch_plan` 恒返回“永不”（去掉截止步数） | 相同（定时器尚未启动） | CPU、内存、设备、观察全部不同 → 抓到 |
| 定时器截止步数晚 1 步 | 相同 | 全部不同 → 抓到 |

见 `local/mutant-timer*.json`。这两次在 r1 代码上运行；r2 没有改定时器的计划代码，也没有改哈希比较，所以结论不变。

## 证据五：速度

交替测速（`local/bench.json`）：从 MAIN 无卡运行到 500 万步，单进程，交替顺序，各 3 次，机器负载 6–15。

| 实现 | 中位数 步/秒 | 范围 |
| --- | ---: | --- |
| 逐条（原版） | 49,489 | 48,947–50,400 |
| 批量（r2） | 741,230 | 636,823–757,505 |
| 倍数 | **14.98** | |

r1 代码同条件为 50,526 / 761,618 步/秒（15.07 倍）。r2 每批多一次声明检查，差别在负载波动范围内。

整段运行耗时：

| 运行 | 逐条 | 批量 | 倍数 |
| --- | ---: | ---: | ---: |
| 无卡冷启动 5000 万步（input_run，带调用观察） | 1039.8 秒（emulator_speed 存档） | 78.9 秒 | 13.2 |
| 有卡冷启动 5500 万步 | 1144.3 秒（存档） | 84.4 秒 | 13.6 |
| 从 MAIN 重新启动到挂载返回（3147 万步） | 661.7 秒（存档） | 47.7 秒 | 13.9 |
| 无卡：MAIN→候选点→ADJ 结束（本轮并排） | 732.5 秒 | 58.8 秒 | 12.5 |
| 有卡：同上 | 928.1 秒 | 72.8 秒 | 12.7 |
| g145 两次开机加文件调用 | 2214.6 秒（开机 754.5 + 655.4） | 198.5 秒（开机 67.4 + 57.3） | 11.2 |

本轮并排运行时另有一个模拟进程在跑，存档时间来自不同机器负载，所以倍数以交替测速为准。

### 退出原因（每 100 万步回到 Python 的次数）

来自 r2 冷启动比较运行，见 `local/exits.json`。执行是确定性的，计数与 r1 完全相同。“截止”指批量跑到设备截止步数后退出。“额外逐步”指批量开始前设备就需要这一步，不另算一次 C 退出。“其他”包括写追踪范围的写（RTOS 任务状态、tick 计数等观察器）、未映射访问、非 RAM 取指和预算用完。

| 段 | 截止 | 额外逐步 | MMIO | 断点 | 中断 | RTE | 其他 | 合计 | 平均批长 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 无卡开机 0→3300 万 | 283 | 45 | 3,518 | 435 | 206 | 0 | 663 | 5,105 | 196 |
| 无卡开机前 100 万步 | 8 | 0 | 7,129 | 2 | 0 | 0 | 1 | 7,140 | 140 |
| 无卡 ADJ 段 | 400 | 80 | 4,663 | 896 | 248 | 0 | 1,037 | 7,243 | 138 |
| 有卡开机 0→4257 万 | 311 | 54 | 3,832 | 509 | 223 | 0 | 746 | 5,620 | 178 |
| 有卡 ADJ 段 | 398 | 80 | 4,645 | 887 | 261 | 0 | 1,031 | 7,222 | 138 |

- RTE 列为 0：修正在 C 里完成，不需要退出。10M 步的计数（`local/rte-count.json`，r1 代码）显示，开机窗口里没有一次 RTE 改变 SM。在 Python 执行的 400 次 RTE 都是监控替身陷阱槽，那些地址本来就是断点。C 侧修正路径由上面 fast 加批量的既有检查覆盖（2 次）。
- MMIO 是主要退出原因，但不是轮询风暴。在 1000 万→1200 万步窗口（`local/mmio-hist.json`，r1 代码），转发访问主要是每次定时器 tick 的中断处理：读中断号、写 EOI、写定时器应答、写中断配置，以及 RTOS tick 和任务超时这两个观察器写追踪，约 667 次 tick/200 万步。启动串口占 240 次。开机前 100 万步约 7,100 次 MMIO 是早期初始化。没有为提速改动设备或固件行为。
- 每 100 万步仍有约 1,000–1,600 步在 Python 里逐条执行（断点、中断进入、截止那一步）。剩余成本主要是每次退出的 ctypes 往返、设备计划计算，以及中断处理里的 MMIO 回调。

## 限制与切换前须知

- 只有 fast 档批量。debug 档的逐条轨迹、覆盖计数和 MMIO 记录不变，依赖这些记录的检查必须用 debug。
- 根钩子或任一前驱层的类型不完全是 `StepHook`（按真实类型判断：把属性转发给内层 StepHook 的普通包装对象、StepHook 的子类都算未声明，r3），或 `devices()` 列出的任一设备缺少 `batch_plan`/`batch_skip` 时，整条钩子链逐条执行（结果正确，但没有提速）；运行中安装或替换钩子也按这条规则处理（r2）。仍然无法自动识别的是：设备推进了却没有列进 `devices()`，或者声明了错误的截止数字。这两种会导致不等价，正是变异自检抓到的那类错误，新设备必须如实声明并加用例。
- 本副本没有默认输出目录和介质目录：调用方必须显式给出（模块 `OUT`、`--output-dir`、`outputs.declare_media`），冻结的研究目录一律拒绝（r2）。
- 写追踪范围在 C 侧最多 256 个，超过时报错，不会静默执行。
- 批量副本的库与原库 SHA 不同。emulator_speed 的候选快照把库 SHA 绑定在身份里，在批量副本中会拒用，需要重建。批量副本的 `m2.restore` 和 `storage_run` 也接受原冻结库生成的检查点（见 README）。
- 剖析结论“瓶颈在每条指令回一次 Python”已被证实：每步不回 Python 后，速度从约 5 万升到约 76 万步/秒。

## 文件

- 脚本：`hook_cases.py`（钩子与设备声明用例，r2/r3）、`r2_extended_hooks.py`、`r2_forwarding_hooks.py`、`r2_machine_forwarding.py`（第二轮复审反例副本，r3）、`output_cases.py`（输出目录用例，r2）、`compare.py`（冷启动并排、ADJ、退出统计）、`equivalence.py`、`bench.py`、`cumulative.py` 和 `run_cumulative.sh`、`m2d_*.py`（M2d 入口副本）、`g145_replay.py` 和 `g145_compare.py`、`crosscheck.py`、`exits.py`、`rte_count.py`、`mmio_hist.py`、`scope_guard.py`（写入限定在本目录、批量副本和 TMPDIR，禁网）、`limit.sh`（墙钟上限）、`delivery.py`。
- 证据在被忽略的 `local/`。`local/superseded-r1/` 是第一轮（复审前）的批量侧输出，`local/superseded/` 是解码缓存调整前的一次批量运行，都不计入。逐条版参照运行（`eq-step-*`、`g145/run-step`）用的是未修改的原版，两轮共用。
- 复核：`/usr/bin/python3 -I -B research/emulator_batch/delivery.py verify`。

## 复审修复（r2）

**P1-01：运行中更换钩子。** 修复位置 `backend.py` 的 `_run_batch`、`_catch_up`。
- 每准备一个批次都重新读取 `self.step_hook`，重新判断它是否声明；没有声明就逐条执行。
- 批次的补推进绑定到生成该批计划的钩子（`_batch_hook`）。所以即使 MMIO 回调在批次中途换了钩子，旧钩子也会补到正确的那一步，新钩子从下一步开始，与逐条版相同。
- 转发访问里的补推进移进了异常保护：出错就记为故障，不会穿过 GNU 边界。

**P1-02：设备缺声明。** 修复位置 `backend.StepHook`。
- 新增 `devices` 参数，列出这一层 `step()` 推进的全部设备对象，每次计划都动态求值。
- 任一设备缺少 `batch_plan` 或 `batch_skip`，这一层返回“未声明”，并沿 StepHook 各层向上传，整条钩子逐条执行。
- 各入口都已列出各自的设备：`devices.install`（定时器、串口、中断控制器）；`storage_run`（启动寄存器、DMA、板级、SIO2、I2C、SD）；`m2`、`m2_checks`；面板。
- 原来只有部分声明的 SIO2、I2C、中断控制器、面板，补上了无操作的 `batch_skip`；中断控制器补了 `batch_plan`，恒为“永不”，因为它的进入点由 C 端的中断停点处理。

**附带一：输出和介质目录改为显式。**
- 新增 `outputs.py`。`storage_run`、`input_run`、`file_calls`、`storage_checks` 的 `OUT` 默认为空，`m2.run` 要求 `--output-dir`。`m2_checks`、`rpc_check`、`fixtures`、`board_checks` 的输出都由调用方给出，冻结的 M2 输入只从 `m2.INPUTS` 读。
- 虚拟介质和 FAT 生成只接受调用方用 `declare_media` 声明过的目录。
- 冻结目录一律拒绝：emulator_m2/m2b/m2c/m2d、emulator_speed、unit28_stock、复审目录、`tools/gxr_emulator`、native_harness、firmware。

**附带二：快照重建命令。** 改为指向本副本的 `tools/gxr_emulator_batch/speed_snapshot.py`；`build` 要求 `--evidence-dir`。快照本身没有重建。

**修复后的检查。**

| 检查 | 结果 |
| --- | --- |
| 复审反例 `reproduce_hooks.py`（原样运行） | 原版、副本逐条、副本批量三者：钩子在第 0–7 步都被调用，RAM `00000055`，r0=0x55，`max_steps` |
| `hook_cases.py`：运行中安装、声明钩子换成未声明钩子、未声明换成声明、MMIO 回调中途换钩子、设备缺 `batch_skip`、Machine 中启动设备缺声明（30 万步） | 6/6：三种实现结果完全相同（寄存器、RAM、各钩子调用次数、Machine 全状态与观察哈希）。批量统计显示确实走了逐条路径或批量路径 |
| `output_cases.py`：缺输出目录、冻结目录、未声明或冻结介质、重建命令 | 11/11 符合预期 |
| 全状态哈希（无卡、有卡：第 100 万、1000 万步，候选点，ADJ 结束） | 全部与原版相同 |
| 副本关闭批量（第 100 万、500 万步） | 与原版相同 |
| M2b / M2c | 22/22、21/21；十项结果与 emulator_speed 逐条存档逐项相同 |
| g145 回放 | 与本轮逐条版和 run2 存档完全相同（非计时字段、71 次调用、扇区表、读回、最终卡镜像） |
| 既有四组检查（debug，逐条） | 全部通过；fast 加批量的额外记录仍是 11/13，差的两项依赖 debug 记录 |

证据：`local/hook-cases.json`、`local/output-cases.json`、`local/equivalence.json`、`local/m2b-batch-r1.json`、`local/m2c-batch-r1.json`、`local/crosscheck.json`、`local/g145-*-vs-batch.json`、`local/bench.json`。

复审的其他说明保留不变：切换时，emulator_speed 的旧候选快照会因身份不同被拒绝，需要用最终库和源码重建，并保留 accepted/quiet 门槛；原冻结库生成的检查点仍可载入，但须核对相邻 JSON、MAIN、设备拓扑和介质身份。

## 第二轮复审修复（r3）

**问题。** 根层（`_run_batch`）和 StepHook 前驱层都用 `getattr(..., 'batch_plan')` 取计划。一个普通对象只要用 `__getattr__` 把属性转发给内层 StepHook，就会被当成“已声明”，它自己 `__call__` 里的逻辑在批量时被跳过。

**修复。** 新增 `backend.declared_plan`：只有类型完全是 `StepHook` 才取计划，否则返回“未声明”。根层和每一个前驱层都用它。StepHook 的子类也算未声明，因为子类可能改写 `__call__`。只要有一层不合格，未声明就沿链向上传，整条链逐条执行。README 已同步修改。

**检查（r3 代码）。**

| 检查 | 结果 |
| --- | --- |
| 第一轮复审 `reproduce_hooks.py`（原样运行，不写文件） | 原版、副本逐条、副本批量相同：钩子在第 0–7 步都被调用，RAM `00000055`，r0=0x55 |
| `hook_cases.py`，新增根层转发、中间层转发、StepHook 子类、真实 Machine 转发钩子（1000 步，每步写 RAM 计数） | 10/10，三种实现完全相同。Machine 用例三边钩子都调用 1000 次，RAM 计数为 1000，完整快照相同；批量统计显示走逐条路径 |
| 第二轮复审的 `extended_hooks.py`、`forwarding_hooks.py`、`machine_forwarding.py`，复制为 `r2_*.py` 运行 | 只改了模块名和输出路径，以免写入复审目录；原文件 SHA 写在各副本开头。extended 4/4 相同；forwarding 两种情形相同；Machine 三边各 1000 次，完整快照、寄存器、内存、设备、观察全部相同 |
| 第 100 万步全状态哈希（无卡、有卡） | 与原版相同：`9961a47f…`、`0d0af170…` |
| M2b / M2c | 22/22、21/21；十项结果与 emulator_speed 逐条存档逐项相同（`local/crosscheck.json`）；既有四组检查（debug）全部通过 |
| 5000 万步无卡冷启动 | 76.7 秒（r2 为 78.9 秒） |

证据：`local/hook-cases.json`、`local/r2-*.json`、`local/eq-r3-batch-*.json`、`local/m2b-batch-r1.json`、`local/m2c-batch-r1.json`、`local/crosscheck.json`、`local/final-input-guard.json`。

执行器仍然无法自行发现的情形没有变：设备推进了却没有列进 `devices()`，或声明了错误的截止数字。这两种情形靠等价用例把关。
