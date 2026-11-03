可以接受。

本轮关闭 P1-CG01。95 个改码符号对应 88 个真实函数区间，全部按题定 A、B、C 关闭，未找到可达行为差异。分类为 70 个 A、10 个纯 B、5 个 C+B、10 个题定已审文件家族 C。同地址别名逐名列出。

审查只覆盖 gen 116 与 gen 117 的冻结容器机器码。实际 v3.6 绑定包沿用题目已核实的相同 engine 事实。本轮未操作相机、卡或刷机，未启动子代理，所有新增文件均在本目录。Python 均使用 `/usr/bin/python3 -I -B`。

1. 输入与证据边界

| 对象 | SHA-256 或身份 |
| --- | --- |
| gen 116 DAT | `1e033dfbcc3ca0bec0e1e5befbdb5579950e9aa8aacfbfd56f8c7342b9a97864` |
| gen 117 DAT | `4f5eeaffdfc4df77d9482887b827fe8ec73e7857b13ea76348e3e49c874d0b5a` |
| 实际绑定 DAT | `35ce20ac843764b9cdd452785683ebf99004c47b77ae90720c2e3dc716c31211` |
| gen 117 engine | 45,948 B；`548715f68ec9731423d6e1e36290fbcc3372de844cc0861ff5cbb859ccbf64e5` |

题目已核实的输入身份、r1 九项 B、容器有意改动裁决直接复用。本轮另冻结并复核 2014 个输入文件，前后哈希全部相同，见 [input-integrity.json](input-integrity.json)、[input-before.json](input-before.json)、[input-after.json](input-after.json)。文中 PC 使用 r1 冻结 ELF 地址。

2. A 的翻译验证

两代各用 r1 原链接命令重放，增加 `-save-temps=obj -Wa,-L -Wl,--discard-none`，全部输出和临时文件留在本目录。新增的局部标签没有改变 engine 的任何字节，见 [labels116/command.json](labels116/command.json)、[labels117/command.json](labels117/command.json)。读取完整符号表时保留不同输入对象的同名 `.LC` 标签，避免 Python 字典按名称覆盖标签。

这使匿名常量的边界来自真实汇编标签。每个匿名常量和只读对象都比较到下一个符号或 section 末尾，包含填充字节。BSS 对应对象的尺寸相同，初始字节全零。164 个 A 类地址目标逐项通过。唯一的 `rv_api+16` 数据重定位是 `R_M32R_32_RELA` 函数指针，递归验证其目标都是已关闭的 `rv_call`；其余 156 个数据字节逐字节相同，没有把不同普通数据当作地址抹掉。证据为 [object-spans.json](object-spans.json) 和各函数 `proof-A` 文件。

非 NOP 指令按执行顺序逐条比较操作码、寄存器和非地址立即数。只转换 ELF 明列的 GOTOFF、GOTPC 字段以及逐目标核对的分支位移。每个 GOTOFF_LO 都有独立目标证据，GOTPC 高低字段都重新计算到 image+0x100。每个真实代码字节都被解码核对，没有未解码空洞。

A 类两代共核对 5718 个双 16 位字的模式位，原始字节与 ELF 一致。所有并行 packet 都只含一条有效指令和 NOP，没有两条有效指令并行的情况；填充全部是 NOP。顺序 packet 保留有效指令的原顺序。直接分支及 call 返回位置逐一映射到相同的下一条有效指令。

`rv_call` 的两个 switch 表分别有 14 和 13 项，108 B 表内容相同，27 个目标都落到对应有效指令。A 类栈调整和 push/pop 序列相同，保存寄存器集合相同。30 个同码符号也独立核对了内部控制流，另核对 23 个同码 native、IRQ 汇编入口。证据为 [packet-modes.json](packet-modes.json)、[switch-tables.json](switch-tables.json)、[identity-leaves.json](identity-leaves.json)。

调用依赖按从叶节点到调用者的顺序关闭，间接调用按真实赋值连接到 `rv_call`、`core_call`、`grain_snapshot`、`address`、`pn_native_from_seed`。148 个符号节点都关闭，无未解析目标，本次没有非平凡递归分量。函数地址字段也纳入依赖，见 [dependency-graph.json](dependency-graph.json)、[function-closure.json](function-closure.json)。

`path` 的 `names.0` 完整区间为 91/90 B，`ig_init` 的单位名称表完整区间为 25/24 B。差异在尾部填充，严格的 A 条件未通过，因此这两个函数改由 B 关闭，没有缩小比较范围来签 A。

3. 新增 B 与五个混合函数

六项各执行 10,000 组随机输入加 64 组明确边界输入，共 60,384 对。比较返回值、恢复后的 r8–r15，以及按对象映射的全部公共字节写入历史。临时栈按内部帧处理，恢复寄存器和 sp 必须相同。五个混合函数的 C 部分只按下表投影，剩余编译改码执行冻结 M32R 正文，callee 的共同边界在 [differential.py](differential.py) 明列。

| 函数 | 116 分支结果覆盖 | 117 分支结果覆盖 | 执行结果 |
| --- | ---: | ---: | --- |
| `finish` | 14/14，100.00% | 8/8，100.00% | [10,000 + 64 组一致](finish-results.json) |
| `ui_finish` | 12/12，100.00% | 6/6，100.00% | [10,000 + 64 组一致](ui_finish-results.json) |
| `ig_event` | 40/190，21.05% | 38/38，100.00% | [10,000 + 64 组一致](ig_event-results.json) |
| `ig_init` | 80/122，65.57% | 80/122，65.57% | [10,000 + 64 组一致](ig_init-results.json) |
| `ig_menu` | 41/184，22.28% | 47/72，65.28% | [10,000 + 64 组一致](ig_menu-results.json) |
| `path` | 40/40，100.00% | 40/40，100.00% | [10,000 + 64 组一致](path-results.json) |

上表是原始正文覆盖率。所有未覆盖结果在 [branch-closure.json](branch-closure.json) 逐 PC 标明 C 片段或不可达理由，没有未解释项。旧版 `ig_event` 去掉两个 C 片段后，20 个剩余条件分支的 40 个结果全覆盖。`ig_menu` 剩下的四类未覆盖结果是 install 已固定返回 2、两次可见行数保持一致，以及冻结 record 全部 occupied=1。

`ig_init` 的不可达结果来自私有加载租约、gate 的布局不变量、首次初始化状态、snapshot 成功条件，以及本次两份冻结容器的配方数据。这里的域是这两份不可变私有 image 和实际可变 resident/native 状态，未把任意改写过配方的其它 DAT 当作同一冻结程序。snapshot 异常版本、cmp_version 和未知名称的拒绝路径也已执行。

固定数据证据包括七段连续和尺寸、三份 stock entry CRC、三个 map+stock pin、48 个 style 和 occupied 字节及 384 组 metadata，见 [frozen-invariants.json](frozen-invariants.json)。两代最终机器码的 semantic 和 stock expansion 在三单元共六组实执行通过，CRC 使用精确 zlib 规格，其余语义和展开正文是真实 M32R，见 [frozen-helper-execution.json](frozen-helper-execution.json)。

| 混合函数 | C：批准的源码改动和机器切点 | 剩余编译改码的关闭方式 |
| --- | --- | --- |
| `finish` | `blackbox.c @@ -146,6 +146,7 @@` 令 `ig_bx_flush` 立即返回 0。原调用和控制分支随之删除。容器审查第 64、96、98 行说明黑盒缩减归属。 | B 运行原正文，共同 flush callee 设为无副作用返回 0，比较全部剩余 RAM 效果。栈帧 36→36 B。 |
| `ui_finish` | 同一 `ig_bx_flush` hunk。只去掉文件 flush，收尾状态清零仍执行。 | B，错误收尾、workspace 失败和普通返回均覆盖，栈帧 24→24 B。 |
| `ig_event` | `adapter.c @@ -344,25 +335,8 @@` 删除 GXTS 保存和失败回滚，留下 RAM draft commit。旧 ELF `0x69b8→0x6ba8` 只代入 `last_store=RV_OK` 后进入原 RAM commit。`@@ -301,6 +291,7 @@` 的 `remember_save` 直接返回，用第二个精确切点跳过旧文件片段。容器审查第 71、98 行已接受。 | B 从入口执行，剩余 draft→values、draft→committed、dirty/open/input、普通列表及收尾路径全部比较。原始 38/38 个新版分支结果全覆盖。栈帧 400→104 B，减少的是已删文件临时区，r8–r15 完整恢复。 |
| `ig_init` | `adapter.c @@ -417,7 +391,7 @@` 与 `@@ -433,7 +407,7 @@` 的两条能力常量 `0xF0000→0xE0000`，对应去掉 CAP_FILE_WRITE。容器审查第 106、110 行已接受。 | B 只投影 reply.capabilities 中明确删除的 `0x10000` 位，其余返回和写入全部比较。机器流另核实只有这两个非地址立即数不同；只读表尾部填充按 B 处理。栈帧 164→164 B。 |
| `ig_menu` | install 的 `@@ -154,6 +154,7 @@`、preload 的 `@@ -222,25 +223,13 @@`，以及 `eng_core.c @@ -328,13 +328,8 @@` 的冷启动 04 和旧 remembered cursor 删除。旧 install、cursor、remembered 覆盖点在 results 的 cutpoints 中逐项列出。metadata 首次默认值路径属于整段已审 preload 改动。容器审查第 72、98 行已接受。 | B 覆盖这些改动以外的 RAM 路径，包括隔离标记、安装尝试记账、workspace 新建与已有 lease、fresh/busy、行内容、已提交 cursor 和 list_bind 失败。栈帧 172→76 B，公共对象写入及 r8–r15 一致。 |

上表源码 hunk 的原文保存在 [C-source-hunks.patch](C-source-hunks.patch)，完整原件仍在 [../../firmware/engine_v38_ro/local/static/all-source-changes.patch](../../firmware/engine_v38_ro/local/static/all-source-changes.patch)。容器裁决原件为 [../review_g117_container/REVIEW.md](../review_g117_container/REVIEW.md)。切点没有改写机器码，只在模拟器边界投影已批准的 C 语义。

4. 每个改码符号的关闭表

| 函数 | 类别 | 证据文件 | 结论 |
| --- | --- | --- | --- |
| `a4_move` | A | [a4_move.json](proof-A/a4_move.json) | 已关闭；支持性 1,000 组一致。 |
| `binding` | A | [binding.json](proof-A/binding.json) | 已关闭；支持性 1,000 组一致。 |
| `card` | A | [card.json](proof-A/card.json) | 已关闭；支持性 1,000 组一致。 |
| `close_once` | A | [close_once.json](proof-A/close_once.json) | 已关闭；支持性 1,000 组一致。 |
| `core_call` | A | [core_call.json](proof-A/core_call.json) | 已关闭；支持性 1,000 组一致。 |
| `current.constprop.0` | A | [current.constprop.0.json](proof-A/current.constprop.0.json) | 已关闭；支持性 1,000 组一致。 |
| `descriptor.lto_priv.0` | A | [descriptor.lto_priv.0.json](proof-A/descriptor.lto_priv.0.json) | 已关闭；支持性 1,000 组一致。 |
| `descriptor.lto_priv.1` | A | [descriptor.lto_priv.1.json](proof-A/descriptor.lto_priv.1.json) | 已关闭；支持性 1,000 组一致。 |
| `descriptor.lto_priv.2` | A | [descriptor.lto_priv.2.json](proof-A/descriptor.lto_priv.2.json) | 已关闭；支持性 1,000 组一致。 |
| `descriptor.lto_priv.3` | A | [descriptor.lto_priv.3.json](proof-A/descriptor.lto_priv.3.json) | 已关闭；支持性 1,000 组一致。 |
| `descriptor.lto_priv.4` | A | [descriptor.lto_priv.4.json](proof-A/descriptor.lto_priv.4.json) | 已关闭；支持性 1,000 组一致。 |
| `disarm` | A | [disarm.json](proof-A/disarm.json) | 已关闭；支持性 1,000 组一致。 |
| `end` | A | [end.json](proof-A/end.json) | 已关闭；支持性 1,000 组一致。 |
| `eng_apply` | A | [eng_apply.json](proof-A/eng_apply.json) | 已关闭；支持性 1,000 组一致。 |
| `eng_current` | B | [eng_current-results.json](../review_g117_codegen/eng_current-results.json) | 已关闭；题定复用 r1，至少 10,000 组。 |
| `eng_entry.constprop.0` | A | [eng_entry.constprop.0.json](proof-A/eng_entry.constprop.0.json) | 已关闭；支持性 1,000 组一致。 |
| `eng_identity` | A | [eng_identity.json](proof-A/eng_identity.json) | 已关闭；支持性 1,000 组一致。 |
| `eng_visible_rows` | A | [eng_visible_rows.json](proof-A/eng_visible_rows.json) | 已关闭；支持性 1,000 组一致。 |
| `es_allocation` | A | [es_allocation.json](proof-A/es_allocation.json) | 已关闭；支持性 1,000 组一致。 |
| `es_range.constprop.0` | B | [es_range_constprop_0-results.json](../review_g117_codegen/es_range_constprop_0-results.json) | 已关闭；题定复用 r1，至少 10,000 组。 |
| `es_session.constprop.0` | A | [es_session.constprop.0.json](proof-A/es_session.constprop.0.json) | 已关闭；支持性 fixture 限制见第 5 节。 |
| `es_ui_abort.constprop.0` | A | [es_ui_abort.constprop.0.json](proof-A/es_ui_abort.constprop.0.json) | 已关闭；支持性 fixture 限制见第 5 节。 |
| `expect` | A | [expect.json](proof-A/expect.json) | 已关闭；支持性 1,000 组一致。 |
| `failure` | A | [failure.json](proof-A/failure.json) | 已关闭；支持性 1,000 组一致。 |
| `finish` | C+B | [finish-results.json](finish-results.json)；[分支裁决](branch-closure.json) | 已关闭；C 切分见第 3 节，B 为 10,000 + 64 组。 |
| `fresh` | A | [fresh.json](proof-A/fresh.json) | 已关闭；支持性 1,000 组一致。 |
| `gate_validate.constprop.0` | B | [gate-results.json](../review_g117_codegen/gate-results.json) | 已关闭；题定复用 r1，至少 10,000 组。 |
| `grain_snapshot` | A | [grain_snapshot.json](proof-A/grain_snapshot.json) | 已关闭；支持性 1,000 组一致。 |
| `gxr2_crc32` | B | [crc-results.json](../review_g117_codegen/crc-results.json) | 已关闭；题定复用 r1，至少 10,000 组。 |
| `gxr2_crc_zeroed.constprop.0` | A | [gxr2_crc_zeroed.constprop.0.json](proof-A/gxr2_crc_zeroed.constprop.0.json) | 已关闭；支持性 1,000 组一致。 |
| `gxr2_expand.constprop.0` | A | [gxr2_expand.constprop.0.json](proof-A/gxr2_expand.constprop.0.json) | 已关闭；支持性 1,000 组一致。 |
| `gxr2_parameter` | A | [gxr2_parameter.json](proof-A/gxr2_parameter.json) | 已关闭；支持性 1,000 组一致。 |
| `gxr2_raw_row` | A | [gxr2_raw_row.json](proof-A/gxr2_raw_row.json) | 已关闭；支持性 fixture 限制见第 5 节。 |
| `gxr2_semantic_validate` | A | [gxr2_semantic_validate.json](proof-A/gxr2_semantic_validate.json) | 已关闭；支持性 fixture 限制见第 5 节。 |
| `identity.constprop.0` | A | [identity.constprop.0.json](proof-A/identity.constprop.0.json) | 已关闭；支持性 fixture 限制见第 5 节。 |
| `ig_apply` | B | [ig_apply-results.json](../review_g117_codegen/ig_apply-results.json) | 已关闭；题定复用 r1，至少 10,000 组。 |
| `ig_bootstrap` | A | [ig_bootstrap.json](proof-A/ig_bootstrap.json) | 已关闭；支持性 1,000 组一致。 |
| `ig_bx_apply` | A | [ig_bx_apply.json](proof-A/ig_bx_apply.json) | 已关闭；支持性 1,000 组一致。 |
| `ig_bx_event` | A | [ig_bx_event.json](proof-A/ig_bx_event.json) | 已关闭；支持性 1,000 组一致。 |
| `ig_bx_receipt` | A | [ig_bx_receipt.json](proof-A/ig_bx_receipt.json) | 已关闭；支持性 1,000 组一致。 |
| `ig_bx_unit` | A | [ig_bx_unit.json](proof-A/ig_bx_unit.json) | 已关闭；支持性 1,000 组一致。 |
| `ig_event` | C+B | [ig_event-results.json](ig_event-results.json)；[分支裁决](branch-closure.json) | 已关闭；C 切分见第 3 节，B 为 10,000 + 64 组。 |
| `ig_init` | C+B | [ig_init-results.json](ig_init-results.json)；[分支裁决](branch-closure.json) | 已关闭；C 切分见第 3 节，B 为 10,000 + 64 组。 |
| `ig_menu` | C+B | [ig_menu-results.json](ig_menu-results.json)；[分支裁决](branch-closure.json) | 已关闭；C 切分见第 3 节，B 为 10,000 + 64 组。 |
| `ig_panel_abort` | A | [ig_panel_abort.json](proof-A/ig_panel_abort.json) | 已关闭；支持性 1,000 组一致。 |
| `ig_panel_event` | A | [ig_panel_event.json](proof-A/ig_panel_event.json) | 已关闭；支持性 1,000 组一致。 |
| `ig_panel_open` | A | [ig_panel_open.json](proof-A/ig_panel_open.json) | 已关闭；支持性 1,000 组一致。 |
| `ig_stop` | A | [ig_stop.json](proof-A/ig_stop.json) | 已关闭；支持性 1,000 组一致。 |
| `ingress` | A | [ingress.json](proof-A/ingress.json) | 已关闭；支持性 1,000 组一致。 |
| `io_close` | C | [source-closure.json](source-closure.json) | 已关闭；题定已审文件家族。 |
| `io_open` | C | [source-closure.json](source-closure.json) | 已关闭；题定已审文件家族。 |
| `io_read` | C | [source-closure.json](source-closure.json) | 已关闭；题定已审文件家族。 |
| `io_remove` | C | [source-closure.json](source-closure.json) | 已关闭；题定已审文件家族。 |
| `io_rename` | C | [source-closure.json](source-closure.json) | 已关闭；题定已审文件家族。 |
| `io_write` | C | [source-closure.json](source-closure.json) | 已关闭；题定已审文件家族。 |
| `list_bind` | B | [list_bind-results.json](../review_g117_codegen/list_bind-results.json) | 已关闭；题定复用 r1，至少 10,000 组。 |
| `mapped` | A | [mapped.json](proof-A/mapped.json) | 已关闭；支持性 1,000 组一致。 |
| `metadata.lto_priv.0` | A | [metadata.lto_priv.0.json](proof-A/metadata.lto_priv.0.json) | 已关闭；支持性 1,000 组一致。 |
| `metadata.lto_priv.1` | A | [metadata.lto_priv.1.json](proof-A/metadata.lto_priv.1.json) | 已关闭；支持性 1,000 组一致。 |
| `metadata.lto_priv.2` | A | [metadata.lto_priv.2.json](proof-A/metadata.lto_priv.2.json) | 已关闭；支持性 1,000 组一致。 |
| `open_read` | C | [source-closure.json](source-closure.json) | 已关闭；题定已审文件家族。 |
| `path` | B | [path-results.json](path-results.json) | 已关闭；10,000 + 64 组，40/40 分支结果。 |
| `pn_address` | B | [pn-results.json](../review_g117_codegen/pn-results.json) | 已关闭；题定复用 r1，至少 10,000 组。 |
| `pn_call` | A | [pn_call.json](proof-A/pn_call.json) | 已关闭；支持性 1,000 组一致。 |
| `pn_native_from_seed` | B | [native-results.json](../review_g117_codegen/native-results.json) | 已关闭；题定复用 r1，至少 10,000 组。 |
| `pn_request` | A | [pn_request.json](proof-A/pn_request.json) | 已关闭；支持性 1,000 组一致。 |
| `pn_ui_render.constprop.0` | A | [pn_ui_render.constprop.0.json](proof-A/pn_ui_render.constprop.0.json) | 已关闭；支持性 1,000 组一致。 |
| `read_exact` | A | [read_exact.json](proof-A/read_exact.json) | 已关闭；支持性 1,000 组一致。 |
| `remember_load` | C | [source-closure.json](source-closure.json) | 已关闭；题定已审文件家族。 |
| `remove_owned` | C | [source-closure.json](source-closure.json) | 已关闭；题定已审文件家族。 |
| `rpc.lto_priv.0` | A | [rpc.lto_priv.0.json](proof-A/rpc.lto_priv.0.json) | 已关闭；支持性 1,000 组一致。 |
| `rpc.lto_priv.1` | A | [rpc.lto_priv.1.json](proof-A/rpc.lto_priv.1.json) | 已关闭；支持性 fixture 限制见第 5 节。 |
| `rt_tone.constprop.0` | A | [rt_tone.constprop.0.json](proof-A/rt_tone.constprop.0.json) | 已关闭；支持性 1,000 组一致。 |
| `rv_call` | A | [rv_call.json](proof-A/rv_call.json) | 已关闭；支持性 fixture 限制见第 5 节。 |
| `rv_unit.constprop.0` | A | [rv_unit.constprop.0.json](proof-A/rv_unit.constprop.0.json) | 已关闭；支持性 fixture 限制见第 5 节。 |
| `same.constprop.0` | A | [same.constprop.0.json](proof-A/same.constprop.0.json) | 已关闭；支持性 1,000 组一致。 |
| `sd_current.constprop.0` | A | [sd_current.constprop.0.json](proof-A/sd_current.constprop.0.json) | 已关闭；支持性 fixture 限制见第 5 节。 |
| `select_cached` | A | [select_cached.json](proof-A/select_cached.json) | 已关闭；支持性 1,000 组一致。 |
| `slot_descriptor` | A | [slot_descriptor.json](proof-A/slot_descriptor.json) | 已关闭；支持性 fixture 限制见第 5 节。 |
| `snapshot` | A | [snapshot.json](proof-A/snapshot.json) | 已关闭；支持性 1,000 组一致。 |
| `sticky_put` | A | [sticky_put.json](proof-A/sticky_put.json) | 已关闭；支持性 1,000 组一致。 |
| `svc.constprop.0` | A | [svc.constprop.0.json](proof-A/svc.constprop.0.json) | 已关闭；支持性 fixture 限制见第 5 节。 |
| `t_read` | A | [t_read.json](proof-A/t_read.json) | 已关闭；支持性 1,000 组一致。 |
| `t_store` | A | [t_store.json](proof-A/t_store.json) | 已关闭；支持性 1,000 组一致。 |
| `transfer` | A | [transfer.json](proof-A/transfer.json) | 已关闭；支持性 1,000 组一致。 |
| `ui_call.constprop.0` | A | [ui_call.constprop.0.json](proof-A/ui_call.constprop.0.json) | 已关闭；支持性 fixture 限制见第 5 节。 |
| `ui_finish` | C+B | [ui_finish-results.json](ui_finish-results.json)；[分支裁决](branch-closure.json) | 已关闭；C 切分见第 3 节，B 为 10,000 + 64 组。 |
| `ui_prepare.constprop.0` | A | [ui_prepare.constprop.0.json](proof-A/ui_prepare.constprop.0.json) | 已关闭；支持性 fixture 限制见第 5 节。 |
| `ui_seed.constprop.0` | A | [ui_seed.constprop.0.json](proof-A/ui_seed.constprop.0.json) | 已关闭；支持性 fixture 限制见第 5 节。 |
| `unit_equal.lto_priv.0` | A | [unit_equal.lto_priv.0.json](proof-A/unit_equal.lto_priv.0.json) | 已关闭；支持性 1,000 组一致。 |
| `unit_equal.lto_priv.1` | A | [unit_equal.lto_priv.1.json](proof-A/unit_equal.lto_priv.1.json) | 已关闭；支持性 1,000 组一致。 |
| `verify` | C | [source-closure.json](source-closure.json) | 已关闭；题定已审文件家族。 |
| `warp` | A | [warp.json](proof-A/warp.json) | 已关闭；支持性 1,000 组一致。 |
| `workspace_close` | B | [workspace_close-results.json](../review_g117_codegen/workspace_close-results.json) | 已关闭；题定复用 r1，至少 10,000 组。 |
| `write_word` | A | [write_word.json](proof-A/write_word.json) | 已关闭；支持性 1,000 组一致。 |

5. 分级发现与支持性执行

P0：未发现可达行为差异。

P1-CG01：已关闭。没有具体函数遗留 A、B、C 无法关闭的证明缺口。

P2-S01：支持性 harness 仍有 14 项 fixture 限制。56 个 A 类函数各完成 1,000 组差分，全部一致。另 14 项在下面的共同边界发生相同 fault，未把这些域外模型失败计为产品反例或通过。题目明确此矩阵不构成证明前提，不阻断。完整 70 项状态见 [support-results.json](support-results.json)。

| A 类函数 | 未跑满的具体原因 |
| --- | --- |
| `es_session.constprop.0` | 现有通用 fixture 未满足此入口的 resident 地址或 ABI 前提；两代都报 `unmapped memory 0x20054700/4`。已完成 0 组。 |
| `es_ui_abort.constprop.0` | 现有通用 fixture 未满足此入口的 resident 地址或 ABI 前提；两代都报 `unmapped memory 0x2005479c/4`。已完成 0 组。 |
| `gxr2_raw_row` | 现有通用 fixture 未满足此入口的 resident 地址或 ABI 前提；两代都报 `unmapped memory 0x44000c08/1`。已完成 0 组。 |
| `gxr2_semantic_validate` | 现有通用 fixture 未满足此入口的 resident 地址或 ABI 前提；两代都报 `unmapped memory 0x0/4`。已完成 0 组。 |
| `identity.constprop.0` | 现有通用 fixture 未满足此入口的 resident 地址或 ABI 前提；两代都报 `unmapped memory 0x200547d4/4`。已完成 0 组。 |
| `rpc.lto_priv.1` | 现有通用 fixture 未满足此入口的 resident 地址或 ABI 前提；两代都报 `unmapped memory 0x14/4`。已完成 0 组。 |
| `rv_call` | 现有通用 fixture 未满足此入口的 resident 地址或 ABI 前提；两代都报 `unmapped memory 0x20054734/4`。已完成 10 组。 |
| `rv_unit.constprop.0` | 现有通用 fixture 未满足此入口的 resident 地址或 ABI 前提；两代都报 `unmapped memory 0x2040f804/4`。已完成 0 组。 |
| `sd_current.constprop.0` | 现有通用 fixture 未满足此入口的 resident 地址或 ABI 前提；两代都报 `unmapped memory 0x200547d4/4`。已完成 0 组。 |
| `slot_descriptor` | 现有通用 fixture 未满足此入口的 resident 地址或 ABI 前提；两代都报 `unmapped memory 0x19/1`。已完成 0 组。 |
| `svc.constprop.0` | 现有通用 fixture 未满足此入口的 resident 地址或 ABI 前提；两代都报 `unmapped memory 0x10/1`。已完成 0 组。 |
| `ui_call.constprop.0` | 现有通用 fixture 未满足此入口的 resident 地址或 ABI 前提；两代都报 `unmapped memory 0xc/4`。已完成 0 组。 |
| `ui_prepare.constprop.0` | 现有通用 fixture 未满足此入口的 resident 地址或 ABI 前提；两代都报 `unmapped memory 0x20054788/4`。已完成 0 组。 |
| `ui_seed.constprop.0` | 现有通用 fixture 未满足此入口的 resident 地址或 ABI 前提；两代都报 `unmapped memory 0x2022f720/4`。已完成 0 组。 |

支持性首轮的 helper stub 曾按名称区分，导致一边执行 primitive、另一边执行同机器码别名的替身。现已按机器码等价类统一，binding、descriptor、metadata 的最终各 1,000 组都一致。semantic 补验首次沿用 gate 专用 trust fixture，缺少 stock_sha256 的四字节 pin 标签，返回 GXR2_PIN；补入真实 trust_init 写入的字段后六组全部通过。初版输出及当前状态分类保留在 [model-diagnostics.json](model-diagnostics.json)，没有把初版结果算作已验证产品行为。

6. 复核入口与清单

以下命令只写本目录。重放使用受保护的 r1 输入和相同工具链，不需要相机、卡、网络或固件写入。

```sh
/usr/bin/python3 -I -B research/review_g117_codegen_r2/relink_labels.py 116
/usr/bin/python3 -I -B research/review_g117_codegen_r2/relink_labels.py 117
/usr/bin/python3 -I -B research/review_g117_codegen_r2/translation.py
/usr/bin/python3 -I -B research/review_g117_codegen_r2/invariants.py
# 对 finish、ui_finish、ig_event、ig_init、ig_menu、path 分别运行：
/usr/bin/python3 -I -B research/review_g117_codegen_r2/differential.py ig_event 10000
/usr/bin/python3 -I -B research/review_g117_codegen_r2/branches.py
/usr/bin/python3 -I -B research/review_g117_codegen_r2/closure.py
```

`SHA256SUMS` 覆盖本目录全部文件，按惯例不包含清单自身。最终校验命令为：

```sh
cd research/review_g117_codegen_r2
shasum -a 256 -c SHA256SUMS
```
