修改后再采用

本结论只评严格登记流。旧 Python 调用方式被明确拒绝，按新合同记为通过。普通冷启动、首次菜单、GPIO/SD、BOOT_RUN、H52、恢复确认入口和输入驱动的所测配方均与参考相等，可以按既定策略逐流程用于迭代。下面三个 P1 涉及登记控制和完整快照，不能把整个 strict_r2 合同判为已关闭。

使用前提仍是：FAIL、OPEN、fault、DeviceBoundary、超时、未达目标，以及任何上卡或刷写决定，均以同一冻结输入和独立虚拟介质在 Python 参考上重跑一次，保留首次失败。

复跑命令均从仓库根目录执行。新回执须换输出名称，保留本轮证据。

## P1-01：登记的观察标签会被截短，中文还会在推进后解码失败

`machine_flow.inc:8,17,23,25` 用 128 字节 C 缓冲区和 `%s` 拼接标签。`native_controls.watch_point()` 接受普通字符串，却没有相应的长度、NUL 或编码边界检查。

这次直接调用登记 API，没有替换类、方法或回调。在 g155b、50mm、4096 B 设置输入的真实冷启动中，于 `0x202b1210` 登记两个观察标签并跑到 50M 步，两种标签各命中 5 次：

| 输入 | 严格原生记录 | Python 参考记录 |
| --- | --- | --- |
| 130 个 `x` | 127 个 `x`，后缀也丢失 | 130 个 `x` 加 `-point`，共 136 字符 |
| `a\x00b` | `a-point` | `a\x00b-point` |

原生确实执行了 50,000,000 条指令，Python 总线和 HLE 回调均为零。两个后端都正常返回预算终点。寄存器、架构、内存、设备和其他历史相同，Flow 记录及计数不同。见 [原生回执](runs/control-label-pair-real-native.json) 和 [参考回执](runs/control-label-pair-real-reference.json)。独立的一步反例也得到同样结果。

相邻的中文输入 `"中" * 50` 更严重。原生已执行 1 步，随后抛出 `UnicodeDecodeError`，位置为 UTF-8 字节 126；参考正常执行 1 步并保留标签。它没有在推进前拒绝这个输入。见 [中文原生](runs/control-label-unicode-native.json) 和 [中文参考](runs/control-label-unicode-reference.json)。

应按字符串实际字节长度无损拼接。若只支持较窄的标签范围，就在登记控制时检查具体类型、NUL 和 UTF-8 长度，在推进前明确拒绝。关闭条件是上述三种输入等价或提前拒绝，并保留正常 watch/stop 的两种登记顺序；本轮这两种顺序已相等。

```sh
R3=research/review_emulator_fast_r3
nice -n 15 /usr/bin/python3 -I -B "$R3/control_probes.py" --case label-pair --real --backend native --name label_new_native
nice -n 15 /usr/bin/python3 -I -B "$R3/control_probes.py" --case label-pair --real --backend reference --name label_new_reference
nice -n 15 /usr/bin/python3 -I -B "$R3/control_probes.py" --case label-unicode --backend native --name unicode_new_native
nice -n 15 /usr/bin/python3 -I -B "$R3/control_probes.py" --case label-unicode --backend reference --name unicode_new_reference
```

## P1-02：快照键没有覆盖完整的登记控制配方

`registry.py:164–166` 的 `snapshot_contract()` 只记录调度层、观察器数量、Flow/ready-hold 是否存在及单元名称，没有绑定实际停止条件和控制声明。`snapshots.py:150` 把这个摘要作为登记配方放进身份。

用相同文件输入和模型，分别调用 `engine_watch(..., stop_on_return=True)` 与 `False`，两个完整身份及键相同。保存前者 19 步快照后，后者接受该快照，停止配置从空集合变成 `{'BOOT_RUN'}`。目标机器已经被改变。没有修改快照、元数据、登记表或私有状态。

原生键为 `d4c2816c25baaebf0fd76003fd8660285d6486e85d3a3a1942e340ca1c371d01`。候选自己的显式 reference 后端也复现相同问题，见 [原生](runs/key-off-native-recipe-native.json) 和 [候选 reference](runs/key-current-reference-recipe-reference.json)。旧 fix_r1 参考路径的复跑另保留，未混为候选 reference。

所以“源码、模型和登记表已进入键”是真的，“旧快照不会被不同登记配方接受”仍不成立。应绑定实际控制参数，包括停止条件、观察地址及标签、初始化声明。若由调用方通过 Inputs 声明参数，保存前仍须核对声明与实际机器一致。关闭条件是改变这些参数后身份变化，恢复在改写目标前拒绝，并继续通过文件、源码、四项修正和常量失效测试。

```sh
R3=research/review_emulator_fast_r3
nice -n 15 /usr/bin/python3 -I -B "$R3/snapshot_probes.py" recipe-off --backend native --name key_new_native
GXR_STRICT_REFERENCE_ORACLE=current nice -n 15 /usr/bin/python3 -I -B "$R3/snapshot_probes.py" recipe-off --backend reference --name key_new_reference
```

## P1-03：带单元的完整快照接受恢复，却没有恢复活跃控制和所有权

真实 g155b/50mm 冷启动到 20,000,000 步时，ready-hold 中有三个 32 B 包。保存后由同配方的新机器恢复，`restore()` 返回成功，其内部指纹检查也通过，但 `export_controls()` 读出的活跃队列是空的。独立完整状态比较已不同。

`snapshots.py:294–299` 更新的是 `context.controls`。新合同中的 `export_controls()` 返回复制的导出值，这份副本已经不再是引擎持有的队列。`snapshots.py:303` 又用这份副本检查指纹，因此把漏恢复的 96 B 掩盖了。

另一个问题在 `snapshots.py:273–274`：反序列化得到的 UnitLink 直接替换现有模型，未恢复原生所有权。恢复后调用 `run(13)`，原生在 20M 步处抛出 `unit link model is not registered`，未再推进。这里是合法登记快照造出了无效状态，不能当成正确拒绝外部 Python 扩展。

见 [结构化复现](runs/hold-native-02.json) 和 [首次失败日志](runs/snapshot-ready-hold.log)。旧 Python 参考快照路径也会漏掉活跃 ready 队列，见 [旧参考复跑](runs/hold-reference.json)。候选当前 reference 在保存同一 20M 状态时因共享观察对象明确拒绝，日志保留在 [当前参考复核](runs/hold-current-reference-queue.log)，没有把这项拒绝算成恢复相等。

应通过登记的恢复接口写回实际控制状态，保留或重新绑定 UnitLink 所有权，并从活跃引擎重新导出后核验。暂不支持的完整快照组合应在改写目标前明确拒绝。关闭条件至少覆盖 unit-off、50mm、28mm 的真实中途状态及 ready 包存在时的保存、恢复、继续运行，与同后端连续执行逐点相等。仅有 MAIN 的 19+13 步正例不够。

```sh
R3=research/review_emulator_fast_r3
nice -n 15 /usr/bin/python3 -I -B "$R3/snapshot_probes.py" hold --backend native --name hold_new_native --short
GXR_STRICT_REFERENCE_ORACLE=current nice -n 15 /usr/bin/python3 -I -B "$R3/snapshot_probes.py" hold --backend reference --name hold_new_reference --short
```

## P2-01：MOUNT 有实现入口，尚无本轮流程覆盖

`prepare(unit='mount')`、`UNIT_PROFILES['mount']`、C 的第三套单元 ROM 和 RPC 分支均存在。它们证明有实现，不能证明 MOUNT 配方已经等价。本轮流程和交付采用范围只有 unit-off、50mm、28mm，本轮没有跑 MOUNT。

要覆盖 MOUNT，先固定 `l08firm3`、相应机身/DAT、MOUNT 设置和单元输入、私有 SD 种子及所用修正组合。当前登记 ROM 的 SHA256 为 `0a4dff6d3be9b9a9b56dfcbd98a2df59efcb31f7d4eaca6b0c3fbdb1641fde44`。随后用相同输入的两个新进程，对照冷启动握手、DMA/unit-info、ready、state 5、该任务所用菜单/按键、BOOT_RUN/H52 和 SD 路径，记录预期业务停点、完整状态和实际原生比例；若任务复用完整快照，还须关闭 P1-02/P1-03 并比较恢复续跑。50mm 的 4096 B 设置不能直接充当 MOUNT 的验收输入。

这份补测清单只补宿主等价性。真实 MOUNT、相机 RTOS/LCD、物理按键和拍摄仍须各自的设备证据。

## P2-02：交替测速和空闲条件

本轮确认所测流程有明显提速，没有确认空闲机器上的精确 65.35 倍和 45.91 倍。正式计时每项五对新进程，固定 reference/native 顺序；两项共 20 次运行都实际完成 50M 步，配对完整状态及输入驱动业务回执均相同，原生侧全部为 C 指令，零 Python 总线/HLE 回调。

| 流程与口径 | 参考中位秒（范围） | 原生中位秒（范围） | 逐对倍率中位（范围） |
| --- | ---: | ---: | ---: |
| MAIN，执行段 | 118.006（113.642–132.364） | 2.111（1.870–2.230） | 62.44（51.32–64.64） |
| input_run / native_input_run，完整驱动 | 102.766（99.275–114.700） | 3.259（3.213–3.747） | 31.38（26.50–35.20） |

倍率是每对“参考秒÷原生秒”后取中位，不是表中两个独立中位秒相除。MAIN 包含 cpu.run 及状态同步，构造和独立哈希在计时外；输入驱动包含构造、执行、原有 CPU 检查点保存，扣除额外审计导出，不含模块导入。两边均 fast+batch，四项修正全关、unit-off、nice 15，实际参考库及每次负载/CPU 秒保留在回执中。这里没有用快照恢复、拒绝或未完成预算代替计算。

![五对交替测速](benchmark.svg)

正式样本见 [MAIN](runs/benchmark-main.json)、[输入驱动](runs/benchmark-input.json) 和 [计时口径](benchmark-intent.md)。原报告仅三对，且负载剧烈变化；本轮开始前仍有虚拟机重计算，启动前独立采样约 13% CPU 空闲，未取得可验证的空闲条件。数据支持提速量级，不能支持固定机器倍率承诺。精确复现需等其他重计算结束后，按相同口径再交替至少五对。

另一次 200M 指令采样未计入测速，主线程落在 gxr_machine_run 和设备值查找/更新函数中。输入驱动的独立 profile 还看到 native_machine.run 与原有 storage_run.save 两个主要阶段；额外审计导出和其状态哈希没有混入正式计时。见 [MAIN 采样](runs/profile-native.sample.txt)、[输入驱动 profile](runs/profile-input-functions.json) 和 [空闲条件采样](runs/benchmark-queue-quiet-preflight.log)。

```sh
R3=research/review_emulator_fast_r3
nice -n 15 /usr/bin/python3 -I -B "$R3/benchmark.py" --kind main --pairs 5 --label main_new
nice -n 15 /usr/bin/python3 -I -B "$R3/benchmark.py" --kind input --pairs 5 --label input_new
```

## P3

没有单列的 P3 问题。

## 已复跑的普通流程和旧反例

比较器独立用 Python 流式哈希，覆盖全部寄存器、145 B 架构状态、所有内存区域及可写属性、全部设备/NAND 状态、观察器、事件、Panel、Flow、活跃控制、完整 SD 字节、trace、MMIO、coverage、IO 计数和错误。只规范化同角色私有介质路径，文件字节另核哈希。流程配方复用冻结脚本，结果判定和完整状态比较由本轮脚本完成。正常长流程的参考来自旧 fix_r1 Python 设备实现，使用候选 Flow 记录格式，未只比较候选的两个开关。

| 流程 | 实际终点 | 完整检查点 | 独立结果 |
| --- | ---: | ---: | --- |
| 28mm、g154 Looks18、四项修正、首次八行菜单 | 449,600,040 步 | 40 | 全状态相同，原生 100% |
| 50mm、g155b、冷启动/state 5/BOOT_RUN/H52 | 199,544,255 步 | 7 | 全状态相同，原生 100% |
| unit-off、官方恢复确认入口 | 65,975,242 步 | 4 | 全状态相同，PC `0x2036c9e4` |
| GPIO 按键和 guest SD 两扇区写入读回 | 1,112 步 | 24 | 全状态及两个 512 B 扇区相同 |
| 输入驱动 IDLE/HALF down/HALF up | 1,000,054 步 | 终态及业务回执 | 相同，原生 100% |
| 自有 CPU 检查点 1,000,003 步后续 31 步 | 1,000,034 步 | 两阶段 | 相同，续跑原生指令为新增 31 步 |
| 四项修正全部组合 | 每组 19/1,000/1,000,000 步 | 48 | 16 组相同，16 个独立键、64 次错误模型恢复均提前拒绝且目标未变 |

BOOT_RUN 返回为 199,006,590 步，r0=0；回复中的 -4 仍只是固件返回观察。H52 在 199,544,255 步到 `0x202afe9c`。这些结果没有证明自动配方事务或刷写成功。

两轮旧反例最终得到 1 项执行、70 项带 reference 提示的明确拒绝。唯一执行的自修改代码结果为 `[1,127,126,42]`，7 步完整状态与旧 Python 参考相同。调度缺层、StepHook 类/实例方法变化、共享 tuple/list、容器写入、大整数及非法类型、快照模型常量和预装包装都没有静默进入不同执行。部分保留引用用例先合法执行 19 步，随后修改视图时被拒绝，没有再推进。完整逐项记录见 [最终旧反例](runs/replay-old04.json) 和 [独立汇总](runs/assessment-review.json)。

源码副本变化、共享图拒绝、只读视图，以及 MAIN 19 步保存/恢复再执行 13 步的正例均复跑通过，见 [快照基础验收](runs/snapshot-acceptance.json)。这些正例没有覆盖 P1 中的真实单元中途快照。

复跑旧反例的命令：

```sh
nice -n 15 /usr/bin/python3 -I -B research/review_emulator_fast_r3/replay_all.py --name old_new
```

## 输入与运行记录

计算进程最多两个，均为 nice 15。测速单独串行执行。主动写入仅在本目录；Python 审计钩子拒绝目录外写入及网络连接。没有改候选、实现方证据、原入口或 Git，没有卡、相机或网络操作。

首轮评审工具出现过 Counter 编码、巨大整数十进制转换、关闭句柄后读取统计，以及顶层脚本参数加载顺序问题。日志保留，未计为候选故障。修正后使用 `menu-*-03`、`replay-old04` 和完成的功能队列作为正式证据。首次快照续跑失败也保留，并以 `hold-native-02` 独立复现。

本轮没有运行完整官方恢复成功、实卡 FAT32、物理 SD、刷写、断电、相机 RTOS/LCD、物理按键或拍摄。M2b/M2c 属于显式参考调用方，本轮未重跑全套，也没有把它们算作原生覆盖。

## SHA256SUMS

冻结的 343 项输入收尾逐项重读，变化为零。机器为 MacBookPro18,1、Apple M1 Pro、10 逻辑核、CPython 3.9.6。见 [初始冻结](inputs.initial.json)、[收尾核对](inputs.final.json) 和 [进程/临时目录收尾](runs/cleanup.json)。

输入驱动的五对测速和按键分段，还对实际审计文件使用本轮独立的类型哈希重算，六组全部相等；没有只信实现方的汇总哈希。见 [独立驱动状态审计](runs/driver-independent-state-audit.json)。

| 对象 | SHA256 |
| --- | --- |
| 严格原生 CPU 库 | `49519375b9724b41fcaf269a6d0226b171650cc30a965052664f328f2d94d254` |
| 传输扩展 | `a2cceee24700bd8226b97e00d5df9ec9ce55087858c43151e4b9ea319dca660f` |
| 冻结登记表 | `54defd2fda0913c23ce04609304507ecf73b1f128b5ca1448687b6f60922d32a` |
| Python 设备参考实际 GNU 库 | `018a6d9731d54b6b27e6729d4a8903a4cab5b8763a0ce92467ad91e02d2d8c95` |
| g155b 机身 | `a04f1ed40143b2c54d7f28e3af8af1f9a5ef5e115edf49eb404b8e26a53509c8` |
| g155b DAT | `1df64437d83629627fd4ba513b2988a014114f22cf5b184f7347f5437073bcfc` |
| g154 Looks18 机身 | `8233a1c464b29ba88cfdfce1d083b9bf652586edeb216cacf6f16cf36788b25d` |
| g154 Looks18 DAT | `5f6191c88e7691472541dce245df67679390aa850ffd110e8f8eb35f4b24c681` |

[SHA256SUMS](SHA256SUMS) 绑定上述输入和本目录交付文件，包含 REVIEW.md 自身。清单自身不列入自身哈希。可从仓库根目录核对：

```sh
shasum -a 256 -c research/review_emulator_fast_r3/SHA256SUMS
```
