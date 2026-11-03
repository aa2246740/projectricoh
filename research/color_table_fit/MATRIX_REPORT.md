# type-28 矩阵进入拟合（初步，不得写入固件）

2026-10-20。这份报告由 Opus worker 写成；它没有写文件的权限，由主代理落盘并删减。

主代理独立重跑了以下几项，数字与 worker 报的一致：
- `fit_matrix.py selftest`：PASS。
- `fit_matrix.py check2e`。
- `split_tone.py`：灰轴 3.50 / 2.59 / 1.65 / 0.20 / 0.25。
- `bw_mix.py`：用 GXR 03 帧做的模型比较。

`fit_sectors.py` 一字未改，默认输出的规范化哈希与基线相同。

## 结论

1. **显式链复现了 2e 实拍。**
   - 显式链：从 04 依次反解 stock 色表、矩阵 row 1 和 stock 曲线，再换新曲线正向。
   - 01/02/05/06 彩色块的 ΔE00 中位为 0.33/0.27/0.24/0.21，最大 0.86。
   - 旧拟合器的近似（H3：在 JPEG RGB 上逐通道反解曲线）是 0.87/0.55/0.89/1.41，最大 2.86。
   - 06 的 CbCr 色度比实测 1.241，显式链算出 1.240，H3 是 1.129。
2. **曲线之前没有颜色矩阵。**
   - 每帧用自己的白平衡 raw 直接正向，彩色块中位 0.27–0.41。
   - 反解出的传感器码与 raw 之间的最小二乘 3×3 近似单位阵：对角 0.982–0.997，非对角 ≤0.014。
   - GXR 的颜色链就是：白平衡 → 逐通道 type-26 曲线 → BT.601 矩阵 → 24 扇区表。
3. **旧拟合器对自己的初步色表过于乐观。** 同一张表放进显式模型：
   - Classic Neg. 从 1.85 变成 3.68；
   - Chrome 从 2.38 变成 2.68；
   - GR 正片从 2.98 变成 3.20。

   以后一律以显式链为准。
4. **矩阵里真正有用的是 Y 行。**
   - 中性保持的 Cb/Cr 行改动，等于在 (Cb, Cr) 上乘一个固定的 2×2，色表能逐色相复现它，两者近乎退化：只用色表复现色度行改动，中位误差 0.18。
   - Y 行能按色相改明度，这是色表做不到的。
5. **GR 正负片：Y 行 + 扇区的收益很大**（模型内的数字，上机未验证）。
   - 负片 LOO 中位从 6.06 降到 3.73。之前卡住的明度块全部解开：C5 从 11.27 到 1.43，B3 从 9.56 到 0.75，C3 从 9.08 到 1.80。合成环中位从 3.29 降到 1.96。
   - 正片 LOO 从 3.32 降到 2.18，合成环从 3.48 降到 2.83。
   - 拟合出的正片 Y 行是 0.21/0.89/−0.10。GR III Positive look 矩阵在线性光下的有效亮度行是 0.19/0.92/−0.11，两者几乎相同（推断为同一物理效果）。
6. **富士：Y 行先保持 stock。**
   - 用 DNG 场景拟合，Y 行会把红黄提亮。色卡 LOO 变好了（Chrome 从 3.30 降到 1.61），但不参与拟合的合成环反而变差（从 3.27 升到 4.16）。说明它学到的是这张卡或 DNG 矩阵特有的明度偏差。
   - 红黄的绝对明度定下来之前，富士推荐「只改扇区、用公布值」。
7. **03 真黑白在曲线之后按 Y 行混合**（证据强，属推断，T3a 可以确认）。

   在 GXR 自己的 03 帧上比较几种模型（|J| 误差，码）：
   - 曲线后按 stock Y 行加权：2e 中位 0.52、最大 1.43；2d 中位 0.39、最大 0.71。
   - 先转灰再过曲线：彩色块中位 4–6、最大 22。
   - 自由拟合出的曲线后权重是 0.305/0.570/0.125，就是 BT.601。

   GR IV 在曲线之前混合，GXR 只能在曲线之后用 Y 行去近似：
   - 拟合出的 [541, 288, 195] 让分箱 RMS 从 8.91 降到 7.10，最大误差从 81.5 降到 55.6；
   - 但彩色块中位从 9.40 升到 11.80；
   - 分帧拟合差别很大，色相覆盖也几乎只有橙黄。

   收益有限，不算确定。
8. **Classic Neg. 的分色**（灰轴 ΔE00 中位）：

   | 方案 | 中位 |
   |---|---|
   | 不分色 | 3.50 |
   | (b0) 矩阵斜坡，偏置保持 stock | 2.59 |
   | (b) 矩阵斜坡，偏置也调 | 1.65 |
   | (a) 三条通道曲线 | 0.20 |
   | (a) + (b) | 0.25 |

   - (b) 要求 Cb/Cr 偏置偏离 stock，拟合结果为 127/126。表文件 v2 草案原本会拒绝这种行，要放宽成有界范围。
   - 固件按鲜艳度缩放斜率，但不缩放偏置，所以鲜艳度不在 5 档时，斜坡的支点会移动。
   - (a) 要写 T 块，有被永久保存的风险，见 `research/split_tone/REPORT.md`，未获批。
9. **上机测试行，预测的变化都很大，容易判读。**
   - **T3b**：彩色配方上把 Y 行的 R、B 权重对调。预测 C3、B3、C4 暗 5–8 L\*，C1、B2、C6 亮约 5–6 L\*，CbCr 完全不变。如果画面与 stock 在漂移范围内一致，说明矩阵写入没有生效。这项最直接、风险最低，先做。
   - **T3a**：03 的 Y 行改成 0/1024/0（只取绿）。配 GR IV 候选曲线时，彩色块 |ΔJ| 中位 16、最大 55；灰块几乎不动。如果没有变化，说明黑白在矩阵之前就转了灰。

## 推荐（都是初步，色相环拍完后要用新模型重跑）

| 配方 | 推荐变体 | 文件（local/） |
|---|---|---|
| 01 GR 正片 | Y 行 + 扇区 | `gr3_positive_matrix.json` |
| 02 GR 负片 | Y 行 + 扇区 | `gr3_negative_matrix.json` |
| 05 Classic Chrome | 只改扇区，公布值 | `fuji_classic_chrome_matrix.json` |
| 06 Classic Neg. | 只改扇区，公布值；分色方案 (b) 另存 | `fuji_classic_neg_matrix.json`、`fuji_classic_neg_splittone_b_matrix.json` |
| 03 HC B&W | Y 行 [541, 288, 195]，待定 | `hcbw_03_matrix.json` |

- 每个文件都含 row 1 和 row 2。row 2 由 row 1 推出：Y 行原样复制，Cb、Cr 行分别乘 stock 比例 0.9287、0.9678，再保持行和。
- 每个文件都标着「PRELIMINARY … DO NOT WRITE TO FIRMWARE」，`firmware_ready = false`。
- 所有色度系数都 ≤ 1279。除分色文件的偏置外，没有触发其他拒绝条件。

## 命令

```bash
python3 -I research/color_table_fit/fit_matrix.py selftest
python3 -I research/color_table_fit/fit_matrix.py check2e
python3 -I research/color_table_fit/fit_matrix.py fit --target gr3:negative --scene published   # 每个目标 8–13 分钟
python3 -I research/color_table_fit/fit_matrix.py emit
python3 -I research/color_table_fit/bw_mix.py
python3 -I research/color_table_fit/split_tone.py
```

色相环真片到了以后，在 `fit_matrix.py` 的 `Setup` 里把模型路径换成 `ring_model.json`，全部重跑。

## 局限

- 全部结果都建立在只有 18 块色卡的部分扇区模型上。合成环检验的是参数能否外推，检验不了模型本身。
- LOO 选出的正则常落在网格最弱的一端。色卡块太少，LOO 本身噪声也大。
- Y 行的偶极很强：GR 负片合成环上的 |ΔL\*| 中位约 3.5，最大 7.8。这是目标本身要求的效果，但会明显改变饱和色的明暗，上机要专门看肤色、植物和天空。
- 未知：
  - 节点的准确位置和满权重增益；
  - 红黄的绝对明度；
  - u_m；
  - 鲜艳度不等于 100% 时固件怎么取整；
  - C+0xDA 的含义；
  - GR IV 到 GXR 的相机映射误差。

## 文件

- 代码：`matrix_model.py`、`fit_matrix.py`、`bw_mix.py`、`split_tone.py`。
- 结果在 `local/`，已被 gitignore：
  - `matrix_check2e.json`、`mfit_*`；
  - 各配方的 `*_matrix.json`、`test_T3a_matrix.json`、`test_T3b_matrix.json`；
  - `bw_mix.json`、`split_tone.json`、`matrix_selftest.json`。
