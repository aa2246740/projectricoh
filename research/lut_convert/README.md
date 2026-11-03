提交 `.cube` 文件并说明输入空间，就可以生成 50mm 的本地配方候选、色差报告和四列模拟预览。输出不是可上卡的配方包。

用户交付时至少给两项：

- LUT 原文件，保留原文件名和压缩包中的说明或许可。
- 输入的传递函数和色域，例如 `sRGB`、`L-Log / Rec.2020`、`F-Log2 / F-Gamut`。仅写“Log”无法确定转换。

如果输出不是 sRGB，还需注明输出传递函数、色域和 full/legal 范围。例如本次徕卡官方文件输出为 `Rec.709 / Gamma 2.4`；把它当成 sRGB 会改变明暗。没有输入空间说明时，工具拒绝猜测。

在仓库根目录运行：

```bash
cd /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh
python3 -I -B research/lut_convert/convert.py /absolute/path/my-look.cube \
  --input-space srgb --out local/my-look
```

徕卡 L-Log 示例：

```bash
python3 -I -B research/lut_convert/convert.py /absolute/path/leica.cube \
  --input-space llog --output-space gamma24 \
  --out local/my-leica --variants safe,t1,t2-hypothesis
```

输出目录相对于本工具目录，必须位于 `research/lut_convert/local/`。已有目录默认拒绝覆盖；显式使用 `--overwrite` 才重写本工具自己的结果。输入 LUT 始终只读。下载目录中的内容只作为数据读取，不能从那里运行程序。

默认 `safe` 拟合共同曲线、矩阵 Y 行和 24 个对称色相扇区，不启用 T 控制、C/D 或 T2。这里的 safe 指旋钮范围，不是相机安全验收。每份候选都保留 `daily_eligible=false` 和 `camera_acceptance=false`。颜色扫描不通过时会保留原始数值；原厂 04 的当前模型也存在低彩度扫描失败，详见 REPORT.md。

`t1` 增加三条绝对通道曲线，R=C、G=B5、B=D，需要 T 控制，属于受限研究版本。`t2-hypothesis` 只比较假设的按亮度色度增益，不导出硬件条目，因为亮度轴、步距和插值尚未实拍标定。两者都不是日常候选。

输入空间参数如下；完整公式与出处见 [SOURCES.md](SOURCES.md)。

| 参数 | 传递函数与默认色域 |
|---|---|
| `srgb` | sRGB，Rec.709 原色。 |
| `rec709` | BT.709 OETF，Rec.709 原色；与 sRGB 和 Gamma 2.4 分开处理。 |
| `gamma24` | Gamma 2.4，Rec.709 原色。 |
| `flog`、`flog2` | Fujifilm F-Log 或 F-Log2，F-Gamut 即 Rec.2020。 |
| `llog` | Leica L-Log，Rec.2020，适用于本次 SL2-S 与 SL3 系列 LUT。 |
| `llog709` | 同一 L-Log 曲线，Rec.709 原色，用于旧 SL Typ 601 的明确声明输入。 |
| `vlog` | Panasonic V-Log，V-Gamut。 |
| `slog3` | Sony S-Log3，S-Gamut3.Cine。 |
| `slog3-sgamut3` | Sony S-Log3，S-Gamut3。 |
| `applelog` | Apple Log，Rec.2020；不等于 Apple Log 2。 |
| `linear` | 场景线性 RGB，默认 Rec.709 原色。 |

`--input-gamut` 与 `--output-gamut` 可以显式选 `rec709`、`rec2020`、`vgamut`、`sgamut3`、`sgamut3cine`。输出默认 `--output-space srgb`；也支持 `rec709`、`gamma24`、`linear`。`--input-range legal` 把归一化输入换为 10 bit 64–940 code 所对应的数值，`--output-range legal` 作反变换；这些范围不从文件名猜测。

解析器支持 1D、3D、1D shaper 后接 3D，包含 17、33、65 格，`DOMAIN_MIN/MAX` 和 Resolve 的 `LUT_1D_INPUT_RANGE`、`LUT_3D_INPUT_RANGE`。3D 使用四面体插值。域外输入逐级夹紧并报告比例；有限的负输出暂保留到显示转换。拒绝非有限数、错行数、重复或未知指令、含义冲突的范围声明、超过 64 MiB 的文件及超出 129 格的 3D 表。

默认从仓库实景 DNG 模拟 04，再应用 LUT；预览会明确标成 `04 HOST MODEL`。它不会把现有的其他模式 JPEG 冒充原厂 04。显示参考 LUT 如需严格套在实拍 04 上，增加 `--stock04-json`，并用 `--scene` 指定 3–4 对 DNG，最后一整张只验收，不参与拟合。清单格式如下，每张场景都必须有对应项；路径相对于仓库根目录。

```json
{
  "schema": "gxr-confirmed-stock04/1",
  "pairs": {
    "captures/a12-50/example/A.DNG": "research/lut_convert/local/input/A.JPG",
    "captures/a12-50/example/B.DNG": "research/lut_convert/local/input/B.JPG",
    "captures/a12-50/example/C.DNG": "research/lut_convert/local/input/C.JPG"
  }
}
```

上例展示清单结构，路径需替换为实际文件。`pairs` 表示用户已确认 JPEG 是 04，槽号本身不记录在 EXIF 中。工具反解 JPEG 后正向重放，只使用通过反解检查的像素。Log 目标仍来自原始 DNG 的矩阵、白平衡和固定中灰锚，不从 JPEG 反猜场景线性值。

每个输出目录包含：

| 文件 | 内容 |
|---|---|
| `results.json` | 相似度、ΔE00、输入哈希、模型与场景边界、优化器状态。 |
| `preview.png` | 04 模拟、LUT 理想效果、日常旋钮预测；选择 T1 时增加 T1 列。 |
| `safe/sector_residuals.csv` | 24 扇区的样本数、中位与 p90 ΔE00、带符号 Lab 残差。 |
| `safe/LIMITATIONS.txt` | 白话的表达限制；其他版本也分别输出。 |
| `safe/candidate.entry` | 单条 448 B 深层条目，无表头和卡容器。 |
| `safe/candidate.json` | 曲线、色表、矩阵和 mask，全部只保存在 local/。 |
| `t1/` | 选择 T1 后产生的受限比较结果。 |
| `t2-hypothesis/` | 假设模型的比较结果，没有 `.entry`。 |
| `SHA256SUMS` | 本次转换的逐文件哈希。 |

单条 `.entry` 的槽位 03 或 05 和 recipe CRC 只是集成占位。上层组表器须重新绑定配方名、原生模式和 recipe CRC，并完成生命周期与相机验收，不能把该文件改名当卡文件使用。

黑白默认自动检测：真正无色的 LUT 走原生 03、共同曲线和通道混合，额外写 A20/B20。带棕色、蓝色等偏色的黑白保留在彩色拟合路径。共同曲线后混合通道，不能保证等价于任意 LUT 的“先混合再套曲线”；色差会如实保留。`--bw off` 可明确禁用原生 03。

`--module a12-50` 是目前唯一接入的单元。接口预留 `a12-28`、`mount-a12`，但在校准适配器接入前会明确拒绝，绝不静默套用 50mm。`--iso` 支持现有 200、1600 模型；场景 ISO 与模型不同时会在结果中标记。

本轮八个官方文件每个耗时约 9.3–21.7 秒，包含三档拟合和四张预览，复用已经准备好的 Engine 与 DNG；这是高负载机器上的单次实测，首次还需准备模型和 DNG。默认只跑 safe，最多 60 次求值，本轮三档比较上限为 100 次。逐文件时长、优化次数和机器负载见 [REPORT.md](REPORT.md) 与 `local/leica-complete/batch.json`。增加采样数、预览宽度或 `--max-nfev` 会延长时间。`status=0` 表示达到求值上限，结果只是该预算内的近似，不能写成已收敛。

复核命令：

```bash
python3 -I -B research/lut_convert/selftest.py --out local/selftest-new
python3 -I -B research/lut_convert/verify.py
cd research/lut_convert
shasum -a 256 -c SHA256SUMS
```

下载脚本先检查挂载身份和 `df -h`，只在一个全新的隔离目录下载官方数据，不执行其中任何内容。原始三套 LUT 下载于 `artifacts/downloads/leica-luts/20261023-official/`。归档与解压文件的 URL、许可状态和 SHA-256 见该目录的 `SOURCES.json` 及本任务 `local/official_sources.json`。ZIP 中没有 LICENSE 或使用条款文件；“官网可公开下载”不等于开放再分发许可。本轮没有发布 LUT 或衍生配方。
