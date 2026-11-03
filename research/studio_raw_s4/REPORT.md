可以交复审

# S4：RAW 读取与导出基础（studio-raw-s4-r1）

范围：ARCHITECTURE §14 的 S4，对应 M1 验收 6、7 和 M2 基础。没有碰 `engine/`、`camdata/`，没有访问任何真实挂载的卡，没有联网，没有 git commit，没有子代理，同时最多 1 个测试进程。

## 结果一句话

只有 RAW 的照片现在能导出（"中性预览"：白平衡后的线性数据 → 标准 sRGB 伽马，不加配方），JPEG 和 PNG 都行，带 EXIF 和 sRGB ICC，支持裁切和拉直。全套 177 个测试通过（原有测试一个都没改；其中 E0 任务当时在磁盘上的测试也在内）。

## 交付物

| 位置 | 内容 |
|---|---|
| `studio/src/gxr_studio/raw/tiff.py` | 来自 `analyze_capture.Tiff`（SHA `9e20f581…`），`assert` 换成 `ValueError` |
| `…/raw/dng.py` | 来自 `dng_scene.Dng`（SHA `f0e8dd88…`）：SubIFD、12/16 位条带、黑电平（含重复图案、DeltaH/V）、白电平、线性化表、CFA、ActiveArea、DefaultCrop、AsShotNeutral、Orientation、EXIF 摘要。新增整块读取 `normalised_block`、窗口自检、`open_dng`（所有解析失败统一成 `RawDecodeError`） |
| `…/raw/codes.py` | 白平衡码值（归一化 ÷ AsShotNeutral × 4095，不夹紧，不加曝光，BaselineExposure 不应用）、**半分辨率 2×2 合并**、`orient_array` |
| `…/raw/demosaic.py` | **全分辨率去马赛克**：Malvar–He–Cutler 5×5，条带式（默认 256 行），条带版与整幅版逐位相同 |
| `…/raw/render.py` | `Renderer` 接口 + `NEUTRAL`（中性预览）；`render_full` / `render_half` |
| `…/raw/PROVENANCE.json` | 来源路径与 SHA-256，每个文件的改动说明 |
| `studio/src/gxr_studio/export.py` | JPEG/PNG、尺寸档/质量档、`render_raw`、`export_shot(…, renderer=NEUTRAL)` |
| `studio/src/gxr_studio/api/routes.py` | 导出接口新增 `format`、`size`、`quality_tier`，返回新增 `format`、`render`、`render_label` |
| `studio/README.md` | 目录和接口表更新 |
| `studio/tests/raw_support.py`、`test_raw.py`、`test_raw_export.py` | 合成 DNG 写入器；25 + 11 个新测试 |
| `research/studio_raw_s4/measure.py`、`measure.json` | 速度和诊断数字（只读样本） |

## 数值口径（和研究代码的对照）

- 白平衡码值的算式与 `model_adapter.Model.raw`、`camera.scene()` 一致：同色取均值 ÷ AsShotNeutral × 4095。
- 测试 `test_real_sample_matches_research_reader_and_half_res_arithmetic`（真实样本 R8051144，SHA `c8b6fd6d…`）：
  - 字段（尺寸、位深、CFA、裁切、白电平、neutral 等）与研究 `Dng` 完全相等；原始平面逐元素相等；
  - 20 万个随机点的 `normalised_at` 与整块读取逐位相等；
  - 半分辨率（float64 路径）对研究算式整幅最大差 < 1e-9；默认 float32 路径 < 5e-4 码。
- 合成 DNG 上同样的对照覆盖了 5 种裁切起点（含奇数起点，CFA 相位 G/B/R/G 和别的相位）、黑电平图案 + DeltaH/V、线性化表、12/16 位。
- 真实样本已核实的事实：原始 4304×2862、12 位大端、CFA `[[R,G],[G,B]]`、裁切 (8,7)+4288×2848、裁切起点相位 `[[G,B],[R,G]]`、白电平 4095、黑电平 0、无线性化表、Orientation 1、neutral = (0.645161, 1, 0.574712)。

## 去马赛克算法的选择（研究里没有）

选 MHC 5×5：线性滤波，输入输出都在线性码值域；比双线性少拉链和假色；比方向自适应算法简单可复现；ARCHITECTURE §2.3 已经这样写定。白平衡在去马赛克之前做（滤波里有跨通道项）。输出不夹紧，由后面的链去夹。边界用镜像延拓（保持 Bayer 相位）。

合成测试：纯色场整幅（含边界）精确还原；线性渐变在内部误差 < 1.5 码；每个位置自己颜色的采样值原样保留；条带与整幅逐位相同（条带高 4/6/16/256）。

## 数字（M 系列 Mac，单张真实样本，取 2–3 次最快；不是 M2 验收数据）

| 项目 | 秒 |
|---|---|
| 打开 DNG | 0.011 |
| 半分辨率码值 | 0.07 |
| 半分辨率中性渲染（2144×1424） | 0.13 |
| 全分辨率中性渲染（4288×2848） | 0.78 |
| 导出 JPEG q95 原始尺寸 | 0.97（2.76 MB） |
| 导出 XPan 裁切 + 2048 长边 JPEG q85 | 0.90（143 KB） |
| 导出 PNG 原始尺寸 | 1.71（14.9 MB） |

**U3 的"代码域"版本（不是 ΔE00）：** 全分辨率去马赛克后做 2×2 平均，对半分辨率合并，在 200–3500 码的区域，相对差 中位 0.93%、p90 3.3%、p99 9.2%；全图均值比 1.000002。ΔE00 版本需要 M2 的配方链，还没量。

**中性预览比相机 JPG 暗：** 平均亮度 114.4 对 162.2（8 位灰度）。原因是相机 JPG 烤进了色调曲线和色彩处理，中性预览只有标准 sRGB 伽马，也不应用 BaselineExposure（+0.3 EV，按 ARCHITECTURE §5.1 阶段 3，现有链是在不应用它的前提下标定的）。颜色是相机原生的，偏淡。这是设计内的结果，不是缺陷；它正是文件名里带 `_neutral` 和 EXIF 里写明的原因。

## 导出

- 格式：`jpeg`（质量 1–100，q≥90 用 4:4:4）、`png`（无损，质量只校验）。
- 档：尺寸 large/medium/small/original = 3000/2048/1600/原始（Lanczos，不放大）；质量 high/medium/low = 95/85/70。API 既收 `long_edge`/`quality` 数字，也收档名，档名盖过数字。
- EXIF（只有 RAW）：厂商/型号/DateTime、EXIF 子目录（去掉 MakerNote，ISO、快门、光圈、拍摄时间等保留）、镜头名取自 UniqueCameraModel（"GR LENS A12 50mm F2.5 MACRO"）、方向改 1、尺寸改成输出尺寸、`Software = GXR Studio`、`ImageDescription = "GXR Studio neutral-preview: white-balanced linear sensor data to sRGB, no recipe applied"`；JPEG 和 PNG 都带 sRGB ICC。完整 EXIF 写不进去时退回只带日期/ISO/镜头（沿用 M1 做法）。
- 文件名：`原名_gxr_neutral.jpg|png`（相机 JPG 作源时仍是 `原名_gxr.jpg|png`），重名加 `-2`、`-3`。
- 裁切与拉直：走与 JPG 源完全同一段代码（`_finish`），在转正后的 8 位 sRGB 图上做；XPan 在真实样本上得到 4288×1583。
- 有配对 JPG 时仍用相机 JPG（不变）。

## 给 S6 的接口缝

`raw.render.Renderer(id, label, filename_tag, calibrated, display)`：`display` 把白平衡码值 float32 (h,w,3)（0..4095，不夹紧）变成 uint8 sRGB，必须逐像素、与位置无关（这样条带渲染与整幅一致）。把它传给 `export_shot(..., renderer=…)` 或 `render_full(dng, renderer)` 即可，导出代码、文件名标记、API 的 `render` / `render_label` 都不用改。测试 `test_renderer_plugs_into_export` 用一个假的配方渲染器验证了这一点。曝光、白平衡偏移、曲线要放进 `display` 之前的链里，目前接口只覆盖"码值 → 显示"这一段。

## 与要求的差别 / 需要复审者注意的地方

1. **"不再返回 409"的边界：** 只有 RAW 且 RAW 能解码 → 导出成功。RAW 读不出来（非 GXR 写法、压缩、被截断，或合成假卡里那种没有 CFA 的假 DNG）仍然是 409 `no_jpg_source`，消息改成了白话"这份 RAW 暂时读不出来"。这样原有的两个测试（`test_export_errors`、`test_batch_export_by_date`，用的是没有 CFA 的合成 DNG）不需要改动就继续通过。新测试覆盖了"可解码的只有 RAW 导出成功"。
2. **前端还在挡：** `studio/web/assets/export.js` 写死了"只有 RAW 暂时不能导出"并提前跳过这些照片。`web/` 不在本任务的可写范围内，没改。接口已经可用；前端需要另一个小任务去掉这个提示，并把返回里的 `render_label` 展示出来（建议在导出成功后写明"这是中性预览，不是相机 JPG"）。
3. **没做的：** 曝光/白平衡偏移/曲线（S6）；`thumbs` 对只有 DNG 的照片仍用 DNG 内嵌预览（没有改成半分辨率路径，`render_half` 已备好）；条带式的拉直（目前整幅 8 位图在内存里再 `transform`，4288×2848 约 37 MB，够用；ARCHITECTURE §5.5 的"只渲染所需区域"留给 S6 之后）；不支持压缩 DNG 和 28mm/MOUNT 的样本（没有样本，U4/U10）。
4. **没有 ΔE00：** U3 只量了码值域的相对差，原因见上。
5. **测试里依赖本机文件的部分：** 真实样本与研究代码对照的测试在 `captures/` 或 `research/` 不在时自动跳过（本次都在、都跑了，没有跳过）。
6. `studio/` 目前整个目录在 git 里是未跟踪状态，所以没有 diff 可附；改动的既有文件只有 `export.py`、`api/routes.py`、`README.md`。

## 复现

```bash
cd studio
.venv/bin/python -m pytest -q tests/test_raw.py tests/test_raw_export.py   # 36 个，约 10 秒
.venv/bin/python -m pytest -q                                              # 全部 177 个，约 2 分钟
cd .. && studio/.venv/bin/python -I research/studio_raw_s4/measure.py       # 速度和诊断数字
```
