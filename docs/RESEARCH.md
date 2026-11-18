# GXR 独立色彩配方库的首轮研究

研究日期：2026-10-12。用户拥有两款 A12，本文记录首轮 A12 28mm 与 A12 50mm Macro 研究。当前首版已集中 A12 50mm，要求16个列表配方并保留 JPEG 与 DNG，见 [当前范围](A12_50_SCOPE.md)与 [RAW和风险核验](A12_50_RAW_AND_RISK.md)。当前机身及模块固件版本尚未取得。

## 结论

GXR 有继续扩展色彩配方的研究基础。本轮已经定位机身的 SD My Settings 文件操作候选代码，并验证官方固件的格式与校验。建议把最终功能做成“选一个有名字的配方，只恢复颜色参数”，先复用原厂颜色处理和 SD 文件接口。

目前没有新增配方固件，也没有真机验证。下一步最有价值的证据是两个 My Settings 记录能否分别恢复不同的 Setting 1 内部参数。这决定能否复用现有记录，以及还需追踪哪一段机身和模块代码。

老相机有可修改的软件，并不直接证明存在未使用的硬件能力。增加保存数量主要涉及菜单、记录格式和参数加载。任意 LUT、新的胶片算法、动态范围或视频能力是另外的研究目标，本轮没有它们的可行性证据。

## 原厂已有的能力

- Image Settings 仍有两个自定义彩色样式，Setting 1 和 Setting 2。各有全局鲜艳度、对比度、锐度，以及橙、绿、蓝、红、洋红五组颜色各自的色相和鲜艳度。依据见 [Ricoh 官方 FAQ](https://www.ricoh-imaging.co.jp/english/r_dc/support/faq/bp/gxr/05/gxr05012.html)。另一篇官方 FAQ 对档位数的描述有冲突，实际参数编码和范围仍要核对。
- My Settings 有机身 Box 1 至 6，拨盘调用位为 MY1、MY2、MY3。A12 28mm 与 50mm 从固件 1.50 起还支持 SD 卡 Card 1 至 6，1.51 沿用。依据见 [Ricoh 版本功能表](https://www.ricoh-imaging.co.jp/english/r_dc/download/firmware/gxr/bymodes.html)和[官方 1.50 补充手册](https://www.ricoh-imaging.co.jp/english/r_dc/download/firmware/docs/gxr_vup_en.pdf)。
- My Settings 保存整套拍摄状态，包含 Image Settings、白平衡、ISO、拍摄模式与曝光项目。白平衡补偿须打开 My Settings WB Comp. 才随记录保存。依据见[机身手册](https://www.ricoh-imaging.co.jp/english/r_dc/support/manual/pdf/gxr/GXR_E.pdf)，印刷页 129 至 133。

这些资料没有逐字段说明每个记录是否复制 Setting 1/2 的内部颜色数组。因此不能把 Box 与 Card 的 12 个库位宣传为已经证实的 12 套独立色彩参数。完整官方能力和模块差异见 [research/recipes/REPORT.md](../research/recipes/REPORT.md)。

官方功能表和固件功能介绍都支持 A12 50mm 从 1.50 起保存到 Card；固件下载页的旧 1.50 矩阵却标为 `--`。本报告采用前两份直接说明，保留这处冲突。实验开始前仍须实际检查版本与 Card 菜单。

## 本轮实际分析的结果

官方 1.51 ZIP 下载自 Ricoh，SHA-256 为 `3705984b8433c40d2ed4fd2600c11f03ed8a6de7dbe7f66efd38ee5ca15fc898`。29 个升级文件全部与固定版本中文补丁仓库的哈希表一致。这个哈希表是社区基准，不能代替 Ricoh 的数字签名。

主程序使用 M32R 指令编码的证据与上游研究相符，具体芯片型号尚未确认。机身主程序 `ilaunch3` 有 16 个初始化段，文件偏移必须按段记录映射到运行地址。A12 50mm 的型号串位于 `jlaunch3`，A12 28mm 的型号串位于 `qlaunch3`。

本轮对 29 个文件重跑校验。`*0` 文件的加权校验相位为 2，`l06firm5` 为 4，其余 21 个文件为 0，全部匹配。早期把 ilaunch3 的相位 0 套在所有文件上出现差异，已在分析记录中解释。语言补丁的样本测试与校验只证明该补丁的桌面行为。

机身 `ilaunch3` 中已找到 My Settings 的静态入口线索：

- 路径和标签在文件偏移 `0xF6870` 至 `0xF69AD`，对应运行地址 `0x20141670` 至 `0x201417AD`。包含 `/ATA1/MYSET`、`.IFO` 和 My Settings Card 标签。
- 地址构造候选集中在文件偏移 `0xD29BC` 至 `0xD5B08`，对应运行地址 `0x2011D7BC` 至 `0x20120908`。有读取、写入、删除和创建接口地址的候选引用。
- 读取接口候选为 `0x200A449C`，写入为 `0x200A45E8`。功能名称依据上游 PARAM.DAT 调用链交叉判断，本轮尚未恢复 My Settings 全部控制流和结构。
- 两款 A12 主程序中没有 MYSET 字符串，有各自的调整数据和 PARAM 路径。这支持优先追踪机身 SD 文件管理，但不能证明完整颜色状态只在机身。

`.IFO` 是静态代码中的候选记录后缀。实际 SD 文件名、字段布局、校验、槽位编码和模块绑定规则需要原厂导出样本确认。完整偏移、地址、脚本和限定条件见 [research/firmware/REPORT.md](../research/firmware/REPORT.md)。

当前没有已证明安全的代码空洞。15 个段间 FF 填充区不属于初始化段；段内长零区和 FF 区也未证明用途、运行引用或权限。中文补丁采用等长替换，不能作为新增代码放置方案的证明。

## 推荐的实现次序

第一步是原厂 A/B 交叉实验。两条记录都选择 Setting 1，但保存不同颜色值。重启后分别调用，核对参数与 JPEG，再采集 SD 文件做单变量差分。实验只用研究卡和未使用槽，保留原有配方；拨盘位置已使用时先通过原厂菜单备份。实验步骤见 [CAPTURE_PLAN.md](CAPTURE_PLAN.md)。

如果两个记录恢复各自的颜色值，就先解析现有记录。电脑端配方库可以用已核验的原厂记录做备份和整理，机内超过六组的调用还要扩展枚举和菜单。完整拍摄记录会切换曝光，最终独立色彩库需要只提取经过确认的颜色字段。

如果两个记录始终使用最后一次修改的 Setting 1，就继续追踪全局颜色数组和机身到模块的设置传输。新增配方加载时须显式恢复这些数组。仅改槽编号不能增加独立配方。

取得数据结构后，建议首版只保存原厂已有颜色参数和可选白平衡参数，沿用原厂 JPEG 处理。选配方时保持曝光、对焦和按钮配置。首版同时提供名称、保存、覆盖、删除和卡文件损坏时的回退。这里描述的是目标行为，尚未实现或证明可容纳。

直接把 Setting 1/2 的全局数组扩大涉及菜单枚举、数组长度、默认值、序列化、机身与模块通信和 JPEG 应用，当前证据不足以选择补丁位置。独立配方库的代码和内存预算也要先验证。

## REA 已安装，适用范围已实测

本项目使用 npm 发布的 `rea-agents@6.4.0`，发布 commit 为 `a56f7bb668ab23fec8d33f7af353ac7ed2fe1895`。当前 GitHub main 虽然也标 6.4.0，但包含尚未进入该发布包的功能，二者分别锁定。

REA 位于 `tools/rea/`。为遵守用户的浏览器固定版本要求，本项目从独立依赖清单排除 Playwright 1.58.2；没有修改发布包的 package.json，也没有执行全局 setup。它是静态分析 CLI 安装，浏览器和可选原生功能不在本轮验证范围。

实际测试结果如下：版本和 provider 清单正常，官方 ZIP 清单正常；直接检查 ilaunch3 报 `unsupported binary format`；raw-binary 参数报只接受 dos-com；固件区域检查要求 Linux 和调用者提供的 Binwalk。REA 可做通用文件取证，当前不能承担 GXR 的 M32R 反编译。

安装证据见 [artifacts/rea/install-manifest.json](../artifacts/rea/install-manifest.json)，实际命令输出见 [artifacts/rea/probes.json](../artifacts/rea/probes.json)。工具边界、固定版本依据和恢复路径分析见 [research/tooling/REPORT.md](../research/tooling/REPORT.md)。没有为这个样本额外安装 Ghidra 或更换全局浏览器。

## 进入固件实现前还缺的证据

- 机身与两款 A12 的实际版本，以及原厂 A/B 交叉实验。
- 原厂 Card 导出文件的稳定差分，内部颜色数组及范围的定义。
- 完整保存与加载函数、菜单边界、模块参数应用路径、代码和 RAM 预算。
- 主程序损坏时可用的独立恢复机制。即使未来在正常启动条件下成功重刷官方固件，也只能验证正常回滚；本轮尚未执行回滚或救援。

首次新增固件的验收须在两款 A12 上分别完成：配方选择、编辑、命名、保存、重启保留、覆盖、删除、卡缺失或损坏、换模块、实际 JPEG 效果。构建成功、校验正确或菜单可见都不能替代这些结果。

## 本轮交付

- 研究协议、三个 GPT-6.1 worker 报告和决策记录 `decisions.tsv`。
- 官方固件清单、分段映射、My Settings 静态引用候选和实际 REA 输出。
- `scripts/inspect_gxr.py`、`research/firmware/scan_gxr_firmware.py`、`research/firmware/trace_mysettings.py`，均读取官方固件并输出证据。
- `scripts/diff_settings.py` 用于比较原厂导出的两个文件，已以合成样本验证差分逻辑，尚无真机样本。
- REA 安装准备脚本、项目 wrapper 和验证脚本。

官方固件和下载包保留在本地忽略目录，未公开发布。本轮没有操作相机、制作新增配方刷写包或运行固件。
