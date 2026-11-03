可以评审

# GXR 配方 JPG → 带增益图的 HDR JPG（原型）

2026-10-31。只在电脑端处理；没碰相机、没碰卡。最后一步要由用户在 iPhone 照片 App 里看。

## 一句话结论

15 张都做出来了：
- **主图**：就是原配方 JPG。压缩数据逐字节没动，解码后的像素和原图一模一样（PIL 逐像素比对）。
- **增益图**：作为第二幅图接在主图后面，同时写了 ISO 21496-1 和 Adobe/Ultra HDR（XMP `hdrgm` + MPF）两种写法。
- **本机验证**：macOS 系统自带的 ImageIO 15/15 认出了增益图，并能按 HDR 解码；系统实际给的提亮和按规格算出来的一致，p99 误差 ≤ 0.095 档。
- **提亮幅度**：受 RAW 本身余量限制，这批照片最大提亮在 0.3–1.8 档之间：白天天空和楼面约 1.2–1.8 档，夜里招牌 1.8 档，灯笼的灯泡 1.5 档。

## 1. 原理

- **SDR 底图**：配方 JPG 原样不动。不支持 HDR 的屏幕和 App 只读第一幅图，看到的就是原配方照片。
- **增益图**：一张 1/4 分辨率（1072×712）的单通道 8 位灰度图，每个点记录"这里在 HDR 屏上可以再亮多少档"（log2 增益）。
- **显示公式**：支持的看图软件按下式显示，`w` 由屏幕当前余量决定，取 0–1：

  `HDR = (SDR + 1/64) × 2^(增益 × w) − 1/64`

  三个通道乘的是同一个增益，所以色相和 RGB 比例不变（自检的比例误差 < 1e-5）。增益为 1（log2 = 0）的地方 HDR = SDR，画面不变。
- **增益怎么来**：用同一张 DNG。12 位 RAW 在 JPG 已经发白的地方还有 1.4–3.4 档没用上的亮度。

## 2. 规格要点和出处

| 项目 | 内容 | 出处 |
|---|---|---|
| Ultra HDR v1.1 | 主图 XMP 里 `hdrgm:Version="1.0"`，加上 `Container:Directory`（Primary + GainMap，GainMap 带 `Item:Length` = 第二幅图的字节数）。增益图 XMP 的字段：`GainMapMin/Max`、`Gamma`、`OffsetSDR/HDR`、`HDRCapacityMin/Max`，都是 log2 值；`BaseRenditionIsHDR`。编码：`recovery = ((log2 增益 − min)/(max − min))^gamma`，存成 `floor(×255+0.5)`。推荐偏移 1/64、增益图 1/4 尺寸、JPEG 质量 85–90。增益图的方向跟主图的存储方向一致，增益图自己的 EXIF 方向不看。ISO 21496-1 段紧跟在 XMP 段后面，两种写法共用同一幅增益图，同时有两种时解码优先用 ISO | https://developer.android.com/media/platform/hdr-image-format |
| ISO 21496-1 二进制布局 | APP2，命名空间 `urn:iso:std:iso:ts:21496:-1\0`。主图里只放 4 字节版本号（`00 00 00 00`）。增益图里放完整内容，大端：`min_version u16, writer_version u16, flags u8`（bit7 = 三通道，bit6 = 用底图色彩空间），`base/alternate HdrHeadroom` 是无符号分数，然后每通道依次是 `gainMapMin`（有符号）、`gainMapMax`（有符号）、`gamma`（无符号）、`baseOffset`（有符号）、`alternateOffset`（有符号）的分数。headroom = log2(HDRCapacity)。ISO 原文要付费，这次没读；字节布局按 libultrahdr 源码实现 | https://github.com/google/libultrahdr ：`lib/src/gainmapmetadata.cpp`、`lib/include/ultrahdr/gainmapmetadata.h`（只读源码，没编译没运行） |
| MPF | APP2 `"MPF\0"` 后接 TIFF 结构，大端。三个标签：B000 版本 "0100"、B001 图像数 2、B002 记录（每条 16 字节：属性、大小、偏移、两个依赖号）。第一幅（主图）属性 0x030000、偏移 0；第二幅（增益图）属性 0、**偏移相对 MPF 段里 TIFF 头（"MM"）的位置**。libultrahdr 把 MPF 放在 SOS 之前，段顺序是 SOI → APP0 → EXIF → XMP → ICC → ISO → DQT/SOF/DHT → MPF → SOS | 同上：`lib/src/multipictureformat.cpp`、`lib/src/jpegr.cpp`（`appendGainMap`） |
| 解码端怎么找增益图 | libultrahdr 把**第二幅顶层 JPEG** 当增益图；严格模式（`hasValidMpfAssociation`）要求 MPF 正好两幅 | `lib/src/jpegr.cpp`（`extractPrimaryImageAndGainMap`） |
| Apple | WWDC24 原话："With the release of iOS 18, we are transitioning to Adaptive HDR"，"JPEG files also fully support Adaptive HDR"。读写 API：`kCGImageAuxiliaryDataTypeISOGainMap`、`kCGImageSourceDecodeToHDR`、`contentHeadroom`。Apple 的 Adaptive HDR 就是 ISO 21496-1 | https://developer.apple.com/videos/play/wwdc2024/10177/ |
| 跨平台（二手资料） | Android 15 起同时写 Ultra HDR 和 ISO 两种；iOS 18 的照片、信息、预览能显示 Ultra HDR。另有文章说 Apple 对老的 XMP 写法支持不全，建议带上 ISO。这次两种都写 | https://www.androidauthority.com/google-apple-hdr-photo-standard-3495035/ 、https://www.cultofmac.com/news/hdr-photos-android-iphone-work-better-across-platforms （只看了搜索摘要） |
| Adobe Gain Map 规范 | 网页对抓取返回 403，没读到原文。字段定义与 Ultra HDR 页一致（hdrgm 命名空间本来就是 Adobe 的） | https://helpx.adobe.com/camera-raw/using/gain-map.html |

本机实测（macOS 27.0.1，系统 ImageIO）：
- 两种都写、只写 XMP、只写 ISO，三种文件**都**被认成 ISO 增益图（`HDRToneMap:*` 元数据完整）。
- 原 JPG 不被认成 HDR。
- 成品两种都写，兼顾 libultrahdr、安卓和老系统。

## 3. 实现

代码在 `research/hdr_gainmap/`，不依赖仓库里其他代码，`python -I` 也能直接跑。

| 文件 | 作用 |
|---|---|
| `gxr_hdr.py` | 读 DNG（自写的 TIFF 解析）、读 JPEG 段结构、计算增益、编码增益图、封装 |
| `make_samples.py` | 批量生成 15 张样张，同时输出增益图 PNG 和 `stats.json` |
| `selfcheck.py` | 自检。解析代码独立写，不复用封装函数 |
| `check_imageio.swift` | 只用系统框架：检查 ImageIO 能否识别、比较 SDR 像素、导出 HDR 解码的亮度 |
| `run_checks.sh` | 自检全流程 |

运行：
```
studio/.venv/bin/python -I research/hdr_gainmap/make_samples.py        # 约 13 秒 / 15 张
research/hdr_gainmap/run_checks.sh                                    # 自检 + 系统 ImageIO 对照
```

### 3.1 算法

1. **读 RAW**：GXR 的 DNG 是未压缩 12 位 Bayer。按 DefaultCrop 取 4288×2848，每个 2×2 小块合成一个 RGB 点（不做去马赛克），得到 2144×1424。然后减黑电平、除以白电平、除以 AsShotNeutral（白平衡）。任一传感器点 ≥ 白电平的 98% 记为"RAW 过曝"。亮度 = 0.25R + 0.5G + 0.25B，只用来比较亮和暗。
2. **对齐**：DNG 和 JPG 都按各自的 Orientation 转到 JPG 的存储方向。RAW 缩放到增益图网格，做相位相关找平移，并在 ±2% 范围试缩放，按高通相关系数选最好的结果。15 张实测全部是缩放 1.0、平移 (0,0)，相关系数 0.68–0.96，B&W 和夜景偏低但峰值明确。
3. **曝光对齐 + 配方曲线**：在 4×4 块上，把 log2 RAW 亮度对 log2 SDR 线性亮度做分箱中位数，得到单调曲线 T，也就是这张照片"RAW → 配方 JPG"的实际色调曲线。曝光差、BaselineExposure、配方的反差和对比都包含在 T 里。中间调（SDR 0.10–0.30）RAW 比 JPG 暗 0.3–1.3 档，各张不同，见 `stats.json`。
4. **HDR 曲线**：SDR 线性亮度 0.45（约 sRGB 码值 180）对应的 RAW 位置记为拐点。拐点以下 HDR = T，增益严格为 1。拐点以上 HDR 按场景线性继续变亮（对数斜率 1），不再被配方的肩部压缩。
   - `log2 增益 = HDR(x) − T(x)`，再用 `2.5·tanh(·/2.5)` 软上限，最多 2.5 档。
   - **增益只是 RAW 亮度的函数**，不是两张图逐点相除，所以对齐误差和配方局部差异不会变成噪声。
5. **门控**：本块 SDR **亮度**低于 0.30 的增益强制为 0，0.30–0.50 之间平滑过渡。这样深色天空（红滤镜黑白）、饱和但不亮的颜色都不会被提亮，中间调保证不动。
6. **元数据**：`GainMapMin=0`，`GainMapMax=HDRCapacityMax=本张最大增益`（不同张 0.30–1.82），`Gamma=1`，偏移 1/64，`BaseRenditionIsHDR=False`。增益图存成灰度 JPEG，质量 90，每张 54–80 KB。
7. **黑白配方**（1532、1644、1653）走同一套流程，不需要特殊处理。拟合的是"RAW 亮度 → 黑白 JPG 亮度"，滤镜效果包含在曲线里，门控挡住被滤镜压暗的区域。

### 3.2 封装（不重新压缩）

- **主图**：SOI，原 EXIF APP1（原样，含 160×120 缩略图），新 XMP APP1，ISO 版本段 APP2，新 MPF APP2，然后是原 DQT/SOF/DHT/SOS…EOI（原样字节）。
- **第二幅**：SOI + 增益图 XMP + 增益图 ISO + 增益图 JPEG。
- **去掉的部分**：
  - 原文件的 MPF 段，换成新的；
  - 原 MPF 带的第二幅图，即 GXR 的 640×424 预览，约 86 KB；
  - 主图 EOI 后面 19 字节的填充。

  去掉预览的原因是 libultrahdr 把第二幅 JPEG 当增益图，严格模式要求正好两幅；三幅的写法兼容性没把握。代价是个别看图软件不能再用那张预览图做快速缩略图，EXIF 小缩略图还在。成品反而比原 JPG 小 2–73 KB。

## 4. 自检结果（15/15 通过）

`selfcheck.py` 逐张检查以下项目，结果写在 `captures/hdr-gainmap-proto/selfcheck.json`：

1. 主图解码像素和原 JPG 逐像素相同（PIL）：**15/15**。
2. 原文件的 EXIF、DQT、SOF、DHT 和整段熵编码数据，原样出现在新文件里：**15/15**。没有重新压缩。
3. MPF：版本 0100，两条记录。第一条大小 = 主图实际长度；第二条偏移 + TIFF 头位置 = 增益图的 FFD8；两幅图首尾相接到文件末尾：**15/15**。
4. 主图 XMP 能用 XML 解析；Container 两项；`Item:Length` = 第二幅实际字节数：**15/15**。
5. ISO：主图有版本段；增益图 ISO 段长度正确（单通道 61 字节）、flags 0x40；每个字段和增益图 XMP 的值一致（差 < 1e-4）：**15/15**。
6. 第二幅单独解码：1072×712 灰度：**15/15**。
7. 按规格重建 HDR：SDR 亮度 < 0.18 的像素中，≥ 99.8% 提亮 ≤ 0.05 档（p99 ≤ 0.021 档）；三通道比例不变：**15/15**。
8. 系统 ImageIO（`check_imageio.swift`）：
   - **15/15** 认出 ISO 增益图（`kCGImageAuxiliaryDataTypeISOGainMap`，1072×712）；
   - HDR 解码得到 10 位图像，`contentHeadroom` = 2^GainMapMax；
   - 系统实际提亮和本脚本按规格算的相比，4×4 块中位误差 0.002–0.006 档，p99 0.013–0.095 档。

每张的统计（"面积"指增益图像素占比）：

| 编号 | 最大增益（档） | 提亮 >0.1 档面积 | >1 档面积 | RAW 过曝面积 | 对齐（缩放/平移/相关） | 系统 HDR 余量 | 系统提亮与规格差 p99（档） | 中间调提亮 p99（档，系统测） | 文件大小变化 |
|---|---|---|---|---|---|---|---|---|---|
| 1530 配方1 | 1.34 | 8.7% | 2.4% | 3.0% | 1.0/[0, 0]/0.938 | 2.53× | 0.034 | 0.025 | −29 KB |
| 1531 配方2 | 1.59 | 14.1% | 1.2% | 1.1% | 1.0/[0, 0]/0.948 | 3.01× | 0.043 | 0.016 | −15 KB |
| 1532 配方3 黑白 | 1.80 | 16.5% | 4.3% | 3.0% | 1.0/[0, 0]/0.77 | 3.49× | 0.072 | 0.041 | −2 KB |
| 1533 配方4 | 1.60 | 12.7% | 2.6% | 2.5% | 1.0/[0, 0]/0.94 | 3.02× | 0.053 | 0.021 | −12 KB |
| 1534 配方5 | 1.18 | 5.5% | 1.1% | 2.7% | 1.0/[0, 0]/0.927 | 2.26× | 0.035 | 0.025 | −40 KB |
| 1535 配方6 | 1.30 | 7.6% | 1.8% | 2.8% | 1.0/[0, 0]/0.926 | 2.46× | 0.038 | 0.029 | −30 KB |
| 1536 配方7 | 1.27 | 7.2% | 1.7% | 2.8% | 1.0/[0, 0]/0.934 | 2.41× | 0.031 | 0.025 | −36 KB |
| 1537 配方8 | 1.15 | 8.1% | 1.6% | 4.1% | 1.0/[0, 0]/0.936 | 2.22× | 0.042 | 0.025 | −25 KB |
| 1562 天空 | 0.30 | 29.0% | 0.0% | 0.0% | 1.0/[0, 0]/0.944 | 1.23× | 0.024 | 0.029 | −41 KB |
| 1577 | 0.32 | 0.1% | 0.0% | 0.0% | 1.0/[0, 0]/0.962 | 1.24× | 0.032 | 0.034 | −73 KB |
| 1627 灯笼 | 1.53 | 0.3% | 0.1% | 0.1% | 1.0/[0, 0]/0.843 | 2.88× | 0.022 | 0.020 | −69 KB |
| 1644 夜 黑白 | 0.84 | 0.2% | 0.0% | 0.0% | 1.0/[0, 0]/0.684 | 1.79× | 0.013 | 0.013 | −68 KB |
| 1653 夜招牌 黑白 | 1.82 | 38.5% | 20.3% | 16.7% | 1.0/[0, 0]/0.763 | 3.54× | 0.095 | 0.179 | −3 KB |
| 1680 猫 | 0.52 | 0.0% | 0.0% | 0.0% | 1.0/[0, 0]/0.935 | 1.44× | 0.026 | 0.026 | −71 KB |
| 1685 猫 | 0.59 | 0.8% | 0.0% | 0.0% | 1.0/[0, 0]/0.885 | 1.50× | 0.022 | 0.024 | −63 KB |

说明：
- 系统测的中间调提亮 p99 约 0.02–0.03 档，是 10 位 HDR 输出在暗处的量化误差；本脚本按规格算是 0。
- 1653 的 0.18 档来自招牌边上的暗像素，见 §5 光晕。

**一个要如实说明的现象**：用 macOS 系统解码器比较，12 张彩色图的 SDR 有约 40% 的值差 ±1，3 张黑白图完全相同。查明的原因如下：
- 只在原 JPG 里加一个 ISO 21496-1 段，其他字节全不动，就出现同样的 ±1；只加 XMP、去掉 MPF 或去掉预览都不会。
- 所以这是 macOS 看到"这是 ISO HDR 图"后换了一条 JPEG 解码路径，差在彩色转换的取整。新路径反而更接近 libjpeg：与 PIL 不同的值从 45% 降到 7%。
- 压缩数据逐字节相同（第 2 项），配方颜色没有被改；只要文件被 Apple 当成 HDR 图，这个 ±1 就无法避免。

**本机没验证的**：
- iPhone 照片 App 的实际显示，要用户看；
- 安卓；
- libultrahdr 的解码器。规则不允许运行它，只按源码核对了写法。

## 5. 已知限制

- **提亮幅度受 RAW 限制**：这批照片里，JPG 发白的地方 RAW 最多还有 1.4–3.4 档余量。实际最大增益是 1.2–1.8 档，没碰到 2.5 档上限。RAW 本身也过曝的地方（灯、反光）只能给到"过曝那一档"。想要更强的效果可以调 `hdr_slope` > 1，但那是夸张，不是如实。
- **饱和色**：红灯笼在 JPG 里红通道已经顶满，但 RAW 显示它只比中间灰亮约 1 档，是配方的饱和度和反差把它推满的。按如实原则，灯笼主体几乎不提亮，只有灯泡亮。另有 `measure="maxrgb"` 选项按三通道最大值衡量，试过：灯笼面积只从 0.3% 增加到 0.6%，同时蓝天会被略提亮，所以默认不用。
- **光晕**：增益图是 1/4 分辨率，又经过双线性放大，亮物体旁边 1–4 个像素的暗处会被一起提亮，看起来像轻微泛光；1653 招牌边缘的暗像素 p99 提亮 0.18 档。可以改 `map_factor=2`（1/2 分辨率，规格允许），代价是增益图约大 4 倍，还没试。
- **对齐**：只验证了 MOUNT 单元，DNG 裁切和 JPG 完全一致。50mm/28mm 单元如果机内做了畸变校正，±2% 缩放加平移可能不够，要另做局部（网格）对齐，待验证。
- **白平衡**：增益只用亮度比，白平衡只影响 RAW 亮度的加权，用 AsShotNeutral 足够。没用 DNG 的色彩矩阵。
- **去掉了 MPF 预览图**，见 §3.2。
- **App 支持**：
  - 能显示 HDR：iOS 18+/macOS 15+ 的照片、预览、快速查看（WWDC24），以及 Android 14+/15+ 的 Ultra HDR 和 Chrome 系浏览器（二手资料）。
  - 会被剥成 SDR：会重新压缩图片的 App（例如微信、多数社交平台）。剥掉后看到的就是原配方 JPG，不会更糟。
  - 隔空投送进照片 App 一般保留原文件，但这批没实测。在 iPhone 照片里编辑后是否还保留 HDR，也未知。

## 6. 工作室集成建议（导入时自动生成 HDR 版本）

- **前置 bug（另开任务修，本任务没改 `studio/`）**：`studio/src/gxr_studio/raw/tiff.py` 读这批 DNG 时直接 `ZeroDivisionError`。原因是根 IFD 的 LensInfo（50736）写成 `0/100, 0/100, 0/0, 0/0`，MOUNT 单元装手动镜头时光圈未知。也就是说工作室现在读不了 MOUNT 的 DNG。修法：有理数分母为 0 时读成 0 或 NaN，本目录 `gxr_hdr.Tiff` 就是这么做的。
- **生成时机**：导入时，如果一张照片同时有 JPG 和 DNG，就在后台任务里生成 `<名>_HDR.JPG`，作为派生文件放进图库。原 JPG 和 DNG 不动，哈希不变。耗时约 0.8 秒/张（单进程，含 DNG 解码）。没有 DNG 的照片不生成。
- **导出**：导出选项里加"HDR（增益图）"。工作室里做过的编辑会改变 SDR，所以导出时对编辑后的 SDR 重新拟合曲线 T、重算增益：
  - 裁切/旋转：RAW 亮度先做同样的几何变换；
  - 边框、日期戳：区域内增益 = 0；
  - 曝光、曲线：本方法本来就按每张的"RAW → SDR"关系自动适应。
- **界面文案**沿用 Apple 照片的说法"HDR"，不用新造的词。可以加一个开关"导出时保留 HDR"。
- 把 `gxr_hdr.py` 的计算和封装两部分搬进 `studio/src/gxr_studio/`，要按工作室规范补测试。可以直接把本目录的 `selfcheck.py` 和 `check_imageio.swift` 当验收：①主图字节保留，②ImageIO 识别，③系统提亮与规格一致。

## 7. 远期：在相机里直接做需要什么

相机已经会写 MPF 两幅图（主图 + 640×424 预览），把预览那一格换成增益图，是最自然的切入点。需要：

1. **拍后钩子**：在 JPEG 编码完、写卡之前拿到控制权。现在的常驻代码空间是 0 字节余量，需要等机身更新（body v4 / arch B 永久内存扩展）。
2. **数据来源**：RAW 缓冲区（或拍 RAW+JPG 时的 RAW 数据），算 1072×712 的块平均亮度；再拿到 JPG 编码前的 SDR，或者直接用配方曲线 T。机内知道配方的色调曲线，不需要拟合，比电脑端更准。
3. **算增益并编码 1072×712 灰度 JPEG**：用相机的硬件 JPEG 编码器第二次编码，或者用软件编码（约 76 万像素，速度待测）。
4. **改写文件写入器**：插入 XMP 和 ISO APP 段，按真实大小重写 MPF 第二条记录。
5. **风险和验证**：要刷机身；按"先探针、可恢复"的规则走测试卡，必须有官方固件可恢复的保证。相机回放看不到 HDR 效果，只能拷到 iPhone 上验证。

在那之前，电脑端（工作室导入时）生成是零风险、立刻可用的路线。

## 8. 产物位置

- 15 张成品：`captures/hdr-gainmap-proto/R805xxxx_HDR.JPG`，增益图可视化 `R805xxxx_gainmap.png`（每张按自己的最大增益归一化，白 = 提亮最多），`stats.json`，`selfcheck.json`。这个目录被 git 忽略。
- 给用户隔空投送的 5 张：`~/Downloads/GXR-HDR-samples/`，分别是 1653（夜里招牌，黑白，效果最强）、1627（灯笼灯泡）、1532（白天楼面和天空，黑白）、1533、1531（白天彩色）。
- 临时文件放在 `/Volumes/Workspace/Scratch/tmp/projectricoh/hdr-gainmap`，结束时已删除，包括只读参考用的 libultrahdr 源码文本。
