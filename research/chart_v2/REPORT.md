# chart-v2 交付报告

6 页 Display P3 色卡、1 张白页和合并拍摄清单已就绪，自检通过。测量页共 696 块，拍摄方案三单元合计 37 次快门，预计 40 至 60 分钟。可按 [SHOOT_LIST.md](SHOOT_LIST.md) 开拍。本结论只代表页面与数据通过主机验证，尚无本版色卡的实拍验收；本轮没有做实拍解析器。

## 已核实

- 外置盘挂载于 `/Volumes/Workspace`，APFS、可写，Volume UUID 为 `14BE04EB-AF49-497E-B36A-B078B2F7C5E8`。已读盘根 `AGENTS.md`。本任务只写共享检出的 `research/chart_v2/`；没有操作相机、访问任何存储卡、改写官方固件或其它 worker 的目录，没有 commit/push，没有安装依赖。
- 7 张 3456×2234 RGB8 PNG 均嵌入系统 Display P3 ICC，`sips -g profile` 全部返回 `Display P3`。ICC SHA-256 为 `0ff6958f98684c61f6bbdce1368ddeaf3873baf84545baba482e920d92a914c0`。7 张图片合计 203,108 字节。
- 另起一个 Python 进程重复生成，7 张 PNG 和 `patches.json` 的 SHA-256 全部一致。数值复核使用独立的 P3→XYZ 矩阵；JSON 的线性 P3、XYZ(D65) 和 Lab(D65) 与量化色值重算的最大单分量差小于 `5.1e-11`。
- 576 个网格样本覆盖 48 色相、L*18/38/58/78、各自局部色域可用最大 C* 的 25%/60%/97%。另外有 21 灰阶、12 肤色、15 记忆色与 72 个重复锚点。每页 116 块，12 个锚点的色值各页一致，同一锚点在六页的位置各不相同。白页 `[246,246,246]`，实际名义 L*=96.8849。
- 设计色块通道限制 4 至 251，实际 6 至 250。扫描整幅图确认除四角定位标记外，没有任何 0 或 255 通道。所有色块框内像素与 JSON 色值一致。`.gitignore` 的 `/pages/`、`/local/` 均经 `git check-ignore -v` 确认生效。
- 目标 Lab 24 个 15° 扇区各有 24 个网格样本；量化后 Lab 每扇区至少 22 个，名义 P3 转裁剪 sRGB 的 BT.601 CbCr 每扇区至少 9 个。这里只验证输入和参考变换的覆盖，不把 Lab 扇区等同于机身固件扇区。
- 六页逐一模拟线性光高斯失焦 σ=6 原图像素，FWHM≈14.13 px，再施加缩放与透视，输出为 2400×1600，中心缩放约 0.5878。通过恢复出来的几何映射检查每块中央宽高各 40% 的全部像素，三通道均在目标值 1 码内的像素比例为 100%；最大浮点误差为 `3.052e-5` 码，每块最少剩 1,807 个有效像素。这个数只衡量该模拟里的邻块污染，不是相机色差。
- 未修改的 `research/hue_ring/analyze_ring.py::locate_screen` 在六页模拟图上都独立找到正确方向与 TL/TR/BR/BL 的 3/4/6/8 格角标。63 个已知探针点的最大位置误差为 1.818 输出像素。底部页码的两行位值与页号 1 至 6 全部恢复正确。
- 额外调用 `calibration_geometry.locate` 时，前四页通过，最大探针误差不超过 0.261 px；第 5、6 页失败，原始错误分别为 `ValueError: border checker mismatch {'TL': 3, 'TR': 4, 'BR': 6, 'BL': 3}` 和 `ValueError: border checker mismatch {'TL': 3, 'TR': 4, 'BR': 6, 'BL': 4}`。完整记录保留在 `local/validation.json`。所以可用的六页基线是原始 `locate_screen`，不能声称两个定位方法都通过。两个参考源码的验证前后哈希一致。
- 已查看六页联系表，四角棋盘、顶部页号、底部机器码和中性间隔完整，无文字压进色块。另单独查看白页、第一页原图及第六页失焦图。T3 原生 `html_preview` 在 728px 宽度渲染审阅图，内容高 650px，无控制台错误。审阅缩略图转成 sRGB，仅用于版面检查。
- 抽查已有 `captures/a12-50/2026-10-21/screen-closedloop/R8051198.JPG`，EXIF 为 `Model=GXR A12`、`LensModel=GR LENS A12 50mm F2.5 MACRO`、焦距 33mm、f/4；证据及源文件哈希在 `local/exif_sample.json`。28mm、MOUNT 的 EXIF 本轮未核实。

## 设计取舍与推断

旧卡的两层明度、共同低彩度适合找色相环，但不足以观察高饱和与明暗依赖。这版改为逐个色相和明度找 P3 边界，保留通道余量。实得网格 C* 为 4.48 至 134.49，268 块高于旧卡较高一圈约 C*31；177 个网格色处于名义 sRGB 色域之外。灰阶从旧 9 级增至 21 级，另补肤色、记忆色和跨页锚点。样本覆盖更宽，并不直接证明实拍准确度更高。

选 4 层明度和 3 层彩度，是为保住 6 页内的色块面积。每块 228×156 px、间隔 32 px，中央采样区离边缘至少 46.8 px。角标沿用不同棋盘格数表示方向，另加低对比双行 Hamming 页码。图像顶部、边缘留空，允许整图等比例缩放，不依赖像素 1:1。

三单元的完整 04 六页优先，供后续建立各自基线。只有 50mm 拍其它配方，每配方取第 1、4 页；两页都有全部目标色相，合计每色相四种明度/彩度组合，也有共同灰锚点。推断足够先筛配方差异和黑白响应，不能当作每个配方的完整密集拟合数据。拍摄量为 50mm 19 张、28mm 9 张、MOUNT 9 张；耗时为计划估计，未实测。

## 未知与覆盖不到的内容

PNG/ICC 的名义 P3 色域不等于现场屏幕完整实测色域。屏幕光谱与反射物体不同，不能代替实体卡、自然场景或测光仪；也无法覆盖高于屏幕亮度的场景动态范围、荧光或屏幕色域外的颜色。肤色和记忆色是合成样本，不是色卡厂商标定值。

真实 RAW 通道饱和、传感器噪声、屏幕局部调光、眩光、PWM/刷新条纹、色温漂移和真实摩尔纹均未验收。σ=6 的理想失焦模拟没有这些因素。相机真正的 24 个 CbCr 扇区分布、三单元的实拍定位成功率和其它配方的实际响应，留待拍完后测量。没有在用户的“预览”会话中操作或验证现场全屏；清单要求开拍前确认整图完整显示。

## 产出与复核

| 文件 | 用途 |
|---|---|
| `make_chart.py` | 确定性 P3 色卡生成器，内置外置盘与输出路径检查。 |
| `pages/00_white.png` | 手动白平衡与定曝光白页。 |
| `pages/01_chart.png` 至 `06_chart.png` | 六张拍摄原图，嵌 Display P3 ICC。 |
| `patches.json` | 696 块及白页区域的页号、编号、框、ROI、P3 码值、线性值、XYZ/Lab(D65)、类别与色相扇区；并含角标和页码几何。 |
| `README.md` | 取样、色度学、版面与下一轮几何接口说明。 |
| `SHOOT_LIST.md` | 给用户的合并中文拍摄清单与文件编号记录模板。 |
| `verify_chart.py` | 独立数值、重复生成、失焦/缩放/透视、既有定位函数与页码的自检。不是实拍解析器。 |
| `CHART_READY.json` | 七张原图、`patches.json`、生成/验证脚本及验证记录的 SHA-256。 |
| `SHA256SUMS` | 本目录交付文件与本轮证据的完整哈希清单，清单本身除外。 |
| `local/validation.json` | 完整量化结果与两条原始定位失败。 |
| `local/icc_profiles.txt`、`local/ignore-check.txt` | 系统 ICC 与 Git 忽略规则的原始输出。 |
| `local/repeat/`、`local/repeat-generation.txt` | 第二次生成原件与进程输出。 |
| `local/simulation_01.png` 至 `simulation_06.png` | 六页失焦、缩放、透视的模拟图。 |
| `local/contact_sheet.png`、`local/review.html` | 实际版面检查用联系表和自包含审阅页。 |
| `local/exif_sample.json` | 已有 50mm JPEG 的 EXIF 抽查证据。 |

环境为系统 `python3` 3.14.7、numpy 2.4.3、Pillow 12.2.0，scipy 为原有安装。复核命令如下：

```bash
cd /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/chart_v2
shasum -a 256 -c SHA256SUMS
sips -g profile pages/*.png
git check-ignore -v pages/01_chart.png local/validation.json
python3 -I -B verify_chart.py
```

最后一条会重做验证、更新 `local/` 证据和 `CHART_READY.json`；先核对封存哈希，再重跑。生成命令为 `python3 -I -B make_chart.py`。所有派生文件都留在本目录；`pages/` 和 `local/` 被忽略，不随 Git 自动交付，复制成果时要一并带上。
