可交复审
P1-02 在本轮所测登记合同内关闭：Observer 容量及全部登记对象的构造实参与默认值进入身份；变更容量会换键，并在写入目标前拒绝。
候选为 `tools/gxr_emulator_fast/strict_r4/`，需新 Python 进程。strict_r3 的 1460 个冻结文件未变。采用草稿见 [ADOPTION](strict_r4_final/ADOPTION.md)。
MAIN：负载门槛未满足，不报本轮正式倍率；完整配对 0/5，最后 load1/5/15 [6.26318359375, 5.013671875, 4.6484375]。原始队列状态 ERROR，门槛明细见 speed-gate-r4.json。
native_input_run：负载门槛未满足，不报本轮正式倍率；完整配对 4/5，最后 load1/5/15 [5.4052734375, 5.578125, 5.30126953125]。原始队列状态 DEFERRED，门槛明细见 speed-gate-r4.json。

本轮证据只覆盖宿主 strict registered-flow 合同。不是独立复审通过或相机采用结论。原 C 库和传输扩展字节复制到新目录；本轮未重编 C、未替换旧入口。native-build.json 仅用于核对实际 C 编译输入，当前 Python 源码以新登记表和交付清单为准。

r4 反例先在原 strict_r3 复现：同一键让 limit=9 目标接受 limit=1 快照，20M 时只留下 1 条事件，连续参考保留 9 条。另外先复现 trace 容量恢复后才发现差异、Flow 初始 pending 漏键，两项期望断言均失败。三项失败证据见 [before-r4-recipes](strict_r4_final/runs/before-r4-recipes.json) 和 [原 20M 反例](strict_r4_final/runs/before-r4-limit-native.json)。旧脚本和原始回执保留。

修复集中在 construction.py。LazyState 的子类构造器和 Backend 用同一个边界记录器，以 signature.bind/apply_defaults 保存所有参数，保留值类型、初始容器种类和容量。引擎引用按登记角色绑定；路径在正常校验后绑定文件字节。只读视图有明确类型声明；未知对象不获得原生资格。Observer 先构造 deque，再登记到 CPU，非法容量不会留下一半登记。

本轮盘点 29 个构造器。实际 release 配方的 26 个引擎对象逐项对比签名与记录参数，两端完整构造声明也相同。未把几个字段名列成 Observer 特例。StepHook 仍由冻结工厂证书限制；只读 Image/UnitImage 由实际输入字节与模型源哈希绑定，CPU 结构容器由有效回调与内存配方覆盖。另绑定当前 mode、variant 及 trace/MMIO 的实际容量。详见 [构造器盘点](strict_r4_final/CONSTRUCTORS.md) 和 [26 对象核对](strict_r4_final/runs/constructor-coverage-r4.json)。

新登记表从 17 个独立干净 reference 进程重建，含 16 种四修正组合、705 个回调代码和 68 个源文件。构造声明、覆盖层及登记表全文都受身份绑定。完整快照格式升至 r4，r3 整机快照需重建。见 [干净构建日志](strict_r4_final/runs/registry-build-final.log)。

最终结果由 [assessment-final-r4](strict_r4_final/runs/assessment-final-r4.json) 逐项读取原始回执生成：

| 验证 | 本轮结果 |
| --- | --- |
| 十类新配方变更，native/reference 各一轮 | 全部换键、写入前拒绝、目标完整指纹不变 |
| 位置/关键字、隐式/显式默认值两类 | 相同键；三种非法容量拒绝且状态不变 |
| 同容量 19 步保存恢复，续跑五点至 20M | 原生 0/1/9/None/16384/平台最大值均等于连续执行；0/9/None 另与本轮独立 reference 相同 |
| 两轮相邻/原控制配方，共二十类，每个后端 | 全部通过，错误身份在改写前拒绝 |
| 原 71 项反例、r3 六项回归 | 一项相等、其余明确拒绝；六项通过 |
| 十六种模型组合 | 48 个全状态比较、64 次错误模型恢复拒绝通过 |
| 输入分段与原 CPU 检查点 | 1,000,054 步业务回执及全状态相同；1,000,034 步续跑新增 31 条 C 指令 |

同容量原生恢复段真实执行 19,999,981 条 C 指令，Python 总线和 HLE 回调为零。容量 9 没有退化成容量 1。观察器总计数、事件、寄存器、全部内存、设备、控制及介质纳入独立完整指纹。

| 登记流程 | 步数 | 完整检查点 | 与独立参考 |
| --- | ---: | ---: | --- |
| 50mm g155b 冷启动、state 5、BOOT_RUN、H52 | 199,544,255 | 7 | 相同 |
| 28mm g154 首次八行菜单和按键段 | 449,600,040 | 40 | 相同 |
| 官方恢复确认入口 | 65,975,242 | 4 | 相同，虚拟 NAND 页相同 |
| MOUNT 冷启动、state 5、BOOT_RUN、ADJ 菜单 | 277,400,060 | 19 | 相同 |
| GPIO 与 guest SD 写入/读回 | 1,112 | 24 | 相同，扇区字节相同 |

off/50mm/28mm/MOUNT 的 20M 快照恢复后到 50,000,013 步，每种五点相同；每个恢复段实际执行 30,000,013 条 C 指令。MOUNT 另在五个活跃保存点恢复，十五个续跑点相同，ready 队列、SD FIFO、未返回调用、按住状态和对象所有权保留。长流程及这些恢复对照明确复用 review_emulator_fast_r4 冻结的独立 Python 连续执行回执；本轮重新跑候选原生。Observer 同容量对照的 reference 是本轮新跑。

首轮构造记录器曾把输入驱动的合法只读映射当成未知值，在第 0 步明确拒绝。证据保留于 strict_r4/runs/；修正后重新生成登记表，以上验收全在 strict_r4_final/ 重跑，没有拿早期成功回执代替最终源码结果。

测速声明在运行前冻结于 [benchmark-intent](strict_r4_final/benchmark-intent.md)。两边均为 fast+batch、unit-off、四修正关闭、nice 15，同一输入的新进程交替执行 50M。前置 load1≤5.0，连续三次一秒 CPU 空闲均≥50%，测速期间无本任务其他仿真。MAIN 只计 run 与返回同步；输入驱动计构造、执行和原 CPU 检查点，扣除额外审计导出，不含导入。错误或未完成预算不算测速。每对必须全状态相同；输入驱动另核业务回执。所有原始前后负载、CPU 秒、库哈希和调度信息在 benchmark-*-r4.json 中。条件不满足时保留 DEFERRED 和已有单侧结果，不估算倍率。

限速剖析单独运行，不混入正式计时。参考侧仍承担 Python 的设备调度、批计划与回调；原生 MAIN 的采样热点为 C 的 scalar_step、gxr_machine_run 及值树操作，完整输入驱动还承担构造登记、状态同步与检查点。具体采样见 profile-reference-r4.json、profile-native.sample.txt 和 profile-input-functions.json。倍率只适用于表述的工作负载，未用未完成执行或 HALT 计算。计时图见 [benchmark.html](strict_r4_final/benchmark.html)。

原复审输入 456 项和参考回执 43 项已重新核对。唯一交付改写的原路径是用户要求更新的本 REPORT.md；旧报告按原 SHA256 保存在 strict_r4_final/prior/REPORT.md，发布映射单独记录于 report-publication-r4.json。没有改历史输入清单或 protected-inputs.json。原 strict_r3 的 1460 个文件再次逐项核对。

MOUNT HALF 的未声明 HSP 响应沿用复审 r4 的共有模型边界结论，本轮未重跑该 fault 分支，不算拍摄成功。采用策略不变：快路径供迭代，FAIL、OPEN、fault、DeviceBoundary、超时和未达目标，按相同冻结输入与独立虚拟介质在 Python 参考重跑并保留首次失败。

未重跑 M2b/M2c 全套或成功完整官方恢复；没有实卡 FAT32、物理 SD、刷写、断电、相机 RTOS/LCD、物理按键或拍摄证据。没有卡、相机、网络、Git 写操作或子代理。

关键冻结哈希如下；完整源码、构建产物、输入、回执、失败证据和本报告见 [SHA256SUMS](SHA256SUMS)，独立 shasum 核验回执在 strict_r4_final/runs/sha256-verification.json。

```text
47699f02e78781241afbe90ea40ee7c3c8a60ecdb422d60e65a6baa1aaf306bf  tools/gxr_emulator_fast/strict_r4/build/libgxr_m32r.dylib
ca9e75f68c336d670ee26a5c7944e1cb4a45580ace0c718e0b22c28e843fe51e  tools/gxr_emulator_fast/strict_r4/NATIVE_REGISTRY.json
c9789bd03c3b9c00b2e0a8ae4a511ef5f92eb103af5ef3c023c100c30a140cbb  tools/gxr_emulator_fast/strict_r4/construction.py
c6a682eb72300f9a9a35ffc2b38ae174117d96616668eb27a3307610c7af2251  tools/gxr_emulator_fast/strict_r4/registry.py
e3908e9c02121ac20aaf21572ea13b6346b24a2f6932435d3d96a813986bc4b7  tools/gxr_emulator_fast/strict_r4/snapshots.py
```

从仓库根目录重跑。NEW_NAME 必须未使用；脚本拒绝覆盖已有证据。全队列的每条命令和超时见 lane-*-r4.json，若完整重跑需复制脚本到新的同层证据目录并改输出绑定，保留当前回执。

```sh
nice -n 15 /usr/bin/python3 -I -B research/emulator_fast_r1/strict_r4_final/scripts/accept_r4.py isolation --backend native --name NEW_NAME
nice -n 15 /usr/bin/python3 -I -B research/emulator_fast_r1/strict_r4_final/scripts/accept_r4.py resume --backend native --limit 9 --name NEW_NAME
nice -n 15 /usr/bin/python3 -I -B research/emulator_fast_r1/strict_r4_final/scripts/accept_r4.py resume --backend reference --limit 9 --name NEW_NAME
nice -n 15 /usr/bin/python3 -I -B research/emulator_fast_r1/strict_r4_final/scripts/benchmark_r3.py --kind main --pairs 5 --label NEW_LABEL
nice -n 15 /usr/bin/python3 -I -B research/emulator_fast_r1/strict_r4_final/scripts/benchmark_r3.py --kind input --pairs 5 --label NEW_LABEL
nice -n 15 /usr/bin/shasum -a 256 -c research/emulator_fast_r1/SHA256SUMS
```

本轮临时目录已清理，没有本任务残留仿真。清理回执见 strict_r4_final/runs/cleanup-r4.json。
