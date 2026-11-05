# 午间分析 noon-20261104

已提取 70 帧，其中屏幕 70 帧、无 RAW 的合成/页面图 0 帧。耗时 314.2 秒。

绑定 g156 test DAT SHA-256 `0f4f26d4cd3669915b41ce8e38260a61c60c590e2c581cb72e93f52a2ac631f7`。照片本身不能证明安装的是这个 DAT。

主测为每块中央 40%，另算 30% / 50%。DE00 比较实拍 JPEG 与现行模型预测；正 ΔL 为偏亮，正 ΔC 为偏艳，正色相角沿 Lab 逆时针。

## 每条配方、每页

| 配方 / 页或场景 | n | DE00 中位数 | P95 | 最差块 | ΔL | ΔC | 色相角偏差 | 条件 |
| --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |

OPEN: 本批没有可比较的配方实拍；页面识别或 ramp 提取不等于配方验收。

## 肤色、蓝色、绿叶与符号缺口

| 配方 / 页 | 区域 | n | DE00 中位数 | P95 | ΔL | ΔC |
| --- | --- | ---: | ---: | ---: | ---: | ---: |

肤色 Cb：方向反号 0 块，其中 0 块缺参照或有设置冲突，只作为条件结果。同号 0 块，弱分量未判 0 块。

蓝色 Cr：方向反号 0 块，其中 0 块缺参照或有设置冲突，只作为条件结果。同号 0 块，弱分量未判 0 块。

这里比较完整配方相对 04 的响应，不能单独归因于 probe3 的 R±/B± 节点机制。符号门使用三 ROI 与独立 04 漂移包络，再留 0.25 输出码诊断余量；这不是置信区间。缺独立尾 04 或分量落在漂移、量化范围内时，符号结论仍为条件结果。

## 顺序与响应

| 帧 | 顺序默认 | 响应校验 | 余量 DE00 | 状态 |
| --- | --- | --- | ---: | --- |
| R8051966 | 04 Std | unknown |  | unknown，保留默认假设 |
| R8051967 | 04 Std | unknown |  | unknown，保留默认假设 |
| R8051968 | 04 Std | unknown |  | unknown，保留默认假设 |
| R8051969 | 04 Std | unknown |  | unknown，保留默认假设 |
| R8051970 | 04 Std | unknown |  | unknown，保留默认假设 |
| R8051971 | 04 Std | unknown |  | unknown，保留默认假设 |
| R8051972 | 04 Std | unknown |  | unknown，保留默认假设 |
| R8051973 | 04 Std | unknown |  | unknown，保留默认假设 |
| R8051975 | 05 F-CC | unknown |  | unknown，保留默认假设 |
| R8051976 | 05 F-CC | unknown |  | unknown，保留默认假设 |
| R8051977 | 05 F-CC | unknown |  | unknown，保留默认假设 |
| R8051978 | 05 F-CC | unknown |  | unknown，保留默认假设 |
| R8051979 | 05 F-CC | unknown |  | unknown，保留默认假设 |
| R8051980 | 05 F-CC | unknown |  | unknown，保留默认假设 |
| R8051981 | 05 F-CC | unknown |  | unknown，保留默认假设 |
| R8051982 | 06 F-CN | unknown |  | unknown，保留默认假设 |
| R8051983 | 06 F-CN | unknown |  | unknown，保留默认假设 |
| R8051984 | 06 F-CN | unknown |  | unknown，保留默认假设 |
| R8051985 | 06 F-CN | unknown |  | unknown，保留默认假设 |
| R8051986 | 06 F-CN | unknown |  | unknown，保留默认假设 |
| R8051987 | 06 F-CN | unknown |  | unknown，保留默认假设 |
| R8051988 | 06 F-CN | unknown |  | unknown，保留默认假设 |
| R8051989 | 06 F-CN | unknown |  | unknown，保留默认假设 |
| R8051990 | M9 STD | unknown |  | unknown，保留默认假设 |
| R8051991 | M9 STD | unknown |  | unknown，保留默认假设 |
| R8051992 | M9 STD | unknown |  | unknown，保留默认假设 |
| R8051993 | M9 STD | unknown |  | unknown，保留默认假设 |
| R8051994 | M9 STD | unknown |  | unknown，保留默认假设 |
| R8051995 | M9 STD | unknown |  | unknown，保留默认假设 |
| R8051996 | M9 STD | unknown |  | unknown，保留默认假设 |
| R8051997 | M9 STD | unknown |  | unknown，保留默认假设 |
| R8051998 | HNCS HiCon | unknown |  | unknown，保留默认假设 |
| R8052000 | HNCS HiCon | unknown |  | unknown，保留默认假设 |
| R8052002 | HNCS HiCon | unknown |  | unknown，保留默认假设 |
| R8052004 | HNCS HiCon | unknown |  | unknown，保留默认假设 |
| R8052006 | Kodachrome25 | unknown |  | unknown，保留默认假设 |
| R8052007 | Kodachrome25 | unknown |  | unknown，保留默认假设 |
| R8052008 | Kodachrome25 | unknown |  | unknown，保留默认假设 |
| R8052009 | Kodachrome25 | unknown |  | unknown，保留默认假设 |
| R8052010 | Kodachrome25 | unknown |  | unknown，保留默认假设 |
| R8052011 | Kodachrome25 | unknown |  | unknown，保留默认假设 |
| R8052012 | Kodachrome25 | unknown |  | unknown，保留默认假设 |
| R8052013 | Kodachrome25 | unknown |  | unknown，保留默认假设 |
| R8052014 | HNCS LowSat | unknown |  | unknown，保留默认假设 |
| R8052015 | HNCS LowSat | unknown |  | unknown，保留默认假设 |
| R8052016 | HNCS LowSat | unknown |  | unknown，保留默认假设 |
| R8052017 | HNCS LowSat | unknown |  | unknown，保留默认假设 |
| R8052018 | HNCS LowSat | unknown |  | unknown，保留默认假设 |
| R8052019 | HNCS LowSat | unknown |  | unknown，保留默认假设 |
| R8052020 | HNCS LowSat | unknown |  | unknown，保留默认假设 |
| R8052021 | HNCS LowSat | unknown |  | unknown，保留默认假设 |
| R8052022 | Vision3 500T | unknown |  | unknown，保留默认假设 |
| R8052023 | Vision3 500T | unknown |  | unknown，保留默认假设 |
| R8052024 | Vision3 500T | unknown |  | unknown，保留默认假设 |
| R8052025 | Vision3 500T | unknown |  | unknown，保留默认假设 |
| R8052026 | Vision3 500T | unknown |  | unknown，保留默认假设 |
| R8052027 | Vision3 500T | unknown |  | unknown，保留默认假设 |
| R8052028 | Vision3 500T | unknown |  | unknown，保留默认假设 |
| R8052029 | Vision3 500T | unknown |  | unknown，保留默认假设 |
| R8052030 | 04 Std | unknown |  | unknown，保留默认假设 |
| R8052031 | 04 Std | unknown |  | unknown，保留默认假设 |
| R8052032 | 04 Std | unknown |  | unknown，保留默认假设 |
| R8052033 | 04 Std | unknown |  | unknown，保留默认假设 |
| R8052034 | 04 Std | unknown |  | unknown，保留默认假设 |
| R8052035 | 04 Std | unknown |  | unknown，保留默认假设 |
| R8052036 | 04 Std | unknown |  | unknown，保留默认假设 |
| R8052037 | 04 Std | unknown |  | unknown，保留默认假设 |
| R8052038 | 04 Std | unknown |  | unknown，保留默认假设 |
| R8052039 | 04 Std | unknown |  | unknown，保留默认假设 |
| R8052040 | 04 Std | unknown |  | unknown，保留默认假设 |

## 提取与 OPEN

| 帧 | 类型 | 页面 | 区域数 | RAW |
| --- | --- | --- | ---: | --- |
| R8051966 | screen | T1 | 48 | 有 |
| R8051967 | screen | T2 | 48 | 有 |
| R8051968 | screen | T3 | 48 | 有 |
| R8051969 | screen | T4 | 48 | 有 |
| R8051970 | screen | V1 | 48 | 有 |
| R8051971 | screen | V2 | 48 | 有 |
| R8051972 | screen | V3 | 48 | 有 |
| R8051973 | screen | V4 | 48 | 有 |
| R8051975 | screen | T1 | 48 | 有 |
| R8051976 | screen | T2 | 48 | 有 |
| R8051977 | screen | T3 | 48 | 有 |
| R8051978 | screen | T4 | 48 | 有 |
| R8051979 | screen | V1 | 48 | 有 |
| R8051980 | screen | V2 | 48 | 有 |
| R8051981 | screen | V3 | 48 | 有 |
| R8051982 | screen | V4 | 48 | 有 |
| R8051983 | screen | T1 | 48 | 有 |
| R8051984 | screen | T2 | 48 | 有 |
| R8051985 | screen | T3 | 48 | 有 |
| R8051986 | screen | T4 | 48 | 有 |
| R8051987 | screen | V1 | 48 | 有 |
| R8051988 | screen | V2 | 48 | 有 |
| R8051989 | screen | V3 | 48 | 有 |
| R8051990 | screen | V4 | 48 | 有 |
| R8051991 | screen | T1 | 48 | 有 |
| R8051992 | screen | T2 | 48 | 有 |
| R8051993 | screen | T3 | 48 | 有 |
| R8051994 | screen | T4 | 48 | 有 |
| R8051995 | screen | V1 | 48 | 有 |
| R8051996 | screen | V2 | 48 | 有 |
| R8051997 | screen | V3 | 48 | 有 |
| R8051998 | screen | V4 | 48 | 有 |
| R8052000 | screen | T2 | 48 | 有 |
| R8052002 | screen | T4 | 48 | 有 |
| R8052004 | screen | V2 | 48 | 有 |
| R8052006 | screen | V4 | 48 | 有 |
| R8052007 | screen | T1 | 48 | 有 |
| R8052008 | screen | T2 | 48 | 有 |
| R8052009 | screen | T3 | 48 | 有 |
| R8052010 | screen | T4 | 48 | 有 |
| R8052011 | screen | V1 | 48 | 有 |
| R8052012 | screen | V2 | 48 | 有 |
| R8052013 | screen | V3 | 48 | 有 |
| R8052014 | screen | V4 | 48 | 有 |
| R8052015 | screen | T1 | 48 | 有 |
| R8052016 | screen | T2 | 48 | 有 |
| R8052017 | screen | T3 | 48 | 有 |
| R8052018 | screen | T4 | 48 | 有 |
| R8052019 | screen | V1 | 48 | 有 |
| R8052020 | screen | V2 | 48 | 有 |
| R8052021 | screen | V3 | 48 | 有 |
| R8052022 | screen | V4 | 48 | 有 |
| R8052023 | screen | T1 | 48 | 有 |
| R8052024 | screen | T2 | 48 | 有 |
| R8052025 | screen | T3 | 48 | 有 |
| R8052026 | screen | T4 | 48 | 有 |
| R8052027 | screen | V1 | 48 | 有 |
| R8052028 | screen | V2 | 48 | 有 |
| R8052029 | screen | V3 | 48 | 有 |
| R8052030 | screen | V4 | 48 | 有 |
| R8052031 | screen | T1 | 48 | 有 |
| R8052032 | screen | T2 | 48 | 有 |
| R8052033 | screen | T3 | 48 | 有 |
| R8052034 | screen | T4 | 48 | 有 |
| R8052035 | screen | V1 | 48 | 有 |
| R8052036 | screen | V2 | 48 | 有 |
| R8052037 | screen | V3 | 48 | 有 |
| R8052038 | screen | V4 | 48 | 有 |
| R8052039 | screen | T1 | 48 | 有 |
| R8052040 | screen | V1 | 48 | 有 |

屏幕周期纹诊断：43/3360 个中央 ROI 触发既有频谱门。该门只提示条纹或摩尔纹，不自动改颜色，也不把它当成厂商规格。逐块频谱与 4×4 子区域统计在 local 帧明细中。

- OPEN: R8051974 提取失败，原因详见 local summary.json。

- OPEN: R8051999 提取失败，原因详见 local summary.json。

- OPEN: R8052001 提取失败，原因详见 local summary.json。

- OPEN: R8052003 提取失败，原因详见 local summary.json。

- OPEN: R8052005 提取失败，原因详见 local summary.json。

- OPEN: R8052041 提取失败，原因详见 local summary.json。

- OPEN: R8052042 提取失败，原因详见 local summary.json。

- OPEN: R8052043 提取失败，原因详见 local summary.json。

- OPEN: R8052044 提取失败，原因详见 local summary.json。

- OPEN: R8052045 提取失败，原因详见 local summary.json。

- OPEN: R8052046 提取失败，原因详见 local summary.json。

- OPEN: R8052047 提取失败，原因详见 local summary.json。

- OPEN: R8052048 提取失败，原因详见 local summary.json。

- OPEN: R8052049 提取失败，原因详见 local summary.json。

- OPEN: 存在提取失败帧，自动分组不能证明没有缺帧；请在 manifest 逐帧确认设置。

- OPEN: 屏幕第 2 组页面顺序/完整性不符，需核对 manifest。

- OPEN: 屏幕第 3 组页面顺序/完整性不符，需核对 manifest。

- OPEN: 屏幕第 4 组页面顺序/完整性不符，需核对 manifest。

- OPEN: 屏幕第 5 组页面顺序/完整性不符，需核对 manifest。

- OPEN: 屏幕第 6 组页面顺序/完整性不符，需核对 manifest。

- OPEN: 屏幕第 7 组页面顺序/完整性不符，需核对 manifest。

- OPEN: 屏幕第 8 组页面顺序/完整性不符，需核对 manifest。

- OPEN: 有失败帧，未确认设置的帧不出具配方统计；用 intake-manifest.json 逐帧确认。

- OPEN: 没有任何配方的有效对比块，不能出具实拍预测误差。

RAW 逐块扣黑并按 AsShotNeutral 处理，用于相同块的输入漂移校正。RAW 的 BT.601 数值只是线性传感器代理，不是相机内部 YCbCr，不对它和 JPEG 直接声称颜色准确度。

屏幕 CSS 数值只用于识页，P3-D65 屏幕、局部调光和摩尔纹不按网页标称 Lab 校准。山寨色卡不使用印刷值。MOUNT 参考仍是迁移模型，照片误差报告才是本次待测结果。

逐块数值、输入哈希、552 B 记录和 ROI 叠图均在 [local 明细](local/noon-20261104/summary.json)。
