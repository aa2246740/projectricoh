<img src="assets/icon.svg" width="64" height="64" alt="">

# projectRicoh

Ricoh GXR 色彩配方扩展研究。当前先集中 A12 50mm Macro，首版目标为16个列表配方并同时保存配方 JPEG 与 DNG RAW。

[路线图：把 GXR 改成现代 GR](docs/ROADMAP.md) · [当前协作流程与操作清单](docs/A12_50_COLLABORATION.md) · [首轮结论与实现路线](docs/RESEARCH.md) · [研究协议](docs/RESEARCH_PROTOCOL.md)

[当前 A12 50mm 目标](docs/A12_50_SCOPE.md) · [RAW 与风险核验](docs/A12_50_RAW_AND_RISK.md)

2026-10-16 色彩方向：[16 个品牌模式参照与当前能力](research/color_targets/README.md)已按用户要求整理，优先理光正片、负片、高对比黑白。当前上机的 16 槽是项目自编功能测试库，尚未按这些品牌调色。正式库需要实拍标定，黑白模式也需接入配方系统。

2026-10-15 真机进展：用户报告新版运行成功，照片显示新增配方列表的第 08 至 16 槽，第 16 槽高亮。已确认配方界面在相机运行；实际 JPEG 效果、同次 DNG 和重启后的状态待拍摄验证。见[首次配方真机记录](research/stage1b_integration/FIRST_CAMERA_RUN.md)。

本次使用[新版 16 配方实验包](artifacts/stage1b-candidate/packages/stage1b-16-recipes-012bcd24e77b/README.md)。候选和官方恢复目录各 29 文件已读回核验。Fn2 与即时提交挂钩已移到原厂活动判断之后，其他活动在这两处不进入配方代码。支持电脑编辑配方、相机 ADJ 选择；相机内编辑保存尚未接入。附带的 16 槽验收库用于检查功能，胶片风格尚未调校。见[本轮检查](research/stage1b_recovery/RECOVERY_PLAN.md)和[独立复核](research/review/STAGE1B_NATIVE_GATES_REVIEW.md)。

2026-10-15 写卡记录：用户确认后，新版已放入 RICOHDCX，29 个固件文件与配方库读回通过，原有照片哈希不变，卡已安全弹出。[写卡记录](artifacts/stage1b-candidate/media-012bcd24e77b/handoff.json)与包内未上机状态保留为当时快照；后续真机结果另行记录，不改动原包。

阶段 0 的 `ISX` 刷写演练及阶段 1a v3 的 `OK 8` 探针已由用户完成，随后刷回官方 1.51 并核对 ISO 显示和重启正常。这些恢复结果覆盖对应旧包；新候选已观察到配方界面运行，JPEG+DNG 配对与故障后恢复仍待验证。见[刷写与恢复说明](research/phase0_drill/FLASH_AND_RECOVERY.md)和 [decisions.tsv](decisions.tsv)。

专用 M32R 工具、原厂 My Settings 记录、13 项颜色字段与白平衡偏移映射已用于当前实现。见[整合报告](research/stage1b_integration/REPORT.md)、[字段证据](research/field_mapping/REPORT.md)和[配方核心](firmware/recipe_v1/README.md)。

新增参考：[FRAME-GR2 对比研究](research/frame_gr2/REPORT.md)。已静态对比其 WN3 与官方 GR II 3.00 固件；当前缺少实现源码，内部代码未解包，作为配方列表和独立保存的产品参照。

## 重跑本地分析

下载的原始资料与工具保留在 `sources/`、`tools/` 和 `artifacts/downloads/`，Git 忽略这些目录。来源版本和 SHA-256 在研究报告及证据文件中。

```sh
python3 scripts/inspect_gxr.py artifacts/downloads/gxr-151.zip --extract artifacts/firmware/gxr-1.51 --output artifacts/firmware-inventory.json
python3 research/firmware/scan_gxr_firmware.py artifacts/firmware/gxr-1.51 --output research/firmware/scan.json
python3 research/firmware/trace_mysettings.py artifacts/firmware/gxr-1.51/ilaunch3 research/firmware/ilaunch3-sections.csv --output research/firmware/mysettings-trace.json
sh scripts/rea --version
python3 scripts/probe_rea.py
python3 scripts/verify_research.py
```

三个方向的报告分别在 [官方配方能力](research/recipes/REPORT.md)、[固件结构与定位](research/firmware/REPORT.md)和 [REA 工具边界](research/tooling/REPORT.md)。

Created in [T3 Code](https://t3.codes).
