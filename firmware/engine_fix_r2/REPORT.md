# engine_fix_r2 与 full-r3 实施报告

F01 已按会话工作区方案修复。F02 按指定的保守分支处理，官方 rename 的“目标已存在且失败无副作用”前提没有得到证明，因此不能给出旧副本无条件保留的结论。full-r3 已生成，generation=105；258 项主机检查通过，另有 3 项持续 open(-1) 的 GXTS 丢值风险被刻意复现，未计入安全通过数。

日期：2026-10-24。对象为用户自己的 Ricoh GXR 机身官方 1.51，以及官方 1.51 的 GR LENS A12 50mm、A12 28mm、MOUNT A12。本次只修改容器内引擎和相关主机工具，不提供上机放行结论。

## 交付物

- 容器为 [full-r3/GXRCE.DAT](local/product/candidates/full-r3/GXRCE.DAT)，59,704 B，generation=105。
- SHA-256 为 `0f49317ac8b2609cb268a7951ec263959e8a2fedef818c7d9dd8e530796c7885`。
- 主块 request 为 78,380 B，私有会话工作区 request 为 912 B。每块原生分配头另计 12 B。
- [SHA256SUMS](SHA256SUMS) 覆盖源码、报告、容器、ELF、编译对象、输入保护记录和原始日志。容器目录另有独立清单。

已核实的是源码、磁盘上的官方字节、M32R 交叉编译产物和真实产品 C 的主机行为。文件系统、原生分配器、UI、RPC 由故障可注入的 doubles 提供。主机通过最终入口 offset 调用真实 C，没有执行 M32R 指令，也没有连接相机。

## F01：工作区复用和释放失败

已核实：[adapter.c](containers/product/adapter.c) 的 `SessionWork` 含一份 `PnGxts` 和 256 B 存储工作缓冲。目标 M32R 的 `PnGxts` 为 656 B，合计 912 B。64 位主机的同一工作区为 944 B，日志中的 944 不能当作相机申请量。

首次 `menu_open` 在安装临时缓冲收尾之后、`eng_menu_open` 和列表发布之前申请一次 usage=4 私有 lease。resident 已经进入 READY，但原生 UI 尚未引用本次引擎的列表。16 槽预加载和之后的面板保存复用同一个 token、base 和工作区。关闭列表或微调面板只结束本次菜单操作，resident 会话继续，工作区继续保留。`shutdown`、`abort` 或引擎出错停用时才尝试释放一次。

原有 usage=2 临时 lease 只能在申请它的入口释放。为避免把会话工作区强行改写为“当前入口申请”，[services.c](engine_services/services.c) 仅对既有 usage=4 增加会话归属下的释放处理。服务仍先验证当前 session、epoch、token、inverse、堆头和 UI 引用，原始 `lease_entry` 不改写。usage=2 安装缓冲仍用原先的 `rv_free_checked`。机身 ABI、resident 源码和 resident ELF 均不改。

`release()` 检查 `pn_call(RV_LEASE,2)` 的返回值。成功才清本地 lease 信息。失败保留 token、base、length、原始归属记录，设置失败标记并让本次开机停用扩展。工作区的“已经尝试释放”标记阻止第二次 free；常驻层随后按原逻辑进入 `RV_DISABLED_UNTIL_REBOOT`。下一入口不重新安装、不申请新块、不重试 free。

安装的两块 65,536 B usage=2 lease 都检查释放结果。第二块申请失败时，也检查第一块的收尾。任一释放失败都返回 `RV_FAULTED`，剩余已申请块各收尾一次，随后停用，不再申请会话工作区。安装的文件提交可能已经成功，释放失败不会假装撤销已有写入。

没有把 `PnPanel`、UI labels、refs、details 或 native snapshot 移入这个可释放工作区。它们仍在主块或 resident 的保留快照内。工作区从不作为 UI lease 发布。故障用例确认工作区 free 失败后，主块和 UI snapshot 的分配头仍为 live，未释放原生 UI 仍引用的内存。

连续 8 次保存逐次检查 GXTS generation=1..8 和实际微调值，始终复用同一工作区，没有逐次 alloc/free。会话结束时注入 native free 保持 header=1，真实服务返回失败，归属记录保留，下一入口不再分配。正常跨入口释放、两块安装缓冲各自释放失败、第二块申请失败后的释放失败均通过。证据见 [释放失败](local/logs/revision-review-free-preload-0.log)、[连续保存](local/logs/revision-review-free-repeat-0.log)、[正常跨入口释放](local/logs/revision-r3-workspace-release-0.log) 和 [逐例结果](local/revision-acceptance.json)。

推断：反复临时 lease 导致的五槽耗尽路径已消除。释放失败仍可能保留一个私有工作区或安装缓冲，这是有归属记录、次数有界的停用状态，不是零泄漏保证。设备上该失败条件的发生频率未知。

## F02：官方 rename 的逐指令证据

输入为只读 `artifacts/firmware/gxr-1.51/ilaunch3`，SHA-256 `da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7`。完整原始指令与切片摘要在 [rename/regions.json](local/rename/regions.json) 和 `local/logs/rename-*.log`。只用指定 `research/tooling_m32r/prefix/bin/m32r-elf-objdump`，没有执行官方代码。

1. [包装器](local/logs/rename-wrapper.log) 的 `0x200A49E0` 保存新路径到 r10。`0x200A49EC` 调 `0x200A531C`，`0x200A4A08` 复制旧路径到栈，`0x200A4A14` 再规范化新路径。`0x200A4A20` 进入原生锁，`0x200A4A30` 调 `0x200A6CB8`。`0x200A4A34` 保存结果，`0x200A4A40` 解锁，`0x200A4A44` 原样恢复返回值。包装器没有提供目标不存在的独立操作。
2. [内层](local/logs/rename-inner.log) 的 `0x200A6CBC` 把新路径放入 r8，`0x200A6CC0` 把旧路径放入 r10。`0x200A6CD4` 先以 r8、参数 85 调 `0x200AF654`；`0x200A6D18` 再以 r10 调它。`0x200A6D9C` 调 `0x200B4824(1)`，失败走错误 42。`0x200A6DDC..6DEC` 设置栈指针和 32 B 长度，经 `0x200BA2F4` 保存原目录项。
3. `0x200A6E0C` 或 `0x200A6E20` 从当前上下文取目录项指针到 r9。`0x200A6E38` 调 `0x200B9CD4(0,1,r9+11)`，`0x200A6E4C` 调 `0x200B9CD4(0,6,r9+26)`。`0x200A6E58` 把 r9 传入 `0x200B52B4`，非零会走错误 43。
4. [该下层函数](local/logs/rename-check-source.log) 的 `0x200B52BC` 将输入保存到 r10，`0x200B5300` 设置上下文 +698 的标志。`0x200B5320` 明确执行 `ldi r0,#-27 -> stb r0,@r10`，即把原目录项首字节改成 `0xE5`。`0x200B541C` 又调用 `0x200B8B40(2)`。这证明已有源目录项内存副作用，不能把后续失败解释成函数从未改动状态；是否已落到物理介质没有运行证据。
5. 返回后，内层到 `0x200A6E98` 才再次处理目标路径。`0x200A6F30` 调 `0x200B3CCC(3)`；`0x200A6F3C` 调 `0x200B6D08`；`0x200A6F44` 只有零结果才能继续，否则走错误 46。已展开这些下层的上下文修改和空目录项扫描，但没有闭合“所有既有同名目标必被拒绝且无副作用”的条件。
6. `0x200A6F8C` 以 32 B 长度调用复制函数，`0x200A6FA0` 再处理目标名字；`0x200A6FCC` 复制 11 B 名字段，`0x200A6FE0` 把上下文 +696 设为 1。`0x200A7020` 或 `0x200A7060` 调 `0x200B71B0`，`0x200A7078` 调 `0x200B8B40(2)`，其失败走错误 47。后面还有目录移动相关更新。`0x200A71A4` 才设置成功值 0。
7. [错误函数](local/logs/rename-error.log) `0x200AF4EC` 会记录错误并调用清理函数，`0x200AF64C` 返回 -1。不能从这个 -1 推出先前目录项改动已经回滚。

已核实：rename 有多步状态修改，返回 -1 的路径可以位于源目录项修改之后。未知：既有正式目标究竟被拒绝、替换还是形成其它目录状态，以及各错误点的物理持久化结果。因而本次选择任务的“会覆盖或行为不能确定”分支，没有采用依赖无副作用拒绝的方案。

## F02：已实施策略与剩余风险

[panel_store.c](containers/product/src/firmware/engine/panel/panel_store.c) 的单一只读 open 边界在 `RV_UNAVAILABLE` 时最多再试两次，共三次。GXTS 的 `PnGxts` 适配器也经过该边界，因此没有在通用 `gxts_io.c` 再加一套重试。真实 read、close、create、write、delete 和 rename 错误不被重试成成功。resident loader 和安装见证的原有逻辑不变。

引擎扫描仍把“三次 -1”记为未知，而不是已证不存在。A/B 都未知、没有可见有效副本时，只将完整核对后的卡容器写到 A，B 不作为这种首次提交的目标。这个授权依赖任务给定的前提：卡 DAT 严格新于任何旧引擎副本。本次卡为 generation 105，旧测试前件为 104。可读或在重试后恢复的 generation 106 会返回 `RV_CONFLICT`，没有写入和 rename。

已有有效副本时仍先保留它，再向另一副本提交。TMP 必须写完、关闭、完整读回并逐字节核对，rename 成功和正式副本再次核对成功才算提交；DAT→OK 另有原来的来源、正式副本和 SD ID 见证。rename 失败一律停写并停用。替身测试分别覆盖目标已存在时拒绝、失败前不修改字节，以及先丢失源 TMP 再失败。后两类都核对保留的正式副本字节，未把“TMP 一定仍在”当作官方保证。

[panel_gxts.c](containers/product/src/firmware/engine/panel/panel_gxts.c) 记录非缺失类 open、read 和 close 错误。adapter 将它锁存在整个会话中。任一槽发生这类错误，之后所有槽的保存都返回失败，不因下一次读取恢复或换槽而解锁；预加载和保存重扫都受此规则保护。面板第一行显示 `SaveFail`，其文本已经过实际 glyph 转换和 resident snapshot 复制核对。

剩余风险已复现，见 [remaining-risk.json](local/remaining-risk.json)。如果唯一有效 GXTS A 在预加载和保存重扫时，各连续三次只读 open 都返回 -1，而 rename 替身允许覆盖，程序仍只能把它视为与空目录不可区分的状态。测试从 Cont=3 出发，读到默认 0，保存 Cont=1 时覆盖 A，并把 generation 重新从 1 开始。这是主机替身上的明确反例，不是相机上已经发生的数据丢失，也不计为产品安全通过。

因此，有限重试解决了审查中一次 open=-1 的全部隐藏副本反例，但不能提供持续 -1 下 GXTS 的无条件保留。现有 ABI 若既要支持空 GXTS 首次保存，又要完全区分不可读的旧副本，还需要可靠的“不存在”证据或已证明不覆盖的提交操作。相同歧义也让引擎无法在 A/B 全部不可读时运行时证明卡 generation 更高；若违反本任务“卡严格更新”的前提，A 可能被较旧容器替换。掉电、共享目录损坏和并发原生修改均未验收。

## 内存、数据和常驻身份

| 项目，单位 B | full-r2 | full-r3 |
| --- | ---: | ---: |
| 文件 | 59,328 | 59,704 |
| 引擎 | 49,900 | 50,276 |
| BSS | 11,392 | 11,172 |
| 数据段，不含头 | 9,164 | 9,164 |
| 主块 request | 78,224 | 78,380 |
| 会话工作区 request | 无，反复申请 652 | 912，一次 |

主块从已批准 resident ELF 的真实分配指令推导，而不是采用旧常数。`0x20053764` 加数为 7,504，包含 session=1,104、state=6,144、UI capacity=256。实际申请为 `7,504 + align4(59,704 + 11,172) = 78,380 B`。三单元空 IROM 首次安装日志均观测到这个 request。

含原生头的正常保留量为主块 78,392、loader 工作区 620、UI snapshot 1,980、会话工作区 924，合计 81,916 B。首次空目录安装时会话工作区和 UI snapshot 尚未申请，两块 64 KiB 缓冲含头各 65,548 B，该阶段合计 210,108 B。若已有保留 UI snapshot，再加 1,980 B。两块安装缓冲都收尾成功后才申请私有工作区，不把这些申请量遗漏在峰值之外。它们不是相机可用连续堆空间的测量值。

已核实：两版完整 C 校验路径对 full-r3 展开 48 槽，448 B 条目、160 B GXTS 绑定和 240 B 默认记录均与 full-r2 全等。另逐槽核对原 full 与 Mount 校准源，见 [data-and-gxts-compatibility.json](local/data-and-gxts-compatibility.json)。内容为 50mm 全套、Mount 01–08 校准及 09–16 原厂别名、28mm 全部 16 个原厂别名。Mount 八条均无 T1，控制值为 2。没有用新的引擎字节掩盖数据改变。

常驻层逐文件摘要与任务开始时一致，未重新链接或发放身份。final DAT 的 80 B 身份与原 resident ELF 相同，7,772 B 常驻 payload 与批准映像对应地址逐字节一致，pins 为 `DF2BCAF5 / 6700E6FF / 1B3C7000`。

```text
approved image SHA256 = 05b46ee65f4861f2e09e9b7c519cbcc2dffb195158a40c3bb033540b36a98d8c
resident ELF SHA256   = f25899258471d0652a8fef8980b9f0a83a0ca7cd4ddc6bbe8fcc337467362b58
body SHA256           = da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7
resident build        = 2eea6eb324790b035d37d33395d60880a1909b4e693414a939dee45f96bfbae7
resident ABI          = 9583fdd751bebc36f3af305595559643
```

[artifact-inspection.json](local/artifact-inspection.json) 记录目标 sizeof、分配指令和身份检查。容器引擎段与本次 `engine.elf`、`engine.bin` 全等，header 和 payload CRC 正确。沿用 r1 的工具链、FLAGS、`-Os -flto -fpic -m32r -mmodel=medium -msdata=none -G0`、服务归档选项及重定位审计；归一化平移到 `0x21004000` 后字节相同，只有一项容器重定位，零未解析符号。

## 测试、重跑和写入边界

| 检查 | 数量 | 结果 |
| --- | ---: | --- |
| 当前完整 C 校验器，base、huzi、full-r3 × 三单元 | 9 | 通过。 |
| 原 18 个端到端场景 × 两组容器 × 三单元 | 108 | 通过。 |
| 原新增 10 场景 × 三单元 | 30 | 通过，含空 IROM、空 GXTS、读回和申请失败。 |
| 七个原生操作 × -1/-2 × 三单元 | 42 | 通过，仅只读 open(-1) 有不可用语义。 |
| 本次 23 类修复回归 × 三单元 | 69 | 通过，包含原审查五类反例的新安全断言。 |
| 冻结 v3.2 完整 C 路径验证 final 三单元，展开和 full-r2 对照 | 3 单元、48 槽 | 通过。 |
| slot、identity 篡改并重算全部 CRC | 16 | 冻结完整 C 路径全部拒绝。 |
| GXTS 持续 -1 且覆盖式 rename 的限制复现 | 3 | LIMITATION_REPRODUCED，未计入 258 项安全检查。 |

全部主机行为测试启用 ASan/UBSan。缺文件的原始返回值确实为 -1。`lease-save` 不再注入一个已经删除的逐次申请点，而是让下一次 alloc 失败，验证保存仍成功且 alloc 计数不变。写后 open 故障用例增加为连续三个 -1，确保有意耗尽新增重试，不能把重试恢复当成失败路径覆盖。

`full-r3-prev` 只是同代码、同数据、generation=104 的主机前件，明确标记非生产容器，用于使 105 的提交路径实际执行。它不是旧 M32R 引擎运行证据。开发过程中三个测试夹具关闭菜单后漏开菜单的失败原始日志保留在 `local/failures/`，已修正操作顺序，没有改产品逻辑来迎合断言。所有最终逐例结果见 [product/acceptance.json](local/product/acceptance.json)、[extra-acceptance.json](local/extra-acceptance.json)、[revision-acceptance.json](local/revision-acceptance.json)、[semantic-results.json](local/semantic-results.json) 和 [test-summary.json](local/test-summary.json)。

重跑以下入口，只向本任务目录写文件，不安装新包。

```sh
cd /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh
/usr/bin/python3 -I -B firmware/engine_fix_r2/rename_evidence.py
/usr/bin/python3 -I -B firmware/engine_fix_r2/build.py
/usr/bin/python3 -I -B firmware/engine_fix_r2/verify.py
/usr/bin/python3 -I -B firmware/engine_fix_r2/inspect_artifacts.py
/usr/bin/python3 -I -B firmware/engine_fix_r2/write_report.py
/usr/bin/python3 -I -B firmware/engine_fix_r2/finalize.py
cd firmware/engine_fix_r2
/usr/bin/shasum -a 256 -c SHA256SUMS
```

已读取 `/Volumes/Workspace/AGENTS.md`，并在写入前确认挂载点、APFS、WritableVolume、WritableMedia 和 UUID `14BE04EB-AF49-497E-B36A-B078B2F7C5E8`。`git check-ignore -v` 命中 `firmware/engine_fix_r2/.gitignore:1:/local/`，见 [ignore.log](local/ignore.log)。理光数据、容器、固件切片、反汇编和生成物均在本任务 local。

任务起始记录 2,968 个输入摘要，包含 r1、resident_v32、官方固件和原审查证据。最终重新核对，详见 [scope.json](local/scope.json)。只向 `firmware/engine_fix_r2/` 写文件；共享检出原有 tracked 修改和其它有效未跟踪工作保留。没有删除或移动其它目录，没有访问存储卡、操作相机、刷机、启动子代理、sleep、轮询任务状态、安装包、commit 或 push。长命令后台执行后读取终态，未建立状态轮询循环。

未知仍包括实际 M32R 执行、堆碎片、真实原生 UI 时序、官方 rename 的完整目标存在语义和物理持久化行为。主机通过不等于设备验收。
