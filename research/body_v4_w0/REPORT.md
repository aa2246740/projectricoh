架构 A：未通过（差 5,668 B）；架构 B：最小窗口尺寸通过（余量 736 B）；推荐继续 B，先闭合永久 RAM 与早期载入屏障。

# body-v4-w0-size-r2

本轮续用 r1 的代码、ABI 和编译记录。A 压缩 392 B 后仍超限；B 已编译、严格链接并验证最小窗口部分。B 的完整受信扩展尚未链接，永久 RAM、全局启动顺序和 native 门禁仍为 OPEN。这里的尺寸通过只对应 B 的窗口原型。

工作起点为 2026-10-28 13:45:21 UTC，时间盒截止 16:45:21 UTC。最终核对时间见 [verification.json](verification.json)。本轮只写 `firmware/resident_v4` 和 `research/body_v4_w0`；没有生成机身镜像、DAT 或卡目录，没有访问相机、存储卡或网络，没有启动子代理。

## 1. 固定边界与证据身份

窗口固定为 `[0x2005276C,0x20054800)`，8,340 B。两种窗口都保留 512 B root 和 200 B 强制保留区，payload 严格上限为 7,628 B；原设计名义目标为 7,520 B。

| 项目 | A | B 最小窗口 |
| --- | ---: | ---: |
| payload。 | 13,296 B。 | 6,892 B。 |
| root。 | 512 B。 | 512 B。 |
| 物理余量。 | −5,468 B。 | 936 B。 |
| 扣除 200 B 后的余量。 | −5,668 B。 | 736 B。 |
| 相对 7,520 B 名义目标。 | 超出 5,776 B。 | 低于 628 B。 |
| 严格链接返回码。 | 1。 | 0。 |
| payload end。 | `0x20055B5C`，诊断用，覆盖 root 地址。 | `0x20054258`。 |
| 可安装产物。 | 无。 | 无。 |

A 的负余量是窗口预算差额；诊断 ELF 中代码和 root 地址重叠，不能执行或安装。B 的普通空余是 `[0x20054258,0x20054538)` 的 736 B；`[0x20054538,0x20054600)` 的 200 B 未使用。

| 已核对文件 | SHA-256 |
| --- | --- |
| 官方 1.51 `ilaunch3`，全文件 3,993,340 B。 | `da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7` |
| 固定 v3.6 `ilaunch3`。 | `50720c80696ca88f25dc25a85285acd0e0f19906e1d7da1dd404f6cc243f9008` |
| A 最终诊断 ELF。 | `09a7b4210ac546f3baef224b7d64dc60a9bc146c4b93aa7b0c5a9e43de747652` |
| B 最终窗口 ELF。 | `fde39decc1ac3f1176432df87831dd241c635ea0c82af5769bd502b99b37e69b` |

工具链为本地 M32R GCC 13.4.0 和 GNU ld 2.43。两者均使用 `-Os`、freestanding、medium model、无 PIC、无额外可写全局；没有 LTO 或节 GC。编译关闭的路径仍保留在尺寸账中。实际 map、反汇编和理光派生字节均在 `local/`。

r1 的 135 个文件已按原路径层次复制到两个目录各自的 `local/r1/`，包括源码、生成头、原始 JSON、日志、ELF 和 map。起点清单为 [r1-snapshot.json](local/r1-snapshot.json)，本轮核对未改动这些副本。原始尺寸记录见 [r1 size.json](local/r1/size.json)。

## 2. 架构 A 的最终链接账

以下按实际保留的 input section 计数，包含只读数据、桩和模块内填充。root 只另计一次。完整账见 [size.json](size.json)，严格失败信息见 [strict-link.log](../../firmware/resident_v4/local/strict-link.log)。

| 模块 | 名义目标 B | r1 B | r2 B | r2 超目标 B |
| --- | ---: | ---: | ---: | ---: |
| 信封与 trust。 | 1,104 | 1,432 | 1,312 | 208 |
| loader。 | 1,536 | 2,143 | 2,143 | 607 |
| binding、入口、退役。 | 992 | 1,584 | 1,536 | 544 |
| runtime、native、bridges。 | 312 | 728 | 712 | 400 |
| UI 安全与 192 B 空说明。 | 896 | 3,364 | 3,364 | 2,468 |
| 通用分派与 hook 处理。 | 192 | 1,708 | 1,644 | 1,452 |
| 36 个桩、元数据和特殊续程。 | 1,376 | 1,640 | 1,496 | 120 |
| storage owner/fence 预算。 | 768 | 768 | 768 | 0 |
| boot/retry 预算。 | 128 | 128 | 128 | 0 |
| capture pin 预算。 | 96 | 96 | 96 | 0 |
| render 预算。 | 96 | 96 | 96 | 0 |
| 最终对齐。 | 24 | 1 | 1 | −23 |
| 合计。 | 7,520 | 13,688 | 13,296 | 5,776 |

storage 行包含 192 B 的 scope 拒绝代码及补足预算；boot 行包含 92 B 拒绝代码及补足预算；capture/render 各保留 96 B。它们尚未授予 task 8 作业、开机恢复、拍摄或自绘能力。目标 native profile 为 UNKNOWN，不能把这些预算或拒绝返回算作已实现门禁，也没有将其宣称迁入 DAT。

所有 36 个桩仍各占 32 B。原七处包含经官方字节核对的重放；其余 29 个位置仍是 UNKNOWN 返回桩，其 native ABI、实际覆盖指令和拒绝语义未闭合。

### 2.1 压缩项与安全义务

| 改动 | 实际变化 | 保留的义务 |
| --- | --- | --- |
| 比较 `-Os`、`-Oz` 和关闭 inline 的配置。 | `-Os` 和 `-Oz` 均为 13,688 B；关闭 inline once 为 13,712 B，关闭全部 inline 为 13,760 B。选用 `-Os`，没有尺寸收益。 | 不改入口、检查、桩和预算。原始比较见 [compiler-sweep.json](compiler-sweep.json)。 |
| hook 元数据删除重复 id，按固定目录顺序推导。 | 元数据 288→144 B，节省 144 B。 | 保留 36 个地址和对应顺序；没有删除 hook 槽或地址。 |
| hook 安全续程和生命周期路由表驱动；合并重复调用前检查。 | `hooks.o` 860→768 B，节省 92 B。 | H06/H08 的安全动作仍在 retire 前锁存；H02 保留自己的 binding 检查；DAT 调用在 `rv4_call` 入口和返回后检查 binding。零路由仍表示 native 协议未实现。 |
| 固定版本字段表驱动，连续 80 B 身份一次比较；十六入口一次解码。 | `envelope.o` 1,352→1,232 B，节省 120 B。 | 长度、CRC、布局、保留位、重定位和全部入口检查保留。入口验证失败仍清空结果，身份字段连续性有静态断言。 |
| 调用与 host 服务共用 wire 身份校验。 | binding 节省 48 B，dispatch 增加 28 B，净省 20 B。 | 各自的指针边界、phase、view generation、实际 owner、IRQ、pin 和返回后检查保留。 |
| 对固定且对齐的 unit-info 地址使用 M32R 大端 word 读取。 | `native.o` 84→68 B，节省 16 B。 | 仍读同三个身份字；信封和任意字节地址仍使用原大端字节读取 helper。 |
| 总计。 | 13,688→13,296 B，节省 392 B。 | 未使用 200 B，未减少 root，未开放未知能力，未把安全职责移给 DAT。 |

每轮编译状态和模块变化见 [compression.json](compression.json)；相应源码、ELF 和 map 在 `firmware/resident_v4/local/a-iterations/{a1-tables,a2-validation,a3-final}`。

UI 安全层仍为 3,364 B，仅 `rv4_view_publish` 已占 1,224 B，高于整个 UI 的 896 B 名义预算。分派为 1,644 B，loader 为 2,143 B。本轮没有找到再减少 5,668 B 且保留同等安全义务的实现，因此 A 的最终结论是未通过。

### 2.2 ABI 与 A 的验证范围

M32R 导出的 `sizeof/offsetof` 与 r1 相同，见 [ABI.md](ABI.md) 和 [target-layout.json](../../firmware/resident_v4/generated/target-layout.json)。root 为 512 B，wire envelope 为 256 B，event 为 64 B，reply 为 32 B，host header 为 32 B，descriptor 为 16 B。源码变化更新了 build/ABI 身份，不能把旧 DAT 直接 rebind 后视为已迁移。

主机 ASan/UBSan 通过，当前 harness 执行 1,493 次 CHECK，包含任意受理行数、四类 early、嵌套构造反例、reader 期间变更和返回后失效。native context、I/O 和 DAT 入口都是替身。

另将同一组 M32R 编译对象链接到 `0x21000000`，执行 H06/H08、七种行数、四类 gate、两种键，共 112 项。全部到安全 skip，未访问所监控的 setter，设置区零写入。它验证 hook 到续程的有界指令路径，不覆盖完整原生按键栈或完整 DAT。见 [host-tests.json](host-tests.json)、[machine-tests.json](machine-tests.json)。

## 3. 架构 B 的最小窗口

窗口保留开机 scope 检查、完整 SHA-256 pin 校验、只读载入、重定位、缓存同步、代码 pin、hook 跳板和有限应急续程。UI ticket、准入、撤销、DAT loader 和策略分派的完整常驻级实现拟放在受信扩展。受信扩展使用独立的 `GXRB4E01` 封装，普通 v4 DAT 使用另一套 ABI；二者不混用。

源码在 [arch_b](../../firmware/resident_v4/arch_b/ABI.md)。所有以下字节来自严格链接，没有诊断放宽：

| 链入对象 | 字节 |
| --- | ---: |
| `window.o`，冷启动、文件读取和最终发布。 | 1,520 |
| `sha256.o`，含常量表。 | 1,116 |
| `header.o`，身份、范围和重定位。 | 752 |
| `hooks.o`，代码 guard、pin、帧备份及 192 B 应急空说明。 | 1,020 |
| `linked_hooks.o`，36 个 32 B 桩、shared 和续程。 | 1,352 |
| `hook_metadata.o`。 | 144 |
| `boot_entry.o`，真实 native 启动 wrapper。 | 96 |
| `native.o`，scope/lifetime 检查入口及调用桥。 | 136 |
| `platform.o`，零权限 profile 和 16 B API。 | 32 |
| `bridges.o`，原厂文件、分配和 cache/IRQ 桥。 | 144 |
| `runtime.o`，完整链接的复用 helper。 | 464 |
| `trust.o`。 | 116 |
| 节间填充。 | 0 |
| payload 合计。 | 6,892 |

账见 [arch-b-size.json](arch-b-size.json) 和 [window.map](../../firmware/resident_v4/arch_b/local/window.map)。无未解析符号、无残留重定位、无 root 之外的可写全局。窗口 root 的实际 M32R 布局见 [arch-b-abi.json](arch-b-abi.json)，仍为 512 B。完整 v4 resident 状态要另放扩展 BSS，不能重复占用这个 bootstrap root。

启动 wrapper 已取代首次原型的 96 B 占位，实际仍为 96 B。最初版本的原厂 32 位重放未按字对齐，M32R 用例抓到非法指令对；现已补 NOP 并通过完整寄存器、PSW、SP 对照。失败 ELF、map、生成汇编和记录保留在 `arch_b/local/history/boot-replay-misaligned`。

### 3.1 永久 RAM 从哪里来

当前编译实现选择开机早期的原生主堆分配，申请一次并在已执行后持有、隔离，不 free、不热换。已从当前官方和固定 v3.6 输入复核：

| 事实 | 本轮证据与边界 |
| --- | --- |
| 主堆为 `[0x20704800,0x20744800)`，配置容量 256 KiB。 | 直接读取当前 `0x200C0DC0/C4`，两份输入相同。 |
| 初始化、分配、释放入口分别为 `0x2005BF00`、`0x2005BF5C`、`0x2005C038`。 | 当前字节相同，大端反汇编；原厂分配器有界执行见下文。 |
| 正常分配链中，持有块不会被另外一次分配领取。 | 原厂 M32R 指令用例先申请 81,920 B，再申请 72,560 B，释放邻块后再申请；第一块地址不重叠、内容保留。第一块实际 extent 为 81,932 B。只是合成堆状态下的局部合同。 |
| 单次分配不等于永久独占。 | 再次执行原厂 heap init 后，分配器会把第一块地址再次发出；堆边界相同，`rv4_allocation` 的包头检查仍通过，旧内容此时甚至仍在。这个反例没有证明运行期一定发生 heap init，但证明边界、包头和未 free 本身不足以标识分配实例。 |
| 堆执行与 cache 同步已有相机证据。 | `decisions.tsv:295`，UTC 2026-10-21、当地 2026-10-22 的 P0 用户回报。本轮没有重做相机实验；该证据是一次性执行后释放，未证明永久驻留。 |

原始窗口、偏移、哈希和反汇编在 [ram-evidence.json](ram-evidence.json) 所列 `local/r2-evidence/`，原厂指令用例在 [arch-b-machine-tests.json](arch-b-machine-tests.json)。

因此，当前不能证明运行期没有其他使用者。要把该主堆块称为永久 RAM，必须覆盖所有 heap init、销毁、重载、睡眠/唤醒和模块/模式切换路径，在改内存前阻止有代码 pin 的重建；同时审清释放、直接写者、DMA 或别名对该区的影响。还需核对实际空闲量、最大连续块和跨生命周期的实机存活。当前 `Bv4Platform` 的相关证明位为 0。

另一条方案是从原厂内存配置明确切出独占区，并同步扣减原厂 heap/arena 容量。它能把“普通 allocator 不再发出该区”变为结构约束，但仍须审边界、全部初始化和原始写者。本轮没有实现或链接这个预留区变体。已有高端保留区、UI arena、图像 arena 和段尾空洞均有已知用途或归属缺口，未作免费 RAM 使用。

### 3.2 载入时机

真实 96 B wrapper 的候选点是 `0x2010DDF8`：task 8 已调用 `0x2010E14C` 返回，随后原厂将媒体状态存入 `0x204F41E8` 并进入接收循环。wrapper 保存 r0..r13、LR、PSW 和 SP，调用 `bv4_boot` 后重放原厂 8 B，到 `0x2010DE00`，保留原厂初始化结果。

这只闭合局部 ABI。尚未证明 task 6、构造、绘制、所有拍摄生产者、恢复和更新分支都晚于此点。正式 B 必须先阻止这些 hook 调用者进入，完成扩展校验和 INIT 后再释放屏障；也要排除更新 init 路径。原型不把“提前触发时走默认分支”当作满足早于任何 hook 的证明。候选挂点未安装，boot probe 为 0，故目标默认在文件 I/O 前返回 UNKNOWN。

### 3.3 来源、信任和机身绑定

最小实现只读固定 `/IROM/GXRTR4.EXT`。IROM 是可写文件系统卷，不是不可改写的代码 ROM。现有 `research/irom_storage/REPORT.md` 支持正常启动时先挂载 IROM；其首次菜单结论不能直接升级成早期启动可读证明。卡可在未来作为交付来源，当前 bootstrap 没有卡回退分支。

执行权限来自窗口内嵌的批准文件 SHA-256。160 B 文件头还必须匹配官方底板 SHA、window build ID、bootstrap ABI、固件/CPU、入口和布局。完整文件通过 SHA 后，先检查全部重定位，再修改代码；INIT 之前同步缓存，返回后再核代码，最后发布 READY。没有由扩展自报一个 CRC/SHA 就取得信任。

窗口 build ID 排除待 pin 文件摘要，避免“文件头包含窗口身份、窗口身份又包含文件摘要”的循环；最终 ELF 的 SHA 仍覆盖内嵌 pin。当前批准摘要为 null，pin_enabled 为 0，平台证明也为 0；目标没有任何已获准执行的扩展。

这采用固定摘要 allowlist，不是签名更新系统。修改受信扩展需要重新批准摘要并重新链接窗口；普通 DAT 的策略更新仍可使用既定 ABI。若要求任意新受信扩展只换文件，就要另做签名验证、密钥和回滚策略并重新计账，本轮未实现。

### 3.4 失败、隔离与恢复

| 失败阶段 | 已实现行为 | 仍需证明的边界 |
| --- | --- | --- |
| 任何扩展入口之前失败，scope 和 close 健康。 | 停止装载，释放仍可证明归属的私有候选块，保留 factory 标志；原七处 hook 重放原厂指令。 | 完整冷启动、原厂 UI 和拍摄链未在相机验证。 |
| scope 变化或 close 不确定。 | 失败锁存，不再尝试另一来源；scope 丢失后不再补一次 native I/O，保留不确定句柄/隔离状态。 | 不能保证原厂文件系统健康，不能宣称已安全恢复全部原厂行为。 |
| INIT 已进入或扩展已 READY 后出错。 | 不释放执行过的内存，不热换；保留隔离，撤销新入口，恢复当前帧备份并走固定应急续程。 | 完整 UI 撤回、全部 native 生命周期与跨任务事务仍在完整扩展和 W2/W3/W5 中闭合。 |

窗口内应急路径包含 H06/H08 skip、H07 固定关闭、H05 永久空说明和 H01/H02 续程。它们的有限指令路径已经测试；它们不是任意运行期故障后的完整原厂恢复证明。

当前窗口在每次 hook 进入前、返回后都对 code 区做完整 SHA-256。最大输入接近 64 KiB，原生任务的时延与截止约束尚未测量，属于 B 后续必须验收的运行成本。

设计的日常停用方式是移走固定受信扩展文件后冷启动。该恢复路径依赖已验证的启动失败默认和健康文件 scope；本轮没有实机验收。boot wrapper 或 native hook 自身故障仍可能需要既定 Stage2l/官方机身恢复；恢复可达性和 50mm 安装约束沿用设计要求，未在本轮重新验证。没有生成任何恢复包。

### 3.5 扩展大小与总 RAM

当前 loader 的受理上限为文件 65,536 B、BSS 16,384 B、1024 个 8 B 重定位，最大申请为 81,920 B。没有重定位和额外区时，代码最多为 65,376 B；实际表、只读数据和重定位都从文件上限中扣。完整受信扩展尚未链接，不能把 A 的若干模块相加当成 B 扩展的真实尺寸。

完整 resident root 至少再占扩展 BSS 的 512 B。allocator 元数据、未拆分尾块、UI、loader 工作区、DAT 和原厂分配者还要另扣。A 的 DAT image+BSS 上限为 192 KiB，与 B 的 80 KiB 最大申请合计 272 KiB，已超过主堆 256 KiB，二者不能同时取上限。

设计基准 gen 123 的文件+BSS 为 62,676+9,884=72,560 B；它与最大 B 申请合计 154,480 B，只说明名义总量未超过配置容量，不证明开机时可分配。失败时不启用扩展，不能挤占原厂已用区。

### 3.6 跨任务准入原则

B 与“跨任务准入不依赖 DAT 自己 busy 位”兼容。UI safety、actor 状态、grant/revoke、代次和完成判定属于固定摘要批准的常驻级扩展；它在 DAT 被调用前执法，并能在 DAT 不可用时处理撤回。

窗口现已实现的是受信代码 pin、嵌套入口和返回后检查。嵌套调用仍进入受信安全层，未用一个 DAT busy 位阻挡安全处理。这不代表 task 8 授予、全拍摄准入、USB 或媒体门禁已经实现；完整扩展未产出，这些能力保持关闭。两层代码共享 CPU 地址空间，本轮没有证明硬件隔离；“受信常驻级”是批准身份、接口与生命周期合同，不是执行地点自动提供的权限。

## 4. 对比与推荐

| 维度 | A，全部窗口常驻 | B，受信扩展 |
| --- | --- | --- |
| 空间。 | 当前差 5,668 B，安全层本身已超过名义预算。 | 最小窗口余 736 B；RAM 和完整扩展另计，未来 probe、更多 native 站点仍要扣账。 |
| 主要风险。 | 为追尺寸删掉 ticket、归属、返回检查或真实门禁；本轮未这样缩减。 | 永久内存、早期载入屏障、文件失败默认、代码生命周期与完整扩展批准链。 |
| 恢复。 | 常驻代码可不依赖 DAT 做撤回；机身缺陷仍需既定固件恢复。 | 执行前健康失败可走原厂；执行后错误先隔离和 FENCED；移走扩展后的冷启动恢复尚待验收。 |
| 实现量。 | 还需减少超过 5.5 KiB，同时闭合现有未知 native 协议。 | 增加第二个可执行封装、pin 链和启动/内存合同；完整常驻逻辑仍要实现，不能只搬目录。 |
| 后续代码余地。 | 200 B 保留区不可用，当前无可接受空间。 | 常驻级实现不再受 7.6 KiB 代码总量限制；736 B 仍约束固定窗口机制，64 KiB 文件和总 RAM 约束扩展。 |

推荐把 B 作为下一轮实现方向，先解决内存归属与启动时序。当前主堆 loader 是已链接的尺寸原型，不能据此宣布已找到永久 RAM。若不能证明所有重建都尊重代码 pin，就应转向明确扣减原厂容量的预留区，并重新链接核算。A 保留为失败基线和安全语义参考。

| 后续任务 | B 下的影响与不变的验收义务 |
| --- | --- |
| W1。 | DAT 信封与 loader 进入完整受信扩展；窗口自身的扩展信任链独立。仍须证明候选、EOF、close、重定位和错误所有权。 |
| W2。 | 保留 36 槽，另有已编译的启动候选 wrapper；逐个闭合真实 native ABI、重放和拒绝返回。完整物理点数仍未知。 |
| W3。 | ticket、reader、withdraw 在受信扩展；永久代码和快照寿命要同时成立。固定应急路径只兜有限故障。 |
| W4。 | DAT 重新链接到 v4 shim，host 服务地址位于受信 RAM；绑定应覆盖 window 与受信扩展身份。不能沿用 A root 地址语义或只 rebind 头。 |
| W5。 | 系统准入、授予、完成与撤销由受信扩展执行；所有 native actor 仍需进入同一合同，DAT busy 不替代它。 |
| W6。 | 先证明扩展在首个 hook 和参数构造前可用，正常启动屏障与更新路径分离；文件失败走已验证默认。 |
| W7。 | capture/JPEG pin、槽代次、DMA/cache 和 RAW 默认禁令不减少；代码、旁表和工作区一起扣 RAM。 |
| W8。 | render reader 与视图生命周期仍要闭合；没有证明时能力为 0。 |
| W9。 | 最终 body、受信扩展和 DAT 三者冻结身份，做缺失/损坏/错 pin、启动、生命周期、恢复及最终包验收。W0 的 B 窗口通过不能代替这些验收。 |

## 5. 验证、复跑与交付

| 本轮检查 | 结果及限制 |
| --- | --- |
| 卷、工具链、原始输入和 r1 副本。 | APFS、指定 UUID、可写；68 项登记输入未变，135 个 r1 副本未变。补录输入的登记时间单列，未冒充任务开始时冻结。 |
| A 严格链接与模块账。 | FAIL_SIZE，返回 1；仅保留诊断 ELF。 |
| A 主机与 M32R。 | ASan/UBSan 通过；112 项有限 hook 用例通过。native/DAT 替身和生产地址诊断 ELF 的边界分开记录。 |
| B 严格链接。 | PASS_SIZE_MINIMAL_WINDOW，返回 0；完整 gated 路径保留，平台权限和批准 pin 均为 0。 |
| B 主机。 | ASan/UBSan 通过，1,547 次 CHECK。19 个独立 SHA 向量、头/重定位、EOF、close、scope 失效锁存、隔离和嵌套 pin。native 与扩展入口均为替身。 |
| B M32R。 | 22 项通过：目标默认拒绝 1、启动 wrapper 1、实际 SHA 7、原厂 allocator 合同及重建反例 2、原七处重放 7、应急续程 4。无设备、trap 或 native 透传。 |
| 完整受信扩展、永久 RAM、全局启动屏障。 | OPEN，未用主机或静态结果替代。 |
| 镜像、卡、相机和物理恢复。 | NOT_RUN。 |

主机和机器用例分别见 [host-tests.json](host-tests.json)、[machine-tests.json](machine-tests.json)、[arch-b-host-tests.json](arch-b-host-tests.json)、[arch-b-machine-tests.json](arch-b-machine-tests.json)。测试驱动、编译源和最终 ELF 身份均由 [r2_evidence.py](r2_evidence.py) 再核对，拒绝旧驱动或旧产物结果。

从仓库根复跑；A builder 返回 1 是本轮预期的真实尺寸失败，不应改成成功：

```sh
/usr/bin/python3 -I -B firmware/resident_v4/build.py
/usr/bin/python3 -I -B firmware/resident_v4/test_host.py
/usr/bin/python3 -I -B firmware/resident_v4/test_machine.py
/usr/bin/python3 -I -B firmware/resident_v4/arch_b/build.py
/usr/bin/python3 -I -B firmware/resident_v4/arch_b/test_host.py
/usr/bin/python3 -I -B firmware/resident_v4/arch_b/test_machine.py
/usr/bin/python3 -I -B research/body_v4_w0/r2_evidence.py collect
/usr/bin/python3 -I -B research/body_v4_w0/r2_evidence.py seal
/usr/bin/python3 -I -B research/body_v4_w0/r2_evidence.py verify
```

[SHA256SUMS](SHA256SUMS) 覆盖两个授权目录的交付文件与 `local/` 证据，路径以仓库根为基准，不含清单自身。复跑会更新日志和时间字段，之后要重新 seal。清单和验证通过证明的是本轮文件身份及所列编译、静态、主机和指令级范围。
