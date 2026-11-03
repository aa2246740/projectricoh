不能上卡

g150 离线复审，2026-11-01。按本轮测试卡门槛，发现 1 个阻断 P1，R1/P1-01 尚未完全关闭。结论绑定下列两个 DAT，适用于既有 v3.8 机身、只换卡上 DAT、以 MOUNT 为主并覆盖 50mm 的测试。没有上机、写卡或刷机。

已有的原厂九行起点用例通过；新增的未建基线、非原厂九行起点却会静默写回原厂模板，既非此前状态，也非完整目标。该 P1 发生时菜单归属始终有效。已披露的失归属和持续通信错误边界另列，均未作为本次新增阻断理由。

## 0. 阻断 P1：未验证的模板被当成“此前状态”

主位置：[eng_core.c:343](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/firmware/engine_v58_g150/candidate/containers/product/src/firmware/engine/core/eng_core.c:343)。关联位置同文件 :166、:333-345、:376-395、:425、:722-729。

eng_init 在 :166 把原厂 04 模板复制到 g.live。首次 S 模式不是 1 时，boot_restore 在 :722-727 返回，未设置 baseline，也没有把实际九行读进 g.live。正向写入在 :382 已专门用 !g.baseline 承认“没有可信行账本”，但写 S 遇忙后 :343 仍把 g.live 当成真实此前状态写回，:344 清掉 uncertainty，最后普通拒绝而不报 ERR。

独立复现使用最终 DAT 的合法 02 九行和 T=2 作为起始单元状态，S=4 与原 R1 用例相同。没有写 UI、引擎变量或修改被审文件。首次打开还逐项确认 W=0、S/九行/T 都未变。随后选择 05，op 6 返回 OK，实际写 S 入口才由模型持有者取锁。主证据复核显式设置 IRQ 开启，并在持有者变化处断言 IRQ 确实开启。

| 检查点 | 主机实际值 |
| --- | --- |
| 按键前 | 实际九行为完整 02 表，T=2，S=4；未建基线。 |
| 服务返回 | op 6=0，op 2=-2；S 一次也没有写。 |
| 按键后 | W=506；九行成为原厂 04，T=2，S 仍为 4；九行既不等于此前 02，也不等于目标 05。 |
| 画面与退出 | failed=0，没有 ERR/Unsaved；光标回 04，OK 正常关成 7 行；重开仍是原厂 04 九行、S=4，无 ERR。 |

MOUNT 和 50mm 均观察到同一问题。主证据为 [MOUNT IRQ 开启复核](tests/local/unverified-late-mount-irq/checks/mount-unverified-late.json)、[50mm IRQ 开启复核](tests/local/unverified-late-50mm-irq/checks/50mm-unverified-late.json)；早先观察保留在 [MOUNT](tests/local/unverified-late-mount/checks/mount-unverified-late.json) 和 [50mm](tests/local/unverified-late-50mm/checks/50mm-unverified-late.json)。它们输出 OBSERVED_P1，表示复现了缺陷，不能计作固件通过。实际九行与 02/04/05 表项的独立比较及结果文件 SHA另见 [P1 汇总](evidence/p1-summary.json)。

对照用相同起始九行/T/S：锁全程空闲时完整应用 05，S=1；按键前已忙时该次按键 W=0、实际此前九行不变。后者在后续退出重查时会进入 ERR 0JEM，原记录完整保留，没有把它说成所有边界都保持此前状态。[对照结果](evidence/receipts/unverified-controls-mount.json)。新增的静默第三状态来自迟到的锁忙及错误恢复源。

原用例没发现的原因是 research/g150/g150_checks.py:29-36 的 p1_start 把起点固定为原厂九行。此时“真实此前九行”和 g.live 的原厂模板恰好相等，无法区分恢复了哪一个。82 项、49 组及原始十行 FAIL 的说明均未覆盖这个区别。

这是静态与原 Python M32R 主机层已证的恢复源错误。真实相机出现此起始组合的条件和频率均未测；代码也没有证明未建基线时实际九行必为原厂值。因此不能把未验证的起点假设当作放行条件。

最小修正方向是在未建基线时先获得并验证实际九行/T 快照，以该快照回写；无法获得可信快照或无法恢复时，应明确进入 ERR，不能普通拒绝并清除 uncertainty。修复后须重跑本轮非原厂起点，并另写断言“完整目标或真实此前状态”的正常合同检查。

本次在测试 DAT 上执行复现；发布 DAT 的涉事指令与 02/04/05 表逐字节相同，45 B 差异仅在用户扩展及 CRC，故发布 DAT 静态同因受影响。

## 1. 产物、输入和证据层

| 对象 | 独立核对 |
| --- | --- |
| 发布 DAT | SHA256 c4878f6600cec8b2dfe973c0888bc9c61bcd3a51e6d20a63e12c7dcceb3f9b78；87,464 B；generation 150；0 个用户条目。 |
| 测试 DAT | SHA256 68418fe71744c0fabd8dde7fcb88782631a71767521804b0cf580ebcbd4252c8；87,464 B；FCC-001、FCC*002、GRN*001 三个条目。 |
| 引擎 ELF | SHA256 8be7e95dde0df1351122551940754a8f007e6ed45bf9e8e2524ea7eee5fe7b21；.engine 与两个最终 DAT 的引擎段逐字节相同。 |
| 机身 | 两包各 29 个非 DAT 文件与 g139 逐字节相同。ilaunch3 为 d4fa3b46da137b8b7c7c703e66750a8249c0715271290c0fdb490a2f7a239a90。resident 段匹配，机身校验和 6a7d99ef。 |
| 内存请求 | 104,120 B；相对 106,124 B 上限余 2,004 B。未独立重建，独立检查的是最终文件及 ELF/DAT 绑定。 |
| 冻结输入 | 先核对 research/g150/SHA256SUMS 的 467 项，全部匹配；该清单 SHA256 为 9d5e6b3d7fea610f527d767bb2b1aee898bc6bb442e14099e99dc42a96fd78ce。末次复核见封存回执。 |

证据：[输入回执](evidence/input-receipt.json)、[产物检查](artifact-results.json)、[静态复审](evidence/static-review.json)、[服务调用检查](service-proof.json)、[最终封存](evidence/seal.json)。

- 静态已证：上述字节关系、代数、表、服务分支和写入范围。
- 主机已证：原 PythonBackend 解释执行最终 DAT 与原厂 M32R 指令；锁、S、单元通信和图形叶子是模型。每个返回 Camera 的用例均记录并核对原厂 getter 未替换、原生 UI 无主机直接预置、没有 create/write/rename/delete。
- 推断：故障只影响单元 RAM 且 S 未被破坏时，冷启动重新装载单元可恢复；DAT 的文件服务关闭，RAM 诊断落盘函数直接返回。模型没有写照片或固件文件。真实关机、存储保存及模块重启行为仍须上机确认。
- 未知：真实 RTOS 的锁时序、实拍效果、物理按键分派、真实断电恢复和相机存储行为。本结论是测试卡复审，不是发布或真机验收。

后文行号基于冻结的 g150 源码。core = firmware/engine_v58_g150/candidate/containers/product/src/firmware/engine/core/eng_core.c；services = firmware/engine_v58_g150/candidate/engine_services/services.c；adapter = firmware/engine_v58_g150/candidate/containers/product/adapter.c。

## 2. 锁忙修法

### 2.1 op 6 的检查和零写边界

services:179-195 对 op 2 和 op 6 使用同一份计划校验，检查数量、模式、偏移、重复项、保留位和数值范围。services:213-224 在关闭 IRQ 后重查归属、S 指针、长度及 settings epoch，随后只接受锁 ID=55、count=-1。op 6 在取锁和写 S 之前返回。services:216 的 op-4u<2u 仅匹配记录操作 4/5，op 6 与 op 2 一致，不误入记录版本检查。

“只读”指不写 S、不改原厂锁、不发单元 W；请求、回复及服务自身状态内存仍有正常 ABI 写入。

独立 service-six-matrix 在 MOUNT 上测试 (count,ID)=(0,55)、(1,55)、(-1,54)、(-2,55)、(-1,55)。前四项返回 BUSY，全部 S、九行/T、W 次数和锁值不变。空闲项返回 OK，op 6 区间也没有 S/锁/W 写入，后续完整应用 05。各次检查到 rv_irq_restore 入口时 IRQ 关闭，返回后恢复开启。

证据：[锁矩阵](tests/local/own-lock-restore-mount/checks/mount-service-six-matrix.json)、[IRQ 汇编](../../firmware/engine_v58_g150/candidate/engine_services/bridges.S)。

### 2.2 时序与退出

core:376-379 在首次单元 W 之前预查；core:389-395 在实际写 S 处识别 BUSY；core:341-345 的回写使用 g.live 和 deep(1)，全量写九行/T 并读回，成功才清除 uncertainty。这些原厂起点的 S 写入失败没有进入目标发布点；未建基线、非原厂起点另有第 0 节的错误回写。

| 时序 | 本轮证据及观察 |
| --- | --- |
| 按键前已忙 | MOUNT 和 50mm 的 held-busy-ok；MOUNT 的 held-busy-half/menu。op 6 一次，op 2/5 零次，W=0，S 全部不变；退出、重开仍是此前状态。 |
| op 6 返回后、第一次 W 前变忙并保持 | 独立 lock-after-check-held。预查返回 OK 后、W=0 时取锁；到 S 处被拒，九行/T 写回此前状态；MENU 退出、重开及锁空闲后的完整应用通过。 |
| 写 S 时才忙 | MOUNT 的 race-at-s-ok/half/menu，50mm 的 race-at-s-ok。先写目标再写回，MOUNT 实测两轮共 506 次 W；按键结束及退出重开均为此前九行/T，S 全部不变。 |
| 瞬时忙 | 50mm transient-busy-fixed。在第一次忙的 op 6 恢复 IRQ 后释放锁；本键仍拒绝，W=0；两个原厂半按入口之后仍为此前状态。 |
| 新增的中途释放 | 独立 lock-during-rows。op 6 返回后取锁，第 128 次单元 W 后释放；实际 op 2 成功，最终九行/T、S 和记录均为完整 05；MENU 退出重开一致。 |
| 回写中失去归属 | 独立 owner-during-restore。写 S 遇忙后，在第一次回写 RPC 返回处执行原厂换页；此前九行/T、全部 S 保持，重开一致。 |
| 正向写入中失去归属 | 见第 3 节的继承例外，不能计入“完整状态已收敛”的通过数。 |

主证据：[MOUNT 基本组](evidence/receipts/r-mount-basic.json)、[新增锁时序与恢复](evidence/receipts/own-lock-restore-mount.json)、[更多恢复](evidence/receipts/own-restore-more-mount.json)、[归属与用户条目组](evidence/receipts/own-owner-users-mount.json)、[MOUNT 退出补测](evidence/receipts/mount-exits-more.json)、[50mm A](evidence/receipts/fixed-50mm-a.json)、[50mm B](evidence/receipts/fixed-50mm-b.json)。

用户指定的旧 busy-settings-exit、transient-busy-half 已复制到本目录并换成 g150 重跑。二者分别在“九行应已变成 05”的旧缺陷断言处 FAIL；未改判 PASS。对应用例 held-busy-ok 和 transient-busy-fixed 另外验证正确结果。原函数 AST 与 g139 完全相同：[复制来源核对](evidence/copy-provenance.json)、[原始重跑回执](evidence/receipts/r-old-lock-50mm.json)。

### 2.3 回写本身失败

| 故障输入 | 实测结果 |
| --- | --- |
| 回写首行有一次“W 回答成功、读回不同”，锁保持忙 | 错误被读回发现；后续恢复写回此前九行/T，累计 W=790；S 全部不变，进入 ERR。OK、半按、MENU、重开都没有把它发布成成功配方。 |
| 同一读回错误后锁释放 | 此前九行/T 恢复，S 仍全部不变，仍进入 ERR。s_busy 在本键内保持，程序不因锁刚释放而再次尝试写 S。 |
| 每次回写同一个字都读回不同 | 共七次不一致，累计 W=470，最后 ERR 0RPD。部分九行 RAM 与此前状态不同；S 全部不变、记录仍全零，重开仍 ERR。 |

证据：[一次读回错误](tests/local/own-lock-restore-mount/checks/mount-restore-readback-once.json)、[随后锁释放](tests/local/own-restore-more-mount/checks/mount-restore-readback-release.json)、[持续读回错误](tests/local/own-restore-more-mount/checks/mount-restore-readback-persistent.json)。

core:453-482 的恢复有上界；失败保持 uncertain/write_started，adapter:125-133 记录 ERR，后续各入口按 n.failed 停止应用。原厂 S 锁再次忙不会直接阻止九行/T 的 RPC 回写，因为这条回写路径不写 S；它会阻止后续恢复的 S 计划。持续通信错误下没有“必恢复完整”的保证，处理方式是停止使用本次状态并冷启动恢复，不能继续拍摄验收。

## 3. 失归属例外与确认检查

正向 W 期间执行原厂换页后，g150 保持完整目标九行/T，但 S 模式仍为 4，记录未写。这就是实现报告第 10 节第 2 条已披露的继承路径，按本轮门槛不作为新增 P1 阻断。

这里必须区分三个动作：

1. 首次重开 H01 会执行 core:563-570 的 accept_menu_preview()。confirmed_valid 从 0 变为 1，S 仍待写。这段函数与 g139 逐字节相同，没有 s_unwritten 条件。
2. 随后的 OK 确实检查 s_unwritten。在最终 ELF 的 0x89F0 处读到 1，确认配方/levels/有效位区域没有任何 OK 阶段写入，H07 返回 CONSUMED；g139 对照返回 CLOSE_AND_PASS。core:488 的新增确认检查有效。
3. 原厂后续仍可关页，8 行变回 7 行，S 保持 4。锁空闲后再次重开才补成 S=1，记录写入。

因此，“OK 不确认 S 待写状态”不能扩大为“菜单一定保持打开”或“S 完成前任何路径都不会确认”。原来的独立 owner-during-forward 把“拒绝确认”误当成“菜单必须仍为 8 行”，原始 FAIL 保留；后续用逐指令检查确认了实际写入边界，未把原 FAIL 改成 PASS。当前复跑脚本改查确认写入，执行时旧版本的完整字节也已保存。

证据：[g150 观察](tests/local/own-owner-observe-mount/checks/mount-owner-path.json)、[g139 同输入对照](tests/local/own-owner-observe-g139-mount/checks/mount-owner-path.json)、[g150 确认写入检查](tests/local/own-owner-guard-mount/checks/mount-owner-path.json)、[最终 H07 反汇编](evidence/ig_event.txt)、[继承源码比较](evidence/inherited-source-comparison.json)。

## 4. 原始 10 行 FAIL 的逐条裁定

10 行实际分类为 2 行 g139 对照、7 行旧期望与新行为不同、1 行继承清理合同。实现报告 4A 节开头写成“4+5+1”是计数笔误；另外两条旧版 OBSERVED_P1 不在这 10 行 FAIL 中。

| # | 原始 FAIL | 裁定与对应通过证据 |
| --- | --- | --- |
| 1 | g139-fixed-held-busy-ok | 旧版确实在锁忙时写了单元，新断言失败成立。本轮 50mm、MOUNT held-busy-ok 均 PASS，op 6 一次、W/S 写入零。 |
| 2 | g139-fixed-race-at-s-ok | 旧版没有 op 6，计数断言失败成立；旧版实际半套状态另由两个 OBSERVED_P1 支持。本轮 50mm/MOUNT race-at-s-ok 及 MOUNT race-at-s-half/menu 均 PASS，回写读回完整此前状态。 |
| 3 | h-50mm-04 / held-lock | 旧脚本仍期待 op 2 一次和后续 Unsaved；g150 实际在 op 6 拒绝，op 2=0。本轮同输入 held-lock-g150/50mm PASS；锁忙时 W/S 零，锁闲后完整应用并恢复 WB=9。 |
| 4 | h-28mm-00 / held-lock | 与第 3 条同一旧断言。对应 g150 的 28mm-held-lock-g150 原结果 PASS_M32R，176.794 s，实际 DAT=68418fe7…；回执、文件 SHA、时间及全状态断言已核对。本轮未重新执行这一条，未把它算入本轮执行数。 |
| 5 | h-mount-00 / held-lock | 与第 3 条同一旧断言。本轮 MOUNT held-lock-g150 PASS，对比全部 S、九行/T、W 和下一次成功应用。 |
| 6 | r-busy-settings-exit-50mm | 已原样重跑，仍在“九行应已是 05”的旧缺陷断言 FAIL。本轮修复合同 held-busy-ok PASS，OK/重开保持此前状态，锁闲后完整应用。 |
| 7 | r-transient-busy-half-50mm | 已原样重跑，仍在同类旧缺陷断言 FAIL。本轮 transient-busy-fixed PASS，瞬时释放后本键 W=0，两个半按处理入口之后状态不变。 |
| 8 | r-record-busy-attempts-50mm | 原断言期待两次 op 5；实际一次。本轮 record-busy-once PASS，S 零写、锁不改、完整配方生效，仅记录待写，显示 >Unsaved。 |
| 9 | r-offer-stock-tweak-50mm | 原断言期待首开 >4*Std；实际 stock 应显示 >4 Std。本轮 offer-stock-tweak-fixed PASS；首开 S/九行/T/W 不变，OK 后才应用 Cont+1，重开显示 >4*Std。 |
| 10 | r-glyph-parent-50mm | 原“换父页后任何 UI store 都应为零”的断言不符合既有清理合同。本轮 glyph-cleanup-contract PASS，只允许恢复 0x2022F5A8、0x2022F5AC、0x2022F725/726 四处固定值；S、单元 W 和新增 cursor_cache 写入为零。release_view 与 g139 字节相同，原 FAIL 仍保留。 |

实现者对十行的逐行解释成立，开头分类计数应更正；这十行没有覆盖第 0 节，不能据此断言 P1 已全部关闭。第 10 条的原对应状态是 OBSERVED_INHERITED_UI_RESTORE，本轮另以明确的固定清理合同作通过检查；没有把原“零 UI 写入”断言改判。

机器可核对的逐行链接、状态、SHA 和是否本轮重跑见 [十行证据映射](evidence/ten-fail-evidence.json)。原始 76 份用例回执、130 项结果及 49 组回归的检查见 [原记录审计](evidence/implementation-audit.json)、[回归内层结果审计](evidence/regression-result-audit.json)。这些审计不等于本轮重跑全部 82 项或 49 组。

## 5. MOUNT 表与用户条目

### 5.1 表和代数

复用复制到本目录的 mount_vs_50mm.py 与 decode.py，并另查 g139m 段关系：

- MOUNT 01、02、03、05、07、08 的 552 B 条目与 50mm 相同。
- 06 只在 T1 相关的 mask、C/D 行及 CRC、控制字不同；MOUNT T=2，C/D 为 MOUNT 原厂值。
- MOUNT 04 与 g139 原厂条目相同，map、pin、配方记录、范围不变；非 04 的 A14=A5、B14=B5。
- 50mm、28mm 的全部 16 项与 g139 相同。
- g150 与 g139m 的 map 段 456 B、行池/描述符段 2,868 B、旋钮/UI 段 20,776 B 逐字节相同；配方记录段只差三个代数字节及各自头 CRC，共 15 B。
- 引擎三处代数检查为 150。resident_v38/resident/loader.c:109-120 先选卡上文件，仅检查读入代数与该文件头部自洽；只有 IROM 两候选之间比较代数，没有卡上代数单调要求。

证据：[逐条目比较](diff/mount-vs-50mm.json)、[与 g139m 段比较](diff/mount-section-vs-g139m.json)、[产物检查](artifact-results.json)。MOUNT 表合并函数 AST、kv_math.c 和 kv_data.c 均已与来源比较：[源码关系](evidence/inherited-source-comparison.json)。

MOUNT 旋钮仍来自旧表，范围和步长与 50mm 不同，属于已书面披露的限制。默认表一致不能据此宣称所有旋钮档位或实拍色彩一致。

### 5.2 三个用户条目

本轮使用测试 DAT，经真实原厂 ADJ 构造器、DAT 菜单、MyRec 分组和条目卡片逐个应用，再 OK、重开检查。每项都比较实际单元九行/T 与主机 C 数学参照的结果；C 只用来计算参照值，M32R 执行仍是原 PythonBackend，未使用 C 模拟后端。

| 条目 | 应用结果 |
| --- | --- |
| FCC-001 | base 05，levels=[100,0,0,0,0,0,0,0,0,0]；卡片 <FCC-001；user=1。 |
| FCC*002 | base 05，Cont=+1，其余默认；卡片 <FCC*002；user=2。 |
| GRN*001 | base 02，Cont/High/Shad/Satu=2/5/5/-5；卡片 <GRN*001；user=3。 |

三项均为 T=2、S 模式 1、WB=9/9，用户记录 40 B 全零；九行逐字节等于参照结果，A14=A5、B14=B5；OK 后重开仍是刚应用的用户项。此处没有借用发布包页脚代替测试 DAT 身份。

证据：[MOUNT 三条目完整结果](tests/local/own-owner-users-mount/checks/mount-mount-user-entries.json)。其 552 B 参照条目 SHA256 分别为 a815eef4b3d2596f8bee3e45f39e7a1b56a09aaa219710639ef9305b2d04d852、6d3f09b12e80cc2a5d359220c44f8481727e7bb30eab4c853b35329660785c4d、fb3c3a59be1e2e9bc55ecd065f1494e68012f3b4a33fa40eba7b275b9ab1e175。

### 5.3 未跑的 28mm 17 组

不阻断本轮 MOUNT/50mm 结论。两个单元已直接执行共用的锁忙代码；各自的数据、pin、映射和计算结果另有独立检查，结论不依赖那 17 组通过。原回归记录是 MOUNT 12、50mm 27、28mm 10 组，剩余 17 组未执行，未计入通过。本轮仍不覆盖 28mm 或完整产品发布验收；阻断来自第 0 节。

## 6. 问题分级与最小修改建议

新增 P0：0；新增阻断 P1：1，见第 0 节。

| 分级 | 位置、复现与建议 |
| --- | --- |
| P2，说明准确性 | research/g150/REPORT.md:194 把十行写成 4+5+1，正确是 2+7+1；:255 写“op 6、2、5 合计每键最多一次”，空闲成功键实际可以各调用一次。查看 held-lock-g150 的第二个按键或 lock-during-rows 的调用轨迹即可复现。改为“本键首次遇 BUSY 后不再尝试写 S/记录”，并更正分类计数。 |
| P2，继承的结果身份记录 | research/g150/tests/g139_check.py:626 用 TEST_DAT 创建 Camera，:731-732 却统一以 H.DAT 写页脚。主机组按发布包启动时，users 等实际跑测试 DAT，页脚仍是 c4878f66…。应从实际 Camera.dat_path 记录身份，涉及两个 DAT 的用例应分别记录。该问题不推翻行为断言；本轮 MOUNT 三条目已用实际 DAT 身份独立重跑。 |

失归属的 S 待写、H01 自动接受、原厂 cursor_cache 残留和 MOUNT 旧旋钮数据按书面继承例外保留。尤其不能把未显示 Unsaved 读成“S 已完成”，也不能把 OK 的拒绝确认读成“原厂一定不关页”。这些限制已在第 2、3、5 节给出实际状态和证据。

被审源码、包和原报告未修改；以上是下一轮的建议。

## 7. 本轮执行、时间和边界

模型执行、输入复核及临时目录清理计时为 2026-11-01 10:09:45 +08:00 至 2026-11-01 11:31:05 +08:00，墙钟 81.3 分钟。共 22 个作业，各作业耗时合计 121.4 分钟，测试作业并发峰值 2。实际模型用例 34 次，原始状态为 24 PASS_M32R、3 OBSERVED_OWNER_PATH、4 OBSERVED_P1、3 FAIL。OBSERVED_P1 是同一新增缺陷在两单元及复核中的记录，不能计作通过。锁矩阵的五个子项、三个用户条目均不额外重复计数。

原始 FAIL 中两条是保留旧缺陷断言，另一条是本轮“OK 拒绝就应保持 8 行”的错误预期，见第 3、4 节。静态审计另有两次首次失败：旧主机结果没有内层开始/结束字段；切换 DAT 和生成条目对照用例使用的实际 DAT 与运行器默认目标不同。修正审计的数据模型后第三次通过，前两份日志、回执及执行时脚本字节均保留，没有改判。

完整列表见 [RUNS.md](RUNS.md)、[本轮回执审计](evidence/review-receipt-audit.json)、[原生输入与文件操作审计](evidence/native-input-audit.json)。对十行 FAIL 的九条对应通过证据在本轮重跑；28mm 的一条只独立核对原通过记录。首次封存因系统 Python 不接受 Z 格式 UTC，在临时目录清理后报错；修正时间解析后重新核对冻结输入并确认临时目录不存在，未重建删除数量。[首次封存错误记录](evidence/seal-initial-error.txt)。

所有模型作业经 run_case.py，在同一前台进程树内以 nice -n 10 和 /usr/bin/python3 -I -B 执行；用 kqueue 阻塞等待，超时为 2,400–4,800 s，均超过对应历史整组用时的三倍。没有开子代理，没有 git 写操作，没有联网，没有访问任何存储卡。离线沙盒禁止网络，文件写入只允许本复审目录、指定 Scratch 及 /dev/null。

写入目录只有 research/review_g150/ 和 /Volumes/Workspace/Scratch/tmp/projectricoh/review-g150/。测试缓存与 C 数学参照库按作业隔离。末次核对 32813 个冻结文件无增删改，467 项原清单再次全部匹配；Scratch 已清理，且所有本轮测试作业都已结束。挂载卷为 APFS，UUID=14BE04EB-AF49-497E-B36A-B078B2F7C5E8。[封存回执](evidence/seal.json)记录实际清理与时间；本目录 SHA256SUMS 的路径相对仓库根，涵盖最终报告、脚本、原始结果、日志与回执，清单自身不在其中。

复跑示例须使用新的 job 名及尚不存在的输出路径，以保留本次证据：

```sh
mkdir -p /Volumes/Workspace/Scratch/tmp/projectricoh/review-g150
/usr/bin/python3 -I -B research/review_g150/run_case.py \
  --generation 150 --job repeat-unverified-mount --timeout 2400 \
  --outputs research/review_g150/tests/local/repeat-unverified-mount/checks/mount-unverified-late.json \
  -- /usr/bin/python3 -I -B research/review_g150/previous_state_checks.py unverified-late --unit mount
```

示例先重建已清理的指定 Scratch 目录。新增独立用例在 review_checks.py，确认写入观察在 owner_trace.py；最终产物及原记录检查在 static_review.py，回执、冻结输入和清单检查在 finish_review.py。

