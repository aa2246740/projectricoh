# GPT-6.1 review 独立复核

复核日期：2026-10-12  
Reviewer：GPT-6.1 review

## 结论

首轮研究的主结论可交付，没有高严重程度问题。报告清楚区分了原厂能力、静态候选、待验证项和真机验收，也明确说明本轮没有实现或刷写新增配方固件。

需要修正 2 个中等问题和 4 个低等问题。中等问题都位于可重跑证据或下一轮真机计划，不会把当前静态研究误写成已经实现。

## Findings

### 1. 中等：第二款 A12 的创建与保存实验没有独立执行

位置：`docs/CAPTURE_PLAN.md:9-14,40-42`；对照 `research/firmware/REPORT.md:146-159`。

证据：计划的步骤 2 至 5 只在第一款模块上创建 A/B、保存 Box/Card、重启和调用。步骤 6 换到第二款 A12 后只“重复 Card 调用实验”。这能测试同一张卡跨模块调用，不能证明第二款模块自己创建的 Box/Card 是否独立保存 13 个字段，也不能证明第二款模块的保存布局和第一款相同。固件报告另有更严格的说法，要求 A12 28mm 与 A12 50mm 各用一张备用卡并执行相同步骤，两份交付现在不一致。

具体修法：把实验拆成两段。先在 A12 28mm 和 A12 50mm 上分别用独立格式化卡完整执行 A/B 创建、Box 1/2、Card 1/2、重启、13 字段核对和 JPEG 对照。完成后再用同一张卡做 A12 28mm 到 A12 50mm、A12 50mm 到 A12 28mm 的双向跨模块实验。分别记录“本模块创建”和“跨模块调用”。

### 2. 中等：checksum 的主清单和 append-only 决策记录仍停在旧的 phase 0 判断

位置：`scripts/inspect_gxr.py:45-64,98-104`；`artifacts/firmware-inventory.json` 的 `weighted_rule_matches_header`；`decisions.tsv:5`；`README.md:15-18`。

证据：`inspect_gxr.py` 只计算 phase 0，因此固化清单把 7 个 `*0` 文件和 `l06firm5` 标成 `weighted_rule_matches_header: false`。`decisions.tsv:5` 仍说算法已知范围只限 `ilaunch3`。后续 `scan_gxr_firmware.py` 已证明 29 个文件各有唯一匹配相位：7 个 `*0` 是 phase 2，`l06firm5` 是 phase 4，其余 21 个是 phase 0。主报告写对了，但 README 的第一条重跑命令仍会重新生成旧口径清单。

本 reviewer 重跑到 `/tmp`，结果与仓库证据逐字节一致：`scan.json` 和 `mysettings-trace.json` 均 `cmp=0`；29 个文件的相位分布为 phase 0/2/4，数量分别为 21/7/1。

具体修法：让 `inspect_gxr.py` 也输出 `weighted_checksum_matching_phases`，或复用 `scan_gxr_firmware.py` 的实现，随后重建 `artifacts/firmware-inventory.json`。由于 `decisions.tsv` 是 append-only，不改第 5 行；新增一行 correction，记录 phase 0/2/4 的最终范围、脚本和 `scan.json`。

### 3. 低等：真机计划把 Card 改名当成已确认能力

位置：`docs/CAPTURE_PLAN.md:10-11`；对照 `research/recipes/REPORT.md:120-130`。

证据：计划要求把 Box 1/Card 1 命名为 `COLOR-A`，把 Box 2/Card 2 命名为 `COLOR-B`。官方机身手册明确说明 MY1/2/3 与 Box 可命名，但它早于 Card 功能。配方报告已把 Card 名称沿用列为“有依据的推断”，并把 Card 能否单独改名列为未知项。

具体修法：把命名步骤限定到 Box。Card 仅在菜单确实提供改名时命名，否则记录 Card 槽号、界面原样文本和照片。Card 改名能力应作为观察结果，不应成为实验前提。

### 4. 低等：官方 1.50 页面内部对 A12 50mm 的 Card 支持存在冲突，报告没有注明

位置：`docs/RESEARCH.md:16`；`research/recipes/REPORT.md:64-68,111-118`。

证据：本地官方 `feature-table.html:533-541` 把 A12 28mm、A12 50mm、S10、P10 都列为 v1.50；`product-firmware.html:306-311` 也明确把 A12 50mm 包含在新增 SD Card My Settings 的四款模块中。可是 `firmware-index.html:568-577` 的 v1.50 矩阵在 A12 50mm 列显示 `--`。现有“1.50 起支持”的判断有两份直接官方材料支撑，结论合理，但第三份官方矩阵冲突应留痕。

具体修法：在配方报告的“固件 1.51”或“已确认、推断和未知”中增加一条官方页面冲突说明。保留 1.50 结论，并把真机 Firmware Version 与 Card 菜单检查设为开始条件。

### 5. 低等：决策日志的 REA 依赖措辞和合成测试证据不够精确

位置：`decisions.tsv:6,8`；`artifacts/rea/install-manifest.json:10-14`；`scripts/prepare_rea.py`。

证据：第 6 行写“仅保留非浏览器依赖”，实际动作是从 35 个 production dependencies 中只删除 `playwright-core@1.58.2`，其余 34 个保留。第 8 行写比较逻辑已用合成数据验证，但没有记录合成输入、命令或结果摘要。本 reviewer 用 9 字节和 10 字节样本重跑，工具正确报告 2 个变化字节、2 个 span，包含替换和尾部增长。

具体修法：append-only 追加一行 tooling clarification，明确“只排除 playwright-core，其余 34 个依赖保留”；再追加或附一份可重跑的最小合成命令与预期 `changed_byte_count=2, span_count=2`。不要改旧行。

### 6. 低等：固件报告的 PDF 物理页码整体提前一页

位置：`research/firmware/REPORT.md:21-24`。

证据：用 Poppler 按 PDF 页号提取本地 `GXR_E.pdf`：印刷页 71 至 72 对应 PDF 物理页 83 至 84；印刷页 129 至 132 对应物理页 141 至 144；印刷页 150 对应物理页 162。报告分别写成 82 至 83、140 至 143、161。印刷页编号本身正确。

具体修法：把三处物理页改为 83 至 84、141 至 144、162，保留印刷页编号。

## 已复核为成立的边界

- Setting 1/2 各有 13 个字段。官方 FAQ 明列 3 个全局字段，加 5 组颜色各自的 Hue 与 Vividness。
- Box 1 至 6 与 Card 1 至 6 保存完整拍摄设置。现有官方资料没有证明它们是 12 套独立颜色参数组。
- 用户原话“A12 两个都有”被明确标成暂按 A12 28mm 与 A12 50mm 研究，未冒充明确型号。
- `SETH`/`OR3` 扫描结果被限定为地址构造候选。报告明确说明没有控制流、寄存器存活和运行可达性证明。
- 官方 ZIP 的 SHA-256 为 `3705984b8433c40d2ed4fd2600c11f03ed8a6de7dbe7f66efd38ee5ca15fc898`。29 个文件只与固定社区仓库哈希表一致，没有被写成 Ricoh 数字签名。
- REA npm 6.4.0 的 registry `gitHead` 是 `a56f7bb668ab23fec8d33f7af353ac7ed2fe1895`，current main 是 `ee50ed121e38cc6e1a2ff0dc8b789f15f71c5402`。发布包没有 `raw-binary`，current main 有该代码；两者没有混用。
- REA 项目依赖树排除了 `playwright-core`。版本、provider 清单和 ZIP inventory 成功；裸 M32R、native admission 与 firmware-region 探测分别受格式、provider/ISA 和 Linux/Binwalk 限制。
- 正常开机后的官方重刷只被认定为回滚流程。报告没有把它写成主程序损坏后的砖机救援。
- README、三份报告和汇总报告的相对链接全部存在。三份分析脚本复跑结果与固化 JSON 一致。
- 本轮交付是研究、工具和真机实验设计。没有新增配方固件、相机操作或刷写结果。

## 最终复核状态

复核日期：2026-10-12  
Reviewer：GPT-6.1 review

前述 6 条 finding 保留为审计记录。当前状态如下：

1. **Resolved。** `docs/CAPTURE_PLAN.md:9-14,40-42` 现要求 A12 28mm 与 A12 50mm 各自使用独立研究卡，分别完成 A/B 创建、Box/Card 保存、重启、13 字段核对和 JPEG 对照。双向跨模块调用已拆成独立实验。
2. **Resolved。** `scripts/inspect_gxr.py:48-72` 现检查全部 6 个相位，并拒绝没有匹配相位的文件。主清单与验证副本完全一致，29 个文件的 phase 0/2/4 数量为 21/7/1。`decisions.tsv:10` 已按 append-only 规则追加 correction。
3. **Resolved。** `docs/CAPTURE_PLAN.md:10-11` 只要求 Box 命名。Card 仅在实际菜单允许时命名，否则记录槽号和界面原样文本。
4. **Resolved。** `research/recipes/REPORT.md:66-68` 已记录 A12 50mm 的官方 1.50 页面矩阵冲突，并要求真机实验开始前同时核对固件版本和 Card 菜单。
5. **Resolved。** `decisions.tsv:11-13` 已澄清只排除 `playwright-core`、保留其余 34 个 production dependencies，并记录修正后的复跑。`scripts/verify_research.py:65-75` 固定使用 `abcdefghi` 与 `abcXefghiZ`，验证结果为 2 个变化字节和 2 个 span。
6. **Resolved。** `research/firmware/REPORT.md:21-24` 的 PDF 物理页已改为 83 至 84、141 至 144、162。

抽查证据：

- `artifacts/firmware-inventory.json` 与 `artifacts/verification/firmware-inventory.json` 完全一致。
- `research/firmware/scan.json` 与验证副本完全一致；`research/firmware/mysettings-trace.json` 与验证副本完全一致。
- `artifacts/verification/report.json` 的状态为 `passed`。限制项明确写明未操作相机、未执行固件、没有 IFO 捕获或颜色字段结构，静态地址候选也不证明运行可达。
- `artifacts/verification/upstream-language-tests.stderr` 记录 7 项测试全部通过。

**Remaining：No flags。** 当前交付可以作为首轮研究、可重跑工具和真机实验设计提交。它仍未实现或刷写新增配方固件，也没有真机验证。

## 实验数据保留条款复核

复核日期：2026-10-12  
Reviewer：GPT-6.1 review

**Resolved。** `docs/CAPTURE_PLAN.md:9-18,44-46` 的新增条款与实验结果标记一致：

- 实验前记录 Setting 1、Setting 2 的全部 13 个字段，以及白平衡、曝光和按钮设置，实验后按记录恢复。
- Box 只使用明确未占用的槽。没有两个空 Box 时先执行 Card 实验，并把 Box 结果标为“未执行”，不能根据 Card 结果声称 Box 通过。
- MY 拨盘位置已占用时，先用原厂菜单把原 MY1 保存到研究卡 Card 6，并记录原 Box 关联。实验后恢复原 MY1、Box 关联和原始颜色值，Card 6 保留为实验前备份。
- `docs/RESEARCH.md:44` 和 `decisions.tsv:14` 使用相同边界，仍明确真机实验尚未执行。

**Remaining：No flags。** 新增条款保护现有用户配方和拨盘关联，也没有扩大本轮“研究与实验设计”的完成声明。

