不可以。当前 full-r2 不放行；临时 lease 释放失败被忽略，且只读 open 的歧义尚不能保证保留有效旧副本。

日期：2026-10-24。审查对象是用户自己的 GXR，机身官方 1.51，以及官方 1.51 的 GR LENS A12 50mm、MOUNT A12。28mm 只增加主机覆盖。本轮只审容器内引擎和数据，已安装的 v3.2 常驻层按冻结基线核对。

指定文件为 `firmware/engine_fix_r1/local/product/candidates/full-r2/GXRCE.DAT`，59,328 B，SHA-256 为 `6ba63d294e86a591e5752d7c237cf7b88aeda1f3b0b51064439709b5feed9cc0`。本报告的拒绝结论只针对这个摘要。没有修改产品源码或生成替代容器。

## 1. 按严重度列问题

### F01 · P1，阻断：新增临时 lease 释放失败后，调用方仍按成功继续

已核实：[adapter.c](../../firmware/engine_fix_r1/containers/product/adapter.c) 第 94–97 行的 `release()` 返回 `void`，直接丢弃 `pn_call(RV_LEASE, 2)` 的结果。新增加的 `preload_gxts()` 第 174–175 行释放后照常设置 `n.tweaks_loaded=1`，`a4_finish()` 第 198–207 行也在释放后继续按原保存结果更新缓存和关闭面板。

服务自身的判断正确。[services.c](../../firmware/engine_fix_r1/engine_services/services.c) 第 292–294 行只在 `rv_free_checked()==RV_OK` 时清空 lease token。[shared.c](../../firmware/resident_v32/resident/shared.c) 第 104–113 行先核对归属与头部，调用原生 free，再检查 `base-8` 的标志是否由 1 变成 0。失败返回 `RV_IO`。本轮指定 objdump 对实际容器 ELF 的检查也确认 `es_free_checked` 在 `0x9810` 调 free，`0x9814` 读取头部标志；`release` 的 `0x1750` 调服务后直接返回。容器引擎字节与该 ELF 全等。

独立故障注入只替换原生 free 这个边界，让一次 free 保持 live/header=1，其余引擎、服务、lease 表和常驻 C 都是真实实现。结果如下，三单元均复现。

- 预加载临时对象释放失败，菜单仍返回 `RV_CONSUMED`、root 仍为 READY、列表仍为 16 项，遗留 1 个临时 lease。
- 后续入口的 `entry_serial` 已变化，旧 token 再走真实释放服务返回 `RV_STALE=-5`，不会回收该对象。
- 连续 5 次保存各泄漏一个 lease，耗尽全部 5 个临时槽。第 6 次保存无法申请 lease，没有持久化写入，root 仍为 READY。

原始结果见 [预加载释放失败](local/logs/review-free-preload-0.log)、[连续保存](local/logs/review-free-repeat-0.log) 和 [三单元反例汇总](local/adversarial-results.json)。目标 M32R 的 `PnGxts` 为 652 B，5 份合计 3,260 B，另加分配头。64 位主机的同结构为 688 B，日志中的 688 不是相机申请量。

这证明的是注入释放失败时的代码行为，不是已经发生的相机泄漏。原生 free 在正常、有效头部下会清标志，设备出现该失败条件的频率没有测量。但任务明确要求覆盖释放失败；当前代码连服务已报告的失败也没有接住，因此这一验收项失败。

修复要求：让释放结果进入预加载、保存与安装两块 64 KiB lease 的收尾流程。失败时不得继续报成功或继续分配临时槽，应保留归属证据并停止扩展，不能盲目重试 free。若要求失败时也零泄漏，需要可证明安全的回收办法，或改成有界复用的私有工作区。修复不得释放仍被 native UI 引用的主块或快照。回归需覆盖头部保持 1、下一入口、连续保存和不能重复释放的情况。

### F02 · P2，安全论证缺口：open 返回 -1 不能授权覆盖一个未证空的正式目标

已核实：官方 open 的 -1 同时包括缺文件和其它失败。修复把它译为 `RV_UNAVAILABLE` 后，[panel_store.c](../../firmware/engine_fix_r1/containers/product/src/firmware/engine/panel/panel_store.c) 第 163–178 行的扫描不设置 `observed`。第 291–314 行的 `commit()` 在没有可见有效副本时选择 A，并跳过对未观察目标的删除检查，随后直接 `TMP → A`。GXTS 的 [gxts_io.c](../../firmware/engine_fix_r1/containers/product/src/firmware/card_container_v2/gxts_io.c) 第 58–97 行同样把这种情况作为首次保存，目标为 A。

开发方 `rv_native_rename()` double 原本就允许覆盖已存在目标。没有改动这个 double 的覆盖语义，仅让有效 A 的只读 open 返回 -1，三单元得到两个反例。

| 起点和注入 | 真实产品 C 在现有 double 上的结果 |
| --- | --- |
| IROM 只有有效 A，generation=103；卡是 full-r2，generation=104。扫描 A 时一次 open=-1。 | 把 A 当作未观察，直接覆盖 A；B 仍不存在；安装和 DAT→OK 均报告成功，旧 generation=103 副本不再保留。 |
| GXTS 只有有效 A，Cont=3，generation=1。预加载与保存扫描 A 时各一次 open=-1。 | 预加载默认 Cont=0，保存 Cont=1 时直接覆盖 A；B 仍不存在；generation 重新从 1 开始。 |

见 [隐藏引擎副本](local/logs/review-hidden-engine-0.log)、[隐藏 GXTS 副本](local/logs/review-hidden-tweak-0.log)，其余单元见 [汇总](local/adversarial-results.json)。

证据边界：上述覆盖已在项目自己的 replace-existing rename double 上发生。官方包装器 `0x200A49D8` 及其调用 `0x200A6CB8` 的字节已重新反汇编；本轮没有证明官方 rename 对“目标已存在”是否拒绝、是否覆盖、失败是否完全无副作用。因此不能把这个主机反例说成已发生的真机覆盖，也不能反过来承诺有效旧副本一定保留。此前 [IROM 研究](../irom_storage/REPORT.md) 第 41、112、197 行也明确没有给出目标已存在时的保证。

完整读回能阻止未核对的 TMP 进入正常提交，不能证明旧 A 被保留，也不能撤销已经发生的覆盖。把 -1 的最坏后果只写成“重装、默认值或本次保存失败”不完整。若 native rename 允许替换，当前代码可以丢失唯一旧副本；若它拒绝既有目标，预期会在 rename 处失败停用，但这个前提尚未闭合。

修复要求：把 open=-1 保留为“缺失或不可读”，不能作为目标确实不存在的证据。写入需要一个已证明不覆盖目标的原生操作或等价保护，并验证失败无破坏；否则在目标不能确认时停写。用现有无细分错误码的 ABI 能否同时支持空 IROM 首次安装和严格保留旧副本，需要开发方给出具体办法。至少补上隐藏有效 A/B、较新 generation、GXTS、目标已存在和 rename 失败后的字节保留用例。

## 2. 源码范围、机身和容器身份

独立逐文件比较 `resident_v32` 与 `engine_fix_r1` 的 `engine_services`、`containers/product`，共 19 个差异文件。列表和完整差异分别在 [source-differences.json](local/source-differences.json)、[source-differences.patch](local/source-differences.patch)。

- 服务差异是两个头文件路径调整，以及 storage 中只读 open(-1) 映射和 delete(-2) 特例移除。UI 服务及其准入、发布、撤回逻辑没有变化。
- adapter 改成临时 `PnGxts`、缓存微调值和错误标志、共享参数索引，并复用 core 的已验证 view。
- core 删除重复 `EngData`，CRC 改为分段累加；GXTS encode 直接写调用方输出。完整语义校验仍在 READY 前执行。
- `panel_store` 在受限删除前增加只读存在性探测；数据打包增加 Mount 八条校准。其余 Python 差异是路径、构建适配和测试覆盖。

已核对最终 layout 记录中的 29 个链接源码摘要、3 个工具摘要。没有发现新增机身常驻源码、常驻 ELF 或身份发放。独立从冻结 v3.2 源码和现有工具链重算的 build/ABI 与 ELF 相同。

| 对象 | 本轮核对值 |
| --- | --- |
| 已批准 v3.2 机身映像 | `05b46ee65f4861f2e09e9b7c519cbcc2dffb195158a40c3bb033540b36a98d8c` |
| resident ELF | `f25899258471d0652a8fef8980b9f0a83a0ca7cd4ddc6bbe8fcc337467362b58` |
| 官方机身输入 | `da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7` |
| resident build | `2eea6eb324790b035d37d33395d60880a1909b4e693414a939dee45f96bfbae7` |
| resident ABI | `9583fdd751bebc36f3af305595559643` |
| 三单元 pin | `DF2BCAF5 / 6700E6FF / 1B3C7000` |

ELF 的 7,772 B `.payload` 与批准映像对应 VA 全等，root pins 也全等。final DAT 的 80 B body/build/ABI 身份与该 ELF 全等，49,900 B 引擎段与产品 ELF 全等，头和负载 CRC 正确。基线 full 的完整摘要是 `24f420731b354de270d7d98636ee3783ff5bd2ca4b104d35f32f0373521d3c57`。详见 [artifact 检查](local/artifacts.json)。

这些检查证明磁盘上的输入保持 v3.2 身份，没有读回相机 flash。

## 3. 逐路径核对只读 open 的 -1

[services.c](../../firmware/engine_fix_r1/engine_services/services.c) 第 101 行确实只在 `op==2 && n==-1` 返回 `RV_UNAVAILABLE`。调用前仍限制固定路径、对象、owner、epoch、SD ID 和 capability。其它操作未获得缺失特例；42 个边界用例独立重跑通过。

| 调用点 | -1 被误认作缺失时的最坏结果及保护 |
| --- | --- |
| 未改的 resident loader，卡 DAT、IROM A/B 探测及全文读取。 | loader 不使用这次服务映射，仍把负 open 当失败，并尝试既有回退。全部来源不可读时回原厂。 |
| adapter 安装来源的卡 DAT open。 | 当前安装终止，DAT 保留。菜单是否继续由安装返回码决定；不能据此标记交付成功。 |
| `ps_install` 扫描 IROM A/B。 | 有效副本可能不可见，丢失 generation 和目标占用信息。读回仍完整，但保留旧副本的例外见 F02。 |
| GXTS A/B 预加载与保存重扫。 | 单副本可能被忽略、双不可见时使用默认值，`io_error_mask` 不会记录这些 open 失败。后续保存的例外见 F02。真正 read 失败仍会阻止或限制保存。 |
| 删除前探测 TMP。 | 跳过显式删除，随后 create 只针对固定 TMP。即使旧 TMP 被截断，也不会因此把它当作正式候选。 |
| 删除前探测正式目标。 | 引擎提交处会停止；GXTS 可能把 unavailable 视为已不存在，后续 rename 的保护仍需要 F02 的保证。 |
| 写后 TMP open、正式副本回读 open。 | 核对失败；TMP 未通过时不 rename，正式副本提交后的失败进入不确定状态。不能把已发生的 rename 回滚。 |
| DAT、OK 的再核对，以及安装见证 `es_storage_mark` 的直接 open。 | 必需的来源与正式副本字节比较、EOF、close、CRC 和 SD ID 不会被跳过。见证失败不会主动执行 DAT→OK；OK 已改名后的验证失败仍停用，不宣称交付成功。 |

create/read/write/close 的 -1 和 -2 都返回 I/O 类失败。rename/delete 的非零返回会设置 `RF_UNCERTAIN` 并返回 `RV_UNCERTAIN`，不再把 delete(-2) 当缺文件。写入失败不会因为这次 open 修改被翻译成成功。

已通过的写后故障包括 `install-readback-failure`、`install-readback-mismatch`、`install-readback-open`、`gxts-readback-open`、`gxts-readback-mismatch`。在这些注入点，没有把半写 TMP 发布为正式副本。真实存储掉电和共享 FAT/NAND 损坏没有在本轮模拟或测试。

## 4. 内存缩减与 F08

| 项目，单位 B | v3.2 原 full | full-r2 | 变化 |
| --- | ---: | ---: | ---: |
| 文件 | 58,160 | 59,328 | +1,168 |
| 引擎 | 50,044 | 49,900 | -144 |
| BSS | 23,576 | 11,392 | -12,184 |
| 主块请求 | 89,240 | 78,224 | -11,016 |

本轮只交叉编译了 sizeof 常量对象，没有链接固件或机身映像。目标尺寸为 session=1,104、state=6,144、UI capacity=256，overhead=7,504；`PnGxts=652`、loader work=608、UI snapshot=1,968。已批准 ELF 的 `0x20053764` 是 `add3 r4,r4,#7504`。计算与主机首次安装观测一致。

```text
主块 = 7,504 + align4(59,328 + 11,392) = 78,224 B
主块加原生头 = 78,236 B
再加 loader workspace、UI snapshot 及其头 = 80,836 B
安装期间另有两块 65,536 B 临时 lease，不能从峰值中漏掉。
```

正常路径中，新临时 lease 在预加载循环复用，读完 16 槽后释放；保存仅在绑定、读取、编码和同步 I/O 返回后释放。分配失败、预加载读取失败、保存失败用例通过，正常成功路径无临时 token 遗留，也没有观察到重复 free。释放失败另见 F01。

没有发现重新引入 review_flash_v31 F08 的代码变化。UI labels、refs、details、panel 和 state 继续使用主 lease；新 `PnGxts` 不向 native 发布 UI 地址。UI service 的非存储部分、`resident/shared.c` 与已审 v3.2 相同，仍只接受固定原生 view 数组，撤回只写两个固定 state 字段，published 主块不会释放。这个判断来自源码差异、实际 ELF 和主机路径，不扩大成真机 UI 时序压力验收。

## 5. 三单元数据和身份绑定

本轮分别编译冻结 v3.2 与 full-r2 的完整 C 校验器，验证 base、huzi、full-r2 三组 × 三单元，共 18 次通过。两个独立编译版本对 final DAT 展开 48 槽，448 B 条目、160 B GXTS 绑定以及 240 B 默认记录逐字节相同。

| 银行 | 逐槽来源核对 |
| --- | --- |
| 50mm 01/02 | 与原 Stage2l `DEEPTBL0.DAT` 的对应条目全等。 |
| 50mm 05/06 | 与 v6 的原 05/06 全等。 |
| 50mm 07/08 | 与 Leica Chrome / VIVID 源条目按目标 slot、49 B 身份重绑后全等。 |
| 50mm 09/10 | 与 v6 原 01/02 按 `09 Posi6`、`10 Nega6` 重绑后全等。 |
| 50mm 其它槽、28mm 16 槽 | 与 resident_v32 原 full 的 C 展开结果全等。 |
| Mount 01–08 | 与 `mount_calib_r1/local/entries` 的八条校准及 records64 全等，pin 采用产品冻结的 CRC profile。 |
| Mount 06 | 身份为 `06ClsNeg`，无 C/D、T1 位，T control=2。其它七条也无 T1。 |
| Mount 09–16 | 与原 full 的原厂别名展开结果全等。 |

银行 record 的 slot、记录 CRC、49 B 身份、descriptor 绑定均已核对。另对八个关键槽分别篡改 slot 或名称身份，并重算 record、bank、payload、header CRC；共 16 个语义负例仍被冻结 C 校验器以 BANK 或 TABLE 拒绝。这排除了只验证外层 CRC 就算数据合格的情况。

完整逐槽标签、来源和条目摘要见 [data-results.json](local/data-results.json)。理光展开字节和输入副本只存于本任务忽略的 local。

## 6. 主机测试是否真正覆盖需求

主机程序从冻结的产品、engine services、resident v3.2 C 重新编译，使用 ASan/UBSan。原生文件、分配器、UI、RPC 是 doubles；实际 adapter、存储事务、GXTS、引擎 core 和 resident 路由没有被成功返回值替代。入口 offset 调度到真实 C，不执行 M32R 机器码。

| 本轮检查 | 结果 |
| --- | --- |
| 原 full，只把缺文件 raw code 从 -2 改为 -1。 | 三单元都重现 `state=6 fault=-5`，验证原故障仍可复现。 |
| 开发方 18 场景 × 两组容器 × 三单元。 | 108 次通过，包括 IROM 重启、16 项实际逐槽应用、DAT→OK、保存/取消、模拟格式化和既有失败注入。 |
| 新增十场景 × 三单元。 | 30 次通过，包括空 IROM、空 GXTS 首次安装、写后核对和分配失败。 |
| 七操作 × -1/-2 × 三单元。 | 42 次通过，仅只读 open(-1) 获得缺失语义。 |
| 两版完整 C 校验器 × 三容器 × 三单元。 | 18 次通过，包含原测试计数中的 9 次。 |
| 新审查反例，五场景 × 三单元。 | 15 次成功复现 F01、F02，不计作产品安全通过。 |
| slot/identity 语义负例。 | 16 次均被拒绝。 |

开发方报告的 189 项可以重现：180 次行为/边界检查加 9 次新校验器检查。首次安装从空文件表开始，确实走真实 `ig_menu → install/preload → storage`，缺文件原始码确实为 -1。并非先写好 IROM 或绕开预加载。full-r2 故障组使用同数据的 generation=103 测试前件，再升级实际 generation=104，避免相同文件跳过提交而造成假覆盖。

但 `lease-preload`、`lease-save` 实际注入的是 alloc 失败；`rv_native_free()` double 总是清标志。`gxts-partial-io` 注入 read 失败，不覆盖 open 失败丢失错误标记的情况。既有 green suite 因此不能反驳 F01、F02。

首次安装三单元均记录 `rows=16 IROM_install=OK DAT_to_OK=OK IROM_reboot=OK raw_missing=-1 temporary_leases=0 main_request=78224`。例见 [50mm 首次启动](local/logs/suite-full-r2-firstboot-empty-0.log) 与 [完整流程](local/logs/suite-full-r2-prev-flow-0.log)。模拟格式化是清空 double 中 `/IROM/` 文件后重启，不是真机格式化证据。

所有逐例返回码见 [suite-results.json](local/suite-results.json)、[baseline-results.json](local/baseline-results.json)、[adversarial-results.json](local/adversarial-results.json)。预期基线失败和审查脚本两处尺寸/编译宏假设错误均保留在 local；后两者已纠正，未冒充产品缺陷。

## 7. Stage2l 恢复后，残留产品文件不会被加载

已核实：审查的 Stage2l 映像为 `efe6587190e845b1c28364c02a6b8bde14e046e7c7411393a4c9892124b6bfd7`，8,080 B payload 为 `5510f2be98906f3b17c8a664be6108a12def3a26c7b575e38812744b0de66c44`。ELF、payload.bin、映像内 payload 逐字节相同，manifest 中全部构建源码/头文件摘要均匹配。没有只凭字符串搜索作结论。

源码和已审机器码的文件调用链只有以下路径。

- [ui.c](../../firmware/stage2l_switch/ui.c) 的 `load_view` 经 `rfw_read_file`，只允许当前编译分支的 `/ATA1/DEEPISP0.DAT`、`/ATA1/DEEPISP1.DAT`。
- [deep_isp.c](../../firmware/stage2l_switch/deep_isp.c) 的表加载经 `rfw_read_path`，只传 `/ATA1/DEEPTBL0.DAT`、`/ATA1/DEEPTBL1.DAT`。
- [platform.c](../../firmware/stage2l_switch/platform.c) 的 `rfw_read_path` 是 payload 中唯一调用 `gxr_open` 的函数。实际 ELF 确认这两个调用入口；生产 ELF 没有 create/write/delete、产品 `rv_load` 或 `rv_service`。

实际 payload 没有 `/IROM`、GXRCE、GXTS 或三类微调文件名，也没有 Stage2k P0 外部加载器。由有限调用链、固定路径、无产品 loader，以及与已审映像的字节绑定，可以确认 Stage2l 不读取 `/IROM/GXRCE*` 和产品 GXTS。成功刷回这个 Stage2l 后，残留产品容器与微调文件是惰性的，不影响 Stage2l 使用，无需先清除它们才能回退。

本轮没有操作“+ & 播放键”。用户指定的 A 卡回刷流程作为恢复前提；这里确认的是成功回刷后的文件惰性，没有声称任意 RAM 损坏都保证进入更新入口。恢复证据见 [recovery.json](local/recovery.json) 和 [Stage2l 实际反汇编](local/logs/stage2l-disassembly.log)。以后重新刷回匹配身份的产品常驻层时，残留 IROM 仍可重新生效。

## 8. 交付、重跑和范围

本轮不放行 full-r2，因此不列试用步骤。开发方先处理 F01，并闭合 F02 的正式目标保护，再对新容器摘要复审；机身 v3.2 无需因本报告而重刷。

重跑入口只向本审查目录写文件，不调用产品 builder，不修改冻结产品源码。已有冻结输入不能被 `freeze` 覆盖。

```sh
cd /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh
/usr/bin/python3 -I -B research/review_engine_fix_r1/review.py inspect
/usr/bin/python3 -I -B research/review_engine_fix_r1/review.py layout
/usr/bin/python3 -I -B research/review_engine_fix_r1/review.py suite
/usr/bin/python3 -I -B research/review_engine_fix_r1/review.py baseline
/usr/bin/python3 -I -B research/review_engine_fix_r1/review.py adversarial
/usr/bin/python3 -I -B research/review_engine_fix_r1/review.py data
/usr/bin/python3 -I -B research/review_engine_fix_r1/review.py recovery
/usr/bin/python3 -I -B research/review_engine_fix_r1/review.py finalize
```

写入前已读取 `/Volumes/Workspace/AGENTS.md`，确认已挂载、可写 APFS，UUID 为 `14BE04EB-AF49-497E-B36A-B078B2F7C5E8`。本目录 `.gitignore` 为 `local/`，`git check-ignore -v` 命中本目录第 1 行，结果见 [ignore.log](local/ignore.log)。已冻结并复核 440 份输入，源文件摘要未变，原 tracked Git 状态未变。共享检出本来就有大量有效未跟踪目录，本轮没有删除、移动或回退它们。

只向 `research/review_engine_fix_r1/` 写文件。理光二进制、展开数据、固件切片、反汇编、编译对象和日志都在本任务 local。没有操作相机、存储卡或刷机，没有重建常驻 ELF 或机身映像，没有安装包、启动子代理、sleep、轮询、commit 或 push。所有 Python 使用系统 `/usr/bin/python3 -I -B`，反汇编只用指定 m32r-elf-objdump。

交付清单为 [SHA256SUMS](SHA256SUMS)，输入保护结果为 [scope.json](local/scope.json)。本轮已核实的是静态字节、源码与主机故障行为；实际 M32R 执行、真实堆状态、物理存储与拍摄效果没有验收。
