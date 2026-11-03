# GXR 配方切换残留修复

2026-10-23 更新：R1 两项缺口已补齐并生成新候选 `efe6587190e8`，正在独立复审 R2，尚未写卡或上机。首轮 `ce4d9a537821` 已冻结并阻止交付，不能再用它替代新候选。以下分别保留本轮与首轮的证据身份。

## R2 候选，待独立复审

同一 cache 在部分 W 失败后重开，会核对原槽完整 49 字节 identity；只有 identity 未变才保留历史回退位置。改名、参数、白平衡、移位或空槽会清掉过期历史，uncertain 仍拒绝任何深层写入。为保持原来的代码区边界，删除对同一文件的第二次重复 decode，卡输入仍由完整 decoder 校验；生成默认值、名字检查及代码放置调整见 [WORKER_R2.md](WORKER_R2.md)。

打包入口现核对 host/sanitizer 的真实字段、编译 flags、固定表和库 SHA、完整源码/头文件/驱动/runner 身份及逐场景结果，19 项归类 fixture 包含 R1 原错标反例。fixture 本身不代表编译通过；新的四份实际编译报告使用 `*-r2` 路径，普通与 sanitizer 各 6/6，daily 各 64 种槽位对。

| 项目 | R2 身份与结果 |
| --- | --- |
| 本地包 | `artifacts/stage2l-switch-packages/stage2l-switch-efe6587190e8/`。 |
| 机身 | SHA-256 `efe6587190e845b1c28364c02a6b8bde14e046e7c7411393a4c9892124b6bfd7`，3993340 B。 |
| payload | SHA-256 `5510f2be98906f3b17c8a664be6108a12def3a26c7b575e38812744b0de66c44`，8080 B，early 余 0 B、原保护尾前余 4 B。builder/linker/hook 护栏未放宽。 |
| 完整 host / sanitizer | worker 各 282 项；新增重开回归 after 64/64。root 另以原 R1 驱动核对新树，34 个独立进程、2052 个故障场景通过，输出 `local/root-r2-review/results.json`。 |
| 最终包读回 | 79 个清单文件全匹配，35 个候选、29 个官方恢复文件，30 个 boot/OSD 窗口原样；来源与实际编译证据均绑定当前源码。 |
| 现卡 | 用户确认 R-all RESTORED；只读备份 `artifacts/stage2l-switch-packages/card-backup-before-switch-20261023T071151Z/`，37 个根文件、177 个 DCIM 文件指纹，尚未改动。 |

第二轮审查任务为 `gxr-switch-residue-review-20261023-r2`，结果预期写入 `REVIEW_R2.md`。只有该轮关闭缺口并核对精确身份后，root 才创建绑定被审文件的 `local/release.json` 并运行 `prepare_card.py`。用户已授权核验通过后准备卡，无需重新逐步询问。

## 首轮归档

R1 复审发现同 cache 重开丢历史光标及打包证据错标缺口，见 [REVIEW_R1.md](REVIEW_R1.md)。下述 `ce4d9a537821` 构建及 266 项结果仅属于首轮，不能当作 R2 身份或真机验收。

## 症状与证据

用户报告从 06 扫到 08 后，画面仍有富士风格。现有机身运行 Stage2j 加 Stage2k P0，机身 SHA-256 为 `8a0ab7a1c490d1213eb22ff9c4b41b7c874fb774b6606330f4884f4ffb9820ba`。现用表为 v5-fuji-test，SHA-256 为 `a52084ab8fcb04880b8454e11c8798725518d0997da122c049747b796a510343`。

有两条能产生残留的实际代码路径：

1. 当前 P0 在 08 找到并运行 `/ATA1/P` 后会返回 NULL，跳过普通配方 apply。原来 06 的深层颜色表因此可以继续生效；P 恢复助手只恢复此前峰值实验的字段，不负责恢复这些颜色表。`probe_bypass.py` 将旧 ELF 与现用机身映像逐字节对上后，复演了这条分支。有 P 时普通 apply 回调为 0 次，无 P 时为 1 次。这是带服务与缓存假设的指令模型，没有重新在相机执行 P。
2. Stage2j 的 `rfw_acquire()` 吞掉未发生 W 时的 clean CONFLICT，随后把原生 S、preview、applied_slot 发布成新槽。真实生产 C 加现卡备份表的 host 模型复现了 06→04 首 RPC 失败、丢回包、T 状态不符、ownership 丢失后，界面错报 04、deep.active 却仍为 5 的情况。没有这一次真机 RPC 追踪，不能断言用户现场一定也触发了这个失败分支。

菜单和 EXIF 的 Standard 只能说明原生模式，不能证明深层曲线已恢复。06 与 04 可以使用同一个原生 Standard 选择器，前次用元数据排除残留的结论不成立。

## 修复范围

- `firmware/stage2l_switch/platform.c` 对 deep transition 的所有非 OK 结果原样返回，不再写 S、请求 preview 或发布新配方。
- `firmware/stage2l_switch/ui.c` 在有效占用槽切换失败时，把光标退回最后成功的 applied_slot；没有成功身份时不捏造 04。
- 新树基于 Stage2j，没有集成 P0。08 走正常选择和恢复流程。
- W 尝试后失去回包仍置 uncertain，后续深层切换被拒绝，不盲写重试。保留上次提交身份不表示物理 ISP 已全部回到那个状态。

未改 deep 颜色算法、格式、生成输入、九个 hook 或 linker 容量。01～06 的颜色表与现用 v5-fuji-test 逐字节相同；包使用已有 v5-fuji-daily，07、08 是标准别名，名称仍保留旧库的 PrbA/PrbB。这次没有新增品牌调色或准确度主张。

## 本地验证

| 对象 | 结果 |
| --- | --- |
| 现卡表的独立 06→04 复现 | 旧树 2/6；新树 host 与 ASan/UBSan 各 6/6。五种失败不发布新槽；成功逐行核对七条 stock 行及 T=2。 |
| 新包 daily 表的切换 | host 与 ASan/UBSan 均通过全部 64 种有序槽位对，以及 04→05→06→07→08→04、关闭再打开。 |
| 实现 worker 完整验证 | host 与 ASan/UBSan 各 266 项，ABI 48 项；原成功路径 RPC 记录与旧版本逐字节相同，mutation 与菜单分支检查通过。 |
| M32R payload | 8064 B，SHA-256 `13e0aa2cea8df2721e360fd76d596ae0cd240694acc065051f4269d6a04755f3`。early 区剩 4 B，原 256 B 探针保留区保持 FF。 |
| 最终包读回 | 清单 75 个文件全匹配；candidate 35 文件、official recovery 29 文件；28 个非机身组件等于官方原件，30 个既有 boot/OSD 窗口保持原样。 |
| 旧产物保护 | root 517 个基线文件哈希未变；worker 完成时的独立快照 4626 个旧文件未变。后续 root 更新本报告、README、HANDOFF 与决策日志，不属于 worker 当时的检查。 |

证据在 `local/baseline-stage2j/`、`local/fixed-stage2l*/`、`local/daily-sweep*/`、`local/probe-bypass.json`、`local/package-readback.json`；实现详情见 [WORKER_REPORT.md](WORKER_REPORT.md)，精确差异见 `firmware/stage2l_switch/build/source.diff`。`python3 -I -B research/switch_residue/audit_package.py` 可对最终包、官方组件、当前源码和 host 证据重新核验，不写卡。

## 交付及真机步骤

本地包为 `artifacts/stage2l-switch-packages/stage2l-switch-ce4d9a537821/`。

- 机身 `ilaunch3`：3993340 B，SHA-256 `ce4d9a537821908435a1af6f0510caaf1655f52fd950e684fad4af924c3240fc`。
- `DEEPTBL0.DAT` 与 `DEEPTBL1.DAT`：SHA-256 `44a0ff9e3b584f62dafb76aa90ba05c2bb75c2b74f78f23853345930804e6f05`。
- 配方库与既有 Stage2j 相同；包内没有 P。

此前最后一次写卡是 R-all 恢复助手，SHA 前缀 `c84d12e4`。本轮用户已确认重新运行并显示 RESTORED，随后重新插卡，不再要求重复恢复。新版不运行 P，不能把旧峰值实验的持久字段留到升级后处理。本轮尚未写 SD；先确认卷 UUID `0F824AED-99E3-397F-AC62-EFC0D90DD373`、核对现有文件并备份，待 R1 缺口补齐、重建和复审通过后再准备最终包。

上机后需要核对同一场景 04→06→08→04，确认最后 04 与最初 04 一致；再检查关页、重启及同次 JPEG+DNG。若恢复或拍摄失败，记录实际表现，不把本地通过当成相机通过。

已附带逐字节等于官方的 29 文件恢复目录。既有正常更新与旧实验回退成功，不证明 MAIN 任意损坏时都可恢复。继承的 F6 固定 `!4`、F7 cache 丢失时 deep 会话身份丢失、启动 T 读值范围问题本轮未改。

## 峰值颜色结论更正

按用户决定停止新峰值实验。两个模式的既有试验都只把整幅染紫，白边仍白；这否定所测入口，不能证明 GXR 硬件绝对无法换色。没有可交付的彩色峰值实现。详见 [证据复核](../peaking_color/EVIDENCE_REVIEW_20261023.md)。
