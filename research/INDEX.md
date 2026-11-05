# 研究与固件包索引

生成日期：2026-11-04。只读整理，不替代各目录里的报告正文。

现行现场（MOUNT，2026-11-04）：机身 v3.10（ilaunch3 `a04f1ed4`）已刷；DAT 为 g156 test（`0f4f26d4`）。g156 复审结论是可以上卡做有监督现场测试。随后出现 BOOT 跳过与朋友关机丢表，正在进 g157。28mm/50mm 当天未刷 v3.10。Studio 当时还不能读写 g156（PR #29 复审可以合并）。

公开仓库约定：本页只写标题、结论和相对链接，不含固件地址、偏移、逐字节或表数据。

完整决策流水账：[`../decisions.tsv`](../decisions.tsv)。路线图原文：[`../docs/ROADMAP.md`](../docs/ROADMAP.md)（2026-10-13，后面的代数以本页和 decisions 为准）。

## 想找什么 → 去哪里

| 想找 | 先打开 | 再看 |
| --- | --- | --- |
| 颜色模型和预测链（含 C040 修正） | [model_c040_r1/REPORT.md](model_c040_r1/REPORT.md)、[bluecyan_r1/REPORT.md](bluecyan_r1/REPORT.md) | [beyond24/REPORT.md](beyond24/REPORT.md)、[capability_ladder/REPORT.md](capability_ladder/REPORT.md)、[calibration_20261020/REPORT.md](calibration_20261020/REPORT.md)、[hw_mining_r1/SYNTHESIS.md](hw_mining_r1/SYNTHESIS.md) |
| 拟合工具 fit_fast | [../tools/fit_fast/](../tools/fit_fast/) | [fit_fast_r1/REPORT.md](fit_fast_r1/REPORT.md)（可以交复审）；[review_fit_fast_r2/REVIEW.md](review_fit_fast_r2/REVIEW.md)（修改后再采用）；decisions 里 fit-fast-r3 为不能采用 |
| 模拟器（快速版 / 参考版） | 快速：[../tools/gxr_emulator_fast/](../tools/gxr_emulator_fast/)；参考：[../tools/gxr_emulator/](../tools/gxr_emulator/) | [emulator_fast_r1/REPORT.md](emulator_fast_r1/REPORT.md)、[review_emulator_fast_r4/REVIEW.md](review_emulator_fast_r4/REVIEW.md)（修改后再采用）；可行性：[emulator_feasibility_r1/REPORT.md](emulator_feasibility_r1/REPORT.md)；批量：[../tools/gxr_emulator_batch/](../tools/gxr_emulator_batch/)；待机：[emulator_standby/REPORT.md](emulator_standby/REPORT.md) |
| 测试工具（C 版 / Python 版） | C：[../tools/native_harness_c/](../tools/native_harness_c/)；Python：[../tools/native_harness/](../tools/native_harness/) | [harness_speed/](harness_speed/)、[review_harness_c_switch_r2/REVIEW.md](review_harness_c_switch_r2/REVIEW.md)；快路径：[../tools/native_harness_fast/](../tools/native_harness_fast/) |
| Studio | [../studio/](../studio/)（独立仓库检出） | 设计 [studio_v2/PRD.md](studio_v2/PRD.md)、[studio_design/ARCHITECTURE.md](studio_design/ARCHITECTURE.md)；g156 编解码 [review_studio_g156_r2/REVIEW.md](review_studio_g156_r2/REVIEW.md)（可以合并）；GPU 预览 [studio_gpu_r1/REPORT.md](studio_gpu_r1/REPORT.md) |
| 探针 probe1–3 | [probe_pack_r1/REPORT.md](probe_pack_r1/REPORT.md) → [probe_pack_r2/REPORT_PROBE2.md](probe_pack_r2/REPORT_PROBE2.md) → [probe_pack_r3/REPORT_PROBE3.md](probe_pack_r3/REPORT_PROBE3.md) | 复审均可上卡（v3.9 MOUNT）：[review_probe_pack_r1](review_probe_pack_r1/)、[review_probe2_r1](review_probe2_r1/REVIEW.md)、[review_probe3_r1](review_probe3_r1/REVIEW.md)；包在 `../firmware/package_v39_g154_probe{,2,3}/` |
| 现场照片 captures | [../captures/](../captures/) | 中午色卡 [../captures/noon-20261104/](../captures/noon-20261104/)；探针 [../captures/probe2-field-20261103/](../captures/probe2-field-20261103/)、[../captures/probe3-field-20261104/](../captures/probe3-field-20261104/)；g152 Looks [../captures/looks-g152-20261102/](../captures/looks-g152-20261102/)；早期 50mm [../captures/a12-50/](../captures/a12-50/) |
| 胶片和 LUT 目标源 | [film_look_routes/REPORT.md](film_look_routes/REPORT.md)、[film_looks_r2/ACROS.md](film_looks_r2/ACROS.md) | [spektrafilm_bake/REPORT.md](spektrafilm_bake/REPORT.md)、[fotufilm_bake/REPORT.md](fotufilm_bake/REPORT.md)、[fuji_phase2/REPORT.md](fuji_phase2/REPORT.md)、[huzi_luts/](huzi_luts/)、[vlog_alchemy_eval/REPORT.md](vlog_alchemy_eval/REPORT.md)、[color_targets/README.md](color_targets/README.md) |
| g156 现场问题 | [g156_field_issues_r1/REPORT.md](g156_field_issues_r1/REPORT.md) | [field_gate_r1/REPORT.md](field_gate_r1/REPORT.md)、[g156/REPORT.md](g156/REPORT.md)、[review_g156_r1/REVIEW.md](review_g156_r1/REVIEW.md) |
| g157 | [g157/](g157/)（无 REPORT，构建脚本与 local） | 包 [../firmware/package_v310_g157/](../firmware/package_v310_g157/)；颜色输入 [model_c040_r1/REPORT.md](model_c040_r1/REPORT.md)、[film_looks_r2/ACROS.md](film_looks_r2/ACROS.md) |
| 路线图 | [../docs/ROADMAP.md](../docs/ROADMAP.md) | 2026-11-04 之后：g157 稳定后再衡量机内 3D LUT（decisions `roadmap-after-g157`）；槽位政策见 `slot-policy+speed-review` |

## 固件包 `firmware/package_*`

SHA 只写前 8 位。body 列是 `ilaunch3`。DAT 列是 `GXRCE.DAT`。上过相机以 `decisions.tsv` 的写卡/刷写/现场记录为准，找不到就写未知。

| 包 | 版本 | 代数 | body | DAT | 状态（README/清单首行） | 上过相机 |
| --- | --- | --- | --- | --- | --- | --- |
| [package_v35_g117](../firmware/package_v35_g117/) | v3.5 | 117 | `6e9ea058` | `4f5eeaff` | 只读容器交付 | 未知 |
| [package_v36_diag1](../firmware/package_v36_diag1/) | v3.6 | diag 1 | `50720c80` | `38e3db6e` | GENERATION 125; 30 files in local/SD_ROOT; 29 identical to gen120b. | 已上（diag-v2 现场目录对应更早诊断链） |
| [package_v36_diag2](../firmware/package_v36_diag2/) | v3.6 | diag 2 | `50720c80` | `ef39f71b` | Generation 128. Host checks complete. Ready for review. | 已上（diag-v2-field） |
| [package_v36_diag21](../firmware/package_v36_diag21/) | v3.6 | diag 21 | `50720c80` | `097a178a` | Generation 132. Complete 30-file package. Host review candidate. | 已上（diag-v21-field） |
| [package_v36_g117](../firmware/package_v36_g117/) | v3.6 | 117 | `50720c80` | `35ce20ac` | 主机三单元 PASS，非真机验收 | 主机 PASS；三单元现场见 three_module_audit |
| [package_v36_g118](../firmware/package_v36_g118/) | v3.6 | 118 | `50720c80` | `e557c726` | （包内无 README 首行） | 未知 |
| [package_v36_g119](../firmware/package_v36_g119/) | v3.6 | 119 | `50720c80` | `d11e88ea` | （包内无 README 首行） | 未知 |
| [package_v36_g120](../firmware/package_v36_g120/) | v3.6 | 120 | `50720c80` | `b22928a8` | STOPPED | STOPPED，不上卡 |
| [package_v36_g120b](../firmware/package_v36_g120b/) | v3.6 | 120 | `50720c80` | `233e23f7` | NOT_ACCEPTED / STOPPED | NOT_ACCEPTED / STOPPED |
| [package_v36_g121](../firmware/package_v36_g121/) | v3.6 | 121 | `50720c80` | `3b9342ee` | （包内无 README 首行） | 未知 |
| [package_v36_g122](../firmware/package_v36_g122/) | v3.6 | 122 | `50720c80` | `9724268c` | （包内无 README 首行） | 未知 |
| [package_v36_g123](../firmware/package_v36_g123/) | v3.6 | 123 | `50720c80` | `4ee9e6fe` | （包内无 README 首行） | 未知 |
| [package_v36_g124](../firmware/package_v36_g124/) | v3.6 | 124 | `50720c80` | `ebf07faa` | （包内无 README 首行） | 未知 |
| [package_v36_g126](../firmware/package_v36_g126/) | v3.6 | 126 | `50720c80` | `a855adcf` | （包内无 README 首行） | 未知 |
| [package_v36_g127](../firmware/package_v36_g127/) | v3.6 | 127 | `50720c80` | `9100616f` | （包内无 README 首行） | 未知 |
| [package_v36_g129](../firmware/package_v36_g129/) | v3.6 | 129 | `50720c80` | `b5839674` | （包内无 README 首行） | 未知 |
| [package_v36_g130](../firmware/package_v36_g130/) | v3.6 | 130 | `50720c80` | `bd2f47c0` | （包内无 README 首行） | 未知 |
| [package_v36_g131](../firmware/package_v36_g131/) | v3.6 | 131 | `50720c80` | `5ca22d7b` | （包内无 README 首行） | 未知 |
| [package_v37_diag](../firmware/package_v37_diag/) | v3.7 | — | `d0060740` | `a1b53c21` | （包内无 README 首行） | 未知 |
| [package_v37_g135](../firmware/package_v37_g135/) | v3.7 | 135 | `d0060740` | `57743bc1` | （包内无 README 首行） | 复审可上测试卡；是否实拍见现场目录 |
| [package_v37_redisplay](../firmware/package_v37_redisplay/) | v3.7 | redisplay | `d0060740` | `—` | （包内无 README 首行） | 研究记录已写卡 B，等实拍 |
| [package_v38_cpuprobe](../firmware/package_v38_cpuprobe/) | v3.8 | cpuprobe | `d4fa3b46` | `94f042a1` | （包内无 README 首行） | 已上（cpuprobe-field-20261101） |
| [package_v38_diag](../firmware/package_v38_diag/) | v3.8 | — | `d4fa3b46` | `b19ec9a3` | （包内无 README 首行） | 未知 |
| [package_v38_diag143](../firmware/package_v38_diag143/) | v3.8 | diag 143 | `d4fa3b46` | `52a19ed1` | （包内无 README 首行） | 未知 |
| [package_v38_diag144](../firmware/package_v38_diag144/) | v3.8 | diag 144 | `d4fa3b46` | `acb44ac0` | （包内无 README 首行） | 未知 |
| [package_v38_diag145](../firmware/package_v38_diag145/) | v3.8 | diag 145 | `d4fa3b46` | `222ccf4b` | （包内无 README 首行） | 未知 |
| [package_v38_diag146](../firmware/package_v38_diag146/) | v3.8 | diag 146 | `d4fa3b46` | `1a3ed045` | （包内无 README 首行） | 未知 |
| [package_v38_diag147](../firmware/package_v38_diag147/) | v3.8 | diag 147 | `d4fa3b46` | `85fd69ff` | （包内无 README 首行） | 未知 |
| [package_v38_diag147a](../firmware/package_v38_diag147a/) | v3.8 | diag 147 | `d4fa3b46` | `9e03675d` | （包内无 README 首行） | 已上（diag147a-field-20261101） |
| [package_v38_g137](../firmware/package_v38_g137/) | v3.8 | 137 | `d4fa3b46` | `78dcbb9a` | （包内无 README 首行） | 已上（field-v38-g137 / 三单元 / 街头） |
| [package_v38_g138](../firmware/package_v38_g138/) | v3.8 | 138 | `d4fa3b46` | `88a4359b` | （包内无 README 首行） | 未知 |
| [package_v38_g139](../firmware/package_v38_g139/) | v3.8 | 139 | `d4fa3b46` | `aab6c4f8` | （包内无 README 首行） | 未知 |
| [package_v38_g139_test](../firmware/package_v38_g139_test/) | v3.8 | 139 | `d4fa3b46` | `2378a88c` | （包内无 README 首行） | 未知 |
| [package_v38_g139m](../firmware/package_v38_g139m/) | v3.8 | 139 | `d4fa3b46` | `295850cb` | （包内无 README 首行） | 未知 |
| [package_v38_g139m_test](../firmware/package_v38_g139m_test/) | v3.8 | 139 | `d4fa3b46` | `594fe2ba` | （包内无 README 首行） | 未知 |
| [package_v38_g150](../firmware/package_v38_g150/) | v3.8 | 150 | `d4fa3b46` | `c4878f66` | （包内无 README 首行） | 已上（MOUNT/街头；朋友包） |
| [package_v38_g150_test](../firmware/package_v38_g150_test/) | v3.8 | 150 | `d4fa3b46` | `68418fe7` | （包内无 README 首行） | 未知 |
| [package_v38_g152](../firmware/package_v38_g152/) | v3.8 | 152 | `d4fa3b46` | `5ec4f1d2` | （包内无 README 首行） | 未知（release） |
| [package_v38_g152_test](../firmware/package_v38_g152_test/) | v3.8 | 152 | `d4fa3b46` | `563c9227` | （包内无 README 首行） | 已上（2026-11-01 现场，looks-g152 照片） |
| [package_v38_probe_p1](../firmware/package_v38_probe_p1/) | v3.8 | probe p1 | `d4fa3b46` | `a79020be` | （包内无 README 首行） | 复审不可上测试卡 |
| [package_v39_body_only](../firmware/package_v39_body_only/) | v3.9 | 机身-only | `71697385` | `—` | （包内无 README 首行） | 未知 |
| [package_v39_diagv4p](../firmware/package_v39_diagv4p/) | v3.9 | diag v4p | `8233a1c4` | `—` | （包内无 README 首行） | 已上（MOUNT 录像，2026-11-02） |
| [package_v39_g149](../firmware/package_v39_g149/) | v3.9 | 149 | `已删除` | `—` | 作废（2026-11-01） | 作废，未上机 |
| [package_v39_g151](../firmware/package_v39_g151/) | v3.9 | 151 | `71697385` | `544211ae` | （包内无 README 首行） | 机身复审可刷；DAT 待 g152 移植 |
| [package_v39_g151_test](../firmware/package_v39_g151_test/) | v3.9 | 151 | `71697385` | `5574164c` | （包内无 README 首行） | 未知 |
| [package_v39_g153](../firmware/package_v39_g153/) | v3.9 | 153 | `8233a1c4` | `e6dab162` | （包内无 README 首行） | 未知 |
| [package_v39_g153_test](../firmware/package_v39_g153_test/) | v3.9 | 153 | `8233a1c4` | `5afc3889` | （包内无 README 首行） | 未知 |
| [package_v39_g154](../firmware/package_v39_g154/) | v3.9 | 154 | `8233a1c4` | `3c63ae08` | （包内无 README 首行） | 复审为修改后再上卡；随后有 Looks18/探针路径 |
| [package_v39_g154_looks18_test](../firmware/package_v39_g154_looks18_test/) | v3.9 | 154 | `8233a1c4` | `5f6191c8` | Looks18 测试 DAT（G154L） | 已上（G154L；探针基线，朋友回退包） |
| [package_v39_g154_probe](../firmware/package_v39_g154_probe/) | v3.9 | 154 | `8233a1c4` | `a30675fa` | 可以上卡（复审） | 已上（MOUNT 探针 1，2026-11-03） |
| [package_v39_g154_probe2](../firmware/package_v39_g154_probe2/) | v3.9 | 154 | `8233a1c4` | `102388ab` | 可以上卡（复审） | 已上（MOUNT 探针 2，2026-11-03） |
| [package_v39_g154_probe3](../firmware/package_v39_g154_probe3/) | v3.9 | 154 | `8233a1c4` | `a3f831f9` | 可以交复审；复审可以上卡 | 已上（MOUNT 探针 3，2026-11-04） |
| [package_v39_g154_test](../firmware/package_v39_g154_test/) | v3.9 | 154 | `8233a1c4` | `ac4263a0` | （包内无 README 首行） | 未知 |
| [package_v310_g155](../firmware/package_v310_g155/) | v3.10 | 155 | `a04f1ed4` | `308c7096` | （包内无 README 首行） | 未知 |
| [package_v310_g155_test](../firmware/package_v310_g155_test/) | v3.10 | 155 | `a04f1ed4` | `a1e731f1` | （包内无 README 首行） | 未知 |
| [package_v310_g155b](../firmware/package_v310_g155b/) | v3.10 | 155 | `a04f1ed4` | `1df64437` | （包内无 README 首行） | 复审建议可作无 DAT 刷机后的备选 DAT；是否实际使用未知 |
| [package_v310_g155b_test](../firmware/package_v310_g155b_test/) | v3.10 | 155 | `a04f1ed4` | `466bf5b7` | （包内无 README 首行） | 未知 |
| [package_v310_g155c](../firmware/package_v310_g155c/) | v3.10 | 155 | `a04f1ed4` | `69fa8510` | 可以上卡（复审，有监督） | 复审放行；未见写卡/刷写记录 |
| [package_v310_g155c_test](../firmware/package_v310_g155c_test/) | v3.10 | 155 | `a04f1ed4` | `c3017d36` | 可以上卡（复审，有监督） | 复审放行；未见写卡/刷写记录 |
| [package_v310_g156](../firmware/package_v310_g156/) | v3.10 | 156 | `a04f1ed4` | `f42b81a8` | 可以上卡（有监督现场测试） | 复审放行；机主现场主要用的是 test 包 |
| [package_v310_g156_test](../firmware/package_v310_g156_test/) | v3.10 | 156 | `a04f1ed4` | `0f4f26d4` | 可以上卡（有监督现场测试） | 已上（MOUNT，2026-11-04；见 noon / BOOT 跳过现场） |
| [package_v310_g157](../firmware/package_v310_g157/) | v3.10 | 157 | `a04f1ed4` | `cdc5a7bd` | ACCEPTANCE_PENDING | 未知（清单 camera_verified=false，ACCEPTANCE_PENDING） |
| [package_v310_g157_test](../firmware/package_v310_g157_test/) | v3.10 | 157 | `a04f1ed4` | `d411edac` | ACCEPTANCE_PENDING | 未知（清单 camera_verified=false） |

配套机身 SHA 速查：v3.5 `6e9ea058`，v3.6 `50720c80`，v3.7 `d0060740`，v3.8 `d4fa3b46`，v3.9 初版（g151）`71697385`，v3.9 后（g153 起）`8233a1c4`，v3.10 `a04f1ed4`。

## 研究目录

同一主题的 r1、r2…按先后排。结论尽量用报告第一行的判定句；第一行若是长技术段，改成不带地址和表数据的短句。

### 起步、协议与早期真机

| 目录 | 日期 | 类型 | 结论 | 状态 | 关键产出 |
| --- | --- | --- | --- | --- | --- |
| [a12_50_firmware](a12_50_firmware/) | 2026-10-12 | 研究 | 不能把 My Settings 六槽直接扩成 16 个独立色彩配方，应新建配方库 | 历史 | [REPORT.md](a12_50_firmware/REPORT.md) |
| [contrast_curve](contrast_curve/) | 2026-10-13 | 研究 | 对比度处理入口已找到，固定表在单元固件 | 历史 | [REPORT.md](contrast_curve/REPORT.md) |
| [contrib_gr_analysis](contrib_gr_analysis/) | 2026-10-19 | 研究 | 投稿照片不能直接当 phase 目标 | 历史 | [REPORT.md](contrib_gr_analysis/REPORT.md) |
| [dng_structure](dng_structure/) | 2026-10-13 | 研究 | 原厂 DNG 结构首轮扫描 | 历史 | [REPORT.md](dng_structure/REPORT.md) |
| [field_mapping](field_mapping/) | 2026-10-13 | 现场分析 | Setting1 十三字段位置经真机照片确认 | 历史 | [REPORT.md](field_mapping/REPORT.md) |
| [firmware](firmware/) | 2026-10-12 | 研究 | 固件结构与定位首轮扫描 | 历史 | [REPORT.md](firmware/REPORT.md) |
| [frame_gr2](frame_gr2/) | 2026-10-16 | 研究 | FRAME-GR2 作为产品参照，不直接移植 | 历史 | [REPORT.md](frame_gr2/REPORT.md) |
| [git_sync](git_sync/) | 2026-11-04 | 研究 | 需要人工确认 | OPEN | [REPORT.md](git_sync/REPORT.md) |
| [grmod_study](grmod_study/) | 2026-11-01 | 研究 | Ricoh-GRMod 参照 | 历史 | [REPORT.md](grmod_study/REPORT.md) |
| [gxr_deep_access](gxr_deep_access/) | 2026-10-25 | 研究 | 深层 ISP 访问 | 历史 | [REPORT.md](gxr_deep_access/REPORT.md) |
| [gxr_possibilities](gxr_possibilities/) | 2026-10-31 | 研究 | GXR 可改范围盘点 | 历史 | [REPORT.md](gxr_possibilities/REPORT.md) |
| [hidden_processing](hidden_processing/) | 2026-10-13 | 研究 | 隐藏处理：13 色彩字段经机身传到模块 | 历史 | [REPORT.md](hidden_processing/REPORT.md) |
| [isp_pipeline](isp_pipeline/) | 2026-10-16 | 研究 | ISP 流水线静态图 | 历史 | [REPORT.md](isp_pipeline/REPORT.md) |
| [phase0_drill](phase0_drill/) | 2026-10-14 | 研究 | 刷写与条件恢复手册；演练已在真机闭环 | 历史 | [FLASH_AND_RECOVERY.md](phase0_drill/FLASH_AND_RECOVERY.md) |
| [pitfalls](pitfalls/) | 2026-11-01 | 研究 | 清单完成 | 现行 | [CHECKLIST.md](pitfalls/CHECKLIST.md) |
| [recipes](recipes/) | 2026-10-12 | 研究 | 官方 My Settings 能力核验 | 历史 | [REPORT.md](recipes/REPORT.md) |
| [review](review/) | 2026-10-16 | 研究 | 早期 GPT 独立复核 | 历史 | [REPORT.md](review/REPORT.md) |
| [stage1_brief](stage1_brief/) | 2026-10-13 | 研究 | 第 1 阶段 worker 共同背景 | 已被后续阶段取代 | [COMMON.md](stage1_brief/COMMON.md) |
| [stage1_codespace](stage1_codespace/) | 2026-10-13 | 研究 | 当时没有经真机证明安全的代码空间 | 已被后续阶段取代 | [REPORT.md](stage1_codespace/REPORT.md) |
| [stage1_data](stage1_data/) | 2026-10-13 | 研究 | 配方保存在卡上双文件，选中时覆盖 Setting1 | 已被后续阶段取代 | [REPORT.md](stage1_data/REPORT.md) |
| [stage1_ui](stage1_ui/) | 2026-10-13 | 研究 | 推荐替换 ADJ 的 Image Settings 列表 | 已被后续阶段取代 | [REPORT.md](stage1_ui/REPORT.md) |
| [stage1a_probe](stage1a_probe/) | 2026-10-14 | 研究 | 候选区可用于实验，运行时持久性待真机 | 已被 [stage1a_probe_v3](stage1a_probe_v3/) 取代 | [REPORT.md](stage1a_probe/REPORT.md) |
| [stage1a_probe_v2](stage1a_probe_v2/) | 2026-10-14 | 研究 | 原位压缩与等价重放 0 分歧 | 已被 [stage1a_probe_v3](stage1a_probe_v3/) 取代 | [REPORT.md](stage1a_probe_v2/REPORT.md) |
| [stage1a_probe_v3](stage1a_probe_v3/) | 2026-10-14 | 研究 | 改为有界哨兵读取，待复核确认 | 已被后续阶段取代 | [REPORT.md](stage1a_probe_v3/REPORT.md) |
| [stage1b_integration](stage1b_integration/) | 2026-10-15 | 研究 | 可链接实现完成，电脑端验证通过 | 已被后续阶段取代 | [REPORT.md](stage1b_integration/REPORT.md) |
| [stage1b_recovery](stage1b_recovery/) | 2026-10-15 | 研究 | 新版已写卡，配方列表已在相机运行 | 已被后续阶段取代 | [RECOVERY_PLAN.md](stage1b_recovery/RECOVERY_PLAN.md) |
| [tone_curve](tone_curve/) | 2026-10-13 | 研究 | 首轮单调表扫描未找到可确认曲线 | 历史 | [REPORT.md](tone_curve/REPORT.md) |
| [tooling](tooling/) | 2026-10-12 | 工具 | REA 可留作只读 CLI，不能反编译 GXR 主程序 | 历史 | [REPORT.md](tooling/REPORT.md) |
| [tooling_m32r](tooling_m32r/) | 2026-10-12 | 工具 | 项目内 M32R objdump 可用 | 历史 | [REPORT.md](tooling_m32r/REPORT.md) |
| [tooling_m32r_asm](tooling_m32r_asm/) | 2026-10-12 | 工具 | M32R 汇编链接闭环可用 | 历史 | [REPORT.md](tooling_m32r_asm/REPORT.md) |
| [tooling_m32r_c](tooling_m32r_c/) | 2026-10-12 | 工具 | m32r-elf C 交叉编译器已构建 | 现行 | [REPORT.md](tooling_m32r_c/REPORT.md) |
| [ui_bug_audit](ui_bug_audit/) | 2026-10-16 | 研究 | 根因是 force_adj_image 无条件改写当前功能 | 历史 | [REPORT.md](ui_bug_audit/REPORT.md) |
| [unit_drill](unit_drill/) | 2026-10-16 | 研究 | BLOCKED | 历史 | [REPORT.md](unit_drill/REPORT.md) |
| [unit_recovery](unit_recovery/) | 2026-10-16 | 研究 | PARTIAL：现有证据不足以开始单元固件写入 | 历史 | [REPORT.md](unit_recovery/REPORT.md) |

### 颜色模型、标定与 C040

| 目录 | 日期 | 类型 | 结论 | 状态 | 关键产出 |
| --- | --- | --- | --- | --- | --- |
| [beyond24](beyond24/) | 2026-10-20 | 研究 | 最值得先试的是移动 C040 色相节点；部分扇区可不改 T | 历史 | [REPORT.md](beyond24/REPORT.md) |
| [bluecyan_r1](bluecyan_r1/) | 2026-11-04 | 研究 | 部分找到：预测链误用 50mm 的 C040 节点给 MOUNT | 现行 | [REPORT.md](bluecyan_r1/REPORT.md) |
| [bridge_public_r1](bridge_public_r1/) | 2026-10-26 | 研究 | 继续使用冻结的共同白点 ColorMatrix 桥接 | 历史 | [REPORT.md](bridge_public_r1/REPORT.md) |
| [bw03_round2](bw03_round2/) | 2026-10-20 | 研究 | 两候选未守住彩色门槛，不建议直接替换日用 03 | 已被 [bw03_standard_mode](bw03_standard_mode/) 取代 | [REPORT.md](bw03_round2/REPORT.md) |
| [bw03_round3](bw03_round3/) | 2026-10-21 | 研究 | 不建议替换日用 03 | 已被 [bw03_standard_mode](bw03_standard_mode/) 取代 | [REPORT.md](bw03_round3/REPORT.md) |
| [bw03_standard_mode](bw03_standard_mode/) | 2026-10-25 | 研究 | 可行：新 03 只写与 04 相同的 Standard 设置 | 现行 | [REPORT.md](bw03_standard_mode/REPORT.md) |
| [bw_and_base_modes](bw_and_base_modes/) | 2026-10-16 | 研究 | B&W 与配方基础模式的静态追踪 | 历史 | [REPORT.md](bw_and_base_modes/REPORT.md) |
| [calibration_20261020](calibration_20261020/) | 2026-10-20 | 研究 | 不需要补拍；旧模型把 04 输出色相当成查表坐标 | 历史 | [REPORT.md](calibration_20261020/REPORT.md) |
| [capability_ladder](capability_ladder/) | 2026-10-20 | 研究 | 先补 Y 行，再决定是否上三通道曲线；没有现成任意 3D LUT | 现行 | [REPORT.md](capability_ladder/REPORT.md) |
| [channel_mixing](channel_mixing/) | 2026-10-20 | 研究 | type-26 一条曲线，type-28 的 3×3 可按配方写 | 历史 | [REPORT.md](channel_mixing/REPORT.md) |
| [closed_loop](closed_loop/) | 2026-10-21 | 工具 | 工具已跑通，不能宣称达到原机 95% | 现行 | [REPORT.md](closed_loop/REPORT.md)、[REPORT_R1.md](closed_loop/REPORT_R1.md) |
| [color_calibration](color_calibration/) | 2026-10-16 | 研究 | 16 个目标中相机标定和机内验收均为 0 | 历史 | [REPORT.md](color_calibration/REPORT.md) |
| [color_fit_v2](color_fit_v2/) | 2026-10-21 | 研究 | 01/02 主机候选未升级为已接受配方 | OPEN | [gr_round6/REPORT.md](color_fit_v2/gr_round6/REPORT.md) |
| [color_injection](color_injection/) | 2026-10-16 | 研究 | 颜色注入路径静态研究 | 历史 | [REPORT.md](color_injection/REPORT.md) |
| [color_references](color_references/) | 2026-10-19 | 研究 | 已取得 GR 色卡与 Adobe 包内 DCP 参照 | 历史 | [REPORT.md](color_references/REPORT.md) |
| [color_table_fit](color_table_fit/) | 2026-10-30 | 研究 | 编码往返一致，干净目标可恢复 | 历史 | [REPORT.md](color_table_fit/REPORT.md) |
| [color_targets](color_targets/) | 2026-10-16 | 研究 | 品牌目标清单，尚不是可安装配方库 | 现行 | [README.md](color_targets/README.md) |
| [daily_bugs_20261024](daily_bugs_20261024/) | 2026-10-25 | 现场分析 | 紫片是 06 遇到 ISO100 原厂特殊曲线分支 | 历史 | [REPORT.md](daily_bugs_20261024/REPORT.md) |
| [fidelity_ceiling](fidelity_ceiling/) | 2026-10-20 | 研究 | 主机模型上限；05 优先试节点移动，06 先验证分通道曲线 | 历史 | [fuji/REPORT.md](fidelity_ceiling/fuji/REPORT.md) |
| [grain](grain/) | 2026-10-20 | 研究 | 颗粒路径研究 | 历史 | [REPORT.md](grain/REPORT.md) |
| [grain_raw_feasibility](grain_raw_feasibility/) | 2026-10-20 | 研究 | RAW 颗粒可行性 | 历史 | [REPORT.md](grain_raw_feasibility/REPORT.md) |
| [hue_ring](hue_ring/) | 2026-10-20 | 工具 | 色相环屏幕测试图与分析工具 | 历史 | [README.md](hue_ring/README.md) |
| [hw_mining_r1](hw_mining_r1/) | 2026-10-27 | 研究 | 颜色硬件潜力三方汇总（核验后修正） | 现行 | [SYNTHESIS.md](hw_mining_r1/SYNTHESIS.md) |
| [hw_mining_r2](hw_mining_r2/) | 2026-10-27 | 研究 | 曲线前矩阵：没有找到已确认可按配方改的 3×3 | 现行 | [SYNTHESIS.md](hw_mining_r2/SYNTHESIS.md) |
| [hw_mining_r3](hw_mining_r3/) | 2026-10-27 | 研究 | MCR 三方汇总（核验后收窄） | 现行 | [SYNTHESIS.md](hw_mining_r3/SYNTHESIS.md) |
| [hw_refit_r1](hw_refit_r1/) | 2026-10-27 | 研究 | 硬件约束下回拟 | 历史 | [REPORT.md](hw_refit_r1/REPORT.md) |
| [hw_second_pass_r1](hw_second_pass_r1/) | 2026-10-27 | 研究 | 硬件第二轮 | 历史 | [REPORT.md](hw_second_pass_r1/REPORT.md) |
| [iso100_fix](iso100_fix/) | 2026-10-25 | 研究 | ISO100 分支修复相关研究 | 历史 | [REPORT.md](iso100_fix/REPORT.md) |
| [matrix_test_onbody](matrix_test_onbody/) | 2026-10-20 | 研究 | 矩阵上机测试 | 历史 | [REPORT.md](matrix_test_onbody/REPORT.md) |
| [mcr_value_model_r1](mcr_value_model_r1/) | 2026-10-27 | 研究 | MCR 价值模型 | 历史 | [REPORT.md](mcr_value_model_r1/REPORT.md) |
| [model_c040_r1](model_c040_r1/) | 2026-11-04 | 研究 | g157 配方候选 13 条；按单元 C040 已接入 | 现行 | [REPORT.md](model_c040_r1/REPORT.md) |
| [mount_calib_r1](mount_calib_r1/) | 2026-10-24 | 研究 | MOUNT 标定 | 历史 | [REPORT.md](mount_calib_r1/REPORT.md) |
| [phase1_curves](phase1_curves/) | 2026-10-19 | 研究 | type-26 曲线在中性像素上是 12-bit 到 JPEG 的折线 | 历史 | [REPORT.md](phase1_curves/REPORT.md) |
| [recipe_redo_r1](recipe_redo_r1/) | 2026-11-04 | 研究 | 电脑预测：MOUNT 映射优于 50mm 迁移 | 历史 | [REPORT.md](recipe_redo_r1/REPORT.md)、[REPORT_PREVIOUS_MODEL.md](recipe_redo_r1/REPORT_PREVIOUS_MODEL.md) |
| [recipe_tweak](recipe_tweak/) | 2026-10-23 | 研究 | 单配方微调参考实现已跑通 | 历史 | [REPORT.md](recipe_tweak/REPORT.md) |
| [refit_50mm_r7](refit_50mm_r7/) | 2026-10-24 | 研究 | 本轮没有达到 95% | 历史 | [REPORT.md](refit_50mm_r7/REPORT.md) |
| [split_tone](split_tone/) | 2026-10-20 | 研究 | 分色/裂调静态分析 | 历史 | [REPORT.md](split_tone/REPORT.md) |
| [structural_colour_r1](structural_colour_r1/) | 2026-11-02 | 研究 | 最有希望的是机身 F034 小图处理链 | 历史 | [REPORT.md](structural_colour_r1/REPORT.md) |
| [t1_probe](t1_probe/) | 2026-10-20 | 研究 | 08 探针条目已生成，相机效果未知 | 历史 | [REPORT.md](t1_probe/REPORT.md) |
| [t3_probe](t3_probe/) | 2026-10-21 | 研究 | 只供主机诊断，暂不适合上机 | 历史 | [REPORT.md](t3_probe/REPORT.md) |
| [t_persistence](t_persistence/) | 2026-10-20 | 研究 | T 持久化静态分析 | 历史 | [REPORT.md](t_persistence/REPORT.md) |
| [t_recovery](t_recovery/) | 2026-10-20 | 研究 | T 恢复静态分析 | 历史 | [REPORT.md](t_recovery/REPORT.md) |
| [tables_v1](tables_v1/) | 2026-10-20 | 研究 | preliminary first version，host 校验通过 | 已被 [tables_v4](tables_v4/) 取代 | [REPORT.md](tables_v1/REPORT.md) |
| [tables_v2](tables_v2/) | 2026-10-20 | 研究 | firmware_ready 保持 false | 已被 [tables_v4](tables_v4/) 取代 | [REPORT.md](tables_v2/REPORT.md) |
| [tables_v4](tables_v4/) | 2026-10-21 | 研究 | firmware_ready 保持 false，相机验收 pending | 历史 | [REPORT.md](tables_v4/REPORT.md) |
| [um_measurement](um_measurement/) | 2026-10-20 | 研究 | 点测光中灰工作锚已更新 | 历史 | [REPORT.md](um_measurement/REPORT.md) |

### GR / 富士目标与胶片 LUT

| 目录 | 日期 | 类型 | 结论 | 状态 | 关键产出 |
| --- | --- | --- | --- | --- | --- |
| [canonical_gr_pack](canonical_gr_pack/) | 2026-10-16 | 研究 | 已合成 16 槽原生候选，尚未通过深表运行或品牌外观验收 | 历史 | [REPORT.md](canonical_gr_pack/REPORT.md) |
| [film_engines_eval](film_engines_eval/) | 2026-10-31 | 研究 | 可以评审 | 历史 | [REPORT.md](film_engines_eval/REPORT.md) |
| [film_look_routes](film_look_routes/) | 2026-10-31 | 研究 | 可以评审 | 现行 | [REPORT.md](film_look_routes/REPORT.md) |
| [film_looks_r2](film_looks_r2/) | 2026-11-04 | 研究 | 可以换进 g157 的既定兼容布局（官方 Acros） | 现行 | [ACROS.md](film_looks_r2/ACROS.md) |
| [fotufilm_bake](fotufilm_bake/) | 2026-11-01 | 研究 | 可以评审 | 历史 | [REPORT.md](fotufilm_bake/REPORT.md) |
| [fuji_phase2](fuji_phase2/) | 2026-10-19 | 研究 | 主结果改成直通：F-Log2 LUT 输出码即比较用显示码 | 历史 | [REPORT.md](fuji_phase2/REPORT.md) |
| [gr4_analytic_target_r1](gr4_analytic_target_r1/) | 2026-10-27 | 研究 | 模拟器还不够准，暂不改 01/02 为解析新目标 | 已被 [gr4_analytic_target_r2](gr4_analytic_target_r2/) 取代 | [REPORT.md](gr4_analytic_target_r1/REPORT.md) |
| [gr4_analytic_target_r2](gr4_analytic_target_r2/) | 2026-10-27 | 研究 | 02 值得有限离线研究，01 暂缓 | 历史 | [REPORT.md](gr4_analytic_target_r2/REPORT.md) |
| [gr4_bench](gr4_bench/) | 2026-10-21 | 研究 | 电脑端计算，无相机操作 | 历史 | [REPORT.md](gr4_bench/REPORT.md) |
| [gr4_bleach_fit_r1](gr4_bleach_fit_r1/) | 2026-10-31 | 研究 | 部分：50mm 已拟合，MOUNT 本轮未单独拟合 | 历史 | [REPORT.md](gr4_bleach_fit_r1/REPORT.md) |
| [gr4_chart_ask_20261024](gr4_chart_ask_20261024/) | 2026-10-24 | 研究 | GR IV 色卡拍摄包已发出 | 历史 | [README.md](gr4_chart_ask_20261024/README.md) |
| [gr4_dense_returns_r1](gr4_dense_returns_r1/) | 2026-10-25 | 研究 | 50mm 的 01 已按新 GR IV 正片目标重拟合，仍是主机候选 | 历史 | [REPORT.md](gr4_dense_returns_r1/REPORT.md) |
| [gr4_lut_ceiling](gr4_lut_ceiling/) | 2026-10-26 | 研究 | 现有证据不能承诺 01/02 达到 95% | 历史 | [REPORT.md](gr4_lut_ceiling/REPORT.md) |
| [gr4_modes](gr4_modes/) | 2026-10-19 | 研究 | GR IV 投稿与连拍模式对照 | 历史 | [REPORT.md](gr4_modes/REPORT.md) |
| [gr4_nega_returns_r1](gr4_nega_returns_r1/) | 2026-10-25 | 研究 | 50mm 的 02 已转向 GR IV 默认 Negative 密集目标 | 历史 | [REPORT.md](gr4_nega_returns_r1/REPORT.md) |
| [gr4_positive](gr4_positive/) | 2026-10-22 | 研究 | GR IV 正片目标对照 | 历史 | [REPORT.md](gr4_positive/REPORT.md) |
| [gr4_repos_review_r1](gr4_repos_review_r1/) | 2026-10-27 | 研究 | GR 相关仓库复核 | 历史 | [REPORT.md](gr4_repos_review_r1/REPORT.md) |
| [gr4_sim_r3](gr4_sim_r3/) | 2026-10-27 | 研究 | GR IV 模拟第三轮 | 历史 | [REPORT.md](gr4_sim_r3/REPORT.md) |
| [gr_ae_target](gr_ae_target/) | 2026-10-21 | 研究 | GR 测光/AE 目标 | 历史 | [REPORT.md](gr_ae_target/REPORT.md) |
| [gr_complete_pipeline](gr_complete_pipeline/) | 2026-10-16 | 研究 | GR 完整流水线对照 | 历史 | [REPORT.md](gr_complete_pipeline/REPORT.md) |
| [gr_dense_reference](gr_dense_reference/) | 2026-10-22 | 研究 | GR 密集参照 | 历史 | [REPORT.md](gr_dense_reference/REPORT.md) |
| [gr_evalsets](gr_evalsets/) | 2026-10-21 | 研究 | GR 评测集 | 历史 | [REPORT.md](gr_evalsets/REPORT.md) |
| [gr_firmware](gr_firmware/) | 2026-10-16 | 研究 | GR 固件参照 | 历史 | [REPORT.md](gr_firmware/REPORT.md) |
| [gr_hdfchart](gr_hdfchart/) | 2026-10-22 | 研究 | GR HDF 色卡 | 历史 | [REPORT.md](gr_hdfchart/REPORT.md) |
| [gr_incamera_dev](gr_incamera_dev/) | 2026-10-21 | 研究 | GR 机内显影对照 | 历史 | [REPORT.md](gr_incamera_dev/REPORT.md) |
| [gr_metering_anchor](gr_metering_anchor/) | 2026-10-20 | 研究 | GR 测光锚仍未完全钉死 | 历史 | [REPORT.md](gr_metering_anchor/REPORT.md) |
| [gr_pairs](gr_pairs/) | 2026-10-21 | 研究 | GR 成对样本 | 历史 | [REPORT.md](gr_pairs/REPORT.md) |
| [gr_posneg_gap](gr_posneg_gap/) | 2026-11-01 | 研究 | 正负片差距 | 历史 | [REPORT.md](gr_posneg_gap/REPORT.md) |
| [gr_reference](gr_reference/) | 2026-10-13 | 研究 | GR 配方公开资料调研 | 历史 | [REPORT.md](gr_reference/REPORT.md) |
| [gr_webpairs](gr_webpairs/) | 2026-10-21 | 研究 | 网上成对样本 | 历史 | [REPORT.md](gr_webpairs/REPORT.md) |
| [huzi_luts](huzi_luts/) | 2026-10-24 | 研究 | 社区 LUT 包评估 | 历史 | [REPORT.md](huzi_luts/REPORT.md) |
| [look_ceiling_r1](look_ceiling_r1/) | 2026-11-02 | 研究 | Looks 上限 | 历史 | [REPORT.md](look_ceiling_r1/REPORT.md) |
| [looks_expansion_design](looks_expansion_design/) | 2026-11-01 | 研究 | 可以评审 | 历史 | [DESIGN.md](looks_expansion_design/DESIGN.md) |
| [looks_g152](looks_g152/) | 2026-11-01 | 研究 | g152 Looks 构建 | 历史 | [REPORT.md](looks_g152/REPORT.md) |
| [lut_convert](lut_convert/) | 2026-10-23 | 研究 | LUT 转换 | 历史 | [REPORT.md](lut_convert/REPORT.md) |
| [review_g154_looks18_r1](review_g154_looks18_r1/) | 2026-11-02 | 复审 | 不能上卡 | 已被后续代数取代 | [REVIEW.md](review_g154_looks18_r1/REVIEW.md) |
| [review_looks_design](review_looks_design/) | 2026-11-01 | 复审 | 修改后再实现 | 已被 [review_looks_design_r2](review_looks_design_r2/) 取代 | [REVIEW.md](review_looks_design/REVIEW.md) |
| [review_looks_design_r2](review_looks_design_r2/) | 2026-11-01 | 复审 | 修改后再实现 | 历史 | [REVIEW.md](review_looks_design_r2/REVIEW.md) |
| [spektrafilm_bake](spektrafilm_bake/) | 2026-11-01 | 研究 | 可以评审 | 历史 | [REPORT.md](spektrafilm_bake/REPORT.md) |
| [vlog_alchemy_eval](vlog_alchemy_eval/) | 2026-11-02 | 研究 | 部分值得 | 历史 | [REPORT.md](vlog_alchemy_eval/REPORT.md) |

### 拟合工具

| 目录 | 日期 | 类型 | 结论 | 状态 | 关键产出 |
| --- | --- | --- | --- | --- | --- |
| [fit_data_relocate_r1](fit_data_relocate_r1/) | 2026-11-02 | 工具 | 已关闭 P1-01 | 历史 | [REPORT.md](fit_data_relocate_r1/REPORT.md) |
| [fit_fast_r1](fit_fast_r1/) | 2026-11-04 | 工具 | 可以交复审：1,530 项质量门通过；整轮提速未形成合格倍数 | OPEN | [REPORT.md](fit_fast_r1/REPORT.md)、[REPORT_round1.md](fit_fast_r1/REPORT_round1.md) |
| [review_fit_fast_r2](review_fit_fast_r2/) | 2026-11-03 | 复审 | 修改后再采用 | 历史 | [REVIEW.md](review_fit_fast_r2/REVIEW.md) |
| [speed_hillclimb](speed_hillclimb/) | 2026-11-01 | 工具 | P1-03 已修；2.83 倍仅为历史测量 | 历史 | [REPORT.md](speed_hillclimb/REPORT.md) |

### 模拟器与测试工具

| 目录 | 日期 | 类型 | 结论 | 状态 | 关键产出 |
| --- | --- | --- | --- | --- | --- |
| [boot_early_sources_r1](boot_early_sources_r1/) | 2026-11-02 | 研究 | OPEN：启动早期来源盘点进行中 | OPEN | [PROGRESS.md](boot_early_sources_r1/PROGRESS.md) |
| [card_engine](card_engine/) | 2026-10-23 | 研究 | 建议小型机身常驻层加卡上通用引擎 | 历史 | [REPORT.md](card_engine/REPORT.md) |
| [cpu_speed_probe](cpu_speed_probe/) | 2026-11-01 | 构建 | 可以交复审 | 历史 | [REPORT.md](cpu_speed_probe/REPORT.md) |
| [cpu_speed_r1](cpu_speed_r1/) | 2026-10-27 | 研究 | 原生 tick 语义是 1 ms，主频仍未用外部时钟校准 | 历史 | [REPORT.md](cpu_speed_r1/REPORT.md) |
| [emulator_batch](emulator_batch/) | 2026-10-31 | 工具 | 可以切换 | 历史 | [REPORT.md](emulator_batch/REPORT.md) |
| [emulator_fast_r1](emulator_fast_r1/) | 2026-11-04 | 工具 | 可交复审 | OPEN | [REPORT.md](emulator_fast_r1/REPORT.md) |
| [emulator_feasibility_r1](emulator_feasibility_r1/) | 2026-10-26 | 工具 | 部分可行：值得做机身启动/菜单仿真，不值得整机含 ISP | 历史 | [REPORT.md](emulator_feasibility_r1/REPORT.md) |
| [emulator_m2](emulator_m2/) | 2026-10-29 | 工具 | 越过 cache 故障，Task 6 已建立 | 已被 [emulator_m2d](emulator_m2d/) 取代 | [REPORT.md](emulator_m2/REPORT.md) |
| [emulator_m2b](emulator_m2b/) | 2026-10-29 | 工具 | M2b 已达成 | 已被 [emulator_m2d](emulator_m2d/) 取代 | [REPORT.md](emulator_m2b/REPORT.md) |
| [emulator_m2c](emulator_m2c/) | 2026-10-29 | 工具 | M2c：达成 | 已被 [emulator_m2d](emulator_m2d/) 取代 | [REPORT.md](emulator_m2c/REPORT.md) |
| [emulator_m2d](emulator_m2d/) | 2026-10-29 | 工具 | M2d：部分 | 历史 | [REPORT.md](emulator_m2d/REPORT.md) |
| [emulator_speed](emulator_speed/) | 2026-10-29 | 工具 | 部分 | 历史 | [REPORT.md](emulator_speed/REPORT.md) |
| [emulator_standby](emulator_standby/) | 2026-11-02 | 工具 | 到达待机 | 历史 | [REPORT.md](emulator_standby/REPORT.md) |
| [engine_lifecycle](engine_lifecycle/) | 2026-10-23 | 研究 | 建议首次打开配方菜单时从 IROM 加载 | 历史 | [REPORT.md](engine_lifecycle/REPORT.md) |
| [freeze_capture](freeze_capture/) | 2026-10-30 | 研究 | 不能排除 | 历史 | [REPORT.md](freeze_capture/REPORT.md) |
| [harness_ccore](harness_ccore/) | 2026-10-31 | 工具 | 无 REPORT，仅有本地产物 | OPEN | [harness_ccore/](harness_ccore/) |
| [harness_speed](harness_speed/) | 2026-10-29 | 工具 | C 测试工具速度 | 历史 | [REPORT.md](harness_speed/REPORT.md) |
| [heap_headroom](heap_headroom/) | 2026-10-29 | 研究 | 堆余量 | 历史 | [REPORT.md](heap_headroom/REPORT.md) |
| [reentry_reachability](reentry_reachability/) | 2026-10-29 | 研究 | 未定 | OPEN | [REPORT.md](reentry_reachability/REPORT.md) |
| [review_cpuprobe](review_cpuprobe/) | 2026-11-01 | 复审 | 不能上卡 | 已被 [review_cpuprobe_r2](review_cpuprobe_r2/) 取代 | [REVIEW.md](review_cpuprobe/REVIEW.md) |
| [review_cpuprobe_r2](review_cpuprobe_r2/) | 2026-11-01 | 复审 | 不能上卡 | 已被后续工作取代 | [REVIEW.md](review_cpuprobe_r2/REVIEW.md) |
| [review_emulator_batch](review_emulator_batch/) | 2026-10-31 | 复审 | 不可以切换 | 已被 [review_emulator_batch_r3](review_emulator_batch_r3/) 取代 | [REVIEW.md](review_emulator_batch/REVIEW.md) |
| [review_emulator_batch_r2](review_emulator_batch_r2/) | 2026-10-31 | 复审 | 不可以切换 | 已被 [review_emulator_batch_r3](review_emulator_batch_r3/) 取代 | [REVIEW.md](review_emulator_batch_r2/REVIEW.md) |
| [review_emulator_batch_r3](review_emulator_batch_r3/) | 2026-10-31 | 复审 | 可以切换 | 历史 | [REVIEW.md](review_emulator_batch_r3/REVIEW.md) |
| [review_emulator_fast_r1](review_emulator_fast_r1/) | 2026-11-03 | 复审 | 不能采用 | 已被 [review_emulator_fast_r4](review_emulator_fast_r4/) 取代 | [REVIEW.md](review_emulator_fast_r1/REVIEW.md) |
| [review_emulator_fast_r2](review_emulator_fast_r2/) | 2026-11-03 | 复审 | 不能采用 | 已被 [review_emulator_fast_r4](review_emulator_fast_r4/) 取代 | [REVIEW.md](review_emulator_fast_r2/REVIEW.md) |
| [review_emulator_fast_r3](review_emulator_fast_r3/) | 2026-11-03 | 复审 | 修改后再采用 | 已被 [review_emulator_fast_r4](review_emulator_fast_r4/) 取代 | [REVIEW.md](review_emulator_fast_r3/REVIEW.md) |
| [review_emulator_fast_r4](review_emulator_fast_r4/) | 2026-11-04 | 复审 | 修改后再采用 | 历史 | [REVIEW.md](review_emulator_fast_r4/REVIEW.md) |
| [review_engine_fix_r1](review_engine_fix_r1/) | 2026-10-24 | 复审 | 不可以。当前 full-r2 不放行；临时 lease 释放失败被忽略，且只读 open 的歧义尚不能保证保留有效旧副本。 | 历史 | [REPORT.md](review_engine_fix_r1/REPORT.md) |
| [review_engine_fix_r2](review_engine_fix_r2/) | 2026-10-24 | 复审 | 不可以 | 历史 | [REPORT.md](review_engine_fix_r2/REPORT.md) |
| [review_harness_c](review_harness_c/) | 2026-10-31 | 复审 | 不可以切换 | 已被 [review_harness_c_r2](review_harness_c_r2/) 取代 | [REVIEW.md](review_harness_c/REVIEW.md) |
| [review_harness_c_r2](review_harness_c_r2/) | 2026-10-31 | 复审 | 不可以切换 | 历史 | [REVIEW.md](review_harness_c_r2/REVIEW.md) |
| [review_harness_c_switch](review_harness_c_switch/) | 2026-11-01 | 复审 | 修改后再采用 | 已被 [review_harness_c_switch_r2](review_harness_c_switch_r2/) 取代 | [REVIEW.md](review_harness_c_switch/REVIEW.md) |
| [review_harness_c_switch_r2](review_harness_c_switch_r2/) | 2026-11-01 | 复审 | 修改后再采用 | 历史 | [REVIEW.md](review_harness_c_switch_r2/REVIEW.md) |
| [stack_headroom](stack_headroom/) | 2026-10-24 | 研究 | 主应用任务栈余量已核实 | 历史 | [REPORT.md](stack_headroom/REPORT.md) |

### Studio

| 目录 | 日期 | 类型 | 结论 | 状态 | 关键产出 |
| --- | --- | --- | --- | --- | --- |
| [review_studio_a1a](review_studio_a1a/) | 2026-11-01 | 复审 | 修改后再提交 | 已被 [review_studio_a1a_r3](review_studio_a1a_r3/) 取代 | [REVIEW.md](review_studio_a1a/REVIEW.md) |
| [review_studio_a1a_r2](review_studio_a1a_r2/) | 2026-11-01 | 复审 | 修改后再提交 | 已被 [review_studio_a1a_r3](review_studio_a1a_r3/) 取代 | [REVIEW.md](review_studio_a1a_r2/REVIEW.md) |
| [review_studio_a1a_r3](review_studio_a1a_r3/) | 2026-11-01 | 复审 | 修改后再提交 | 历史 | [REVIEW.md](review_studio_a1a_r3/REVIEW.md) |
| [review_studio_camera_manager](review_studio_camera_manager/) | 2026-10-31 | 复审 | 修改后再开工 | 历史 | [REVIEW.md](review_studio_camera_manager/REVIEW.md) |
| [review_studio_fix](review_studio_fix/) | 2026-10-30 | 复审 | 可以给用户试用（P0-1、P1-1、P1-2 都已真正关闭；没有 P0、没有 P1。剩下 6 条 P2，都不丢照片，只有边角情形会出小毛病，试用时留意 §2 的 | 历史 | [REVIEW.md](review_studio_fix/REVIEW.md) |
| [review_studio_g152](review_studio_g152/) | 2026-11-02 | 复审 | 修改后再合并 | 历史 | [REVIEW.md](review_studio_g152/REVIEW.md) |
| [review_studio_g156_r1](review_studio_g156_r1/) | 2026-11-04 | 复审 | 修改后再合并 | 已被 [review_studio_g156_r2](review_studio_g156_r2/) 取代 | [REVIEW.md](review_studio_g156_r1/REVIEW.md) |
| [review_studio_g156_r2](review_studio_g156_r2/) | 2026-11-04 | 复审 | 可以合并 | 现行 | [REVIEW.md](review_studio_g156_r2/REVIEW.md) |
| [review_studio_gpu_preview_r1](review_studio_gpu_preview_r1/) | 2026-11-02 | 复审 | 不能合并 | 已被 [review_studio_gpu_preview_r5](review_studio_gpu_preview_r5/) 取代 | [REVIEW.md](review_studio_gpu_preview_r1/REVIEW.md) |
| [review_studio_gpu_preview_r2](review_studio_gpu_preview_r2/) | 2026-11-02 | 复审 | 不能合并 | 已被 [review_studio_gpu_preview_r5](review_studio_gpu_preview_r5/) 取代 | [REVIEW.md](review_studio_gpu_preview_r2/REVIEW.md) |
| [review_studio_gpu_preview_r3](review_studio_gpu_preview_r3/) | 2026-11-03 | 复审 | 不能合并 | 已被 [review_studio_gpu_preview_r5](review_studio_gpu_preview_r5/) 取代 | [REVIEW.md](review_studio_gpu_preview_r3/REVIEW.md) |
| [review_studio_gpu_preview_r4](review_studio_gpu_preview_r4/) | 2026-11-03 | 复审 | 不能合并 | 已被 [review_studio_gpu_preview_r5](review_studio_gpu_preview_r5/) 取代 | [REVIEW.md](review_studio_gpu_preview_r4/REVIEW.md) |
| [review_studio_gpu_preview_r5](review_studio_gpu_preview_r5/) | 2026-11-03 | 复审 | 可以合并 | 现行 | [REVIEW.md](review_studio_gpu_preview_r5/REVIEW.md) |
| [review_studio_hdr](review_studio_hdr/) | 2026-11-01 | 复审 | 修改后再提交 | 历史 | [REVIEW.md](review_studio_hdr/REVIEW.md) |
| [review_studio_lut](review_studio_lut/) | 2026-11-01 | 复审 | 修改后再提交 | 历史 | [REVIEW.md](review_studio_lut/REVIEW.md) |
| [review_studio_m2](review_studio_m2/) | 2026-10-30 | 复审 | 不可以给用户试用（有 1 个 P0：导入出错时界面仍说"可以安全弹出卡了"。修法很小，改完复核后即可试用；其余没发现会丢照片的路径） | 历史 | [REVIEW.md](review_studio_m2/REVIEW.md) |
| [review_studio_v2](review_studio_v2/) | 2026-10-31 | 复审 | 不能交付 | 历史 | [REVIEW.md](review_studio_v2/REVIEW.md) |
| [studio_a1a_r1_fix](studio_a1a_r1_fix/) | 2026-11-01 | 工具 | 无 REPORT，仅修复产物 | 已被 [studio_a1a_r4_fix](studio_a1a_r4_fix/) 取代 | [studio_a1a_r1_fix/](studio_a1a_r1_fix/) |
| [studio_a1a_r2_fix](studio_a1a_r2_fix/) | 2026-11-01 | 工具 | 可以复审 | 已被 [studio_a1a_r4_fix](studio_a1a_r4_fix/) 取代 | [REPORT.md](studio_a1a_r2_fix/REPORT.md) |
| [studio_a1a_r3_fix](studio_a1a_r3_fix/) | 2026-11-01 | 工具 | 可以复核 | 已被 [studio_a1a_r4_fix](studio_a1a_r4_fix/) 取代 | [REPORT.md](studio_a1a_r3_fix/REPORT.md) |
| [studio_a1a_r4_fix](studio_a1a_r4_fix/) | 2026-11-01 | 工具 | 已修好 | 历史 | [REPORT.md](studio_a1a_r4_fix/REPORT.md) |
| [studio_camdata_api](studio_camdata_api/) | 2026-10-30 | 工具 | 可以交复审 | 历史 | [REPORT.md](studio_camdata_api/REPORT.md) |
| [studio_camera_manager](studio_camera_manager/) | 2026-10-31 | 工具 | 可以评审 | 历史 | [DESIGN.md](studio_camera_manager/DESIGN.md) |
| [studio_crop_guides](studio_crop_guides/) | 2026-10-30 | 工具 | 可以交复审 | 历史 | [REPORT.md](studio_crop_guides/REPORT.md) |
| [studio_design](studio_design/) | 2026-10-30 | 工具 | 工作室技术架构与 UX 设计 | 历史 | [ARCHITECTURE.md](studio_design/ARCHITECTURE.md) |
| [studio_engine_e0](studio_engine_e0/) | 2026-10-30 | 工具 | 可以交复审 | 历史 | [REPORT.md](studio_engine_e0/REPORT.md) |
| [studio_fix_review](studio_fix_review/) | 2026-10-30 | 工具 | 可以交复审 | 历史 | [REPORT.md](studio_fix_review/REPORT.md) |
| [studio_g152_r1](studio_g152_r1/) | 2026-11-02 | 工具 | Studio 已加入 152/153 包支持 | 历史 | [REPORT.md](studio_g152_r1/REPORT.md) |
| [studio_g154_g155_r1](studio_g154_g155_r1/) | 2026-11-02 | 工具 | 可以交复审 | 历史 | [REPORT.md](studio_g154_g155_r1/REPORT.md) |
| [studio_gpu_r1](studio_gpu_r1/) | 2026-11-03 | 工具 | 网页预览能做到跟手；推荐 WebGPU | 现行 | [REPORT.md](studio_gpu_r1/REPORT.md) |
| [studio_hdr_fix_r1](studio_hdr_fix_r1/) | 2026-11-01 | 工具 | 可以复审 | 历史 | [REPORT.md](studio_hdr_fix_r1/REPORT.md) |
| [studio_hdr_r1](studio_hdr_r1/) | 2026-11-01 | 工具 | 可以复审 | 历史 | [REPORT.md](studio_hdr_r1/REPORT.md) |
| [studio_integration](studio_integration/) | 2026-10-30 | 工具 | 可以交复审 | 历史 | [REPORT.md](studio_integration/REPORT.md) |
| [studio_lut_ident_r1](studio_lut_ident_r1/) | 2026-11-02 | 工具 | 已修 LUT 声明，可以交复审 | 历史 | [REPORT.md](studio_lut_ident_r1/REPORT.md) |
| [studio_lut_library_r1](studio_lut_library_r1/) | 2026-11-01 | 工具 | 可以复审 | 历史 | [REPORT.md](studio_lut_library_r1/REPORT.md) |
| [studio_lut_s8a](studio_lut_s8a/) | 2026-10-30 | 工具 | 可以交复审 | 历史 | [REPORT.md](studio_lut_s8a/REPORT.md) |
| [studio_m1](studio_m1/) | 2026-10-30 | 工具 | 可以交复审 | 历史 | [REPORT.md](studio_m1/REPORT.md) |
| [studio_m1_web](studio_m1_web/) | 2026-10-30 | 工具 | 可以交复审 | 历史 | [REPORT.md](studio_m1_web/REPORT.md) |
| [studio_m2_web](studio_m2_web/) | 2026-10-30 | 工具 | 可以交复审 | 历史 | [REPORT.md](studio_m2_web/REPORT.md) |
| [studio_onboarding_r1](studio_onboarding_r1/) | 2026-11-01 | 工具 | 可以复审 | 历史 | [REPORT.md](studio_onboarding_r1/REPORT.md) |
| [studio_polish_p2](studio_polish_p2/) | 2026-10-30 | 工具 | 可以交复审 | 历史 | [REPORT.md](studio_polish_p2/REPORT.md) |
| [studio_raw_s4](studio_raw_s4/) | 2026-10-30 | 工具 | 可以交复审 | 历史 | [REPORT.md](studio_raw_s4/REPORT.md) |
| [studio_readiness](studio_readiness/) | 2026-10-30 | 工具 | Level 5，95.7% | 已被 [studio_readiness_r2](studio_readiness_r2/) 取代 | [REPORT.md](studio_readiness/REPORT.md) |
| [studio_readiness_r2](studio_readiness_r2/) | 2026-10-30 | 工具 | 可以交复审 | 历史 | [REPORT.md](studio_readiness_r2/REPORT.md) |
| [studio_realphoto_qa_20261102](studio_realphoto_qa_20261102/) | 2026-11-02 | 工具 | 第 152 代配方文件进不去，照片导入走通 | 历史 | [REPORT.md](studio_realphoto_qa_20261102/REPORT.md) |
| [studio_render_s6](studio_render_s6/) | 2026-10-30 | 工具 | 可以交复审 | 历史 | [REPORT.md](studio_render_s6/REPORT.md) |
| [studio_send_to_camera](studio_send_to_camera/) | 2026-10-31 | 工具 | 有阻塞：g139 用户条目存不了自起名 | 历史 | [DESIGN.md](studio_send_to_camera/DESIGN.md) |
| [studio_ui_r1](studio_ui_r1/) | 2026-11-02 | 工具 | 重做整套界面，17 个界面截图 | 历史 | [REPORT.md](studio_ui_r1/REPORT.md) |
| [studio_v2](studio_v2/) | 2026-10-30 | 工具 | PRD 与文案合同 | 历史 | [PRD.md](studio_v2/PRD.md) |
| [verify_studio_a1a_r2](verify_studio_a1a_r2/) | 2026-11-01 | 复审 | 无 REPORT，仅复审测试 | 历史 | [verify_studio_a1a_r2/](verify_studio_a1a_r2/) |
| [verify_studio_a1a_r3](verify_studio_a1a_r3/) | 2026-11-01 | 复审 | 无 REPORT，仅复审测试 | 历史 | [verify_studio_a1a_r3/](verify_studio_a1a_r3/) |
| [verify_studio_hdr](verify_studio_hdr/) | 2026-11-01 | 复审 | 无 REPORT，仅探针脚本 | 历史 | [verify_studio_hdr/](verify_studio_hdr/) |

### 探针（含峰值）

| 目录 | 日期 | 类型 | 结论 | 状态 | 关键产出 |
| --- | --- | --- | --- | --- | --- |
| [body_rpc8_probe](body_rpc8_probe/) | 2026-10-16 | 研究 | 机身经 RPC 写模块 RAM 的静态审计 | 历史 | [REPORT.md](body_rpc8_probe/REPORT.md) |
| [focus_assist](focus_assist/) | 2026-10-16 | 研究 | 可能可行，尚未证实白色改红色常量 | 历史 | [REPORT.md](focus_assist/REPORT.md) |
| [gate_probe](gate_probe/) | 2026-10-19 | 构建 | 门控输入采样探针设计 | 历史 | [REPORT.md](gate_probe/REPORT.md) |
| [peaking_color](peaking_color/) | 2026-10-23 | 研究 | 峰值染色：尚无可交付的彩色描边 | 历史 | [REPORT.md](peaking_color/REPORT.md) |
| [peaking_leads_r2](peaking_leads_r2/) | 2026-10-30 | 研究 | 峰值线索第二轮 | 已被 [peaking_color](peaking_color/) 取代 | [REPORT.md](peaking_leads_r2/REPORT.md) |
| [peaking_probe](peaking_probe/) | 2026-10-22 | 研究 | 峰值改色探针操作说明 | 已被 [peaking_color](peaking_color/) 取代 | [操作说明.md](peaking_probe/操作说明.md) |
| [peaking_probe_dat](peaking_probe_dat/) | 2026-10-30 | 研究 | 峰值探针 DAT | 历史 | [REPORT.md](peaking_probe_dat/REPORT.md) |
| [probe_mcm_r1](probe_mcm_r1/) | 2026-10-27 | 研究 | 交付只读候选 DAT，不具备一次上机测清四项的完整能力 | 历史 | [REPORT.md](probe_mcm_r1/REPORT.md) |
| [probe_pack_r1](probe_pack_r1/) | 2026-11-03 | 构建 | 可以交复审 | 已被 [probe_pack_r3](probe_pack_r3/) 取代 | [REPORT.md](probe_pack_r1/REPORT.md) |
| [probe_pack_r2](probe_pack_r2/) | 2026-11-03 | 构建 | 可以交复审 | 已被 [probe_pack_r3](probe_pack_r3/) 取代 | [PROGRESS.md](probe_pack_r2/PROGRESS.md)、[REPORT_PROBE2.md](probe_pack_r2/REPORT_PROBE2.md) |
| [probe_pack_r3](probe_pack_r3/) | 2026-11-04 | 构建 | 可以交复审 | 现行 | [PROGRESS.md](probe_pack_r3/PROGRESS.md)、[REPORT_PROBE3.md](probe_pack_r3/REPORT_PROBE3.md) |
| [review_probe2_r1](review_probe2_r1/) | 2026-11-03 | 复审 | 可以上卡 | 历史 | [REVIEW.md](review_probe2_r1/REVIEW.md) |
| [review_probe3_r1](review_probe3_r1/) | 2026-11-03 | 复审 | 可以上卡 | 现行 | [REVIEW.md](review_probe3_r1/REVIEW.md) |
| [review_probe_p1](review_probe_p1/) | 2026-10-30 | 复审 | 不可以上测试卡 | 历史 | [REVIEW.md](review_probe_p1/REVIEW.md) |
| [review_probe_pack_r1](review_probe_pack_r1/) | 2026-11-02 | 复审 | 可以上卡 | 历史 | [REVIEW.md](review_probe_pack_r1/REVIEW.md) |

### 机身、常驻、启动与 v3.x / v4

| 目录 | 日期 | 类型 | 结论 | 状态 | 关键产出 |
| --- | --- | --- | --- | --- | --- |
| [blink_state_50mm](blink_state_50mm/) | 2026-10-25 | 现场分析 | 机身在 50mm 启动或通信处停住，不能据此判定 MAIN 已损坏 | 历史 | [REPORT.md](blink_state_50mm/REPORT.md) |
| [body_lut](body_lut/) | 2026-10-21 | 研究 | 静态可行性研究，主图 LUT 路径未闭合 | 已被 [body_lut_r2](body_lut_r2/) 取代 | [REPORT.md](body_lut/REPORT.md) |
| [body_lut_r2](body_lut_r2/) | 2026-10-26 | 研究 | 原理可行，当时主 JPEG 像素探针仍阻塞 | 历史 | [REPORT.md](body_lut_r2/REPORT.md) |
| [body_next_plan](body_next_plan/) | 2026-10-31 | 研究 | 可以评审 | 历史 | [PLAN.md](body_next_plan/PLAN.md) |
| [body_next_steps](body_next_steps/) | 2026-11-01 | 研究 | 可以评审 | 历史 | [REPORT.md](body_next_steps/REPORT.md) |
| [body_v39](body_v39/) | 2026-11-01 | 研究 | 可以交复审 | 历史 | [REPORT.md](body_v39/REPORT.md) |
| [body_v4_archB](body_v4_archB/) | 2026-10-28 | 研究 | 永久 RAM 与早期载入屏障仍 OPEN | OPEN | [REPORT.md](body_v4_archB/REPORT.md) |
| [body_v4_design](body_v4_design/) | 2026-11-01 | 研究 | 有条件可行：薄常驻名义预算有余量，尚未链接证明 | 现行 | [REPORT.md](body_v4_design/REPORT.md) |
| [body_v4_storage](body_v4_storage/) | 2026-10-28 | 研究 | 存储桥未闭合；三方报告结论不一致，见 SYNTHESIS | OPEN | [SYNTHESIS.md](body_v4_storage/SYNTHESIS.md) |
| [body_v4_w0](body_v4_w0/) | 2026-10-28 | 研究 | 架构 A 未通过；架构 B 最小窗口通过 | 历史 | [REPORT.md](body_v4_w0/REPORT.md) |
| [boot_hang_50mm](boot_hang_50mm/) | 2026-10-25 | 现场分析 | 不能把 50mm 黑屏归因于启动加载 IROM 引擎 | 历史 | [REPORT.md](boot_hang_50mm/REPORT.md) |
| [boot_hang_v34c](boot_hang_v34c/) | 2026-10-26 | 现场分析 | 静态证据不能锁定根因，交付实验方案 | 历史 | [REPORT.md](boot_hang_v34c/REPORT.md) |
| [boot_hang_v35](boot_hang_v35/) | 2026-10-26 | 现场分析 | STOP_AFTER_DESIGN，不构建 v3.5 | 历史 | [REPORT.md](boot_hang_v35/REPORT.md) |
| [boot_inert_v34](boot_inert_v34/) | 2026-10-25 | 研究 | v3.4 应默认走原厂启动，明确进入 Image Settings 后再消费 token | 历史 | [REPORT.md](boot_inert_v34/REPORT.md) |
| [deep_guard](deep_guard/) | 2026-10-16 | 研究 | NOT_CLOSEABLE_STATICALLY | 历史 | [REPORT.md](deep_guard/REPORT.md) |
| [deep_select_fix](deep_select_fix/) | 2026-10-16 | 研究 | 选择全灭是门通过之后预览没发出 | 历史 | [REPORT.md](deep_select_fix/REPORT.md) |
| [emptystack_v38](emptystack_v38/) | 2026-10-30 | 构建 | 可以交复审 | 历史 | [REPORT.md](emptystack_v38/REPORT.md) |
| [irom_storage](irom_storage/) | 2026-10-23 | 研究 | IROM 存储 | 历史 | [REPORT.md](irom_storage/REPORT.md) |
| [persist_recipe](persist_recipe/) | 2026-10-30 | 研究 | 配方持久化 | 已被 [persist_recipe_r2](persist_recipe_r2/) 取代 | [REPORT.md](persist_recipe/REPORT.md) |
| [persist_recipe_r2](persist_recipe_r2/) | 2026-10-30 | 研究 | 配方持久化第二轮 | 历史 | [REPORT.md](persist_recipe_r2/REPORT.md) |
| [poweron_autoapply](poweron_autoapply/) | 2026-11-01 | 研究 | 需要先探测 | OPEN | [DESIGN.md](poweron_autoapply/DESIGN.md) |
| [poweron_lite](poweron_lite/) | 2026-11-02 | 研究 | OPEN：开机轻量套用进行中 | OPEN | [PROGRESS.md](poweron_lite/PROGRESS.md) |
| [redisplay_fix](redisplay_fix/) | 2026-10-29 | 构建 | 已修好载入问题，主机三单元通过，已写卡 B 等实拍 | 历史 | [REPORT.md](redisplay_fix/REPORT.md) |
| [review_body_plan](review_body_plan/) | 2026-10-31 | 复审 | 修改后再开工 | 历史 | [REVIEW.md](review_body_plan/REVIEW.md) |
| [review_body_reclaim](review_body_reclaim/) | 2026-11-01 | 复审 | 修改后再实现 | 已被 [review_body_reclaim_r2](review_body_reclaim_r2/) 取代 | [REVIEW.md](review_body_reclaim/REVIEW.md) |
| [review_body_reclaim_r2](review_body_reclaim_r2/) | 2026-11-01 | 复审 | 可以实现 | 历史 | [REVIEW.md](review_body_reclaim_r2/REVIEW.md) |
| [review_body_v39](review_body_v39/) | 2026-11-01 | 复审 | 不能刷机 | 已被后续工作取代 | [REVIEW.md](review_body_v39/REVIEW.md) |
| [review_fixes_design](review_fixes_design/) | 2026-11-01 | 复审 | 修改后再实现 | 历史 | [REVIEW.md](review_fixes_design/REVIEW.md) |
| [review_flash_v2](review_flash_v2/) | 2026-10-24 | 复审 | 不可以刷 | 已被 [review_flash_v32](review_flash_v32/) 取代 | [REPORT.md](review_flash_v2/REPORT.md) |
| [review_flash_v3](review_flash_v3/) | 2026-10-24 | 复审 | 不可以刷 | 已被 [review_flash_v32](review_flash_v32/) 取代 | [REPORT.md](review_flash_v3/REPORT.md) |
| [review_flash_v31](review_flash_v31/) | 2026-10-24 | 复审 | 不可以刷 | 已被 [review_flash_v32](review_flash_v32/) 取代 | [REPORT.md](review_flash_v31/REPORT.md) |
| [review_flash_v32](review_flash_v32/) | 2026-10-24 | 复审 | 可以刷 | 已被后续机身取代 | [REPORT.md](review_flash_v32/REPORT.md) |
| [review_flash_v33](review_flash_v33/) | 2026-10-25 | 复审 | 不可以刷机 | 已被后续机身取代 | [REPORT.md](review_flash_v33/REPORT.md) |
| [review_flash_v34c](review_flash_v34c/) | 2026-10-25 | 复审 | 可以刷机 | 已被后续机身取代 | [REPORT.md](review_flash_v34c/REPORT.md) |
| [review_full_r4](review_full_r4/) | 2026-10-25 | 复审 | 不可以上卡 | 已被 [review_full_r7](review_full_r7/) 取代 | [REPORT.md](review_full_r4/REPORT.md) |
| [review_full_r6](review_full_r6/) | 2026-10-25 | 复审 | 不可以上卡 | 已被 [review_full_r7](review_full_r7/) 取代 | [REPORT.md](review_full_r6/REPORT.md) |
| [review_full_r7](review_full_r7/) | 2026-10-25 | 复审 | 不可以上卡 | 已被后续机身取代 | [REPORT.md](review_full_r7/REPORT.md) |
| [review_lut_p0](review_lut_p0/) | 2026-10-26 | 复审 | 不可以上卡 | 已被 [review_lut_p0_r2](review_lut_p0_r2/) 取代 | [REPORT.md](review_lut_p0/REPORT.md) |
| [review_lut_p0_r2](review_lut_p0_r2/) | 2026-10-26 | 复审 | 不可以上卡 | 历史 | [REPORT.md](review_lut_p0_r2/REPORT.md) |
| [review_v310_body_r1](review_v310_body_r1/) | 2026-11-03 | 复审 | 可以刷 | 现行 | [REVIEW.md](review_v310_body_r1/REVIEW.md) |
| [review_v32_diag](review_v32_diag/) | 2026-10-24 | 复审 | 可以用 | 已被后续机身取代 | [REPORT.md](review_v32_diag/REPORT.md) |
| [review_v35_body](review_v35_body/) | 2026-10-27 | 复审 | 不可以上卡。仅针对 BODY。 | 已被后续机身取代 | [REVIEW.md](review_v35_body/REVIEW.md) |
| [review_v35_container](review_v35_container/) | 2026-10-27 | 复审 | 不可以上卡。 | 已被后续机身取代 | [REVIEW.md](review_v35_container/REVIEW.md) |
| [review_v36_body](review_v36_body/) | 2026-10-27 | 复审 | 可以上卡。仅针对本次 v3.6 BODY。 | 已被后续机身取代 | [REVIEW.md](review_v36_body/REVIEW.md) |
| [review_v37_flash](review_v37_flash/) | 2026-10-30 | 复审 | 不可以刷机 | 已被后续机身取代 | [REVIEW.md](review_v37_flash/REVIEW.md) |
| [review_v38_g137](review_v38_g137/) | 2026-10-30 | 复审 | 可以刷机 | 已被后续机身取代 | [REVIEW.md](review_v38_g137/REVIEW.md) |
| [review_v4_design](review_v4_design/) | 2026-11-01 | 复审 | 修改后再实现 | 已被 [review_v4_design_r4](review_v4_design_r4/) 取代 | [REVIEW.md](review_v4_design/REVIEW.md) |
| [review_v4_design_r2](review_v4_design_r2/) | 2026-11-01 | 复审 | 修改后再实现 | 已被 [review_v4_design_r4](review_v4_design_r4/) 取代 | [REVIEW.md](review_v4_design_r2/REVIEW.md) |
| [review_v4_design_r3](review_v4_design_r3/) | 2026-11-01 | 复审 | 修改后再实现 | 已被 [review_v4_design_r4](review_v4_design_r4/) 取代 | [REVIEW.md](review_v4_design_r3/REVIEW.md) |
| [review_v4_design_r4](review_v4_design_r4/) | 2026-11-01 | 复审 | 可以实现（探测后） | 现行 | [REVIEW.md](review_v4_design_r4/REVIEW.md) |
| [switch_residue](switch_residue/) | 2026-10-23 | 构建 | 新候选待独立复审，尚未写卡 | 历史 | [REPORT.md](switch_residue/REPORT.md) |
| [user_storage_r1](user_storage_r1/) | 2026-10-28 | 研究 | 推荐卡上预建文件，当前保留只读 | 已被 [user_storage_r3](user_storage_r3/) 取代 | [REPORT.md](user_storage_r1/REPORT.md) |
| [user_storage_r2](user_storage_r2/) | 2026-10-28 | 研究 | 还不行：原厂存储排他门禁未闭合 | 已被 [user_storage_r3](user_storage_r3/) 取代 | [REPORT.md](user_storage_r2/REPORT.md) |
| [user_storage_r3](user_storage_r3/) | 2026-10-28 | 研究 | 只改 DAT 不可行 | 历史 | [REPORT.md](user_storage_r3/REPORT.md) |
| [v310_body](v310_body/) | 2026-11-02 | 构建 | 可以交复审 | 现行 | [REPORT.md](v310_body/REPORT.md) |
| [v310_resident](v310_resident/) | 2026-11-02 | 构建 | 放不下 | OPEN | [REPORT.md](v310_resident/REPORT.md)、[REPORT_R2.md](v310_resident/REPORT_R2.md) |
| [v310_window](v310_window/) | 2026-11-02 | 构建 | 需机主决定 | OPEN | [REPORT.md](v310_window/REPORT.md) |
| [v39_g153](v39_g153/) | 2026-11-04 | 构建 | 可以交复审 | 历史 | [REPORT.md](v39_g153/REPORT.md) |

### 配方代数与诊断 DAT

| 目录 | 日期 | 类型 | 结论 | 状态 | 关键产出 |
| --- | --- | --- | --- | --- | --- |
| [diag147](diag147/) | 2026-10-31 | 构建 | 可以交复审 | 历史 | [REPORT.md](diag147/REPORT.md) |
| [diag_dat_v1](diag_dat_v1/) | 2026-10-28 | 构建 | 可以交复审 | 已被 [diag_v4p](diag_v4p/) 取代 | [REPORT.md](diag_dat_v1/REPORT.md) |
| [diag_dat_v2](diag_dat_v2/) | 2026-10-29 | 构建 | 可以交复审 | 已被 [diag_v4p](diag_v4p/) 取代 | [REPORT.md](diag_dat_v2/REPORT.md)、[REPORT_r1.md](diag_dat_v2/REPORT_r1.md)、[REPORT_r2.md](diag_dat_v2/REPORT_r2.md) |
| [diag_dat_v21](diag_dat_v21/) | 2026-10-29 | 构建 | 有缺陷 | 已被 [diag_v4p](diag_v4p/) 取代 | [REPORT.md](diag_dat_v21/REPORT.md) |
| [diag_dat_v3](diag_dat_v3/) | 2026-10-29 | 构建 | 记录每次打开菜单，查拍后首次 ADJ 原厂菜单 | 已被 [diag_v4p](diag_v4p/) 取代 | [README.md](diag_dat_v3/README.md) |
| [diag_dat_v37](diag_dat_v37/) | 2026-10-30 | 构建 | 可以用（主机验收通过；未上真机） | 已被 [diag_v4p](diag_v4p/) 取代 | [REPORT.md](diag_dat_v37/REPORT.md) |
| [diag_v4p](diag_v4p/) | 2026-11-02 | 构建 | 有缺陷 | 历史 | [REPORT.md](diag_v4p/REPORT.md) |
| [g121_field_fix](g121_field_fix/) | 2026-10-28 | 构建 | 候选已产出，完整验收未通过 | 已被 [g156](g156/) 取代 | [REPORT.md](g121_field_fix/REPORT.md) |
| [g122_hint_design](g122_hint_design/) | 2026-10-28 | 构建 | 有条件可行 | 已被 [g156](g156/) 取代 | [REPORT.md](g122_hint_design/REPORT.md) |
| [g122_keep_list](g122_keep_list/) | 2026-10-28 | 构建 | 已产出，完整模型验收 INCOMPLETE | 已被 [g156](g156/) 取代 | [REPORT.md](g122_keep_list/REPORT.md) |
| [g123_fix](g123_fix/) | 2026-10-28 | 构建 | 可以交复审 | 已被 [g156](g156/) 取代 | [REPORT.md](g123_fix/REPORT.md) |
| [g124_ui_v2](g124_ui_v2/) | 2026-10-28 | 构建 | 可以交复审 | 已被 [g156](g156/) 取代 | [REPORT.md](g124_ui_v2/REPORT.md) |
| [g126_fix](g126_fix/) | 2026-10-29 | 构建 | 可以交复审 | 已被 [g156](g156/) 取代 | [REPORT.md](g126_fix/REPORT.md) |
| [g127_fix](g127_fix/) | 2026-10-29 | 构建 | 有缺陷 | 已被 [g156](g156/) 取代 | [REPORT.md](g127_fix/REPORT.md) |
| [g129_knobs](g129_knobs/) | 2026-10-29 | 构建 | 有缺陷 | 已被 [g156](g156/) 取代 | [REPORT.md](g129_knobs/REPORT.md) |
| [g129_safety_triage](g129_safety_triage/) | 2026-10-30 | 构建 | 三条均非产品缺陷 | 历史 | [REPORT.md](g129_safety_triage/REPORT.md) |
| [g130_fix](g130_fix/) | 2026-10-29 | 构建 | 有缺陷 | 已被 [g156](g156/) 取代 | [REPORT.md](g130_fix/REPORT.md) |
| [g131_merge](g131_merge/) | 2026-10-29 | 构建 | 有缺陷 | 已被 [g156](g156/) 取代 | [REPORT.md](g131_merge/REPORT.md) |
| [g135_v37](g135_v37/) | 2026-10-30 | 构建 | 可以交复审 | 已被 [g156](g156/) 取代 | [REPORT.md](g135_v37/REPORT.md) |
| [g138_persist](g138_persist/) | 2026-10-31 | 构建 | 可以交复审 | 已被 [g156](g156/) 取代 | [REPORT.md](g138_persist/REPORT.md) |
| [g139_fix](g139_fix/) | 2026-10-31 | 构建 | 可以交复审 | 已被 [g156](g156/) 取代 | [REPORT.md](g139_fix/REPORT.md) |
| [g139m](g139m/) | 2026-11-01 | 构建 | 可以交复审 | 已被 [g156](g156/) 取代 | [REPORT.md](g139m/REPORT.md) |
| [g150](g150/) | 2026-11-01 | 构建 | 可以交复审 | 已被 [g156](g156/) 取代 | [REPORT.md](g150/REPORT.md) |
| [g151_design](g151_design/) | 2026-11-01 | 构建 | 可以评审 | 已被 [g156](g156/) 取代 | [DESIGN.md](g151_design/DESIGN.md) |
| [g154](g154/) | 2026-11-02 | 构建 | 可以交复审 | 已被 [g156](g156/) 取代 | [REPORT.md](g154/REPORT.md) |
| [g154_looks_r1](g154_looks_r1/) | 2026-11-02 | 构建 | 可以交复审，结论限电脑构建，尚未上卡 | 已被 [g156](g156/) 取代 | [REPORT.md](g154_looks_r1/REPORT.md) |
| [g155](g155/) | 2026-11-02 | 构建 | 可以交复审 | 已被 [g156](g156/) 取代 | [REPORT.md](g155/REPORT.md) |
| [g156](g156/) | 2026-11-04 | 构建 | 可以交复审 | 现行 | [REPORT.md](g156/REPORT.md) |
| [g157](g157/) | 2026-11-04 | 构建 | OPEN：构建中，无 REPORT；包清单状态 ACCEPTANCE_PENDING | OPEN | [g157/](g157/) |
| [stage2a_deep_isp](stage2a_deep_isp/) | 2026-10-16 | 构建 | UI 根因已修，Deep 目标写入仍禁用 | 已被 [stage2b_deep_select_fix](stage2b_deep_select_fix/) 取代 | [REPORT.md](stage2a_deep_isp/REPORT.md) |
| [stage2b_deep_select_fix](stage2b_deep_select_fix/) | 2026-10-16 | 构建 | 合法 DEEPISP 下 16 槽并非同一条提前返回 | 已被 [stage2c_category_gate](stage2c_category_gate/) 取代 | [REPORT.md](stage2b_deep_select_fix/REPORT.md) |
| [stage2c_category_gate](stage2c_category_gate/) | 2026-10-19 | 构建 | 配方页能开但套用被 acquire 门挡住 | 已被 [stage2d_phase1](stage2d_phase1/) 取代 | [REPORT.md](stage2c_category_gate/REPORT.md) |
| [stage2d_phase1](stage2d_phase1/) | 2026-10-19 | 构建 | 已构建未上机 | 已被 [stage2e](stage2e/) 取代 | [REPORT.md](stage2d_phase1/REPORT.md) |
| [stage2d_verification](stage2d_verification/) | 2026-10-19 | 构建 | 01/02 相对 04 的明暗就是装进去的曲线 | 已被后续阶段取代 | [REPORT.md](stage2d_verification/REPORT.md) |
| [stage2e](stage2e/) | 2026-10-19 | 构建 | 已构建未上机 | 已被 [stage2f](stage2f/) 取代 | [REPORT.md](stage2e/REPORT.md) |
| [stage2e_verification](stage2e_verification/) | 2026-10-19 | 构建 | 曲线落地，扇区顺序已标定，节点与满权重增益未完成 | 已被后续阶段取代 | [REPORT.md](stage2e_verification/REPORT.md) |
| [stage2f](stage2f/) | 2026-10-19 | 构建 | 已构建未上机 | 已被 [stage2g](stage2g/) 取代 | [REPORT.md](stage2f/REPORT.md) |
| [stage2f_design](stage2f_design/) | 2026-10-19 | 构建 | 空闲区/扩展设计 | 已被后续阶段取代 | [REPORT.md](stage2f_design/REPORT.md) |
| [stage2g](stage2g/) | 2026-10-19 | 构建 | 已构建未上机 | 已被 [stage2h](stage2h/) 取代 | [REPORT.md](stage2g/REPORT.md) |
| [stage2h](stage2h/) | 2026-10-20 | 构建 | 已构建未上机 | 已被 [stage2i](stage2i/) 取代 | [REPORT.md](stage2h/REPORT.md) |
| [stage2i](stage2i/) | 2026-10-20 | 构建 | 已构建未上机 | 已被 [stage2j](stage2j/) 取代 | [REPORT.md](stage2i/REPORT.md) |
| [stage2j](stage2j/) | 2026-10-20 | 构建 | 已构建、已验证、报告写未上机（随后有写卡记录） | 已被后续阶段取代 | [REPORT.md](stage2j/REPORT.md) |
| [stage2k_design](stage2k_design/) | 2026-10-20 | 构建 | P0 自检固件设计 | 已被后续阶段取代 | [REPORT.md](stage2k_design/REPORT.md) |
| [stage2k_p0](stage2k_p0/) | 2026-10-21 | 构建 | 无 REPORT；有写卡记录 | 已被后续阶段取代 | [stage2k_p0/](stage2k_p0/) |
| [stage2k_v2_design](stage2k_v2_design/) | 2026-10-21 | 构建 | P0 v2 设计 | 已被后续阶段取代 | [REPORT.md](stage2k_v2_design/REPORT.md) |
| [stage2l_leica_0708](stage2l_leica_0708/) | 2026-10-24 | 构建 | Leica 07/08 表三项验证通过 | 已被后续阶段取代 | [REPORT.md](stage2l_leica_0708/REPORT.md) |

### 现场分析与照片会话

| 目录 | 日期 | 类型 | 结论 | 状态 | 关键产出 |
| --- | --- | --- | --- | --- | --- |
| [chart_session_20261024](chart_session_20261024/) | 2026-10-24 | 现场分析 | 选 (a)：本批测量放宽后可用，不必因摩尔纹标记重拍 | 历史 | [REPORT.md](chart_session_20261024/REPORT.md) |
| [chart_v2](chart_v2/) | 2026-10-23 | 研究 | 6 页 Display P3 色卡已就绪，尚无本版实拍验收 | 历史 | [REPORT.md](chart_v2/REPORT.md) |
| [diag_v4p_mount_20261102](diag_v4p_mount_20261102/) | 2026-11-02 | 现场分析 | 可用。两段录像各 37 页齐全 | 历史 | [REPORT.md](diag_v4p_mount_20261102/REPORT.md) |
| [field_gate_r1](field_gate_r1/) | 2026-11-04 | 现场分析 | C 的原厂列表回退尚未定位 | OPEN | [REPORT.md](field_gate_r1/REPORT.md) |
| [g156_field_issues_r1](g156_field_issues_r1/) | 2026-11-04 | 现场分析 | Q1 最可能是 BOOT 模式许可过窄；朋友整表消失尚未定位 | OPEN | [REPORT.md](g156_field_issues_r1/REPORT.md) |
| [gen115_field_r1](gen115_field_r1/) | 2026-10-26 | 现场分析 | 01/02 没有以完整配方进入成片 | 历史 | [REPORT.md](gen115_field_r1/REPORT.md) |
| [library_28mm_r1](library_28mm_r1/) | 2026-11-04 | 现场分析 | 224 对 28mm stock-04 可用 | 历史 | [REPORT.md](library_28mm_r1/REPORT.md) |
| [mount_g150_field](mount_g150_field/) | 2026-11-01 | 现场分析 | g150 MOUNT 现场 | 历史 | [REPORT.md](mount_g150_field/REPORT.md) |
| [noon_sweep_r1](noon_sweep_r1/) | 2026-11-04 | 现场分析 | 可以接照片；中午色卡与屏幕页分析 | 现行 | [REPORT_binary-intake.md](noon_sweep_r1/REPORT_binary-intake.md)、[REPORT_historic-screen.md](noon_sweep_r1/REPORT_historic-screen.md)、[REPORT_noon-20261104-r2.md](noon_sweep_r1/REPORT_noon-20261104-r2.md) |
| [recipe_iso_unit_drift](recipe_iso_unit_drift/) | 2026-10-31 | 研究 | 可以评审 | 历史 | [REPORT.md](recipe_iso_unit_drift/REPORT.md) |
| [recipe_tag_r1](recipe_tag_r1/) | 2026-11-02 | 研究 | 建议以后逐张写入拍摄标记 | 历史 | [REPORT.md](recipe_tag_r1/REPORT.md) |

### 界面、旋钮与其他玩法

| 目录 | 日期 | 类型 | 结论 | 状态 | 关键产出 |
| --- | --- | --- | --- | --- | --- |
| [g140_entries_design](g140_entries_design/) | 2026-10-31 | 构建 | 可以评审 | 已被 [g156](g156/) 取代 | [DESIGN.md](g140_entries_design/DESIGN.md) |
| [hdr_gainmap](hdr_gainmap/) | 2026-11-01 | 研究 | HDR gain map 原型 | 历史 | [REPORT.md](hdr_gainmap/REPORT.md) |
| [inbody_xpan_halfframe](inbody_xpan_halfframe/) | 2026-11-01 | 研究 | 机内半幅/XPan 相关 | 历史 | [REPORT.md](inbody_xpan_halfframe/REPORT.md) |
| [knobs_v2_engine_design](knobs_v2_engine_design/) | 2026-10-29 | 研究 | 可以实现 | 历史 | [DESIGN.md](knobs_v2_engine_design/DESIGN.md) |
| [knobs_v2_r1](knobs_v2_r1/) | 2026-10-28 | 研究 | 旋钮 v2 第一轮 | 历史 | [REPORT.md](knobs_v2_r1/REPORT.md) |
| [knobs_v2_r2](knobs_v2_r2/) | 2026-10-28 | 研究 | 旋钮 v2 第二轮 | 历史 | [REPORT.md](knobs_v2_r2/REPORT.md) |
| [kv2_data_ui](kv2_data_ui/) | 2026-10-29 | 研究 | knobs v2 数据与界面 | 历史 | [REPORT.md](kv2_data_ui/REPORT.md) |
| [kv2_math](kv2_math/) | 2026-10-29 | 研究 | knobs v2 计算 | 历史 | [REPORT.md](kv2_math/REPORT.md) |
| [module_adapt](module_adapt/) | 2026-11-04 | 研究 | 多模块适配 | 历史 | [REPORT.md](module_adapt/REPORT.md) |
| [multi_module](multi_module/) | 2026-10-23 | 研究 | 三模块 | 历史 | [REPORT.md](multi_module/REPORT.md) |
| [myrec_v2_design](myrec_v2_design/) | 2026-10-30 | 研究 | 可以实现 | 历史 | [DESIGN.md](myrec_v2_design/DESIGN.md) |
| [panel_keys_b](panel_keys_b/) | 2026-10-24 | 研究 | 面板按键 | 历史 | [REPORT.md](panel_keys_b/REPORT.md) |
| [r28_bank_design](r28_bank_design/) | 2026-10-26 | 研究 | 可以只更新 DAT，不需要重刷机身 | 历史 | [REPORT.md](r28_bank_design/REPORT.md) |
| [r28_first_open_r1](r28_first_open_r1/) | 2026-10-27 | 研究 | 仅改配方包不能让 28mm 冷开首次自动显示 8 行 | 历史 | [REPORT.md](r28_first_open_r1/REPORT.md) |
| [review_publish_v114](review_publish_v114/) | 2026-10-26 | 复审 | 可以上卡 | 历史 | [REPORT.md](review_publish_v114/REPORT.md) |
| [review_r28_v115](review_r28_v115/) | 2026-10-26 | 复审 | 不可以上卡 | 历史 | [REPORT.md](review_r28_v115/REPORT.md) |
| [review_stage2l_28mm](review_stage2l_28mm/) | 2026-10-26 | 复审 | 可以上卡 | 历史 | [REPORT.md](review_stage2l_28mm/REPORT.md) |
| [review_stage2l_mount](review_stage2l_mount/) | 2026-10-24 | 复审 | 修改后可以刷 | 历史 | [REPORT.md](review_stage2l_mount/REPORT.md) |
| [three_module_audit_r1](three_module_audit_r1/) | 2026-10-27 | 研究 | 三单元八槽已齐，28mm 标定不足 | 历史 | [REPORT.md](three_module_audit_r1/REPORT.md) |
| [tracer_design](tracer_design/) | 2026-10-28 | 研究 | 部分可行；推荐只用屏幕导出 | 历史 | [DESIGN.md](tracer_design/DESIGN.md) |
| [trend_ideas](trend_ideas/) | 2026-10-31 | 研究 | 可以评审 | 历史 | [REPORT.md](trend_ideas/REPORT.md) |
| [tweak_panel_ui](tweak_panel_ui/) | 2026-10-23 | 研究 | 建议复用 Fn2 打开微调面板 | 历史 | [REPORT.md](tweak_panel_ui/REPORT.md) |
| [ui_refs](ui_refs/) | 2026-10-28 | 研究 | 仅一张参考图，无报告 | 历史 | [ui_refs/](ui_refs/) |
| [ui_v2_design](ui_v2_design/) | 2026-10-30 | 研究 | 配方 v2 界面设计 | 历史 | [DESIGN.md](ui_v2_design/DESIGN.md) |
| [unit28_stock](unit28_stock/) | 2026-10-31 | 构建 | 可以交复审 | 历史 | [REPORT.md](unit28_stock/REPORT.md)、[REPORT-r1-g142.md](unit28_stock/REPORT-r1-g142.md)、[REPORT-r2-g143.md](unit28_stock/REPORT-r2-g143.md) |
| [ux_preview_dot_r1](ux_preview_dot_r1/) | 2026-10-27 | 研究 | 两项 UX 在 native harness 验证，离线候选 | 已被 [ux_preview_dot_r5](ux_preview_dot_r5/) 取代 | [REPORT.md](ux_preview_dot_r1/REPORT.md) |
| [ux_preview_dot_r2](ux_preview_dot_r2/) | 2026-10-27 | 研究 | P1-01 已修，持续断链仍不能保证九行收敛 | 已被 [ux_preview_dot_r5](ux_preview_dot_r5/) 取代 | [REPORT.md](ux_preview_dot_r2/REPORT.md) |
| [ux_preview_dot_r3](ux_preview_dot_r3/) | 2026-10-27 | 研究 | 停止构建，未产出通过验收的 gen 120 | 已被 [ux_preview_dot_r5](ux_preview_dot_r5/) 取代 | [REPORT.md](ux_preview_dot_r3/REPORT.md) |
| [ux_preview_dot_r4](ux_preview_dot_r4/) | 2026-10-27 | 研究 | 停止实施，未产出 gen 120 候选 | 已被 [ux_preview_dot_r5](ux_preview_dot_r5/) 取代 | [REPORT.md](ux_preview_dot_r4/REPORT.md) |
| [ux_preview_dot_r5](ux_preview_dot_r5/) | 2026-10-28 | 研究 | 未通过交付验收；已产出 gen 120b 候选 | 历史 | [REPORT.md](ux_preview_dot_r5/REPORT.md) |
| [xpan_feasibility](xpan_feasibility/) | 2026-10-30 | 研究 | 部分可行：电脑裁切一定可行，机内真输出不可行 | 已被 [xpan_incamera_r2](xpan_incamera_r2/) 取代 | [REPORT.md](xpan_feasibility/REPORT.md) |
| [xpan_incamera](xpan_incamera/) | 2026-10-30 | 研究 | 部分可行：推荐复用 16:9 类别 | 已被 [xpan_incamera_r2](xpan_incamera_r2/) 取代 | [REPORT.md](xpan_incamera/REPORT.md) |
| [xpan_incamera_r2](xpan_incamera_r2/) | 2026-10-30 | 研究 | 无 REPORT，仅候选脚本 | OPEN | [xpan_incamera_r2/](xpan_incamera_r2/) |

### 复审（未归入上列主题）

| 目录 | 日期 | 类型 | 结论 | 状态 | 关键产出 |
| --- | --- | --- | --- | --- | --- |
| [review_diag](review_diag/) | 2026-10-29 | 复审 | 不可以上测试卡 | 已被 [review_diag2](review_diag2/) 取代 | [REVIEW.md](review_diag/REVIEW.md) |
| [review_diag142](review_diag142/) | 2026-10-30 | 复审 | 可以上卡 | 历史 | [REVIEW.md](review_diag142/REVIEW.md) |
| [review_diag143](review_diag143/) | 2026-10-31 | 复审 | 不能上卡 | 已被后续工作取代 | [REVIEW.md](review_diag143/REVIEW.md) |
| [review_diag144](review_diag144/) | 2026-10-31 | 复审 | 不能上卡 | 已被后续工作取代 | [REVIEW.md](review_diag144/REVIEW.md) |
| [review_diag145](review_diag145/) | 2026-10-31 | 复审 | 不能上卡 | 已被后续工作取代 | [REVIEW.md](review_diag145/REVIEW.md) |
| [review_diag146](review_diag146/) | 2026-10-31 | 复审 | 不能上卡 | 已被后续工作取代 | [REVIEW.md](review_diag146/REVIEW.md) |
| [review_diag147](review_diag147/) | 2026-10-31 | 复审 | 不能上卡 | 已被 [review_diag147_r3](review_diag147_r3/) 取代 | [REVIEW.md](review_diag147/REVIEW.md) |
| [review_diag147_r2](review_diag147_r2/) | 2026-10-31 | 复审 | 无 REVIEW.md，仅有脚本与日志 | OPEN | [review_diag147_r2/](review_diag147_r2/) |
| [review_diag147_r3](review_diag147_r3/) | 2026-10-31 | 复审 | 不能上卡 | 已被后续工作取代 | [REVIEW.md](review_diag147_r3/REVIEW.md) |
| [review_diag2](review_diag2/) | 2026-10-29 | 复审 | 不可以上测试卡 | 历史 | [REVIEW.md](review_diag2/REVIEW.md) |
| [review_diag_v4p](review_diag_v4p/) | 2026-11-02 | 复审 | 修改后再上机 | 历史 | [REVIEW.md](review_diag_v4p/REVIEW.md) |
| [review_g117_codegen](review_g117_codegen/) | 2026-10-27 | 复审 | 不可以接受。 | 已被 [review_g117_codegen_r2](review_g117_codegen_r2/) 取代 | [REVIEW.md](review_g117_codegen/REVIEW.md) |
| [review_g117_codegen_r2](review_g117_codegen_r2/) | 2026-10-27 | 复审 | 可以接受。 | 已被后续代数取代 | [REVIEW.md](review_g117_codegen_r2/REVIEW.md) |
| [review_g117_container](review_g117_container/) | 2026-10-27 | 复审 | 不可以上卡。 | 已被后续代数取代 | [REVIEW.md](review_g117_container/REVIEW.md) |
| [review_g118](review_g118/) | 2026-10-27 | 复审 | 不可以上卡。 | 已被后续代数取代 | [REVIEW.md](review_g118/REVIEW.md) |
| [review_g119](review_g119/) | 2026-10-27 | 复审 | 无 REVIEW.md（pitfalls 记为被安全过滤中止） | OPEN | [review_g119/](review_g119/) |
| [review_g119b](review_g119b/) | 2026-10-27 | 复审 | 不可以上卡。 | 已被后续代数取代 | [REVIEW.md](review_g119b/REVIEW.md) |
| [review_g120b](review_g120b/) | 2026-10-28 | 复审 | 不可以上卡。 | 已被后续代数取代 | [REVIEW.md](review_g120b/REVIEW.md) |
| [review_g120b_codegen](review_g120b_codegen/) | 2026-10-28 | 复审 | 不可以上卡。 | 已被后续代数取代 | [REVIEW.md](review_g120b_codegen/REVIEW.md) |
| [review_g122](review_g122/) | 2026-10-28 | 复审 | 不可以上测试卡 | 已被后续代数取代 | [REVIEW.md](review_g122/REVIEW.md) |
| [review_g123](review_g123/) | 2026-10-28 | 复审 | 不可以上测试卡 | 已被后续代数取代 | [REVIEW.md](review_g123/REVIEW.md) |
| [review_g124](review_g124/) | 2026-10-28 | 复审 | 不可以上测试卡 | 已被后续代数取代 | [REVIEW.md](review_g124/REVIEW.md) |
| [review_g126](review_g126/) | 2026-10-29 | 复审 | 不可以上测试卡 | 已被后续代数取代 | [REVIEW.md](review_g126/REVIEW.md) |
| [review_g127](review_g127/) | 2026-10-29 | 复审 | 不可以上测试卡 | 已被后续代数取代 | [REVIEW.md](review_g127/REVIEW.md) |
| [review_g129](review_g129/) | 2026-10-29 | 复审 | 不可以上测试卡 | 已被后续代数取代 | [REVIEW.md](review_g129/REVIEW.md) |
| [review_g135](review_g135/) | 2026-10-30 | 复审 | 可以上测试卡 | 已被后续代数取代 | [REVIEW.md](review_g135/REVIEW.md) |
| [review_g135_gpt](review_g135_gpt/) | 2026-10-30 | 复审 | 不可以上测试卡 | 已被后续代数取代 | [REVIEW.md](review_g135_gpt/REVIEW.md) |
| [review_g138](review_g138/) | 2026-10-31 | 复审 | 不能上卡 | 已被后续代数取代 | [REVIEW.md](review_g138/REVIEW.md) |
| [review_g139](review_g139/) | 2026-11-01 | 复审 | 不能上卡 | 已被后续代数取代 | [REVIEW.md](review_g139/REVIEW.md) |
| [review_g150](review_g150/) | 2026-11-01 | 复审 | 不能上卡 | 已被后续代数取代 | [REVIEW.md](review_g150/REVIEW.md) |
| [review_g151_body](review_g151_body/) | 2026-11-01 | 复审 | 机身可以刷；DAT 待 g152 修复移植后差量复审 | 已被后续代数取代 | [REVIEW.md](review_g151_body/REVIEW.md) |
| [review_g152](review_g152/) | 2026-11-01 | 复审 | 不能上卡 | 已被后续代数取代 | [REVIEW.md](review_g152/REVIEW.md) |
| [review_g153](review_g153/) | 2026-11-02 | 复审 | 修改后再刷 | 已被后续代数取代 | [REVIEW.md](review_g153/REVIEW.md) |
| [review_g154](review_g154/) | 2026-11-02 | 复审 | 修改后再上卡 | 已被后续代数取代 | [REVIEW.md](review_g154/REVIEW.md) |
| [review_g155c_r1](review_g155c_r1/) | 2026-11-03 | 复审 | 可以上卡（test）；可以上卡（release） | 历史 | [REVIEW.md](review_g155c_r1/REVIEW.md) |
| [review_g156_r1](review_g156_r1/) | 2026-11-04 | 复审 | 可以上卡（release）；可以上卡（test） | 现行 | [REVIEW.md](review_g156_r1/REVIEW.md) |

### 其他

| 目录 | 日期 | 类型 | 结论 | 状态 | 关键产出 |
| --- | --- | --- | --- | --- | --- |
| [status_report_20261024](status_report_20261024/) | 2026-10-24 | 研究 | 无 Markdown 报告，仅 HTML | 历史 | [status_report_20261024/](status_report_20261024/) |
| [status_report_20261028](status_report_20261028/) | 2026-10-28 | 研究 | 无 Markdown 报告，仅 HTML | 历史 | [status_report_20261028/](status_report_20261028/) |
| [tweak_memory_r1](tweak_memory_r1/) | 2026-11-03 | 研究 | 有缺陷 | OPEN | [REPORT.md](tweak_memory_r1/REPORT.md) |
| [verify_g152](verify_g152/) | 2026-11-01 | 复审 | 无 REPORT，仅验证日志 | OPEN | [verify_g152/](verify_g152/) |

## 关键节点时间线

从 `decisions.tsv` 抽出约 40 条。每条尽量链到对应报告。

| 时间 | 键 | 发生了什么 | 报告 |
| --- | --- | --- | --- |
| 2026-10-12 | `start / product` | 开始研究；目标定为独立色彩配方库 | [recipes/REPORT.md](recipes/REPORT.md) |
| 2026-10-12 | `tooling / m32r` | 锁定 REA；随后自建 M32R 工具链 | [tooling/REPORT.md](tooling/REPORT.md) |
| 2026-10-13 | `camera_arrival` | 相机到场，先只读菜单与研究卡备份 | [phase0_drill/FLASH_AND_RECOVERY.md](phase0_drill/FLASH_AND_RECOVERY.md) |
| 2026-10-13 | `roadmap` | 目标写成把 GXR 改成现代 GR | [../docs/ROADMAP.md](../docs/ROADMAP.md) |
| 2026-10-13 | `setting1_fields_confirmed` | Setting1 十三字段经真机照片确认 | [field_mapping/REPORT.md](field_mapping/REPORT.md) |
| 2026-10-13 | `drill_step1_done` | 官方 1.51 刷写成功，镜头 1.50→1.51 | [phase0_drill/FLASH_AND_RECOVERY.md](phase0_drill/FLASH_AND_RECOVERY.md) |
| 2026-10-13 | `drill_step2_flashed` | ISX 演练包刷写成功 | [phase0_drill/FLASH_AND_RECOVERY.md](phase0_drill/FLASH_AND_RECOVERY.md) |
| 2026-10-14 | `drill_recovery_confirmed` | 刷回官方，回放 ISO 恢复，演练闭环 | [phase0_drill/FLASH_AND_RECOVERY.md](phase0_drill/FLASH_AND_RECOVERY.md) |
| 2026-10-15 | `stage1a_v3_first_run_ok8` | 真机首次执行新代码，回放显示 OK 8 | [stage1a_probe_v3/REPORT.md](stage1a_probe_v3/REPORT.md) |
| 2026-10-15 | `stage1a_v3_recovery_confirmed` | 探针验证结束并恢复官方 | [stage1a_probe_v3/REPORT.md](stage1a_probe_v3/REPORT.md) |
| 2026-10-15 | `stage1b_first_camera_recipe_ui_observed` | 配方列表第一次在相机上出现 | [stage1b_integration/REPORT.md](stage1b_integration/REPORT.md) |
| 2026-10-16 | `stage2a_deep_isp_card_written` | Deep 候选写卡 | [stage2a_deep_isp/REPORT.md](stage2a_deep_isp/REPORT.md) |
| 2026-10-19 | `stage2c_first_run_success` | M 档配方能选、颜色有变化 | [stage2c_category_gate/REPORT.md](stage2c_category_gate/REPORT.md) |
| 2026-10-19 | `stage2d_onCamera_verified` | Stage 2d 真机色卡 | [stage2d_verification/REPORT.md](stage2d_verification/REPORT.md) |
| 2026-10-20 | `stage2j_card_written` | Stage 2j 写卡；随后补表 | [stage2j/REPORT.md](stage2j/REPORT.md) |
| 2026-10-21 | `tables_v4 / fuji_round5` | v4/v5 表与富士第 5 轮上卡测试 | [tables_v4/REPORT.md](tables_v4/REPORT.md) |
| 2026-10-25 | `blink_state_50mm` | 50mm 黑屏绿灯闪，排除内部存储引擎文件触发 | [blink_state_50mm/REPORT.md](blink_state_50mm/REPORT.md) |
| 2026-10-26 | `boot_hang_v35` | 不构建 v3.5：原生固件也会挂 | [boot_hang_v35/REPORT.md](boot_hang_v35/REPORT.md) |
| 2026-10-27 | `review_v36_body` | v3.6 BODY 可以上卡 | [review_v36_body/REVIEW.md](review_v36_body/REVIEW.md) |
| 2026-10-27 | `ux_preview_dot_r3` | gen 120 因 H07 停建 | [ux_preview_dot_r3/REPORT.md](ux_preview_dot_r3/REPORT.md) |
| 2026-10-30 | `review_v38_g137` | v3.8 / g137 可以刷机 | [review_v38_g137/REVIEW.md](review_v38_g137/REVIEW.md) |
| 2026-10-31 | `studio_v2` | Studio PRD 与设计落地 | [studio_v2/PRD.md](studio_v2/PRD.md) |
| 2026-11-01 | `g152-field-ok` | g152 test 现场颜色正确 | [looks_g152/REPORT.md](looks_g152/REPORT.md) |
| 2026-11-01 | `package_v39_g149 作废` | g149 作废，改走 g151 | [../firmware/package_v39_g149/README.md](../firmware/package_v39_g149/README.md) |
| 2026-11-02 | `diag-v4p-mount-captured` | 确认 v3.9 机身已在 MOUNT | [diag_v4p_mount_20261102/REPORT.md](diag_v4p_mount_20261102/REPORT.md) |
| 2026-11-02 | `review_g154` | g154 修改后再上卡 | [review_g154/REVIEW.md](review_g154/REVIEW.md) |
| 2026-11-03 | `review-v310-body-pass` | v3.10 机身可以刷（无 DAT 先开机检查） | [review_v310_body_r1/REVIEW.md](review_v310_body_r1/REVIEW.md) |
| 2026-11-03 | `probe2-shot / probe3-card-written` | 探针 2 已拍；探针 3 复审可以上卡 | [probe_pack_r2/REPORT_PROBE2.md](probe_pack_r2/REPORT_PROBE2.md) |
| 2026-11-03 | `review-g155c-pass` | g155c release/test 可以上卡（有监督） | [review_g155c_r1/REVIEW.md](review_g155c_r1/REVIEW.md) |
| 2026-11-03 | `g156-accepted+review` | g156 可以交复审，随后复审可以上卡 | [g156/REPORT.md](g156/REPORT.md) |
| 2026-11-04 | `probe3-shot+card-restored` | 探针 3 八对已拍并恢复卡 | [probe_pack_r3/REPORT_PROBE3.md](probe_pack_r3/REPORT_PROBE3.md) |
| 2026-11-04 | `mount-v310-flashed+g156-test-staged` | MOUNT 刷 v3.10，无 DAT 开机正常，再上 g156 test | [review_v310_body_r1/REVIEW.md](review_v310_body_r1/REVIEW.md) |
| 2026-11-04 | `noon-shot / noon-analysis-r2` | 中午色卡与屏幕页已拍并分析 | [noon_sweep_r1/REPORT_noon-20261104-r2.md](noon_sweep_r1/REPORT_noon-20261104-r2.md) |
| 2026-11-04 | `fit-fast-r3-not-adopted` | fit-fast 第三轮不能采用 | [review_fit_fast_r2/REVIEW.md](review_fit_fast_r2/REVIEW.md) |
| 2026-11-04 | `bluecyan-r1 / model-c040` | MOUNT 蓝青误差归因于 C040 节点误用，并接入 g157 候选 | [bluecyan_r1/REPORT.md](bluecyan_r1/REPORT.md) |
| 2026-11-04 | `friend-lost-after-powercycle` | 朋友 v3.10+DAT 首次正常，关机再开变原厂列表 | [g156_field_issues_r1/REPORT.md](g156_field_issues_r1/REPORT.md) |
| 2026-11-04 | `boot-apply-skipped-field` | 机主 M 档选 03 关机再开，首拍回到彩色 04 | [g156_field_issues_r1/REPORT.md](g156_field_issues_r1/REPORT.md) |
| 2026-11-04 | `g157-build / film-looks-r2` | g157 开工；官方 Acros 可换进既定布局 | [film_looks_r2/ACROS.md](film_looks_r2/ACROS.md) |
| 2026-11-04 | `roadmap-after-g157` | g157 稳定后再衡量机内 3D LUT | [../docs/ROADMAP.md](../docs/ROADMAP.md) |
| 2026-11-04 | `studio-pr29-merged` | Studio g156 编解码复审可以合并 | [review_studio_g156_r2/REVIEW.md](review_studio_g156_r2/REVIEW.md) |
| 2026-11-04 | `git-sync-commit-ready` | 公开同步需要人工确认 | [git_sync/REPORT.md](git_sync/REPORT.md) |
| 2026-11-04 | `data+research-index` | 要求做数据总索引与本页 | [INDEX.md](INDEX.md) |

## 索引时看到的缺口

- `g157/` 没有 REPORT.md；`package_v310_g157` 清单是 ACCEPTANCE_PENDING、camera_verified=false。
- `docs/HANDOFF.md` 仍停在 2026-10-23 的 Stage2l 候选，不能当现行机身状态。
- `package_v39_g149` 已作废；`package_v36_g120` / `g120b` 已 STOPPED。
- g156 README 写 Studio 暂不能读写 g156，与 `review_studio_g156_r2`（可以合并）之间有时间差。
- `stage2j/REPORT.md` 标题写未上机，`decisions.tsv` 随后有 `stage2j_card_written`。
- `g156` 的 MANIFEST 仍带 `G155_BOOT` 字段名，代数已是 156。
- `body_v4_storage/` 三方报告结论不一致（仍不可行 / 找到可行桥）。
- `review_g119/`、`review_diag147_r2/`、`harness_ccore/`、`verify_*` 等没有 REVIEW/REPORT。
- 多数 `package_*` 没有 README 首行，状态只能从复审报告或 STATUS.txt 推断。
- `package_v37_redisplay`、`package_v39_diagv4p` 的 DAT SHA 未写入 SHA256SUMS。

目录计数：研究目录 414 个（`research/` 下一级文件夹）；固件包 63 个。
