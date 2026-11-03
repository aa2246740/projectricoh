# 拍完后解析 chart-v2

在共享检出根目录运行。`--input` 只扫描一层目录，读取同名的 DNG 与 JPG/JPEG，不改输入。每次使用新的 run 名称。

```bash
python3 -I -B research/chart_v2/analyze_chart_v2.py --input <dir> --manifest <json> --out research/chart_v2/local/runs/<name>
```

先打开输出的 `quality.html` 检查页号和取样框，再看 `scores_by_recipe.csv`、`scores_by_hue.csv` 与 `stability.json`。`quality.json` 的 `extraction_pass` 表示解析与配准通过，`pass` 另要求所有色块都没有质量标记。部分色块被排除时仍会导出其读数和可用色块的评分。

退出码 `0` 表示解析结束，`2` 表示输入、配准、元数据或评分错误。未提供槽号时 `score_status=unassigned`；少页时为 `partial`。两者都不能当作完整评分通过。原始异常及 traceback 保存在失败帧的 JSON，不会静默跳过。孤立 DNG、孤立 JPEG 或大小写配对歧义也会保存错误记录。

## 按首尾编号填写 manifest

复制 `analyzer_manifest.example.json` 到本任务的 `local/` 下，改成导入后真实的首尾编号。`shoot_list=true` 按封存 `SHOOT_LIST.md` 分配 50mm 的 19 张，以及另外两个单元各 9 张。工具要求首尾之间的有效配对张数恰好为 19/9/9，不会按缺失照片补猜槽号。

```json
{
  "schema": "chart-v2-manifest/1",
  "ranges": [
    {"first": "R8051300", "last": "R8051318", "unit": "a12-50", "shoot_list": true}
  ],
  "exclude": [],
  "frames": {}
}
```

若范围内夹有试拍，把编号放进 `exclude`。这些帧仍会解析，但标为 `trial`，不参加评分与漂移统计。范围按完整文件编号排序，需使用相机原始的等长编号；重命名或跨编号回卷时逐帧指定。识别出的页码必须与拍摄顺序的 `expected_page` 一致，否则报错，不会用 manifest 强行改页码。

若拍摄顺序变化，在 `frames` 中逐帧填写。逐帧字段覆盖范围字段。

```json
{
  "schema": "chart-v2-manifest/1",
  "frames": {
    "R8051300": {"unit": "a12-50", "slot": "04", "purpose": "white", "expected_page": 0},
    "R8051301": {"unit": "a12-50", "slot": "04", "purpose": "screen", "expected_page": 1},
    "R8051307": {"unit": "a12-50", "slot": "01", "purpose": "screen", "expected_page": 1, "baseline": "R8051301"},
    "R8051317": {"unit": "a12-50", "slot": "04", "purpose": "drift", "expected_page": 1},
    "R8051318": {"unit": "a12-50", "slot": "04", "purpose": "physical"}
  }
}
```

`unit` 为 `a12-50`、`a12-28` 或 `mount-a12`。`slot` 为 `01` 至 `06`。`purpose` 为 `auto`、`screen`、`white`、`physical`、`drift` 或 `trial`，省略时自动分类。MOUNT 可另填 `lens_note` 和 `aperture_note`，保留所装镜头与镜头环光圈记录；它们不覆盖 EXIF。

不传 manifest 也会自动识页、白页、DIOPTIX、LensModel 和原生选择器，并输出取样结果。选择器 `1` 只能说明彩色模式，不能区分 01/02/04/05/06；这些帧的槽号留空。选择器 `3` 按本次六配方范围推断为 03，报告会注明这只是原生黑白模式的推断。28mm 与 MOUNT 的真实 LensModel 字符串尚未验收，manifest 是这两个单元的可靠归属来源。

## 输出接口

| 文件 | 内容 |
|---|---|
| `frames/<frame>.json` | 原文件哈希、元数据、识页双证据、单应矩阵、配准、每块读数、质量数值和标记。 |
| `patches.csv` | 每块一行的模块交换数据，连同逐帧曝光、白平衡和选择器字节。 |
| `overlays/*.jpg`、`quality.html` | 绿色框是有效 ROI，红色框是被排除的 ROI；HTML 内嵌图片，无外部依赖。 |
| `quality.json` | 解析状态、孤立文件与失败帧、质量阈值、缺少归属的帧和评分状态。 |
| `scores.json`、`scores_by_recipe.csv`、`scores_by_hue.csv` | 六配方与 24 个色相扇区的 ΔE00、分位数、实测相似度、模型误差及覆盖。 |
| `stability.json` | 同页首尾锚点的漂移，以及相同锚点跨页、跨位置的一致性。 |
| `vendor/`、`vendor_manifest.json` | 本 run 的辅助代码副本、原源码和适配副本的哈希。 |
| `provenance.json`、`SHA256SUMS` | 输入运行前后哈希一致性，以及输出文件哈希。 |

CSV 的前八列固定为 `frame,page,patch_id,class,raw_rgb,jpeg_rgb,valid,spatial_sd`。数组用 JSON 编码在 CSV 单元格中，`valid` 为 `true/false`，失败 ROI 的值留空。`patch_id` 对屏幕页采用 `patches.json` 的全局数字 id；`sample_key` 另保留跨页相同锚点的语义名称。DIOPTIX 的 id 为 `A1` 至 `D6`，`page` 留空。

`raw_rgb` 是原生 CFA RGB，先线性化、减黑电平，再按白电平归一，不做白平衡、不去马赛克。每通道取 10% 至 90% 截尾后的中位数；`raw.mean_cam` 另保留 `DngScene.stats` 的均值。`jpeg_rgb` 是 8 位码值单位的截尾中位数，可带 `.5`。`spatial_sd` 是未截尾 JPEG RGB 的空间总体标准差，单位同为 8 位码值。RAW 标准差、样本量及饱和比例在帧 JSON 的 `raw` 中。

CSV 的 `valid` 表示测量质量。目标或模型支持域的排除另列在 `scores.json` 的逐帧 `valid`，不会改写原始取样有效性。

评分沿用 `closed_loop` 对 JPEG 的 sRGB 解释。工具不修改相机文件的色彩空间。

## 评分和诊断边界

评分只处理 50mm 的屏幕帧。每帧匹配同页最早的一张 04，或 manifest 明确指定的同页 04。重复的 04 留给诊断，不重复加权。每个配方的相似度是 `1 - median(该配方到其目标的 ΔE00) / median(配对 04 到该配方目标的 ΔE00)`，分母不足 `0.25` 时留空。负值保留为负值。

中灰固定用 `ANCHOR_midgray`，映射为旧目标接口的 `G_L50`。不从评分结果选择曝光锚点，不用色卡名义 P3 值代替实拍 RAW。01/02 使用原有 GR III 相对迁移目标，03 使用 GR IV HC 实拍块插值，05/06 使用原有官方 Fuji LUT 通路。它们各自的目标等级、不支持色块、ISO 模型适用性与 0 EV 及 ±0.3 EV 敏感性都保留在结果里。04 是原厂控制，不把其近零差值解释为另一台原机的绝对相似度。

默认表与原 `measure.py` 相同，为 `artifacts/stage2j-packages/tables-v4r2-noprobe/DEEPTBL0.DAT`。若实际使用另一份兼容的 noprobe 表，传 `--table <path>`。工具记录表哈希，但不能从 EXIF 证明相机实际加载的 DAT。已有模型只在 A12 50mm 的 ISO 200/1600 校准；其它 ISO 会保留原模型的 ISO 200 回退并明确标为未校准。需要外部目标时可传 `--targets <closedloop-targets/1.json>`，仍要求正确 DNG 哈希、标签和匹配基准的目标。

摩尔纹、闪烁和亮带标记来自去平面趋势后的图像结构。它们会排除可疑色块，但不能单凭图像证明 PWM 或显示器硬件故障。漂移门限为原生 RAW 中位变化超过 `0.03 EV`，或 JPEG 中位 ΔE00 超过 `1`，或 p90 超过 `2`。跨页一致性分别报告未校正的跨度和去除页公共曝光偏移后的跨度，`0.1 EV` 及 `2 ΔE00` 是提示门限，不是面板认证标准。缺少首尾帧、有效锚点、完整页数或曝光/白平衡不一致时输出 `unknown`，不补猜。

## 重跑自检

下列命令使用新的输出名称，包含 30 个页面场景、12 次强制回退、合成 DNG、质量干扰、Hamming、评分、漂移、CLI 和指定旧照片检查。

```bash
python3 -I -B research/chart_v2/analyzer_selftest.py --part all --out research/chart_v2/local/runs/selftest-new
```

只复核某条路径时，`--part` 可选 `geometry`、`stress`、`signal`、`scoring`、`real` 或 `cli`；几何可用 `--pages 1,2` 缩小范围。`stress` 同时加入 σ=10 模糊、透视、缩放留黑、类摩尔纹与闪烁条纹。其色值真值包含已知的周期干扰，检查 ROI 取样是否正确，不表示工具已经恢复了未受干扰的颜色。所有测试输入、缓存和报告仍只写该 run。`real` 读取指定的旧 captures，既不要求新版照片，也不访问相机或存储卡。
