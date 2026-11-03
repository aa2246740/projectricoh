# 交接说明（2026-10-23）

2026-11-04 公开同步记录见 [Git 同步检查](../research/git_sync/REPORT.md)。第二台 Mac 先读[照片统计所需文件与分工](../research/git_sync/PROBE_ANALYSIS.md)。下文是 10 月 23 日的历史交接，不代表本轮重新验收了机身或卡。

当前工作是修复配方切换残留，不再做峰值染色实验。先读 [本轮报告](../research/switch_residue/REPORT.md)、[R2 实现报告](../research/switch_residue/WORKER_R2.md)与首轮审查 `research/switch_residue/REVIEW_R1.md`。两项 R1 缺口已补齐，新候选 `efe6587190e8` 正等独立复审 R2；首轮 `ce4d9a537821` 已冻结，不准写卡。任务状态和后续命令保存在 `research/switch_residue/local/inflight.json`，不要重复派发活跃任务。

## 现在的真实状态

- 当前待审新包：`artifacts/stage2l-switch-packages/stage2l-switch-efe6587190e8/`，机身 SHA-256 `efe6587190e845b1c28364c02a6b8bde14e046e7c7411393a4c9892124b6bfd7`，8080 B payload SHA `5510f2be98906f3b17c8a664be6108a12def3a26c7b575e38812744b0de66c44`。host/sanitizer 各 282 项，root 原 R1 驱动 2052 故障场景通过，最终包 79 个清单文件读回通过。以下 ce4 只作首轮归档，不能用于交付。
- 卡已只读备份，37 个根文件仍与备份相同，177 个 DCIM 指纹已保存。备份指针为 `research/switch_residue/local/card-backup-pointer.json`。新 `prepare_card.py` 尚未执行；它要求不存在的最终 `release.json`，不能跳过 R2 复审手填假通过。

- 相机：GXR + A12 50mm，官方组件 1.51；机身运行 Stage2j + Stage2k P0，`ilaunch3` SHA-256 为 `8a0ab7a1c490d1213eb22ff9c4b41b7c874fb774b6606330f4884f4ffb9820ba`。不是下面 10 月 19 日的 R3。
- 最后一次卡交接是 R-all 的 P，SHA 前缀 `c84d12e4`。本轮用户已确认重新运行并显示 RESTORED、重新插卡，不再要求重复恢复。新固件移除了 P0，不再运行 P。
- 新树 `firmware/stage2l_switch/`：deep 失败不写 S、不请求 preview、不发布新选择，光标退回上个成功槽；08 为普通切换。uncertain 继续锁住深层切换。原 F6/F7 与启动 T 范围问题未改。
- 新包 `artifacts/stage2l-switch-packages/stage2l-switch-ce4d9a537821/`：机身 SHA-256 为 `ce4d9a537821908435a1af6f0510caaf1655f52fd950e684fad4af924c3240fc`，payload 8064 B；candidate 35 文件，official recovery 29 文件。使用已有 v5-fuji-daily，01～06 与现卡测试表相同，07/08 为标准别名。没有新增色彩拟合。
- 本地验证：host 与 sanitizer 各 266 项；现卡表独立 6/6；daily 表 64 种槽位对及扫过 08 再回 04、关页重开均通过。`research/switch_residue/audit_package.py` 对最终包读回通过。没有相机成像、DNG/JPEG 或固件更新验收；本轮未写卡。
- 用户指定全部 worker 使用 GPT-6.1-Sol max，不切换 Claude。模型 capacity 失败按用户要求重试，不能用旧交接里的模型偏好覆盖它。

## 下一次接手

先完成 R1 缺口、重新构建和独立复审，再确定最终包哈希。旧 R-all 恢复已获用户确认；卡插回后先只读核对 UUID `0F824AED-99E3-397F-AC62-EFC0D90DD373`，备份现卡。已有授权是核对通过后准备卡，不必重新逐步问许可。只使用经核验的最终新包；不把 P 混入新包，不改照片。物理升级和同场景 04→06→08→04、JPEG+DNG 验收由用户完成。

峰值“硬件绝对不能换色”结论已更正，详见 [证据报告](../research/peaking_color/EVIDENCE_REVIEW_20261023.md)；不能据可写表、静态反汇编或离线算法声称已实现彩色描边。

## 2026-10-19 历史交接（状态和模型约定已被上文更新）

新 session 从这里接手。完整决策记录在 `decisions.tsv`（6 列：时间、key、决定、原因、产物、备注），最后十几行是最新进展。

## 目标

Ricoh GXR（机身 + A12 50mm，固件 1.51）做成类似现代 GR 的用法：16 个色彩配方，与 P/A/S/M 无关，ADJ 一键进配方列表，每张照片存 JPEG + DNG。

## 相机现在的状态

- 卡上是读数探针 R3，`ilaunch3` sha256 前缀 `728d3c02`（2026-10-19 写卡，旧的 R1 已备份到 `artifacts/gate-probe-packages/card-backup-before-r3-20261019T024031Z/`）。用户刷机后，相机里也是 R3；刷之前还是 R1。Image Settings 页显示的是读数，不是模式名。
- 恢复官方 1.51：用 `artifacts/gate-probe-packages/gate-probe-r1/recovery-official-1.51/SD_ROOT/` 的 `ilaunch3` 覆盖卡上的同名文件，然后在相机里升级。这条路在这台相机上验证过。

## 已经确认的事实

1. R1 真机读数（`captures/a12-50/2026-10-19/gate-probe-r1-readout/`）：`A=08 T=05 P=02 C=01 G0=21 S=2022F71C V=01 W=00000008 E=205A279C`。配方页打开时，`rfw_ui_active` 的五个条件全部满足。
2. 所以 Stage 2a/2b 配方选不中，不是这五个值的问题。`decisions.tsv` 里 `deep_select_regression_diagnosed`（“活动号不是 8”）的结论已被真机推翻。
3. 头号嫌疑：`firmware/stage2b_deep_select_fix/platform.c` 的 `rfw_acquire` 还要求 `*(u8*)0x205D9A7F == 0`。这个值由模式拨盘位置算出，有些档位不是 0。不为 0 时，配方不会写入，也不会刷新预览。这与用户看到的症状一致：选不中、颜色不变、停在 04。
4. 历史对照：Stage 1b 没有这项要求，真机能选。从 Stage 1c 开始加了这项要求，带着它的 2a、2b 真机都失败。

## 正在进行

- R2（`K/M/N` 放在第 10..12 行）已构建完成，但一屏只显示 9 行，开页看不到这三行。滚动会不会触发图像模式写入未核实，所以 R2 **不上机**。
- 已让同一个 Opus 5.5 high 子线程（标题“读数探针 R2：多显示三个状态值”）改做 **R3**：第一屏 9 行依次为 `K M N A T P C V G0`，去掉已确认的 `W`、`E`，其余与 R1/R2 相同。产出在 `firmware/gate_probe_r3/`、`artifacts/gate-probe-packages/gate-probe-r3/`、`research/gate_probe/R3_BUILD_REPORT.md`。
- R3 已核对并写卡（`decisions.tsv` 的 `gate_probe_r3_root_verified`、`gate_probe_r3_card_written`），等用户刷机后在常用拨盘挡位拍第一屏，重点看 `K`。

## 接手后的步骤

1. 等 R3 完成，然后自己逐字节核对：和官方、和 R1 的差异区间；反汇编确认运行期只写自己的显示缓冲和重入字节；校验和。方法可参考 `research/gate_probe/BUILD_REPORT.md` 和 `decisions.tsv` 里的 `gate_probe_root_verified` 一行。
2. 写卡：卡名 `RICOHDCX`，UUID `0F824AED…`。先只读确认，备份卡上的 `ilaunch3`，用 `cp -X` 只替换 `ilaunch3`，按包里的清单核对 29 个文件，删除 `._*`，然后弹出。
3. 一次性告诉用户要做什么：升级，开机，按 ADJ 进 Image Settings，拍下第一屏 9 行读数（重点看 `K`），关机。在那一页不要按 OK、Fn2，不要拨 ADJ 拨盘。
4. 如果 `K` 不是 0，基本坐实头号嫌疑。修法是以 Stage 2b 为基础，让配方写入不再依赖这个值，同时保留其余条件。修好后同样先核对，再写卡上机。

## 用户的工作约定

- 回复用中文。代码、命令、路径保持原样。
- 用户授权在固件做好之前主动推进：核对通过就直接写卡，不必每步询问。逐字节核对不能省。
- 相机操作一次说完整，用户做完一起反馈。
- worker 优先用 grok-4.7-build-fast，也可用 Opus 5.5 high。不用 codex，额度快用完了。
- SD 卡挂载时先只读确认，再写。
- 给 worker 的任务说明尽量写成短指令，把技术细节放进仓库里的说明文档，让 worker 自己去读。长段技术说明多次被安全分类器误拦；被拦的内容不能换个说法重发。

## 公开仓与本地数据

- GitHub 仓库公开发布。从理光官方固件提取的曲线和颜色表**只留在本地**，不进 Git：两份 `firmware/*/deep_tables.c` 已加进 `.gitignore`，并从历史中移除；`decisions.tsv` 里的具体矩阵数值也已删除，只保留结论。
- 本地开发和构建不受影响：`deep_tables.c` 仍在工作区。换机器或新 checkout 时，先下载官方固件，再运行 `firmware/stage2b_deep_select_fix/tools/generate_deep_tables.py` 重新生成。它读的是 `research/` 下的本地数据，这些同样不提交。
- 提交统一使用 GitHub 隐私邮箱 `10174279+aa2246740@users.noreply.github.com`（本仓库 `git config user.email` 已设置）。
- 不要提交：原厂固件文件、反汇编、`research/` 下带原始字节的证据、`artifacts/`、`captures/`。
