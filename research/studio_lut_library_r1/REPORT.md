可以复审

本轮 P1-01 和四项 P2 均已修复，完整检查 941 项通过、零重跑，详见末尾「复审修复」。以下至该节之前保留 R1 初版记录，其中 912 项测试、界面验收和源码冻结均对应修复前版本。

LUT 库 MVP 已接入现有「配方」页和照片编辑流程。导入、分组、改名、标星、删除、空间改选、照片套用、成片导出，以及单个和分组 `.cube` 导出均有测试。来源、作者和许可从文件头读取，支持补填并随导出保留。

工作室仍为 `main`，HEAD `f7bdc393f78940da612db916cfd11b95b44ff4b1`。本轮改动 36 个文件，全部未提交，暂存区为空。完整检查、最终界面检查和当前源码的 SHA-256 清单一致。

| 核对项目 | 结果与证据 |
| --- | --- |
| 完整 `make check` | 退出 0；912 passed，3 warnings；全程 747.903 秒。[日志](make_check_final.log)、[源码收据](make_check_final.result.json) |
| 零重跑 | 实际 `force_reruns=0`、`rerun_max=0`；912 项收集、912 项通过。[pytest 收据](make_check_final_pytest_28423.json) |
| 覆盖率 | 92.47581202487906%（10705 / 11576 行），高于基线 92.16900382444%（10122 / 10982 行）。[比较](coverage_comparison.json)、[完整数据](coverage.json) |
| 基线可比性 | 上轮 HDR 收据中的 248 个源码文件与当前 HEAD 全部同 SHA。[核对结果](baseline_verification.json) |
| 私有字节检查 | 完整检查内运行 `scripts/private_bytes.py --tracked --dist`，262 个文件通过。 |
| 其他质量检查 | Ruff、格式、mypy、保密信息检查、Bandit、功能开关、OpenAPI、导入契约、deptry、vulture、重复代码检查均通过，见完整日志。 |
| 实际界面 | 固定 Playwright 1.61.1 / Chromium 1228；10 个状态，包含桌面与窄窗口。无脚本异常或页面横向溢出。请求由本机 ASGI TestClient 处理。[界面收据](focus_after_ui_check.json) |
| 删除确认 | LUT、分组、我的配方均默认聚焦「取消」；默认回车取消，聚焦「删除」后回车也不执行。明确点击或空格才确认。通用组件另测「替换」按钮。[组件测试](../../studio/tests/test_confirmation.py)、[界面截图](focus_after_ui_delete_confirmation.png) |
| 最终源码对应关系 | 界面验收与完整检查使用同一份源码，检查期间没有改动；Git diff 格式检查通过。[汇总收据](final_evidence.json) |

`coverage.json` 保留全部逐行命中、缺失行及统计，省去函数级名称明细；原始覆盖率数据库为 `make_check_final.coverage`。[逐行导出收据](coverage_line_export.json)

导入支持多选文件、文件夹选择及拖放文件夹，默认以所选文件夹名分组。目录分批读取到结束，跳过 `__MACOSX/` 和 `._*`；不支持的格式和坏文件逐项显示结果。原始字节按 SHA-256 存储和去重，文件名及 TITLE 作为数据处理。界面用文本节点，导出清理 TITLE，避免多出 cube 指令。

空间识别覆盖设计组合表的 known、guessed、unknown、conflict；强 S 曲线、反相、偏色和不单调灰轴允许返回未知。用户可从全部 12 个空间中改选，设计中的 13 种为笔误。改选会停止旧拟合、使旧拟合结果不可保存，并更新磁盘和浏览器图片缓存键。改名、标星不触发颜色重算。

照片使用库里记录的输入空间，预览和成片共用渲染阶段。显示类 LUT 可用于现有底图；Log 类必须有 A12 50mm RAW 和合格色彩矩阵，全尺寸导出使用 RAW 条带。测试包含套用后的实际图像导出、全尺寸 RAW 路径，以及缺少 RAW、矩阵或不支持单元的拒绝情况。

`.cube` 导出位于应用数据 `luts/exports/`。按本次要求清理 TITLE，因此导出 SHA 可以与原文件不同；1D、3D、shaper、输入域和范围的数值，以及多行来源、作者、许可字段均通过往返测试。还用不对称通道向量核对格点和通道顺序。其他头部注释也保留。库删除会给派生的我的配方保留署名并标记 `source.lut_deleted=true`，不会删掉配方。

库、作业、配方、导出和相关缓存写入均接入实际位置核对与 `PrivateDir`；持久化使用 `durable_write`。测试覆盖目录链接变更、已有缓存目录链接、删除中断恢复和存储失败。测试 LUT 均为现场合成，未加入任何用户或第三方 LUT 文件。工作只在本机运行，没有访问真实存储卡、指定服务或用户图库，没有 Git 写操作。

保留了早期失败证据。首轮完整检查为 905 passed / 1 failed，原冒烟测试的编辑范围断言少了 LUT，更新断言后重新运行了完整检查，未启用 pytest 重跑。`cache_before.json` 记录空间改选后仍显示旧缓存，`cache_after.json` 证明 URL、文件 SHA 和图像颜色已更新。`focus_before` 记录旧确认框默认聚焦删除，`focus_after` 记录三个删除流程修正。早期界面脚本的定位和等待条件错误也保留日志，不作为最终通过依据。

本轮范围和未测层次如下：

- 「全部调节」「机内 LUT」两档新预测留到下一版。现有配方预测沿用原流程，没有新增这两档分数。
- 不含相机写入、写卡、3dl/Hald 转换、配方烘焙 cube 或分享码。导出的是库内 LUT，没有实现设计全文的所有导出类型。
- 本轮在 macOS 主机核对；本轮新增产品代码和确认测试不依赖 macOS 专用能力，宿主判断沿用 `os.uname()`，没有在 Linux 主机或实机相机上验收。
- 新组件的版面检查无失败项；保留桌面紧凑控件小于 44px 的提示。本轮没有对整个旧界面作无障碍验收。

指定临时目录 `/Volumes/Workspace/Scratch/tmp/projectricoh/studio-lut` 已删除；清理前核对了 APFS 卷 UUID，未清理其他目录。[清理收据](cleanup.json)

复审入口：[改动说明](CHANGES.md)、[逐文件清单](FILE_LIST.tsv)、[全部新增及复用文案](COPY.md)、[进展记录](PROGRESS.md)、[SHA-256 清单](SHA256SUMS)。清单覆盖全部改动的工作室文件和本报告目录中的交付文件，不含清单自身。

在 projectricoh 项目根目录核对：

```sh
shasum -a 256 -c research/studio_lut_library_r1/SHA256SUMS
```

## 复审修复

本轮以 `research/review_studio_lut/REVIEW.md` 为依据，修复 P1-01 及四项 P2。开始前 259 个工作室文件与被审 R1 完全一致；复审清单为 567 项，复审目录保持只读。[输入收据](fix_input.json)

P1-01 采用用户给出的方案 1。LUT 内容和署名未改时，直接导出原文件字节；TITLE 需要清理时只替换该行，同行注释仍保留。选择这个方案是为了完整保留合法注释位置、空白、换行、BOM 和数值写法，避免重新序列化时遗漏内容。

读取署名改为检查整个文件，包括数据行间、末尾和行内注释。署名经用户修改时，保留全部原注释，在文件头增加当前字段，再以末尾 JSON 注释记录多行字段的精确值；原作者及许可注释不会因为修改字段而被移除。库中旧记录会补齐此前漏读且用户未改过的署名，保留用户已改过的值；只升级署名记录，不改变颜色版本。

| 编号 | 本轮修改 |
| --- | --- |
| P2-01 | 后端错误提示统一使用「名称」，同步更新 COPY.md；相机配方文件目录项的同类提示一并改正。 |
| P2-02 | LUT 名称和分组名称分别提示 1–255 个字符，配方名称提示 1–40 个字符；无效控制字符另报名称无效。 |
| P2-03 | `PrivateDir.replace_file()` 的临时文件创建和写入移入清理用的 `try`。真实短写后失败、文件同步失败均验证旧索引和 LUT 字节不变、临时文件无残留，恢复后可继续修改。 |
| P2-04 | 空间共 12 种，设计中的 13 种为笔误。未增加空间，也未修改锁定的 `spaces.py`。 |

新增 29 项回归。先在未修复代码上运行，29 项失败；修复后 29 项通过，随后连同原 LUT 库及 A1a R3 共 175 项通过。三份署名样本与复审文件的 SHA 完全一致，实际 API 检查覆盖头部、数据行间、末尾的导入、单个导出和分组导出，未改动时文件字节及 SHA 一致。还核对了无末尾换行、CRLF、BOM、重复注释、TITLE 同行注释、署名编辑、旧库恢复以及各入口名称限制。

修复前证据：[失败日志](fix_red.log)。修复后证据：[29 项回归](fix_green.log)、[175 项定向回归](fix_regression.log)。测试隔离修正后的最终检查为 [178 项定向回归](fix_regression_final.log) 和 [静态检查](fix_static_final.log)。

第一次全量检查提前返回 0，却没有 pytest 完成收据和覆盖率文件，不计为通过。旧单元测试在当前进程调用 `worker.run()` 后留下 4 个父进程监测线程；后续测试短暂模拟父进程离开，会让这些线程结束 pytest。新增收尾断言稳定列出这 4 个残留线程，见 [失败记录](fix_watch_red.log)。现已在单元测试中隔离进程监测和信号安装，原有文件结果断言保留，真实监测仍单独运行并等待退出；真实子进程随父进程结束的测试也保留。[三项通过记录](fix_watch_green.log)

检查脚本现要求正常结束的 pytest 收据；单有返回 0 不算通过。使用返回 0、没有收据的独立负例，脚本正确判为未完成，见 [收据检查](fix_receipt_guard.result.json)。第一次不完整日志保存在 `fix_make_check.log`，最终全量使用 `fix_make_check_final` 标签。

| 最终验收 | 结果与证据 |
| --- | --- |
| 完整 `make check` | 正常结束，退出 0；941 passed，3 warnings；全程 732.08 秒。[完整日志](fix_make_check_final.log)、[运行收据](fix_make_check_final.result.json) |
| 零重跑 | 收集 941 项、通过 941 项；`force_reruns=0`、`rerun_max=0`，无失败或跳过。[pytest 完成收据](fix_make_check_final_pytest_64840.json) |
| 覆盖率 | 10791 / 11660 行，92.54716981132076%，高于被审 R1 的 92.47581202487906%。[比较](fix_coverage_comparison.json)、[逐行数据](fix_coverage.json) |
| 私有字节及其他检查 | `private_bytes.py --tracked --dist` 检查 263 个文件通过；其他 `make check` 前置项目均通过。 |
| 复审反例 | 三份原件与回归输入逐字节相同；头部、数据中间、末尾均经实际 API 单个及分组导出，未改动时保留原 SHA。[反例映射](fix_counterexamples.json) |
| 源码与工作区 | 当前 260 个文件与完整检查收据一致。相对被审 R1，本轮修复涉及 9 个文件；合计未提交改动 39 个文件。main、HEAD 和空暂存区保持不变。[汇总](fix_final_evidence.json)、[本轮清单](FIX_FILE_LIST.tsv) |
| 复审目录 | 39 项证据与原清单一致，清单自身未改动；没有写入复审目录。 |

逐行覆盖率导出省去函数级名称明细，命中行、缺失行和统计不变；原始数据库保存在 `fix_make_check_final.coverage`，见 [导出收据](fix_coverage_line_export.json)。为遵守文案要求，收集日志的两个既有用例名称在展示文件中省略，序号及收集总数保留；实际测试结果日志未修改，见 [展示收据](fix_collect_presentation.json)。

本轮未重新运行浏览器界面检查。网页源码与 R1 一致，名称文案通过实际 API 核对，既有确认框测试包含在完整检查中。本轮仍为 macOS 主机验收，没有运行 Linux 主机或实机相机检查；没有 Git 写操作，也没有访问真实存储卡、指定服务或用户图库。

指定临时目录已全部删除，清理前再次核对 APFS 卷 UUID，见 [本轮清理收据](fix_cleanup.json)。当前交付用 `SHA256SUMS`；`r1_before_fix.SHA256SUMS` 仅保留修复前的 303 项哈希记录。新增文案已更新到 `COPY.md`，本轮改动见 `CHANGES.md` 和 `FIX_FILE_LIST.tsv`。
