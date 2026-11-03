# gen 118：ADJ 实时预览与选中标记

两项 UX 已在三个单元的 native harness 路径验证：移动即预览，ADJ/OK/半按离开保留所见；黄点采用允许的次选，最终重画与高亮重合，未彻底去掉。只改配方包，resident 不变。每格实计 122–227 次 RPC、220–412 B 单元写入，CPU 条件估计 12.3–46.5 ms，另加真实 RPC 和显示等待。遗留风险：持续断链仍可留下混合行，须重启；H08 前的旧标记中间绘制和实机时延未验收。这是离线候选，未达到“任何故障都不混合”的完整验收。

本报告区分官方机器码静态证据、执行最终机器码的 native harness 证据和条件耗时估算。没有访问相机或存储卡，也没有实机/LCD/断电验收。

## 1. 输入与交付身份

| 对象 | SHA-256 或固定身份 |
| --- | --- |
| 官方 `gxr-151.zip` | `3705984b8433c40d2ed4fd2600c11f03ed8a6de7dbe7f66efd38ee5ca15fc898` |
| ZIP 内官方 `ilaunch3`，仅作静态分析 | `da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7` |
| v3.6 `ilaunch3`，卡包沿用 | `50720c80696ca88f25dc25a85285acd0e0f19906e1d7da1dd404f6cc243f9008` |
| v3.6 resident build id | `b779cc756a740506415ca5df8eb5c8f08e1b04ea9d8c4c614f7ae971e92b94f7` |
| v3.6 ABI | `d7387c3670059c325186de3af1b3d5c6` |
| gen 117 输入 DAT | `35ce20ac843764b9cdd452785683ebf99004c47b77ae90720c2e3dc716c31211` |
| gen 118 候选 DAT | `e557c7266c05ea5b997bd369b505ea364c660e87aef07180c784207ffd0f3f2d` |
| gen 118 engine ELF | `108bdd2b6546df7ebb0f58cf165e5c86864f293e17aa49b76fef06ac5c067383` |

新树为 `firmware/engine_v39_ux`，从 `engine_v38_b36` 复制。生产 C/H 仅改 adapter、eng_core.c、eng_core.h、eng_internal.h 四个文件；resident 源码和二进制均未修改。独立解包比较确认 48 份配方展开数据、record、metadata、3 份单元 map 和 pin 与 gen 117 相同。[产物身份](local/artifacts/identity.json)、[数据比较](local/artifacts/data-equality.json)、[生产源码 diff](local/artifacts/production-source.patch)。

新树非 local 的 C/H/S/Python/链接脚本另有 [source-manifest.json](local/artifacts/source-manifest.json)，用于复查本代实际源码与构建入口。旧树、旧卡包和官方输入由冻结清单保护。

DAT 为 56,840 B，距本轮 65,536 B 门限余 8,696 B；engine 47,288 B，BSS 9,716 B。代码比 gen 117 增加 1,340 B，新增确认/预览状态使 BSS 增加 64 B。链接及 PIC 重定位检查通过，使用未改的 v3.6 trust。[构建布局](../../firmware/engine_v39_ux/candidate/local/full-r13/layout.json)、[两代预算比较](local/artifacts/budget.json)。

冻结清单覆盖 9,011 个原有文件；最终复查全部未变。[初始清单](inputs-before.json)、[复查](inputs-verification.json)、[SSD 身份](volume.json)。写入仅在获批的两个新 firmware 目录和本研究目录。

使用默认 v3.6 trust 再构建一次，DAT 和 ELF 均逐字节相同：[复现结果](local/artifacts/reproducibility.json)。raw key 0x17 的 down 翻译也从本轮官方字节独立核对为 `0x0E+29=0x2B`：[地址及字节](local/native/adj-key-translation.json)。

## 2. 黄点从哪里来，为什么选跟随高亮

以下地址来自已校验 ZIP 的官方 `ilaunch3`，使用段表换算文件偏移后直接提取。每个窗口均记录 VMA、文件偏移、字节 SHA 和 objdump 命令：[窗口索引](local/native/index.json)、[重取脚本](collect_native.py)。

| 地址 | 机器码动作 | 证据 |
| --- | --- | --- |
| `0x20287158` | Image 列表构造器把 r8 写到状态 `+9`，全局即 `0x2022F725`。 | [constructor](local/native/constructor.txt) |
| `0x20287164` | 同一 r8 随后写到 `+10`，即高亮行 `0x2022F726`。这两次写均在 H01/H02 返回后。 | 同上 |
| `0x201FFABC`、`0x201FFAD8`、`0x201FFAF8` | 原生列表绘制器读取状态 `+9` 计算标记位置；高亮另取 `+10`。 | [list-render](local/native/list-render.txt) |
| `0x201FFB20..28` | 检查标记 Y 是否落在可绘区域内。 | 同上 |
| `0x201FFB2C..38` | 把标记绘制参数交给 `0x201D7B88`。 | 同上 |

八行时标记 Y 为顶部加 `38 × (marker − 1)`。把 marker 置 0 会在这条路径被边界检查跳过，不会索引配方数组；但构造器在当前 container hook 之后又把选中行写回 `F725`。H01 写 0 不能稳定隐藏首帧，H02 skip 的续行仍经过这两次写。把共同的 r8 置 0 又会把高亮置成 0，不是安全方案。

因此本轮选已获准的最小次选：保持合法的 1..8，使用 resident 已有 `RV_UI_LIST` op 3 重画，让 F725 和 F726 都等于当前行，不增 resident 字节。冷启动两者均为 04。

还有一个容易漏掉的时序：原生上下键先画列表，随后才进 H08。仅改 F725 的 RAM 值，屏上的标记仍可能停在上一行。当前 H08 先通过 op 3 重画，再写单元；失败补偿改变目标行时再重画一次。矩阵在绘制调用点记录 `marker/cursor/Y`，核对每次完整导航最后一次绘制的 marker 和 cursor，而非只检查内存字节。

限制：H08 前的原生首次绘制仍可能短暂含上一行的标记，本轮不能在 container 中阻止这个更早的绘制。最终重画在 RPC 前发生；LCD 是否把中间帧显示出来未测。没有使用越界标记、修改原生 draw 代码或改 resident。

## 3. ADJ、OK、半按快门和取消的原生语义

| 输入/状态 | 原生路径 | 结论 |
| --- | --- | --- |
| ADJ `0x2B` | state 56 表项 `0x203764D4`；第一处理列 `0x202C2ABC`，第二列 `0x202B76EC`。 | ADJ 与 MENU/OK 进入同一确认处理器。 |
| MENU/OK `0x23` | 表项 `0x20376510`，同上两列。 | 本机这条逻辑事件是 MENU/OK；没有独立的“MENU 取消”分支。 |
| Image 活动项 8 | `0x202C2D54` 分支；调用 `0x20265824` 读取 `0x2037F2FE`。值为 1 时 `0x202C2D70` 调 H07，keep=1，返回地址 `0x202C2D74`；其余 `0x202C2D80` 调 H07，keep=0，返回 `0x202C2D84`。 | keep 控制是否保留菜单，不表示确认/取消。ADJ 与 OK 都可走两种 keep。 |
| 半按相关事件 `0x29` / `0x63` | state 56 表中第一列 `0x2029FDC4`，第二列 `0x202BD724`。Image 活动 8 的第二列在 `0x202BD88C` 调 H07，keep=0，返回 `0x202BD890`；第一列可经 `0x202BE978`，在 `0x202BEA50` 调 H07，keep=0，返回 `0x202BEA54`。 | H07 的调用点不限于旧的两个确认地址。 |
| 原生 Image setter | `0x202871D8` 起，使用 F726 的高亮行。 | 不以 F725 的旧标记作为退出选择，不存在恢复入口前行的明确取消语义。 |

证据：[state56-events](local/native/state56-events.txt)、[confirm-dispatch](local/native/confirm-dispatch.txt)、[keep flag](local/native/native-keep-flag.txt)、[half first](local/native/half-first-handler.txt)、[half second](local/native/half-second-handler.txt)、[half helper](local/native/half-commit-helper.txt)、[setter](local/native/constructor.txt)。已有按压输入见证为 raw 消息 `+6=0x700B,+12=0x17,+16=1` 经 `0x202B0C14 → 0x202AFE98` 和表项 `0x20375F4C` 翻译成 event 0x2B；本轮重新提取了 [translator](local/native/key-translator.txt)、[key table](local/native/physical-key-table.txt)、[state5 ADJ 表项](local/native/state5-adj-entry.txt)，既有回放说明见 [boot_inert_v34](../boot_inert_v34/REPORT.md)。按键的物理命名沿用原生行为与本地官方手册的对应关系；逻辑事件路由已核实，电气扫描、长按/释放及实机按键投递未验收。本地官方手册 `research/phase0_drill/evidence/gxr-manual-extracted.txt` 的 ADJ Shutter Confirmation 段也说明 ADJ/MENU-OK 选择，以及开启快门确认后的高亮项选择。

gen 117 的 `ig_event` 在已链接机器码偏移 `0x8130..54` 检查 raw 必须等于 `0x23`，caller 必须为 `0x202C2D74` 或 `0x202C2D84`；正常列表在 `0x8284..82B0` 才调用 `select_cached`。ADJ raw=0x2B 因而漏掉，H08 也只移动光标，不应用配方。[原 gen 117 ELF 反汇编](local/native/gen117-event.txt)。本轮还执行了实际 gen 117：冷开 04，滚到 08 的每步都是 0 RPC/0 preview，ADJ 后再开仍为 04。[基线结果](local/runs/baseline-50mm.json)。

gen 118 把所有由 resident 接受的自有列表 H07 都作为确认。ADJ、OK、快门退出保留已经完整预览的行；keep=1 保留菜单，keep=0 关闭菜单。没有新增普通退出回滚。若原生退出绕开 H07，下次 H01 接受已验证的 live preview，再用该行构造菜单，保持可见配方和下次高亮一致。

三单元额外执行了 `0x29` 与 `0x63` 两种快门事件的两列 native 处理器，均观察到 overlay 从 32 撤为 0，完整 03 保持不变；该运行条件下没有进入 H07。退出后 live 立即生效，confirmed 元数据在下一次 H01 才接受它。重开均为高亮 03、confirmed 03，文件写入为零。[快门执行结果](local/runs/exits-50mm.json)。活动项地址是 `0x205D9BF8`；注意 `seth 0x205E` 配合有符号偏移 `-25608` 也指向这个地址。原生 item-8 arm 为 `0x202BA384 → 0x202BA3BC..C4`，见 [image-item-arm](local/native/image-item-arm.txt)。

退出时 v3.6 的 `rv_ui_abort` 会恢复原生七项页的 RAM 字节，这时菜单已隐藏，F726 不再是配方页的可见高亮。验收比较退出前可见配方行、退出后实际单元数据和重开后的配方高亮；不把已撤下的原生页行号当作配方编号。

03 的黑白效果来自三单元全部 96 B chroma 行为零，原生模式仍为标准 1；本轮独立核验这段不变数据，并在执行后比对实际单元九行。[黑白数据检查](local/artifacts/monochrome.json)。没有用 getter 固定返回 1 来掩盖模式变化。

## 4. 预览、失败补偿和串行处理

正常 H08 顺序是：验证行 → 重画同位置黄点/高亮 → `compute` → `RV_SETTINGS` 取 token → delta `deep` 写单元 → 写设置 → `RV_PREVIEW` → 释放 token → 发布完整 live 状态。成功后状态为 BROWSING/previewing，尚未把 confirmed 改成它。

OK/ADJ 对同一行直接接受完整 live 的配方与实际微调，只更新元数据，不重复 RPC 或预览，并把这一实际值同步到 RAM cache。这样，补偿退回纯 04 后，确认键不会把此前给 04 缓存的微调再次应用。冷开尚无已应用预览时才从默认 cache 应用当前行。confirmed 保存配方 identity 和当时的 RAM 微调；普通退出确认当前显示行。冷启动不读 GXLS/GXTS，光标从 04 开始，Fn2 值只保存在本次启动的 RAM。

resident 的 inflight 和 adapter 的 active 拒绝重入。一次 H08 返回前再读实际 F726；若 RPC 期间原生另一上下键改变了它，本次调用串行应用最后的行。测试用共享 RAM、独立寄存器和任务栈的第二 CPU 上下文执行真正的 native 上下键，验证嵌套时不进入 engine，RPC 最大嵌套深度为 1，外层最终应用最后停留行。

失败不能信任正常 delta 的 live 账本。补偿重新检查身份和 epoch，取最后 confirmed；从未确认则取纯 04；强制写全九行并逐 word 读回，同时保留奇数边界相邻字节，重核 T，再写设置、刷新取景。补偿目标成为高亮行。若该次补偿也失败且绑定仍可验证，再强制写完整纯 04；这会丢掉本次选择和之前的确认/微调选择。再失败则停用 engine，不清除 uncertain。

这次执行发现并修正了以下问题，反例没有删除：

1. op 5 结束 RPC 在写入结果不确定时返回 `RV_UNCERTAIN`，旧 `end()` 同时丢弃绑定，导致补偿未开始。现在只对此返回保留绑定；新事务重新校验身份和 epoch，真正 stale/owner/transport 失败仍不允许恢复写。
2. 强制读回 B5 跨越 `0x2012FFFC → 0x20130000`。V 命令必须使用低 16 位并在跨页处重新 X；修正前的读回把大于 65535 的地址传给 V。现在逐 word 计算地址和页。
3. 原生上下键用 `0x205A2944` 缓存递增下一行，再在 `0x201CA774` 写入 `*(0x205A293C)+10`，并非从屏幕行号重新开始。Fn2 换成数值列表时只更新了画面和状态行，没有同步这个缓存；从配方 05 打开数值中点 06 后，首个向下键仍把旧缓存 05 增为 06，draft 就保持 0。读取 snapshot 不能解决它，已用写入轨迹推翻这一中间改法。最终 container 在成功发布列表/重画后同步该缓存；仅当缓存的 state 指针等于官方 Image 全局状态或本 resident 的 ui_block 时才写入，行号保持在该列表已验证范围内。Fn2 移动仍使用 H08 的实际行号。失败补偿改变高亮后也同步缓存，避免下一次滚动从失败行起算。[原生缓存递增与写回](local/native/native-view-cursor.txt)、[原生上下键](local/native/cursor-down.txt)、[H08 调用点](local/native/cursor-hook-caller.txt)、[保留的早期 Fn2 反例](local/commands/fn2-probe50mm-r2/stderr.txt)。
4. 半按退出 Fn2 也会绕过 H07；新的配方列表 H01 因此清掉旧 panel.open/input_enabled，避免下一次上下键仍被解释为数值微调。未接受的数值 draft 不应用，已经接受的 RAM 微调保留。

保留的 `local/runs/*-<hash>.json` 和 `local/commands/` 包含早期失败、测试前提修正及最终重跑；旧 SHA 的 PASS 不作为本代候选验收。Fn2 独立参考也改为先把未启用的行归一化为 stock，再计算微调，不能在微调后覆盖掉它。最初把 Fn2 失败判断为仅有参考错误不成立；实际 draft=0 以及 native 写入 06 而非 07 的反例促成了上述缓存修正。不能把零文件写入或正常返回当成微调已经应用。

缓存修正阶段的 50mm 定向复核（中间 SHA 见结果，最终验收以完整矩阵为准）已观察到单个向下键变为数值行 07，实际 tweak 为 `[1,0,0,0,0,0,0,0]`，B5 与独立 contrast +1 结果逐字节一致；继续通过预览交错、失败补偿，以及 Fn2 半按退出后重新滚动配方。[完整定向结果](local/runs/edges-50mm.json)、[独立 B5 比较](local/artifacts/fn2-reference-correction.json)、[最终 ELF 的缓存同步代码](local/artifacts/cursor-cache.asm.txt)。

无法保证的边界：如果单元在写了一部分后持续拒绝通信，或身份/链路丢失，container 无法把剩余字节送达。持续失败的负例已在 native 模型复现：第 16 次 RPC 在设备执行后返回错误，其后每次 RPC 都失败，engine 停在 uncertain，实际行不是完整 04，须重启。[持续故障反例](local/runs/persistent-fault-50mm.json)。因此“任何失败都绝不残留混合状态”没有做到；本候选通过的是后续通信可恢复时的完整补偿，不是原子事务。换 resident 也不能向持续不响应的单元送达剩余字节。实机断线与断电未验收。

## 5. native 验收矩阵

最终同一 SHA 的三个单元完整矩阵均通过。测试从真实原生列表构造器、上下键和确认/快门处理器进入，执行既有 v3.6 resident 和最终 DAT 中的 M32R 机器码；没有直接写 native 光标、活动项或 resident 状态。必要的 Image item-8 arm 也执行原生代码。移除了固定返回 1 的 `0x20271FEC` 替身；路径调用 getter 时执行原生代码，访问计数保存在结果中。

设备边界仍是 harness：单元 RPC、文件系统、字体/图形与预览提交是模型，主机提供合成 settings 输入。验证实际 RPC 内存的九行、T、模式、应用后的 WB；Fn2 的 contrast +1 由独立 Python 算术算期望值。检查每个阶段文件 create/write/rename/delete/write-open 都为 0。冷开检查 stock 九行、T、mode 和零单元写，合成初始 WB 不构成实机白平衡冷启动证据。

| 序列 | A12 50mm | A12 28mm | MOUNT A12 |
| --- | --- | --- | --- |
| 冷启动 04；标记与高亮均 04；未写单元 | PASS | PASS | PASS |
| 首次预览写到单元后返回错误；恢复完整 04 | PASS | PASS | PASS |
| 实时预览 03；ADJ 确认；再开高亮 03 | PASS | PASS | PASS |
| 实时预览 08；OK 确认；再开高亮 08 | PASS | PASS | PASS |
| 半按离开；保留 03；再开 03 | PASS | PASS | PASS |
| 41 次连续上下移动；逐步核对最终绘制和完整配方 | PASS | PASS | PASS |
| 确认 03 后，第 16/140 次 RPC 失败；失败前/设备已执行后返回错误 | PASS | PASS | PASS |
| 第一次补偿也失败；退回完整纯 04 | PASS | PASS | PASS |
| RPC 中插入另一个 native 上下键；串行收敛到最后行 | PASS | PASS | PASS |
| Fn2 contrast +1、ADJ、交错预览和失败恢复 | PASS | PASS | PASS |
| 重建冷启动；04、零单元写、无上次 RAM 微调 | PASS | PASS | PASS |
| 首次保留原生 7 行，ready 后第二次发布 8 行 | 不适用 | PASS | 不适用 |

额外边界复核：曾给 04 保存 contrast +1 后，双故障退回纯 04，再按 ADJ 不新增 RPC/refresh，仍为纯 04；[结果](local/runs/fallback-fn2-50mm.json)。

明确取消键：未发现，不添加取消回滚。旧整体脚本 `run_v35.py` 的 diag 0x307 假设未作为本轮通过标准。

28mm 的“冷开 04”指八行配方页成功发布后。ready 尚未建立时第一次仍是原生七项页，第二次才有八行；第一张原生页保持原厂选择与标记，不提前应用配方。

主矩阵原始结果：[50mm](local/runs/matrix-50mm.json)、[28mm](local/runs/matrix-28mm.json)、[MOUNT](local/runs/matrix-mount.json)。额外的真实快门路径：[50mm](local/runs/exits-50mm.json)、[28mm](local/runs/exits-28mm.json)、[MOUNT](local/runs/exits-mount.json)。脚本：[native_ux.py](native_ux.py)、[native_exits.py](native_exits.py)。

## 6. 每格成本与延迟估计

独立计量三个单元共 96 次导航，覆盖 16 种相邻转移，每单元每种重复两次；另有功能矩阵的 123 次连续滚动。每步非 NOP 指令为 2,141,922–3,680,818，基础周期为 2,835,538–4,879,838。计数范围是完整 native 上下键，包括 H08/resident 校验、CRC、重画和应用代码。功能矩阵沿用原 harness 的数学等价 CRC 加速，它在重开菜单时会重新装入；因此不使用那份矩阵的指令数估时。独立计量在每个移动边界移除 engine CRC 替身，执行真实 bit loop，`crc_accelerated_calls` 必须为 0。RPC 数为实际模型调用，单元写字节为 W 次数乘 2；它不是文件写入量。原始计量：[50mm](local/runs/perf-50mm.json)、[28mm](local/runs/perf-28mm.json)、[MOUNT](local/runs/perf-mount.json)。

<!-- MEASURED_COSTS_BEGIN -->
| 行 | RPC 次数 | 单元写入 B | 非 NOP 指令 | 基础周期 | CPU 条件估计 ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| 01→02 | 188 | 344 | 3103739–3109487 | 4113661–4120855 | 17.9–39.2 |
| 01→08 | 188 | 344 | 3103702–3109393 | 4113596–4120781 | 17.9–39.2 |
| 02→01 | 188 | 344 | 3103699–3109382 | 4113569–4120794 | 17.9–39.2 |
| 02→03 | 188 | 344 | 3103373–3109120 | 4113499–4120822 | 17.9–39.2 |
| 03→02 | 188 | 344 | 3103683–3109440 | 4113585–4120792 | 17.9–39.2 |
| 03→04 | 188 | 344 | 3104712–3110482 | 4115072–4122340 | 17.9–39.3 |
| 04→03 | 188 | 344 | 3103344–3109118 | 4113462–4120824 | 17.9–39.2 |
| 04→05 | 188 | 344 | 3103602–3119388 | 4113610–4134216 | 17.9–39.4 |
| 05→04 | 188 | 344 | 3104629–3110363 | 4114957–4122173 | 17.9–39.3 |
| 05→06 | 188–227 | 344–412 | 3103594–3680818 | 4113488–4879838 | 17.9–46.5 |
| 06→05 | 188–225 | 344–412 | 3103591–3648348 | 4113599–4837142 | 17.9–46.1 |
| 06→07 | 188–225 | 344–412 | 3103749–3648531 | 4113673–4837241 | 17.9–46.1 |
| 07→06 | 188–227 | 344–412 | 3103493–3680735 | 4113347–4879723 | 17.9–46.5 |
| 07→08 | 122 | 220 | 2141984–2147675 | 2835608–2842793 | 12.3–27.1 |
| 08→01 | 188 | 344 | 3103753–3109418 | 4113643–4120842 | 17.9–39.2 |
| 08→07 | 122 | 220 | 2141922–2147662 | 2835538–2842674 | 12.3–27.1 |
<!-- MEASURED_COSTS_END -->

周期模型沿用 [cpu_speed_r1](../cpu_speed_r1/REPORT.md)：非 NOP 各 1，串行 NOP 各 1，乘法额外 2，成立控制转移额外 2；并行 NOP 不加。此模型不含指令/数据访存等待、native RPC 边界内部代码与通信等待、RTOS 调度和 LCD/preview 等待。不能用 Python 回放墙钟当相机速度。

tick 的 1 ms 静态语义见上述报告的原生 RTOS 时间链、`msec` 直接输出和 `1000/Δtick` 吞吐计算；本轮没有实机 tick 样本。CPU 换算仅采用同报告的工作假设 150–230 MHz、可用份额 70%–100%，不是确认了 GXR 主频。

成本轮使用默认零微调，覆盖八行的双向相邻转移；表中范围是这些输入的观察值，不是任意 Fn2 组合或跨行跳转的上限。

总延迟应按 `已计 CPU 时间 + RPC 次数 × 平均 RPC 耗时 + 预览/显示等待` 理解，其中 RPC 耗时包括 API 内部执行和通信等待。按上述 CPU 情景、忽略显示等待，平均 RPC 耗时达到约 2.00 ms 就可使总延迟超过 0.5 秒；本轮没有数据排除这种情况。已给出的可选折中是停留约 100–150 ms 才预览，或连续输入只合并到最后一行；本候选仍按每格同步预览，未擅自改成交互延时策略。

补偿属于异常慢路径，本次记录为 555–680 次 RPC、526–758 B W 尝试；包含强制全行写入及逐 word 读回，不能套用正常滚动延迟。完整计数见 [costs.json](local/artifacts/costs.json)。

## 7. 构建、复核与卡包

本代唯一构建入口是新树的 `candidate/build118.py`，旧树不写入：

```sh
/usr/bin/python3 -I -B firmware/engine_v39_ux/candidate/build118.py \
  --resident-trust firmware/resident_v36/local/resident/trust.json
/usr/bin/python3 -I -B research/ux_preview_dot_r1/target_layout.py
/usr/bin/python3 -I -B research/ux_preview_dot_r1/native_ux.py 50mm --matrix
/usr/bin/python3 -I -B research/ux_preview_dot_r1/native_ux.py 28mm --matrix
/usr/bin/python3 -I -B research/ux_preview_dot_r1/native_ux.py mount --matrix
/usr/bin/python3 -I -B research/ux_preview_dot_r1/native_exits.py 50mm
/usr/bin/python3 -I -B research/ux_preview_dot_r1/native_exits.py 28mm
/usr/bin/python3 -I -B research/ux_preview_dot_r1/native_exits.py mount
/usr/bin/python3 -I -B research/ux_preview_dot_r1/native_fallback_fn2.py
/usr/bin/python3 -I -B research/ux_preview_dot_r1/native_persistent_fault.py
/usr/bin/python3 -I -B research/ux_preview_dot_r1/native_ux.py 50mm --perf
/usr/bin/python3 -I -B research/ux_preview_dot_r1/native_ux.py 28mm --perf
/usr/bin/python3 -I -B research/ux_preview_dot_r1/native_ux.py mount --perf
/usr/bin/python3 -I -B research/ux_preview_dot_r1/artifacts.py --package
/usr/bin/python3 -I -B research/ux_preview_dot_r1/freeze.py
```

卡包已生成于 `firmware/package_v36_g118/SD_ROOT`：新 DAT、原 v3.6 ilaunch3、从固定官方 ZIP 直接读出的另外 28 个文件，共 30 个文件。封包脚本逐字节比较官方成员，逐项核验绑定、DAT CRC、ELF payload、配方数据与最终测试 SHA，`CARD_SHA256SUMS` 对全部 30 个文件自检。[封包证据](local/artifacts/package.json)、[逐项校验](local/artifacts/card-check.stdout.txt)。

交付文件：[GXRCE.DAT](../../firmware/package_v36_g118/SD_ROOT/GXRCE.DAT)、[CARD_SHA256SUMS](../../firmware/package_v36_g118/CARD_SHA256SUMS)。剩余验收为实机 LCD 中间帧、真实 RPC/显示耗时、断电及持续通信故障的恢复边界；本轮未访问设备。

研究目录 `SHA256SUMS` 覆盖除清单本身之外全部文件，包括脚本、初始冻结清单、历史反例、原生窗口、最终矩阵、构建产物快照和报告。完整自检为 4,643/4,643 OK；原有保护输入 9,011/9,011 未变，卡包为 30/30 OK。[封存检查](local/artifacts/seal-checks.json)。复核命令为 `/usr/bin/python3 -I -B research/ux_preview_dot_r1/seal.py`，它会重新检查证据、链接和全部校验和。
