不可以刷

# v3 机身映像刷机前独立对抗复审

本结论只针对候选 `ilaunch3`，SHA-256 为 `104637a935c66e4087d8ab2884a17f308840e11bf27a91652596df1a8871dbe9`。F01 的 IRQ 极性、F03 的 post 返回地址问题已消除，上一轮 F02 的原始两层视图用例也已修复。但 H07 的关闭分派和列表行号仍有确定的行为错误；堆失效后的释放与 UI 撤回也有独立主机反例。官方更新路径隔离和原生任务栈余量尚未得到足够证明，不能批准这个摘要刷入。

没有发现新的、已证明必然发生的开机 P0，也没有观察实机故障。下面区分最终字节、源代码行为夹具与尚未证明可达的失效时序。空卡、空 IROM 不会触发需要有效引擎和自有 UI 的问题；这不构成对带引擎运行的放行。

审查日期为 2026-10-24。目标是用户的 GXR 机身 1.51、官方 1.51 的 A12 50mm 与 MOUNT A12。用户给定的 Stage2l 日常使用及官方菜单回退实机记录作为基线，本轮没有重做或扩大这些实机结论。

## 1. 按严重度排列的问题

### F04 · P1 · H07 吞掉 PASS，并遗漏原生关闭动作

已核实，最终 resident 的 `0x20052964..0x2005299C` 把 H07 事件交给引擎后，对 PASS 和 CONSUMED 都选择 `rv_skip_07`，把保存的 r0 改成零。`0x20052B00..0x20052B04` 直接恢复 LR 并返回。它不会执行官方 `0x202871DC..0x202871F8` 的关闭分支及 overlay 清除。

这条路径确实包含关闭请求。官方 `0x202B8D98`、`0x202BD88C`、`0x202BEA50`、`0x202C2D80` 都以 native r4=0 调用 `0x202871D8`；`0x202C2D70` 则传 1。v3 把这个参数放在引擎请求 `args[9]`，但没有在 resident 中兑现关闭语义。

两种现有引擎都暴露问题。

- LIFE 的最终 `pv_event` 正常出口返回 PASS。其注释称物理按键保持原生行为，实际 H07 会消费这个 PASS。
- 产品最终 `ig_event` 对 `args[8]==7` 直接返回 CONSUMED，没有按 `args[9]` 关闭视图或清 overlay。对应容器相对地址为 `0x5898..0x58B8`。

独立夹具以真实 `rv_hook_observe`、有效自有 UI 和 `keep_open=0` 调用 H07，让引擎 double 返回 PASS。结果是选择直接返回桩，`0x2037F3BC` 仍为 32，原生 view 与 `ui_restore` 仍保持发布。这里没有用 double 代替 H07 的 C 分派；实际 M32R 桩的保存、直接返回也另有机器码检查。

与 Stage2l 的差别已核实。Stage2l 的 `rfw_apply_action(0)` 会清 overlay、调用 native layer hide，并关闭自有 cache。v3 没有等价收尾。推断，用户的确认、退出或模式切换会遗漏原来负责的关闭操作。上层是否在某些路径随后整体重建页面，尚未逐条证明，不能把“菜单一定无法退出”写成实机事实。

修复建议：为 H07 明确区分保持与关闭。自有列表接管时，需要显式撤回自己的 UI、执行所需的原生 hide/overlay 收尾，并返回正确的 native 结果。不能只把判断改为 PASS 就重放，因为扩展行号也不能直接进入原厂七项 setter。用 r4=0、1 分别驱动真实 H07 路由，检查关闭后的原生记录、overlay 和后续再次打开。

证据：[最终关闭指令与引擎出口](local/EVIDENCE.md#f04-close)、[原生 caller 上下文](local/h07-and-row-context.txt)、[夹具原始输出](local/host/behaviour.log)。源码位置为 [hooks.c:43](../../firmware/resident_v3/resident/hooks.c:43) 与 [adapter.c:215](../../firmware/resident_v3/containers/product/adapter.c:215)。

### F05 · P1 · 会话验证失败后，清理仍可能释放同地址的新对象

已核实，`rv_check` 能因 session/lease/context 不符拒绝旧引擎。但是 `rv_retire` 在 `rv_session` 已返回空的情况下，仍会独立用旧 root 的 block、反码及分配头决定是否 free。最终路径为 `0x20052D90` 的 retire、`0x20052E30..0x20052E5C` 的主块释放判断，以及 `0x20053D64` 的 `rv_free_checked`。准确指令见附件，不能把分配头“看起来仍被占用”当成当前对象仍归 resident 所有。

独立反例保留原 root，将主块地址模拟为同尺寸 native 新分配，头部仍合法而内容已不再是 session。真实 `rv_check` 报 SESSION 失效；真实 `rv_engine → rv_retire` 没有调用旧引擎，却 free 了这个替代对象。复现地址为 `0x2070480C`。

官方分配器 `0x2005BF5C` 与 free `0x2005C038` 的头部只有链指针、占用标志和长度，没有 resident lease 或分配代次。头部可在地址复用后再次相同。额外核对发现，官方长度包含对齐后的请求量及 12 B 头部，开发夹具写的是请求量；这个差别不消除“同地址、同头部、不同 owner”的反例，但说明夹具并未执行官方分配器。

已核实的另一个入口差异是 H09：单元身份自检失败时，它会在 sender 路径调用 retire 并释放主块。独立夹具观察到 free 计数增加，而没有旧引擎调用。Stage2l 的 H09 只检查状态及修改 packet，没有这个 close/free 收尾。v3 的 native allocator/free 本体也没有可见的 IRQ 或任务锁保护，不能据此证明 sender 与原生 UI 分配之间安全。

未知：这台机身是否在 root 存活期间实际重建同边界主堆或复用这个地址，以及对应任务交错。本轮没有把模型中的堆事件当成设备观测。问题是当前“入口自检失败即可安全收尾”的保证不成立。

修复建议：失去会话归属证明时，不向 native free 传旧地址。将不确定分配隔离到受控重启，或补上能识别实际分配代次的归属证据。H09 只发布失效标志，关闭 fd、释放与重载集中到已证明可阻塞、可分配的受控入口。

证据：[最终 retire/session/free](local/EVIDENCE.md#f05-retire)、[官方分配器](local/heap-native.txt)、[同头部复用与 H09 反例](local/host/behaviour.log)。源码位置为 [resident.c:39](../../firmware/resident_v3/resident/resident.c:39) 与 [shared.c:83](../../firmware/resident_v3/resident/shared.c:83)。

### F06 · P1 · UI 快照失效后，撤回漏掉原生引用并擦除恢复记录

上一轮 F02 的“主块由 loader 释放，底层 view 仍指向主块”已修复。v3 将原生可见 state、描述符、labels、refs、glyphs、零 details 放到独立的 1,968 B 分配中；正常主块释放不会释放这个快照。本轮重跑单层、两层、当前数组不匹配及 root 全 FF 的旧场景均通过。

残留问题发生在快照本身失效时。最终 `rv_ui_abort` 在 `0x20053D4C..0x20053D58` 只对 `ui_at` 仍认可的对象替换 view 指针。`ui_at` 先要求当前堆范围和分配头有效，再读归属标记。失败后，abort 仍在 `0x20053CF0..0x20053CF4` 清空整份 `ui_restore`。

两条独立主机反例已经复现。

1. 模拟 native 堆回收快照后，名称表恢复成官方值，但底层 view 仍指向已失效的 `0x2070807C`，恢复记录已经清空。生产代码自身不会主动 free 快照；这是快照过期边界的模型输入。
2. 将当前堆范围移到不包含旧块的位置，真实入口自检拒绝旧引擎并 retire。旧 view 仍指向当前堆外的快照，恢复记录同样清空。此例无需先破坏快照内容。

`rv_check` 也没有独立验证 UI 快照的当前归属，验证主块成功不等于原生侧保留的所有对象仍有效。保留快照而不主动 free，不能阻止原生堆重建或其他 owner 复用其内存。

推断，后续原生绘制或此前已取走的指针可能访问已失效内存。未知，这台相机在休眠、USB、回放或换单元时是否形成上述堆/view 交错。因此这是有条件的生命周期阻断，不能宣称已经在实机复现 UAF。

修复建议：保留可信的记录位置和旧 state 地址，撤回当前已知引用时不依赖解引用失效快照。撤回应返回结果；没有确认成功就不能丢掉恢复记录。对已被原生消费者取走的指针，还需要快照失效前的生命周期约束。仅在下次入口查询分配头，补不上已经发生的原生消费。首轮更小的映像可以暂不发布堆上自有 UI。

证据：[最终 abort 与 ui_at](local/EVIDENCE.md#f06-ui-lifetime)、[两层 UI 与失效反例](local/host/behaviour.log)。源码位置为 [shared.c:61](../../firmware/resident_v3/resident/shared.c:61) 与 [services.c:123](../../firmware/resident_v3/engine_services/services.c:123)。

### F07 · P1 · native 行号与服务行号错一位

已核实，原生 ADJ 使用 1 基行号。官方初始化 `0x202870FC..0x20287164` 把 1..7 写入 state；原关闭/确认函数在 `0x2028725C..0x20287274` 将零及超界值归回 1。已验证 Stage2l 也直接使用 1..16 的配方序号。

v3 的服务合同却按 0 基处理：`ui_list` 允许 `0 <= cursor < rows`，并把 cursor 原样写入 native state 的 `+9/+10`。H01/H02 同样把 `s->cursor` 原样交回 native。产品 `list_bind` 把引擎的 1 基 cursor 减一，探针则固定传零。

反向路径也没有转换。最终 resident `0x200529C8..0x200529D4` 把 `0x2022F726` 的 native 行号直接放到引擎 `args[8]`。产品容器相对 `0x7940..0x7948` 又加一，再检查是否超过 16；这一关键指令片段在 base、huzi 两份最终容器一致。

真实 H08 C 路由的独立结果为 native 行 1 传入 1，产品将其解释为槽 2；native 行 16 传入 16，产品得到 17 并拒绝。没有在相机上拍照验证错误配方，但错位的字节和参数链已确认。它影响的是实际设置写入的配方身份，不能当成显示偏差。

修复建议：在 native 边界统一转换。若服务继续使用 0 基，发布 native cursor 时加一，H08 先验证 native 行号在 1..rows，再减一传入引擎。H01/H02、探针、产品和故障撤回都按同一合同处理；原厂恢复值必须在 1..7 内。至少覆盖首行、末行、首次打开、重开与失败回退。

证据：[最终行号指令](local/EVIDENCE.md#f07-row)、[原生 state 与渲染](local/h07-and-row-context.txt)、[H08 夹具](local/host/behaviour.log)。源码位置为 [hooks.c:45](../../firmware/resident_v3/resident/hooks.c:45)、[services.c:148](../../firmware/resident_v3/engine_services/services.c:148) 与 [adapter.c:206](../../firmware/resident_v3/containers/product/adapter.c:206)。

## 2. 上一轮 F01、F02、F03 的最终状态

| 项目 | 本轮判断 | 证据与边界 |
|---|---|---|
| F01，IRQ 极性。 | 已消除。 | resident 最终 save 在 `0x2005442C`，restore 在 `0x20054438`。实际字节清 IE 并保留原 PSW。服务库和五容器具有同样的 helper。 |
| F02，原两层 view 指向已 free 主块。 | 原反例已消除。 | 独立快照切断主块释放与原生引用。快照自身失效的边界仍有 F06。 |
| F03，post 返回地址只存 root。 | 已消除。 | 最终 ELF 没有 post、notify、epochs 符号，也没有 H10 及系统桩。H10–H37 的 28 个点逐个核对为官方字节。 |

对七份最终 helper 的 65,536 种原始 16 位 PSW 分别检查，共 458,752 组，保存后 IE 均为零、恢复后等于原值；合法 PSW 的嵌套保存恢复也通过。它只验证指令语义，不模拟真正中断、PSW 栈切换或硬件时序。

全部 IRQ 使用位置已逐项检查编译后分支。resident 有 reset、engine 调用资格、READY 发布、record、UI abort 五处 save。服务库有 record、UI abort、grain commit、settings 写入、epoch 快照、UI list、UI view、event 快照八处 save。13 个 save 对应 16 个静态 restore 调用点，包含共享恢复出口和提前失败分支；未发现漏 restore 或把修改后的 PSW 当原值恢复的路径。文件、分配和引擎调用不在这些 IRQ 临界区内，这也不能替代 F05 所需的归属与并发约束。

root 可变区的最终映像字节为 244 B FF，末尾 12 B 为 pins。`rv_reset` 在最终 `0x20052B48` 先关中断，清可变区，填版本、12 个 epoch、token 和 flags，在 `0x20052B8C` 最后发布 magic，随后恢复 PSW。非 H01 入口遇无效 root 直接透传；H01 才做懒初始化。冷 FF-root 主机用例通过。

证据：[IRQ 字节与所有调用点](local/EVIDENCE.md#irq)、[独立 IRQ 结果](local/irq-independent.json)、[独立重放结果](local/replay-independent.json)。

## 3. 七个执行 hook 的逐点审查

七处默认分支的原字节均从实际官方映像取出，并与最终 ELF 中重放字节核对。它们没有 PC 相对指令。桩保留 r0..r13、LR、PSW，外层 LR 连同公共保存共增加 68 B；默认返回再执行被覆盖内容。解释器对七点各 128 个向量检查寄存器、条件位、PSW、SP 和有效栈内容，896 组通过。六种接管分支另检查 768 组，保存与返回结构通过；这不认可 F04、F07 的业务语义。

| 点 | 官方 VA / 长度 | 默认续接 | 与 Stage2l 对照及判断 |
|---|---|---|---|
| H01 | `0x2028709C`，8 B。 | `0x202870A4`。 | 两条绝对地址构造。Stage2l 在原位置替换 getter 目标并保留 native 调用；v3 先观察，默认重放，接管时直接去 `0x202870A8`。默认相符，接管 cursor 有 F07。 |
| H02 | `0x202870A8`，4 B。 | `0x202870AC`。 | 寄存器复制及立即数。Stage2l 为复制加短跳转；v3 自有页去同一 `0x20287118`。默认相符，非 BRA24 的 Stage2l 字不能按长跳转解码。 |
| H05 | `0x201FEBE4`，8 B。 | `0x201FEBEC`。 | 两条绝对地址构造。Stage2l 换成静态零 details；v3 只在 owned 页选快照 details，其余重放官方地址。 |
| H06 | `0x202BE24C`，4 B。 | `0x202BE250`。 | 上半地址构造；低半保留在 native 续接。原活动 8 比较仍在 hook 前。Stage2l 接管返回 2，v3 返回 0 是不重建 ADJ 的现有策略，不能仅据此报 ABI 错误。 |
| H07 | `0x202871D8`，4 B。 | `0x202871DC`。 | 原生 LR 入栈。默认相符，接管直接返回且栈平衡；关闭语义有 F04。 |
| H08 | `0x202BB968`，4 B。 | `0x202BB96C`。 | r11 的上半地址构造；低半留在原流程。原活动 8 比较仍在前面。自有页去 `0x202BCF58`，参数行号有 F07。 |
| H09 | `0x2017098C`，4 B。 | `0x20170990`。 | 原生 LR 入栈。默认保存重放相符，无 grain 时不改 packet；失效时新增 retire/free 路径，见 F05。 |

没有保存 ACC、BPC、SPI/SPU 等额外特殊寄存器。公共保存解释器没有模拟它们，也没有执行 native 文件函数或 M32R 引擎。不得把寄存器子集通过扩大为全 CPU 状态证明。

中间入口检查覆盖完整官方文件的 BE32 指针、16 个初始化映射段的直接分支编码、反汇编直接边及地址构造。没有发现进入七处覆盖区内部的引用。重点的两个 8 B 覆盖区内部字地址为 `0x202870A0`、`0x201FEBE8`；18 处邻近的已识别相对表也没有命中。共识别 256 处相对表，自动上界保留 candidate 标记，不把这次负扫描称作完整 CFG 证明。任意 RAM 计算目标与未识别表仍未知。

证据：[逐点字节与桩](local/EVIDENCE.md#hooks)、[中间引用扫描](local/xrefs.json)、[相对表](local/EVIDENCE.md#tables)、[表扫描边界](local/relative-tables-summary.json)。

## 4. 设置、回放、USB 与官方更新界面的隔离

已核实，上一版直接介入启动、建堆、段装载、link、SD、关机、卷操作和更新清理的所有补丁都已移除。官方 `0x2036D4E8 → 0x2036CAD8 → 0x202E4F44` 确认 UI 所使用的 `0x201C06F4`、`0x201C092C` 现在保持官方字节。这消除了上一版已定位的更新 UI hook 介入点。

剩余七点的证据强度不同。

- H01/H02 的已定位 caller 受活动号分派控制。当前官方 `0x20377434` 相对表的活动 8 项指向 `0x202BA764`，在 `0x202BA76C` 调用 H01 所在函数 `0x20287080`。见 [实际表项](local/h01-native-activity-table.json)。
- H06、H08 之前分别有 `0x202BE248`、`0x202BB964` 的活动 8 判断。H07 已定位五个调用点，分布在四组关闭/保持上下文中；其中有显式活动 8 比较和同类表分派。
- H05 只有 type 5 的原生门限，它是通用绘制代码。v3 的 owned 判断另外要求 READY、已发布名称表、活动 8、状态 56、part 2、tag 33、匹配的 state。非 owned 页不会调用 H05 的引擎业务或替换 details。
- H09 是共享 sender 入口，四个已定位 caller 为 `0x202D6B6A`、`0x202D6CBE`、`0x202D6DAE`、`0x202D6E6E`。它没有 ADJ 页面门限。即使不改 packet，也可能先自检和 retire。

未知，设置、回放、USB、更新全过程是否完全不经过这些入口。上述 caller 和门限没有覆盖所有间接调用、活动转换和异步任务。也不能证明所有非 owned 进入都是纯透传，因为进入 owned 判断前可以执行自检、事件记录及失效 retire，F05 的 H09 反例已经显示 free 副作用。

因此用户要求的“全部避开，或即使进入也纯透传”尚未满足。这是放行证据缺口，不是声称已经找到更新界面必经 H07 的路径。需要针对保留下来的点证明调用上下文，或将有副作用的工作集中在更窄的安全入口；不能只用“与 Stage2l 同位置”替代证明。

## 5. loader、自检失败与原生 RAM

已核实，loader 先读 256 B 头，检查声明文件长、镜像/BSS 上限和身份，再按文件实际声明长度加 BSS、state 等开销申请私有块。每次 read 不超过剩余量，完整读取还做 1 B EOF 检查，随后校验、重定位、清尾部、同步缓存、bootstrap/init，最后在 IRQ 临界区发布 READY。没有发现将 image 直接铺到未分配的固定原厂 RAM 的路径。

三源读取每次只持有一个 fd。独立新增六例覆盖截断、尾部多字节、超长头、分配失败、部分读取后出错和 SD ID 改变。全部拒绝、关闭自己的 fd、没有引擎调用，已登记的主块分配和释放数相等。观察到 fd 峰值为 1。该结果来自 native 文件/分配 double，不是相机存储栈验收。

当前元数据自检能拒绝 magic/version、nonce/token、堆边界、主块头部、抽样代码和单元字段的逐项破坏；旧引擎调用被拦住。它不能证明分配代次，也不能覆盖 F05/F06。代码哨兵仅检查 16 个分散字，共 64 B，未采样位置破坏的负对照仍能通过。

对头部读取的静态检查确认，最终 `rv_allocation` 先校验 `p-12` 的头部范围及主块范围，再读头部，不先解引用明显的越界 p。边界依据是 native 当前 heap begin/end；实现没有独立钉住物理 RAM 可读范围。如果两个边界本身都损坏，不能给出无条件的非法地址读取排除证明。正常官方初值为堆 `[0x20704800,0x20744800)`。

原生写入可分为 root、分配所得块、UI 名称表/计数/view、受限 S 设置和 grain packet。空文件条件下不启动引擎、不写 S、不发 RPC 或存储写入；带引擎时 UI、设置和 packet 都有实际写入。单靠容器校验正确不能保证这些生命周期与原厂任务一致。

证据：[冻结 loader 源](local/frozen/firmware/resident_v3/resident/loader.c)、[最终 resident](local/disasm/resident.txt)、[loader 六例原始输出](local/host/behaviour.log)。

## 6. 卡与 IROM 均无 GXRCE 时

已核实的范围是冷 FF-root 和主机 C 分派：H01 懒初始化，依次尝试卡、IROM 两个槽，三处文件都不存在时，没有读取、分配或引擎调用，寄存器帧不改，官方名称表与七项计数保持。v3 没有缺文件负缓存，每次再次走 H01 都会重试；不能沿用上一版“不重复装载尝试”的描述。

| 场景 | 当前能确认的内容 | 未核实内容 |
|---|---|---|
| 菜单、details、Fn2、确认。 | 没有会话时不选扩展 skip，默认保存与重放通过。 | native 文件 API 耗时、任务栈及真实按键路径。 |
| 拍摄。 | grain 为零，不改拍摄 packet，不调用引擎。 | 实际拍摄任务、特殊寄存器与时序。 |
| 回放。 | 专用回放及中央 mode hook 均为官方字节。 | 完整回放过程是否碰到共享绘制/sender，以及真实行为。 |
| 休眠与唤醒。 | 三个 sleep 点及系统通知点均未改。 | RAM 保留、段重载与 heap 生命周期。 |
| USB。 | 没有 USB 系统 hook 或空文件引擎服务。 | 完整连接、卷访问与断开。 |
| 关机。 | H25 已恢复官方字节。 | 实际关机收尾及再次冷启动。 |
| 换单元。 | H19/H20/H21 及 post 均已移除。 | A12 50mm、MOUNT A12 的真实重连与内存变化。 |

这是主机默认路径检查，不是七种整机行为均已与原厂等价。没有相机操作权限，本轮保留这些未知。

## 7. 栈用量

公共汇编新增 68 B，observer 的最终固定帧为 120 B。下表由冻结的 `.su`、最终调用边及 native 桥保存计算，表示已建模 resident/桥范围的最大嵌套，不包含 native 函数、动态引擎、中断和原任务既有栈。

| Hook | 已建模部分的最大增量 | 说明 |
|---|---:|---|
| H01 | 956 B。 | 读头路径包括 observer、load、probe、read_one、unchanged、unit snapshot。 |
| H02 / H05 | 各 280 B。 | 包含最深的自检失效撤回路径。 |
| H06 / H07 / H08 | 各 320 B。 | 包含 engine 返回后发现失效的 retire 路径；引擎执行自身另计。 |
| H09 | 280 B。 | 包含失效 retire，超出 Stage2l 单纯 sender 检查的工作范围。 |

另在最终 huzi 产品机器码确认 H08 的实际嵌套链：公共保存 68、observer 120、engine 40、invoke 4、ig_apply 104、bind_gxts 1,280、gxts_load 716，合计至少 2,332 B。`ig_apply → bind_gxts` 的调用在容器相对 `0x79E0`，`bind_gxts → gxts_load` 在 `0x77C4`。还未计入其内部文件读取、服务、native 调用与中断；2,332 B 是下界，绝不是总上限。

没有查得足够证据将各 hook 绑定到已知剩余栈空间，不能判断是否已越过这台机身的任务栈。开发报告的 resident/service 单函数列表漏不掉这个更深的产品调用链，安全评估也不能只看最大的单个帧。

修复/验收要求：减少这些大栈工作区，取得各实际任务的栈分配、调用基线和中断余量，再检查完整入口。不得把当前数字写成“栈安全”。

证据：[栈计算器输出](local/stack-independent.json)、[产品帧与调用指令](local/EVIDENCE.md#stack)、[完整产品反汇编](local/disasm/product.txt)。

## 8. BRA24、容器与输入身份

| 输入 | 核实的 SHA-256 |
|---|---|
| v3 候选 `ilaunch3`。 | `104637a935c66e4087d8ab2884a17f308840e11bf27a91652596df1a8871dbe9` |
| 官方 1.51 `ilaunch3`。 | `da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7` |
| 最终 resident ELF。 | `0845f7c4b50d04fe0e5c9393ce32bd4b6c37b044afba18a0225909c98e8c405c` |
| Stage2l 对照映像。 | `efe6587190e845b1c28364c02a6b8bde14e046e7c7411393a4c9892124b6bfd7` |

候选长度为 3,993,340 B。七个实际 BRA24 的解码目标均落在对应最终 ELF 桩，4 B 对齐；两处 8 B 点的剩余覆盖字也与 manifest 一致。7,532 B payload 与 12 B pins 在候选中逐字节匹配最终 ELF，root 可变区 244 B 保持 FF。H03/H04 为官方数据，H10–H37 全部保持官方字节。没有跳到 ELF 头、root 或空洞的补丁目标。

独立按完整 `image[512:]` 重算加权校验，包含段间隙与尾部，权重以 payload 起点的 i 为准：

```text
sum(payload[i] * (i % 6 + 2)) mod 2^32
```

| 映像 | 头部存值与独立重算值 |
|---|---|
| 官方 1.51。 | 均为 `0x6ACDB212`。 |
| 已验证 Stage2l。 | 均为 `0x6A78DA1E`。 |
| v3 候选。 | 均为 `0x6A834F7B`。 |

BRA24 与容器算法符合已验证 Stage2l 的编码及 phase 0 规则。用户已给定的差异白名单和 29 文件恢复包逐字节一致检查，作为已独立核对的输入事实使用；本轮没有将其重新包装为新的设备恢复证明。

## 9. 变砖风险评估

相较上一版，早期启动、建堆、段装载、link、SD、关机、卷及更新清理入口恢复官方，且错误 IRQ helper 与 post LR 槽消失，启动与恢复链的直接风险明显下降。剩余执行点的位置与 Stage2l 相同，不能据此继承 Stage2l 的运行安全。

相较已日常使用的 Stage2l，新增风险主要在这些地方。

1. H01 从固定驻留逻辑变为动态分配、文件验证、重定位和引擎执行，加入一整套 RAM 生命周期。
2. 每个保留活动入口都可以做自检；H09 也能触发 native close/free。Stage2l 的 sender 不承担这类收尾。
3. 多个独立 UI 快照在失效后保留，每次重新发布的新会话可再占 1,968 B。主块遗失也可能泄漏，最终会影响与原生代码共用的 256 KiB 堆；没有无限重载安全保证。
4. H07 的关闭与 native 行号合同发生确定偏差，影响菜单撤回、按键和实际配方选择。
5. 产品存在至少 2,332 B 的新增嵌套栈，原生余量未知。

F04/F07 首先构成菜单与配方故障。F05/F06 在对应内存失效时序成立时，可进一步造成原生对象误释放或悬空引用。是否会阻断本机菜单回退、是否有不依赖 MAIN 的救援入口，本轮均没有证明。

正确的恢复包以及过去能从菜单刷回官方，只能说明正常菜单状态下的已验证回退链。它不能保证这份 MAIN 故障后仍能进入该菜单。因此当前结论不是“校验错所以不能刷”，而是执行及失效收尾仍未达到放行条件。

## 10. 刷机后第一步应验证的事项

以下仅适用于修复并重新审查通过的新摘要，是探针前的最小人工检查，不授权把当前候选上卡。本轮没有执行这些步骤。

1. 先确认卡和 IROM 两个槽都没有可加载的 GXRCE。冷启动到正常拍摄画面，先不要打开 ADJ 或运行探针。
2. 先进入设置菜单，查看固件版本、进入官方固件更新界面并取消返回。确认恢复入口仍可达，不开始新的升级。
3. 再首次打开 Image ADJ，确认官方七项、首末项选择、确认/取消、Fn2 和再次打开均正常。此步才有意触发 H01 的空文件路径。
4. 拍摄一张并回放，检查菜单关闭、拍摄返回和文件可读。随后覆盖一次休眠/唤醒、USB 连接/断开、正常关机及再次冷启动。
5. 关机后换 MOUNT A12，重复启动、更新界面取消、ADJ、拍摄/回放最小路径。A12 50mm 的结果不能代替另一单元。

出现菜单、更新入口或关机异常就停止进入探针阶段。只有以上空文件路径通过后，才讨论加载只读容器；只读容器同样会执行机器码、占堆和发布 UI，当前 F04/F07 修复前也不能拿它作安全试探。

## 11. 证据、复跑与只读边界

本目录交付 [review.py](review.py)、[native_checks.py](native_checks.py)、[machine_checks.py](machine_checks.py)、[run_host.py](run_host.py)、[stack_checks.py](stack_checks.py)、[make_evidence.py](make_evidence.py)、[checksums.py](checksums.py) 与 [SHA256SUMS](SHA256SUMS)。所有冻结固件、容器、反汇编、主机程序、日志及机器记录都在 `local/`；正文以地址和交叉引用指向它们。

复跑从仓库根执行，输出仅刷新本目录的 `local/`。`collect` 对原始输入摘要和固定候选摘要有断言，`verify` 会核对审查期间输入是否变化。host 程序使用 ASan/UBSan，native 文件、分配、UI 动作和引擎执行仍是 double。最终指令检查使用的是实际 ELF/容器字节，不用 C IRQ double 代替。

```sh
/usr/bin/python3 -I -B research/review_flash_v3/review.py collect
/usr/bin/python3 -I -B research/review_flash_v3/review.py xrefs
/usr/bin/python3 -I -B research/review_flash_v3/native_checks.py
/usr/bin/python3 -I -B research/review_flash_v3/machine_checks.py
/usr/bin/python3 -I -B research/review_flash_v3/run_host.py
/usr/bin/python3 -I -B research/review_flash_v3/stack_checks.py
/usr/bin/python3 -I -B research/review_flash_v3/make_evidence.py
/usr/bin/python3 -I -B research/review_flash_v3/review.py verify
/usr/bin/python3 -I -B research/review_flash_v3/checksums.py
/usr/bin/python3 -I -B research/review_flash_v3/checksums.py --verify
```

卷预检确认挂载点、APFS、可写及 UUID `14BE04EB-AF49-497E-B36A-B078B2F7C5E8`；[原始预检](local/volume-preflight.plist) 已保留。`.gitignore` 第一行为 `/local/`，并用 `git check-ignore -v` 确认。最终输入复核见 [inputs-verification.json](local/inputs-verification.json)，写入范围复核见 [delivery-validation.json](local/delivery-validation.json)。

本轮没有启动子代理，没有 sleep 或轮询，没有安装包，没有构建或修改固件源码，没有操作相机、存储卡或刷机，没有 commit/push。共享检出的其他目录及官方固件保持只读。只生成了本审查目录的报告、核查脚本与本地证据。
