修改后再实现

P1-04 未关闭。R4 交付的 8,509 组负例、6 组完整合成正例及 20 组命令行检查均已复跑，结果与证据一致；但 JPEG_L、RAW_L、RAW_169 的成功计数没有与实际记录数核对。本轮 381 份独立负例中，30 份计数不一致的记录仍被判为齐全，三个代表输入在公共命令行入口也均退出 0。

本轮只复审 P1-04 和 R4 差量。未发现独立于该项的新 P0/P1；P1-01、P1-02、P1-03、P1-05 的既有设计层结论保持，不重做其原生重放、布局或像素检查。本结论不批准诊断程序、存储卡或相机阶段。

## 冻结输入与范围

仓库根为 `/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh`。开始先核验指定 APFS 卷身份，随后核对设计目录清单，90 项路径唯一、90 项摘要全部匹配。四个指定旧文件仅作摘要读取，没有查看文本内容或执行。上一轮报告、记录变体和清单另行冻结，见 [additional-inputs.json](additional-inputs.json)。

| 对象 | 本轮核对的 SHA-256 |
| --- | --- |
| `body_v4_design/SHA256SUMS` | `83ff713f77a68cde4743b6777e2467e9e72afe3f699ad0b431443c89789db009` |
| `body_v4_design/DESIGN.md` | `2a32cbb9b2142782538e2cec002c290c530cd20a3d22bfd3d6635816102380d7` |
| `body_v4_design/r3/diag_gate.py` | `6cef7602edea7a122856448773cb1cc4b487f23fa823eba68d05322bdb1abe7a` |
| `body_v4_design/r4/reference-profile.json` | `3af19c2f4cb57233b7a1bba14429001f23839cf70ad67dace91dbd805590fa4e` |
| `body_v4_design/r4/complete-records.json` | `2e301374e98873797c2188c18bc5ce9b8cc1f166fab1e3017877a9ea5c9c12e3` |
| `review_v4_design_r2/REVIEW.md` | `e7b249751ebfb0cec9d5f96c543eab2e5e78be143be8656f88620b6a13523372` |

输入核对见 [input-hashes-before.json](input-hashes-before.json) 和 [input-hashes-after.json](input-hashes-after.json)。所有检查前台串行，以 `nice -n 10` 执行；命令行检查脚本逐个启动并等候单个检查子进程，没有并行作业。测试使用 [offline.sb](offline.sb) 限制网络、卷读取和写入路径。未做 Git 写操作、联网、相机或存储卡访问，未开子代理。

## R4 声称的核实结果

| 声称 | 独立核实 |
| --- | --- |
| 旧六组的共同原因是只检查已有值自洽，未先验全。 | 方向成立。旧判定器对原六组和移到完整正例后的同六组均报齐全，共 12 次；当前判定器全部拒绝。见 [before-rerun.json](before-rerun.json)。 |
| 统一检查字段、独立参考、身份和连续性。 | 字段缺失、精确类型、参考摘要、嵌套上下文及多种序号检查已经落在实际入口；但成功计数的语义关联仍漏了三个场景，不能据此关闭整个 P1-04。 |
| 8,509 组负例全部拒绝。 | 复跑 `r4/record_check.py --check`，8,509/8,509 拒绝，逐例证据与已交付文件一致。包含原六组、旧 28 组及其完整正例上的 34 组对应修改。见 [r4-record-rerun.json](r4-record-rerun.json)。 |
| 6 组完整合成正例接受。 | 6/6 接受。覆盖分别绑定的三单元合成身份、tick 回卷、类别排列变化及拍摄交错，不是单元设备验收。 |
| 20 组命令行检查通过。 | 实际重新执行公共入口，2 组完整输入退出 0，18 组不完整或格式错误退出 2；结果与原文件逐项相同。只适配临时路径和结果写入位置，见 [cli-path-adapter.json](cli-path-adapter.json)、[r4-cli-rerun.json](r4-cli-rerun.json)。 |
| 上轮 P2 与实现要求已同步。 | §R4.4 已列入类别覆盖、字段来源、实际 BSS 预算、两个恢复目标、50mm 范围及原有实现合同。下文补充两处仍需明确的实现注意事项。 |

“原六组已修正”与“P1-04 全部关闭”是两件事。8,509 个已交付负例确实通过检查，但字段删除和错误类型不能覆盖所有合法类型内的计数矛盾。

## P1-04 仍未关闭：成功计数与单拍记录数不一致

静态位置为 `r3/diag_gate.py:58`、`:59`、`:119`、`:120`、`:271`、`:301`。公共 `valid` 只要求为正的 uint32；KEY、OSD、BURST、PLAY、BW 都另行核对期望计数，JPEG_L、RAW_L、RAW_169 没有对应核对。这三种场景的格式各只能保留一份 `image`。

从完整正例各独立修改一个字段，保留 `complete=true`、`lost=0`、`overwritten=0`、全部身份和原始记录：

| 最小修改 | 记录内容 | 公共入口实际结果 |
| --- | --- | --- |
| JPEG_L 的 `valid` 从 1 改为 2。 | 仍只有一份 JPEG_L IMG。 | 退出 0，`records_complete=true`。 |
| RAW_L 的 `valid` 从 1 改为 2。 | 仍只有一份 RAW_L IMG。 | 退出 0，`records_complete=true`。 |
| RAW_169 的 `valid` 从 1 改为 2。 | 仍只有一份 RAW_169 IMG。 | 退出 0，`records_complete=true`。 |

实际成功数声称有两次，但只保留一次证据，也没有报告漏失或覆盖，不能判为本场景记录齐全。即使错误发生在成功计数字段本身，矛盾也必须使本次采集不通过。将同样字段分别改为 2、3、4、5、8、20、95、96、97、4,294,967,295，三个场景共 30 份均被接受；其他场景的 80 份计数变体全部被拒，定位到三个未做语义核对的分支。

误判输出的 `record_stage` 为 `records_complete_for_offline_review`，`reasons` 为空，容量、坐标和 TIME 分项也没有回到 `undetermined`。这违反 `DESIGN.md:28`、`:36`、`:370`、`:372` 的完整性合同。ER 归属和最终 H42 时间仍未通过；本项证明的是主机采集门判断有误，没有证明实际相机或照片已经受损。

三个完整最小输入及结果保存在 [count-mismatch-examples.json](count-mismatch-examples.json)，真实命令行结果见 [independent-cli.json](independent-cli.json)。修改前后的输入差异只有各自的 `valid` 字段。

关闭条件：

1. 为全部 11 场景明确成功计数的单位，并核对计数、已保存原始记录数和相应序号。本格式下三种单拍场景各只能有一份成功 IMG；多次采集若要保留，必须扩展记录格式并逐份验全，不能仅接受任意正数。
2. 三个场景的计数与记录不一致时，总状态及容量、坐标、TIME 分项均按 R4 统一不完整规则处理。不要按本轮用例名称作特殊判断。
3. 复跑原 8,509 组、本轮计数变体及完整正例。既要拒绝矛盾记录，也要继续接受计数正确的完整输入。

## 本轮新增变体与完整正例

[replay_review.py](replay_review.py) 从被审完整正例独立构造输入，调用实际 `classify`。逐例记录包含输入摘要、可重建的修改路径和完整判定结果，见 [independent-records.json](independent-records.json)。381 份负例的输入摘要互不相同。

| 负例类型 | 输入数 | 被拒绝 | 误判齐全 |
| --- | ---: | ---: | ---: |
| 所有场景的成功计数不一致。 | 110 | 80 | 30 |
| 同时改变嵌套场景和配置身份。 | 177 | 177 | 0 |
| 拼接 OSD、IMG、逐张记录、BW 或 MEM。 | 42 | 42 | 0 |
| 配对两侧同时缺字段，或类别三份列表同时少项。 | 11 | 11 | 0 |
| 参考身份、参考摘要或记录种类不符。 | 7 | 7 | 0 |
| 主图地址、来源或区间无效。 | 12 | 12 | 0 |
| 完成标志为真但同时报告漏失或覆盖。 | 22 | 22 | 0 |
| 合计。 | 381 | 351 | 30 |

完整正例有 47 份不同输入，含重复控制共执行 49 次，全部接受。它们覆盖计数正确的基准、各类零槽但原生跨度有据、18 槽封顶、类别重排、320 像素的非坐标层、两侧层数组同步重排、不同有效 BW tick、MEM 实际读数变化、uint32 回卷和独立 K 的拍摄交错。两次整周 tick 平移与基准相同，按重复控制计算，没有当成额外不同输入。

另外复跑 14 个公共命令行用例：4 个完整输入退出 0，7 个负例退出 2，上述 3 个计数矛盾输入错误退出 0。所有这些检查均保持 ER 归属与最终 H42 时间的独立关口，没有将它们改成通过。

## P2 实现注意事项

1. 明确 OSD 层数组的顺序合同。`diag_gate.py:234` 按索引集合验全，但 `:266` 至 `:270` 又按列表位置比较受控配对。单独倒置四个 OSD 场景中任一层数组，字段、层索引、缓冲、坐标和时间都未丢失，却均得到 `controlled_buffer_mismatch`；按 `index` 排序后四份都接受。应按索引核对，或明确固定顺序并在解码处归一，避免完整测量因表示顺序被拒。该排序要求当前未写清，列为交换格式的 P2，未混入上述 381 份负例。见 [ordering-observations.json](ordering-observations.json)。
2. 同步 TIME 交错规则。§R4.2、`DESIGN.md:42` 与完整交错正例允许前一张未到 H40、后一张 H09 已到；`:438` 仍将这一情况列为作废条件。应以 R4 的唯一身份配对为准，改掉旧句，保留真正缺项、身份复用和单张内乱序的拒绝规则，避免实现时拒绝正常交错。
3. 继续执行 §R4.4 已列明的要求：11 个有效描述和 99 项物理覆盖分开记账，跨度/数量/地址矩阵与池末端按原生字段解释，新增元数据及紧凑记录重过 G0，恢复目标分别封存官方 1.51 与日用 v3.8。旧布局余量不能证明新诊断程序放得下。
4. 合成参考继续只解释合成记录。真实参考的原生映射、最终诊断文件、64 KiB 自有对照区、整回调与栈、完整 UI、H43 时机及真实相片仍须各自验收。50mm 的一次采集不能转换成其他单元的结论。

## 复现与证据边界

从仓库根执行，先建立本轮临时目录，再使用复审策略运行。下面两个新增检查当前都应退出 1，分别报告 30 个误判齐全输入和 3 个命令行误判；这是复审发现，不能解释为被审程序检查通过。

```sh
mkdir -p /Volumes/Workspace/Scratch/tmp/projectricoh/review-v4-r3
TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/review-v4-r3 nice -n 10 \
  /usr/bin/sandbox-exec -f research/review_v4_design_r3/offline.sb \
  /usr/bin/python3 -I -B research/review_v4_design_r3/replay_review.py independent
TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/review-v4-r3 nice -n 10 \
  /usr/bin/sandbox-exec -f research/review_v4_design_r3/offline.sb \
  /usr/bin/python3 -I -B research/review_v4_design_r3/replay_review.py extra-cli
```

`before` 重放旧判定器的六组输入及其完整基准变体，`original-cli` 复跑既有 20 个命令行用例，`ordering` 复跑层顺序边界及排序控制。`original-cli` 只替换临时路径和结果落点，不修改被审脚本。复审脚本首次读取旧结果时用错一个旧版不存在的字段，已修正并重跑；原始错误另存 [review-runner-initial-failure.json](review-runner-initial-failure.json)，不计为被审程序缺陷。

静态已证的是设计差量、当前类型合同和三个计数分支的缺项；主机已证的是本报告所列原型入口行为及输入摘要。诊断固件、目标紧凑格式、设备原生参考和相机行为没有在本轮执行。汇总见 [verification.json](verification.json)。

收尾再次核对输入清单及另冻输入，均未变；本轮启动的检查均已结束，临时目录已删除。清理回执见 [cleanup.json](cleanup.json)，本目录 [SHA256SUMS](SHA256SUMS) 的路径相对仓库根，不包含清单自身。复跑会更新本复审目录的证据，之后须重新生成清单并清理临时目录。
