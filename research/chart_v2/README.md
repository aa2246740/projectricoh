# GXR 屏幕色卡 v2

今天拍摄请直接看 [SHOOT_LIST.md](SHOOT_LIST.md)。色卡在 `pages/`，共 6 张测量页和 1 张白页；测量页共 696 块，每页 116 块。白页另有 1 个全画面参考区域。

## 生成与复核

在共享检出根目录执行。脚本写入前检查外置盘的挂载点、APFS、可写状态和指定 UUID，输出路径只能位于本任务目录。

```bash
cd /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh
python3 -I -B research/chart_v2/make_chart.py
python3 -I -B research/chart_v2/verify_chart.py
git check-ignore -v research/chart_v2/pages/01_chart.png research/chart_v2/local/validation.json
sips -g profile research/chart_v2/pages/*.png
cd research/chart_v2
shasum -a 256 -c SHA256SUMS
```

生成器仅依赖标准库、已有 numpy 和 Pillow。验证器另外复用本机已有 scipy 与仓库中的定位函数。没有安装新包。第二次生成放在 `local/repeat/`，验证 7 张 PNG 和 `patches.json` 的 SHA-256 与第一次完全一致。没有时间戳、随机种子漂移或字体文件依赖；重现条件包括相同脚本、Python/Pillow/numpy 和 ICC 文件。哈希清单与报告对应交付时的验证结果，重新生成或验证后应重新封存清单。

## 颜色取样

- 网格是 48 色相 × 4 明度 × 3 彩度，共 576 色。Lab 色相每 7.5° 一点，从 3.75° 起，避开 15° 扇区边界。L* 为 18、38、58、78，兼顾暗部、中间调和亮部，同时给较大色块留出面积。
- 每个色相和 L* 单独求 Display P3 的最大 C*，另求通道保留余量后的最大 C*。按后者的 25%、60%、97% 取样，不使用所有色相共用的 C*。完整边界和保留余量后的边界都写进每块数据。低彩度供小色偏判断，中彩度供常规颜色，高彩度接近该处可用色域边界。
- 另有 21 级灰阶，目标 L*5 至 97，含参考白；12 个从深到浅、偏暖与偏冷的肤色；15 个天空、植物、土、沙、砖、花色等记忆色。这些肤色和记忆色是设计的色域内样本，不是某个人、DIOPTIX 色卡或自然物体的实测反射率。
- 每页重复 12 个锚点，包括白、浅灰、中灰、深灰及红、黄、绿、青、蓝、品红、橙和叶绿。每个锚点在六页占六个不同位置，共 72 个锚点实例。它们供页间曝光、漂移、眩光和空间不均匀检查；仅凭这些锚点不能唯一分离所有误差。
- 白页为均匀 P3 `[246,246,246]`，和每页参考白一致。它是带余量的近白，不是 255，也不是对屏幕实际白点的测量。

Display P3 使用 P3 原色、D65 白点和 sRGB 分段传递函数，定义可见 [W3C Display P3](https://www.w3.org/TR/css-color-4/#predefined-display-p3)。PNG 嵌入系统 `/System/Library/ColorSync/Profiles/Display P3.icc`，当前 SHA-256 为 `0ff6958f98684c61f6bbdce1368ddeaf3873baf84545baba482e920d92a914c0`。所有非角标像素均避开 0 和 255；色块设计通道限制为 4 至 251，本次实际为 6 至 250。

`patches.json` 的线性 P3、XYZ 与 Lab 都从实际量化后的 P3 8 位值重算，另外保留设计 Lab。XYZ 的 D65 白为 `[0.9504559271,1,1.0890577508]`，Y=1；Lab 也相对这个 D65 白，不能和 ICC PCS D50 Lab 混用。

24 扇区采用从 0 开始的 `floor(hue/15)`。`target_sector_15deg` 指 Lab 目标色相；另记量化后 Lab 色相与名义 P3 转到裁剪 sRGB 后的 BT.601 CbCr 参考色相/扇区。目标 Lab 每扇区 24 个网格样本，量化后至少 22 个，参考 CbCr 每扇区至少 9 个。相机 JPEG 的实际 CbCr 色相还取决于传感器、屏幕光谱、白平衡和处理，不能由文件值保证；下轮需在实拍中重算，不能把 Lab 扇区直接当固件扇区。

## 页面和几何契约

画布为 3456×2234，颜色管理正确时可按比例缩放显示，不要求显示像素与 PNG 像素一一对应。12 列 × 10 行的测量网格，色块 228×156 px，中性 P3 `[60,60,60]` 缝宽 32 px，起点为 `[184,193]`。四个角槽用于定位标记，其余 116 槽都是色块，不在色块上印文字。

采样框用每个色块中央宽高各 40%，即面积的 16%，原图约 91×62 px；到色块边缘最短有 46.8 px。这给缩放、轻微失焦和几何误差留出余量。所有坐标为左上原点、半开框 `[x0,y0,x1,y1]`。主要色块和角标均位于顶部 193 px 以下；人读页码在 y=112，底部机器码位于 y=2070 至 2134。需完整显示整张图片，保留刘海、菜单栏和全屏缩放的空间；现场仍以四角全入镜、页码不遮挡为准。

四角棋盘分别为 TL=3、TR=4、BR=6、BL=8 格，黑格起头，给出方向。外框 156×156 px，白边 18 px，内部 120×120 px；最细格 15 px。`markers` 同时包含角点、中心、外框、棋盘框、格宽和内部交点，兼容既有几何函数需要的字段。每页上方另有人读页号 P1/6 至 P6/6。

底部机器码第一行是同步位 `1101`，随后是扩展 Hamming(8,4) 码；页号 1 至 6 的二进制按低位优先放入 d0…d3。第一行 8 位载荷依次为 `p1,p2,d0,p4,d1,d2,d3,p8`，其中 p1=d0⊕d1⊕d3，p2=d0⊕d2⊕d3，p4=d1⊕d2⊕d3，p8 为前七位异或。第二行逐位取反。每格 32×32 px，低/高值为 80/180；灰度对比低于棋盘，减少抢走角标候选的风险。码块和每一格的框、预期位值都在 `pages[].page_code` 中。这里仅验证模拟图的位值，本轮没有交付实拍解码器。

6 页每页均含全部 48 个目标色相，每色相取两个明度/彩度组合；六页合起来补齐全部 12 种组合。每页再分配 8 个灰阶/肤色/记忆色，及 12 个锚点。第 1、4 页合计覆盖每个色相的四种组合，供其它配方的快速差异检查；它们不能替代完整六页做密集拟合。

## 与既有解析链的接口

下一轮可从 `patches.json` 构造 `{"markers": {m["corner"]: m for m in metadata["markers"]}}`，传给只读的 `research/hue_ring/analyze_ring.py::locate_screen`。本轮六页失焦模拟都通过这个函数。`calibration_geometry.locate` 在同一模拟的第 5、6 页失败，错误保存在 `local/validation.json`；不能假定它对六页都适用。下一轮应以原始 `locate_screen` 为可用基线，再验证需要的抗模糊改进。

旧 `load_layout()`、取样器和颜色转换仍有旧色卡的单页、ring 和 sRGB 假设，不能原封不动当本色卡解析器。实拍解析需按机器页码选择该页的 `bbox_px` / `roi_bbox_px`，并尊重这里的 D65/P3 数据。未改动 `closed_loop`、`hue_ring`、`calibration_geometry`、DNG 解码器或固件。

## 版面检查约束

这是一份翻拍测量图，固定栅格、无装饰、无色块内文字，优先保证中心纯色、角标和页码完整。采用单 agent 执行。`ultimate-design` 的 Craft Core 用于留白和实际像素检查，Visual Verification 用于查看全部六页和白页，Quality Gates 用于核对交付范围；色块取样由本任务的色度学约束决定，不套用营销页面样式。`local/contact_sheet.png` 是转成 sRGB 的审阅缩略图，不能拿它翻拍；拍摄只打开 `pages/*.png` 原件。

实际图像检查和测量结果见 [REPORT.md](REPORT.md) 及 `local/validation.json`。屏幕发射光谱、局部调光、实际亮度、噪声、RAW 饱和、PWM/刷新条纹和真实摩尔纹均需实拍验收。
