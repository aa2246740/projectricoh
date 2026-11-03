不可以

full-r3 的 F01 修复通过本轮增量审查，但 F02 仍超出协调者接受的 GXTS 微调丢值范围：有效 IROM 引擎持续 open(-1) 时，可以被较旧或同代不同内容的卡容器覆盖。不能据此放行题设 SHA-256 的 full-r3 上卡试用；机身 v3.2 不需要因此重刷。

日期：2026-10-24。本轮只读审查用户指定的共享检出，设备对象为官方 1.51 的 GXR、GR LENS A12 50mm 和 MOUNT A12。主机检查另外覆盖 A12 28mm，没有操作任何设备。结构化结论见 [findings.json](local/findings.json)。

## 1. F02 · P2，阻断本轮放行：未知引擎副本仍可被降级覆盖

已核实：[panel_store.c](../../firmware/engine_fix_r2/containers/product/src/firmware/engine/panel/panel_store.c) 第 71–84 行最多重试三次只读 open；第 167–179 行跳过持续 `RV_UNAVAILABLE` 的副本，不保留其 generation。第 296–317 行在目标未被观察时跳过删除检查，直接把核对后的 TMP 改名到该正式目标。第 362–373 行的代次比较只覆盖可见的有效副本。

第 300–302 行的注释明确承认，这个回退依赖“卡比任何旧副本都更新”的假定。现有服务 ABI 没有提供这个证明。问题也不限于 A/B 都未知：另一份较旧副本可读时，提交会覆盖不可读的较新目标。

独立夹具在调用真实 `rv_load` 前放入有效 IROM 文件。resident 按原有逻辑优先加载卡，之后真实 `ig_menu → install → ps_install → storage` 执行提交。只注入正式目标的三次只读 open=-1，沿用项目原有的允许替换目标的 rename double，没有替换产品安装或校验函数。三单元均复现以下五种情况，共 15 例。

- A=106、B 不存在，A 连续三次不可读。卡 105 覆盖 A，唯一的 106 丢失，B 仍不存在。
- A=106、B=104，A 连续三次不可读。卡 105 覆盖 A，剩下 105 和 104。
- A=104、B=106，B 连续三次不可读。卡 105 覆盖 B，剩下 104 和 105。
- A=B=106，两份各连续三次不可读。A 被改成 105，B 的 106 保留；仍然违反严格更新后才能写入的要求。
- A=105，但内容为 r1 的 full-r2 引擎经合法改代次后的容器。A 连续三次不可读，full-r3 105 覆盖它，没有报告同代不同内容冲突。

这些情况下均返回安装成功，root 仍 READY，DAT 已变为 OK。例：[唯一较新 A](local/logs/audit-audit-engine-newer-A-0.log)、[较新 B 与可读旧 A](local/logs/audit-audit-engine-newer-dest-B-other-0.log)、[同代不同内容](local/logs/audit-audit-engine-equal-0.log)。全部逐例结果在 [audit-results.json](local/audit-results.json)。

106 和同代冲突容器是本轮构造的输入，不是相机存储读回。除了被改写的 generation 和头 CRC，它们保留原生产容器字节；当前完整 C 校验器及冻结 v3.2 完整 C 校验器均接受，后者另独立验证两份夹具 × 三单元。见 [夹具摘要](local/counterexample-fixtures.json)。这排除了用无效容器制造反例的情况。

对照也通过：较新 A 可读时返回 `RV_CONFLICT`，没有写入或 rename；仅一次 open=-1 时，重试恢复后保留旧副本，并向另一副本提交。开发方 `r3-newer-generation` 用例只隐藏两次，第三次就读到较新副本，因此它的通过不能证明持续 -1 的保护。

证据边界：这里复现的是产品 C 在覆盖式 rename 语义下的行为。官方 rename 的目标已存在语义及失败后的物理持久化仍未闭合，本轮没有声称真机已经发生覆盖。但当前实现无法保证题设要求的引擎副本保护，协调者只接受了 GXTS 例外，不能把引擎降级也算进该例外。

修复要求：正式引擎目标或其代次仍未知时，停止安装和 DAT→OK；保护必须覆盖首次安装和“另一副本可读”的分支。若仍要支持空 IROM 首次安装，需要可验证的不存在证据，或已证明不会覆盖目标的提交操作。增加有限重试不能区分空目录和持续不可读。应先在当前反例上证明修复，再审新的容器摘要。本轮没有修改产品源码。

## 2. F01 已关闭，会话工作区与 UI 生命周期通过

已核实：实际 M32R 编译的 `SessionWork` 为 912 B，含 `PnGxts` 656 B 和 256 B 存储缓冲。64 位主机为 944 B，不能把日志中的 944 当作相机申请量。独立 sizeof 对象直接包含冻结的实际 adapter，见 [目标布局](local/actual-workspace-layout.json)。

[adapter.c](../../firmware/engine_fix_r2/containers/product/adapter.c) 的工作区只在首次菜单、安装缓冲收尾之后申请一次 usage=4 lease。16 槽预加载、关菜单、重开和后续保存都复用同一 token 与 base。连续八次保存逐次核对实际微调值和 generation=1..8，alloc/free 计数不增加。

`shutdown`、`abort` 和引擎出错停用才释放工作区。第 110–115 行先记录已经尝试释放；`release` 只在服务返回 OK 时清本地 lease 信息。独立检查分别覆盖三种结束路径的正常释放和 native free 保持 header=1 的失败，共 18 例。失败时 token、inverse、base、length、原始 `lease_entry` 均保留，resident 停用，下一入口不再申请或重试 free。正常释放后重入也不会再次 free。见 [故障停用](local/logs/audit-audit-work-fault-fail-0.log) 和 [连续保存后释放失败](local/logs/revision-review-free-repeat-0.log)。

安装的两个 65,536 B usage=2 lease 各自检查释放结果。第二块申请失败时也检查第一块收尾。分别注入 work、raw 释放失败，以及第二块申请失败后 raw 释放失败，均保留失败块归属，停用且不申请工作区。已成功提交的文件没有被伪装成回滚。见 [raw 收尾失败](local/logs/revision-r3-install-free-raw-0.log)。

没有重新引入 review_flash_v31 的 F08。`PnPanel`、labels、refs、details 和 glyph 继续位于主块的 `Integrated` 中，resident 发布时复制到保留的 UI snapshot。它们没有移进可释放工作区。独立用例核对实际发布的 labels、refs、glyph 地址属于 snapshot，panel 属于主块，工作区 token 没有作为 view lease 发布。释放成功或失败后，主块和 snapshot 的头部均保持 live。

[services.c](../../firmware/engine_fix_r2/engine_services/services.c) 对 usage=4 的放宽只取消“必须在申请它的同一入口释放”的限制。当前 session、六个请求 epoch、token/inverse、堆头、非主 lease、非 UI view lease、非嵌套调用和 owner 检查仍然生效。它不改写原始 `lease_entry`。usage=2 继续走 `rv_free_checked` 的原有入口限制。

本轮对真实释放服务补了 20 类边界 × 三单元，共 60 例。合法跨入口释放成功，重复 token 被拒绝；旧 session nonce、六种旧 epoch、未知 token、坏 inverse、UI 引用、嵌套、owner/stop、坏堆头、单元变化、主 lease、堆范围变化及 usage=2 跨入口释放均未触发 free。见 [合法跨入口与重复请求](local/logs/audit-audit-lease-0-0.log) 和完整 [独立检查](local/audit-results.json)。在这些已测边界内，没有发现跨会话或跨代次误释放。

实际引擎 ELF 也保留这些判断：`release` 在 `0x16E8` 检查服务结果；`workspace_close` 在 `0x173C` 设置一次标志后才调用释放；usage=4 路径在 `0xAEAC` 调原生 free，`0xAEB8` 读头标志，非零不会清 token；安装两块收尾在 `0x6268`、`0x627C` 各自调用并汇总结果。见 [release](local/logs/m32r-release.log)、[会话释放](local/logs/m32r-session-work-free.log)、[安装收尾](local/logs/m32r-install-release.log)。

推断：原先反复分配导致五个临时槽耗尽的路径已经消除。释放失败会留下有归属记录、次数有界的私有块，这是停用保留，不是零泄漏保证。没有测量设备上的失败频率、连续堆余量或任意内存破坏。

## 3. GXTS 的已接受限制复现，非缺失读错误会锁住保存

已核实：只读 open=-1 经过最多三次尝试后仍映射为 unavailable。唯一有效 GXTS A 在预加载和保存扫描时各持续三次 -1，覆盖式 rename 下仍会从默认 Cont=0 保存 Cont=1，替换原 Cont=3，并把 generation 从 1 重新开始。三单元均复现，记为已接受限制，不算产品安全通过。见 [原始日志](local/logs/revision-r3-gxts-persistent-minus1-0.log)。

一次 open=-1 的旧反例已经修复：独立重放在预加载和保存各只隐藏一次，读取恢复后保留 A 的原字节，新值写 B，generation=2。

非缺失类 open、read 错误会被 `panel_gxts.c` 记录并锁存在 adapter 会话中。之后即使读取恢复、换槽或重开菜单，保存仍被拒绝，显示 SaveFail。开发方的预加载与保存扫描四类检查、跨槽两次保存，以及本轮独立补充的 close 失败均通过。close 失败进入更严格的停用状态，旧 A/B 字节保留。见 [错误锁存](local/logs/revision-r3-sticky-read-0.log)、[保存时 close 失败](local/logs/audit-audit-gxts-close-save-0.log)。

存储服务仍只允许固定的 GXRCE 路径和各单元各槽的微调路径，未开放照片或固件路径。48 槽展开、GXTS 身份和默认记录与 full-r2 逐字节相同，基础配方数据没有改变。但第 1 节已证明风险还涉及 GXRCE 引擎副本，因此不能确认“本候选的剩余风险只限 GXTS 微调数值”。

## 4. 增量范围与 v3.2 身份保持一致

已核实：r1→r2 的 `engine_services` 与 `containers/product` 共 14 个差异文件。运行逻辑差异集中于 services、adapter、panel_store、panel_gxts 及其头、panel_ui；其余为测试、主机声明、候选编号和工具路径。`gxts_io.c`、core 和 resident 源码没有增量变化。完整清单及补丁见 [source-differences.json](local/source-differences.json)、[source-differences.patch](local/source-differences.patch)。

本轮核对 29 个链接源码摘要和三个工具摘要。最终 DAT 的 80 B body/build/ABI 身份与批准的 resident ELF 相同；ELF 的 7,772 B payload 与批准映像对应地址全等，pins 相同。独立从冻结 v3.2 源码和现有工具链重算的 build/ABI 也相同。

```text
full-r3 bytes        59704
full-r3 SHA256       0f49317ac8b2609cb268a7951ec263959e8a2fedef818c7d9dd8e530796c7885
generation           105
engine / BSS bytes   50276 / 11172
approved image       05b46ee65f4861f2e09e9b7c519cbcc2dffb195158a40c3bb033540b36a98d8c
resident ELF         f25899258471d0652a8fef8980b9f0a83a0ca7cd4ddc6bbe8fcc337467362b58
official body        da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7
resident build       2eea6eb324790b035d37d33395d60880a1909b4e693414a939dee45f96bfbae7
resident ABI         9583fdd751bebc36f3af305595559643
pins                 DF2BCAF5 / 6700E6FF / 1B3C7000
```

最终 DAT 的引擎段与 `engine.elf` 全等，头和 payload CRC 正确。反汇编只使用指定 objdump，输出列出的字节逐一对回各 ELF，见 [artifacts.json](local/artifacts.json)、[disassembly-byte-checks.json](local/disassembly-byte-checks.json)。这些是磁盘输入身份，没有读回相机 flash。

实际主块请求为 `7504 + align4(59704 + 11172) = 78380 B`，三单元首次安装日志与其一致。含原生头的正常保留量为 81,916 B。安装两块 64 KiB 临时缓冲时工作区尚未申请，首次安装阶段为 210,108 B；若已有 UI snapshot，还须计入其 1,980 B。它们是请求量，不能当作设备堆容量测量。

## 5. 端到端与旧反例复跑结果

所有行为程序都从本轮冻结源码重新编译，启用 ASan/UBSan。adapter、engine core、存储事务、GXTS、engine services、resident loader 与路由均是真实产品 C。替身只位于原生文件、分配器、UI、RPC 以及“按最终 offset 调用 C 入口”的宿主边界，不执行 M32R 指令。新增审查驱动仅接入测试分派和 include，差异见 [audit-driver.patch](local/audit-driver.patch)。

- 原 18 个场景 × 两组容器 × 三单元，共 108 例通过，覆盖实际 16 槽应用、保存、取消、IROM 重启和模拟格式化回退。
- 原增补十场景 × 三单元，共 30 例通过，包含空 IROM、空 GXTS、读回失败及申请失败。
- 七种原生操作 × -1/-2 × 三单元，共 42 例通过。仅只读 open(-1) 获得 unavailable 语义。
- r2 的 23 类修复回归 × 三单元，共 69 例通过。旧 F01 三类反例按新生命周期改为检查复用与结束时释放；旧 F02 引擎、GXTS 两类瞬时 -1 反例均检查保留原字节。原先逐次分配、释放的调用点已经删除，没有用一个永远不命中的 free 注入冒充复测。
- 独立新增 37 类 × 三单元，共 111 例中，96 例满足安全断言，15 例成功复现第 1 节引擎缺陷。这 15 例的程序返回 0 仅代表反例断言成立。
- 已接受的持续 open(-1) GXTS 限制另有三例复现，不计入安全通过数。
- 两版完整 C 校验器对 base、huzi、full-r3 × 三单元，共 18 次通过；另外两份反例夹具的六次冻结校验通过。48 槽 entry、GXTS 绑定和默认 wire 记录与 full-r2 全等，16 个重算全部 CRC 的 slot/identity 篡改样本仍被拒绝。

首次安装确实从空文件表开始，只放入 DAT，缺文件的原始返回码为 -1，真实菜单入口完成安装、16 项显示及 DAT→OK，再重启从 IROM 加载。三单元均记录 `temporary_leases=0 session_workspace=1 main_request=78380`，不是先种好 IROM 后绕开安装。例见 [空目录首次安装](local/logs/suite-full-r3-firstboot-empty-0.log)、[完整流程](local/logs/suite-full-r3-prev-flow-0.log)。

`full-r3-prev` 是同代码、同数据、generation=104 的测试前件，用来确保 105 实际走提交路径，不代表旧 M32R 引擎在运行。独立“卡内容在 load 后变化”用例在任何写入前返回 STALE。写后 open 失败会连续注入三次以耗尽重试；TMP 未核对不提交。rename 的目标存在拒绝、失败无字节变化和源 TMP 已丢失后失败均覆盖，并核对保留正式副本。

模拟格式化只清空文件 double 的 IROM 项。未知仍包括真实格式化、物理断电、堆碎片、完整 native UI 时序、实际 M32R 执行和照片效果。没有把上述通过计为真机验收。

逐例清单为 [suite-results.json](local/suite-results.json)、[revision-results.json](local/revision-results.json)、[audit-results.json](local/audit-results.json)，数据证据为 [data-results.json](local/data-results.json)、[incremental-data.json](local/incremental-data.json)。

## 6. Stage2l 回退后的残留文件不参与加载

已核实：题设 A 卡恢复所对应的已审 Stage2l 映像 SHA-256 为 `efe6587190e845b1c28364c02a6b8bde14e046e7c7411393a4c9892124b6bfd7`，8,080 B payload 摘要为 `5510f2be98906f3b17c8a664be6108a12def3a26c7b575e38812744b0de66c44`。本轮重新核对 payload、ELF、映像内对应字节及构建输入摘要。

源码和实际 ELF 的文件调用链只有 `ui → rfw_read_file → rfw_read_path` 的 DEEPISP0/1，以及 `deep_isp → rfw_read_path` 的 DEEPTBL0/1，均在 `/ATA1/`。`rfw_read_path` 是 payload 唯一调用 `gxr_open` 的函数，没有产品 `rv_load`、`rv_service` 或 IROM 文件名。判断依据包含固定调用点及字节绑定，不只靠字符串搜索。见 [recovery.json](local/recovery.json)、[实际 Stage2l 反汇编](local/logs/stage2l-disassembly.log)。

因此，在成功刷回该 Stage2l 后，残留 `/IROM/GXRCE*` 和 GXTS 不会被它读取，无须先删除残留才能恢复 Stage2l 使用。本轮没有执行 A 卡“+ & 播放键”，沿用题设的回刷入口；这里只确认回刷成功后的残留惰性，不证明任意 RAM 损坏下都能进入升级。日后重新装匹配的产品常驻层，残留文件仍可能重新生效。

## 7. 复跑与写入边界

本候选不放行，因此不提供上卡试用步骤。下一轮先关闭 F02 的引擎保护缺口，再交新摘要复审。

以下入口只写本审查目录，不调用产品固件 builder，不安装依赖。冻结输入已经保留，不能重复运行 `freeze` 覆盖它们。

```sh
cd /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh
/usr/bin/python3 -I -B research/review_engine_fix_r2/review.py inspect
/usr/bin/python3 -I -B research/review_engine_fix_r2/review.py layout
/usr/bin/python3 -I -B research/review_engine_fix_r2/review.py suite
/usr/bin/python3 -I -B research/review_engine_fix_r2/review.py revisions
/usr/bin/python3 -I -B research/review_engine_fix_r2/review.py audit
/usr/bin/python3 -I -B research/review_engine_fix_r2/review.py data
/usr/bin/python3 -I -B research/review_engine_fix_r2/review.py recovery
/usr/bin/python3 -I -B research/review_engine_fix_r2/review.py static
/usr/bin/python3 -I -B research/review_engine_fix_r2/review.py finalize
```

写入前读取了 `/Volumes/Workspace/AGENTS.md`，核对已挂载、可写 APFS，Volume UUID 为 `14BE04EB-AF49-497E-B36A-B078B2F7C5E8`。本任务 `.gitignore` 第一行为 `local/`，`git check-ignore -v` 已确认，见 [preflight.json](local/preflight.json)、[ignore.log](local/ignore.log)。最终重新核对 560 份保护输入，源码和输入摘要未变，原 tracked Git 状态未变，见 [scope.json](local/scope.json)。

理光数据、固件副本、夹具、反汇编、编译对象和原始日志全部位于本任务忽略的 local。只向 `research/review_engine_fix_r2/` 写文件，没有删除、移动或改写共享检出的其它有效工作，没有操作相机、访问存储卡、刷机、安装包、启动子代理、sleep、状态轮询、commit 或 push。长命令只读取一次终态，没有轮询循环。

审查工具首次复用时遗留一个派生 objdump 路径，导致 inspect 在启动反汇编前失败；修正为题设绝对路径后通过，说明保存在 [harness-failures.md](local/harness-failures.md)，没有计作产品缺陷。所有 Python 使用系统 `/usr/bin/python3 -I -B`；仅为尺寸验证编译目标对象，没有重建机身映像或 resident ELF。

交付清单为 [SHA256SUMS](SHA256SUMS)，最终检查为 [delivery-validation.json](local/delivery-validation.json)。
