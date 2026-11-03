# 富士目标改由 DNG 推算场景色：工具已接入，红黄色块的明度要靠独立参照才能定

2026-10-20。这份报告由 Opus worker 写成。它没有写文件的权限，由主代理落盘。

主代理独立复核了两项：
- `dng_scene.py --selftest` 结果为 PASS。
- 重跑默认的 `fit_sectors.py --preliminary`，去掉耗时字段 `seconds` 后，6 个输出与改动前的基线规范化哈希全部相同。

## 结论

1. **两条路径都已接入 `fit_sectors.py`，默认行为不变。**
   - DNG 推场景色的路径：富士目标 = LUT(本帧 DNG 测得的场景 XYZ)，可用于色卡，也可用于色相环。
   - 新选项：`--chart-scene-source {published,dng}`、`--ring-scene-source {design,dng}`、`--dng-white {as_shot,in_frame}`、`--dng-matrix {interp,cm1,cm2}`。
   - 默认产出与原来逐字节一致，只有耗时字段 `seconds` 不同。
2. **在 2e 色卡上，用 DNG 目标拟出的 Chrome/Neg 色表，p90 和留一法都变差了，差在明度。**
   - B3、C3、C5、B1、B6 这几块红黄色，DNG 推出来比 X-Rite 公布值亮 5–8 L\*。
   - 扇区表改不了明度。
   - 只看色度和色相（L\* 对齐），新表中位 1.25–1.52，用公布值时约 1.0，略松。
3. **这 5–8 L\* 的偏差来源分不清。** 可能是 DIOPTIX 色卡和 X-Rite 不同，也可能是 Ricoh 的 DNG 矩阵本身的误差：3×3 矩阵满足不了 Luther 条件。
   - 两次拍摄的 B3、C3 偏差几乎一样。2e 是 +6.68/+5.47；2d 是 +6.67/+5.70，那次色卡转了 180°，光源也不同（4223 K）。所以偏差跟光谱有关，不是光照不匀造成的。
   - 要分开这两种可能，需要一个独立参照，见文末「要定下来需要什么」。DIOPTIX 没有公布这张卡的参考 Lab 值，网上也查不到。
4. **只靠 Ricoh 的单份矩阵，影响有多大**：只用 CM1 或只用 CM2 时，富士目标变化的中位是 1.0 ΔE00，最大 ≤1.81。这大约是「公布值换成 DNG」那一步变化量的 1/3～1/2。
5. **白点怎么选，影响和换数据源一样大。** as_shot 和 in_frame 两种白点之间，|ΔA| 最多 7，转角最多差 8.5–11°。
   - 这次色卡是自动白平衡，所以 as_shot 带偏色。
   - 色相环按 README 要先对参考白做手动白平衡，那样两种白点应当几乎一致。
6. **色相环这条路径已经端到端跑通。**
   - 合成数据：DNG 环目标和设计目标的中位差 0.061 ΔE00。
   - 真屏幕帧（2026-10-16 拍的 MacBook 屏幕色卡）：L\* 对齐后，DNG 场景色和名义 sRGB 中位差 1.39–1.62，最大 3.85。这大约就是真片到来后环目标会被修正的幅度。
   - 明度随位置偏差最多 17 L\*，像是屏幕均匀性、暗角或反光。所以看环的结果要用 L\* 对齐的指标。
7. **新发现：GXR 的 JPEG 比 DNG 的默认裁切整体右移 1 px**，即 raw_x = jpeg_x − 1。
   - 9 张 2e 帧的偏移在 −0.989 到 −1.020 px 之间。
   - 加上偏移后，残差 ≤0.004 px。

## 关键数字

**R8051160 的 DNG Lab 对 X-Rite 公布值**（D50，D4 对齐公布的 Y，中位/p90/最大）

| 白点 | 中性块 | 彩色块 | L\* 对齐后的彩色块 |
|---|---|---|---|
| in_frame（D2–D4） | 1.54/3.18/3.66 | 3.04/5.81/7.52 | 1.80/4.08/4.90 |
| as_shot | 5.00/7.14/7.77 | 3.06/6.61/6.91 | 2.40/4.18/6.86 |

**色表拟合**（色卡彩色块，中位/p90/最大）

| 版本 | 新表 | 留一法 | L\* 对齐后的新表 |
|---|---|---|---|
| Chrome 公布值 | 2.38/3.51/4.96 | 3.24/6.06/7.38 | 1.04/1.89/3.81 |
| Chrome DNG as_shot | 2.99/7.83/9.41 | 3.70/8.60/11.03 | 1.52/3.46/4.46 |
| Chrome DNG in_frame | 2.68/7.45/9.19 | 3.98/8.46/10.10 | 1.25/3.41/4.77 |
| Neg 公布值 | 1.85/5.10/5.66 | 4.57/7.32/12.05 | 0.97/2.63/4.07 |
| Neg DNG as_shot | 2.78/6.09/8.37 | 4.15/9.92/13.04 | 1.35/4.92/6.23 |
| Neg DNG in_frame | 2.42/6.97/8.75 | 3.87/9.83/13.16 | 1.25/5.00/7.11 |

两种目标下拟合出的色表字节：Chrome 24 个字全变，|ΔA| ≤9，转角最多差 6.8°；Neg 变了 23 个字，|ΔA| ≤11，转角最多差 13.2°。

## 和通道混合的关系

扇区表改不了明度，所以只拟扇区表时，明度这个问题不影响色表。

但 type-28 矩阵的 Y 行可以按色相改明度（见 `research/channel_mixing/REPORT.md`）。一旦把矩阵加进拟合，红黄色到底该多亮就直接决定矩阵怎么写。这件事必须先定，否则矩阵可能把红色往错的方向改。

## 要定下来需要什么（任选一项）

1. 用分光仪测一次 DIOPTIX 色卡。
2. 在同一光源下，用 GXR 拍一张正品 X-Rite/Calibrite ColorChecker Classic。
3. （主代理补充，零成本）在同一光源下，用另一台机身拍这张 DIOPTIX 色卡的 RAW，比如 iPhone 的 ProRAW。两台机身的矩阵彼此独立：
   - 两台都看到红色偏亮约 6 L\*，偏差多半来自色卡；
   - 只有 GXR 偏亮，多半是 Ricoh 矩阵的问题。

   这不是严格的参照，但足以判断偏差出在哪一边。

## 命令

```bash
python3 -I research/color_table_fit/dng_scene.py --selftest
python3 -I research/color_table_fit/dng_chart_check.py
python3 -I research/color_table_fit/ring_dng_check.py
python3 -I research/color_table_fit/compare_scene_runs.py
python3 -I research/color_table_fit/fit_sectors.py --preliminary --chart-scene-source dng --dng-white as_shot
```

色相环真片到了以后，先跑 analyze_ring，再运行：

```bash
python3 -I research/color_table_fit/fit_sectors.py --model research/hue_ring/local/ring_model.json \
  --ring-patches research/hue_ring/local/ring_patches.json --ring-iso 100 \
  --ring-scene-source dng --ring-dir <真片目录> \
  --target fuji:classic_chrome --target fuji:classic_neg [--chart-scene-source dng] [--u-m X]
```

## 局限

- 目标就定义为 FujiLUT(Ricoh 矩阵 × raw)，矩阵有任何偏差都会原样进入目标。
- 色卡和拍摄都只有一次，跨场次差约 1.65 ΔE00，单次测量不能当真值。
- 还是部分扇区模型，所以结果是 PRELIMINARY，不能写入固件。
- 不支持压缩或分块的 DNG。遮罩 ROI 只支持 1:1 比例，GXR 正好是 1:1。

## 文件

- 新文件：`dng_scene.py`、`dng_chart_check.py`、`ring_dng_check.py`、`compare_scene_runs.py`。
- 改动：`fit_sectors.py`，加了新选项，默认行为不变。
- 输出放在 `local/`，已被 gitignore。
- 捕获文件读取前后都校验了哈希，32/32 一致。
