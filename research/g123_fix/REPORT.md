可以交复审

gen 123 DAT 为 `firmware/package_v36_g123/SD_ROOT/GXRCE.DAT`，62,676 B，SHA256 `4ee9e6fefcd33619bcd763eacba9c56be4d3fb265b9e2ca0d73d49d59b8c1e64`。本结论只针对交复审的测试卡候选；未操作相机、存储卡或网络。

1. P1-01 已撤销哨兵。`validate_live()`、`eng_require_recheck()`、`rebind_impl()` 恢复 gen 121 的源码行为。每次已应用配方的重开完整核对九行、T 和原生设置，失配沿既有补偿路径恢复。`sentinel_offset()`、`read_live()`、`full_check` 和延后菜单入口已删除。
2. P1-02 采用裁决允许的原生列表回退。H01 不能核对且未锁定时，只标记下次完整核对并释放自有视图，不发布八行配方。随后方向键、DISP、确认走原生列表；下次成功 H01 才恢复已核对的八行。
3. 锁定显示补充项已修复。W 已开始且全部补偿失败时，若视图仍归引擎所有，立即复用 list_bind(2) 更新为既有 ERR 单行，再用 list_bind(3) 重绘；面板同时停止输入。原因码沿用 record_failure，光标、小圆点和原生缓存均回到 1。若归属已丢失，不写当前原生界面，下次 H01 仍显示 ERR。锁定条件未改。

短列表探针实际发布了两行 Busy / Retry，方向键能到 H08，但首开光标和小圆点都为 1。现有列表服务只接受 `cursor < rows`，并把光标和标记设为同一行；固定 resident 的 H01/H02 只返回同一个一基行号。原生构造器又在 `0x20287158` 和 `0x20287164` 写回同一个值。现有契约无法独立隐藏标记，本轮没有引入越界光标状态，因此选择原生七行回退。探针 DAT、ELF、原始写入和绘制记录均保存在 [local/probe](local/probe/)，不计作最终候选验收。
本轮未采用经验证的 RTOS 等待服务，未在 H01 加短重试或忙等。gen 122 的 W 前保留列表与面板、H01 视图切换 STALE 检查及 Shadow 标签均保留。

验收分两阶段。两个 P1 的完整验收先在 SHA `0a687c3427bb23125cd8b88855cedcf80639ce625152931ab2251e382325fabe` 上全部通过并冻结。随后按编排者补充裁决，仅增加锁定显示增量，生成上面的最终 SHA，只重跑相关锁定案例。两阶段原始记录分开保存，未把阶段 A 的执行说成最终 SHA 上的全套重跑。

| 验收 | 50mm | 28mm | MOUNT |
| --- | --- | --- | --- |
| 复审反例 | 9/9 | 9/9 | 9/9 |
| H01 条件与入口组合 | 48/48 | 48/48 | 48/48 |
| W 前保留视图组合 | 36/36 | 36/36 | 36/36 |
| 定向安全检查 | 8/8 | 8/8 | 8/8 |
| 阶段 A 原审查主矩阵 | PASS | PASS | PASS |
| 阶段 A 完整官方半按路径 | PASS | PASS | PASS |
| 原始通信流复核 | PASS, raw=true | PASS, raw=true | PASS, raw=true |
| 最终 SHA 锁定显示相关案例 | 8/8 PASS | 8/8 PASS | 8/8 PASS |

H01 共覆盖八种条件：通信失败、通信失败且行复位、ready=0、ready=0 且行复位、settings epoch 与持续通信失败、mode epoch 与持续通信失败、读取中 settings epoch 变化、读取中 mode epoch 变化。每种条件分别走方向键、DISP、确认，并分别检查入口前恢复和持续失败。每例都验证不显示自有八行、没有新 W、没有锁定，后续成功重开恢复配方 05。
W 前组合覆盖列表和面板、settings epoch、mode epoch、通信失败、连续三次失败、ready 变化及行复位，再分别走三个重试入口。复审九例、H01 各入口及主矩阵都保存完整 `rpc_log`；主矩阵按实际会话分别保存，没有把多个会话拼成一条流。

partial_reset 三单元均恢复配方 05。50mm 为 805 次 X/V/W、W=253，28mm 和 MOUNT 为 803 次、W=253，与 gen 121 的完整恢复行为一致。正常已应用配方重开为 265 / 264 / 264 次 X/V，W=0；最终锁定案例的准备阶段也核对了相同完整流，见 [final-normal-open.json](evidence/final-normal-open.json)。数字只计展开的单元通信，不表示相机耗时。
官方半按从原始键 0x0d 转换为逻辑 0x29，再经原生任务分派和 H07。H01 失败后已先回到原生七行，半按期间 DAT 入口和 RPC 都为零；没有把仍未核对的配方显示成已应用。下一次成功重开完成完整恢复。此处不包含曝光完成。

通信复核直接调用编排者提供的 `research/g122_keep_list/audit_records.py`，没有修改该入口，也没有传 `--sentinel-records`。结果见 [record-safety.json](record-safety.json) 和 [分组原始流复核](evidence/)。每次 X/V/W 均核对九行映射与 T。奇地址和 33 B 行的半字边缘允许协议覆盖相邻字节，W 必须保留最近读回的原值；没有把物理半字扩边写成严格只访问逻辑字节。
复核器另通过 17 项检查，包含拒绝缺页故障摘要、越界页、越界 V 及相邻字节改变。故障事件摘要单独登记，不计作原始流。

| 编译码类别 | 闭合依据 |
| --- | --- |
| 地址与长度 | 六个改动函数映射到七个编译区间；最终 DAT、ELF `.engine` 与 engine.bin 字节一致。阶段 A 的 889 例执行该阶段 M32R 完整读回生成器，完整核心源码在最终增量中逐字不变，含所有失败切点、九行首中末差异及 T 差异。W 恢复另由原生案例及完整流检查。 |
| 文件操作 | 改动没有 storage 调用。三单元能力不含文件写位；原生服务 create/rename/delete/mark 拒绝，只读句柄 write 拒绝。所有已收集文件变更计数为零。 |
| 原生界面写入 | 失败 H01 走既有 release_view；gen 122 的活动页与状态 STALE 条件逐字保留。op 2 在既有 IRQ 写入点核对旧归属，再改为单行，op 3 另查归属后重绘。三单元视图切换和锁定时失去归属均无 DAT 迟到写入。固定原生续程仍可写界面。 |
| 循环与内存 | 九行、每行最大 96 B，条目最大末端 551≤552。导航编译上限各 16 轮，补偿 4+2。没有新增循环；列表更新增加一个 40 B 栈描述符。最大静态单帧 172 B，不表示 RTOS 栈高水位。 |

编译码细目见 [codegen-safety.json](evidence/codegen-safety.json)。889 例属于冻结的 P1 阶段，未在最终 SHA 上扩跑。其核心源码、H01 与锁定规则未变，增量只改 keep_view 与 ui_list，见 [p1-preservation.json](evidence/p1-preservation.json)。889 例把 RPC 和恢复叶函数作为边界模型；内联 settings 成功尾部在首次 compute 调用处建模。原生设置、完整恢复和界面行为由分阶段的原生案例检查。本轮没有声称全程序翻译等价或 RTOS 调度验收。

包内 30 个文件齐全，29 个固定文件与 gen 120b 逐字节相同，只替换 GXRCE.DAT。三单元 48 个展开条目和全部有效行与 gen 121 相同，固定 resident 未变。核对见 [package-check.json](evidence/package-check.json)。源码差异为 [相对 gen 122](source-change-vs-g122.patch) 和 [相对 gen 121](source-change-vs-g121.patch)。

原审查 24 条命令只在阶段 A 尝试。按补充裁决优先完成 P1 和锁定增量，停止可选命令；未完成项不记 PASS。逐条结果见 [optional-24-commands.tsv](optional-24-commands.tsv)，本轮不把它们设为放行条件。

| 单元 | 已通过 | 尝试数 | 状态 |
| --- | --- | --- | --- |
| 50mm | 2/24 | 3 | INCOMPLETE_PRIORITY_STOP |
| 28mm | 2/24 | 3 | INCOMPLETE_PRIORITY_STOP |
| mount | 2/24 | 3 | INCOMPLETE_PRIORITY_STOP |

锁定增量覆盖 write_latch、d2 四次失败后恢复、d2 持续失败、原因码和单行光标、面板中途锁定、列表与面板归属丢失、ERR 转换期间归属丢失。三单元各八例全部通过。四次失败恢复的控制例没有提前锁定；归属丢失时当次 DAT 迟到界面写入为零，下一次 H01 合法重发布另记。
ERR 字形转换在 IRQ 段之前。归属核对位于既有列表服务的 IRQ 写入点，先检查原列表或面板，再更新为单行并恢复 IRQ，之后走既有原生重绘。任务上下文查询在 IRQ 外。已归属视图必有缓存快照，此段不分配、不发 RPC、不写文件，也不在 IRQ 段转换字形或重绘。
已接受的限制保留：H07 keep=0 的固定收尾会关闭列表；拍摄完成和拍后回显超出设备模型；resident 的 inflight、RF_BUSY、rv_check 提前返回不在 DAT 覆盖内；冷启动单元未就绪时 DAT 不运行；DISP 提示仍由另一项研究处理。
首轮核对复审 SHA256SUMS 为 811 项全匹配。gen 121/122 源码、DAT、旧包和复审目录保持不变。本轮期间观察到五个共享 g122 证据文件随 r2 核器交回而更新，前后摘要单列在 [integrity.json](integrity.json)，未把这些更新说成旧快照未变。
只写本任务三个新目录。原始字节、反汇编和含实际值的运行记录均在 local 下，卡候选文件按要求位于 package_v36_g123/SD_ROOT。启动的并发执行均为本地主机检查进程，没有启动子代理。

主矩阵首轮为补齐完整 RPC 流而停止，记录保留在 local/history；表中结果只取完整重跑。自动历史输出统一移入 local/history/generated-output-history，原路径与摘要见 [history-paths.json](evidence/history-paths.json)。复现命令见 [REPRODUCE.md](REPRODUCE.md)。[SHA256SUMS](SHA256SUMS) 的路径以仓库根为基准，排除清单自身。
