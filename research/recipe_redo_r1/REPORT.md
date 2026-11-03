电脑预测：新7张04中央60%区，冻结MOUNT映射中位ΔE00为0.785，比50mm迁移下降16.60%；中央重标定留出回退，保留原输入。
以g155c实际10个Looks为发布基线；105项已重新比较，当前21条现有槽位候选通过模型门；28mm仅合成。
10项默认候选先按最多新增1条数据行的约束选最低整数训练损失，再过留出门；完整共享模型另列，不按照片成绩换旧解。
需要机主素材：MOUNT同场节点16正负定标、更多整场景原厂04；28mm仍缺可用RAW。
本轮不构建DAT；格式和主分配只作静态核算，代数、主机运行与相机验收由后续构建任务负责。

## 发布基线与记录身份

发布基线为firmware/package_v310_g155c，release SHA为69fa85104fcb449e613950bb58c802b9b64464769ae524fe3f7303e06093c2ad。每单元实际10个Looks，逐条由DAT解码并对照g156的before map；原生04的552 B与既有模型输入相同。g154 Looks18只保留历史研究身份。
本轮改动30条研究记录，另75条SHA不变。上一轮供构建读取的38条原路径与字节全部保留；新内容使用SHA命名的文件。差异收据见record_sha_changes.json。

## 10项共享曲线重拟合，电脑预测

三组均使用flags=1和S=04。free允许共享曲线、Y系数与对称扇区重拟合；reuse_tone_matrix保留g155c横轴、曲线和完整矩阵，只拟合扇区；reuse_hue_matrix保留横轴、扇区和完整矩阵，只拟合共享曲线。后两组最多新增一条96 B或33 B行。模板原字节在量化后保留，避免负零或矩阵舍入造成多余行。
默认部署策略在两组紧凑模型间只按整数训练损失选型，不读照片分数。之后应用逐场景中位/P95、MOUNT七张自然RAW整组、exact的0.1百分点及None绝对误差门；失败就保留g155c行，不改挑另一组或旧解。其他模型作为单独声明的候选对照保留。
每组先迭代，再由exact重跑全部原声明起点、父候选、已有可行整数解及横轴，并把迭代整数解作为额外起点和可保留状态。所有选择都用保存后解码的整数训练目标；记录、预测、全部夹具及门控均独立复算。

| 单元/Look | 模型 | g155c照片% | 候选照片% | 提升pp | exact门 | 场景门 | 新增行62/33/96/56 | 该模型结论 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mount-a12 Portra 400 | free | 59.961 | 61.631 | 1.670 | REVIEW | mount_natural_20261103_whole_collection | [0, 1, 1, 1] | 保留当前 |
| mount-a12 Portra 400 | reuse_tone_matrix，默认 | 59.961 | 63.055 | 3.094 | REVIEW | mount-a12_2026:10:31_dng | [0, 0, 1, 0] | 保留当前 |
| mount-a12 Portra 400 | reuse_hue_matrix | 59.961 | 59.899 | -0.062 | PASS | mount-a12_2026:11:01_street-g150-20261101、mount-a12_2026:11:02_new39、mount_natural_20261103_whole_collection | [0, 1, 0, 0] | 保留当前 |
| mount-a12 Kodachrome25 | free | 64.176 | 71.021 | 6.844 | PASS | mount-a12_2026:10:31_dng | [0, 1, 1, 1] | 保留当前 |
| mount-a12 Kodachrome25 | reuse_tone_matrix，默认 | 64.176 | 72.544 | 8.367 | PASS | 通过 | [0, 0, 1, 0] | 可供构建验证 |
| mount-a12 Kodachrome25 | reuse_hue_matrix | 64.176 | 64.142 | -0.034 | PASS | mount-a12_2026:11:01_street-g150-20261101、mount-a12_2026:11:02_new39 | [0, 1, 0, 0] | 保留当前 |
| mount-a12 HNCS LowSat | free | 77.864 | 78.415 | 0.551 | PASS | 通过 | [0, 1, 1, 1] | 可供构建验证 |
| mount-a12 HNCS LowSat | reuse_tone_matrix，默认 | 77.864 | 78.561 | 0.697 | PASS | 通过 | [0, 0, 1, 0] | 可供构建验证 |
| mount-a12 HNCS LowSat | reuse_hue_matrix | 77.864 | 77.864 | 0.000 | PASS | 通过 | [0, 0, 0, 0] | 保留当前 |
| mount-a12 Vision3 500T | free | 73.021 | 74.716 | 1.695 | PASS | mount-a12_2026:10:31_dng | [0, 1, 1, 1] | 保留当前 |
| mount-a12 Vision3 500T | reuse_tone_matrix，默认 | 73.021 | 74.537 | 1.517 | PASS | 通过 | [0, 0, 1, 0] | 可供构建验证 |
| mount-a12 Vision3 500T | reuse_hue_matrix | 73.021 | 72.744 | -0.277 | REVIEW | mount-a12_2026:10:31_dng、mount-a12_2026:11:01_street-g150-20261101、mount-a12_2026:11:02_new39、mount_natural_20261103_whole_collection | [0, 1, 0, 0] | 保留当前 |
| mount-a12 Metropolis | free | 67.935 | 67.644 | -0.291 | PASS | mount-a12_2026:11:01_street-g150-20261101、mount-a12_2026:11:02_new39、mount_natural_20261103_whole_collection | [0, 1, 1, 1] | 保留当前 |
| mount-a12 Metropolis | reuse_tone_matrix，默认 | 67.935 | 67.735 | -0.201 | PASS | mount-a12_2026:11:01_street-g150-20261101、mount-a12_2026:11:02_new39、mount_natural_20261103_whole_collection | [0, 0, 1, 0] | 保留当前 |
| mount-a12 Metropolis | reuse_hue_matrix | 67.935 | 67.932 | -0.003 | PASS | mount-a12_2026:11:02_new39 | [0, 1, 0, 0] | 保留当前 |
| a12-50 Portra 400 | free | 60.913 | 62.528 | 1.616 | PASS | a12-50_2026:10:21_after-p0-write、a12-50_2026:10:24_stage2l-daily-R8051312-1473 | [0, 1, 1, 1] | 保留当前 |
| a12-50 Portra 400 | reuse_tone_matrix，默认 | 60.913 | 60.928 | 0.015 | PASS | a12-50_2026:10:21_after-p0-write、a12-50_2026:10:23_stage2l-daily-R8051219-1228、a12-50_2026:10:24_stage2l-daily-R8051312-1473 | [0, 0, 1, 0] | 保留当前 |
| a12-50 Portra 400 | reuse_hue_matrix | 60.913 | 60.959 | 0.047 | PASS | 通过 | [0, 1, 0, 0] | 可供构建验证 |
| a12-50 Velvia 50 | free | 71.136 | 73.439 | 2.303 | PASS | 通过 | [0, 1, 1, 1] | 可供构建验证 |
| a12-50 Velvia 50 | reuse_tone_matrix，默认 | 71.136 | 72.088 | 0.952 | PASS | 通过 | [0, 0, 1, 0] | 可供构建验证 |
| a12-50 Velvia 50 | reuse_hue_matrix | 71.136 | 71.136 | 0.000 | PASS | 通过 | [0, 0, 0, 0] | 保留当前 |
| a12-50 Kodachrome25 | free | 69.749 | 69.489 | -0.261 | PASS | a12-50_2026:10:21_after-p0-write、a12-50_2026:10:24_stage2l-daily-R8051312-1473 | [0, 1, 1, 1] | 保留当前 |
| a12-50 Kodachrome25 | reuse_tone_matrix，默认 | 69.749 | 69.726 | -0.023 | PASS | a12-50_2026:10:24_hk-1024、a12-50_2026:10:24_stage2l-daily-R8051312-1473 | [0, 0, 1, 0] | 保留当前 |
| a12-50 Kodachrome25 | reuse_hue_matrix | 69.749 | 69.742 | -0.007 | PASS | a12-50_2026:10:21_after-p0-write、a12-50_2026:10:24_stage2l-daily-R8051312-1473 | [0, 1, 0, 0] | 保留当前 |
| a12-50 Vision3 500T | free | 73.216 | 73.589 | 0.373 | PASS | a12-50_2026:10:24_hk-1024 | [0, 1, 1, 1] | 保留当前 |
| a12-50 Vision3 500T | reuse_tone_matrix，默认 | 73.216 | 73.142 | -0.074 | PASS | a12-50_2026:10:24_stage2l-daily-R8051312-1473 | [0, 0, 1, 0] | 保留当前 |
| a12-50 Vision3 500T | reuse_hue_matrix | 73.216 | 73.183 | -0.033 | PASS | a12-50_2026:10:21_after-p0-write、a12-50_2026:10:24_hk-1024、a12-50_2026:10:24_stage2l-daily-R8051312-1473 | [0, 1, 0, 0] | 保留当前 |
| a12-50 Metropolis | free | 76.669 | 76.847 | 0.178 | PASS | a12-50_2026:10:21_after-p0-write | [0, 1, 1, 1] | 保留当前 |
| a12-50 Metropolis | reuse_tone_matrix，默认 | 76.669 | 76.701 | 0.032 | PASS | 通过 | [0, 0, 1, 0] | 可供构建验证 |
| a12-50 Metropolis | reuse_hue_matrix | 76.669 | 76.669 | 0.000 | PASS | 通过 | [0, 0, 0, 0] | 保留当前 |

| 构建候选，电脑预测 | 确认前训练% | 完整exact训练% | 确认前主要留出% | 完整exact主要留出% | 实际起点数 |
| --- | --- | --- | --- | --- | --- |
| mount-a12 M9 STD | 83.699 | 83.699 | 88.641 | 88.641 | 5 |
| mount-a12 HNCS HiCon | 78.179 | 78.179 | 76.984 | 76.984 | 4 |
| mount-a12 Kodachrome25 | 64.776 | 64.776 | 72.544 | 72.544 | 3 |
| mount-a12 HNCS LowSat | 76.372 | 76.372 | 78.561 | 78.561 | 3 |
| mount-a12 Vision3 500T | 77.286 | 77.286 | 74.537 | 74.537 | 4 |
| mount-a12 05 F-CC | 84.593 | 84.593 | 86.570 | 86.570 | 8 |
| mount-a12 06 F-CN | 85.813 | 85.813 | 84.797 | 84.797 | 9 |
| a12-50 HNCS HiCon | 82.877 | 82.877 | 79.341 | 79.341 | 4 |
| a12-50 Tri-X 400 | 95.071 | 95.071 | 92.894 | 92.894 | 3 |
| a12-50 Velvia 50 | 71.119 | 71.119 | 72.088 | 72.088 | 2 |
| a12-50 Metropolis | 81.334 | 81.334 | 76.701 | 76.701 | 2 |
| a12-50 03 HC BW | 94.939 | 94.939 | 94.092 | 94.092 | 6 |
| a12-50 07 L-Chr | 82.548 | 82.548 | 83.266 | 83.266 | 3 |
| a12-50 08 L-Viv | 81.531 | 81.531 | 80.621 | 80.621 | 3 |
| a12-28 Tri-X 400 | 93.744 | 93.744 | 93.382 | 93.382 | 4 |
| a12-28 Velvia 50 | 64.729 | 64.729 | 61.935 | 61.935 | 3 |
| a12-28 HNCS LowSat | 62.653 | 62.653 | 58.676 | 58.676 | 3 |
| a12-28 01 GRPos | 79.052 | 79.518 | 77.055 | 77.055 | 6 |
| a12-28 03 HC BW | 93.529 | 93.529 | 92.937 | 92.937 | 5 |
| a12-28 06 F-CN | 84.371 | 84.371 | 84.587 | 84.587 | 5 |
| a12-28 08 L-Viv | 68.213 | 68.667 | 66.037 | 66.001 | 4 |

完整训练、合成、ISO200照片、其他ISO诊断、中位/P95和逐照片结果在local/round2_replay；compatible_look_candidates.json绑定30个精确记录、SHA和full-start exact证据。共享曲线不依赖未验收的独立RGB幅度修正。

## 容量核算

新增唯一行按实际g155c全部行池逐字节比较，计数包含跨角色和跨单元复用。净字节另计未用行消失、四字节对齐和Look描述符按单元拆分。仅核算，没有序列化或构建DAT。原g155c保留表容量5588 B；最小去重重排是4992 B，两者不能混作同一个基线。

| 包 | 预测DAT B | 预测主分配B | 上限B | 超出B |
| --- | --- | --- | --- | --- |
| release | 90180 | 107092 | 107612 | 0 |
| test | 93088 | 110012 | 107612 | 2400 |

| 仅MOUNT和50mm候选 | 预测DAT B | 预测主分配B | 上限B | 超出B |
| --- | --- | --- | --- | --- |
| release | 88684 | 105596 | 107612 | 0 |
| test | 91592 | 108516 | 107612 | 904 |

当前现有槽位候选合并后的数据表为9056 B，Look描述符22个。逐条新增行数、负载字节与单项净表差见g155c_row_budget.json。此结果不关闭g156发现的代数检查或实际主机运行问题。

## 全部105项，电脑预测

没有g155c槽位的研究目标使用该单元base05作明确的离线参考，不能把差值说成相对已发布Look的提升；仍保留全部目标，没有删除Looks。10项彩色Looks引用05，必须flags=1。Tri-X引用03，50mm已确认的03和Tri-X均为flags=7，必须成组采用或一起保留g155c；此依赖已写进清单，原记录SHA不变。任何与实际引用base不一致的Look及会破坏既有Looks的05候选均不列替换。原C的fx_area_valid按e[0]选择base并比较d[1]与e[1]，证据是g156冻结的fx_pool.c第69至72行。

| 单元 | 配方 | 比较基线 | 训练% | 合成% | 照片% | 主要提升pp | flags | 全起点exact | 处理 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mount-a12 | Agfa LeBox | base05离线参考 | 79.948 | 73.407 | 79.682 | 132.231 | 7 | REVIEW | do_not_add |
| mount-a12 | 千禧回声 A | base05离线参考 | 71.342 | 69.357 | 69.821 | 62.302 | 7 | REVIEW | do_not_add |
| mount-a12 | 千禧回声 B | base05离线参考 | 47.717 | 59.401 | 34.660 | 34.992 | 1 | PENDING | do_not_add |
| mount-a12 | Y2K Plady | base05离线参考 | 69.599 | 53.903 | 81.222 | 164.635 | 7 | PASS | do_not_add |
| mount-a12 | Phocus Standard | base05离线参考 | 48.637 | 50.566 | 34.297 | 180.772 | 7 | PENDING | do_not_add |
| mount-a12 | Phocus Nature | base05离线参考 | 56.102 | 58.435 | 37.651 | 143.012 | 7 | PENDING | do_not_add |
| mount-a12 | ARRI Classic709 | base05离线参考 | 91.061 | 89.286 | 89.672 | 21.002 | 1 | PENDING | do_not_add |
| mount-a12 | Kodak 2383 | base05离线参考 | 67.129 | 70.438 | 58.296 | 4.084 | 7 | PENDING | do_not_add |
| mount-a12 | Fuji 3513DI | base05离线参考 | 62.986 | 68.303 | 59.055 | 13.826 | 7 | PENDING | do_not_add |
| mount-a12 | Eterna BB | base05离线参考 | 90.463 | 87.487 | 93.499 | 28.820 | 7 | PASS | do_not_add |
| mount-a12 | RED Film Bias | base05离线参考 | 85.444 | 83.701 | 72.311 | 60.913 | 7 | PENDING | do_not_add |
| mount-a12 | Classic Chrome | base05离线参考 | 89.406 | 86.755 | 92.177 | 18.354 | 7 | PASS | do_not_add |
| mount-a12 | Classic Neg | base05离线参考 | 88.352 | 85.145 | 88.860 | 24.327 | 7 | PASS | do_not_add |
| mount-a12 | Eterna | base05离线参考 | 87.473 | 86.367 | 88.148 | 26.736 | 7 | PASS | do_not_add |
| mount-a12 | Acros | base05离线参考 | 97.483 | 94.782 | 97.646 | 39.876 | 7 | PASS | do_not_add |
| mount-a12 | Leica Classic | base05离线参考 | 89.762 | 88.850 | 89.428 | 27.252 | 7 | PENDING | do_not_add |
| mount-a12 | RED IPP2 | base05离线参考 | 87.693 | 86.203 | 83.931 | 22.265 | 7 | PENDING | do_not_add |
| mount-a12 | M9 STD | g155c | 83.699 | 74.912 | 88.641 | 3.034 | 1 | PASS | replace_candidate |
| mount-a12 | HNCS HiCon | g155c | 78.179 | 72.871 | 76.984 | 3.726 | 1 | PASS | replace_candidate |
| mount-a12 | Tri-X 400 | g155c | 93.942 | 93.028 | 88.578 | -0.776 | 7 | PENDING | needs_shared_compatible_refit |
| mount-a12 | Portra 400 | g155c | 64.610 | 68.922 | 63.055 | 3.094 | 1 | REVIEW | review_exact_holdout |
| mount-a12 | Velvia 50 | g155c | 69.935 | 65.189 | 72.830 | 3.203 | 1 | PENDING | pending_full_start_exact |
| mount-a12 | Kodachrome25 | g155c | 64.776 | 66.038 | 72.544 | 8.367 | 1 | PASS | replace_candidate |
| mount-a12 | HNCS LowSat | g155c | 76.372 | 64.334 | 78.561 | 0.697 | 1 | PASS | replace_candidate |
| mount-a12 | Vision3 500T | g155c | 77.286 | 77.416 | 74.537 | 1.517 | 1 | PASS | replace_candidate |
| mount-a12 | instax mini | g155c | 81.562 | 72.052 | 82.375 | 0.270 | 1 | PENDING | pending_full_start_exact |
| mount-a12 | Metropolis | g155c | 82.630 | 86.549 | 67.735 | -0.201 | 1 | PASS | keep_current_after_review |
| mount-a12 | 01 GRPos | g155c | 79.233 | 74.391 | 69.546 | -3.921 | 7 | PENDING | keep_current_after_review |
| mount-a12 | 02 GRNeg | g155c | 67.871 | 75.316 | 56.884 | 1.315 | 7 | PENDING | pending_full_start_exact |
| mount-a12 | 03 HC BW | g155c | 95.653 | 91.942 | 96.294 | 11.574 | 7 | PENDING | pending_full_start_exact |
| mount-a12 | 04 Std | g155c | — | — | — | — | 0 | PENDING | keep_native04 |
| mount-a12 | 05 F-CC | g155c | 84.593 | 81.682 | 86.570 | 6.389 | 1 | PASS | replace_candidate |
| mount-a12 | 06 F-CN | g155c | 85.813 | 83.768 | 84.797 | 7.250 | 7 | PASS | replace_candidate |
| mount-a12 | 07 L-Chr | g155c | 77.790 | 70.067 | 79.416 | 5.435 | 7 | PENDING | pending_full_start_exact |
| mount-a12 | 08 L-Viv | g155c | 72.732 | 62.534 | 74.977 | 2.341 | 7 | PENDING | keep_current_after_review |
| a12-50 | Agfa LeBox | base05离线参考 | 82.629 | 72.343 | 82.221 | 127.136 | 7 | PASS | do_not_add |
| a12-50 | 千禧回声 A | base05离线参考 | 50.894 | 65.526 | 47.484 | 44.936 | 7 | PASS | do_not_add |
| a12-50 | 千禧回声 B | base05离线参考 | 65.056 | 62.075 | 60.934 | 59.565 | 7 | PASS | do_not_add |
| a12-50 | Y2K Plady | base05离线参考 | 77.642 | 53.426 | 82.424 | 166.012 | 7 | PASS | do_not_add |
| a12-50 | Phocus Standard | base05离线参考 | 48.891 | 45.375 | 48.258 | 228.556 | 7 | PENDING | do_not_add |
| a12-50 | Phocus Nature | base05离线参考 | 55.880 | 54.574 | 54.459 | 185.096 | 7 | PENDING | do_not_add |
| a12-50 | ARRI Classic709 | base05离线参考 | 95.696 | 92.697 | 95.089 | 36.168 | 7 | PENDING | do_not_add |
| a12-50 | Kodak 2383 | base05离线参考 | 76.798 | 76.127 | 73.000 | 9.923 | 7 | PASS | do_not_add |
| a12-50 | Fuji 3513DI | base05离线参考 | 76.965 | 74.772 | 71.988 | 16.368 | 7 | PASS | do_not_add |
| a12-50 | Eterna BB | base05离线参考 | 92.992 | 90.207 | 92.358 | 36.485 | 7 | PENDING | do_not_add |
| a12-50 | RED Film Bias | base05离线参考 | 92.504 | 89.668 | 88.771 | 54.350 | 7 | PASS | do_not_add |
| a12-50 | Classic Chrome | base05离线参考 | 92.535 | 89.736 | 92.527 | 20.149 | 7 | PASS | do_not_add |
| a12-50 | Classic Neg | base05离线参考 | 89.861 | 89.407 | 89.549 | 40.524 | 7 | PASS | do_not_add |
| a12-50 | Eterna | base05离线参考 | 91.695 | 89.275 | 92.538 | 29.541 | 7 | PASS | do_not_add |
| a12-50 | Acros | base05离线参考 | 97.230 | 95.681 | 96.045 | 41.504 | 7 | PASS | do_not_add |
| a12-50 | Leica Classic | base05离线参考 | 94.592 | 91.725 | 94.215 | 42.039 | 7 | PASS | do_not_add |
| a12-50 | RED IPP2 | base05离线参考 | 93.432 | 90.565 | 91.845 | 27.560 | 7 | PASS | do_not_add |
| a12-50 | M9 STD | g155c | 84.738 | 75.008 | 86.711 | 0.036 | 1 | PENDING | pending_full_start_exact |
| a12-50 | HNCS HiCon | g155c | 82.877 | 74.246 | 79.341 | 1.182 | 1 | PASS | replace_candidate |
| a12-50 | Tri-X 400 | g155c | 95.071 | 94.631 | 92.894 | 7.383 | 7 | PASS | replace_candidate |
| a12-50 | Portra 400 | g155c | 57.564 | 73.231 | 60.928 | 0.015 | 1 | PASS | keep_current_after_review |
| a12-50 | Velvia 50 | g155c | 71.119 | 65.569 | 72.088 | 0.952 | 1 | PASS | replace_candidate |
| a12-50 | Kodachrome25 | g155c | 70.565 | 66.767 | 69.726 | -0.023 | 1 | PASS | keep_current_after_review |
| a12-50 | HNCS LowSat | g155c | 78.587 | 64.689 | 77.095 | -1.169 | 1 | PENDING | keep_current_after_review |
| a12-50 | Vision3 500T | g155c | 74.982 | 77.756 | 73.142 | -0.074 | 1 | PASS | keep_current_after_review |
| a12-50 | instax mini | g155c | 80.059 | 71.912 | 81.641 | 0.000 | 1 | PENDING | keep_current_after_review |
| a12-50 | Metropolis | g155c | 81.334 | 89.524 | 76.701 | 0.032 | 1 | PASS | replace_candidate |
| a12-50 | 01 GRPos | g155c | 74.504 | 77.278 | 67.954 | -1.423 | 7 | PENDING | keep_current_after_review |
| a12-50 | 02 GRNeg | g155c | 69.153 | 76.250 | 58.904 | -0.035 | 7 | PENDING | keep_current_after_review |
| a12-50 | 03 HC BW | g155c | 94.939 | 92.424 | 94.092 | 14.778 | 7 | PASS | replace_candidate |
| a12-50 | 04 Std | g155c | — | — | — | — | 0 | PENDING | keep_native04 |
| a12-50 | 05 F-CC | g155c | 89.628 | 87.454 | 87.795 | 5.510 | 7 | PENDING | pending_full_start_exact |
| a12-50 | 06 F-CN | g155c | 88.756 | 88.353 | 86.331 | 3.897 | 7 | PENDING | pending_full_start_exact |
| a12-50 | 07 L-Chr | g155c | 82.548 | 74.533 | 83.266 | 11.012 | 7 | PASS | replace_candidate |
| a12-50 | 08 L-Viv | g155c | 81.531 | 67.923 | 80.621 | 4.569 | 7 | PASS | replace_candidate |
| a12-28 | Agfa LeBox | base05离线参考 | 74.716 | 70.422 | 仅合成 | 123.635 | 7 | PASS | do_not_add |
| a12-28 | 千禧回声 A | base05离线参考 | 64.770 | 68.018 | 仅合成 | 54.979 | 7 | PASS | do_not_add |
| a12-28 | 千禧回声 B | base05离线参考 | 57.259 | 59.571 | 仅合成 | 38.758 | 7 | PASS | do_not_add |
| a12-28 | Y2K Plady | base05离线参考 | 62.603 | 56.116 | 仅合成 | 191.521 | 7 | PASS | do_not_add |
| a12-28 | Phocus Standard | base05离线参考 | 55.655 | 51.950 | 仅合成 | 109.842 | 7 | PASS | do_not_add |
| a12-28 | Phocus Nature | base05离线参考 | 56.428 | 51.697 | 仅合成 | 95.528 | 1 | PENDING | do_not_add |
| a12-28 | ARRI Classic709 | base05离线参考 | 91.932 | 90.781 | 仅合成 | 45.857 | 7 | PASS | do_not_add |
| a12-28 | Kodak 2383 | base05离线参考 | 71.940 | 72.987 | 仅合成 | 26.604 | 7 | PASS | do_not_add |
| a12-28 | Fuji 3513DI | base05离线参考 | 69.357 | 73.022 | 仅合成 | 23.999 | 7 | REVIEW | do_not_add |
| a12-28 | Eterna BB | base05离线参考 | 89.545 | 88.505 | 仅合成 | 33.884 | 7 | PASS | do_not_add |
| a12-28 | RED Film Bias | base05离线参考 | 87.193 | 86.830 | 仅合成 | 31.986 | 7 | PASS | do_not_add |
| a12-28 | Classic Chrome | base05离线参考 | 88.499 | 86.892 | 仅合成 | 17.025 | 7 | PASS | do_not_add |
| a12-28 | Classic Neg | base05离线参考 | 88.250 | 87.339 | 仅合成 | 24.206 | 7 | PASS | do_not_add |
| a12-28 | Eterna | base05离线参考 | 88.626 | 87.130 | 仅合成 | 23.776 | 7 | PASS | do_not_add |
| a12-28 | Acros | base05离线参考 | 95.880 | 94.739 | 仅合成 | 75.075 | 7 | PASS | do_not_add |
| a12-28 | Leica Classic | base05离线参考 | 90.578 | 89.885 | 仅合成 | 46.261 | 7 | PASS | do_not_add |
| a12-28 | RED IPP2 | base05离线参考 | 89.025 | 88.592 | 仅合成 | 38.505 | 7 | PASS | do_not_add |
| a12-28 | M9 STD | g155c | 78.943 | 73.478 | 仅合成 | 16.137 | 7 | REVIEW | review_exact_holdout |
| a12-28 | HNCS HiCon | g155c | 76.660 | 71.947 | 仅合成 | 11.253 | 7 | PASS | needs_shared_compatible_refit |
| a12-28 | Tri-X 400 | g155c | 93.744 | 93.382 | 仅合成 | 5.941 | 7 | PASS | replace_candidate |
| a12-28 | Portra 400 | g155c | 74.618 | 74.339 | 仅合成 | 9.525 | 7 | PASS | needs_shared_compatible_refit |
| a12-28 | Velvia 50 | g155c | 64.729 | 61.935 | 仅合成 | 2.039 | 1 | PASS | replace_candidate |
| a12-28 | Kodachrome25 | g155c | 78.049 | 72.880 | 仅合成 | 16.915 | 7 | PASS | needs_shared_compatible_refit |
| a12-28 | HNCS LowSat | g155c | 62.653 | 58.676 | 仅合成 | 3.512 | 1 | PASS | replace_candidate |
| a12-28 | Vision3 500T | g155c | 84.629 | 80.803 | 仅合成 | 10.098 | 7 | PASS | needs_shared_compatible_refit |
| a12-28 | instax mini | g155c | 72.752 | 69.532 | 仅合成 | -0.062 | 1 | PENDING | keep_current_after_review |
| a12-28 | Metropolis | g155c | 91.771 | 91.203 | 仅合成 | 7.409 | 7 | PASS | needs_shared_compatible_refit |
| a12-28 | 01 GRPos | g155c | 79.518 | 77.055 | 仅合成 | 13.647 | 7 | PASS | replace_candidate |
| a12-28 | 02 GRNeg | g155c | 76.915 | 76.522 | 仅合成 | 9.378 | 7 | REVIEW | review_exact_holdout |
| a12-28 | 03 HC BW | g155c | 93.529 | 92.937 | 仅合成 | 11.203 | 7 | PASS | replace_candidate |
| a12-28 | 04 Std | g155c | — | — | 仅合成 | — | 0 | PENDING | keep_native04 |
| a12-28 | 05 F-CC | g155c | 83.461 | 82.344 | 仅合成 | 12.745 | 7 | PASS | needs_shared_compatible_refit |
| a12-28 | 06 F-CN | g155c | 84.371 | 84.587 | 仅合成 | 8.018 | 7 | PASS | replace_candidate |
| a12-28 | 07 L-Chr | g155c | 74.934 | 72.583 | 仅合成 | 12.454 | 7 | REVIEW | review_exact_holdout |
| a12-28 | 08 L-Viv | g155c | 68.667 | 66.001 | 仅合成 | 16.409 | 7 | PASS | replace_candidate |

## 28mm与MOUNT两项复核

28mm的32项待确认均按原计划独立执行全起点exact；每项是否通过0.1门与当前flags兼容性分开记录。只有合成预测，没有照片或相机实测成绩。待确认与失败项见pending_exact_confirmations.json。
MOUNT Agfa LeBox与千禧回声A增加至每起点1000预算，仍相对原固定照片参考下降1.045151与0.124622百分点，均超过0.1门。两者不在g155c实际10个Looks内，决定不新增；原先“保留发布行”的说法已更正为保留历史g154参考，不冒称g155c有该槽位。证据见MOUNT_REEXAMINATION.md。

## 实测范围、素材与方法

MOUNT节点16的+2只有密集灰阶已采离散点得到复现，RAW_WB端点约为R585–752、G578–758、B590–773；点间空档、其他色相、其他节点与完整幅度继续标为模型外推。分段线性是工作假设，未加入统一RGB增益或色度修正。probe2现场分析已冻结并用于下述条件局部导数重拟合；仍未把局部导数当成完整色彩响应。
R8051894–1900由机主在2026-11-03口头确认原厂04、拍摄间不切配方或微调；白平衡为日光预设。继续作为整组独立留出，不混回既定训练目标。1895小色卡按普通场景。镜头为35mm f/2七片式Mandler设计复刻手动M口；探针f/5.6，自然七张光圈未知。采样避开边缘；既有中心区域标定、镜头暗角及色偏诊断见LENS_SPATIAL.md和素材身份表。
逐单元04标定、日期/光源整场景划分、数据清单、GR目标限制及05/06先前证据保留在REPORT_PREVIOUS_MODEL.md；其中历史18个发布Looks与旧构建清单已由本报告和新registry替代。此轮没有改变标定系数，不以七张新照片的分数冒充重新训练的标定改善。

## 求解器、复跑和封存

本轮共享模型全部实际运行SciPy TRF/SVD。色相罚项直接调用least_squares；紧凑模型在活跃参数列上解精确子问题。L0/L1没有调用guarded_normal普通分解，因此不借用1530项门为本适配器背书。每个fit回执绑定实际分支、起点清单、停止条件与代码快照；有限预算不代表全局最优。
批次清单、源版本和复跑步骤见RERUN_ROUND2.md；最终SHA256SUMS覆盖脚本、报告、输入与本地候选。全部派生数据只在被git忽略的local/，最终逐文件git check-ignore -v核对。没有访问卡、机主Studio或修改上游工具。本任务Scratch已删除，本地候选与证据保留；清理回执见cleanup.json。

可交后续DAT构建验证的现有槽位候选如下。所有分数均为电脑预测，28mm仅合成。
mount-a12：M9 STD、HNCS HiCon、Kodachrome25、HNCS LowSat、Vision3 500T、05 F-CC、06 F-CN
a12-50：HNCS HiCon、Tri-X 400、Velvia 50、Metropolis、03 HC BW、07 L-Chr、08 L-Viv
a12-28：Tri-X 400、Velvia 50、HNCS LowSat、01 GRPos、03 HC BW、06 F-CN、08 L-Viv
需要的机主素材：MOUNT probe2现场分析及后续多节点响应、更多原厂04整场景；28mm原厂04 RAW+JPG。清理状态见cleanup.json。

## probe2局部导数重拟合与剩余模型误差


节点8/19的+2及节点16的−2都有局部响应。35个MOUNT档案中，27项按测得方向做最多2码的局部重拟合，并由完整原声明/父候选投影起点重新跑exact；8项原生或共享控制记录逐字节保留。11条局部分支记录改变，主registry中原有105条记录SHA均未因此改变。
校准按输入亮度、色相、节点与符号分别估计Y/Cb/Cr导数，固定分段线性工作模型；节点8/19只允许正增量，16只允许负增量，不借用非同场资料强设正负对称。其它节点、完整矩阵、扇区与横轴冻结。原曲线距离探针A的差异、未采色相、节点间空档和量化相位仍是模型误差。没有一个连续全颜色范围得到定量验收。
主灰阶/彩块校准使用1935/1936/1937及1947/1948/1949，第二次P2扰动1951/1952/1953整帧留出；1940/1941/1942不同页面负向只作诊断。1944–1946继续unknown，不作04或拟合输入。21组照片42个原文件SHA已核对，镜头为机主给出的35mm f/2七片式Mandler复刻，实际f/5.6，EXIF光圈0保留为未报告。

| probe2验证，输出码RMSE | 原Y/Cb/Cr | 局部校准Y/Cb/Cr |
| --- | --- | --- |
| calibration gray | 0.1549 / 0.2966 / 0.2398 | 0.1177 / 0.2047 / 0.2118 |
| calibration coloured | 0.1746 / 0.4337 / 0.4377 | 0.0121 / 0.0349 / 0.0849 |
| heldout_repeat gray | 0.2074 / 0.3022 / 0.2438 | 0.1563 / 0.1813 / 0.2001 |
| heldout_repeat coloured | 0.2309 / 0.1950 / 0.6119 | 0.0296 / 0.2763 / 0.1295 |
| extra_negative_diagnostic gray | 0.0848 / 0.2206 / 0.2024 | 0.0738 / 0.1682 / 0.1811 |
| extra_negative_diagnostic coloured | 0.2237 / 0.3835 / 0.4345 | 0.2385 / 0.4806 / 0.4289 |

灰阶重复组改善，但彩块留出Cb与不同页面负向彩块仍有回退，因此此分支不替换主DAT准入模型和现有主候选。肤色Cb缺口、蓝块Cr反号保留原始观测与旧预测；没有通过一个RGB倍率或固定色度矩阵把反例隐藏。分支中的完整记录、条件预测、原L1分数、三种ROI/最近A包络、exact起点与SHA见probe2_refit_registry.json及local/probe2_local_response。
06的局部候选ISO200照片名义提升约0.0091百分点；16个输出量化假设下，增益从−0.0099至+0.0092百分点，方向不稳。该敏感性不模拟JPEG DCT/IDCT，也不命名真实ISP舍入算法。其余记录继续保留原128分支量化证据与probe2形状/输入分布诊断，均不等于量化相位已定。

实测范围只包括下列离散灰点，端点间空档和其他色相仍不算定量验收。

| 通道/节点 | RAW_WB受激灰点端点 | 首帧峰两侧灰点数 |
| --- | --- | --- |
| R/16 | 573.2190 至 752.0605 | 9 / 10 |
| G/16 | 580.4497 至 776.9773 | 6 / 10 |
| B/16 | 580.6073 至 767.2917 | 7 / 8 |
| R/8 | 106.2378 至 146.6737 | 5 / 4 |
| R/19 | 933.1118 至 1138.5412 | 4 / 5 |
| G/8 | 98.5608 至 137.9319 | 3 / 5 |
| G/19 | 928.3053 至 1151.2765 | 5 / 3 |
| B/8 | 105.4653 至 146.1165 | 3 / 4 |
| B/19 | 928.4816 至 1145.8327 | 2 / 5 |

| MOUNT配方，电脑预测 | 原L1照片% | 局部迭代照片% | 完整exact照片% | ROI/A包络% | 0.1/None门 | 场景门 |
| --- | --- | --- | --- | --- | --- | --- |
| Agfa LeBox | 79.6816 | 79.6891 | 79.6891 | 79.6647 至 79.6891 | REVIEW | 通过 |
| 千禧回声 A | 69.8213 | 69.8213 | 69.8213 | 69.8213 至 69.8213 | REVIEW | 通过 |
| 千禧回声 B | 共享或原生保留 | — | — | — | 不改记录 | — |
| Y2K Plady | 81.2216 | 81.2767 | 81.2767 | 81.2751 至 81.2856 | REVIEW | 通过 |
| Phocus Standard | 34.2966 | 34.2966 | 34.2966 | 34.2966 至 34.2966 | PASS | 通过 |
| Phocus Nature | 37.6512 | 37.6512 | 37.6512 | 37.6512 至 37.6512 | PASS | 通过 |
| ARRI Classic709 | 共享或原生保留 | — | — | — | 不改记录 | — |
| Kodak 2383 | 58.2959 | 58.2959 | 58.2959 | 58.2959 至 58.2959 | PASS | 回退 |
| Fuji 3513DI | 59.0547 | 59.0547 | 59.0547 | 59.0547 至 59.0547 | PASS | 回退 |
| Eterna BB | 93.4985 | 93.4985 | 93.4985 | 93.4985 至 93.4985 | PASS | 通过 |
| RED Film Bias | 72.3112 | 72.3112 | 72.3112 | 72.3112 至 72.3112 | PASS | 通过 |
| Classic Chrome | 92.1765 | 92.1080 | 92.1080 | 92.1037 至 92.1148 | PASS | 通过 |
| Classic Neg | 88.8595 | 89.0301 | 89.0301 | 89.0301 至 89.0510 | PASS | 通过 |
| Eterna | 88.1480 | 88.1480 | 88.1480 | 88.1480 至 88.1480 | PASS | 通过 |
| Acros | 97.6461 | 97.6461 | 97.6461 | 97.6461 至 97.6461 | PASS | 通过 |
| Leica Classic | 89.4281 | 89.4281 | 89.4281 | 89.4281 至 89.4281 | PASS | 通过 |
| RED IPP2 | 83.9307 | 83.9307 | 83.9307 | 83.9307 至 83.9307 | PASS | 通过 |
| M9 STD | 共享或原生保留 | — | — | — | 不改记录 | — |
| HNCS HiCon | 共享或原生保留 | — | — | — | 不改记录 | — |
| Tri-X 400 | 88.5780 | 88.5921 | 88.5921 | 88.5921 至 88.5921 | PASS | 回退 |
| Portra 400 | 78.2840 | 78.2840 | 78.2840 | 78.2840 至 78.2840 | PASS | 通过 |
| Velvia 50 | 共享或原生保留 | — | — | — | 不改记录 | — |
| Kodachrome25 | 83.5161 | 83.5829 | 83.5829 | 83.5829 至 83.5829 | PASS | 通过 |
| HNCS LowSat | 79.0290 | 79.0290 | 79.0290 | 79.0290 至 79.0290 | PASS | 通过 |
| Vision3 500T | 89.9365 | 89.9365 | 89.9365 | 89.9365 至 89.9365 | PASS | 通过 |
| instax mini | 共享或原生保留 | — | — | — | 不改记录 | — |
| Metropolis | 87.3300 | 87.3300 | 87.3300 | 87.3300 至 87.3300 | PASS | 通过 |
| 01 GRPos | 69.5460 | 69.5460 | 69.5460 | 69.5460 至 69.5460 | PASS | 回退 |
| 02 GRNeg | 56.8843 | 56.8095 | 56.8095 | 56.8095 至 56.8460 | REVIEW | 回退 |
| 03 HC BW | 96.2936 | 96.2768 | 96.2768 | 96.2768 至 96.2779 | PASS | 回退 |
| 04 Std | 共享或原生保留 | — | — | — | 不改记录 | — |
| 05 F-CC | 共享或原生保留 | — | — | — | 不改记录 | — |
| 06 F-CN | 84.7971 | 84.8062 | 84.8062 | 84.8062 至 84.8062 | PASS | 通过 |
| 07 L-Chr | 79.4159 | 79.4159 | 79.4159 | 79.4159 至 79.4159 | PASS | 回退 |
| 08 L-Viv | 74.9770 | 74.7975 | 74.7975 | 74.7975 至 74.8022 | REVIEW | 回退 |

Agfa LeBox与千禧回声A的附加门仍对第一次通过候选的固定参考，未把先前失败的训练最小值当成新的门基准。两项仍不新增，且本来不在g155c的10个Looks内。

本轮可交DAT构建验证的主清单仍为dat_candidate_lists.json的accepted；probe2条件分支没有自动混入。需要机主素材：同场A→R+16→R−16→G+16→G−16→B+16→B−16→A最少8张，及更多04整场景；28mm原厂04 RAW+JPG。未构建DAT，最终清理状态见cleanup.json。

## 同时满足release/test静态容量的选行方案


全量21条研究候选仍保留。只在MOUNT/50mm的14条现有槽位候选中枚举16,384个子集，保留全部5条已通过的优先共享曲线重做，03/Tri-X必须成对，不删除任何已发布Look。先最大化MOUNT相对整数训练损失下降，再最大化总下降；包装选行不读取照片。得到9条同时适合release/test静态字节额度的替换，其余条目保留g155c原记录。

| 单元 | 本方案换入 | 为容量保留g155c |
| --- | --- | --- |
| mount-a12 | M9 STD、HNCS HiCon、Kodachrome25、HNCS LowSat、Vision3 500T、05 F-CC、06 F-CN | 无 |
| a12-50 | Velvia 50、Metropolis | HNCS HiCon、Tri-X 400、03 HC BW、07 L-Chr、08 L-Viv |

| 包 | 预测DAT B | 预测主分配B | 静态余量B |
| --- | --- | --- | --- |
| release | 87624 | 104536 | 3076 |
| test | 90532 | 107456 | 156 |

这只关闭选行方案的静态字节超限，不关闭g156发现的代数或主机运行门。完整记录与SHA绑定在capacity_safe_profile.json，DAT构建时必须原字节采用并重新解包核对。没有创建DAT或修改代码以扩大容量。

可进下一轮DAT构建验证的容量方案见capacity_safe_profile.json；完整质量候选见dat_candidate_lists.json，28mm7项仍仅合成。需要机主素材为MOUNT同场正负16定标与更多04整场景、28mm原厂04 RAW+JPG；本任务清理状态见cleanup.json。
