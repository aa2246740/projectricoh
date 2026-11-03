所有 Log 输入都先从 DNG 相机坐标转到 XYZ、Bradford 适配 D65，再转到指定 RGB 色域后编码。显示参考输入则先解码 04 的 sRGB，再编码到声明的显示参考空间。公式在 `spaces.py`，来源快照与哈希保存在 `local/official_sources.json`；下载原件也保存在 `artifacts/downloads/leica-luts/20261023-reference-docs/`。没有安装新的 Python 包。

| 实现 | 主要依据 | 本轮核对 |
|---|---|---|
| F-Log | [Fujifilm F-Log Data Sheet](https://dl.fujifilm-x.com/support/lut/F-Log_DataSheet_E_Ver.1.0.pdf)，§2-3、§3。 | 厂商 PDF 已下载；曲线、Rec.2020 原色、黑/18%/90% code 交叉检查。 |
| F-Log2 | [Fujifilm F-Log2 Data Sheet](https://dl.fujifilm-x.com/support/lut/F-Log2_DataSheet_E_Ver.1.0.pdf)，§2-3、§3。 | 厂商 PDF 已下载；不把 F-Log2C 的色域混进来。 |
| L-Log | [Leica L-Log Reference Manual V1.6](https://leica-camera.com/sites/default/files/2026-06/Leica-L-Log-Reference-Manual-V1.6.pdf)，§3.1–3.3、§4。 | 厂商 PDF 已下载，原 pm 链接 502 后使用官方视频页面当前链接。SL Typ 601 为 Rec.709，SL2/SL2-S/SL3 等为 Rec.2020。 |
| V-Log / V-Gamut | [Panasonic Reference Manual](https://pro-av.panasonic.net/en/cinema_camera_varicam_eva/support/pdf/VARICAM_V-Log_V-Gamut.pdf)，§3、§4。 | 厂商 PDF 已下载；分段曲线与 D65 V-Gamut 原色。 |
| S-Log3 / S-Gamut3 | [Sony Technical Summary](https://pro.sony/s3/cms-static-content/uploadfile/06/1237494271406.pdf) 与 [OpenColorIO 官方 Sony 实现](https://github.com/AcademySoftwareFoundation/OpenColorIO/blob/main/src/OpenColorIO/transforms/builtins/SonyCameras.cpp)。 | Sony PDF 可由网页检索读取，但本地下载为 HTTP 403；公式和两套原色另对照已下载的 OpenColorIO 原始源码，只读、不执行。 |
| Apple Log / Rec.2020 | [Apple AVFoundation 定义](https://developer.apple.com/documentation/avfoundation/avcapturecolorspace/applelog) 与 [OpenColorIO 官方 Apple 实现](https://github.com/AcademySoftwareFoundation/OpenColorIO/blob/main/src/OpenColorIO/transforms/builtins/AppleCameras.cpp)。 | Apple 白皮书下载返回登录页面，本轮未取得该 PDF。曲线常数和分段对照 OpenColorIO 官方实现，色域对照 Apple 文档；不声称重新核读了 Apple 白皮书。 |
| Rec.709、Rec.2020 原色与矩阵构造 | [OpenColorIO ColorMatrixHelpers](https://github.com/AcademySoftwareFoundation/OpenColorIO/blob/main/src/OpenColorIO/transforms/builtins/ColorMatrixHelpers.cpp)。 | 从 xy 原色和 D65 白点计算矩阵，检查白点映射与可逆性。 |
| 组合 `.cube` | [Blackmagic 官方论坛的 LUT 格式说明](https://forum.blackmagicdesign.com/viewtopic.php?f=21&t=40284)。 | R 最快、1D shaper 在 3D 之前、分别使用 INPUT_RANGE；另支持 Adobe 风格逐通道 DOMAIN。 |

令场景线性反射率为 `x`、归一化编码为 `y`。F-Log 与 F-Log2 都使用高段 `c log10(a x+b)+d`、低段 `e x+f`，系数分别为：

```text
F-Log:  a=.555556 b=.009468 c=.344676 d=.790453 e=8.735631 f=.092864 cut=.00089
F-Log2: a=5.555556 b=.064829 c=.245281 d=.384316 e=8.799461 f=.092864 cut=.000889
```

L-Log 在 `x<=.006` 时为 `8x+.09`，否则为 `.27 log10(1.3x+.0115)+.6`。反变换切点采用文档的 `.1380`。厂商给定系数存在微小拼接舍入，工具按文档保留，不擅自移动切点。

V-Log 在 `x<.01` 时为 `5.6x+.125`，否则为 `.241514 log10(x+.00873)+.598206`。S-Log3 在 `x<.01125` 时为 `(95+x(171.2102946929-95)/.01125)/1023`，否则为 `(420+261.5 log10((x+.01)/.19))/1023`。

Apple Log 的常数为 `R0=-.05641088, Rt=.01, c=47.28711236, beta=.00964052, gamma=.08550479, delta=.69336945`。高段为 `gamma log2(x+beta)+delta`，低段为 `c max(x-R0,0)^2`。Apple Log 2 使用其他原色，本工具没有把它作为同一个空间接受。

Gamma 2.4 的负数使用符号对称扩展，以免在色域变换前提前删掉 LUT 的有限负输出；最终显示到 sRGB 时再夹紧到 0–1。这里的扩展是实现约定，不是宣称显示器能显示负光。Rec.709 使用 OETF，与 Gamma 2.4 或 BT.1886 显示模型分开。

徕卡资料与许可：

- [SL3 官方下载页](https://leica-camera.com/en-US/photography/cameras/sl/sl3-black/downloads) 链接 Legacy、Pure、Cine 三份 ZIP。Legacy 含 Classic 和 Natural，各有 Rec.709 与 Rec.2020 Gamma 2.4 输出；输入按 SL2-S 的 L-Log/Rec.2020 规范。Pure 与 Cine 各有 33 格 Viewing 和 65 格文件；65 格文件名明确标为 Rec.2020 L-Log 到 Rec.709 Gamma 2.4。
- [官方视频页面](https://leica-camera.com/en-GB/photography/cameras-videography) 说明 Pure、Cine 作为 L-Log 的起点。33 格与对应 65 格的共同节点另作数值核对，不能仅凭同名推定完全相同。
- [Leica Looks 官方页](https://leica-camera.com/en-US/photography/leica-looks) 列出 Essential、Core 和 Artist 类别。Essential 的可见名称包括 Pure、Cine、Silver、Bleach、TEAL、Brass、Chrome、Classic、Contemporary、Sepia、Blue、Selenium、Eternal；Core 包括 Standard、Natural、Vivid、Monochrom Natural、Monochrom High Contrast。它们通过 Leica FOTOS 工作流分发，本轮没有找到它们的通用公开 `.cube` 下载和开放许可。照片 Look 与同名视频 LUT 不能据名称视为同一变换，Looks 的输入也不能一律宣称为 L-Log。
- 三份 ZIP 的全部普通文件均为 `.cube`，没有 LICENSE、README、EULA、条款文件或 ZIP comment。许可状态记录为“官方公开下载，未发现明确开放或再分发许可”，而不是“无版权”或“已获跨品牌再分发许可”。本轮仅保存本地研究，不发布这些文件或衍生配方。

GXR 部分复用 `research/closed_loop/model.py` 的 50mm `Engine`、冻结数学辅助、`research/color_table_fit/dng_scene.py` 的 DNG 色度处理，以及 `firmware/stage2l_switch/tools/deep_sources.py` 的曲线、矩阵、C/D、mask、CRC 与完整解析检查。沿用 `05_classic_chrome/round4/local/fit_v4_noT1.json` 的固定中灰锚，未重新拟合测光。`camera.py` 明确记录按每帧 AsShotNeutral 与 DNG 矩阵应用该锚的方式；这部分仍是目标迁移模型，不是新的实拍标定。
