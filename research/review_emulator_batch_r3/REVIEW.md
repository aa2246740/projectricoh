可以切换

第三轮关闭了 P1-01。旧转发反例、七项新增钩子用例、第 1000 万步全状态比较和 M2b 均通过，没有发现本次 fast 离线运行方式下的结果差异。现有生产 StepHook 链保持批量；普通面板函数的接法会逐条执行，记为 P2，不阻断。

本结论只判定这份模拟器的替换资格。本轮没有运行诊断 DAT，没有验证相机、物理存储卡或刷写；这些层仍按各自门槛放行。没有替用户切换工具路径。

复审身份与边界

仓库根为 `/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh`。写入仅限本复审目录和指定 TMPDIR；没有修改被审对象、联网、访问存储卡、做 Git 写操作或开子代理。外置卷已核实为可写 APFS，UUID 为 `14BE04EB-AF49-497E-B36A-B078B2F7C5E8`。

| 被审或参照文件 | SHA-256 |
| --- | --- |
| `tools/gxr_emulator/build/libgxr_m32r.dylib` | `ba1efa53ce71dbd5632b2a540d0ca3ad02c395498688ce90089a41d85e8c07ff` |
| `tools/gxr_emulator_batch/build/libgxr_m32r.dylib` | `018a6d9731d54b6b27e6729d4a8903a4cab5b8763a0ce92467ad91e02d2d8c95` |
| `tools/gxr_emulator_batch/backend.py` | `8a8c1d1530c1ea4426ab38f2ed52a0674d1837bc4343360498ad1df04e9b98e0` |
| `tools/gxr_emulator_batch/bridge.c` | `50602a074b607a069c8c71b7d119f9050a59726a31e47330389a9b34b3fbfaea` |

开始时独立核对实现清单 522/522、原版清单 45/45、速度研究清单 190/190、第一轮复审清单 101/101、第二轮复审清单 235/235。原版与批量目录的所有既存文件及清单覆盖的输入，共登记 32,135 个文件。末次复核 32,135/32,135 未变，两份工具目录没有新增或删除文件，既存符号链接未变；补充登记的八个运行输入也未变。证据为 [prepare.log](local/prepare.log)、[inputs-before.json](local/inputs-before.json)、[inputs-after.json](local/inputs-after.json) 和 [runtime-inputs.json](local/runtime-inputs.json)。

没有冻结或比较整个仓库。`research/unit28_stock/` 和 `research/emulator_m2d/local/unit28-g146/` 的并发产物没有用于本轮等价判定，也没有把这些目录的变化算作缺陷。

P1-01：CLOSED，静态调用点与主机反例均通过

Python 生产代码中，涉及钩子计划的调用点共有三处，全部列在下表。没有找到另一条通过属性转发取得钩子计划的路径。

| 位置 | 调用与核实结果 |
| --- | --- |
| `backend.py:462`，`Backend._run_batch` | 每批重新读取当前 `self.step_hook`，通过 `declared_plan(hook, self)` 取根计划；返回 `None` 就走 `_step_once`。 |
| `backend.py:64`，`StepHook.batch_plan` | 每一层前驱通过 `declared_plan(self.previous, cpu)` 取计划；任一前驱未声明，`None` 沿整条链返回根层。 |
| `backend.py:80`，`declared_plan` | 唯一直接调用 `hook.batch_plan(cpu)` 的地方。此前 `backend.py:78` 用 `type(hook) is StepHook` 检查真实类型，普通转发对象、绑定方法、partial 和子类均不通过。 |

`backend.py:56` 的 `getattr` 只检查 `devices()` 列出的设备声明，不用它识别钩子。补推进的两个调用点为 `backend.py:412` 的 `_batch_hook.batch_skip` 和 `backend.py:73` 的前驱 `batch_skip`；它们不另取计划，只补已获准批次的链。MMIO 期间换根钩子时，旧批次的补推进仍绑定旧根，新钩子从下一步生效，独立用例验证了这个边界。

全部 Python 计划调用还包括设备计划：`devices.py:569` 的 Timer/BootSerial，`storage_run.py:104-105` 的 StartupRegisters/DmaReceive/Board/SdHost，`m2.py:197` 的选中设备，`m2_checks.py:82` 的 StartupRegisters/DmaReceive，`panel.py:96` 的 Panel，以及 `board.py:408` 的 SioTransmit/I2cRegisters。这些不是钩子类型识别路径。逐个调用表达式及五处 StepHook 构造表达式均保存在 [static-audit.json](local/static-audit.json)。

第二轮的 `forwarding_hooks.py`、`machine_forwarding.py`、`extended_hooks.py` 均原样复制到本目录执行；第一轮 `reproduce_hooks.py` 和实现方第三轮 `hook_cases.py` 也原样复制。只有 `scope_guard.py` 的 TMPDIR 改为本轮路径，见 [entry-copies.json](local/entry-copies.json) 与 [entry-copies.diff](local/entry-copies.diff)。所有三方比较均为原版、副本关闭批量、副本开启批量，逐个 Backend 串行运行。

| 独立重跑项 | 结果与证据 |
| --- | --- |
| 第二轮根层转发与中间层转发 | 2/2 相同。钩子均调用 step 0–7，RAM 为 `00000055`，r0 为 85，停止于 8 步 `max_steps`。批量侧分别记录 7、8 步未声明回退；根层的第一步在断点路径执行。[forwarding-hooks.json](local/forwarding-hooks.json)。 |
| 第二轮真实 Machine 转发 | 三方均调用 1000 次，RAM 计数均为 1000；完整快照、寄存器、内存、设备及观察哈希相同。批量侧 1000 步均回退。[machine-forwarding.json](local/machine-forwarding.json)。 |
| 第一轮运行中安装普通钩子 | 三方调用 step 0–7，RAM/r0 为 `0x55`，停止结果相同。[reproduce-hooks.log](local/reproduce-hooks.log)。 |
| 第二轮扩展钩子 | 4/4 相同，含同一指令两次替换、同一回调两次替换、中间层缺 plan/skip 后恢复。[extended-hooks.json](local/extended-hooks.json)。 |
| 实现方第三轮钩子检查 | 10/10 相同，含 StepHook 子类、30 万步设备缺声明和真实 Machine 转发。[hook-cases.json](local/hook-cases.json)。 |

另写 [independent_hooks.py](independent_hooks.py)，下列七项均三方相同，比较完整 CPU 快照、RAM、寄存器、各层计数和调用时序。每项 RAM/r0 均为 `0x55`，不是只比较停止原因。

| 本轮新增用例 | 观察到的行为 |
| --- | --- |
| 断点运行中换成绑定方法 | 原钩子执行 2 次，新方法执行 step 2–7，没有漏调用。 |
| MMIO 写回调换成绑定方法 | 原钩子执行当前 store 在内的 5 步，新方法执行 step 5–19；旧批次正确收尾。 |
| partial 包装 StepHook，接在根层 | 八步都调用包装逻辑与内层。 |
| partial 包装 StepHook，接在中间层 | 整条链回退，上层与内层各执行八步。 |
| 两层普通转发对象，接在根层 | 两层观察逻辑均调用 step 0–7。 |
| 两层普通转发对象，接在 StepHook 前驱链中 | 上层、两层转发和内层均没有漏调用。 |
| 绑定方法再换回确切 StepHook | 方法调用 step 2、3，随后恢复批量，最终计数和完整状态相同。 |

原始结果及各项回退/批量统计见 [independent-hooks.json](local/independent-hooks.json)。结合调用点审查，本轮没有留下第二轮所述的根层或任意前驱层转发漏执行路径。P1-02 的缺设备声明传播也继续通过本轮复跑。

生产入口的真实类型与测速

[entry_paths.py](entry_paths.py) 在实际构造路径运行时记录各层的真实类型，并在 fast 加批量下执行。只在本轮进程内设置运行档位及记录统计，没有改钩子构造逻辑。

| 入口 | 实际链类型 | 执行步数 / C 批量步数 | 未声明回退 |
| --- | --- | ---: | ---: |
| `devices.install`，`devices.py:574` | StepHook | 10,000 / 9,991 | 0 |
| `storage_run.run` / Machine，`storage_run.py:115` | StepHook → StepHook | 5,000,000 / 4,999,990 | 0 |
| `Panel.chain`，`panel.py:96` | StepHook → StepHook → StepHook | 10,000 / 9,991 | 0 |
| `m2_checks.restored`，`m2_checks.py:87` | StepHook → StepHook | 10,000 / 9,990 | 0 |
| `m2.run`，`m2.py:207`，无 board | StepHook → StepHook | 10,000 / 9,989 | 0 |
| `m2.run --board-m2b` | StepHook → StepHook | 10,000 / 9,989 | 0 |

以上每层都满足 `type(hook) is backend.StepHook`。`board.py` 不另装 step_hook，由 Machine 或 m2 的确切 StepHook 推进；Board、SioTransmit、I2cRegisters 都在对应 `devices=` 列表中。没有发现“只认确切类型”导致这些入口失去批量。

一次真实 `storage_run.run` 冷启动到 500 万步，五段 `cpu.run` 合计 6.718 秒，含构造、结果和检查点写出的端到端耗时为 7.056 秒。五段均返回 `max_steps`，确实推进 500 万步，4,999,990 步在 C 中执行。这是一次入口确认测速，机器有其他任务，未据此重估实现报告中的提速倍数。证据为 [entry-paths.json](local/entry-paths.json) 和 [storage/types.json](local/entry-paths/storage/types.json)，实际结果与检查点在同目录。

P2-01：保留新增设备的声明要求，不阻断。`StepHook.declared` 无法自动发现未列进 `devices()` 的推进对象，也无法校验错误的截止步数。现有接入未发现这类遗漏；未来新增设备仍需完整列出并提供等价用例。

P2-02：旧式面板普通函数不能提速，不阻断。只读检查发现 `research/unit28_stock/emu_g146_hooks.py:81-86` 使用普通函数包住面板与旧钩子。本轮按相同接法构造实际 Machine，10,000 步记录为 10,000 次 `undeclared-hook-steps`、零 C 批量步，正常返回 `max_steps`。该脚本当前仍引用原版；以后若只换工具路径，这个接法会安全回退。需要提速时可在调用方改用已有的 `Panel.chain(cpu)`。源文件读取时的 SHA 和代码片段见 [static-audit.json](local/static-audit.json)，运行记录见 [panel_function/types.json](local/entry-paths/panel_function/types.json)。没有修改该脚本。

独立全状态比较与 M2b

[state_check.py](state_check.py) 从原厂 MAIN 无卡冷启动，设置相同面板及拨盘输入；先运行原版，再运行第三轮批量版。两个检查点的 CPU、全部映射内存、全部快照设备字段、完整 `cpu.snapshot()`、面板自身字段及观察记录哈希均相同。

| 步数 | 两侧相同的标准全状态 SHA-256 |
| --- | --- |
| 1,000,000 | `9961a47ff91e318e972a3a712ea2448a51fe0ebd5faa396ee2ce6ab0e2eb88f7` |
| 10,000,000 | `84e51c8b3fb0f8b09c0d82c1d63d423fb55b339d001689bf84af7f2e6752f357` |

批量侧累计有 9,998,645 步在 C 中执行，没有未声明回退。标准全状态哈希外还分别比较完整快照、逐内存区哈希、观察与面板哈希，所有结果字段逐值相同。见 [state-step.json](local/state-step.json)、[state-batch.json](local/state-batch.json)。两侧进程用时 198.4、14.7 秒，仅作为本轮执行记录。

[m2b_run.py](m2b_run.py) 独立重跑无卡 5000 万步、从该检查点续跑 500 万步、有卡 5500 万步，以及 board、M2、RPC、conformance 四组既有检查。M2b 22/22，native tick 从 13742 增至 15409；额外检查确认有卡运行确实达到 5500 万步，Task 8/28 均为等待态 512，native ready 符合条件。

三个 Machine 长运行均为 fast 加批量，C 批量步数分别为 49,939,541、4,992,053、54,930,662，未声明回退均为零。四组既有检查保留原来的 debug 逐条档位，均通过，不能将这四组说成批量测试。M2b 断言没有改写；复用的批量适配校验器与原校验器只有工具路径、源码前缀和动态库身份适配，SHA 为 `a66155c9c80b913af04ece692525a5f73d66a80ecfd314b7f3729e7a68f706b6`。原始证据为 [m2b-review.json](local/m2b/m2b-review.json)、[m2b.log](local/m2b.log) 及其引用的结果、介质和检查点。

本轮没有重跑 M2c、g145/g146 文件回放或开机候选点，未把它们记为新增复审证据。第二轮已通过项继续作为历史证据；本轮新增的长状态比较绑定上述第三轮 backend 身份。

切换注意事项

1. 调用方选择批量副本后，仍须先设置 fast，再启用 `GXR_EMULATOR_BATCH=1` 或 `set_batch(True)`。仅设置环境变量不会把默认 debug 自动改成 fast；依赖逐条轨迹或 MMIO 记录的检查继续用 debug。
2. 输出及虚拟介质目录须显式提供并声明。旧速度候选快照需要按最终库和源码重建，保留 accepted/quiet 门槛；可接受的原冻结库检查点仍须核实相邻元数据、MAIN、设备拓扑和介质身份。
3. 普通包装函数、partial、转发对象、StepHook 子类均会触发整条链逐条执行。先读取 `batch_stats` 确认实际执行方式，再使用速度数字。

执行与交付证据

所有模拟入口由 [run_check.py](run_check.py) 启动，使用 `/usr/bin/python3 -I -B`，继承 `nice -n 15`。本轮自己的模拟进程最多一个；子进程全部以前台等待并设置超时。短检查为 1800 秒，全状态每侧 7200 秒，M2b 10800 秒，入口检查 3600 秒，均超过相应实测时间三倍。具体命令、nice 值、超时、PID、退出码和耗时见 `local/*-process.json`。[fence.sb](fence.sb) 在内核层限制写入并禁网，[scope_guard.py](scope_guard.py) 另限制 Python 文件写入及外置介质访问。

[compare_results.py](compare_results.py) 从原始结果重新比较，18/18 项通过，见 [comparisons.json](local/comparisons.json)。自写复算器第一次因少右括号而出现 SyntaxError，未启动模拟器；原脚本保存在 [infrastructure-initial/compare_results.py](local/infrastructure-initial/compare_results.py)，首次退出码 1 和日志保存在 [compare-results-process.json](local/compare-results-process.json)、[compare-results.log](local/compare-results.log)。修正后的复算日志为 [compare-results-final.log](local/compare-results-final.log)。首次失败保留为复审脚本错误，没有改记为模拟器通过或被审对象缺陷。

交付前删除指定 TMPDIR，并检查本轮 Python 进程全部退出，收据为 [cleanup.json](local/cleanup.json)。`SHA256SUMS` 使用仓库根相对路径，覆盖本目录报告、脚本和原始证据，不包含清单自身。

从仓库根复核交付物与现有结果：

```sh
nice -n 15 /usr/bin/python3 -I -B research/review_emulator_batch_r3/delivery.py verify
nice -n 15 /usr/bin/python3 -I -B research/review_emulator_batch_r3/compare_results.py
```

重跑模拟检查使用 `run_suite.py short`、`run_suite.py state`、`run_suite.py entry` 或 `run_suite.py m2b`，均由 `nice -n 15 /usr/bin/python3 -I -B` 启动。运行前重新建立指定 TMPDIR；M2b 的输出目录必须是新目录，原始证据不应覆盖。
