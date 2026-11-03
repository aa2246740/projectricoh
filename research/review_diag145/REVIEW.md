不能上卡

| 编号 | 级别 (P0/P1/P2) | 位置 | 说明 | 建议 |
| --- | --- | --- | --- | --- |
| D145-01，OPEN | P1 | `diag.c:462–482`；最终 DAT `trace_flush@0x24C0`、文件桥 `0x49EC..0x4A10`；原生 `0x0500D4E4`、`0x200A40F4`、`0x200A468C` | 新增写入在 H01 调用任务内同步执行。文件锁等待参数为 `10000`，原生高层 API 不检查等待结果。独立原生函数重放中，等待返回 −50 后，open 仍查找文件并 signal；write 仍调用底层数据写并 signal，最后返回 512。取锁失败没有使写入停止，不能据此保证互斥或写入范围。实机是否会触发该等待失败尚未验证。 | 新增持久写路径必须在取锁失败时停止，且不得释放未取得的锁；核对真实调用任务、锁依赖和完整操作期限。在现有高层 API 外再套 semaphore 47 会重复取非递归锁，不能作为修复。修复前撤去新增写入路径。 |
| D145-02，OPEN | P1 | `diag.c:447–482,493–538`；实现报告 `REPORT.md:72–78,146–149` | 判读表不成立。本轮复现了两条不同执行路径：init 后退役，以及三个菜单均运行但菜单写入失败。两条路径留下的完整 4,096 B 文件逐字节相同，SHA256 均为 `ae9a86f390f6a40962f797684cd7a11e8d35c0bdcc0c298ba40a5047adc9a33e`。空槽还可以来自文件打开/校验/写入失败或落入第 4 槽。不能据这些负记录决定刷 resident。 | 将空槽、只有 init、未更新的旧槽列为原因未定；读取全部四槽及原始/会话身份。给日志失败增加独立的可观察结果；在此之前只使用有效新记录的正向证据，不由缺记录推导机身改动。 |
| D145-03，OPEN | P2 | `diag.c:466–482,501–502,535–536`；`decode_trace.py:52–80` | 文件没有记录 CRC 或提交协议，验证结果滞后一轮，最后一次验证只在 RAM。部分写故障后，文件仍有正确 magic、`menus=1`、首条结果 K、`last_verify=0`，但 last 记录全零；现有解码器照常输出。验证读的 close 返回值也被丢弃。 | 给记录增加完整性与提交校验，保留上一份完整记录，解码器拒绝不一致记录；区分未验证、验证成功和验证关闭失败。不能把上一轮的 0 当作当前落盘成功。 |

2026-10-31。无新增 P0。D145-01 和 D145-02 阻断本候选；不是因缺少本轮实机测试而单独否决。已接受的 g144 左右键写 `S+0x39F` 不作为问题重提。

本文 `diag.c` 指 `firmware/engine_diag_v38_g145/candidate/containers/product/diag.c`。所有原生地址绑定题设 v3.8 ilaunch3。只写本复审目录及指定 Scratch，未访问相机、卡或 `/Volumes/RICOHDCX`，未做 Git 写操作，未改产品、卡包或实现报告，未启动子代理。

## 1. S 和设置安全

静态已证：g145 相对 g144 的执行逻辑增量是 trace、四个文件桥和声明；UI、resident、原有服务逻辑没有改动。源码变化共六个文件，另三个是版本/构建路径信息，详见 `source-diff.txt`、`static-review.json`。

最终卡包 DAT 的代码与所审 ELF 一致，隔离重建也与该 DAT 逐字节一致。本轮从成品核对了 11 个原生桥；五个 RPC 调用点的命令仍只有 X=23、V=21，没有 W=22。没有新增 S store、拍摄设置 setter、设置保存或明确以 NAND 为目标的调用。`rv_settings_entry` 仍只标记本次入口。CAP_UI 不是文件保护机制，新增文件桥直接调用原生 API。

主机已证：最终卡包的 50mm publish、MOUNT publish、28mm refuse、28mm retire 均通过原有断言。refuse 组包含四次拒绝、两次正常发布、关闭、上/下/DISP。新增文件异常、计数和身份故障组均追踪完整 4,096 B S 区，store 为 0，前后哈希相同，RPC W 为 0。见 `cases/`、`probes/*.json`。

未发现超出已接受 g144 集合的新 S 写入。`S+0x39F` 的导航写和事件 `0x7C` 对非法 `S+0x63B` 的规范化逻辑没有变化；本轮没有重跑任意物理事件、模式盘或完整关机保存，也不将这些主机结果扩大为所有实机事件的全称证明。文件 API 的失锁竞争风险另见第 2 节。

## 2. 实机文件写入安全

### 文件入口与路径

静态已证：引擎唯一文件路径是 `/ATA1/GXRTRACE.BIN`。三个 open 调用点的 flags 为 0、2、0；四个桥对应 open `0x200A40B4`、read `0x200A449C`、write `0x200A45E8`、close `0x200A437C`。最终 DAT 中未出现 create `0x200A544C/0x200A41AC`、rename `0x200A49D8`、delete `0x200A4910` 的完整地址常量，桥及拆分指令检查也未发现相应目标。

原生 open 只有 flags 含 `0x200` 才走 create；成品调用不含该位，缺文件不会新建。原生 open 的已有文件分支固定向下传 mode 2，因此“flags=0”在这里是 DAT 的读取用途，不能另解作底层强制只读权限。load 路径本身没有 write。证据为 `static-diag145.json`、`engine-disassembly.txt`、`native-open.txt`。

### 异常分支

以下“主机”均执行最终 DAT 指令，文件 API 是明确的故障模型，未测试真实卡的机械写保护、电气拔卡或断电。

| 条件 | 静态及主机结果 | 实机边界与退出办法 |
| --- | --- | --- |
| 文件缺失 | load open 失败，`trace_error=1`，0 次 write，S 页仍发布。 | 不能把空槽解释为没到 init。关机后保留现有证据，由编排者重新放入并核对空白文件。 |
| 文件短于 4,096 B | 本轮 4,095 B 用例在读取/EOF 检查失败，`trace_error=2`，0 次 write。 | 重新准备前先保留错误文件，不在相机内重建或修复。 |
| 文件长于 4,096 B | 本轮 4,097 B 用例的额外 1 B 检查失败，`trace_error=2`，0 次 write。 | 同上。大小只在 init 检查一次，后续重开不重新核对大小、头或 SD 身份。 |
| 坏文件头 | `trace_error=3`，0 次 write，S 页仍发布。 | 空槽不构成加载失败证据；关机后保留副本，再核对准备过程。 |
| 写保护或写失败 | 拒绝 flags=2 打开时，`trace_verify=1`；拒绝 write 时为 2。DAT 不停用 trace，后续菜单继续尝试，直到 16 次尝试上限。 | 真实卡可能在 open、write 或 close 才报错，等待时长未验证。停止本轮，关机后检查写保护并保留文件；不能把失败期间的旧槽视为新记录。 |
| 部分写、移除介质 | 故障模型允许部分数据已写后返回错误；DAT 尝试 close。该次可留下混合记录，仍继续后续尝试。没有原子提交或介质身份复核。 | 未验证驱动拔卡后的期限、缓存提交和目录/FAT 故障行为。不要热拔验证；若已异常，保留卡的离线镜像，先检查文件系统再继续使用。 |
| close 或读回失败 | 写 close 非零记 3，重新 open 失败记 4，短读记 5，不同记 6；load close 非零记 `trace_error=4`。验证读最后的 close 结果被忽略。 | 最后一次错误不一定能从文件得知。按失败取证处理，不能继续按成功表判读。 |

### 调用任务、阻塞和锁

静态已证：`ig_init → trace_init → trace_flush` 和 `ig_menu → done/trace_menu → trace_flush` 都是同步调用，没有提交给 Task 8、创建 worker 或异步队列。读写在执行 H01 的调用任务上运行，正常 UI 路径为 Task 6。主机将 task-id 桩固定为 6，这不是本轮实机任务观测。

原生 semaphore 47 初值/上限为 1，非递归。`0x0500D4E4` 调用等待包装时传 47 和 `10000`，不是无限等待参数。本轮不将这个数换算成实机秒数。DAT 没有整个 load/flush 的期限、取消或失败后停用逻辑；一个 flush 包含 open、写、close、重新 open、16 次读、close，首个菜单还包含 init 的一轮和菜单的一轮。16 次上限限制的是 flush 尝试，不限制单次延迟。

主机已证：`native_failure.py` 移去高层文件桩，执行真实原生 open/write 和 semaphore wrapper，只在等待结果及下层文件端点注入故障。等待返回 −50 后，open 的观察顺序为 wait、parse、lookup、signal；write 为 wait、data-write、signal，返回 512。见 `native-lock-failure.json`。这是控制流反例，没有向真实介质写入，也没有证明实机必然出现该超时。

实机未证：H01 进入时是否可能已持有 47，其他持有者是否需要 Task 6 的消息处理或回调才能继续，以及设备错误时的完整锁依赖。不能排除这些依赖，也不能宣称已复现同任务死锁。即使信号量等待因期限而返回，忽略结果继续写、随后释放也不构成安全恢复。已有 DAT 读卡或 gen115 create 的现场先例，不能关闭新增 write 路径上的这个问题。

### 数据簇、FAT 和目录项

静态已证：DAT 每轮从文件偏移 0 写总计 4,096 B，无 seek、truncate、extend、create、rename 或 delete 的主动调用。逻辑上只改本单元槽，但实际每次提交整个 4,096 B，包含其他三槽和文件头。正常既有文件仍为原文件、大小/簇链稳定且互斥成立时，这是覆盖已有数据的调用形态。

模拟器已证：在指定 FAT16 镜像和三轮重放后，GXRTRACE 的首簇、长度、目录项和其 FAT 项不变，最终差异仅在自己的数据簇及原厂另外创建的目录。详见第 3 节。

未证：这不是所有实机异常下“绝不写其他簇/FAT/目录”的证明。后续 open 不重新核对大小和介质身份；短文件或替换介质可使覆盖请求变成扩展请求。D145-01 还破坏了对共享文件系统状态互斥的假设。现有镜像前后差异也不能排除向 FAT/目录写入相同字节，原运行没有交付完整块写 LBA 日志。本轮未观察到真实卡越界写或 FAT 损坏，不把这些风险表述为已经发生。

## 3. 模拟器主张

主机静态核对通过：官方与 v3.8 的整个 ilaunch3 差异均落在头部校验、resident/root 窗口和七个钩子，没有额外差异。七处为 H01/H02/H05/H06/H07/H08/H09，差异字节数分别为 8/4/8/4/4/4/4。

以下区间逐字节相同，起点包含、终点不包含。完整 SHA256 见 `static-review.json`。

| 区间 | 核对结果 |
| --- | --- |
| 文件 API `0x200A3000..0x200BC000` | 相同。 |
| SD 驱动所查范围 `0x20057000..0x20060000` | 相同；全文件差异分类还排除了该范围外的未列修改。 |
| 文件信号量包装 `0x0500D418..0x0500D520` | 相同，包含 wait/signal/初始化入口。 |
| 内核所查范围 `0x05002000..0x05003000` | 相同。 |

模拟器已证，限既有 run2：本轮独立重建原始合成 FAT16 初态，SHA256 匹配 `card-0-placed.sha256`；重建三轮预期数据，和现存最终镜像里的 4,096 B 逐字节相同；用独立 FAT 解析核对最终镜像与保存结果一致。首簇为 3，数据起始 LBA 129，大小 4,096 B，32 B 目录项完全不变，两份 FAT 一致，无未引用簇。最终全镜像差异均可分类为 GXRTRACE 簇 3 或原厂 DCIM/CLIPINFO 的 FAT 项、根目录项和目录内容。见 `emulator-review.json`。

因此，“mode 2 在这个已有文件、这个 FAT16 几何和正常返回的重放中覆盖原数据，没有留下重分配结果”成立。不能从一次 mode 2 样本推出任意大小、介质变化、FAT32、写保护、移除、断电或竞争情形都不分配或不改元数据。

run2 是官方 1.51、合成 jlaunch、Task 8 的宿主发起调用。71 个文件调用均返回 Task 8；28mm 槽只是人工生成的数据位置，DAT 未运行，也没有真正的 28mm/MOUNT 单元或 v3.8 H01 调度。文件相关代码字节相同不等于调用任务、锁持有状态和调度相同。

最长读调用为 33,839,199 步。记录里有 Task 8 的 wait 入口和 signal 入口，期间 semaphore 计数为 0，另有 Task 6 的后续活动。但没有“取得锁”事件或锁所有者轨迹，计数 0 既可以表示自己持锁，也可以表示别人在持锁。因此报告将这段全部归为“Task 8 正在等文件锁”证据不足，可能还包含持锁后等待设备。33.8M 步也不直接对应相机上的延迟时间。

本轮核对保存镜像和日志，没有重跑约 36 分钟的模拟器运行。实机 DAT/H01、实际锁依赖、卡时序、拔卡和断电仍未验证。

## 4. 记录能否支撑判定

结论为不能无歧义地区分题设三种结果。

| 文件现象 | 现在可以支持的结论 | 不能直接推出的结论 |
| --- | --- | --- |
| 目标槽为空 | 没有该槽的有效持久记录。 | DAT 未到 init。缺文件、坏长度/头、读写失败、异常身份都能产生此现象。另一单元的成功不证明本单元当时的 I/O 成功。 |
| 只有 init | 至少某次 init 的记录被写入。 | 当前开机第一次菜单前退役。D145-02 有完整文件相同的反例。 |
| 有完整、确定新鲜的菜单记录 | DAT 曾到达菜单记录位置，可以结合 outcome、入口标志、掩码和原始输入分析当次门槛。 | 每个结果都能只靠两个掩码唯一解释，或最后一次记录已验证落盘。 |

主机已证的全文件反例见 `diagnostic-counterexample.json`：正常退役和实际运行三个菜单但后续写失败，均留下 `boots=1/flushes=1/stages=1/menus=0/last_verify=0`，完整文件逐字节相同。这关闭了“只有 init 就能判退役”的主张。部分写还可使计数和记录相互矛盾，见 `probes/partial-menu.json`。

掩码是条件投影和阶段信息，多个位可同时失败。入口拒绝结果 `I` 不在原报告三类拒绝表里；本轮注入第二次菜单的请求版本错误，得到 I、ingress=0、body/DAT 掩码均为 00，此时部分字段沿用上次入口。源码还有 `O`，表示 render 后归属检查失败，也不能按普通 K 或 X 判读。见 `probes/ingress-I.json`、`diag.c:568–587`。因此 §7 的“只有 DAT 掩码就只改指定文件”“空或只有 init 就改 resident”均需撤去无条件推断。

槽选择是会话单元名的完整 8 B 精确比较：`jlaunch\0 → 0`、`qlaunch\0 → 1`、`l08firm\0 → 2`，其他或无可用会话为 3。不会根据物理单元、前缀或后续 RPC 读数修正槽号。单纯 T/行 RPC 读取失败不改变已选槽。正常加载时会话/单元身份本来就要通过 resident 检查，不能把所有坏名称都假定为能成功加载的正常情形。

主机故障注入在 trace_load 的文件入口改变会话名：全零、`qlaunchX`、`l08firmX` 都将 init 写入第 4 槽，目标槽为空，随后 resident 退役。原始名称仍是 qlaunch。该实验验证实际成品的分流，不证明真实单元会产生这些坏名称。解读 28mm/MOUNT 时必须查全部四槽及两份名称，不能只查预期槽。见 `identity-probes.json`。

16 次上限确实生效，但含 init、失败打开和失败写入的尝试。主机连续 18 次菜单后，RAM opens=18，卡上停在 flushes=16、menus=15、last.entry=15，只保留前八条 menu 数组及第十五条 last。此后的记录只改 RAM。三次 ADJ 的计划不会正常触顶。

存在每槽 `boots` 计数器。init 读取旧槽 magic，取旧 boots 加一，再清理本槽；它不是全局启动序号，也不在 DAT 未运行或写入失败时更新，32 位加法可回绕。旧文件保留、下次完全不加载时，原记录及 boots 都原样留下，本轮 `stale-notready` 已复现。题设准备时核对全新空白文件能排除交付前旧记录，但不能补上本次失败记录的缺失，也不能在下次复用时继续假定新鲜。

## 5. 用户看到的行为与延迟

主机已证：最终 DAT 在 50mm 发布 `S0001 R9`，与 g144 的正常 S 页流程一致；MOUNT 的主机正常模型也发布该页。28mm 拒绝页仍为八行、A/B/C 轮换，页尾版本从 `DIAG 144` 更新为 `DIAG 145`。没有新增日志错误提示或进度页；文件缺失/坏头/写入失败时，S 页也可照常发布。

g145 主块请求为 56,272 B，较 g144 的 49,656 B 增加 6,616 B。这会改变可用堆读数和加载余量，本轮不将主机模型的堆余量推作 28mm 实机值。

延迟有明确的同步 I/O 来源，不能承诺只有“一点点”。第一次 ADJ 同时承担 trace load、init flush 和 menu flush；后续每次菜单也读写、重读该文件。实际时间取决于原生锁和设备等待，当前没有整体期限。用户只按 ADJ/OK、不开照片，不能消除开机或其他任务的卡活动；本轮没有访问 B 卡，未核实其现存目录或卡状态。

本轮未验证 LCD、真实按键调度或实际菜单延迟。题设已验证的 g144 屏幕行为可以作为既有事实，不能代替新增文件路径的实机接受。

## 6. 恢复

静态核对通过：恢复用 g137 为 `78dcbb9a2735cd84e55385683ce0296b97818ddf90f8b492d9003512dbeff3f8`。完整关机、把该文件放回 GXRCE.DAT、重新开机，按题设已验证的加载机制可恢复 v3.8 + g137 的程序组合，不需要重刷机身。本轮未操作卡或执行这一实机恢复。

g137 DAT、v3.8 resident/机身和官方机身中均无 GXRTRACE 名称引用；已核对的 loader 只按固定 GXRCE 路径加载。留下这份 GXRTRACE.BIN 作为普通卡数据，不会由这些程序继续更新或作为 DAT 执行。若文件系统完好，保留它不影响程序回退；该结论不等于换 DAT 能修复之前的卡错误。

恢复办法按错误层次区分：

1. 页面正常或仅缺日志时，结束本轮，正常关机，先保存 trace 原件，再恢复并核对上述 g137 哈希。
2. 出现 I/O 失败、部分记录或文件系统异常时，先保留文件及离线卡镜像，再检查文件系统；不要仅换 DAT 后继续写卡，也不要用格式化覆盖证据。
3. 菜单阻塞时，能正常关机就正常关机；若无法退出或关机，只能断电恢复。强制断电不保证在途文件安全，重开前按上一步保全并检查卡。当前未验证的期限不能用“再等一点”替代。
4. 换回 g137 只恢复程序组合，不撤销原厂已保存的 S 字段，也不恢复未知旧设置。题设的 ADJ/OK 路径本轮未发现新增 S 写；若实际操作越出该路径，按实际旧值核对，不能承诺换文件自动回滚。

## 7. 包身份、复现和证据封存

| 对象 | 核对结果 |
| --- | --- |
| `SD_ROOT/GXRCE.DAT` | 29,164 B；generation 145；SHA256 `222ccf4b4f7975bc758160e184742631d4f8bf05fed968ce72483071b1a06a2b`。 |
| `SD_ROOT/GXRTRACE.BIN` | 4,096 B；`GXRT145\0` 后均为零；SHA256 `d207116ca69b55ecc91dd5be07ef5441009ee1758c29d953e4b2f333c37c9cae`。 |
| v3.8 ilaunch3 | SHA256 `d4fa3b46da137b8b7c7c703e66750a8249c0715271290c0fdb490a2f7a239a90`，不在本包 SD_ROOT 中。 |
| resident build / ABI | `79d8e2a2dfc322f3c2470c0369d736473f0b478dcf7c0e3bebf1feb0e82596f2` / `ca2d88a054ee3c2ae71b125cbdec285c`。 |
| 隔离重建 | 使用现有编译器、原构建/打包函数、同一源文件和参数；产物 `rebuild/GXRCE.DAT` 与最终包逐字节一致。代码 19,612 B，BSS 19,604 B，重定位 1 项。 |
| 包内容 | SD_ROOT 恰好两个文件；相对 g144，替换 DAT 并新增空白 trace。`.gitignore` 相同，SHA256SUMS 的三个文件条目均验证，包括包外机身身份条目；没有其他交付文件。 |

重建只在内存中重定向输出/日志/临时目录，并把产物元数据的相对路径根改为仓库根，没有改编译源码、参数或产品脚本。现有 `static_check.py --package` 和直接 build 命令会写产品目录，本轮没有原样执行它们；对应只读检查和隔离适配见 `static_audit.py`、`rebuild.py`。

证据分层如下。

| 层级 | 本轮可复核证据 | 边界 |
| --- | --- | --- |
| 静态已证 | `static-review.json`、`static-diag145.json`、`additional-static.json`、成品及原生反汇编、`source-diff.txt`。 | 源码/二进制身份、调用形态、分支和差异范围。 |
| 主机已证 | `cases/`、`probes/`、`native-lock-failure.json`、`diagnostic-counterexample.json`、`rebuild/result.json`。 | 真 M32R 指令；RTOS、文件、RPC、显示端点含桩，故障明确注入。不能推作介质或 LCD 接受。 |
| 模拟器已证 | 原 `research/emulator_m2d/local/unit28-g145/run2/`；本轮 `emulator-review.json` 独立核对初态、最终镜像与保存结果。 | 原厂 FAT/驱动在合成介质上的 Task 8 重放；不是 DAT/H01 或真实单元。 |
| 实机未证 | 本轮没有相机、卡、实机任务/锁、LCD、延迟、移除/断电或实机恢复观测。 | 不将上三层扩大为这一层。 |

复跑均使用 `/usr/bin/python3 -I -B`；每个测试工作进程的墙钟超时为 4,200 秒，超过相关历史耗时三倍，最多同时两个测试工作进程，没有 sleep 轮询。常规组约 45–61 秒，18 次菜单组约 77 秒，文件故障组约 255 秒，身份注入组约 105 秒。

保留了两次复审工具失败。首次 cap 与故障组共用解码缓存，在原生解码处失败；隔离运行缓存后 cap-r2 通过。首次镜像审计调用既有 create 时被其输出目录限制拒绝；改为独立在内存重建初态后 emulator-audit-r2 通过。没有修改原工具来解除边界。REA 固件扫描接口要求 Linux 和 REA_BINWALK_COMMAND，当前不可用，二进制核查使用仓库现有 M32R 工具。

在仓库根顺序执行以下命令。首次复审的输入快照已保留，勿覆盖；复跑会更新本复审输出，先保留当前证据副本。

```sh
export TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/review-diag145
/usr/bin/python3 -I -B research/review_diag145/run_job.py static static_audit.py
/usr/bin/python3 -I -B research/review_diag145/run_job.py rebuild rebuild.py
/usr/bin/python3 -I -B research/review_diag145/run_job.py 50mm-publish run_case.py 50mm publish
/usr/bin/python3 -I -B research/review_diag145/run_job.py mount-publish run_case.py mount publish
/usr/bin/python3 -I -B research/review_diag145/run_job.py 28mm-refuse run_case.py 28mm refuse
/usr/bin/python3 -I -B research/review_diag145/run_job.py 28mm-retire-r2 run_case.py 28mm retire
/usr/bin/python3 -I -B research/review_diag145/run_job.py faults probes.py faults
/usr/bin/python3 -I -B research/review_diag145/run_job.py cap-r2 probes.py cap
/usr/bin/python3 -I -B research/review_diag145/run_job.py native-failure native_failure.py
/usr/bin/python3 -I -B research/review_diag145/run_job.py identity-probes identity_probes.py
/usr/bin/python3 -I -B research/review_diag145/run_job.py emulator-audit-r2 emulator_audit.py
/usr/bin/python3 -I -B research/review_diag145/run_job.py final-checks final_checks.py
/usr/bin/python3 -I -B research/review_diag145/seal.py
```

最终受保护输入、Scratch 清理和本目录文件校验结果见 `seal.json`、`SHA256SUMS`。SHA256SUMS 使用仓库根相对路径，不包含它自身。
