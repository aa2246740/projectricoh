本轮完成：P1-03 以完整解析链保护修复，A/B API5 全部门槛通过；2.83 倍仅为 API4 历史测量。

第一轮记录（以下保留历史测量，旧 API 3 的方法替换结论以“复审修复”更正）

本轮交付的是可选实现和复验工具，未切换主线 wrapper。没有新增原生设备模型；已按通知把模拟器快照工作转到通过第三轮复审的批量库。完整主机回归 ≤10 分钟、MAIN 冷启动 ≤10 秒均未证明达到。

固定输入与测量口径

输入清单固定 804 个文件；三个单元均使用 `firmware/package_v38_g137`，DAT SHA-256 为 `78dcbb9a2735cd84e55385683ce0296b97818ddf90f8b492d9003512dbeff3f8`。已放行批量副本另外冻结 32 个文件，见 [INPUTS.json](INPUTS.json) 和 [BATCH_INPUTS.json](BATCH_INPUTS.json)。原版、放行副本和 firmware 均只读。

指标以整个子进程的 user+system CPU 秒为主，包含其子进程；墙钟含该组启动、检查与输出。主机速度试验每项交替五对、并发固定为 1，逐对比较全部验收 JSON、后端步数和 op 数，要求两档 CPU 区间不重叠才保留。计时、负载、nice、超时、源与库身份、每个产物 SHA 均在每组 metrics/receipt 中。没有排除验收 JSON 字段；计时单独写在 metrics，允许排除列表为空。

原 Python 三单元串行基线：

| 单元 | CPU 秒 | 组墙钟秒 | 后端步数 | op 数 |
| --- | ---: | ---: | ---: | ---: |
| 50mm | 232.740 | 234.663 | 27,322,942 | 42,299,447 |
| 28mm | 231.944 | 233.510 | 27,277,611 | 42,229,715 |
| MOUNT | 236.837 | 242.476 | 27,284,282 | 42,239,487 |

合计 701.521 CPU 秒，调度端到端墙钟 710.892 秒。这是三组固定负载，不是约 34,000 CPU 秒的完整回归。后端一步是一次取指/指令包，另列其中的 op 数，不与相机主频直接换算。

保留的改动与速度表

每次只打开一处变化，先验等再测量。以下是各阶段在当时实现上的五对中位数；阶段代码、动态库和计时均保留。最终错误边界保护后又独立重测最终版，没有用阶段倍数相乘代替最终实测。

| 改动 | 前 CPU 秒 | 后 CPU 秒 | CPU 倍数 | 墙钟倍数 |
| --- | ---: | ---: | ---: | ---: |
| 解释循环、算术、分支和普通读取搬入 C，写仍同步 Python | 235.222 | 93.024 | 2.529 | 2.526 |
| 在 C 执行冻结 Harness.trace 已有的提前返回条件 | 95.820 | 45.280 | 2.116 | 2.060 |
| Python 边界之间暂存寄存器、PSW、ACC、PC 和映射描述 | 44.916 | 20.807 | 2.159 | 2.157 |
| 合并标准 Counter 增量及 16 条 tail，按字典版本复验类型 | 21.077 | 14.416 | 1.462 | 1.473 |
| 最终版：原 Python → C，含错误边界保护 | 230.410 | 14.575 | 15.808 | 15.700 |
| 参考 C 库按内容缓存，完整 golden/domain/集成检查 | 3.931 | 2.247 | 1.749 | 1.716 |

最终五对 Python CPU 范围 229.971–234.166 秒，C 为 14.289–14.747 秒；每对 189 个验收值完全相同，步数与 op 数相同。数据见 [最终五对](local/final-python-c-r3.json)、[各阶段](local/cbase.json)、[写筛选](local/write-filter.json)、[寄存器](local/native-state.json)、[计数](local/native-stats.json)、[编译缓存](local/cache-compile.json)。

编译缓存键包含实际编译器与选择到的工具文件 SHA、版本、参数、相关环境及编译器 `-M` 给出的全部依赖文件 SHA。每键文件锁加原子安装，避免并行编译写同一库。两工作者同时请求新键时实际只有一次编译、一次命中，等待锁约 0.068 秒，函数均返回字面预期值 42；改坏缓存库一个字节会重编译，全部结果和库字节 SHA 恢复一致。见 [并发自检](local/cache-concurrent-final/summary.json)。

C 后端的结果与错误验证

最终库 SHA-256：`15f9b4e4cc28ff727d56f269ef57f7b938bb115485cd528996761158922b072f`。只在显式 C 入口加载；构建清单校验本机 Python ABI、架构、全部 C/Python 源和库字节。复制来的九个其他 Python 文件和 STUBS.md 与原版相同，python_backend.py 的原实现前缀也逐字节相同；即使给出不存在的 C 构建清单，默认入口仍能构造纯 Python 后端。

C 保留 GIL，在断点、MMIO、未筛掉的写追踪、观察器、信号及退出前提交全部状态，回调后重新取对象与映射。影子后端仍共用原 regions/mmio/traces 和 bytearray。实例/类方法及代码被替换时转回 Python；不支持的容器或计数值保守转回原路径。全空间写追踪没有删除，未知回调仍逐次执行。

- [逐条及边界](local/differential-final/summary.json)：95 种真实编码/地址形式 ×64 组向量，共 6,080 组；覆盖 73 种本机操作，另外 40 个边界用例。包括同值写、重叠/只读映射、MMIO 宽度与权限、未映射/未对齐、一般并行与 trap/rte、动态方法和 Core 对象替换、回调读写全部公开 CPU 状态、部分指令后的异常、非法栈值/元组寄存器、自定义 Counter 值、无用的异常追踪容器及特殊步数上限。
- [UBSan trap](local/differential-ubsan/summary.json) 重跑同一批用例；[关闭暂存和合并的路径](local/differential-boxed/summary.json) 另跑 760 组与同样边界。长无观察区间、回调连续性、原 conformance 和 70 对串行 fork 均通过；最终库重跑记录见 [最终检查](local/final-smoke/summary.json)。
- [完整真实轨迹](local/trace-equivalence.json)：50mm 全部 27,322,942 步、2,383,980 次写入的 CPU/写记录逐字节相同；最终 22,482 个状态值相同，包含全部映射内存 SHA、寄存器、计数、tail 和调用记录。CPU tape SHA `228306c6cb9ae706f199a3cd8d27df62630ba3458c432ba5537d8d6daa56698a`；写 tape SHA `6f2d2ed488043b8a54db8977b9b019c4be1646a0e6eb5e9d3615be001e7b8d17`。观察器计时不参与速度表。
- [实际实现变异](local/mutation-native/summary.json)：把 C 的 ADD 故意改成多加 1，对拍报出两处失败；[真实 tape 变异](local/trace-mutation.json) 分别改坏一条 CPU 和一次写记录，均抓到。JSON 类型、顺序、字段、模拟器每种状态哈希和构建字节也做了独立变异自检。

真实 view-reentry：保留原七屏 ×五切点 ×两键，共 70 个子进程，71 份验收 JSON 的 304,827 个值完全相同，84,747,616 步相同。最终 C 为 468.841 CPU /480.651 墙钟秒，Python 为 791.413 CPU /838.609 墙钟秒，单对观测约 1.69 倍，未当作五对提速结论。每子进程有独立 JSON、日志、计数与输出映射。见 [真实套件](local/legacy-final-equivalence.json)。

该旧套件的 g137 私有适配绑定已通过 13,330 golden、2,504 domain、3,430 集成点（1133/1134/1163）、24 个默认值、3,430 个 plan 和 66 个重置序列的 v2 C 参考，并把 UI 数值读取从旧 11 字节改为 10 个 int16。原数学比较、所有 UI 断言、切点、按键和 3,000 万步上限均保留。源和适配记录在 [view-reference-origin.json](view-reference-origin.json)；原脚本未改。

这一组仍有 runtime_guard.watch 全空间审计，观测到 fast_writes/native_state_steps/deferred_steps 为零；它限制了整套收益。因此不能把 part1 的 15.81 倍外推到完整回归。

并行调度与断点续跑

[最终子集证明](local/scheduler-sealed.json) 中，三组串行墙钟 44.877 秒，最多二组自适应调度为 29.126 秒；CPU 43.614 /43.251 秒。每组全部输出与步数相同，最长任务先启动；负载 >8 时只推进一组。成功产物的全部 SHA、源、输入、库和配置相同才可续跑；三组成功时全部跳过，故意改坏结果后拒绝复用。失败/中断输出保留后重试，身份变化须新 run 名。这是单次子集调度证明，不是完整回归的墙钟承诺。

模拟器新基线与卡镜像缓存

使用已放行批量库 `018a6d9731d54b6b27e6729d4a8903a4cab5b8763a0ce92467ad91e02d2d8c95`，没有改其目录。私有快照驱动显式设置 fast、set_batch(True)、Panel.chain、输出/介质目录，并检查 batch_stats。首次 MAIN→候选点 42,572,307 步→完整 ADJ 3,120,000 步为 77.006 CPU 秒，包含首次保存缓存；目标点的 CPU/全部内存/全部设备哈希与原冻结候选点相同。

[五对交替](local/snapshot-bench.json) 的冷启动全过程中位数 73.113 CPU 秒，恢复后完整 ADJ 为 9.852 秒，实验缓存快 7.421 倍；每对完整 4,253 值证明一致，未少跑 ADJ、观察记录或调用轨迹。全部运行确实执行了 C 批量步，没有未声明钩子回退。首次恢复的 16.960 秒夹带状态变异自检，不用于五对倍数。

缓存键包含卡镜像 SHA、全部机器/库/源码身份、固定输入根、运行时、配置、候选步数/全状态及按键序列。任一身份叶、真实卡镜像字节或快照字节变更都会拒绝加载；损坏缓存可保留旧件后用冷启动重建。见 [身份与卡变异](local/snapshot-cache-checks.json)。

静态已证：Task 1 在设置当前任务优先级 127 后停在原厂 `0x2005C340` 自循环；Task 21 的 service 52 将状态置 1、超时置 -1，service 56 清该位并重新就绪，表示无限期睡眠。[反汇编与快照状态](local/task-analysis/summary.json) 支持这个解释。

正式默认启用仍不通过：原 strict_all_tasks_waiting 条件仍为 false，缓存元数据也保持 accepted=false。重复同卡实验必须显式允许候选；开机验收、重启读回、身份/卡/配置变化仍从 MAIN 冷启动。没有修改原候选点、原 RTOS 状态或原门槛。

批量基线另做了 1,000 万步 CPU 剖析：9,998,645 步确在 C 内，32,045 批、29,855 次 MMIO 转发，未声明回退为零。带剖析器共约 19.7 CPU 秒；_run_batch 自时间 13.60 秒包含 native 执行包络，不能全部归为 C 计算，计划链累计约 2.84 秒。此数只定位瓶颈，未当作提速。见 [profile](local/batch-profile/result.json)。本轮未改设备实现，未把历史 M2b/M2c/g145/hook_cases 放行冒充本轮新增验证。

构建与撤回记录

从冻结 engine.bin、reloc、layout 和 resident 身份重新构造 DAT，产物逐字节 SHA 等于冻结包；这是 DAT 封装构建，没有宣称重新编译全部固件 C。结果见 [DAT 构建](local/runs/build-pack/dat-pack/result.json)。核对器的一字节变异会失败。

- 写筛选最初漏了类版本的有效标志，类属性变异抓到；该版和一次 45.32 秒校准数据撤回，不参与保留倍数。
- Counter 合并最初每边界全量复验，单次 26.83 CPU 秒慢于已接受寄存器版约 20.81 秒，撤回；缓存字典版本后才测五对并保留。
- 三次边界修正覆盖异常后旧寄存器覆盖、pop 使用回调前 SP、非法寄存器/自定义计数值；失败重现、旧源码/库和中断的最终计时均保留，没有将原失败改记为通过。
- 反汇编缓存五对 JSON/步数相同，中位数约快 2.74%，但 CPU 区间重叠，已从活动入口撤回；原型和数据仅留在 ignored local/attempts。没有缓存 fork；原剖析及本轮调用量没有支持它优先于写审计。
- 隔离运行器曾因 common 同名、布局读取钩子、Popen 二次输出映射以及旧数学接口失败，原失败保留；host C 输出父目录问题也保留。动态 UBSan 被系统加载策略拒绝，只有后来的 trap 版计入通过。
- 一次最终续跑证明期间新增交付脚本，正确触发源码变化拒用；冻结工具后以新 run 重跑，成功跳过三组并拒绝损坏产物。

每次尝试见 [LEDGER.tsv](LEDGER.tsv)，源码、日志和原始结果由 [SHA256SUMS](SHA256SUMS) 封存。主机和模拟器测量均为本机离线模型，不能代替存储卡、相机或刷写验收。

可选入口

```sh
nice -n 15 /usr/bin/python3 -I -B tools/speedlab/build_ccore.py
nice -n 15 /usr/bin/python3 -I -B tools/speedlab/schedule.py research/speed_hillclimb/final-c.json --run review-c --max-workers 1
# 审阅后需要最多二组时，把上面的 max-workers 改为 2；同一身份断点恢复加 --resume。
nice -n 15 /usr/bin/python3 -I -B tools/speedlab/host_c.py --output research/speed_hillclimb/local/review-host-c --cache on
GXR_EMULATOR_BATCH=1 nice -n 15 /usr/bin/python3 -I -B tools/speedlab/schedule.py research/speed_hillclimb/emulator-card-cold.json --run review-boot --max-workers 1
```

加载可选副本的程序可设置唯一后端开关 `GXR_HARNESS_BACKEND=c`；不设置仍是原 Python。原 tools/native_harness 不受此开关影响。详细参数与复制套件的输出重定向见 [入口说明](../../tools/speedlab/README.md)。

下一轮优先把 runtime_guard.watch 原有的 UI 范围提前返回搬到 C，按实际 70 子进程套件测五对；随后在私有批量副本上尝试 IRQ/定时器设备及常用替身原生化。任何模拟器改动都保留全状态、M2b、M2c、g145、变异和第三轮 hook_cases 门槛，再交由用户另开复审。具体依据和边界见 [NEXT.md](NEXT.md)。

## 第二轮

本轮先修复两个 P1，再恢复爬坡。修复版 `tools/native_harness_c/` 与编译缓存已单独封存，3,349 项复审修复清单再次全通过；后续工作都在私有副本。只交可选入口，没有切换主线。完整 81 组回归按通知未跑，两个长期速度目标仍未证明达到。

保留：把全空间写审计的纯范围判断放进 C。

`research/review_g126/runtime_guard.py` 的 `watch()` 先调用 `touches_ui()`；不触及七段 UI 地址范围就直接返回，命中后才计数、检查写入来源，违规时抛错。它没有在每次普通写入上记录写入者或统计全空间写入。私有实现只搬这段提前返回；命中、主机写入和 native_memset 仍调用原 Python 审计。函数、代码、全局、builtins、范围表的身份或版本不符时回退。

以下五对完整套件交替串行运行，自己的 CPU 工作负载并发固定为 1，nice 为 15，逐组记录系统负载；CPU 秒含子进程。对照与候选使用同一 API 4 私有库，只切换 `GXR_HARNESS_UI_AUDIT=0/1`。

| 负载与改动 | 前 CPU 中位数 | 后 CPU 中位数 | CPU 倍数 | 墙钟倍数 |
| --- | ---: | ---: | ---: | ---: |
| view-reentry 全部 70 个子进程，原 C → 加 UI 审计过滤 | 507.745 秒 | 179.189 秒 | 2.834 | 2.834 |
| P1 修复后的参考库编译缓存，完整 golden/domain/集成负载 | 4.367 秒 | 2.360 秒 | 1.850 | 1.892 |

写审计对照 CPU 范围为 496.854–520.283 秒，候选为 174.506–188.731 秒，区间分离。墙钟中位数为 544.435 → 192.082 秒。第二行属于编译缓存自身，不能与第一行倍数相乘。第一行也不能外推成 81 组完整回归的倍数。

| 写审计候选门槛 | 结果 |
| --- | --- |
| 完整真实套件 | 70 个子进程全部完成，71 份 JSON 的 304,827 个值与原 Python 基线相同；每次均为 84,747,616 个指令包。 |
| 全部 CPU 写入 tape | 141 份文件、9,548,492 条写入、241,077,497 字节，实际逐块比较，完全相同。 |
| 审计命中 tape | 71 份文件、994 条事件、41,186 字节，顺序、地址、PC、来源与字节完全相同；原 watch 函数代码未包装或改写。 |
| 实际漏报变异 | C 库故意少回报一次命中，事件数从 994 降到 993，被 tape 抓到；原验收 JSON 仍相同。 |
| 回调与范围边界 | 复审的 19 项、trace 的 6 项、UI 范围与动态替换的 90 项全部一致。 |
| 原有逐条对拍 | 最终明确核对 6,080＋40 项；boxed 路径 760＋40 项；均无差异。 |
| 固定三个单元 | 每单元 189 个验收值、指令包数和 op 数与修复版及冻结 Python 证据相同，结果 SHA 均为 `40a01d3ff2d9d328380a6054cb7a6f8c29270e31686613a98bdb1b7e1f9b784d`。 |

私有库 SHA-256 为 `fd90b5ce232fba1f069e909e30880b96698ddc8f0a30a49f8f8011ee8b66f6b0`。该项只在 `tools/speedlab/harness_c_next/`，未合并到待复审的修复版。证据：[五对速度](local/round2/r2-api4-bench/summary.json)、[写 tape](local/round2/r2-api4-tapes/summary.json)、[审计 tape](local/round2/r2-api4-audit/summary.json)、[真实 C 漏报](local/round2/r2-api4-mutation-witness/summary.json)、[最终逐条与三单元](local/round2/host-next-final.json)、[汇总](local/round2/host-audit-final.json)。所有验收比较都未排除字段。

可选入口，在仓库根运行，换一个未使用过的输出名：

```sh
TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/speed-hillclimb \
GXR_HARNESS_BACKEND=c GXR_HARNESS_UI_AUDIT=1 \
nice -n 15 /usr/bin/sandbox-exec -f research/speed_hillclimb/round2.sb \
  /usr/bin/python3 -I -B tools/speedlab/legacy_next.py \
  --side c --name review-ui-audit --limit-seconds 3600 \
  research/emptystack_v38/run_existing.py --crc-implementation native \
  --timeout-seconds 3600 research/review_g126/view_reentry.py --unit 50mm
```

`GXR_HARNESS_UI_AUDIT=0` 是同库对照；默认入口仍用 Python。输出、参考库、日志与子进程结果都重定向到本支线的 local。需要重新完整核对私有副本时，运行 `host_next_run.py --name <新名字>`，它固定检查 6,080/760 的逐条用例数和三个单元。

撤回：只把 IRQ/定时器 MMIO 读取放进 C。

先保持设备写入、时钟与中断进入的语义不变，只尝试在 C 中读取原 Python 状态的镜像。最初的 500 万步没有发生原生目标读取，不能作为目标路径的性能证据。2000 万步确实发生 4,697 次原生读取，但 CPU 从 30.934 增到 71.521 秒。剖析发现，每次退出都在 Python 扫描全部 667 段 MMIO 映射。

第二次只改映射身份核对：用 CPython 列表指针字节检查映射是否更换，并继续检查方法接收对象、代码与类版本。13 个边界用例通过，包括原列表内更换等值接收对象；2000 万步降到 33.251 秒，仍慢于本次对照的 29.624 秒。

| 完整冷启动至候选点，再执行 ADJ | 放行批量版 CPU 秒 | 第二次候选 CPU 秒 | 决定 |
| --- | ---: | ---: | --- |
| 无卡 | 57.862 | 67.758 | 撤回。 |
| 有卡 | 74.335 | 87.725 | 撤回。 |

这两行是各一次完整负载，用来拒绝候选，不作可交付倍数。两种输入在 100 万步、1000 万步、各自开机候选点、ADJ 结束点的 CPU/全部内存/全部设备/观察记录/调用轨迹哈希相同。真实 C IRQ 读取翻转一位的变异抓到三项差异。

设备候选性能未通过，未进入 M2b、M2c、g145、hook_cases 的最终切换门槛，不能交付该原生设备开关。源码与库已归档到 [失败尝试](local/round2/attempts/native-mmio-v2/tool)，`emulator_next` 的 backend、bridge 与库已恢复为放行批量版；库 SHA 为 `018a6d9731d54b6b27e6729d4a8903a4cab5b8763a0ce92467ad91e02d2d8c95`。原放行目录未写入。见 [完整状态对照](local/round2/native-mmio-v2-states/summary.json)、[变异](local/round2/native-mmio-mutation.json)、[撤回原因](local/round2/native-mmio-v2-decision.json)、[实际恢复](local/round2/native-mmio-rollback.json)。

快照：精确拒绝与缓存保护已补，正式启用仍不接受。

新候选入口是 `tools/speedlab/snapshot_policy.py`，版本 `gxr-scheduler-point-3`。封存的第一轮 adapter 不再作为新实验的宽泛豁免入口。新策略绑定原厂 MAIN SHA 与放行批量库身份，只接受 Task 1 为当前任务、PC `0x2005c340`、优先级 127、状态 0，Task 21 为状态 1、超时 `0xffffffff` 且有原厂无限睡眠服务记录；其余任务均须等待，设备与 UI 的原有 quiet 条件继续保留。

负向自检把 Task 2 改成就绪、改错空闲任务 PC/优先级/状态、改错 Task 21 状态或超时；即使重算快照与 RAM 哈希并伪造“已通过”元数据，保存或恢复仍拒绝。默认恢复、开机验收和重启读回用途均拒绝。开机验收与重启读回继续从 MAIN 冷启动。

卡缓存键包含卡 SHA、全部原身份字段、用途范围、策略版本和源码 SHA。每台机器还绑定其实际冷启动或原快照的输入身份，不能把旧 RAM 换标成另一张卡。发布采用独立不可变 generation、三件产物的交叉 SHA、文件锁和原子 HEAD；中断发布保留旧 HEAD，重建生成新代，混代、缺件、身份漂移和损坏均拒绝。多次恢复各用新介质和独立状态，并实测修改 A 不影响 B；本轮没有跑并行恢复压力测试。

| 使用实验 | 冷启动与恢复对照 | 行为门槛 |
| --- | --- | --- |
| 原 ADJ 按键序列 | 4,039 个值、全状态、观察及调用轨迹一致。 | 完成。 |
| 实际 Task 8 文件实验 | 427 个值一致，创建、写入及读回 4,099 字节，读取尾部未改，独立 FAT 检查通过。 | 完成；仅同次开机读回。 |
| 原厂接口唤醒 Task 21 | 在 42,754,496 步，两边都切到 Task 21，在 PC `0x200759e8` 对 `0xff701802/2` 未映射写入时 fault；完整状态、观察和错误相同。 | 未完成，不能视作唤醒成功或正式快照通过。 |

文件实验最初等待旧帮助器的 `0x2005de00`，完整 1000 万步仍未到达，失败已保留。根据实际 ADJ 调用轨迹，把首次会合点改到 Task 6 的缓冲接收入口 `0x2005e078` 后，继续原帮助器的分配、队列发送、Task 8/用户栈/信号量/调用返回检查及全部步数上限，文件实验才通过。

因此快照仍为 `accepted=false`，没有开启默认恢复。`restore(..., purpose=..., allow_candidate=True)` 仅用于明确用途的候选研究；`Cache.open` 强制新运行目录并写 origin.json，记录 MAIN 冷启动或快照恢复、用途、策略与代。见 [精确拒绝及发布自检](local/round2/snapshot-policy-v3-checks/summary.json)、[ADJ 与唤醒边界](local/round2/snapshot-v3-experiments/summary.json)、[文件实验](local/round2/snapshot-v3-file-rendezvous/summary.json)、[旧卡换标反例](local/round2/snapshot-probe/before-provenance-fix.json)。

未保留的核对器与工具尝试也记在账本：第一次子进程 tape 命名重复、P1 插入时中断的旧实验、只比较验收 JSON 时没抓到实际审计漏报、私有补测驱动的输出名及用例轮数错误，都保留原始记录。最后两项已修正，并以最终 6,080＋40 / 760＋40 的原始门槛重新通过；没有把早先失败改写成 PASS。

下一轮先等新的 C 后端复审结论，以及用户允许执行完整 81 组的通知。设备方向需要把状态与有效性核对一起移出 Python 边界，再尝试更完整的定时器/IRQ 原生实现；继续用同一状态与功能门槛。快照先只读查清 Task 21 的 `0xff701802` 通道访问，补齐唤醒行为后再申请正式启用。最终汇总在 [final.json](local/round2/final.json)，逐次决定在 [LEDGER.tsv](LEDGER.tsv)，交付字节以 [SHA256SUMS](SHA256SUMS) 为准。

## 复审修复

两个 P1 已修复，并完成指定的复验，待用户另开复审；没有切换主线。原复审的“不可以切换”结论和八个失败反例保留，没有改记为通过。第一轮关于任意实例方法替换都会回退的表述过宽；旧 API 3 的 15.81 倍只能作为当时固定验收路径的历史测量。

当前库 SHA-256 为 `011de81d91788746320fcbbe6cc4e7a24f0e4b7f9861ace9ff20b305b3e288b1`，API 为 4。版本号把这次接收对象合同与旧库区分开；加载器拒绝旧 API。`method_same()` 现在要求实际类型为绑定方法、`__self__ is obj`、`__func__` 和 `__code__` 均相同；观察器的写代理仍按独立合同检查。回调中替换绑定或赋入未绑定函数时立即转回 Python，保留当前指令包剩余 slot 的顺序。

编译缓存格式改为 3。每次请求重新捕获环境并核实工具，执行已选择的编译器；身份查询、依赖扫描和实际编译共用捕获的环境。键包含全环境 SHA，明文只保留已有工程环境字段。编译后再核实依赖和工具字节，变化时拒绝安装产物。旧格式的键不会被复用。

| 复验 | 结果 |
| --- | --- |
| 复审 19 个独立用例 | 19/19 一致，八个原失败与另外十一项全部通过。 |
| trace 独立用例 | 6/6 一致，控制样本确实走快速写，其余需要的回调均保留。 |
| 编译缓存 | 14.0 首次为 140000；15.0 缓存与直接编译均为 150000，换键。两层头文件、参数、损坏库重建和并发单次编译继续通过。 |
| 扫描中环境改变 | 扫描后故意把实时目标改成 15.0；第一次扫描/编译仍共同使用 14.0，第二次共同使用 15.0，返回 140000/150000，依赖头文件也正确。 |
| 逐条对拍 | 6,080 组真实编码向量与 40 个边界用例均一致；UBSan trap 同批通过；关闭暂存/合并的 760 组和边界继续通过。 |
| 实现变异 | 实际 ADD 多加 1 的新库被抓到两处差异，核对器自检通过。 |
| 固定三个单元 | 每单元全部 189 个验收值与冻结 Python 基线相同，未排除字段，步数与 op 数相同。 |
| 真实 view-reentry | 70 个子进程全部完成；71 份 JSON 共 304,827 个值相同，84,747,616 步相同，全部确实进入 C 循环。 |
| 完整 CPU / 写 tape | 27,322,942 个指令包、2,383,980 次 CPU 写入逐字节相同；最终 22,482 个状态值及 189 个验收值相同。 |
| 默认入口 | 不设开关或显式 python 时仍是纯 Python，不导入 C，坏 C 清单也不影响默认入口。 |

完整 CPU tape SHA 为 `228306c6cb9ae706f199a3cd8d27df62630ba3458c432ba5537d8d6daa56698a`，写 tape SHA 为 `6f2d2ed488043b8a54db8977b9b019c4be1646a0e6eb5e9d3615be001e7b8d17`，均与原 Python 记录相同。本版真实套件一次测得 496.514 CPU 秒、545.679 墙钟秒；本节没有重新认证主机解释器的首轮五对倍数。

修复后参考库缓存另做五对完整 golden/domain/集成负载，CPU 中位数 4.367 → 2.360 秒，1.850 倍；控制范围 4.211–4.677，缓存范围 2.334–2.403，区间分离。全部结果和产物 SHA 相同，一字节缓存损坏仍重建并恢复相同结果。这是参考 C 编译缓存的收益。

证据：[总结果](local/review_fix/result.json)、[19+6 项与缓存](local/review_fix/fixed/summary.json)、[环境边界](local/review_fix/environment-boundary/summary.json)、[完整门槛](local/review_fix/gates.json)、[真实套件](local/review_fix/view-equivalence.json)、[完整轨迹](local/review_fix/trace-equivalence.json)、[缓存五对](local/cache-compile-p1.json)。复审脚本的五份测试体逐字节复制，只有独立 scope 适配输出和本任务边界，见 [来源](local/review_fix/copied-cases.json)。

快照不与 C 后端捆绑放行。整项豁免已在新的 snapshot_policy.py 候选中换成精确任务判定，并补齐身份、发布及独立介质保护；ADJ 与真实文件实验通过。Task 21 唤醒在冷启动与恢复两边均停于同一未映射定时器写入，行为门槛仍未完成，因此 accepted=false；具体证据见“第二轮”。

## 复审修复 2

P1-03 已修复，A 与 B 同步通过指定门槛，待独立复审。原复审的两个父类反例及四个控制样本逐字节复制，另保留原 19 项和 trace 6 项。默认仍是 Python，B 仍只在私有副本，没有合并或切换。

| 修复产物 | API | 最终库 SHA-256 |
| --- | ---: | --- |
| A：tools/native_harness_c | 5 | `29e1e95b52ea5d714b6bc78edb75bd4d9f1123bed071357530f7d710ce2a551f` |
| B：tools/speedlab/harness_c_next | 5 | `a6c79c5bf3d1e9ee4838805e00d6ab919797e487895d66e39a7afe04e2e72058` |

保护固定了完整解析结构：实例方法覆盖、实际 MRO/基类、各层原始类字典中定义的存在性、函数与代码对象、metaclass 和属性解析钩子，以及 super 使用的类闭包。被 Core.op/read/write 遮住的祖先定义也在其中；Counter 原生计数依赖及写事件构造方法一并保护。字典版本只用来加速重新核对，函数代码和闭包始终检查；MRO 按类对象身份逐项比较，恢复同一解析结构后可继续使用 C。构造跟踪和无关类标注不触发误退回。

检查使用原始 tp_mro/tp_dict 和实例字典，避免执行已经被改写的 getter 或 metaclass。回调一旦改变结构，刷新阶段先关闭原生暂存并直接取回 bookkeeping 字段；当前指令尚需写回的寄存器和计数仍按原 Python 访问顺序处理，包内剩余 slot 沿现有 Python finisher 执行，之后继续 Python 路径。

首版保护虽然抓到了结构变化，刷新时仍多调用新 getter。补充例记录到 Python 19 次、C 35 次属性访问，已保留失败和对应源/库；最终为 19 对 19。又用真实编码覆盖普通 store、前增 store、load、后增 load、pop 的回调后属性访问。不是通过删除观察记录来通过比较。

| 门槛 | 本轮新执行结果 |
| --- | --- |
| 第二轮复审新增六项 | A、B 均 6/6；含断点与写回调替换父类 op 的两个反例。r9 分别为 44/39，新方法调用分别为 4/3 次，与 Python 一致。 |
| 原 19 项与 trace 6 项 | 两份库各 19/19、6/6 一致。 |
| 补充同类反例与控制 | A、B 各 19/19：祖父类、父类代码对象、遮蔽的祖先 read/write、同函数换定义类、实例覆盖、metaclass MRO 注入及 getter、super 类闭包、Counter 缺省计数和写事件构造器。无关标注控制样本确实留在 C。 |
| 原逐条门槛 | A、B 各 6,080 指令向量＋40 边界一致；boxed 各 760＋40 一致。 |
| UBSan | A 的同批 6,080＋40 通过 trap 档，无 sanitizer 退出。 |
| 固定三单元 | A、B 各三单元，每单元 189 个值、指令包与 op 数相同；原始结果 SHA 均为 40a01d3ff2d9d328380a6054cb7a6f8c29270e31686613a98bdb1b7e1f9b784d。 |
| 完整 view-reentry | A、B 过滤关、B 过滤开各实际执行 70 子进程；各 71 份 JSON、304,827 个值和 84,747,616 指令包与冻结 Python 相同，未排除字段。 |
| 审计 tape | A、B 两档以及封存的既有全套 tape，均为 71 文件、994 事件、41,186 字节，实际逐块比较相同。 |
| B 全部 CPU 写入 | 两档各 141 文件、9,548,492 写入、241,077,497 字节，实际逐块相同。 |
| 完整 CPU/写轨迹 | A 的 50mm 全部 27,322,942 指令包及 2,383,980 CPU 写入，与原 Python tape 逐字节相同；最终状态与验收值继续一致。 |
| 真实变异自检 | 编译关闭方法解析保护后，两个新反例再次不一致；API5 下重编译漏审计命中一次的变异，994→993 被抓到。 |
| API 与默认入口 | 新源码身份配真实旧库后，API4 明确报 C core API differs；默认或显式 python 保持 Python，坏 C 清单不影响默认入口。 |

本轮是正确性修复，没有重新认证速度倍数。旧 API4 的 2.83 倍仅保留为历史；下表是本轮单次记录，B 两档额外记录全部 CPU 写入，不能拿 A 与 B 的耗时直接算优化倍数。

| 完整 70 子进程运行 | CPU 秒 | 墙钟秒 |
| --- | ---: | ---: |
| A，审计记录 | 578.286 | 743.354 |
| B，过滤关，审计与 CPU 写记录 | 671.842 | 953.075 |
| B，过滤开，审计与 CPU 写记录 | 563.567 | 717.488 |

A 仍通过 GXR_HARNESS_BACKEND=c 选择，默认 python。B 另在私有入口选择：GXR_FIX2_TARGET=b、GXR_HARNESS_BACKEND=c、GXR_HARNESS_UI_AUDIT=1，运行 tools/speedlab/legacy_fix2.py，所有输出重定向到本支线 local。整轮复验用新输出名字，入口如下。它串行等待每个子任务并保留每组日志与实际库 SHA。没有跑完整 81 组，也没有改快照接受结论。

```sh
nice -n 15 /usr/bin/python3 -I -B tools/speedlab/review_fix2_run.py --name repair-review
```

保留两项驱动准备错误：-I 下初版自写例缺本地导入目录，未执行 CPU；初版 API 拒绝测试漏设 c 开关，默认 Python 正常退出，未计为 API 检查通过。修正后均用新目录重跑。首次资料收集曾并发提交三个只读查询，偏离两个进程上限；随后查询与 CPU 工作负载改为串行。所有命令用 nice 15；高负载期间只运行一个 CPU 工作负载。超时至少取历史时长三倍。

旧交付报告、账本、SHA 与 A/B 完整旧字节已留在 local/review_fix2/before。冻结固件及放行批量模拟器输入再次核实不变。写入仅在授权目录与专用 TMPDIR，未联网、访问存储卡、做 Git 写操作或开子代理。

证据：[汇总](local/review_fix2/result.json)、[完整门槛](local/review_fix2/final2/summary.json)、[测试体来源](local/review_fix2/copied-cases.json)、[getter 原差异](local/review_fix2/mro-v2-a/local/mro-cases/class-getattribute-observed.json)。下一步由用户另开独立复审；速度优化和 B 合并均等待复审结论。

