不可以切换

C 后端存在 P1-01：实例方法换了绑定对象后，兼容性检查仍返回真，C 与原 Python 的寄存器、内存或异常结果不同。固定验收和真实 view-reentry 子集通过，不能关闭这个阻断点。可选参考库编译缓存另有 P1-02，环境变化后会返回旧结果。

同卡重复实验可以采用“原厂空闲循环或已确认的无限期睡眠也算等待”的定义。当前实现仍不宜默认启用快照，具体缺口见快照一节。所有结论限于本机离线主机工具，没有切换入口或修改被审对象。

## 复审身份与只读边界

仓库根为 `/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh`。外置卷为可写 APFS，UUID 为 `14BE04EB-AF49-497E-B36A-B078B2F7C5E8`。本轮写入仅在本目录和指定 TMPDIR，没有联网、访问存储卡、做 Git 写操作或启动子代理。

| 固定工件 | SHA-256 |
| --- | --- |
| 被审 C 核心库 | `15f9b4e4cc28ff727d56f269ef57f7b938bb115485cd528996761158922b072f` |
| g137 DAT | `78dcbb9a2735cd84e55385683ce0296b97818ddf90f8b492d9003512dbeff3f8` |
| 快照试验使用的已放行批量模拟器库 | `018a6d9731d54b6b27e6729d4a8903a4cab5b8763a0ce92467ad91e02d2d8c95` |

开始时独立复核实现清单 21,337/21,337、冻结输入 804/804，均通过。另登记 38,118 个既存文件，见 [实现清单复核](local/implementation-manifest.json)、[冻结输入复核](local/frozen-input-check.json) 和 [开始身份](local/inputs-before.json)。

末次全量复核失败，不能记为“全部未变”：38,117 个既存文件相同，`research/speed_hillclimb/LEDGER.tsv` 从 `bd066b667cda598ed7ef2d9521bdb9dc9828eacab66c1458a78a805d976ec040` 变为 `fa481ca743df7932bc0baaa1d7a85aac3c21484ed0441e78cd8713678d1d15a5`，`tools/speedlab/` 新增 78 个后续版本文件。原始失败及退出码 1 保存在 [结束身份](local/inputs-after.json) 和 [检查进程记录](local/inputs-after-process.json)。

随后针对实际执行输入重新检查 859 项，全部保持开始身份，交付前再次检查也相同。账本不在原冻结执行输入中。两个 native_harness 目录和批量模拟器目录均没有新增、删除或既存文件变化；speedlab 的既存代码也未变化。本结论只覆盖上述固定版本，不评审并发新增的 `harness_c_next`、`emulator_next` 和其他新工具。见 [执行输入复核](local/functional-inputs.json) 与 [交付前复核](local/final-execution-inputs.json)。本轮工作负载均受 [内核写入与禁网边界](fence.sb) 及 [Python 审计边界](scope_guard.py) 约束。

## 独立重跑结果

| 核实项 | 本轮执行与结果 | 证据 |
| --- | --- | --- |
| 固定 50mm 验收 | 原版 Python 与指定 C 库各跑一次。全部 189 个验收值相同，没有排除字段。两侧均为 27,322,942 步、42,299,447 个 op。原始验收 JSON 的 SHA 均为 `40a01d3ff2d9d328380a6054cb7a6f8c29270e31686613a98bdb1b7e1f9b784d`。 | [运行脚本](fixed_accept.py)、[Python 原始结果](local/fixed-python-50mm/local/accept-50mm.json)、[C 原始结果](local/fixed-c-50mm/local/accept-50mm.json)、[逐值比较](local/fixed-comparison.json) |
| 真实 view-reentry 子集 | 七屏 L1、card、items、value、groups、entries、ERR；两个切点 entry、row_draw；UP、DOWN 两键。每侧实际 fork 28 个子进程，全部完成。29 份验收 JSON 的 121,083 个值相同，均执行 56,190,466 步。C 的这些步骤确实进入 C 循环。 | [复制运行器](legacy.py)、[复制差异](local/legacy-copy.diff)、[Python 运行记录](local/view-python/summary.json)、[C 运行记录](local/view-c/summary.json)、[逐值比较](local/view-comparison.json) |
| 默认后端 | 不设置开关和显式设置 `python`，即使指定不存在的 C 构建清单，也能构造纯 Python 后端，未导入 C 适配模块。 | [脚本](default_cases.py)、[结果](local/default-summary.json) |
| 复制来源 | Python 后端原实现前缀逐字节相同，另外九个 Python 文件和 STUBS.md 逐字节相同。 | [静态审计](local/static-audit.json) |

view-reentry 使用既有 g137 私有适配，保留原 UI 断言、嵌套影子调用和步数上限。每侧先跑完整 v2 C 参考检查，再绑定数学参考和十个 int16 数值读取。只在本轮运行器副本改写输出位置与审计入口，见 [复制清单](local/copied-runners.json)。本轮覆盖 28 个子进程，没有把它称为原 70 个子进程全套复验。

本轮没有重跑实现方全部 6,080 组指令向量、40 个边界样本、UBSan、27,322,942 步完整 CPU/写入 tape 或变异套件。这些属于清单已核对的既有证据，不计入本轮新增通过项，也不据此重新认证报告中的五对提速倍数。

## P1-01：方法一致性检查漏掉接收对象

位置为 `tools/native_harness_c/ccore/backend.py:64-67`。`method_same()` 只比较 `__func__` 和 `__code__`，没有比较 `__self__`。因此，赋给当前实例的另一个实例的同名原方法仍被视为兼容。`_c_compatible()` 对 `self.core.owner` 的检查不能保护这种绑定替换。

在 `core.c:529`，回调后的检查继续返回真，剩余 slot 和后续指令继续走 C。原 Python 则调用新绑定对象的方法。这直接违反允许的实例替换和回调运行方式。

本轮新写 [independent_cases.py](independent_cases.py) 与 [extended_cases.py](extended_cases.py)，共 19 个用例。8 个出现差异，均归于此根因；另 11 个一致。下表列出全部差异。

| 新用例 | 原 Python | C 后端 | 原始证据 |
| --- | --- | --- | --- |
| 断点回调把 `b.core.op` 换成 `shadow.core.op` | 主实例 r0 保持 `0x12345678`，影子 r0 变为 7。 | 主实例 r0 变为 7，影子保持原值。 | [callback-bound-core-op](local/independent/callback-bound-core-op.json) |
| 断点回调把 `b.read` 换成 `shadow.read` | 读出 `0x55667788`。 | 读出原映射的 `0x11223344`。 | [callback-bound-backend-read](local/independent/callback-bound-backend-read.json) |
| 断点回调把 `b.core.read` 换成 `shadow.core.read` | 读出 `0x55667788`。 | 读出 `0x11223344`。 | [callback-bound-core-read](local/independent/callback-bound-core-read.json) |
| 断点回调替换 `b.core.write` 的绑定对象 | 写入影子内存。 | 快速写入当前实例内存。 | [callback-bound-core-write](local/independent/callback-bound-core-write.json) |
| 断点回调替换 `b.write` 的绑定对象 | 写入影子内存。 | 快速写入当前实例内存。 | [callback-bound-backend-write](local/independent/callback-bound-backend-write.json) |
| store 的写追踪回调中替换 `b.core.op` | 同包剩余 nop 和下一包 ldi 由影子 Core 执行。 | 仍由当前 Core 执行，寄存器与 op 记录不同。 | [write-callback-bound-op](local/extended/write-callback-bound-op.json) |
| MMIO 读回调中替换 `b.core.read`，同时撤下 MMIO 映射 | 下一次读取为影子值 `0x778899aa`。 | 下一次读取为当前映射值 `0x11223344`。 | [mmio-callback-bound-core-read](local/extended/mmio-callback-bound-core-read.json) |
| 回调把 `Core.op` 原函数直接赋给实例，形成未绑定函数 | 抛出缺少 `pc` 参数的 TypeError。 | 正常执行 ldi 并返回 max_steps。 | [callback-unbound-core-op](local/extended/callback-unbound-core-op.json) |

前七项的 C 兼容性诊断仍为真，未发生应有退回。实现报告“实例或类方法被替换时转回 Python”的概括不成立，固定轨迹相同只能证明已运行的固定轨迹。

最小修正方向是同时核对方法类型、`method.__self__ is obj`、原函数和代码对象。不能满足原绑定合同的替换应进入 Python 路径；已有验证观察器写代理继续按其独立合同核实。修正需要在回调内部就生效，并保留同包剩余 slot 的执行顺序。本轮没有修改实现。

其余自写用例均相同，包括：影子共享映射的修改、第一包执行后通过影子覆盖已预热的未来代码映射、自修改后立即执行、覆盖已预热指令、全空间写追踪回调再写内存并改寄存器与 PSW，以及换成新函数体的 op。`max_steps` 为 0、1、2、3 和从第二个 slot 进入的检查也一致。步数按指令包计数，限额为 1 时不会在包内第二个 slot 前额外截断。见 [15 项汇总](local/independent-summary.json) 与 [4 项补充汇总](local/extended-summary.json)。脚本退出 0 仅表示采集结束，等价判定取各项 `equal` 字段。

## trace 提前返回条件复核通过

本轮用实际 Harness.trace 写了六项独立检查。未改条件的控制样本确实记录一次 C 快速写入；另外五项分别在断点关闭 quiet_trace、移动 settings、改 trace 代码常量、替换已注册 trace、改用调用方提供的实例 trace。应记录的写入均进入 Python 回调，五项 `fast_writes` 均为零，两侧状态和写记录相同。

源码中的代码形状检查，以及 C 侧对函数代码、类型版本、全局字典版本和当前字段的检查，与本轮结果一致。这里退回的是写回调处理，指令循环可以继续在 C 中执行。本轮没有发现“trace 已变而旧条件仍筛掉写入”的反例。见 [脚本](trace_cases.py)、[六项结果](local/trace-summary.json)。

## P1-02：编译器身份缓存使环境键过期

位置为 `tools/speedlab/content_cache.py:61-65`，影响 `compile():81` 构造的键。`tool_identity()` 虽包含 `MACOSX_DEPLOYMENT_TARGET` 等环境，但同一 CommandCache 对同一编译器只取一次身份；后续预处理和编译使用实时环境，键仍使用旧环境。

[cache_cases.py](cache_cases.py) 用同一个缓存对象编译一个返回 `__ENVIRONMENT_MAC_OS_X_VERSION_MIN_REQUIRED__` 的真实 C 函数。结果为：

| 请求 | 返回值 | 缓存行为 |
| --- | ---: | --- |
| 部署目标 14.0，首次请求 | 140000 | 编译新库。 |
| 改为 15.0，开启缓存 | 140000 | 仍是同一键，返回旧库。 |
| 保持 15.0，关闭缓存 | 150000 | 实际编译使用新环境。 |

这是缓存与直接编译的可观察结果差异。它没有证明本轮 g137 数学结果出错，但否定了缓存身份完整、环境变化可安全复用的声明。缓存对象跨 fork 后继续使用时，同样不能依赖创建时的环境身份。最小修正方向是每次请求重新核实编译器选择与环境，或者冻结执行环境并拒绝漂移；依赖扫描和实际编译必须使用同一份已绑定环境。

其余已核实项如下，详见 [缓存结果](local/cache-summary.json)。

- 真实编译参数在键内，改变宏参数会换键，函数值从 43 变为 47。
- 编译器 `-M` 给出的两层头文件都入键，改变内层头文件会换键，函数值从 42 变为 43。
- 修改缓存库一个字节后，完整性检查拒绝旧件并重建，库 SHA 和函数值恢复。
- 两个独立 CommandCache 对象在两个线程中同步请求同一个新键，实际仅编译一次，一次 miss、一次 hit，两侧均返回 42。外部命令串行执行，最多一个编译辅助子进程。源码使用每键 flock 和原子替换安装，未发现本轮同键安装破坏。此项是线程并发复跑，没有冒称独立重跑了实现方的两个工作进程实验。

## P2-01：全空间写审计限制提速

真实 view-reentry 子集的 C 循环执行了全部 56,190,466 步，但 `fast_writes`、`native_state_steps`、`deferred_steps` 均为零。这与 runtime_guard.watch 的全空间同步审计相符，属于速度限制，不是等价失败。固定 50mm 的收益不能直接外推到这一运行方式。原审计回调和 UI 断言均保留，见 [view 比较及统计](local/view-comparison.json)。

## 开机快照意见

结论：放宽等待定义合理；当前候选快照可以继续显式用于同卡实验，但尚不放行默认启用。开机验收与重启读回仍须从 MAIN 冷启动。

静态已证：本轮从冻结 MAIN 重新提取并反汇编空闲入口、优先级包装函数、service 36、睡眠包装函数、service 52 和 service 56。Task 1 在以当前任务为目标设置优先级 127 后，进入 `0x2005C340` 自分支。快照内当前任务为 1、PC 为该地址，实际优先级字节也是 127。

Task 21 调用睡眠包装函数时传入 -1。service 52 将任务状态置 1，并保留无限超时；service 56 清除睡眠状态并使任务重新就绪。快照中 Task 21 状态为 1、超时为 `0xffffffff`，最后一次 service 为 52 且相应参数为 `0xffffffff`。状态为 0 或 1 的任务只有 1 和 21。见 [独立反汇编](local/task-code/)、[任务语义与实际状态](local/task-semantics.json)。

据此推断：严格排除所有状态 0 和 1 会同时排除这两个已经确认的静止状态。对于保存完整调度、CPU、设备和介质状态的同卡重复实验，允许这两类状态有依据。这个判断不需要改任务状态或跳过原厂初始化。

主机已证：本轮重新从 MAIN 执行 42,572,307 步到原候选点，再执行 ADJ 按下 120,000 步、释放 3,000,000 步。随后用同一卡镜像缓存恢复，完整重复这两个窗口。CPU、全部映射内存、设备状态、观察记录、调用轨迹和待返回记录的证明值共 4,253 项相同，没有排除字段。两侧确实使用已放行批量库，冷启动全过程 45,692,307 步，恢复后 3,120,000 步；缓存元数据仍为 `accepted=false`。见 [冷启动结果](local/snapshot-cold/result.json)、[恢复结果](local/snapshot-restore/result.json)、[完整比较](local/snapshot-comparison.json) 和对应 metrics。

当前的 `allow_idle_task` 不能直接当作新等待定义。`tools/speedlab/adapters/snapshot.py:246` 与 `:280` 在开关为真时豁免整个严格检查，`quiet():165-176` 也没有检查所有其他任务。本轮另建一个明确标记的合成负向样本：保持原空闲 PC、UI 和设备检查通过，只把 Task 2 改为就绪。保存后元数据仍为 false，默认加载拒绝，`allow_idle_task=True` 却成功恢复，活动任务变成 `[1,2,21]`。样本未执行固件，也未修改原快照。见 [负向脚本](snapshot_negative.py) 和 [结果](local/snapshot-negative/result.json)。

默认启用前还缺以下证据与约束：

1. 用精确的新任务判定替换整项豁免，并在保存和恢复两端核实。只接受已绑定固件身份下的原厂空闲任务和已确认的无限睡眠；额外就绪任务、错误空闲 PC、错误优先级或不匹配的睡眠超时都须拒绝。新判定必须拒绝本轮 Task 2 负向样本。
2. 按缓存实际要承接的实验补冷启动与恢复对拍。当前独立证据只覆盖固定 ADJ 序列；至少还要覆盖 Task 21 经 service 56 唤醒后的调度、队列和 IRQ，以及实际会使用的 UI、文件实验，比较完整状态与实际输出。
3. 证明多次及并行实验各自使用独立的工作介质和机器状态，并验证缓存发布中断、并发重建及损坏时能拒绝混合工件。保留现有卡字节、源码、库、配置、快照与介质身份校验。
4. 给新策略单独的版本和用途标记，在验收入口强制记录冷启动或恢复来源。只允许同卡重复实验使用，开机验收和重启读回不能因默认缓存设置而从快照起跑。

## 切换注意事项与交付

当前继续使用 Python 作为主机验收和回归后端。P1-01 修复并重建后，须绑定新的库 SHA，重跑本轮八个失败反例，并复跑固定验收、完整真实 view-reentry 和既有等价门槛。参考库内容缓存单独关闭，直到 P1-02 关闭。快照按上述独立用途门槛评估，不与主机 C 后端捆绑放行。

所有测试入口均用 `nice -n 10 /usr/bin/python3 -I -B`。工作负载串行启动；view-reentry 按原逻辑保留父进程和一个 fork 子进程并以前台 waitpid 等待。固定验收及快照超时 1800 秒，view-reentry 超时 3600 秒，超过给定实测时间三倍。每次入口的 PID、参数、脚本 SHA、超时、nice、退出码和耗时保存在 `local/*-process.json`，完整日志为相邻 `.log`。

没有把全清单末次失败改记为通过。清理首次在内核沙箱内运行时，系统拒绝执行只读 `/bin/ps`；[原错误](local/cleanup-initial.json) 已保留。随后同一清理脚本在 Python 写入与禁网审计边界内完成进程核对，确认本轮 Python 进程全部退出，并删除指定 TMPDIR。见 [清理收据](local/cleanup.json)。

[SHA256SUMS](SHA256SUMS) 使用仓库根相对路径，覆盖本目录报告、脚本、原始结果、复制差异与收据，不包含清单自身。可从仓库根只读复核封存产物：

```sh
nice -n 10 /usr/bin/python3 -I -B research/review_harness_c/delivery.py verify
```

本报告证明的是指定主机工具的替换资格和快照实验边界，未给任何 DAT 新增上卡、相机或刷写放行。
