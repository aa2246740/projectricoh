# 第二台 Mac 提取照片统计

第二台 Mac 可以只用 DNG/JPG 和公开代码识别测试页、提取色块读数。这个步骤不需要理光固件、DEEP 表、原厂曲线或拟合参数。完整的颜色评分和模型回拟仍在第一台 Mac 做。

## 需要的环境

本轮实测环境是 Python 3.14.7、NumPy 2.4.3、Pillow 12.2.0、SciPy 1.17.1。版本写在 `requirements-probe.txt`。另一个环境需要重新跑实拍检查，本轮没有安装包或下载依赖。

使用仓库以外的 Python 环境。纯统计入口会拒绝读取仓库内的 `local/`、`artifacts/`、`sources/`、`tools/` 和 `Scratch/` 私有数据，只有明确指定的照片输入目录及本次输出目录例外。

不需要 rawpy、LibRaw、OpenCV、ExifTool、pandas、M32R 工具链或相机连接。现有 RAW 解码器支持本项目测试过的未压缩 CFA DNG，不声称支持所有相机或压缩 DNG。

## chart-v2 的完整文件清单

下列 11 个 Python 文件都在 Git 中。它们按仓库相对位置加载，不要求第二台 Mac 具有第一台 Mac 的卷 UUID。

| 用途 | 文件 |
|---|---|
| 只提取统计的入口 | `research/git_sync/extract_probe_stats.py` |
| 配对、逐帧元数据、色块采样和导出 | `research/chart_v2/analyze_chart_v2.py` |
| 路径、模块加载、哈希与序列化 | `research/chart_v2/analyzer_runtime.py` |
| 定位、Hamming 页码与印刷页码交叉核对 | `research/chart_v2/analyzer_geometry.py` |
| 单应变换、ROI 和 EXIF 读取 | `research/hue_ring/analyze_ring.py` |
| 色彩计算及绘图辅助，随上述模块导入 | `research/hue_ring/sector_model.py`、`research/hue_ring/pilplot.py` |
| TIFF、RAW 与实体色卡辅助函数 | `research/stage2d_verification/analyze.py`、`research/stage2e_verification/analyze_2e.py` |
| 本项目的 TIFF/MakerNote 解析器 | `research/color_calibration/analyze_capture.py` |
| CFA 归一化及 DNG/JPG 配准 | `research/color_table_fit/dng_scene.py` |

需要的公开数据只有以下 8 个文件。

- `research/chart_v2/patches.json` 给出我们设计的色块、几何、页码和 ROI。
- `research/chart_v2/pages/00_white.png` 和 `01_chart.png` 至 `06_chart.png` 是我们生成的纯色测试页。页码识别读取其中的字形模板，因此它们也要随 Git 同步。

这些是自编测试图数据，不是理光提取表。不用在第二台 Mac 重跑带第一台卷 UUID 限制的旧生成器。

需要私下复制到第二台 Mac 的数据如下，全部留在 Git 之外。

- 原始同名 DNG 与 JPG/JPEG，保留文件编号和配对关系。
- 可选的人工 manifest，格式见 `research/chart_v2/analyzer_manifest.example.json`，可与照片放在一起。真实配方槽号、单元、拍摄顺序和基准帧由拍摄记录填写。EXIF 的彩色选择器不能区分 01/02/04/05/06，不能自动猜槽号。

不传 manifest 时仍可识页和测量，但未知单元、槽号会保留为空。MOUNT 的未知镜头环光圈会保留为空，不把 EXIF 的零或 0/0 当成实际光圈。

## 运行和交回数据

在 Git 根目录，用准备好上述包的 Python 运行。输入使用已复制到本机的目录，输出使用尚不存在的新目录。

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
python3 -I -B research/git_sync/extract_probe_stats.py \
  --input /absolute/path/to/photos \
  --manifest /absolute/path/to/photos/frames.json \
  --out research/git_sync/local/probe-stats-mac2-001
```

没有 manifest 时删去该参数。只读指定帧时可重复传入 `--frame R8051270`。工具只扫描输入目录的一层；缺失、重复或有大小写歧义的配对会报错。

输出包括 `frames/*.json`、`patches.csv`、取样框 JPG、`extraction.json`、`provenance.json` 和 `SHA256SUMS`。输出目录保留在 `local/`，不要提交照片、预览图或整份逐帧输出。

RAW 读数是线性化、减黑电平、按白电平归一的原生 CFA RGB，不去马赛克、不加白平衡。每通道取 10% 至 90% 截尾中位数，并保存均值、标准差、样本量和饱和比例。JPG 读数使用 8 位 RGB 码值的截尾中位数，空间标准差使用未截尾样本。帧 JSON 保存原文件哈希、元数据、页码、单应矩阵、配准结果、取样框及质量标记。

RAW 的 CFA、黑白电平、AsShotNeutral，以及附加 XYZ 结果用到的 ColorMatrix 来自输入 DNG。它们是照片内的运行时元数据，不是需要从第一台 Mac 复制的固件提取表；这些输出也留在本地。

退出码 0 表示解析和配准没有帧级错误，不表示所有色块都可用于拟合。检查每块的 `valid` 和 `flags`。本轮 50mm 测量页只有 10/116 块通过全部质量门槛，MOUNT 同页为 81/116；工具保留其余读数及排除原因，没有将其当成有效拟合样本。

第二台 Mac 私下交回逐帧 JSON、`patches.csv`、manifest、`provenance.json` 和 `SHA256SUMS`。第一台 Mac 用原图哈希绑定帧号，再把有效块送入自己的校准、目标比较和回拟代码。不要把第二台 Mac 的目录路径当作帧身份。统计文件已有 RAW/JPG 读数，回拟无需把原厂表送到第二台 Mac。

## 旧色环及 T1 probe2

旧的 155 色块色环不是 chart-v2，不能送进上述 chart-v2 CLI。它使用 `research/hue_ring/patches.json`，只做照片统计时不需要 `hue_ring.png`。

其纯提取函数是 `research/t1_probe/probe2/analyze_probe2.py::extract`。除前表的 hue-ring、Stage 2d 和 TIFF 解析辅助代码，还要带上同目录的 `probe2_core.py`、`model_probe2.py` 和 `calibration_geometry.py`。`model_probe2.py` 被入口导入，但只有构造 `Engine` 或运行完整 CLI 才会读取本地表和模型。第二台 Mac 只调用 `extract`，不要构造 `Engine`。该函数保留原文件哈希、元数据、几何、每块 JPG 和 RAW/白平衡读数。

旧色环无法从图案恢复配方槽号。04a/探针/04b 的身份需要拍摄顺序或人工帧记录。完整 probe2 CLI 的假说评分属于第一台 Mac 的工作。本轮只对 chart-v2 新入口重跑了实拍验证，旧色环调用链按源码核对。

## 为什么不直接运行旧完整入口

`analyze_chart_v2.py` 的旧 `Chain` 会复制本地辅助代码，后续评分再读取 DAT 和拟合数据。因此只复制公开仓库并不能运行完整评分。

以下是第一台 Mac 拟合侧的实际私有依赖，不交给第二台 Mac。

- 所选 `DEEPTBL0.DAT` 与 surface bank，默认表来自 `artifacts/stage2j-packages/tables-v4r2-noprobe/`。
- `research/hue_ring/local/ring_model_v2*.json` 及 `local/calibration_20261020/followup_v2/code/ring_model_v2.py`。
- `research/color_fit_v2/06_classic_neg/round4/local/cache/data_*.npz`，含 stock 及标定上下文。
- GR 正负片本地目标状态、GR IV 参考块，以及 `artifacts/downloads/fuji-luts/` 中的第三方 LUT。它们也不能混进公开同步。
- 旧 probe2 另需 `firmware/stage2j/examples/DEEPISP0.DAT`、本地 v3/probe2 表与校准帧数据。

已有工具仍可能引用未提交的本地依赖。新入口通过文件读取限制避开这些依赖，旧拟合和打包入口保留在第一台 Mac 使用。
