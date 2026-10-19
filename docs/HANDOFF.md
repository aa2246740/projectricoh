# 交接说明（2026-10-19）

新 session 从这里接手。完整决策记录在 `decisions.tsv`（6 列：时间、key、决定、原因、产物、备注），最后十几行是最新进展。

## 目标

Ricoh GXR（机身 + A12 50mm，固件 1.51）做成类似现代 GR 的用法：16 个色彩配方，与 P/A/S/M 无关，ADJ 一键进配方列表，每张照片存 JPEG + DNG。

## 相机现在的状态

- 相机里是读数探针 R1，`ilaunch3` sha256 前缀 `94c797cb`。可以正常拍照。Image Settings 页显示的是读数，不是模式名。
- 恢复官方 1.51：用 `artifacts/gate-probe-packages/gate-probe-r1/recovery-official-1.51/SD_ROOT/` 的 `ilaunch3` 覆盖卡上的同名文件，然后在相机里升级。这条路在这台相机上验证过。

## 已经确认的事实

1. R1 真机读数（`captures/a12-50/2026-10-19/gate-probe-r1-readout/`）：`A=08 T=05 P=02 C=01 G0=21 S=2022F71C V=01 W=00000008 E=205A279C`。配方页打开时，`rfw_ui_active` 的五个条件全部满足。
2. 所以 Stage 2a/2b 配方选不中，不是这五个值的问题。`decisions.tsv` 里 `deep_select_regression_diagnosed`（“活动号不是 8”）的结论已被真机推翻。
3. 头号嫌疑：`firmware/stage2b_deep_select_fix/platform.c` 的 `rfw_acquire` 还要求 `*(u8*)0x205D9A7F == 0`。这个值由模式拨盘位置算出，有些档位不是 0。不为 0 时，配方不会写入，也不会刷新预览。这与用户看到的症状一致：选不中、颜色不变、停在 04。
4. 历史对照：Stage 1b 没有这项要求，真机能选。从 Stage 1c 开始加了这项要求，带着它的 2a、2b 真机都失败。

## 正在进行

- R2（`K/M/N` 放在第 10..12 行）已构建完成，但一屏只显示 9 行，开页看不到这三行。滚动会不会触发图像模式写入未核实，所以 R2 **不上机**。
- 已让同一个 Opus 5.5 high 子线程（标题“读数探针 R2：多显示三个状态值”）改做 **R3**：第一屏 9 行依次为 `K M N A T P C V G0`，去掉已确认的 `W`、`E`，其余与 R1/R2 相同。产出在 `firmware/gate_probe_r3/`、`artifacts/gate-probe-packages/gate-probe-r3/`、`research/gate_probe/R3_BUILD_REPORT.md`。
- R3 还没写卡，也没上机。

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
