不能上卡

本轮发现启动状态处理和记录归属检查不符合设计。合格基线上的恢复比较通过，不能抵消这些排除分支的问题。结论只绑定下表的 v3.8 + g138 DAT，不涉及重刷机身。

状态为 FINAL。

| 对象 | 身份 |
| --- | --- |
| GXRCE.DAT | generation 138，91,432 B；`88a4359b284ba5a9765a3dfb1177679ec4c4da0687d9f9a6fb3d31fe19acb02a`。 |
| 机身 ilaunch3 | v3.8；`d4fa3b46da137b8b7c7c703e66750a8249c0715271290c0fdb490a2f7a239a90`。 |
| resident build id | `79d8e2a2dfc322f3c2470c0369d736473f0b478dcf7c0e3bebf1feb0e82596f2`。 |
| 主请求 | 108,060 B，上限 108,124 B，余量 64 B。 |
| 包差异 | 30 个文件中只有 DAT 不同，其他 29 个与 g137 相同。 |

静态已证：包身份、尺寸、ELF 与 DAT 代码对应、编译输入、原厂锁参考代码和下述源码分支。主机已证：实际矩阵、模型中的 M32R 菜单路径、独立 C 比较和明确标出的指令派生 C 检查。H01 和按键由主机调用固定入口；设备、S 和图形叶函数采用模型。采用用户给定的 v3.8 + g137 在 50mm 上实测通过这一前提。

本轮没有执行相机、测试卡或 NAND 操作。合成的异常起始状态证明程序如何处理该输入，不能单独证明真实开机必然到达该状态。

## 问题表

下表位置以仓库根为基准。`core` 指 `firmware/engine_v55_g138/candidate/containers/product/src/firmware/engine/core/eng_core.c`，`services` 指 `firmware/engine_v55_g138/candidate/engine_services/services.c`，`adapter` 指本代 `candidate/containers/product/adapter.c`。

| 编号 | 级别 | 位置 | 说明 | 建议 |
| --- | --- | --- | --- | --- |
| g138/P1-01 | P1，本版复现，OPEN | core:158、195–205、595–596、640–677 | 初始账本被置为 stock。首次完整读回已经发现九行不一致后，程序仍保留这个账本。用户选 04 Default 时，差分可以为零，实际九行没有回到 stock，却接受 04 并写下 04 记录。另一个模型输入中的完整 5 号九行与 S 模式 4 在首开被原样保留，也没有落实“完整配方或纯 04”。 | 未确认基线时，第一次手动应用必须完整写入并读回九行和 T，核对 S 后才能发布或记忆。不能让未知原厂状态使用 stock 差分账本。首次 ADJ 前的更广启动承诺需要另外成立的启动依据。 |
| g138/P1-02 | P1，新增，OPEN | services:314–333；core:370–371 | op 5 只校验待写的新记录，没有核对当前尾部的归属。未知非零 40 B 在首开被保留，下一次普通配方选择却会把它覆盖。选择用户条目同样可以清零。违反 `persist_recipe_r2/REPORT.md` §7.1 的未知非零区只读要求。 | 在同一锁协议下检查原记录，只允许全零或可识别的本程序记录被替换、失效。未知非零内容保留，并提示未记住。 |
| g138/P1-03 | P1，恢复条件不完整，OPEN | core:656–677；`persist_recipe_r2/REPORT.md` §7.2(2)；实现报告 §6(5) | 恢复资格没有普通模式、MY 或启动来源事件的凭据，只有参数值和 epoch。epoch 相等没有给出具体模式。实现报告也确认，MY、复位或来源事件后若这些值仍相同，旧记录会被恢复。因此不能宣称程序只在已核实的普通启动恢复。 | 取得可验证的普通启动及失效事实；没有凭据就不自动恢复。原厂事件后旧记录失效的问题必须明确处理，不能只靠同值参数排除。参数相同不能替代启动来源的证据。 |
| g138/P2-01 | P2，OPEN | adapter:274；实现报告 §6(4) | `!6 F-CN` 表示本次生效但未记住，含义没有写在屏幕上。端点 `!` 刚被删除，原有 T 警告也使用 `!`，用户已经明确不理解该符号。补写成功后还有一帧旧提示。 | 在既有行显示可理解的短文，例如 `6 NoSave`，并在保存结果确定后刷新该行，保持 8 行。 |
| g138/P2-02 | P2，OPEN | core:406–419；实现报告 §6(3) | 原厂锁持续占用且需要写 S 时，单次服务立即返回 BUSY，但一次按键仍会触发 6 次补偿，共 7 次 op 2 尝试，再进入 ERR。每次仍零写 S；这不是一次按键只取锁一次。 | 把锁忙与通信/写入失败分开处理，减少没有机会完成的整套重写。维持 uncertainty 和正确的 ERR，不用无锁写或等待解决。 |
| g138/P2-03 | P2，验收步骤问题，OPEN | 本代 `candidate/containers/product/ui_v2_data.c:22`；实现报告 §5(3) | 指定发布 DAT 的用户条目数为 0，MyRec 会显示 None，照片 3 的 FCC-001 选择无从执行。B 的模型检查使用另一个 32 条用户 DAT。 | 修复后的正式测试包须先包含至少一个用户条目，再封存其新 SHA 并复核。不能把用户夹具静默替换成指定发布 DAT。 |
| g138/P2-04 | P2，静态重查缺项，OPEN | services:280、312、321–322；r2 §6.1 | S 长度和扩展版本在 IRQ 临界区前读取和检查，临界区内只重查 S 指针、归属与 settings epoch。同地址的长度或版本变化没有被重新核对。当前未证明原厂流程能触发该窗口，不能写成已复现越界。 | 在同一 IRQ 区间、取得锁之前重新核对当前长度和扩展版本；变化时零写入拒绝。 |

未确认新增 P0。P1-01 的起始九行由模型明确提供，真实启动可达性未单独重跑；错误的 04 接受路径已由最终 DAT 执行确认。P1-03 是缺失资格凭据的静态结论，不冒充 MY 全流程实测。

## 1. S 写入与原厂参数锁

本版 DAT 的直接 S 写入集中在 op 2 和 op 5。两者共用 `services:321–335` 的临界区，先在 IRQ 关闭时检查实际入口归属、S 指针和 settings epoch，再检查锁 ID 55、计数恰为 −1。成功只作 `−1 → 0 → −1`，忙分支不递增计数、不登记等待者、不调用等待或释放函数。

锁结构位于 `0x204104F0`：该地址是 s32 计数，`0x204104F4` 是 semaphore ID。原厂初始化 `0x20067B2C → 0x20060B84` 写入 −1/55；取得入口为 `0x20060BB4`，释放入口为 `0x20060C10`。本地参考与当前 ilaunch3 的对应代码一致。−1 空闲、0 已持有、正数含等待者。本版没有调用原厂无限等待取得函数。

实际 M32R store 观察为 PASS_M32R，8 个 op 2/op 5 锁状态用例。检查包括同值 store，不能只用最终 S 相同代替零写入。忙调用本体没有 S 或锁 store；测试在 IRQ 恢复后的明确模型边界让原持有者释放，以便上层结束。这不是原厂任务调度证明。

op 5 在取锁前完成新记录格式及 CRC 校验，在同一 IRQ 区间写 10 个 word 并读回，最后释放。正常任务和原厂保存不能观察到这 10 次复制的中间状态。它没有提交 NAND，也不写 `S+0xFFC`。物理断电和原厂整块保存仍属于原有保存流程，40 B CRC 不能代替它。

“旧记录保留”只对写入前的 BUSY、STALE 等拒绝成立。读回不一致返回 RV_VERIFY 后没有旧记录回滚，不能承诺任意写异常仍保留旧值。S 长度和扩展版本未在临界区重查，按静态缺项记 P2-04，不宣称已触发真实调度窗口。

单次调用的互斥满足要求；未知旧内容的归属检查不满足，见 P1-02。op 2 不包含与 op 5 相同的逐 word 读回循环，不能把报告“写完都在临界区读回”的概述扩展到 op 2。

## 2. 恢复资格、完整状态与行为变化

在当前 Engine 实例内，恢复只消费一次 `restore_done`。S 模式 1、WB 9/9、`S+8=0`、单元与 epoch、T=2 和九行完整读取都参与资格判断。记录按当前单元、配方、十个值、数据标识和 CRC 重新编码后整条比较，非法值还会被计算入口拒绝。恢复后的读回没有使用冷状态提前返回。该检查没有补上普通模式的事件凭据，见 P1-03。

5 号 Cont=+1 的独立恢复与按键路径比较：50mm PASS_M32R；28mm PASS_M32R；mount PASS_M32R。每个已通过单元比较 S 全部 4096 B、九行全部 503 B、T 和同一 L1 显示状态，差异为零。私有调用历史和相机硬件状态不在这个逐字节比较内。

条件不满足时，g138 不写 S 和单元九行，也不显示已应用的 `>`。从正确状态进入该分支，不会仅靠这次拒绝动作制造部分写入；但它保留已有的不一致状态，不能据此称为纯 04。

`focused_review.py` 提供了“5 号完整九行、T=2、S 模式 4”的模型起点。首开保留该组合，选择 04 Default 后只归一化 S，九行仍是 5 号，单元 W 为 0。程序已经把未知现场当作 stock 计算差分。`partial_baseline_review.py` 另提供只差一行、其他恢复参数全部合格的模型起点；首开拒绝后，04 Default 仍以 0 次 W 显示 `>4 Std` 并记住 04，OK 退出后该非 stock 行仍在。证据为 `evidence/partial-baseline.json`。

P1-01 的修复必须覆盖首次手动选择，不能只改恢复标签。该路径没有建立可信 live 账本前，也不能把确认或记录写入视为完整生效。

## 3. 借用内存

| 借用区域 | 当前调用关系及寿命 | 结论 |
| --- | --- | --- |
| `g.work.base` | `eng_data_validate` 展开后立即算 CRC；初始化展开后立即复制到 `g.stock`；计算路径展开后立即使用同一 base。`kv_apply_work` 明确支持 base 与 `work.base` 相同。产品调用点没有跨下一次展开保留该指针。 | 当前静态调用关系成立。 |
| `g.work.result` | 初始化时作 224 B trust 缓冲。semantic 校验只复制 view 内容，没有把 trust 指针留进 view。初始化结束后，数学计算才使用 result。552 B 容量足够。 | 当前静态调用关系成立。 |
| `KvWork.stage` | 1104 B 数学暂存承载 260 B EngIo。`compute` 内没有服务调用；服务从计算返回后才使用该区。fresh 使用独立的 epochs/snap，RPC 的回执不会被 fresh 覆盖；plan 与 record 在各自阶段重新构造。settings_match 返回后才调用 apply_impl，end 与 RPC 也不嵌套保存回执。 | 当前静态调用关系成立；由实际计算及菜单回归补证。 |
| `Integrated.spare` 联合体 | 旧 `PsStore` 在本产品路径没有读写者。call、list、list_reply、port 是互不重叠的结构成员。初始化把 port 复制进 Engine 后不再借用原指针；list 请求与其间的 core_call 不覆盖彼此。resident inflight 与现有 busy 门保留。 | M32R `Integrated` 仍为 3920 B，未移动后续字段。 |

`Engine` 从 4864 B 增至 4872 B，旧字段偏移保留。独立构建 g137 的分离缓冲版本与 g138 比较全部 3430 个可选点，并打乱顺序再算一次，6860 次均为 552 B 逐字节相同。没有发现跨调用残留。最终指令派生 C 检查已完成 3430 个参考点，原解释器另复核 45 例。向量多重集合与当前可选点表核对一致。九行加 T 的 505 B 实际参数投影中，相邻档位重复 0 组。镜像身份比较只在副本中归一化 ELF 标识的 4 B t_seen，执行 RAM 不变，逐项依据见各 identity-binding.json。它使用本轮新建模型的 RAM 和主机驱动计算入口，不能替代 RTOS 或原生菜单路径。

## 4. 尺寸与堆

DAT 增加 1496 B，BSS 减少 1560 B，主请求减少 64 B。当前 DAT 91,432 B、引擎段 62,512 B、BSS 9,124 B，主请求 `7504 + align4(DAT+BSS) = 108060`，没有放宽 108,124 B 预算。机身仍是 7908 B 常驻体、距 root 176 B 的原 v3.8。

本轮独立重建结果为 PASS_REBUILD，91432 B，SHA256 `88a4359b284ba5a9765a3dfb1177679ec4c4da0687d9f9a6fb3d31fe19acb02a`。新 ELF SHA256 为 `2aac1ef2c8f9bf0075274c41aa4c98cb108860c9062e8b2f2f7b817ea2594db8`，代码与新 DAT 对应。输出、服务 archive 和链接输入重定位到复审目录；最终链接参数另见 evidence/rebuild-link-audit.json。没有重建或改写机身，早期输出目录适配失败保留。

g129/P2-01 未关闭。按 g137 同一分配前提，三次 32 KiB 残留后的条件余量从 53,032 B 增至 53,096 B，仍小于后续 77,336 B 申请。DAT 没有新增显式原厂分配入口；按同一分配前提，主块缩小 64 B，没有在大小上加重该反例。额外首开 RPC 的实际峰值、连续堆、实际并存和拍摄峰值不能由这个算式证明。

## 5. C 的完整性

`kv_ui.c` 的数值页、逐项页和卡片简写共用格式函数，原 endpoint 函数及三处调用均已去掉。可选点、步进和数值页夹紧分支未改；数值页到端点仍停住，其余列表仍按 g137 循环。

本轮实际 M32R 50mm GR Pos Satu 检查停在 +6 和 −9，多按不动；卡片、逐项页和数值页没有端点 `!`。列表 C 检查覆盖 2814 个端点。3430 个单控制可选点的相邻输出没有相同项，独立比较也没有发现本版改变计算输出。该结论以其他控制保持默认为范围，不是所有旋钮组合的穷举。

保存失败与 T 警告仍能在其他页面显示 `!`，不属于端点标记。它们的提示问题见 P2-01。

## 6. 实现报告的开放项

当前实现报告第 6 节实际列了 9 项，全部评定如下。

| 项 | 级别及状态 | 本轮判断 |
| --- | --- | --- |
| 1. 新组合的相机验收 | P2，待用户验收 | 接受既有 v3.8/g137 实测前提。本轮不把主机模型冒充 g138 跨关机、原厂调度和 LCD 的新验收。单凭这个缺口不阻断测试卡；本轮阻断原因是问题表中的 P1。 |
| 2. 首次 ADJ 前尚未恢复 | P2，已知限制 | 符合用户指定的恢复时机。只有已确认的普通基线才能称为此时的纯 04，不能推广到被排除的原厂状态。 |
| 3. 持续锁忙的 6 次补偿 | P2，OPEN | 独立观察到 7 次 op 2、6 次补偿、3428 次通信和 1690 次单元 RAM W，最终 `ERR 0SX0`，S store 为 0，锁仍由原持有者保持。 主机模型计时不能换算为相机耗时。 |
| 4. `!` 提示未记住 | P2，OPEN | 用户无法从符号判断保存结果。提示滞后一帧方向保守，但没有解决可理解性。 |
| 5. MY、复位、来源事件后旧记录 | P1，OPEN | 与 P1-03 相同。缺少普通启动凭据和失效事实，参数恰好相同就仍可恢复旧记录。没有跑过实际 MY/复位全流程，不写成已现场复现。 |
| 6. DAT 更新让旧记录失效 | 设计限制 | 数据标识同时覆盖本 DAT，更新后拒绝旧记录是保守行为。用户需要重新选择并保存。 |
| 7. 仅余 64 B | P2，预算风险保留 | 当前不超预算，也没有加重连续堆反例。 |
| 8. 新增内存复用 | 本轮未确认缺陷 | 当前调用关系、尺寸和实跑比较见 §3。 |
| 9. 81 组及补充检查 | 已完成本轮执行 | 完整结果逐组列在下节，主机 C、指令派生 C 和 M32R 模型分别标明。 |

## 7. 完整回归和读取修改

已执行完整组 81/81。PASS 69，STALE_LABEL_CONTRACT 6，STALE_RETIRED_FUNCTION 6。PASS 必须同时有整组 OS 退出 0 和内层结果。旧约定失败保留原退出 1，不能改成原组通过。详见 `REGRESSIONS.json` 的所有 attempts。

81 组沿用 `--crc-implementation host`，绑定文件记录 CRC 主机调用数。矩阵证明的是该叶函数模型下的服务和菜单行为，不是全部 CRC 指令的执行证明。

共享模型原来的锁 0/0 没有执行原厂初始化，改为 −1/55 有原厂代码依据。附带把 S 改成 Standard、9/9、Body、扩展 0xD24、尾部零，会让冷启动原有 S 修复路径不再执行。因此正常夹具的 PASS 不能代表该路径；本轮用异常首开、实际 S store 观察和持续锁忙另查。

C 的文本期望修改符合本次约定，夹紧和完整参数断言保留。复审还修正继承套件漏掉的 g137 分隔线和空条目循环期望。最初失败均保留，修正只在复审包装器中。旧函数及旧黑白页面工作流不能只改常量，故保留原组错误，并单列当前检查；不把原退出 1 改成 PASS。详见 `WRAPPER.md`、各 job 的 `review-readings.json`。

实现者 27/27 保留为实现者证据。本轮附加整套早期完成六项后主动停止，回执为 −15，后续重点补测另列；停止的整组不计通过。

| 家族 | 单元 | 组 | 返回码 | 秒 | 状态 | 回执及替代证据 |
| --- | --- | --- | ---: | ---: | --- | --- |
| 124 | 50mm | safety | 0 | 361.4 | PASS | [evidence/receipts/group124-50mm-safety-final-r2.json](evidence/receipts/group124-50mm-safety-final-r2.json) |
| 124 | 50mm | locked | 0 | 307.627 | PASS | [evidence/receipts/group124-50mm-locked-final-r2.json](evidence/receipts/group124-50mm-locked-final-r2.json) |
| 124 | 50mm | nested | 0 | 426.562 | PASS | [evidence/receipts/group124-50mm-nested.json](evidence/receipts/group124-50mm-nested.json) |
| 124 | 50mm | cutpoints | 0 | 238.459 | PASS | [evidence/receipts/group124-50mm-cutpoints-final-r2.json](evidence/receipts/group124-50mm-cutpoints-final-r2.json) |
| 124 | 50mm | exits | 0 | 940.934 | PASS | [evidence/receipts/group124-50mm-exits-final-r2.json](evidence/receipts/group124-50mm-exits-final-r2.json) |
| 124 | 50mm | transitions | 0 | 855.529 | PASS | [evidence/receipts/group124-50mm-transitions-final-r2.json](evidence/receipts/group124-50mm-transitions-final-r2.json) |
| 124 | 50mm | values | 0 | 1620.374 | PASS | [evidence/receipts/group124-50mm-values.json](evidence/receipts/group124-50mm-values.json) |
| 124 | 50mm | view-reentry | 0 | 1543.027 | PASS | [evidence/receipts/group124-50mm-view-reentry.json](evidence/receipts/group124-50mm-view-reentry.json) |
| 124 | 50mm | reentry-six | 0 | 1294.185 | PASS | [evidence/receipts/group124-50mm-reentry-six.json](evidence/receipts/group124-50mm-reentry-six.json) |
| 124 | 50mm | users | 0 | 363.576 | PASS | [evidence/receipts/group124-50mm-users.json](evidence/receipts/group124-50mm-users.json) |
| 124 | 50mm | project | 1 | 140.891 | STALE_RETIRED_FUNCTION | [evidence/receipts/group124-50mm-project.json](evidence/receipts/group124-50mm-project.json)；[HOST_C PASS](boundary-sweep.json) |
| 124 | 50mm | labels | 1 | 938.485 | STALE_LABEL_CONTRACT | [evidence/receipts/group124-50mm-labels.json](evidence/receipts/group124-50mm-labels.json)；[M32R_MODEL PASS_M32R](evidence/labels-current-50mm.json) |
| 124 | 50mm | half | 0 | 178.615 | PASS | [evidence/receipts/group124-50mm-half.json](evidence/receipts/group124-50mm-half.json) |
| 124 | 28mm | safety | 0 | 395.204 | PASS | [evidence/receipts/group124-28mm-safety.json](evidence/receipts/group124-28mm-safety.json) |
| 124 | 28mm | locked | 0 | 325.898 | PASS | [evidence/receipts/group124-28mm-locked.json](evidence/receipts/group124-28mm-locked.json) |
| 124 | 28mm | nested | 0 | 454.596 | PASS | [evidence/receipts/group124-28mm-nested.json](evidence/receipts/group124-28mm-nested.json) |
| 124 | 28mm | cutpoints | 0 | 260.132 | PASS | [evidence/receipts/group124-28mm-cutpoints.json](evidence/receipts/group124-28mm-cutpoints.json) |
| 124 | 28mm | exits | 0 | 992.244 | PASS | [evidence/receipts/group124-28mm-exits.json](evidence/receipts/group124-28mm-exits.json) |
| 124 | 28mm | transitions | 0 | 905.183 | PASS | [evidence/receipts/group124-28mm-transitions.json](evidence/receipts/group124-28mm-transitions.json) |
| 124 | 28mm | values | 0 | 1594.931 | PASS | [evidence/receipts/group124-28mm-values.json](evidence/receipts/group124-28mm-values.json) |
| 124 | 28mm | view-reentry | 0 | 743.835 | PASS | [evidence/receipts/group124-28mm-view-reentry.json](evidence/receipts/group124-28mm-view-reentry.json) |
| 124 | 28mm | reentry-six | 0 | 1219.234 | PASS | [evidence/receipts/group124-28mm-reentry-six.json](evidence/receipts/group124-28mm-reentry-six.json) |
| 124 | 28mm | users | 0 | 610.284 | PASS | [evidence/receipts/group124-28mm-users.json](evidence/receipts/group124-28mm-users.json) |
| 124 | 28mm | project | 1 | 130.948 | STALE_RETIRED_FUNCTION | [evidence/receipts/group124-28mm-project.json](evidence/receipts/group124-28mm-project.json)；[HOST_C PASS](boundary-sweep.json) |
| 124 | 28mm | labels | 1 | 155.194 | STALE_LABEL_CONTRACT | [evidence/receipts/group124-28mm-labels.json](evidence/receipts/group124-28mm-labels.json)；[M32R_MODEL PASS_M32R](evidence/labels-current-28mm.json) |
| 124 | 28mm | half | 0 | 158.278 | PASS | [evidence/receipts/group124-28mm-half.json](evidence/receipts/group124-28mm-half.json) |
| 124 | mount | safety | 0 | 366.6 | PASS | [evidence/receipts/group124-mount-safety.json](evidence/receipts/group124-mount-safety.json) |
| 124 | mount | locked | 0 | 313.456 | PASS | [evidence/receipts/group124-mount-locked.json](evidence/receipts/group124-mount-locked.json) |
| 124 | mount | nested | 0 | 433.348 | PASS | [evidence/receipts/group124-mount-nested.json](evidence/receipts/group124-mount-nested.json) |
| 124 | mount | cutpoints | 0 | 244.808 | PASS | [evidence/receipts/group124-mount-cutpoints.json](evidence/receipts/group124-mount-cutpoints.json) |
| 124 | mount | exits | 0 | 967.236 | PASS | [evidence/receipts/group124-mount-exits.json](evidence/receipts/group124-mount-exits.json) |
| 124 | mount | transitions | 0 | 861.473 | PASS | [evidence/receipts/group124-mount-transitions.json](evidence/receipts/group124-mount-transitions.json) |
| 124 | mount | values | 0 | 1608.462 | PASS | [evidence/receipts/group124-mount-values.json](evidence/receipts/group124-mount-values.json) |
| 124 | mount | view-reentry | 0 | 711.833 | PASS | [evidence/receipts/group124-mount-view-reentry.json](evidence/receipts/group124-mount-view-reentry.json) |
| 124 | mount | reentry-six | 0 | 1223.61 | PASS | [evidence/receipts/group124-mount-reentry-six.json](evidence/receipts/group124-mount-reentry-six.json) |
| 124 | mount | users | 0 | 612.663 | PASS | [evidence/receipts/group124-mount-users.json](evidence/receipts/group124-mount-users.json) |
| 124 | mount | project | 1 | 131.624 | STALE_RETIRED_FUNCTION | [evidence/receipts/group124-mount-project.json](evidence/receipts/group124-mount-project.json)；[HOST_C PASS](boundary-sweep.json) |
| 124 | mount | labels | 1 | 152.17 | STALE_LABEL_CONTRACT | [evidence/receipts/group124-mount-labels.json](evidence/receipts/group124-mount-labels.json)；[M32R_MODEL PASS_M32R](evidence/labels-current-mount.json) |
| 124 | mount | half | 0 | 158.629 | PASS | [evidence/receipts/group124-mount-half.json](evidence/receipts/group124-mount-half.json) |
| 126 | 50mm | safety | 0 | 375.527 | PASS | [evidence/receipts/group126-50mm-safety.json](evidence/receipts/group126-50mm-safety.json) |
| 126 | 50mm | locked | 0 | 315.864 | PASS | [evidence/receipts/group126-50mm-locked.json](evidence/receipts/group126-50mm-locked.json) |
| 126 | 50mm | nested | 0 | 433.995 | PASS | [evidence/receipts/group126-50mm-nested.json](evidence/receipts/group126-50mm-nested.json) |
| 126 | 50mm | cutpoints | 0 | 244.345 | PASS | [evidence/receipts/group126-50mm-cutpoints.json](evidence/receipts/group126-50mm-cutpoints.json) |
| 126 | 50mm | exits | 0 | 952.595 | PASS | [evidence/receipts/group126-50mm-exits.json](evidence/receipts/group126-50mm-exits.json) |
| 126 | 50mm | transitions | 0 | 868.434 | PASS | [evidence/receipts/group126-50mm-transitions.json](evidence/receipts/group126-50mm-transitions.json) |
| 126 | 50mm | values | 0 | 1599.98 | PASS | [evidence/receipts/group126-50mm-values.json](evidence/receipts/group126-50mm-values.json) |
| 126 | 50mm | view-reentry | 0 | 750.049 | PASS | [evidence/receipts/group126-50mm-view-reentry.json](evidence/receipts/group126-50mm-view-reentry.json) |
| 126 | 50mm | reentry-six | 0 | 1213.92 | PASS | [evidence/receipts/group126-50mm-reentry-six.json](evidence/receipts/group126-50mm-reentry-six.json) |
| 126 | 50mm | users | 0 | 607.459 | PASS | [evidence/receipts/group126-50mm-users.json](evidence/receipts/group126-50mm-users.json) |
| 126 | 50mm | project | 1 | 131.953 | STALE_RETIRED_FUNCTION | [evidence/receipts/group126-50mm-project.json](evidence/receipts/group126-50mm-project.json)；[HOST_C PASS](boundary-sweep.json) |
| 126 | 50mm | labels | 1 | 152.613 | STALE_LABEL_CONTRACT | [evidence/receipts/group126-50mm-labels.json](evidence/receipts/group126-50mm-labels.json)；[M32R_MODEL PASS_M32R](evidence/labels-current-50mm.json) |
| 126 | 50mm | half | 0 | 155.971 | PASS | [evidence/receipts/group126-50mm-half.json](evidence/receipts/group126-50mm-half.json) |
| 126 | 50mm | other-users | 0 | 537.272 | PASS | [evidence/receipts/group126-50mm-other-users.json](evidence/receipts/group126-50mm-other-users.json) |
| 126 | 28mm | safety | 0 | 371.905 | PASS | [evidence/receipts/group126-28mm-safety.json](evidence/receipts/group126-28mm-safety.json) |
| 126 | 28mm | locked | 0 | 310.03 | PASS | [evidence/receipts/group126-28mm-locked.json](evidence/receipts/group126-28mm-locked.json) |
| 126 | 28mm | nested | 0 | 434.445 | PASS | [evidence/receipts/group126-28mm-nested.json](evidence/receipts/group126-28mm-nested.json) |
| 126 | 28mm | cutpoints | 0 | 243.885 | PASS | [evidence/receipts/group126-28mm-cutpoints.json](evidence/receipts/group126-28mm-cutpoints.json) |
| 126 | 28mm | exits | 0 | 944.714 | PASS | [evidence/receipts/group126-28mm-exits.json](evidence/receipts/group126-28mm-exits.json) |
| 126 | 28mm | transitions | 0 | 871.26 | PASS | [evidence/receipts/group126-28mm-transitions.json](evidence/receipts/group126-28mm-transitions.json) |
| 126 | 28mm | values | 0 | 1579.016 | PASS | [evidence/receipts/group126-28mm-values.json](evidence/receipts/group126-28mm-values.json) |
| 126 | 28mm | view-reentry | 0 | 735.203 | PASS | [evidence/receipts/group126-28mm-view-reentry.json](evidence/receipts/group126-28mm-view-reentry.json) |
| 126 | 28mm | reentry-six | 0 | 1204.168 | PASS | [evidence/receipts/group126-28mm-reentry-six.json](evidence/receipts/group126-28mm-reentry-six.json) |
| 126 | 28mm | users | 0 | 608.713 | PASS | [evidence/receipts/group126-28mm-users.json](evidence/receipts/group126-28mm-users.json) |
| 126 | 28mm | project | 1 | 130.828 | STALE_RETIRED_FUNCTION | [evidence/receipts/group126-28mm-project.json](evidence/receipts/group126-28mm-project.json)；[HOST_C PASS](boundary-sweep.json) |
| 126 | 28mm | labels | 1 | 149.89 | STALE_LABEL_CONTRACT | [evidence/receipts/group126-28mm-labels.json](evidence/receipts/group126-28mm-labels.json)；[M32R_MODEL PASS_M32R](evidence/labels-current-28mm.json) |
| 126 | 28mm | half | 0 | 154.853 | PASS | [evidence/receipts/group126-28mm-half.json](evidence/receipts/group126-28mm-half.json) |
| 126 | 28mm | other-users | 0 | 524.272 | PASS | [evidence/receipts/group126-28mm-other-users.json](evidence/receipts/group126-28mm-other-users.json) |
| 126 | mount | safety | 0 | 359.563 | PASS | [evidence/receipts/group126-mount-safety.json](evidence/receipts/group126-mount-safety.json) |
| 126 | mount | locked | 0 | 305.833 | PASS | [evidence/receipts/group126-mount-locked.json](evidence/receipts/group126-mount-locked.json) |
| 126 | mount | nested | 0 | 425.923 | PASS | [evidence/receipts/group126-mount-nested.json](evidence/receipts/group126-mount-nested.json) |
| 126 | mount | cutpoints | 0 | 237.834 | PASS | [evidence/receipts/group126-mount-cutpoints.json](evidence/receipts/group126-mount-cutpoints.json) |
| 126 | mount | exits | 0 | 941.944 | PASS | [evidence/receipts/group126-mount-exits.json](evidence/receipts/group126-mount-exits.json) |
| 126 | mount | transitions | 0 | 849.279 | PASS | [evidence/receipts/group126-mount-transitions.json](evidence/receipts/group126-mount-transitions.json) |
| 126 | mount | values | 0 | 1568.756 | PASS | [evidence/receipts/group126-mount-values.json](evidence/receipts/group126-mount-values.json) |
| 126 | mount | view-reentry | 0 | 704.426 | PASS | [evidence/receipts/group126-mount-view-reentry.json](evidence/receipts/group126-mount-view-reentry.json) |
| 126 | mount | reentry-six | 0 | 1183.63 | PASS | [evidence/receipts/group126-mount-reentry-six.json](evidence/receipts/group126-mount-reentry-six.json) |
| 126 | mount | users | 0 | 601.14 | PASS | [evidence/receipts/group126-mount-users.json](evidence/receipts/group126-mount-users.json) |
| 126 | mount | project | 1 | 129.942 | STALE_RETIRED_FUNCTION | [evidence/receipts/group126-mount-project.json](evidence/receipts/group126-mount-project.json)；[HOST_C PASS](boundary-sweep.json) |
| 126 | mount | labels | 1 | 149.756 | STALE_LABEL_CONTRACT | [evidence/receipts/group126-mount-labels.json](evidence/receipts/group126-mount-labels.json)；[M32R_MODEL PASS_M32R](evidence/labels-current-mount.json) |
| 126 | mount | half | 0 | 154.386 | PASS | [evidence/receipts/group126-mount-half.json](evidence/receipts/group126-mount-half.json) |
| 126 | mount | other-users | 0 | 501.671 | PASS | [evidence/receipts/group126-mount-other-users.json](evidence/receipts/group126-mount-other-users.json) |

补充队列共 16 项，退出 0 为 16 项，逐项回执在 `evidence/receipts/`。

矩阵目录的完整通信记录复核为 PASS，按精确 DAT/用户夹具分为 2 组，去重日志 114 份；X/V/W 及邻接字节检查见 `evidence/rpc-summary.json`。

## 8. 三张照片的上机步骤

原步骤在指定 DAT 上连照片 3 都不能执行，发布数据里没有用户条目。另两张只覆盖一次正向恢复和一个数值端点，漏了精确旋钮值、第二个端点及另外两种页面。先准备含条目的正式测试候选并复核新 SHA，随后仍可把照片控制在三张，其他观察用文字记录。当前版本有 P1，下面是修复后以 50mm 为首轮的验收安排。

| 照片 | 操作和不额外拍照的核对 | 照片应显示 |
| --- | --- | --- |
| 1. 恢复 | 明确使用普通模式、Standard、WB 补偿 9/9 和 Body 来源。先选 5 号、Cont=0，正常重启并在首次 ADJ 后确认仍为 0；再改 Cont=+1，确认后正常关机、开机、首次推 ADJ 拍照。这个值变化用来排除旧记录恰好相同的假通过。拍完进入 Cont 看是否恰为 +1，再退出重开菜单，确认没有重复恢复或丢值。首次 ADJ 前的效果不能用来判断已恢复。 | `>5*F-CC`，光标在 5。 |
| 2. 端点 | 选 1 号 GR Pos，进入 Satu，走到 +6 后再多按。拍完走到 −9 再多按，回逐项页和卡片，检查这些页面的对应格也没有端点 `!`。 | `Satu  +6`，多按不动。 |
| 3. 用户标题及忘记 | 选择一个 FCC 条目，拍卡片，再进入逐项页核对同一个条目名。随后正常关机、开机、首次推 ADJ，文字记录是否回到完整 04。 | 例如 `<FCC-001`，逐项页标题也必须相同。 |

这些照片不能观察锁 store、九行字节、连续堆或原厂事件失效，不能用来关闭本轮 P1。非基线输入和原厂事件需要对应的程序证据。

## 继承问题

| 编号 | 级别 | 位置及本轮结论 |
| --- | --- | --- |
| g137/P1-01 | P1，OPEN | 首次 8 行发布前仍有原厂 7 行窗口。本版在首发之前增加完整读取及恢复，不能声称缩小该窗口。未重跑真实调度。 |
| P2-03 | P2，OPEN | services 的最终归属核对后、原生预览前。当前准备点 0xD794、调用点 0xD798，IRQ restore 调用在 0xD790。旧 g137 RVA 不再适用。 |
| g124/P2-01 | P2，OPEN | ui_list 的末端重绘窗口，当前原生绘制调用点 0xC2CC。保持问题，不用本轮列表 C 检查代替时序复现。 |
| P2-04 | P2，OPEN | 普通预览 I/O 失败后的重开刷新。旧回归按其实际范围统计，没有单独关闭这个继承问题。 |
| g129/P2-01 | P2，OPEN | 三次残留后的连续堆反例仍成立，条件余量只改善 64 B。 |
| v38/P2-01 | P2，预算风险保留 | 主块余量从 0 增至 64 B；机身距 root 仍 176 B。 |
| UI/P2-01 | 已关闭 | 用户卡片底子名已改为条目名，逐项页也覆盖。 |
| g135/P2-01 | P2，OPEN | 正式树仍缺当前格式用户 CLI，复审桥接工具不等于产品树已经补齐。 |
| g135/P2-02 | P2，OPEN | 引擎树的 resident 副本仍不能代替 canonical resident_v38。包身份按 canonical 单独核对。 |
| g135/P2-03 | P2，测试适配问题保留 | 老布局和页面约定需要明确重绑，本轮保留原退出码及逐处读取记录。 |
| list/P2-01 | P2，OPEN | 非相邻物理事件的映射分支没有改变，仍不能把分组页的只重绑行为推广到所有页面。 |
| review/P2-01、02 | 旧工具问题已处理 | 回执与测试内容目录分开；旧带告警证据不沿用为本轮 PASS。复审准备错误和修正记录见 WRAPPER.md。 |

## 复跑命令及封存

在仓库根按顺序执行。不要同时启动另一组测试。

```sh
export TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/review-g138
/usr/bin/python3 -I -B research/review_g138/run_regressions.py --queue queue.json --slots 2
/usr/bin/python3 -I -B research/review_g138/run_regressions.py --queue repair-queue.json --slots 2
/usr/bin/python3 -I -B research/review_g138/run_regressions.py --queue supplemental-queue.json --slots 2
/usr/bin/python3 -I -B research/review_g138/run_regressions.py --queue audit-queue.json --slots 1
/usr/bin/python3 -I -B research/review_g138/make_tables.py --final
/usr/bin/sandbox-exec -f research/review_g138/offline.sb /usr/bin/python3 -I -B research/review_g138/seal.py
/usr/bin/python3 -I -B research/review_g138/make_report.py --final
/usr/bin/python3 -I -B research/review_g138/manifest.py --write
/usr/bin/python3 -I -B research/review_g138/manifest.py --check
```

上述运行器会跳过已有同名回执。需要重新执行全部 81 组时，先生成全新的 job 名称，保留早期证据；用户工具夹具继续使用已校验的同 DAT 版本。

```sh
/usr/bin/python3 -I -B research/review_g138/make_repeat_queue.py --label repeat01
/usr/bin/python3 -I -B research/review_g138/run_regressions.py --queue repeat-repeat01.json --slots 2
```

关键问题也可单独复跑。该队列复用已核对的脚本，不计入 81 组；运行器仍限制两槽并设置每项 10,800 秒超时。

```sh
/usr/bin/python3 -I -B research/review_g138/run_regressions.py --queue findings-queue.json --slots 2
```

`focused_review.py`、`partial_baseline_review.py`、`held_lock_review.py` 返回 OBSERVED 表示复现了所列行为，不表示候选通过。单项也应经 `offline.sb` 运行，且占用一个测试槽。

初始冻结输入 18016 项，变更 0 项。Scratch 清理结果：True。各项完整回执、输入比较和清理记录见 `evidence/seal.json`。未访问卡或相机；测试进程禁止联网，未作 Git 写操作。
