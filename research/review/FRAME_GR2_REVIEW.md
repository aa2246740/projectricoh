# FRAME-GR2 参考项目独立复核

复核日期：2026-10-12  
Reviewer：GPT-6.1 review

## 结论

发现 **1 个低严重度措辞问题**，没有中、高严重度问题。FRAME-GR2 的公开来源边界和 A12 50mm 三份当前文档本身准确；历史 reviewer 对“正常回滚”的一句话需要补足尚未执行真机验证的前提。

本次只复核公开来源快照和既有 A12 50mm 范围、RAW、风险边界。发布固件的二进制静态对比由单独报告承接，不在本结论内。

## Finding

### [低] 历史 reviewer 的“正常回滚”表述容易被读成已经实证

- **位置**：`research/review/A12_50_REVIEW.md:50`
- **现有文字**：“正常启动后重刷官方固件只证明正常回滚”。
- **证据**：`docs/A12_50_SCOPE.md:17,25,31` 明确本轮没有相机、刷写或恢复验证，并已改为“正常升级入口并不证明坏固件状态也能恢复；原厂回滚和独立救援都须验证”。`docs/A12_50_RAW_AND_RISK.md:38,42` 也说明实际恢复仍待真机验证，首次配合不刷实验固件。
- **影响**：脱离上下文阅读时，“只证明正常回滚”可能被理解为已经成功重刷过原厂固件。
- **具体修法**：改成“**若相机仍能正常启动，且真机实际成功重刷官方固件，这只能验证正常回滚；本轮尚未执行。它不能证明坏固件状态下可以救援。**”最终给用户的答复也应使用这组条件。

## 来源快照

**通过。** `audit_reference.py` 复跑结果与 `artifacts/frame-gr2/reference-audit.json` 逐字节一致。

- 仓库是 `Lyle-xub/FRAME-GR2`，默认分支为 `main`；保存的提交为 `3f819a5749e5ccb1781337098da646bf77fd2c2c`。
- 提交所指 Git tree 为 `17784099a8a2d62bab94966a245c80da8eb711a3`，`truncated` 为 false，公开树只有一个 blob：`README.md`。保存的 README Git blob 与该树一致。
- README 明确把相机对象写为 **RICOH GR II**，并在发布说明中写明公开仓库“未包含实现源码”。因此，当前公开 main 可以作为产品形态参考，不能提供实现代码或直接证明 GXR/A12 50mm 的可移植性。
- README 自述“16 个机内位置”和 JPEG/RAW 原图导出。这些是作者的产品说明；审计没有运行 App、固件或相机，也没有独立验证功能。
- “保留 JPEG 与 DNG 原始画质”出现在照片导出说明中，只能表示作者声称导出时不缩小、不重新压缩。它不能证明自定义 LUT 的拍摄路径不会改变 RAW，也不能替代 A12 50mm 的同拍 JPEG/DNG 真机验证。
- 发布固件 ZIP 的 GitHub asset digest 与作者 `SHA256SUMS.txt` 相符。这只能识别发布文件，不能证明适配 GXR、刷写安全或可恢复。

## A12 50mm 用户边界

**通过。** 三份当前文档给用户的范围一致：

- 首版只集中 A12 50mm，目标是 16 个可命名、可编辑、可保存的独立配方，通过菜单列表选择；按钮或 MY 拨盘只可作为入口，不能限制配方数量。
- 同一次拍摄必须保存带配方效果的 JPEG 和原厂 DNG。官方 Image Settings 只作用于 JPEG 的结论不等于尚未实现的 16 配方补丁已经兼容 RAW。
- 当前离线成果是 M32R 工具、分段反汇编以及 MYSET 的 1024 字节外壳、288 字节负载和完整性算法。实际颜色字段、真实 Card/DNG/JPEG、菜单、重启保留和可刷构建仍未验证。
- 机身 `ilaunch3` 和 A12 50mm 模块 `jlaunch3` 都可能因修改失效。列表菜单可能需要修改机身，所以不能把最坏风险限定为 50mm 模块。
- 独立救援入口和原厂回滚均未验证，不能承诺刷坏后可自行恢复，也不能承诺一次刷写成功完成 16 配方。

## 最终状态

**Remaining：1 个低严重度措辞修正。** 除历史 reviewer 的正常回滚句子外，本轮来源、RAW、离线能力和风险边界无其他 flags。真实发布固件行为、A12 50mm RAW/JPEG 和相机恢复仍未验证。

## 交付前增量复核

复核日期：2026-10-12  
Reviewer：GPT-6.1 review

**No flags。** 上一轮唯一低严重度 finding 已解决。`research/review/A12_50_REVIEW.md:50`、`docs/RESEARCH.md:69` 和 `docs/A12_50_ACCEPTANCE.md:31` 现在都明确：只有在相机仍能正常启动且真机实际成功重刷时，才算验证正常回滚；本轮没有执行回滚或救援。这不会被读成已经证明坏固件可恢复。

新增 FRAME-GR2 主报告和二进制报告的证据边界一致：

- `research/frame_gr2/binary/analysis.json` 与 `artifacts/frame-gr2/binary-verified.json` 逐字节一致。保存的发布 ZIP SHA-256 为 `af2e231d9ed9a7b604b1e7f63c6dcefd984951f80eb9595421fdc2bdeccc9bcd`，与作者清单及 GitHub 资产记录一致；ZIP 内 `rg2_v003.frm` 的重算 SHA-256 为 `6a978ce29143f53c1620e23581851ca1ed5fa7c6b8b3c00972dfb8ae0eb744ff`，也与 ZIP 内作者清单一致。
- FRAME WN3 和官方 GR II 3.00 都是双层 `UNITY FILE V1.10` 容器。`b01firm6` 的 7,896,704 字节完全相同；`b01firm8` 增加 432,556 字节且内容不同。报告只据此定位组件级差异，没有把共同的 `b01firm6`、共同容器或更新格式写成可救援证据。
- GR II 的 `b01firm8` 仍是高熵不透明负载。报告没有从偶然的 `RAW`、`DNG` 或 `WN3` 字节命中推断 ISA、函数、16 记录格式、LUT 路径或 RAW 行为，也没有把 GR II 的地址、更新按键或恢复预期迁移到 GXR。
- GXR `ilaunch3` 和 A12 50mm `jlaunch3` 各自的 16 段大端加载表与既有 M32R 证据被单独陈述。二进制报告没有声称这能解开 GR II 负载，也没有声称 FRAME 发布物可直接用于 GXR。
- FRAME-GR2 的 16 个机内位置、命名、独立保存和 JPEG/DNG 原图导出仍明确标为作者声明，且未在 GR II 实机复现。导出原图不能证明 LUT 不影响拍摄 RAW，更不能证明 GXR 的同拍 JPEG+DNG 已兼容。
- `research/frame_gr2/REPORT.md` 和 `research/frame_gr2/binary/REPORT.md` 中引用的本地报告、证据 JSON、保存来源和 A12 50mm 文档路径均存在。

最终用户口径准确：首版只做 A12 50mm，目标为 16 个独立命名的列表配方；同次保留配方 JPEG 与原厂 DNG；当前只有 MYSET 外壳等离线研究，没有可刷固件。机身与 A12 50mm 模块都可能因修改失效，独立救援和正常回滚都未验证，也不能承诺一次刷写成功。

**Remaining：No flags。** 所有相机行为、真实 RAW/JPEG、16 配方菜单、刷写和恢复仍未测试。
