C 的原厂列表回退尚未定位：WB 1,1 会挡住记忆恢复，但 G154L 的这道检查不会撤掉 DAT 列表。

本报告区分现场事实、代码结论和模拟器实测。六组冷启动对照均已由 strict_r4 快后端及独立 Python 参考后端复核；模型没有复现现场 C 的列表回退，不能用模型结果否认机主观察。

## 对象与证据边界

研究对象是用户指定的五份现有 DAT。逐份核对完整 SHA、区段 CRC，并把内嵌引擎与对应 ELF 的代码区逐字节比较。没有构建、修改或交付 DAT。

| 对象 | SHA-256 | 对应源码与构建 |
| --- | --- | --- |
| G154L | `5f6191c88e7691472541dce245df67679390aa850ffd110e8f8eb35f4b24c681` | `firmware/engine_v65_g154_looks/`；`firmware/package_v39_g154_looks18_test/local/build/engine.elf` |
| g155c release | `69fa85104fcb449e613950bb58c802b9b64464769ae524fe3f7303e06093c2ad` | `firmware/engine_v67_g155c/candidate/local/boot-off/engine.elf` |
| g155c test | `c3017d3663e9501b43c921e3b46333b74d751eaa170781c4e1a00d90118f0335` | `firmware/engine_v67_g155c/candidate/local/boot-on/engine.elf` |
| g156 release | `f42b81a854d86b66ee7f65ac0123153c7e54e59d6e3d2079834490771d0ce1e0` | `firmware/engine_v68_g156/candidate/local/boot-off/engine.elf` |
| g156 test | `0f4f26d4cd3669915b41ce8e38260a61c60c590e2c581cb72e93f52a2ac631f7` | `firmware/engine_v68_g156/candidate/local/boot-on/engine.elf` |

G154L 使用包装内 SHA 为 `8233a1c464b29ba88cfdfce1d083b9bf652586edeb216cacf6f16cf36788b25d` 的 v3.9 机身。g155c/g156 使用 SHA 为 `a04f1ed40143b2c54d7f28e3af8af1f9a5ef5e115edf49eb404b8e26a53509c8` 的 v3.10 机身。两组不混用。

G154L 的构建确实沿用原 g154 C 对象，再按最终数据长度重链。当前 v63 与 v65 的全部 C、头文件、汇编和链接脚本一致，旧重链记录中的 28 份对象/库哈希仍匹配。当前 v3.9 resident ELF 与指定机身内 resident 的差异全部落在 trust 常量，函数代码一致。g155c 与 g156 的相关源码只有三处代次校验变化，恢复和应用逻辑一致。证据见 `local/identities.json`、`local/audit.json`、`local/frozen.json`；构建来源见 `research/g154_looks_r1/build.py:59`、`research/g154_looks_r1/relink.py:100`、`research/g154_looks_r1/build.py:118`。

每例从 MAIN 第 0 步创建新 Machine，不读取整机快照。用已有原厂逻辑读取边界重放完整设置块，模拟已经保存的设置。最终现场对照明确使用 AUTO 预设，编码为 0；挑战输入从留存的 MOUNT 设置块派生，改入本包有效的 HC BW +1 记录及 B/C 单变量，再重算原厂校验。它们不是机主现场设置转储，也不是原厂 MENU 操作全流程。早期保留 Multi-P AUTO 的夹具及所有未完成运行不计入最终现场矩阵。模型的 NAND 写入缺口保留，不能把重放称为真实关机写 NAND 成功。方法来源见 `research/tweak_memory_r1/REPORT.md:29`，本轮可复跑程序与原始证据全部在 `local/`。

最终矩阵 6/6 通过：G154L 的 B/C、g156 test 的 B/C、g156 release 的 B/C。每对首菜单的完整 4096 B S 块和 552 B 引擎状态逐字节一致，初始引擎状态均为完整原厂 04。G154L B 的后续 HC BW 卡片状态也比较了完整 S 和 552 B；G154L C 与 g156 test C 另核对了居中后重入仍不载入 +1。381 个冻结输入及 178 个历史源码文件的哈希校验通过。最终比较见 `local/matrix.json`，复跑方法见 `local/METHOD.md`，封存清单及回执为 `local/SHA256SUMS`、`local/seal.json`。这些通过项验证模型及代码路径，不关闭下文的现场 OPEN。

## Q1：恢复门不会直接撤下列表

现场 A 说明同一包、同一 MOUNT 单元的 HC BW +1 能跨开关机保留；这不支持“所有设置都保存失败”的解释。A 的 WB 居中没有照片，仍按机主说明保留为推定。若 Standard/WB 中性条件成立，A 与下述恢复路径一致；AUTO 预设不在这道检查中。g154 只读回记忆供预选，不在开机自动套用颜色，所以列表里的当前 04 标记也不能代替进入 HC BW 后读取实际 Cont。

代码结论：G154L 在首次进入 DAT 菜单时先置 `restore_done`，再检查原厂 Standard、WB 两轴编码 9/9、Body 设置来源、完整原厂九行及 T=2。通过后还要满足非 MY、内置条目索引、完整 40 B 记录与本包身份相等、合法微调值，以及配方本身无需额外原厂设置。WB 不居中会提前返回 `ENG_OK`，不会返回“关闭 DAT”或清空记忆记录。

具体路径是 `firmware/engine_v65_g154_looks/candidate/containers/product/src/firmware/engine/core/eng_core.c:646` 进入 `eng_menu_open`，在 `eng_core.c:656` 调 `boot_restore`；`eng_core.c:791` 置一次性标志，`eng_core.c:794` 检查 Standard/WB/来源/九行/T，`eng_core.c:799` 干净返回，`eng_core.c:808` 再限制记录及配方。随后 `firmware/engine_v65_g154_looks/candidate/containers/product/adapter.c:549` 继续同步菜单，`adapter.c:566` 发布 DAT 列表。

模拟器观察：只把 WB 改成 1,1 的完整设置块冷启动后，G154L 仍发布八行 DAT 列表，光标在 04，HC BW 的缓存为默认值，原来的 +1 记录保留。这与现场 C 的“原厂六项列表”不同。因此，WB 门能解释没有恢复数值，不能单独解释列表回退。模型自己的原厂描述符为七项，也没有复现机主所见的六项分支。

列表接管另有独立条件。`firmware/engine_v65_g154_looks/candidate/engine_services/services.c:80` 要求正在原厂 Image ADJ 状态；`services.c:85` 检查菜单层、栈和当前入口；`services.c:94` 要求尚未接管时仍是指定原厂描述符、行数为 7，已接管时则须是自己的八行列表。不满足就返回 `RV_STALE`，随后 `firmware/engine_v65_g154_looks/candidate/containers/product/adapter.c:367`、`adapter.c:566` 报错，再经 `adapter.c:154`、`adapter.c:93` 放弃本次接管。重新绑定或菜单打开失败还会经 `adapter.c:543`、`adapter.c:414` 走相同的释放路径。这些是代码中的列表失败边界，WB 数值不是这里的直接判据。现场说的“六项”是可见条目数，没有描述符或 resident 状态证据，不能据此认定它命中了行数检查。

代码结论：一旦本次初始化已经运行过恢复检查，WB 放回中间不会自动重试恢复。`eng_core.c:656` 只在 `restore_done` 为零时调用；返回中性值不会清这个标志。同次开机的“列表能否回来”是另一件事：若只是临时 UI 条件不满足，后续菜单入口可以重试；若 resident 已退役，则必须重启。后者见 `firmware/engine_v65_g154_looks/resident/resident.c:39` 与 `firmware/engine_v65_g154_looks/resident/hooks.c:140`。

本轮另有“冷启动 C，随后只在 RAM 中居中 WB，再经真实按键关闭/重开 DAT 菜单”的挑战。它检查一次性恢复标志，不冒充原厂 WB 编辑器操作。列表保持 DAT，+1 没有随后载入。由于模型一开始就没有发生列表回退，这个结果不能证明现场 C 在同次开机里也能恢复列表。

机主补充的“WB 居中后重启，DAT 列表恢复”已作为现场事实纳入；它同时重置 WB 条件、DAT 初始化状态和 resident 退役状态，不能区分上述分支。现场 C 同次开机能否恢复列表仍 OPEN。已经跳过的恢复检查不会因居中重试，这是代码结论；若 DAT 此前根本没有进入该检查，后续首次成功进入仍可检查，不能仅从原厂列表断言恢复标志已置位。

## Q2：Standard 的改写必须按观察时点分别判断

机主目前按指示顺序推定，B 的 MENU=Standard 出现在首次 ADJ 之前，但没有照片或明确时序确认。本报告保留这个推定，不把后续进入 HC BW 的行为当成已证实的前置事件。

若 Standard 确实在首次 ADJ 之前已经出现：在本轮验证的 MAIN 冷启动路径中，v3.9 resident 不会主动装载 DAT 或套用 04，DAT 的首次装载由 H01 触发。`eng_init` 把自己的 RAM 状态初始化为 04，也不等于写原厂设置。若能另行证实这个阶段发生了设置字节改写，应追原厂保存/读取/初始化流程，时点在 `boot_restore` 之前；当前没有机主的持久字节或启动写入轨迹，不能给某个原厂函数定责，也不能排除只显示了另一份缓存。依据是 `firmware/engine_v65_g154_looks/resident/hooks.c:143`、`firmware/engine_v65_g154_looks/candidate/containers/product/src/firmware/engine/core/eng_core.c:169`。

这还限制了 B 的判因：如果实际设置字节在首次 ADJ 前已经变成 Standard，不能仅凭“关机前选过 Vivid”认定它命中了非 Standard 门。此时必须另有恢复条件不满足、记录变化，或显示值与受检设置不一致。可能需要区分的条件是完整单元九行/T、设置来源及有效记录，见 Q1 的检查链；本轮没有现场值，不能选其中一个定责。下面的模拟明确保留 Vivid 到恢复检查，只验证这一个拒收条件及之后的手动应用路径。

若 Standard 是进入 HC BW 后查看：DAT 会在应用 HC BW 时写入它的原厂设置计划，包含 Standard，发生在恢复检查之后。恢复先被跳过，条目缓存留在默认；用户再选 HC BW，正常应用成功后会写入默认 Cont 和一份新的默认值记录。路径为 `firmware/engine_v65_g154_looks/candidate/containers/product/adapter.c:453`、`adapter.c:421`，以及 `firmware/engine_v65_g154_looks/candidate/containers/product/src/firmware/engine/core/eng_core.c:288`、`eng_core.c:435`、`eng_core.c:458`。

快模拟器和参考模拟器已走完后一条路径：有效 Vivid 冷启动，首次 DAT 列表仍为 Vivid，旧 +1 记录仍在；再通过按键进入 HC BW，原厂选择变成 Standard，Cont 变为默认，记录也更新为默认。参考写入轨迹确认第一次改变选择值的 store 位于 DAT 引擎，随后原厂预览重复写了相同的 Standard；实际写计划的源码为 `firmware/engine_v65_g154_looks/candidate/engine_services/services.c:227`。这能解释“读完 HC BW 后看到 Standard”，不能解释已证实发生在首次 ADJ 前的变化。

Vivid 的正确原厂编码是 09，来源为 `research/stage1_ui/REPORT.md:33`，并已核对原厂提交指令。早期误用无效编码 02 的夹具全部作废；原厂把无效编码归一化为 Standard 的结果不算现场 B 的解释。

## Q3：非零 WB 是潜在恢复缺口，当前五包没有这样的配方

代码结论：`compute` 把配方 record[49]/[50] 的有符号偏移换成原厂 WB 编码，`make_plan` 再将两个编码写入原厂设置。g154 的依据是 `firmware/engine_v65_g154_looks/candidate/containers/product/src/firmware/engine/core/eng_core.c:202` 与 `eng_core.c:288`；g155c/g156 的逻辑相同，g156 见 `firmware/engine_v68_g156/candidate/containers/product/src/firmware/engine/core/eng_core.c:204` 与 `eng_core.c:290`。

不能把问题表述为“所有非零 WB 配方下次必然让 ADJ 退回原厂列表”。准确范围如下。

- g154 的旧预选路径既要求当前 WB 为 9/9，又明确拒绝配方元数据带 WB 偏移；即使用户先居中，也不会预选这种配方。用户条目/Look 另有旧版记忆记录限制，不能与 WB 拒收混为一谈。依据是 `firmware/engine_v65_g154_looks/candidate/containers/product/src/firmware/engine/core/eng_core.c:304`、`eng_core.c:808`。
- g155c/g156 test 的 BOOT 先检查当前 WB 是否中性。若非零 WB 确实保存，并且启动检查时仍非中性，会在解码配方前干净跳过；不会由这道门直接撤下列表。若启动时已被用户或其它流程居中，则可以继续解码并尝试恢复非零 WB 配方，仍须通过完整事务验证。依据是 `firmware/engine_v68_g156/candidate/containers/product/src/firmware/engine/core/eng_boot.inc.c:21`、`eng_boot.inc.c:64`、`eng_boot.inc.c:69`、`eng_boot.inc.c:93`。
- g155c/g156 release 的 BOOT 功能关闭；它的首次菜单旧预选仍要求 WB 中性及配方 WB 偏移为零。依据是 `firmware/engine_v68_g156/candidate/containers/product/boot_adapter.inc.c:60` 与 `firmware/engine_v68_g156/candidate/containers/product/src/firmware/engine/core/eng_core.c:816`。

非中性 WB 是充分拒收条件，不是每次拒收的唯一原因；与非 Standard 等条件并存时，其它分支也可能先短路。

以上非零 WB 分支是代码结论。本轮没有为它制造或构建 DAT。

实际数据结论：逐份检查五包、三个单元的全部 16 条原生元数据，再展开可见内置、Look 和用户条目的归属。所有 WB 基底偏移均为 0,0。Look 与用户条目的原厂 WB 来自其基底记录，不能把深层颜色表变化或 Warm/Tint 旋钮误当作独立 WB 补偿。逐项清单见 `local/wb-inventory.json`，全部原生记录复核见 `local/audit.json`。原始记录读取与 Look/用户归属依据是 `firmware/engine_v68_g156/candidate/containers/product/src/firmware/engine/core/eng_data.c:28`、`firmware/engine_v68_g156/candidate/containers/product/src/firmware/engine/core/eng_boot.inc.c:9`、`eng_boot.inc.c:13`。

g156 中“配方自身带非零 WB 偏移”的清单为空。

| 单元 | release：8 内置 + 10 Looks | test：8 内置 + 10 Looks + 3 用户 |
| --- | --- | --- |
| A12 50mm | 无非零 WB 配方。 | 无非零 WB 配方。 |
| A12 28mm | 无非零 WB 配方。 | 无非零 WB 配方。 |
| MOUNT A12 | 无非零 WB 配方。 | 无非零 WB 配方。 |

如果机主通过原厂 MENU 把 WB 改为非中性，任何已保存配方都可能命中共同启动门；这与配方自身是否带偏移是两个问题。

旧 F-CC PASS 没有反证这道门。第二轮报告继承的是第一轮同 SHA 的 MOUNT 用户第 2 条 F-CC 结果，见 `research/tweak_memory_r1/REPORT.md:22`、`REPORT.md:27`。本轮直接重读它的持久重放 S 块：基底是 05 F-CC，配方 WB 偏移为 0,0，实际 WB 编码为 9/9，记录的 Cont 为 +2，40 B CRC 与指定 g155c test 身份均正确。它是在中性 WB 条件下通过，不是带非零 WB 的恢复用例；证据为 `local/audit.json` 的 `old_F_CC`。

## Q4：g156 的 B/C 行为

以下预测以“对应新包已重新保存有效 HC BW +1、普通受支持模式、完整原厂单元基线，B 的 Vivid 或 C 的非中性 WB 确实到达启动检查”为前提。旧 g155c 记录不能直接拿来验证 g156，DAT 身份不同会另行拒收，见 `firmware/engine_v68_g156/candidate/containers/product/src/firmware/engine/core/eng_boot.inc.c:18`。

| 条件 | 参数与首菜单 | 开机自动套用 | 是否因这道门退回原厂列表 |
| --- | --- | --- | --- |
| test，B：Vivid，WB 中性 | 旧 +1 记录保留，缓存为默认，列表停 04。 | BOOT 干净跳过。 | 不会；模型仍为 DAT 列表。 |
| test，C：Standard，WB 1,1 | 旧 +1 记录保留，缓存为默认，列表停 04。 | BOOT 干净跳过。 | 不会；模型仍为 DAT 列表。 |
| release，B：Vivid，WB 中性 | 旧 +1 记录保留，旧预选跳过，缓存为默认，列表停 04。 | 此包原本就关闭 BOOT 套用。 | 不会；模型仍为 DAT 列表。 |
| release，C：Standard，WB 1,1 | 旧 +1 记录保留，旧预选跳过，缓存为默认，列表停 04。 | 此包原本就关闭 BOOT 套用。 | 不会；模型仍为 DAT 列表。 |

四项 g156 对照均已由快后端及参考后端完成并通过统一核对，均没有单元颜色 W 写入。这里“记录保留”只描述重放输入在模型中的 40 B，不推断相机实际 NAND 当时保存了什么。随后手动选择 HC BW 会使用当前缓存值，应用成功后会把旧 +1 记录覆盖成默认；这是 g156 的代码结论，本轮实走这一后续路径的是 Q2 的 G154L 对照。

g155c/g156 的启动与菜单源码相同，只有代次校验变化，所以 g155c 的代码预测相同。g156 没有修复这两道恢复门。v3.10 会在首次菜单前装载引擎，加载时机与 v3.9 不同；这不能直接证明它修复了现场 C 未定位的列表回退。

## Q5：g157 建议与风险

优先把“记忆值可以读回”与“现在允许自动套用颜色”分开。读取本身仍绑定当前 S 来源和 epoch，未知来源或非法记录不载入。完整记录、CRC、单元、DAT 身份和合法档位都通过后，可以把记忆值载入条目缓存；原厂图像设定或 WB 与自动套用条件不符时，保留原厂状态，并显示明确的未套用原因。这样用户进入 HC BW 时仍能读到保存的 +1，也能分清当前正在生效的颜色与尚未应用的记忆。不要把“已经读回记忆”画成“配方已生效”。当前初始化默认值和预选写缓存的连接点见 `firmware/engine_v68_g156/candidate/containers/product/adapter.c:526`、`adapter.c:557`。

列表提示应区分“WB 非中性”“原厂图像设定不同”“记录不属于本包”“记录损坏”和“恢复事务失败”，至少显示一个明确原因。可复用现有尾行或短状态文字，遵守现有行长与八行显示合同。WB 归中后可让用户明确选择“应用已保存值”；不要把归中动作本身变成隐式颜色写入，也不要在一次失败后无限自动重试。

诊断还要覆盖 DAT 没装载成功或已被 resident 退役的情况，此时 DAT 内的提示根本不会执行。应先利用 resident 的现有故障/状态信息区分加载、会话和 UI 归属失败，必要时为后续机身诊断保留明确原因码；不能靠删 WB 恢复门来修复未定位的列表回退。相关退役边界见 `firmware/engine_v65_g154_looks/resident/resident.c:35`、`firmware/engine_v65_g154_looks/resident/hooks.c:140`。

不建议直接删除 Standard/WB 检查来实现“任何原厂设置都自动恢复”。B 最后主动选择 Vivid，可能就是用户希望保留的状态；自动套回 HC BW 会覆盖这个选择。若要支持这种策略，必须先确定用户优先级和 WB 归属，再保持完整的准备、写入、读回及补偿事务。全部九行、T、S 计划、记录身份、模式、锁和 DIRTY/GUARD 检查继续有效；颜色不完整就回退现有的完整纯 04，不能放行部分颜色或把非中性状态重新命名为纯 04。现有事务依据为 `firmware/engine_v68_g156/candidate/containers/product/src/firmware/engine/core/eng_boot.inc.c:73`、`eng_boot.inc.c:88`、`eng_boot.inc.c:97`。

若后续要支持配方非零 WB，记录应分别保留用户原厂 WB 基线、配方偏移和上次有效写入值；只有完整身份与来源验证通过，才能把非中性 WB 视为本配方留下的兼容状态。只比较“当前值等于上次值”不能证明用户没在 MENU 里操作过。是否把配方偏移与用户补偿相加，会改变颜色语义，需要单独定规则，不能随本次修复暗改。

格式可考虑新的、仍占 40 B 的记录版本：当前 Amount 范围可用一个无符号字节，其余九项档位可用有符号字节，省下的空间用于归属字段。保留两份 DAT CRC 与记录 CRC，不借用相邻未知尾部。所有值须先按当前元数据验证，再压缩；旧版本归属不明时只恢复显示或要求重新保存，不能猜测 WB 来源。当前范围依据是 `firmware/engine_v68_g156/candidate/containers/product/kv2/kv_data.c:43`、`kv_data.c:61`，现有 40 B 格式见 `firmware/engine_v68_g156/candidate/containers/product/src/firmware/engine/core/eng_core.c:303`。

空间是实际限制：g156 test 的装载余量只有 156 B，代码余量为 976 B；release 装载余量为 2,016 B。可先合并旧预选与 BOOT 的重复解码，避免叠加另一套解析器。本轮不构建 DAT，因此没有宣称以上改动一定装得下；将来必须对最终链接产物重新验尺寸、BSS 和重定位。依据是 `firmware/package_v310_g156_test/MANIFEST:4`、`MANIFEST:10` 与 `firmware/package_v310_g156/MANIFEST:10`。

后续验收应保留 A/B/C，增加三个单元的非零配方 WB、原厂 WB 冲突、归中后的同次开机重入、test/release 分别验证、旧记录/坏 CRC 拒收，以及写入中断和补偿失败。全部以“完整目标或完整纯 04”验收，不用缓存正确替代颜色正确。

## OPEN 与不作出的结论

- C 回到原厂六项列表的直接分支，以及 WB 居中后不重启能否重新接管，尚未定位。WB 恢复门本身不足以解释。
- C 居中重启后只确认了列表回来，没有确认 HC BW +1 是否仍在，不能把列表恢复写成数值恢复。
- B 推定首次 ADJ 前显示 Standard，但顺序未证实；没有确认对应设置字节、原厂写入点或持久输入。后读 HC BW 的 DAT 改写路径已单独解释，不能代替这个缺口。
- 没有机主完整 S 转储、实际启动时单元九行/T 与 resident 状态，模型不能穷尽原厂 MENU 的其它副作用。对 WB 居中的 RAM 挑战不等于原厂编辑器成功提交。
- 没有新增相机、SD 卡或网络访问，没有真实 NAND 成功保存/读回或掉电验收。机身已经换成 v3.10，不再等待 v3.9 现场补测；后续 v3.10 证据不能追认旧现场分支。
- R8051964 按机主说明排除，不用于本问题判因。本报告不构成新 DAT 的上卡或成片验收。
