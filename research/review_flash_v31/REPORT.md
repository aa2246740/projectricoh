不可以刷

# v3.1 第三次刷机前独立对抗审查

本结论针对候选 `ilaunch3`，SHA-256 为 `495841f145daea056c435f7d40c00586984b55675ea56b05674f2bbb2775b295`。F01–F07 的原反例已修复，但新增 F08 证明撤回代码仍会读取已释放的 view 槽位，或改写同址复用的新对象。当前摘要不放行。没有发现已证明必然发生的冷启动 P0，也没有观察相机事故。

栈不再单独构成刷机阻断。已纳入完成后的栈研究，并独立核对其 227 项 SHA-256。任务 6 的 16 KiB 栈、所列路径扣除后约 15 KiB 的模型余量，支持把剩余栈风险留给可恢复条件下的上机测量。这个判断不豁免 F08，也不把入口 SP 采样当成完整峰值证明。

日期为 2026-10-24。审查对象是用户的 GXR 机身 1.51，以及官方 1.51 的 A12 50mm、MOUNT A12。Stage2l 日常使用和官方菜单回退的设备记录按用户给定事实使用。本轮只读共享检出，新增文件仅在本目录；没有改源码、构建固件、操作相机或存储卡、刷机、启动子代理、sleep、轮询、安装包、commit 或 push。A12 28mm 的结果仅是额外主机覆盖。

## 1. 按严重度排列的问题

### F08 · P1，有条件的内存安全缺陷：撤回记录保存了地址，没有证明槽位仍属于原生 view

已核实：[shared.c:61](../../firmware/resident_v31/resident/shared.c:61) 接受整个 `0x20000000..0x207FFFE8` 范围内的 view 数组，包括堆数组，把两个 state 指针槽的地址保存到 root。随后 [shared.c:79](../../firmware/resident_v31/resident/shared.c:79) 的 `rv_ui_abort` 只检查地址落在宽泛 RAM 范围内，就读取槽位；内容等于旧 snapshot 地址时，还会写回原厂 state。没有槽位分配代次、当前 view 归属或存活证明。

最终 resident 的 `rv_ui_abort` 在 `0x20053D60`。第一槽的实际读取、写入分别在 `0x20053E78`、`0x20053E84`；第二槽在 `0x20053DF4`、`0x20053E00`。正常出口会在 `0x20053E48` 清掉恢复记录。服务归档共享同一份源逻辑。反汇编和原字节均保存在本任务 local，见 [机器码证据](local/EVIDENCE.md)。

独立夹具通过真实 `RV_UI_LIST`、`RV_UI_VIEW` 发布页面，再分别输入两种失效：

1. 释放保存 view 槽位的 16 B 原生数组。调用真实 `rv_ui_abort` 时，地址转换 double 当场检测到对 dead allocation 的访问，程序退出 91。它没有读取失效 UI 快照，却读取了同样会失效的槽位容器。见 [原始失败](local/host/expired-slot.log)。
2. 让当前 native view 改用另一数组，释放原数组，并由分配器 double 在原地址重新分配同尺寸的新对象。新对象某个 word 恰好保存旧 snapshot 地址。撤回把新对象 `0x20708544` 的该 word 改成原厂 state，并返回成功、擦除记录。见 [同址复用反例](local/host/reused-slot.log) 和 [夹具](local/host/review_behaviour.c)。这是实际 free/reallocate 的主机模型，不是相机上的原生分配器执行。

推断：对应时序发生时，会造成撤回路径 UAF、其它原生对象被改写或系统失常。先设置 `DISABLED_UNTIL_REBOOT`、停止旧引擎和不 free 主块，都不能阻止这次非法读写。名称表先恢复，再触及失效槽位，也可能留下半恢复状态。

未知：本机正常流程是否会把这种堆数组交给 part 2，并在 root 存活时回收它。官方初始化 `0x201C05F4` 实际把 part 2 数组设为固定 RAM `0x205A279C`，所以不能宣称上述堆时序已在设备上可达。当前实现和开发报告却明确支持堆内槽位，不能把这种支持写成安全保证。

修复建议：首轮只允许已经证实长期有效的原生固定数组及槽位，在发布前拒绝未知或堆内数组。若保留堆数组支持，就需要实际存活/代次约束；失去证明后不能凭“地址仍在 RAM、word 仍相同”写入。只增加分配头检查不能解决同址复用。修复后重跑这两个反例及原有两层、旧数组、新页面保留用例，再审新候选摘要。

### F09 · P2：H07 的 native close 优先级与三态引擎合同不一致

已核实：[abi.h:10](../../firmware/resident_v31/resident/abi.h:10) 写的是 `CONSUMED keeps the page`，但 [hooks.c:81](../../firmware/resident_v31/resident/hooks.c:81) 对 native r4=0 无条件撤回并选择关闭桩，即使引擎返回 CONSUMED。独立结果如下，见 [完整矩阵](local/host/h07-matrix.log)。

| native r4 | 引擎结果 | 实际动作 |
|---|---|---|
| 0 | PASS / CONSUMED / CLOSE_AND_PASS / FAULT | 都关闭；FAULT 另停用。 |
| 1 | CONSUMED | 保持自有页。 |
| 1 | PASS | 撤回自有页，走保持桩，返回原厂调用者。 |
| 1 | CLOSE_AND_PASS / FAULT | 关闭；FAULT 另停用。 |

这不是 F04 的旧遗漏：关闭现在会调用 native hide、清 overlay，原生返回值也已正确。当前产品在 native close 时主动返回 CLOSE_AND_PASS，实际 A4 流程通过；因此未据此判定当前产品必然错误关闭。但“引擎决定保持/关闭”这个通用合同并未完整兑现。

修复建议：明确 native 强制关闭与引擎 KEEP 的优先级。如果沿用任务要求，让引擎明确决定 KEEP/CLOSE/PASS，不要把普通 CONSUMED 再解释为 close；若 native close 必须优先，须同步收紧 ABI 和引擎调用合同，并验证保存、取消与强制退出的区别。

### F10 · P2：H09 安全收尾已隔离，行为仍不完全等价于 Stage2l

已核实：Stage2l 最终 `rfw_grain_check` 在 `0x2005414C` 每次读取当前 `S+0xC9D`。v3.1 则在提交时缓存等级，最终 `0x200531D0..0x200531D4` 从 root 取缓存值写 packet。v3.1 还要求当前图片尺寸等于提交时尺寸，而 Stage2l 对每次当前尺寸检查允许集合。

真实 v3.1 C 反例见 [H09 差异](local/host/h09-differences.log)：提交等级 3 后把当前等级改成 1，packet 仍是 3；尺寸由允许的 1 改成同样允许的 2 后，v3.1 透传，Stage2l 会应用颗粒。推断是照片效果不同，不是已证实的越界或变砖。

修复建议：若要求 Stage2l 等价，按相同门限读取当前等级和尺寸；若保留快照策略，明确说明改尺寸会停用颗粒、等级采用提交值，并将这两项列入照片验收。空文件及无有效 grain 时不受此问题影响。

### F11 · P3：两份产品“引擎字节相同”的交付说明不准确

已核实：base 与 huzi 的引擎区均为 50,176 B，但有 548 B 不同；保留的 `local/product/m32r-lto/engine.elf` 对应 huzi。进一步逐项核对后，274 个变化 word 全部是指向 `.bss` 的静态重定位类型 64，低半部统一相差 400，正好等于两份容器文件长差。其余引擎字节相同，base 也与自己保存的 `engine.bin` 一致。未发现因此产生的错误跳转或错误 BSS 布局。

证据为 [五容器核查](local/containers-independent.json) 和 [可复跑检查器](local/container_checks.py)。建议修正开发报告，并按 variant 保留对应 ELF。此项不是刷机阻断，也不把合理的 BSS 重定位误报为代码损坏。

## 2. F01–F07 复审结果

| 问题 | 本轮结果与证据边界 |
|---|---|
| F01，IRQ 极性和配对。 | 已修复。resident save/restore 在 `0x2005451C / 0x20054528`；resident、服务及五容器共 458,752 个 16 位 PSW 向量通过，旧极性 8 个反例被拒绝。编译后 8 个函数的 save token/restore 分支检查通过。 |
| F02，两层 view。 | 原反例已修复。独立 1,968 B 快照不随主块释放；一层、两层及当前数组变化均恢复已记录引用。槽位容器本身失效另见 F08。 |
| F03，post 丢 LR。 | 已消除。最终 ELF 无 post/notify/epochs 桩；H10–H37 共 28 点逐字节等于官方。旧 post 反例已没有可执行入口，不以人为重建旧 post 充当复测。 |
| F04，H07 关闭/保持。 | 旧缺陷已修复。r4=0/1、PASS/CONSUMED 的真实 C 路由通过；最终关闭/保持桩 256 个向量检查 hide `(2,1,0)`、overlay、返回值和栈平衡。通用合同差异另见 F09。 |
| F05，同址误 free。 | 原反例已修复。旧主块换成同头同址新对象后，自检拒绝旧引擎，retire 不 free 替代对象。跨 entry lease free 被拒绝。 |
| F06，快照失效/堆范围移动。 | 原反例已修复。快照被 ASan 毒化后仍能从 root 恢复固定 view 槽；堆范围移动不再抹掉未恢复引用，失败撤回保留记录。它没有证明槽位自身可释放，见 F08。 |
| F07，行号。 | 已修复。native 1/16 传引擎 0/15，H01/H02 加一；0/17 拒绝。产品真实 C 的末行关闭重开仍为 native 16 / engine 15，三单元通过。A4 native 1/6/11 对应 -5/0/+5。 |

证据：[resident 原始日志](local/host/behaviour.log)、[独立边界结果](local/resident-review-summary.log)、[IRQ](local/irq-machine.json)、[配对](local/irq-pairs-machine.json)、[H07 汇编](local/h07-machine.json)。IRQ 含义按 [Renesas M32R 软件手册 §1.3.1](https://www.renesas.com/en/document/mah/m32r-family-software-manual) 核对，IE=1 允许中断。

## 3. 停用、一次加载及恢复原厂值

已核实：retire 先置停用状态和 STOP/ATTEMPTED，再撤回 UI，最后清主块资格；没有关闭旧 fd 或释放不确定旧地址的路径。13 类自检失败后均没有旧引擎执行、重新加载或新增分配。READY 重开复用主会话和单个快照；一次加载失败后不再重试。loader 五类文件/分配故障和 SD 变化用例均关闭自己的 fd，峰值为 1。

已核实：恢复名称、七项数量、两个原厂 cursor、details 选择和已记录 view 时，不解引用失效快照或 session。原厂 cursor 预先限到 1..7。已经指向原生新 state 的有效槽会保留；无法写回时停用并保留记录。F08 表明“恢复记录位于 root”本身不等于其指向的槽永久有效。

实际产品三单元各做了末行重开、A4 OK、native keep=1、连续五次重开。均无新增分配，保留 3 块、请求总量 91,152 B。产品安装还会短暂申请两块各 65,536 B 的缓冲，连同保留块约 222,224 B，未计分配头、对齐和原生其它分配。分配不足已覆盖失败路径，但真实堆容量占用仍须设备验收。

未知：root 整体被重载或丢失时，“一次开机一次加载”标志也会丢失。全 FF root 只在可识别的冷状态初始化；若仍看见扩展列表，会先回退并停用。完整 root 丢失后，任意旧数组或原生消费者已取走的指针不能从丢失的信息中找回。该限制不能被“不 free”消除。

## 4. H05/H09、通用按键与 A4

H05 与 H09 的最终特殊分支都在通用自检之前返回。H05 非 READY/非 owned 时保持 root、frame；H09 无有效已提交 grain 时同样透传。新增五类资格失效用例核对 root、frame、free 计数和引擎调用不变。H09 没有文件、分配、free、retire、自检或事件记录调用。它与 Stage2l 相同的是默认重放和原 packet 门限，效果等价的例外见 F10。

H06、H08 在 owned 页交引擎处理。CONSUMED 走自有续接；CLOSE_AND_PASS/FAULT 撤回并退出；PASS 先恢复原厂七行，撤回成功才重放，原 r8 保留。失败撤回用例确认不把扩展行号交原厂 setter。H07 的自有关闭与保持桩都跳过原厂七项 setter，返回 1；关闭桩另执行 native hide，优先级差异见 F09。

冻结源码重建的产品检查通过 18 种场景 × 3 单元，共 54 组。覆盖首次不移动直接 OK、首末配方、A4 进入、上下、四参数循环、端点、保存、取消、保存失败、不确定写入停用、安装、双槽及重启回退。另加的三组真实产品 C 检查确认末行重开和 keep=1 的 A4 OK。文件、native UI、RPC、分配和相机动作均为主机 double，不能据此声称实机按键或拍摄已验收。

证据：[54 组结果](local/product-results.json)、[额外产品流程](local/product-host/review-flow-0.log)、[H06 撤回失败](local/host/failed-retract-pass.log)。

## 5. 七处 hook、重放与中间入口

| Hook | 官方位置 / 覆盖 B | 最终桩 | 续接与 Stage2l 对照 |
|---|---|---|---|
| H01 | `0x2028709C` / 8 | `0x20052BA8` | 默认重放两条绝对地址构造，到 `0x202870A4`；owned 到 H02 所在 `0x202870A8`。Stage2l 在此替换 getter。 |
| H02 | `0x202870A8` / 4 | `0x20052BCC` | 默认复制及立即数后到 `0x202870AC`；owned 到 `0x20287118`，与 Stage2l 的绕过枚举目标相同。 |
| H05 | `0x201FEBE4` / 8 | `0x20052BEC` | 默认恢复官方 details 地址，到 `0x201FEBEC`；owned 选空 details。Stage2l 静态替换为空 details。 |
| H06 | `0x202BE24C` / 4 | `0x20052C10` | 默认重放上半地址，到 `0x202BE250`；owned 到 `0x202BE6A8`。活动 8 门限保留。 |
| H07 | `0x202871D8` / 4 | `0x20052C30` | 默认 push LR 到 `0x202871DC`；自有关闭/保持返回原 caller，收尾已补齐。 |
| H08 | `0x202BB968` / 4 | `0x20052C88` | 默认重放 r11 上半地址，到 `0x202BB96C`；owned 到 `0x202BCF58`。活动 8 门限保留。 |
| H09 | `0x2017098C` / 4 | `0x20052CA8` | 默认 push LR 到 `0x20170990`；与 Stage2l 同一 sender 入口，packet 行为差异见 F10。 |

七处均无需要搬迁修正的 PC 相对原指令。默认桩保留 r0–r13、LR、PSW，共同保存加外层 LR 为 68 B。896 组默认重放、其它五种接管 640 组及 H07 256 组均通过寄存器、条件位、SP 和有效栈检查。H06 自有返回 r8=0，而 Stage2l 为 2，是已有不同策略，不能单凭数值不同判定 ABI 错误。

全官方文件 BE32 指针、16 个映射段的直接分支编码及地址构造扫描，未发现覆盖区中间入口；两个 8 B 点的关键内部字地址为 `0x202870A0`、`0x201FEBE8`。256 处已识别相对表中也无命中。任意 RAM 计算目标和未识别表仍未知，不把负扫描当作全程序 CFG 证明。

仅用指定 objdump；20 份反汇编实际显示的 3,935,216 B 全部逐字节对回冻结输入。子集执行器不模拟真正中断、SPI/SPU 切换、ACC/BPC、缓存、native callee 或并发；额外特殊寄存器的完整全调用链副作用仍未证明。见 [字节核验](local/byte-verification.json)、[重放](local/replay-machine.json)、[接管](local/consumed-independent.json)、[中间入口](local/xrefs.json)。

## 6. 栈重新评估：不再单独阻断，可受控上机实测

已阅读 [栈研究报告](../stack_headroom/REPORT.md)，并独立校验其全部 227 项摘要，报告及证据已冻结到本任务 local。任务 6 创建参数为 ID 6、入口 `0x2005CC7C`、优先级 50、栈 16,384 B；`0x2005CEFC` 装载该大小。普通菜单和普通 H09 sender 路径均已闭合到任务 6。

普通任务使用 SPU。中断主体先用 SPI，但返回任务时会在 SPU 下方写 76 B 上下文；trap #7 也先用调用者 SPU 保存 76 B。因此上下文不能从任务预算删掉。原生记录给出动态基址 `B6 = *(u32 *)0x2042C030`，区间 `[B6,B6+0x4000)`，低端另留 4 B 哨兵；目前没有唯一静态绝对基址。

| Hook | v3.1 编译帧模型增量 B | Stage2l B | 扣所列原生帧、112 B 外层、76 B 上下文及哨兵后剩余 B |
|---|---:|---:|---:|
| H01 | 872 | 292 | 15096 |
| H02 | 180 | 0 | 15788 |
| H05 | 104 | 0 | 15436 |
| H06 | 820 | 68 | 15140 |
| H07 | 840 | 288 | 15112 |
| H08 | 812 | 312 | 15120 |
| H09 | 104 | 72 | 15708 |

本轮从冻结 ELF、`.su` 和汇编保存帧复算，得到同一组增量。它们是已建模代码范围的静态估算，不是设备实测。再保守叠加已经识别的 native draw 356 B 和嵌套 H05 104 B，H01 的该模型仍剩 14,636 B。

我的判断：仅因增量超过 Stage2l，不足以阻断刷机；目前没有接近 16 KiB 边界的证据。原生文件/UI/RPC 的深层开销、其它动态上下文和 SPI 峰值尚未闭合，宜作为修复 F08 后的受控验收项，无需先为此增加私有 4 KiB 栈。栈研究没有批准全局最坏安全，本文也没有作这种批准。

验收应在引擎汇编入口、C 序言前记录实际 r15、PSW.SM、task ID、同次开机的 base/end、build、hook/phase、样本数和最小入口 SP；记录留在当前有效引擎 BSS，不调用文件/UI/RPC，不改常驻层或 PSW。bootstrap/init/menu、Fn2、上下、OK/MENU、回放返回后重开分别留原始值。当前候选没有编入该记录器，须另交付并审查相应引擎容器。

入口可用量按 `min_entry_sp − (base+4) − 76` 计算。它只测入口，不能单独关闭 native API 内部峰值；须结合编译帧和必要的深层采样。H02/H05/H09 没有引擎入口，不能伪造它们的直接水位。证据：[栈报告纳入记录](local/stack-headroom-observed.json)、[复算](local/stack/comparison.json)。

## 7. 空文件与原厂一致性的证据范围

已核实：冷 FF-root、卡与 IROM 两槽均不存在文件时，首次 H01 只尝试三处 open，没有 read、分配、引擎、设置/RPC 或持久化写入；native frame、名称表和七项数不变。随后所有 hook 都不重试加载。该 H01 自有路径的已知帧约 224 B，另加未计的 native open 内部深度，不会走 872 B 的产品初始化链。

已核实：启动、建堆、段装载、link、SD 初始化、关机、卷操作及更新 UI 的旧系统 hook 均已移除。设置/更新已定位直接路径保持官方；共享 H05/H09 即使被调用，在无引擎资格时也不做自检或收尾。这支持题设的“先到设置/更新、再首次 ADJ”恢复顺序。

未知：真实菜单、拍摄、回放、休眠/唤醒、USB、关机、换单元和更新全过程的设备行为。不能从默认 frame 相同推导耗时、调度、全部间接调用或整机功能完全相同。上述各功能仍须空文件阶段逐项验收。

## 8. 与 Stage2l 相比的新增风险

1. H01 现在包含动态装载、校验、重定位及引擎执行；其 native 文件/API 耗时和深栈仍需实测。
2. 自有 UI 与主会话占用堆，并依赖原生消费者和槽位生命周期。一次加载限制消除了正常重开累计占堆，但 F08 仍在错误恢复路径上。
3. 产品每次开机约保留 91 KiB，请求安装缓冲时约 222 KiB；真实原生剩余堆未知，分配失败会影响产品可用性。
4. A4 增加同步设置/RPC 和 GXTS 写入；产品首次菜单还会安装 IROM。只删卡文件不再保证下次不加载。
5. H07 的通用合同和 H09 的效果规则与 Stage2l 存在已核实差异。七个位置相同不能继承全部行为验收。

## 9. 可逆性分析

栈溢出通常先损坏易失 RAM，断电可清除这类状态；它本身不等于永久硬件损坏。但控制流或其它任务状态损坏后，不能保证仍可进入更新菜单，也不能保证在途文件写入未受影响。因此“栈风险可受控上机关闭”成立于分阶段恢复条件，不是“即使溢出也一定能救”。

| 阶段 | 失败时的恢复条件与方法 |
|---|---|
| 卡、IROM 都无引擎。 | 不经过升级写入时，关机/必要时断电，移除卡上扩展文件后冷启动；从设置进入官方更新恢复。若仍进不了设置，现有证据没有另一条已验证自主救援链。 |
| 只读探针、IROM 始终为空。 | 去掉卡上探针后冷启动，H01 回短路径；不打开 ADJ，先去设置刷回已验证官方包。这是接受剩余栈风险的首选阶段。 |
| 产品已安装 IROM。 | 移除卡不足以禁用。必须有能到达并清空/禁用 IROM 的已验证原生路径，或能直接进入设置刷回官方。未验证该恢复路径前，不把产品写 IROM 作为首次试验。 |
| 已发生 RAM 损坏且冷启动仍不能到更新菜单。 | 过去成功的菜单回退及正确的恢复包不能保证此状态可救；独立 boot/service 恢复仍未知。停止继续触发扩展。 |

设置与更新不经过扩展业务、探针阶段 IROM 为空且没有持久化写入的题设，显著提高恢复可行性。它足以支持栈这一项留到受控实测；不足以合理化把已知错误撤回逻辑留在当前摘要中。

修复并重新放行后，验收顺序应是：空文件冷启动；先看版本并进入官方更新界面后取消；再测原厂七项 ADJ 的首末行、确认、取消、Fn2、重开；再测拍摄/回放、休眠、USB、关机及关机换单元；随后才用无 IROM 写入的探针记录 SP。任何一步失败，都停止向下一阶段推进，按上表回退。产品/A4/持久化验收最后做，且须先证明 IROM 恢复路径。此顺序不授权本轮上卡或刷机。

## 10. 映像、容器与交付核验

| 对象 | 本轮核对结果 |
|---|---|
| 候选 `ilaunch3` | SHA-256 `495841f145daea056c435f7d40c00586984b55675ea56b05674f2bbb2775b295`，3,993,340 B。 |
| 官方 `ilaunch3` | SHA-256 `da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7`。 |
| resident ELF | SHA-256 `3e178354b3086fa8e9ac2af09fc5434ff013c5e760a7ecbf3689b689c0714160`；源码/工具摘要计算出的 build/ABI 与 ELF 内 trust 一致。 |
| Stage2l 对照映像 | SHA-256 `efe6587190e845b1c28364c02a6b8bde14e046e7c7411393a4c9892124b6bfd7`。 |

全文件比较有 7,488 个不同字节，全部落在窗口 `[0x2005276C,0x20054800)`、七个 hook 和头部校验字段中；没有白名单外差异。七个 BRA24 共覆盖 36 B，全部解码到对应最终桩，4 B 对齐。7,772 B payload 和 12 B pins 与 ELF 匹配，root 可变区为 244 B FF。

按整个 `image[512:]`、从该起点的 i 计算 `sum(b * (i % 6 + 2)) mod 2^32`，候选存值与重算均为 `0x6A80C56D`；官方为 `0x6ACDB212`，Stage2l 为 `0x6A78DA1E`。恢复包 29 文件逐字节等于官方，候选其余 28 文件也等于官方。五个 GXRCE 的头/负载 CRC、身份、重定位及实际引擎字节检查通过；base 的 ELF 对照修正见 F11。`AUDIT_PASS_UNREVIEWED` 仍不等于刷机许可。

冻结并最终核对 999 份保护输入。`.gitignore` 第一行为 `/local/`，已用 `git check-ignore -v` 确认。所有固件副本、派生字节、反汇编、编译出的主机程序、原始失败均只在 local。摘要见 [SHA256SUMS](SHA256SUMS)，范围复核见 [delivery-validation.json](local/delivery-validation.json)。

主要复跑入口均只写本审查目录，不调用固件构建：

```sh
/usr/bin/python3 -I -B research/review_flash_v31/local/image_checks.py
/usr/bin/python3 -I -B research/review_flash_v31/local/container_checks.py
/usr/bin/python3 -I -B research/review_flash_v31/local/machine_checks.py
/usr/bin/python3 -I -B research/review_flash_v31/local/consumed_checks.py
/usr/bin/python3 -I -B research/review_flash_v31/local/run_host.py
/usr/bin/python3 -I -B research/review_flash_v31/local/product_checks.py
/usr/bin/python3 -I -B research/review_flash_v31/local/stack_checks.py
/usr/bin/python3 -I -B research/review_flash_v31/local/byte_checks.py
```

独立新增反例使用真实 resident/service C；原生分配、文件和引擎执行有明确 double 边界。重放沿用审过的 v2 指令子集，IRQ/配对和栈计算器也审读后复跑；产品 54 组复用了开发方行为夹具，并补了三组独立流程，未把它们称作全新独立实现。审查中不成立的对齐异常假设和“一份产品 ELF 可直接匹配两容器”的初始失败均保留在 local/failures，未把错误假设用作刷机阻断。
