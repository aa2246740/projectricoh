不可以接受。

本轮没有找到 gen 117 可达的行为反例。拒绝的是“每个共享改码函数、每个可达输入已经证明等价”这项签字：只对九个重点函数完成了下述执行矩阵，其余共享函数尚缺逐调用点的可达域证明和题定的执行数量。不能把 79 个局部规范化流相同、有限随机测试通过，写成全部共享函数的全域结论。本结论不是“gen 117 已证实会坏”，也不裁决 resident v3.6 或上卡。

1. 对象与完整性

gen 116 DAT SHA-256 为 `1e033dfbcc3ca0bec0e1e5befbdb5579950e9aa8aacfbfd56f8c7342b9a97864`，gen 117 为 `4f5eeaffdfc4df77d9482887b827fe8ec73e7857b13ea76348e3e49c874d0b5a`。两份 DAT 的 engine 段分别逐字节等于本目录冻结的最终 ELF `.engine`。gen 117 engine 为 45,948 B，SHA-256 为 `548715f68ec9731423d6e1e36290fbcc3372de844cc0861ff5cbb859ccbf64e5`。两代重新链接产生的 ELF 均与原交付 ELF 逐字节相同，编译器转储对应的正是这些机器码，不是另编的近似版本。

另读了实际 `firmware/package_v36_g117/SD_ROOT/GXRCE.DAT`，SHA-256 为 `35ce20ac843764b9cdd452785683ebf99004c47b77ae90720c2e3dc716c31211`。它只改十进制 20..23 和 80..111，全部 payload 和 engine 均相同。因此本轮 engine 证据也覆盖这份实际重绑 DAT；这不是对 v3.6 机身的验收。[身份](identities.json)、[重绑](rebound-identity.json)、[重新链接](compiler/command.json)、[116 重新链接](compiler116/command.json)。

独立解析 ELF 后，按精确 LTO 名称及 `.lto_priv.0` 对应得到 95 个符号级改码项、30 个同码符号、25 个消失名称。95 项在两代均折合 88 个真实函数区间，同地址别名为 descriptor 五名、metadata 三名、unit_equal 两名，表中逐名保留，未重复计作独立函数。消失项含 `last_p32` 被相同的 `p32` 合并，不能全部当作删掉功能。另补查 23 个没有 STT_FUNC/size 的汇编入口，真实函数范围内全部字节相同；`rv_irq_restore` 后面是常量，未把它当作函数正文。前审原始 `symbol-diff.tsv` 没漏本轮 95 项。其摘要只挑重点，不能替代完整表。[全部符号](all-functions.tsv)、[汇编入口](untyped-assembly-functions.json)。

79/95 个符号级改码项的非 NOP 指令、运算常数、顺序和分支目标在独立展开后相同。没有把所有立即数一概抹掉：只替换 ELF 记录的重定位操作数，并另审 188 个低位重定位目标、47 个对象对应、两个有界 switch 表。未解析目标为零。匿名常量只按实际常量片段核对身份，完整读取界限仍须由调用路径约束，故这不是全域证明。[规范化](normalization.json)、[差分](normalized.patch)、[重定位](relocation-pairs.json)。

各项的原始并排反汇编在 `side-by-side/函数名.txt`。全部直接调用和地址引用见 [CALLS.md](CALLS.md)、[结构化调用点](callsite-inventory.json)。取地址引用共 47 条，另枚举九个 STT_FUNC 正文内的间接转移，包括 native build、服务回调和两个 switch；汇编 native 桥另列，不把固定 native 跳板算作未知产品回调。[间接转移](indirect-transfers.json)、[取地址引用](function-address-references.json)。

2. 发现

P1-CG01：全域裁决证据没有闭合，是本轮唯一阻断项。

已执行的九项包括原五个缩码函数，以及 `ig_apply`、`list_bind`、`eng_current` 和新增深查的 `workspace_close`。其余共享项没有完成题目要求的“每个调用点域内至少 10,000 随机输入”、域外边界执行和逐调用链约束。这里的 79 项规范化只是局部机器流对应；没有完成全程序回调、别名、内存有效性和所有前置条件的归纳证明。混合函数的允许文件调用删除也未逐项与其余编译改码分离。本轮不自行把该要求改成规范化通过即可签字。

用户可见故障未复现，不能把本项写成已证实的崩溃、错色或写卡。最小修复是补齐表中“未独立执行/未作全域裁决”的共享项，按最终调用点冻结状态和可达域，执行并核对全部写入及 r8–r15，再关闭这个证明缺口。不能只再跑 Host 或再绑一次 build id。

如果已经使用候选、需要整体撤回，恢复用卡 A Stage2l-50mm，挂上 50mm，用“+ 与回放”进入恢复更新；机身刷写必须挂着 50mm。本轮没有操作卡、相机或刷机。

3. pn_address 的空指针分支

ABI 是 r0=port、r1=s、r2=n。删除的是 s 的检查。gen 117 最终 ELF 有十个直接点，未见函数取地址或间接入口：native seed 三处 `0x0f48/0x0f66/0x0f72`，transfer 一处 `0x1534`，ui_call 一处 `0x3e00`，UI render 五处 `0x4030/0x4054/0x413c/0x4168/0x417c`。半字 packet 的 call PC 以 [CALLS.md](CALLS.md) 为准。

native seed 在使用 n 前检查非空，然后传 `&n->glyph_refs[i]`、`n->type_descriptors`、`n->labels`，长度分别 4、72、44；实际 build 回调在 panel 内固定，n 为 `&n.panel.native`。UI render 的五处都是静态 n.panel 内的 text、glyph、state、labels、details，循环 i 在 0..10 内。ui_call 的 buffer 来自同一静态 panel 的 text_request/list/view，长度 40 或 48。transfer 的两个最终上游为 io_read/io_write，传的是已初始化 store->chunk，即有效 PsStore 对象地址加 36，不是上层任意 p；写路径还受停写门禁约束。即便保守包含这两条路径，实际对象和加法界限也排除了地址回绕到零。

重新链接的 WPA IPA 转储给 s 的范围为 `[1,+INF]`；LTRANS 明写 `Setting nonnull for 1`；最终优化转储只剩 n==0 检查。native 的 NULL guard 在取成员地址之前，UI 参数直接来自静态对象，transfer 的来源如上。因此这里有独立的调用点非空依据，不靠“之后对可能为 NULL 的 s 解引用会 UB”来倒推。这里也没有把 port 的非空与 s 的非空混为一谈。[GCC 转储](compiler/engine.elf.wpa.081i.cp)、[最终优化](compiler/engine.elf.ltrans0.ltrans.254t.optimized)。

十种调用形状各执行 10,000 组，在等价端口副本中使用真实 address 回调。另执行 78 个 mapper 边界和 35 个无 mapper 的溢出边界，均一致。它们是调用域的受限上界模型，不是从真实调用者采下来的十万个相机快照。域外 `(port,s,n)=(0,0,1)` 给出确切差异：116 返回 0，117 读 port+40 时 unmapped fault；十处调用都不能传这个组合，因此不是可达 P0/P1。[逐组结果及域外反例](pn-results.json)。

4. gate_validate

两个最终直接调用点是 verify 的 `0x6ba8` 与 ig_init 的 `0x7518`，无地址引用。最终 ABI 已常量传播为 `(p,length,unit,out,private_base)`，trust 固定为 n+156，options=0；第五码在调用栈。verify 传 private_base=0、栈上 out；ig_init 传已租约私有 image base，out=&n.gate。允许的输入对象与静态 v、trust、输出区域分离，header 在这段检查中不被写入。

最大的实际生成变化不只是寄存器编号。117 复用早先读取的 header p+28 build_number 和 p+116 bss_bytes；116 在写静态 v 时再次调用 be32。GIMPLE 差分还显示循环 PHI 重命名、加法换序、比较换向，机器级另有独立字段 store 调度、r8/r9/fp 分工和 84→88 B 局部栈。固定保存七个寄存器后，两代正文栈分别为 112/116 B。缓存读取在这两个调用点的只读 header、非重叠对象条件下成立；本轮没有拿源文件相同当成机器码证明。[两代 GIMPLE](gate-gimple-normalized.patch)、[真实并排机器码](side-by-side/gate_validate.constprop.0.txt)。

执行 11,457 组，其中 10,000 随机、1,457 定向。覆盖三模块、全部返回状态实际可达的验证门、header/section/directory/relocation/pool/tweak/pin 边界，包含完整有效容器及独立破坏 CRC 的负例。两代返回值、输出 84 B、逐地址公共写入和返回 r8–r15 均相同，没有 fault。随机矩阵的 CRC callee 使用精确 zlib 规格；gate 正文和其它 helper 是真实 M32R。另六组覆盖三模块×原始/重定位输入，完全关闭所有 callee 替身，均返回 GXR2_OK；另 128 个 CRC32 包含真实 CRC_add 的执行与 zlib 相符。[矩阵](gate-results.json)、[逐例](gate-cases.jsonl)、[补充分支](gate-extra-results.json)、[无替身重放](full-machine-results.json)。

正文共有 112 条条件转移，输入覆盖 221/224=98.66% 的结果。剩下三条的 taken 分支是 117 的 `0x5da6/0x6298/0x632c`，对应 116 的 `0xd1e6/0xd6d4/0xd764`。第一处前面要求 off==next，next 从 256 开始且每次 len<=length-off，故 next<=length；后两处 pool 的 next 从 64 开始，先要求 pool.length>=64，每次增长前都验证 len 或 align4(len)<=length-next，故仍 next<=length。长度上限也排除 32 位加法回绕。三处条件都在比较 next/off 是否大于 length，所以 taken 不可达。覆盖统计只计正文，已排除 helper 条件。[覆盖率及精确缺口](tested-branch-coverage.json)。

全局 store 顺序并不相同，原始栈写入也不相同。执行时记录原始事件，公共数据按对象地址对应后逐字节比较每个地址的写值序列，独立字段的跨地址调度允许换序；临时栈单独看保存/恢复及写入范围，没有假称原始 write trace 字节相同。证明这种处理对所有共享调用点都适用，正是 P1-CG01 尚缺的全域工作之一。

5. 其它重点与边界

`es_range` 的 token/base/bytes 和六项 lease 表随机矩阵为 10,000 组，包含 session 拒绝、lease 不匹配、有效范围及越界；session callee 是明确的共同边界模型。`gxr2_crc32` 包装体的改变只有把 ldi 与 bl 合入 packet，10,000 组使用共同 CRC_add 规格，另 128 组执行完整 callee。`pn_native_from_seed` 真实执行 10,000 组有效 seed，再执行 49 个 NULL、尺寸、cursor、glyph 边界。没有可达差异。

`workspace_close` 从 80 B 长到 172 B，属于这轮必须注意的共享增长函数。117 内联旧 release，并复用先前读过的 workspace.token；116 先检查 token 再让 release 重查。两代状态机都是 token=0 返回 OK，released!=0 返回 -11，否则先置 released，release 成功清 32 B lease，失败置 release_failed。10,000 组和共同 pn_call 结果边界没有差异；实际硬件服务的并发行为没有被模型替代成已验证事实。[结果](workspace_close-results.json)、[并排](side-by-side/workspace_close.txt)。

`ig_apply`、`list_bind`、`eng_current` 独立解码后与前审一样，只见重定位、同语义 helper 身份、call 距离、NOP/packet 变化，运算和条件目标顺序相同。三项各执行 10,000 组。ingress、finish、fresh、服务和黑盒边界的替身在 [protected.py](protected.py) 明列。list_bind 早期探针只走 seed 拒绝，随后已修正；深路径首轮报告的是 byte-copy 中序列化地址不同，返回值与 ABI 相同，不能当产品反例。最后一轮把四字节地址按对象映射处理，且明确对 ig_copy/ig_zero 使用相同的寄存器与 byte-store 效果规格。保留这两次模型诊断，没有把初版的早退绿灯当作深路径验收。[三项结果](ig_apply-results.json)、[list](list_bind-results.json)、[current](eng_current-results.json)。

6. 完整差异表

表保留题目排除的文件家族以便核对全集；“未独立执行”是 0 组，不借其它函数或旧 Host 通过充数。“局部指令同构”不等于本轮已证明全部可达输入。所有调用点均用 ELF 地址，完整参数生成指令在 CALLS.md。

| 函数 | 116/117 B | 差异类型 | 最终调用点 | 可达域及已知边界 | 差分数量与覆盖 | 结论 |
| --- | ---: | --- | --- | --- | --- | --- |
| `a4_move` | 248/248 | 重定位/调用距离/packet/NOP | ig_apply@0x8064, ig_panel_event@0x8634；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `binding` | 100/100 | 重定位/调用距离/packet/NOP | ig_bootstrap@0xab14, ig_bootstrap@0xabcc；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `card` | 72/72 | 重定位/调用距离/packet/NOP | ig_bootstrap@0xaa84, ig_bootstrap@0xaddc；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `close_once` | 128/128 | 重定位/调用距离/packet/NOP | remove_owned@0x162c, io_close@0x3650；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `core_call` | 488/488 | 重定位/调用距离/packet/NOP | ig_menu@0x7d4c；地址引用 1 处；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `current.constprop.0` | 104/104 | 重定位/调用距离/packet/NOP | rv_call@0x94c8, rv_call@0x979c, rv_call@0x9bac, rv_call@0xa6e8, rv_call@0xa900；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `descriptor.lto_priv.0` | 74/74 | 重定位/调用距离/packet/NOP | slot_descriptor@0xd0a, gxr2_semantic_validate@0x2414, gxr2_semantic_validate@0x2ff8, gxr2_semantic_validate@0x31c4, gate_validate.constprop.0@0x6370, verify@0x6734, verify@0x6950, ig_init@0x7a00, ig_init@0x7a3c；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `descriptor.lto_priv.1` | 74/74 | 重定位/调用距离/packet/NOP | slot_descriptor@0xd0a, gxr2_semantic_validate@0x2414, gxr2_semantic_validate@0x2ff8, gxr2_semantic_validate@0x31c4, gate_validate.constprop.0@0x6370, verify@0x6734, verify@0x6950, ig_init@0x7a00, ig_init@0x7a3c；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `descriptor.lto_priv.2` | 74/74 | 重定位/调用距离/packet/NOP | slot_descriptor@0xd0a, gxr2_semantic_validate@0x2414, gxr2_semantic_validate@0x2ff8, gxr2_semantic_validate@0x31c4, gate_validate.constprop.0@0x6370, verify@0x6734, verify@0x6950, ig_init@0x7a00, ig_init@0x7a3c；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `descriptor.lto_priv.3` | 74/74 | 重定位/调用距离/packet/NOP | slot_descriptor@0xd0a, gxr2_semantic_validate@0x2414, gxr2_semantic_validate@0x2ff8, gxr2_semantic_validate@0x31c4, gate_validate.constprop.0@0x6370, verify@0x6734, verify@0x6950, ig_init@0x7a00, ig_init@0x7a3c；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `descriptor.lto_priv.4` | 74/74 | 重定位/调用距离/packet/NOP | slot_descriptor@0xd0a, gxr2_semantic_validate@0x2414, gxr2_semantic_validate@0x2ff8, gxr2_semantic_validate@0x31c4, gate_validate.constprop.0@0x6370, verify@0x6734, verify@0x6950, ig_init@0x7a00, ig_init@0x7a3c；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `disarm` | 82/82 | 重定位/调用距离/packet/NOP | fresh@0x45e8, eng_apply@0x4ea0, eng_apply@0x56d0；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `end` | 104/104 | 重定位/调用距离/packet/NOP | eng_apply@0x52cc, eng_apply@0x5460；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `eng_apply` | 3636/3636 | 重定位/调用距离/packet/NOP | select_cached@0x581c, ig_event@0x81d4；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `eng_current` | 120/120 | 重定位/调用距离/packet/NOP | ig_event@0x8274, ig_panel_open@0x8494；[上下文](CALLS.md) | 两个输出缓冲区及 g 状态；fresh 成功/失败。 | 10,000 随机；6/6 分支结果。 | 局部指令同构；所测一致。 |
| `eng_entry.constprop.0` | 104/104 | 重定位/调用距离/packet/NOP | eng_apply@0x4b04, ig_init@0x7b1c；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `eng_identity` | 88/88 | 重定位/调用距离/packet/NOP | eng_apply@0x4a6c, select_cached@0x5808, verify@0x6694；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `eng_visible_rows` | 134/134 | 重定位/调用距离/packet/NOP | select_cached@0x57c0, verify@0x6638, ig_menu@0x7c98, ig_menu@0x7e3c, ig_menu@0x7e78, ig_panel_open@0x8434；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `es_allocation` | 172/172 | 重定位/调用距离/packet/NOP | es_session.constprop.0@0x393c, ui_prepare.constprop.0@0x6e3c, ui_prepare.constprop.0@0x6e4c, ui_prepare.constprop.0@0x6ea0, rv_call@0x9980, rv_call@0xaa20；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `es_range.constprop.0` | 128/124 | 重定位/调用距离/packet/NOP | ingress@0x7230, ingress@0x724c, ingress@0x7264, rv_call@0x8bec, rv_call@0x96d8, rv_call@0xa180, rv_call@0xa198, rv_call@0xa1b8, rv_call@0xa270, rv_call@0xa298, rv_call@0xa50c, rv_call@0xa66c, rv_call@0xa688；[上下文](CALLS.md) | token/base/bytes 为 uint32；session 验证后的六项 lease 表。 | 10,000 随机；13/16 分支结果。 | 局部指令同构；所测一致。 |
| `es_session.constprop.0` | 336/336 | 重定位/调用距离/packet/NOP | es_range.constprop.0@0x3a06, same.constprop.0@0x6ca0, ui_prepare.constprop.0@0x6e90, ingress@0x702c, identity.constprop.0@0x8798, rv_call@0x886c, rv_call@0x88f0, rv_call@0x8bac, rv_call@0x8c7c, rv_call@0x8f70, rv_call@0x90d8, rv_call@0x9508, rv_call@0x99e0, rv_call@0x9c7c, rv_call@0xa138, rv_call@0xa3dc；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `es_ui_abort.constprop.0` | 348/348 | 重定位/调用距离/packet/NOP | rv_call@0xa0fc；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `expect` | 62/62 | 重定位/调用距离/packet/NOP | write_word@0x47d0, t_store@0x483c, t_read@0x4892, eng_apply@0x5324, eng_apply@0x544c；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `failure` | 68/68 | 重定位/调用距离/packet/NOP | eng_apply@0x528c, eng_apply@0x5474, eng_apply@0x563c；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `finish` | 252/220 | 含允许删除的文件调用或能力变化，另有调度/寄存器变化 | ig_init@0x73b4, ig_menu@0x7c78, ig_apply@0x80c4, ig_event@0x82f4, ig_panel_open@0x841c, ig_stop@0x8744；[上下文](CALLS.md) | 混合函数；尚未逐调用点分离全部允许改动与其余改码。 | 未独立执行；0 组；分支覆盖未计。 | 未作全域裁决。 |
| `fresh` | 172/172 | 重定位/调用距离/packet/NOP | eng_current@0x46a0, rpc.lto_priv.0@0x46ee, rpc.lto_priv.0@0x4734, eng_apply@0x4e90, eng_apply@0x4f2c, eng_apply@0x546c, eng_apply@0x55c4, eng_apply@0x5604, eng_apply@0x564c, ig_menu@0x7e68, ig_menu@0x7eec；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `gate_validate.constprop.0` | 2816/2792 | 缓存 p+28/p+116，寄存器和栈布局变化 | verify@0x6ba8, ig_init@0x7518；[上下文](CALLS.md) | 两个直接点；p/length/unit/out/private_base，trust 固定在 n+156；正文区不与 v/trust/out 重叠。 | 11,457 组，含 10,000 随机；221/224；另 6 组无替身重放。 | 所测一致；全域机器级证明未闭合。 |
| `grain_snapshot` | 122/122 | 重定位/调用距离/packet/NOP | 无直接调用；地址引用 1 处；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `gxr2_crc32` | 42/38 | 重定位/调用距离/packet/NOP | gxr2_semantic_validate@0x269c, gxr2_semantic_validate@0x26b4, gxr2_semantic_validate@0x26ec, gxr2_semantic_validate@0x2a3c, gxr2_semantic_validate@0x2b4c, gxr2_semantic_validate@0x2d88, gxr2_expand.constprop.0@0x3b48, gate_validate.constprop.0@0x5bc8, verify@0x6b70, ig_init@0x7850, ig_bootstrap@0xae20；[上下文](CALLS.md) | 有效只读缓冲区和长度；包装体全整数状态，callee 为同一 CRC_add。 | 10,000 包装体；128 组完整 callee；未汇总独立包装体分支。 | 局部指令同构；所测一致。 |
| `gxr2_crc_zeroed.constprop.0` | 120/120 | 重定位/调用距离/packet/NOP | io_close@0x375e, gate_validate.constprop.0@0x5ba4, verify@0x65f0；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `gxr2_expand.constprop.0` | 292/292 | 重定位/调用距离/packet/NOP | eng_entry.constprop.0@0x3bdc, ig_init@0x7834；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `gxr2_parameter` | 224/224 | 重定位/调用距离/packet/NOP | verify@0x68f0, ig_panel_open@0x8504；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `gxr2_raw_row` | 140/140 | 重定位/调用距离/packet/NOP | gxr2_semantic_validate@0x28ac, gxr2_semantic_validate@0x2da0, gxr2_expand.constprop.0@0x3af4, gate_validate.constprop.0@0x63dc, verify@0x6810, verify@0x699c, ig_init@0x7a10；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `gxr2_semantic_validate` | 3724/3724 | 重定位/调用距离/packet/NOP | verify@0x6bc4, ig_init@0x7814；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `identity.constprop.0` | 128/128 | 重定位/调用距离/packet/NOP | current.constprop.0@0x87ee, rv_call@0x9484, rv_call@0x97dc, rv_call@0x9f48；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `ig_apply` | 184/188 | 重定位/调用距离/packet/NOP | 无直接调用；地址引用 2 处；[上下文](CALLS.md) | ingress 成功/失败，initialized/panel 状态；请求 args[8] 为候选行。 | 10,000 随机；12/12 分支结果。 | 局部指令同构；所测一致。 |
| `ig_bootstrap` | 1092/1092 | 重定位/调用距离/packet/NOP | 无直接调用；地址引用 1 处；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `ig_bx_apply` | 398/398 | 重定位/调用距离/packet/NOP | ig_event@0x82e8, ig_panel_open@0x8410；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `ig_bx_event` | 238/238 | 重定位/调用距离/packet/NOP | core_call@0x434, ig_bx_receipt@0x630, finish@0x120c, list_bind@0x2250, list_bind@0x22c4, ig_menu@0x7be8, ig_menu@0x7cd4, ig_bootstrap@0xac78, ig_bootstrap@0xac9c；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `ig_bx_receipt` | 368/372 | 重定位/调用距离/packet/NOP | list_bind@0x1ea4, list_bind@0x2168, list_bind@0x2198, list_bind@0x2300, ig_menu@0x7c64；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `ig_bx_unit` | 284/280 | 重定位/调用距离/packet/NOP | ig_init@0x74e8, ig_init@0x7524；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `ig_event` | 2872/604 | 含允许删除的文件调用或能力变化，另有调度/寄存器变化 | 无直接调用；地址引用 2 处；[上下文](CALLS.md) | 混合函数；尚未逐调用点分离全部允许改动与其余改码。 | 未独立执行；0 组；分支覆盖未计。 | 未作全域裁决。 |
| `ig_init` | 2100/2100 | 含允许删除的文件调用或能力变化，另有调度/寄存器变化 | 无直接调用；地址引用 2 处；[上下文](CALLS.md) | 混合函数；尚未逐调用点分离全部允许改动与其余改码。 | 未独立执行；0 组；分支覆盖未计。 | 未作全域裁决。 |
| `ig_menu` | 3056/1172 | 含允许删除的文件调用或能力变化，另有调度/寄存器变化 | 无直接调用；地址引用 2 处；[上下文](CALLS.md) | 混合函数；尚未逐调用点分离全部允许改动与其余改码。 | 未独立执行；0 组；分支覆盖未计。 | 未作全域裁决。 |
| `ig_panel_abort` | 116/116 | 重定位/调用距离/packet/NOP | 无直接调用；地址引用 2 处；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `ig_panel_event` | 100/100 | 重定位/调用距离/packet/NOP | 无直接调用；地址引用 2 处；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `ig_panel_open` | 704/704 | 重定位/调用距离/packet/NOP | 无直接调用；地址引用 2 处；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `ig_stop` | 144/144 | 重定位/调用距离/packet/NOP | 无直接调用；地址引用 2 处；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `ingress` | 928/928 | 重定位/调用距离/packet/NOP | ig_init@0x737c, ig_menu@0x7ba8, ig_apply@0x8034, ig_event@0x80f8, ig_panel_open@0x8354, ig_panel_event@0x860c, ig_panel_abort@0x866c, ig_stop@0x86e0, ig_bootstrap@0xaa74；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `io_close` | 268/652 | 存储/安装/旧偏好家族 | 无直接调用；地址引用 1 处；[上下文](CALLS.md) | 在题目允许删除的文件家族内；表中保留以核对完整性。 | 未独立执行；0 组；分支覆盖未计。 | 排除，不计作编译器共享函数回归。 |
| `io_open` | 444/492 | 存储/安装/旧偏好家族 | 无直接调用；地址引用 1 处；[上下文](CALLS.md) | 在题目允许删除的文件家族内；表中保留以核对完整性。 | 未独立执行；0 组；分支覆盖未计。 | 排除，不计作编译器共享函数回归。 |
| `io_read` | 260/260 | 存储/安装/旧偏好家族 | 无直接调用；地址引用 1 处；[上下文](CALLS.md) | 在题目允许删除的文件家族内；表中保留以核对完整性。 | 未独立执行；0 组；分支覆盖未计。 | 排除，不计作编译器共享函数回归。 |
| `io_remove` | 228/212 | 存储/安装/旧偏好家族 | 无直接调用；地址引用 1 处；[上下文](CALLS.md) | 在题目允许删除的文件家族内；表中保留以核对完整性。 | 未独立执行；0 组；分支覆盖未计。 | 排除，不计作编译器共享函数回归。 |
| `io_rename` | 236/288 | 存储/安装/旧偏好家族 | 无直接调用；地址引用 1 处；[上下文](CALLS.md) | 在题目允许删除的文件家族内；表中保留以核对完整性。 | 未独立执行；0 组；分支覆盖未计。 | 排除，不计作编译器共享函数回归。 |
| `io_write` | 144/144 | 存储/安装/旧偏好家族 | 无直接调用；地址引用 1 处；[上下文](CALLS.md) | 在题目允许删除的文件家族内；表中保留以核对完整性。 | 未独立执行；0 组；分支覆盖未计。 | 排除，不计作编译器共享函数回归。 |
| `list_bind` | 1188/1188 | 重定位/调用距离/packet/NOP | ig_menu@0x7eb8, ig_apply@0x80b0；[上下文](CALLS.md) | 无参；n.context、原生 UI seed、g 的八行列表及端口状态。 | 10,000 随机；16/28 分支结果。 | 局部指令同构；所测一致。 |
| `mapped` | 116/116 | 重定位/调用距离/packet/NOP | eng_apply@0x4ee8, eng_apply@0x5148, eng_apply@0x55bc, eng_apply@0x55f8, eng_apply@0x5630；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `metadata.lto_priv.0` | 76/76 | 重定位/调用距离/packet/NOP | slot_descriptor@0xcea, gxr2_parameter@0xd8c, gxr2_semantic_validate@0x2f58, gxr2_semantic_validate@0x31d4, verify@0x66e0, ig_init@0x78c8；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `metadata.lto_priv.1` | 76/76 | 重定位/调用距离/packet/NOP | slot_descriptor@0xcea, gxr2_parameter@0xd8c, gxr2_semantic_validate@0x2f58, gxr2_semantic_validate@0x31d4, verify@0x66e0, ig_init@0x78c8；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `metadata.lto_priv.2` | 76/76 | 重定位/调用距离/packet/NOP | slot_descriptor@0xcea, gxr2_parameter@0xd8c, gxr2_semantic_validate@0x2f58, gxr2_semantic_validate@0x31d4, verify@0x66e0, ig_init@0x78c8；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `open_read` | 168/212 | 存储/安装/旧偏好家族 | remove_owned@0x1620, io_open@0x1898；[上下文](CALLS.md) | 在题目允许删除的文件家族内；表中保留以核对完整性。 | 未独立执行；0 组；分支覆盖未计。 | 排除，不计作编译器共享函数回归。 |
| `path` | 456/456 | 重定位/调用距离/packet/NOP | rv_call@0x8d88, rv_call@0xa9bc；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `pn_address` | 68/64 | IPA 删除 r1==NULL 检查 | pn_native_from_seed@0xf48, pn_native_from_seed@0xf66, pn_native_from_seed@0xf72, transfer@0x1534, ui_call.constprop.0@0x3e00, pn_ui_render.constprop.0@0x4030, pn_ui_render.constprop.0@0x4054, pn_ui_render.constprop.0@0x413c, pn_ui_render.constprop.0@0x4168, pn_ui_render.constprop.0@0x417c；[上下文](CALLS.md) | r0=有效端口；r1=已验证对象内地址，非 NULL；r2=4/72/44、1..256、1..9、18/32/132、40/48。 | 10×10,000 随机；78+35 边界；1 个域外 NULL 反例。 | 可达非空域等价；域外差异不是相机反例。 |
| `pn_call` | 220/220 | 重定位/调用距离/packet/NOP | workspace_close@0x1182, rpc.lto_priv.1@0x1328, list_bind@0x2184, list_bind@0x226c, list_bind@0x22dc, ui_call.constprop.0@0x3e28, pn_ui_render.constprop.0@0x3f68；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `pn_native_from_seed` | 388/380 | 重定位/调用距离/packet/NOP | 无直接调用；地址引用 1 处；[上下文](CALLS.md) | 固定 build 回调；seed/port/native/glyphs 非空，32/72/132 B，11 个非空 glyph，cursor=0..10。 | 10,000 随机；33/36 分支结果；另 49 边界。 | 局部指令同构；所测一致。 |
| `pn_request` | 96/96 | 重定位/调用距离/packet/NOP | workspace_close@0x1168, list_bind@0x213c, list_bind@0x2238, ui_call.constprop.0@0x3de8, pn_ui_render.constprop.0@0x3f4c；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `pn_ui_render.constprop.0` | 1156/1156 | 重定位/调用距离/packet/NOP | a4_move@0x4348, ig_panel_open@0x83b8, ig_panel_open@0x85d4；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `read_exact` | 88/88 | 重定位/调用距离/packet/NOP | rv_call@0x92c0, rv_call@0x92d4；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `remember_load` | 124/4 | 存储/安装/旧偏好家族 | 无直接调用；地址引用 1 处；[上下文](CALLS.md) | 在题目允许删除的文件家族内；表中保留以核对完整性。 | 未独立执行；0 组；分支覆盖未计。 | 排除，不计作编译器共享函数回归。 |
| `remove_owned` | 152/196 | 存储/安装/旧偏好家族 | io_remove@0x1ae4；[上下文](CALLS.md) | 在题目允许删除的文件家族内；表中保留以核对完整性。 | 未独立执行；0 组；分支覆盖未计。 | 排除，不计作编译器共享函数回归。 |
| `rpc.lto_priv.0` | 152/152 | 重定位/调用距离/packet/NOP | expect@0x4780, t_read@0x48d4, eng_apply@0x5284, eng_apply@0x5338, eng_apply@0x5490；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `rpc.lto_priv.1` | 132/132 | 重定位/调用距离/packet/NOP | open_read@0x140e, close_once@0x14ae, transfer@0x1554, remove_owned@0x1688, io_open@0x1814, io_rename@0x1c1c；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `rt_tone.constprop.0` | 428/428 | 重定位/调用距离/packet/NOP | eng_apply@0x4bb4, eng_apply@0x4bd0, eng_apply@0x4c08, eng_apply@0x5164, eng_apply@0x5180；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `rv_call` | 8720/8720 | 重定位/调用距离/packet/NOP | 无直接调用；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `rv_unit.constprop.0` | 192/192 | 重定位/调用距离/packet/NOP | ingress@0x7278, identity.constprop.0@0x87a4, rv_call@0x9f3c；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `same.constprop.0` | 140/140 | 重定位/调用距离/packet/NOP | rv_call@0x918c, rv_call@0x91f0, rv_call@0x9310, rv_call@0x932c；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `sd_current.constprop.0` | 236/236 | 重定位/调用距离/packet/NOP | rv_call@0x8a3c, rv_call@0x8ce0, rv_call@0x8fa0, rv_call@0x9380；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `select_cached` | 196/196 | 重定位/调用距离/packet/NOP | ig_event@0x82b0, ig_panel_open@0x8440；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `slot_descriptor` | 112/112 | 重定位/调用距离/packet/NOP | gxr2_parameter@0xd48, gxr2_expand.constprop.0@0x3a84；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `snapshot` | 328/328 | 重定位/调用距离/packet/NOP | fresh@0x4600, ig_init@0x76d0；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `sticky_put` | 70/70 | 重定位/调用距离/packet/NOP | ig_bx_unit@0x706, ig_bx_apply@0x844, ig_bx_apply@0x8c0；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `svc.constprop.0` | 158/158 | 重定位/调用距离/packet/NOP | snapshot@0x44c0, snapshot@0x4560, rpc.lto_priv.0@0x472c, end@0x4924, eng_apply@0x4ee4, eng_apply@0x513c, eng_apply@0x55b8, eng_apply@0x55f4, eng_apply@0x562c；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `t_read` | 152/152 | 重定位/调用距离/packet/NOP | eng_apply@0x52ac, eng_apply@0x5414；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `t_store` | 84/84 | 重定位/调用距离/packet/NOP | eng_apply@0x52e4, eng_apply@0x5420；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `transfer` | 268/268 | 重定位/调用距离/packet/NOP | io_read@0x1948, io_write@0x1a2c；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `ui_call.constprop.0` | 168/168 | 重定位/调用距离/packet/NOP | pn_ui_render.constprop.0@0x40a0, pn_ui_render.constprop.0@0x41f4, pn_ui_render.constprop.0@0x426c, pn_ui_render.constprop.0@0x4288, pn_ui_render.constprop.0@0x42b0；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `ui_finish` | 156/124 | 含允许删除的文件调用或能力变化，另有调度/寄存器变化 | ig_apply@0x8070, ig_event@0x81b4, ig_panel_open@0x83c8, ig_panel_event@0x8640, ig_panel_abort@0x86b0；[上下文](CALLS.md) | 混合函数；尚未逐调用点分离全部允许改动与其余改码。 | 未独立执行；0 组；分支覆盖未计。 | 未作全域裁决。 |
| `ui_prepare.constprop.0` | 244/244 | 重定位/调用距离/packet/NOP | rv_call@0xa228, rv_call@0xa58c；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `ui_seed.constprop.0` | 184/184 | 重定位/调用距离/packet/NOP | rv_call@0xa2d8, rv_call@0xa5c8；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `unit_equal.lto_priv.0` | 112/112 | 重定位/调用距离/packet/NOP | gxr2_semantic_validate@0x2464, gate_validate.constprop.0@0x6104；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `unit_equal.lto_priv.1` | 112/112 | 重定位/调用距离/packet/NOP | gxr2_semantic_validate@0x2464, gate_validate.constprop.0@0x6104；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `verify` | 212/1756 | 存储/安装/旧偏好家族 | 无直接调用；地址引用 1 处；[上下文](CALLS.md) | 在题目允许删除的文件家族内；表中保留以核对完整性。 | 未独立执行；0 组；分支覆盖未计。 | 排除，不计作编译器共享函数回归。 |
| `warp` | 124/124 | 重定位/调用距离/packet/NOP | rt_tone.constprop.0@0x3d58, rt_tone.constprop.0@0x3d8c；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |
| `workspace_close` | 80/172 | 内联旧 release，重复 token 检查消除 | finish@0x1210, ui_finish@0x12b4, ig_stop@0x871c；[上下文](CALLS.md) | 无参；workspace token、released 标志、release 服务返回值。 | 10,000 随机；6/6 分支结果。 | 所测一致；与旧 helper 的全域对应未形式化。 |
| `write_word` | 86/86 | 重定位/调用距离/packet/NOP | t_store@0x4812, eng_apply@0x5528；[上下文](CALLS.md) | 尚未逐调用链证明；仅核对局部运算、分支及重定位目标。 | 未独立执行；0 组；分支覆盖未计。 | 局部指令同构；缺逐调用点执行和可达域证明。 |

7. 复跑与范围

所有写入只在本目录，Python 均为 `/usr/bin/python3 -I -B`。只读导入 tools/native_harness 的后端，decode cache 改到本目录。题目列出的 tooling_m32r_asm 目录在此检出不存在，实际 objdump 为 research/tooling_m32r/prefix/bin/m32r-elf-objdump；GCC 是既有 tooling_m32r_c 工具。编译器、后端和源文件依赖哈希在 read-dependencies.json。没有访问相机、卡卷、RPC、网络或执行刷写，没有子代理。

可复跑的入口按依赖顺序是 audit.py、normalize.py、calls_and_relocations.py、compiler_dump.py、execute.py gate 10000、gate_extra.py、primary.py pn/native/crc 10000、protected.py 对五项各 10000、extra_boundaries.py、full_machine.py、write_report.py。compiler_dump.py 116 重链接旧代，默认重链接新代。全量执行会使用 CPU 数分钟。初次完整 CRC 的 200,000 步预算不够，只得到 max_steps；已明确保留 initial-budget 诊断，改成 4,000,000 步后六组全部执行返回，未把超步数算产品差异。

SHA256SUMS 的路径相对本目录，不包含清单自身。验证命令：

```sh
shasum -a 256 -c SHA256SUMS
```
