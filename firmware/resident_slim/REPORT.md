# resident-slim 本地实现与验收报告

主 lease 已按本次头部声明的文件与 BSS 大小申请，默认小夹具从 88836 B 降到 14420 B。常驻层通过严格链接：代码与只读数据 7784 B，root 256 B，总占用 8040 B，8340 B 窗口余 300 B，达到至少 300 B 的要求。服务层已移入引擎库，单独实链 9876 B。PASS_HOST checks=61352 sanitizer=ASan+UBSan transport=mock engine=mock native_execution=0。

这是交叉链接、静态审计和主机故障注入的结果。`firmware_ready=false`、`native_m32r_execution=false`、`camera_acceptance=false`。没有生成机身映像、固件更新包、可上卡容器，也没有接触相机或存储卡。

## 已核实的体积与布局

测量使用 `resident_impl/build.py` 的 M32R GCC、ld、objdump 与 `-Os` 等选项。C 使用 medium model，原生桥使用原有 large model。常驻层没有使用 LTO，也没有扩大链接窗口。服务库另加 `-fpic -fvisibility=hidden`，供引擎合链。

| 常驻对象或区域 | 链接后字节数 |
| --- | --- |
| hooks.o | 1292 |
| linked_hooks.o | 824 |
| resident.o | 1280 |
| loader.o | 2095 |
| shared.o | 732 |
| runtime.o | 152 |
| validate_envelope.inc.o | 1184 |
| bridges.o | 144 |
| trust.o | 80 |
| 链接对齐 | 1 |
| 常驻代码和只读数据 | 7784 |
| root，含 12 B pins | 256 |
| 总占用 | 8040 |
| 窗口余量 | 300 |

代码区从 `0x2005276c` 到 `0x200545d4`，终点不包含在代码区内。root 位于 `0x20054700`，窗口终点仍为 `0x20054800`。`.root` 是 244 B NOBITS，`.root_pins` 是 12 B 只读 PROGBITS。`rv_reset()` 只清前 244 B。

相对本轮修改前的 7780 B payload，净增 4 B。动态 span 检查使 `shared.o` 增加 32 B；共用的候选清理、一次清零 BSS/对齐/state/UI、紧凑通知表与代次复制抵消了读取头部和再打开的成本。generation、source_bytes、entry_offset 的诊断填充移入服务库，取自已接纳的完整头部；值与布局均保持。M32R 重定位改用 gate 已证明 4 B 对齐的大端 word store，主机仍按大端逐字节写。没有删减本任务要求保留的 hook 或校验。

| 引擎服务库对象 | 链接后字节数 |
| --- | --- |
| 01-api.o | 1084 |
| 02-shared.o | 1040 |
| 03-runtime.o | 84 |
| 05-bridges.o | 368 |
| 00-services.o | 7202 |
| 04-crc.o | 96 |
| 链接对齐 | 2 |
| 服务库合计 | 9876 |

服务库测量包含 16 项服务描述表、原生桥、独立的 root 操作、CRC、内存函数、上下文准备，以及 `es_grain_commit`。`rv_service`、`rv_api`、`rv_call` 和 `rv_unit` 都不在常驻 ELF 中。常驻桥只保留 open、read、close、alloc、free、cache 与 IRQ 操作。

服务库的内存、CRC 与 root helper 使用 `es_*` 符号，避免与 core 的 `memcpy`、`memset` 或 CRC 实现重名。归档使用确定性的 GNU ar 格式，由现有工具链的 ld 实际读取并链接。没有安装新工具。库内有 1 个需要容器处理的 32 bit 指针单元。`local/engine-services/relocations.json` 同时保存全部链接重定位和需要容器重定位的单元。链接到 `0x21004000+256` 后，归一化这些单元，全部代码字节与零基址版本相同。

## 已核实的上限与主堆占用

上限仍为 64、48、80 KiB，只用于兜底检查。`resident.h` 定义运行时常量，以及 `rv_image_span()`、`rv_block_bytes()` 的实际分配公式。

| 常量 | 字节数 | 使用处 |
| --- | --- | --- |
| RV_MAX_FILE | 65536 | rv_header 拒绝超限声明；loader 按接纳的实际长度读取；STORAGE 两类对象的读取上限 |
| RV_MAX_CODE | 49152 | validate_envelope.inc.c/rv_validate |
| RV_MAX_IMAGE | 81920 | rv_header 的 image+BSS 检查，不作为实际预留长度 |
| RV_MAX_LEASE | 65536 | LEASE alloc；RvPrivateContext.lease_max_bytes |
| RV_STATE_BYTES | 6144 | 通用引擎私有 state 区 |
| RV_UI_CAPACITY | 256 | 独立 UI state 预留区 |
| RV_SESSION_BYTES | 516 | 按 4 B 对齐后的 RvSession 大小 |
| RV_BLOCK_OVERHEAD | 6916 | RvSession + state + UI 的固定开销 |
| RV_MIN_BLOCK_BYTES | 7172 | rv_session 读取 lease[0].length 后的最小合理 span |
| RV_MAX_BLOCK_BYTES | 88836 | rv_session 的最大合理 span，不传给 alloc 作为固定大小 |

`build.py` 在 `local/trust.json` 写同一组策略元数据，`engine_services/library.ld` 对独立服务库使用 49152 B 链接兜底。`verify.py` 对交叉编译得到的常量检查确切值，防止只改报告或元数据。

实际传给 `rv_native_alloc()` 的字节数为：

```text
align4(sizeof(RvSession)) + align4(header.file_bytes + header.bss_bytes)
  + RV_STATE_BYTES + RV_UI_CAPACITY
= 516 + align4(file_bytes + bss_bytes) + 6144 + 256
= 6916 + align4(file_bytes + bss_bytes)
```

`align4(n)=(n+3)&~3`，有效头部先保证 file≤65536、file+BSS≤81920，再做加法与对齐。Session 位于块首，文件紧接 Session，BSS 紧接文件，0–3 B 对齐填充后是 state，再后是 UI。`lease[0].length` 保存本次确切申请长度。`rv_session()` 先核对 root/代次并验证 516 B Session span，再读取长度，检查 7172–88836 B 范围和完整动态 span；不再用固定 88836 B 检查小块。

本轮小夹具是 7440 B 文件、64 B BSS，共申请 14420 B；BSS 为 65 B 时申请 14424 B，额外 3 B 对齐也清零。65536 B 文件、BSS 为 0 时申请 72452 B；只有 image+BSS 确实达到 81920 B 时才申请 88836 B。分配返回 0 时不发布任何引擎入口，收尾后照常走原厂。

P2 的 65536 B 见证仍是独立 LEASE 申请，通用上下文 `lease_max_bytes=65536`。小夹具主块加见证的请求总和为 79956 B；64 KiB 文件、BSS 0 时为 137988 B；最坏值为 154372 B。这些数值不含分配器头部与碎片，能否与原厂长期共用 256 KiB 主堆仍须机上 P2 验证。

主机测试接受 65536 B 文件与 16384 B BSS，拒绝再多 1 B BSS；接受 49152 B 代码并跑完整 loader 路径，拒绝多 4 B 的代码。文件多 1 B 会在有界 EOF 探测时拒绝。LEASE 接受 65536 B，65537 B 在调用原生分配器前拒绝。

STORAGE 的两个对象类别都采用 65536 B 读取兜底。到达上限后只允许 1 B EOF 探测。返回 0 表示 EOF；返回 1 表示对象超长，报告 `RV_RANGE`。同一 token 在已确认 EOF 或超长后，不再发出原生 read。close 仍可使用一次。小对象的格式长度由引擎校验。

## 已核实的来源选择

1. 先读 `/ATA1/GXRCE.DAT` 的 256 B 头，头有效才按实际大小分配并重开读全文。完整外层 gate 通过即采用，即使它的 build 比 IROM 低，也不读 IROM 头。
2. 卡不可用或 gate 失败时，只读两个 IROM 文件的 256 B 头。头部长度、版本、CRC 和身份有效者参与排序。build 较高者先，同代选 `GXRCE0.DAT`。
3. 对所选 IROM 做完整读取和 gate。完整校验失败后试另一份，各最多一次。没有同代逐字节比较，没有同代 CRC 冲突裁决。
4. 外层 gate 保留完整 CRC、机身与常驻身份、段布局、入口范围和内部重定位检查。目录、配方、stock pin 与数据语义仍由引擎纯 init 验证。所有失败路径撤 UI，并收尾仍能确认有效的 fd 与 lease。

`probe()` 在栈上读满 256 B 头；`read_one()` 在返回前关闭该 fd，再检查头部 CRC、build/ABI/body ID 与长度上限。只有头部已接纳且 fd 已关闭，loader 才申请主块。随后重新 open 同一路径，从文件开头读取声明的 file_bytes，并额外向栈上 1 B 缓冲读一次确认 EOF。文件少于声明、超过声明、read/close 出错都拒绝。成功 open 的每条路径都执行一次 close；open 失败没有 fd 可关。分配失败时头部 fd 已关闭；全文 open 失败时释放新主块。任何时刻 loader 最多持有一个 fd，分配器调用期间没有 fd，探测与全文阶段不共享一个悬挂 fd。

重开后对完整头部与全文重新 gate，声明长度必须等于本次实际读取长度，build 和 BSS 必须等于用来定大小的头部。即便重开的文件重新计算了有效 CRC，只要 BSS 改变也拒绝，避免按小块分配却按大 BSS 清零。候选全文失败后先按 free 标志 1→0 确认主块释放，再为另一来源按它自己的大小申请；free 拒绝时停止加载并回原厂。整个加载尝试只保留一个主 lease token，回退不重复递增它。完整图像与入口已接纳且原 Session 有效的重绑路径不再分配或打开文件。

这里的机身身份检查是文件头中的 body SHA256 与常驻编入的官方机身摘要相等。补丁生成器还检查官方 `ilaunch3` 的完整摘要及每个 hook 的原字节。本稿没有在相机 RAM 中重新计算整份机身 SHA256。

## 已核实的 root 字段合同

全部偏移相对 `RV_ROOT=0x20054700`。多字节值在目标上使用 M32R 大端。`local/target-layout.json` 由目标 GCC 的 `sizeof` 和 `offsetof` 编译结果生成，包含 root、私有上下文和整个 RvSession 的全部字段。

| 字段 | 偏移 | 字节数 | 含义 |
| --- | --- | --- | --- |
| magic | 0 | 4 | RV_ROOT_MAGIC=0x52565331 |
| version | 4 | 1 | root 版本 1 |
| state | 5 | 1 | RvState |
| inflight | 6 | 1 | 当前引擎入口计数 |
| grain | 7 | 1 | 0 关闭，0x80 与 mode 的组合为已提交值 |
| epoch | 8 | 48 | 12 个 u32，顺序为 RvEpoch |
| block | 56 | 4 | 主 lease 的地址，也是 RvSession 地址 |
| inverse | 60 | 4 | block 的按位反码 |
| lease | 64 | 4 | 主 lease 的 token |
| boot_epoch | 68 | 4 | 主 lease 接纳时的 boot 代次 |
| heap_epoch | 72 | 4 | 主 lease 接纳时的 heap 代次 |
| next_token | 76 | 4 | 全会话 token 计数器，不回绕 |
| rx | 80 | 4 | 单元接收序号，奇数表示变化中 |
| event_head | 84 | 4 | 最新事件序号 |
| dropped | 88 | 4 | 覆盖的事件数量 |
| fault | 92 | 4 | 有符号 RV 错误码 |
| post | 96 | 16 | H17、H18、H20、H22 的原 LR，各 4 B |
| ui_restore | 112 | 32 | 8 个 u32，见下方字段合同 |
| flags | 144 | 4 | STOP=1、SD=2、UNCERTAIN=4、BUSY=8、OWNER=16 |
| events | 148 | 96 | 8 项，每项 hook:u16、phase:u16、a:u32、b:u32 |
| pins | 244 | 12 | 固定只读的三个 u32 |

`ui_restore[0..7]` 依次为原生栈数组、栈项数量、完整 tag word、原 top state、扩展拥有的 state、view epoch、扩展标签表、扩展 details。`rv_ui_abort()` 只在当前引用仍匹配这些所有权记录时恢复原厂标签、数量、cursor 和 top state。该函数不查 session，不读 heap 中的 UI state，不调用引擎或原生 UI 函数。

三个 pin 的固定地址分别为 `0x200547f4`、`0x200547f8`、`0x200547fc`，值依次是 50mm `df2bcaf5`、28mm `6700e6ff`、Mount `1b3c7000`。库内 QUERY op3 按模块号 1..3 返回 `reply.detail`。

为容纳 256 B root，root 保存主 lease 的地址、反码、token、boot 和 heap 代次。6 个完整 lease 记录位于 `root.block + offsetof(RvSession,leases)`，当前偏移 160，每项 20 B；第 0 项镜像主 lease，length 为实际分配字节数，另 5 项供引擎申请。任何 boot 或 heap 失效都会先撤 root 中的访问资格，库随后不得读或 free 这些旧记录。这是通过 root 找到的固定记录区，并非把全部辅助 lease 塞进 root。本轮未改变 root、RvSession 或通用上下文的字段布局。

事件内部每项 12 B，省去可由 `event_head` 推导的 sequence。EVENTS snapshot 仍输出原 ABI 的 16 B `RvEvent`，保留序号、覆盖计数和缺口。环容量为 8。

## 已核实的引擎服务表与通用上下文

`RvRequest`、`RvReply`、服务编号和间接结构的 wire 布局与起点相同。`abi.h` 只改 root 地址、root 字节数和 ring count，因此 ABI 文件摘要改变；新引擎必须使用 `local/trust.json` 的新 build 与 ABI ID。

常驻层对每个入口都传 `api=NULL`，`context=root.lease`，`args[0]=args[1]=root.lease`，并填写当前入口代次。`args[10..11]` 始终指向同一份 120 B `RvPrivateContext`，地址为 `root.block+40`。bootstrap 的入口表输出改从上下文中的 `entries_address/entries_bytes` 取得。

引擎 bootstrap、init 和其它入口的 adapter 均先调用库，取得本图像内的服务表：

```c
#include "engine_services/engine_services.h"

const RvPrivateContext *private_context =
	(const RvPrivateContext *)(uintptr_t)request->args[10];
const RvApi *services = rv_services_init(private_context);
/* services == NULL 时由 adapter 返回 RV_FAULT，不进入 core 或探针。 */
```

首次 bootstrap 时，这份上下文已清零。库根据常驻接纳的 RvSession 填入 header、root/session 范围、image/code、state、UI 预留区、入口表和 nonce，并从完整图像头填入 Session 的 generation、entry_offset、source_bytes。state 地址为 `image_address+align4(image_bytes+bss_bytes)`，UI 地址为 `state_address+6144`；两者不再依赖最大 image 预留。库随后验证范围与当前单元缓存。后续入口验证并复用原上下文，不重新分配 state。bootstrap 和纯 init 仍分别通过入口表和 reply 合同受理，READY 在纯 init 成功后发布。

| 字段组 | 本稿合同 |
| --- | --- |
| state_address/state_bytes/state_lease | 6144 B 清零私有区，所有入口同址，由主 lease 持有 |
| image_address/image_bytes/image_lease | 实际接纳文件的区域；image_bss_bytes 单列 BSS 长度 |
| code_address/code_bytes | gate 接纳的准确代码段范围 |
| nonce | 非零的本会话 token，重绑不改，heap 换代后新建会话会改变 |
| ui_state_address/ui_state_capacity/ui_state_bytes | 预留 256 B；未核实原生 renderer 布局前 bytes=0 |
| entries_address/entries_bytes | 指向 RvEngineEntries 的 40 B bootstrap 输出区 |
| input_fields/input_sequence/input[4] | H10 按值复制原 r11 和入口 SP+28/+32/+36 三个 word；位图为 0xf |
| lease_max_bytes | 65536，P2 可据此请求 64 KiB 见证；集成时再改探针 |
| grain_address/grain_bytes | 本稿保留为零；引擎通过库的 es_grain_commit 发布 root 中的颗粒值 |

H10 的输入序号用于区分新观察和后续入口继续持有的旧观察。本稿没有把这些原始值解释成物理键边沿，也没有把请求 post 解释成帧完成。

引擎合链时，把 `local/engine-services/libgxr_services.a` 放在引用它的对象之后。最终 linker 需要合入 `.data.rel.ro*` 和 `.got*`，并从最终 ELF 重新生成容器重定位。独立 linkcheck 的单元偏移不能直接复制到 core 与 panel 的合链结果。主机测试中的 engine 是 double，现有 core、panel 和 probes 的 adapter 尚未由本 worker 修改。

## 已核实的六项修正与 free 判据

| 问题 | 当前行为 | 主机证据 |
| --- | --- | --- |
| LEASE free 冒报成功 | 先检查可信 header，再调用 void native free，只有标志 1 变 0 才返回 OK；失败保留 token | 静默拒绝时 IO、detail=0x101；成功时 OK、detail=0x100；再次 free 被拒绝 |
| snapshot 缺 actual | EPOCHS=60、UNIT=36、SD_ID=16、SETTINGS=24 | 对每个成功回复检查确切 actual 及内容 |
| 到上限不能验 EOF | 64 KiB 后允许额外 1 B，超长返回 RANGE | 短读累计恰好 65536，分别测试 EOF 与额外字节、后续不重读和一次 close |
| inspect 参数冲突 | args[8] 选择目标 token；args[1] 只验证输出缓冲 lease | 描述符写在主 state，检查另一独立 lease；交换输出 lease 时拒绝 |
| current 拒绝新代次 | 只读观察核对会话与 boot/heap 身份，允许取新的 link/unit/view/S；修改操作仍核对完整代次 | 旧绑定成功读新快照；旧 boot 或 heap 拒绝；旧绑定的 alloc 拒绝 |
| 各入口缺同一上下文 | 每次传同一通用 RvPrivateContext，库在图像内提供服务表 | 八个运行入口保持 state/code/UI/nonce；重绑保持，heap 换代新建 |

free 的 header 校验对应 `p-12` 的 next、`p-8` 的分配标志字节、`p-4` 的 size。判据还检查 4 B 对齐、堆边界、size 大于 0 且小于 `*0x200c0dc4`、next 为 0。调用后先检查 boot/heap 代次，再读标志，避免读取已经失效的 header。UI 正在引用或在途计数大于 1 时拒绝 free。`native_result` 不承载 free 成败，库不读取原生 r0 返回值。

另补了 UNIT native 返回后的身份核对，防止 heap 通知后写入旧输出缓冲；CACHE 校验受理区间，不把代码字节当成带 header 的描述符。

## 已核实的 hook 与原厂续接

一级 H01–H12、H15–H22 全部保留，其中 H03、H04 为默认原厂数据点。二级 H13、H14、H23、H25、H31、H32 只增加相应代次并记录一条事件，不撤 UI、不停颗粒、不查 heap、不调用引擎。其影响在下一个 H01 安全菜单入口触发重绑，由引擎处理。三级 H24、H26–H30、H33–H37 删除。

启用点共 26 个，包括 24 个代码 hook 和 2 个原厂数据点。补丁清单保留全部 37 行，逐行记录地址、原字节、替换字节、是否启用及 `installable=false`。原字节和替换字节仅保存在 `local/`。24 个代码桩的原指令重放及续接分支都与最终 ELF 对照，补丁分支也重新解码并核对目标符号。

引擎文件不存在、容器错误、入口越界、返回头错误或主 lease 失效时，主机测试检查菜单 frame 保持默认分支，原厂 7 项标签与 top state 恢复。独立 ui_abort 在 heap 不可用时仍能撤自己的引用，外部接管的 tag 不被覆盖。H09 保留纯 resident 颗粒门，不调用 heap 代码或服务。

## 已核实的主机检查与栈

15 组 ASan、UBSan 检查全部通过。61345 是各组检查计数之和，包含短读循环内检查，不代表同样数量的独立故障场景。完整输出在 `local/host-checks.log`，编译、链接、环境和退出码在 `local/host-commands.json`。

| 组 | 检查计数 |
| --- | --- |
| gate | 275 |
| limits | 7319 |
| loader_faults | 5997 |
| source_selection | 5783 |
| integrated_pin | 2453 |
| ui_abort | 5 |
| grain | 611 |
| services_base | 502 |
| hook_dispatch | 1052 |
| services_six_fixes | 1525 |
| storage_eof_64k | 16424 |
| private_context | 1095 |
| tier2 | 3030 |
| factory_fallback | 1508 |
| dynamic_allocation | 13766 |

测试保留了起点的截断、超长、短读、read/close 错误、返回长度越界、CRC/身份/重定位错误、分配失败、bootstrap/纯 init 失败，以及 alloc/open/read/close/cache/返回边界的通知注入。新增用例覆盖卡优先、IROM 同代选 0、高 build 完整损坏后的回退、六项修正、64 KiB lease、二级 hook 无额外副作用、root pin 复位保留和原厂回退。

本轮动态分配逐例证据在 `local/dynamic-allocation.json`，由测试实际观察值生成；对应原始行在 `local/host-checks.log`。下表的 alloc/free 只计成功的原生分配与释放；分配失败一行发生过一次精确大小的申请，但 alloc 计数为 0。

| 场景 | 实际请求字节数 | alloc/free | 结果 | open/close |
| --- | --- | --- | --- | --- |
| 小文件 | 14420 | 1/0 | READY | 2/2 |
| BSS 65 B 与对齐 | 14424 | 1/0 | READY | 2/2 |
| BSS 为 0 | 14356 | 1/0 | READY | 2/2 |
| 文件长度未对齐 | 14360 | 1/0 | READY | 2/2 |
| 实际少 1 B | 14420 | 1/1 | 拒绝，保留原厂 | 2/2 |
| 实际多 1 B | 14420 | 1/1 | 拒绝，保留原厂 | 2/2 |
| 声明多 4 B | 14424 | 1/1 | 拒绝，保留原厂 | 2/2 |
| 声明文件超过 64 KiB | 0 | 0/0 | 拒绝，保留原厂 | 1/1 |
| 声明 image+BSS 超过 80 KiB | 0 | 0/0 | 拒绝，保留原厂 | 1/1 |
| 主堆分配失败 | 14420 | 0/0 | 拒绝，保留原厂 | 1/1 |
| 全文 reopen 失败 | 14420 | 1/1 | 拒绝，保留原厂 | 1/1 |
| reopen 后 BSS 增大 | 14420 | 1/1 | 拒绝，保留原厂 | 2/2 |
| 卡完整损坏后回退 IROM0 | 14420 → 14420 | 2/1 | READY | 4/4 |
| 较大 IROM1 损坏后回退 IROM0 | 14632 → 14420 | 2/1 | READY | 4/4 |
| 64 KiB 文件、BSS 0 | 72452 | 1/0 | READY | 2/2 |
| 64 KiB 文件、BSS 16 KiB | 88836 | 1/0 | READY | 2/2 |

reopen BSS 改变的用例先声明 64 B，重开后改成 74480 B 并重算有效 CRC，仍在清零前拒绝。所有这些用例都断言 alloc 时无活动 fd、header 已关闭、同时最多一个 fd、最终 open/close 配对。主机模拟堆先全部 ASan poison，仅对实际申请的 header 与内容解 poison；释放后再次 poison 内容，header 保留以检查 free 标志。因此小块越界清零、主 state/UI 放在旧最大偏移处，或释放后读旧内容，都会被实际边界检查捕获。

编译器 `.su` 与汇总均保存在 `local/`。主要静态帧如下。

| 区域 | 函数 | 静态帧 B |
| --- | --- | --- |
| resident | rv_load | 344 |
| resident | probe | 276 |
| resident | rv_validate | 144 |
| resident | rv_hook_observe | 120 |
| resident | read_one | 80 |
| resident | rv_engine | 44 |
| engine_services | rv_service | 112 |
| engine_services | rv_unit | 32 |
| engine_services | es_free_checked | 28 |
| engine_services | es_record | 24 |
| engine_services | path | 20 |
| engine_services | rv_services_init | 20 |

inline hook 保存现场 68 B，原生桥保存 28 B。读头路径的已知帧叠加为 916 B，全文读取为 640 B，头部 gate 为 824 B，全文 gate 为 692 B，loader 进入引擎前的已知部分为 580 B。新增头部缓冲仅占栈，不增加常驻 root 或长期主堆占用。原生文件层、真实引擎、native 回调嵌套的栈用量未知，这些数值不是整条路径的安全上界。

## 推断与未知

- 按用户提供的 core 与 panel 合并 32912 B 加本库 9876 B，算术和为 42788 B，低于 49152 B。这个和没有考虑最终 GC、LTO、共享函数和容器数据，不能替代三者实链或 65536 B 文件验收。
- 主 lease 已按实际需要申请；与 P2 见证同时持有时的真实分配成功率、长期占用、碎片和恢复后保留未知。主机 65536 B 成功只证明库的合同与边界，机上 P2 尚未运行。
- UI 区域已留出，`ui_state_bytes=0` 表示完整 renderer 尚未准备。真实九行面板、标签引用寿命、按键语义、刷新完成与原生任务阻塞上限由集成验收。
- root 全部丢失后的全局唯一 nonce 没有独立持久见证。H15 的 warm/cold 证明、H17/H18 段 0/1 覆盖时的独立见证、在途 heap 代码面对破坏性覆盖的生存，以及真实 M32R 的 PSW/寄存器行为仍无设备证据。本稿保留一级 hook 接点与默认重放，不把这些旧缺口报告为已关闭。
- IROM 安装、readback 登记和 `.DAT` 改名 `.OK` 属于引擎事务，本稿没有执行。库保留起点的文件写能力 gate，`mark_delivered` 仍拒绝；真实 installer 若只依赖服务表，还需在引擎集成时闭合该合同。原生文件桥已在引擎库中，常驻层不会安装或改名。
- 原始 pin 和数据语义由真实引擎纯 init 检查。这里的 host double 验证了分层拒绝路径，没有证明 core、panel 与 probes 已兼容新 root、120 B ingress、inspect 参数或新服务表。
- 外部 `card_container_v2` 的 pack 与 gate 常量未由本任务改动，集成时仍需与 64/48/80 KiB 策略统一。当前 include 的旧 `card_container/gxrce.h` 只提供类型，运行时 gate 使用本目录的 `RV_MAX_*`。

## 产出文件与复核命令

| 文件 | 用途 |
| --- | --- |
| resident.c、loader.c、hooks.c、shared.c、resident.h | 瘦身常驻逻辑、固定共享布局与独立回退 |
| abi.h、resident.ld、bridges.S、runtime.c、validate_envelope.inc.c | 服务 wire、严格窗口、最小桥、运行支持与外层 gate |
| engine_services/ | 引擎内服务库源码、公开头与独立 linkcheck 脚本 |
| build.py、verify.py、host_checks.c、host_slim_checks.inc.c、make_fixture.py | 构建、静态审计、主机故障注入和不可执行夹具 |
| report.py、size_audit.py、checksums.py、SHA256SUMS | 从实测数据生成报告、map 复核与全文件哈希 |
| local/build/resident.elf、local/build/resident.map | 严格窗口的最终 ELF 与 map |
| local/engine-services/libgxr_services.a、services-linkcheck.elf、services.map | 自包含引擎库、独立实链 ELF 与 map |
| local/patch-manifest.json、local/hooks.json | 全部 37 项 hook 的补丁与只读起点元数据 |
| local/verification.json、size.json、stack.json、target-layout.json | 验收状态、字节分解、栈与目标字段布局 |
| local/dynamic-allocation.json | 16 个动态分配场景的实际请求、分配/释放与 fd 计数 |
| local/trust.json、inputs.json、commands.json、host-commands.json | 策略、身份、只读输入摘要和命令证据 |
| local/failures.log、local/failures/、local/*constrained-link.log | 本轮迭代失败记录，保留首次超窗和余量不足的原始结果 |
| local/before-dynamic/ | 本轮动态分配修改前的源码与测量快照；不是当前交付 ELF |

所有文件写入都在本任务目录。`local/` 的忽略规则已用 `git check-ignore -v` 验证。构建记录并在验收时复核 15 个关键只读输入摘要。`resident_impl`、`resident_v2`、官方固件和其它 worker 目录作为只读输入使用。没有 commit 或 push。

从项目根目录复核：

```bash
cd /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh
/usr/bin/python3 -I -B firmware/resident_slim/verify.py
/usr/bin/python3 -I -B firmware/resident_slim/report.py
/usr/bin/python3 -I -B firmware/resident_slim/checksums.py
/usr/bin/python3 -I -B firmware/resident_slim/checksums.py --verify
git check-ignore -v firmware/resident_slim/local/check
```

`verify.py` 应返回 0，并打印 `PASS margin=300`。目标链路工具位于既有 `research/tooling_m32r*` 目录。Python 使用系统 `/usr/bin/python3`，没有安装包。

最终产物 SHA256：

```text
36e65caf5136d65cab35154a950665b9abb61f0afbb2cece75b36273c211dafd  local/build/resident.elf
3306045a410ee26c4533d552bcc4d30a2c298baa98c38a1a35c3a5ca0492d433  local/engine-services/services-linkcheck.elf
eb41d272844b0204eedf80744b06c6b04da9b053351b82f5af07e0c047cefb5c  local/engine-services/libgxr_services.a
```

当前 resident build ID 为 `9a9aa6c9e71cd941035750e035d07be8f721dfd3b830bf6ba2b1b117d6b52059`，ABI ID 为 `f9bf604799edf1d647e3b345967ffc5a`。全部交付文件的摘要由 `SHA256SUMS` 绑定，索引本身不自包含。
