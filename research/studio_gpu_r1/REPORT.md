# GXR Studio 显卡预览：实测报告（studio_gpu_r1）

**结论（大白话）**
1. 网页能做到 Capture One 那样顺滑。原型拖滑块时，每动一下就出一张新画面，跟着屏幕 120 Hz 刷新，一帧不掉；从手动到画面变，中位数约 8 毫秒。现在的工作室拖动时大约每秒才 1 张新画面，中位数要等 0.8–1 秒。
2. 颜色和现有 Python 渲染逐像素对得上：45 组对比里，≥99.85% 的像素一模一样，≥99.995% 的像素差不超过 1 个码值（个别像素最多差 7 个码值，见更正），平均色差 ΔE2000 ≤0.001。目标是平均 ≤1、p95 ≤2，余量很大。
3. 慢的根子是 Python 在每次拖动、每次换照片时都重算整张图。同样的算法放到显卡上：换照片从 1.4–1.6 秒降到 0.01–0.1 秒；全尺寸导出从 2.4–8.9 秒降到 0.17–0.37 秒。
4. 推荐 WebGPU（不是 WebGL2），界面换成 TypeScript。最终形态推荐 (b)：网页界面 + Rust 核心（wgpu），浏览器和本机共用同一份 WGSL 着色器，Mac 和 Windows 都能用。Python 留作测试里卡颜色的参考实现。细节见 `ARCH.md`。

> **更正（2026-11-02 13:20）：**本报告初版写的「全部像素差 ≤1 个码值」不准确。
> - 「≤1 码值」那一列的占比按 4 位小数四舍五入后显示为 100%。
> - 原始数据里，部分参数组有个别像素差 2–7 个码值：预览 45 对里有 16 对，导出 8 对里有 4 对，占比 <0.005%。
> - 原因是连续几步 uint8 取整把 float32 的取整翻转放大了。
> - 平均和 p95 的结论不变。

下面的数字，标「本机实测」的是这台 MacBook Pro M1 Pro 16 GB 上实际跑出来的；标「估计」的是推算，不是测量。

## 测量环境（本机实测）

| 项 | 值 |
|---|---|
| 机器 | MacBook Pro M1 Pro，16 GB，macOS（Darwin 27.0），内建屏 3456×2234（ProMotion 120 Hz），DPR 2 |
| 浏览器 | Google Chrome 156.0.8078.74，有窗口（不是无头），独立用户目录 |
| 显卡 | WebGPU 适配器 `vendor=apple, architecture=metal-3`，`isFallbackAdapter=false`；WebGL 渲染器 `ANGLE (Apple, ANGLE Metal Renderer: Apple M1 Pro)`，不是 SwiftShader |
| 同时负载 | 全程 load average 7–17，WKWebView 那一轮 35–37。基线测量时有 3 个别的 Python 进程各占 60–70% CPU，内存 15 GB 已用，只剩约 114 MB 空闲，6.2 GB 在压缩区。所有数字都是在这种负载下测的 |
| 素材 | 6 张 GXR DNG：50mm 3 张（R8051410、R8051448 为 ISO 200，R8051312 为 ISO 1600），MOUNT 3 张（R8051691、R8051699、R8051707） |
| 工作室 | 临时图库，端口 49711；相机数据用 g127 夹具 DAT 和研究目录的标定文件。原型静态服务端口 49712 |

GXR DNG 已核实：Compression=1（未压缩），12 位打包。RAW 平面 4304×2862，每行 6456 字节，条带 18,477,072 字节，文件 18.66 MB。DefaultCrop 4288×2848，黑电平 0，白电平 4095，没有线性化表，CFA 为 RGGB。

## 1. 基线：现有工作室（本机实测）

测法：用 CDP 发真实鼠标事件，拖「曝光」滑块 4 秒（60 Hz 鼠标，正弦来回）。记录每个 `input` 事件，到第一张「请求晚于这次输入」的图片解码、显示完（再过 2 个 rAF）的时间。数据在 `data/baseline-r1.json`。

| 项 | 第 1 轮 | 第 2 轮 |
|---|---|---|
| 4 秒内 `input` 事件 | 124 | 124 |
| 发出的预览请求 | 3 | 3 |
| 拖动中新画面频率 | ≈1 张/秒（只在手停顿时） | ≈1 张/秒 |
| 输入 → 新画面 p50 / p95 / 最大 | 1050 / 1750 / 2017 ms | 792 / 1626 / 1893 ms |
| 服务器出 1600 px 预览 | 548 ms（含第一次烘焙）、180、180 ms | 60、66、68 ms |
| 松手后清晰画面 | 306 ms | 193 ms |

| 换照片（带配方 01） | 冷 | 热（第二次看） |
|---|---|---|
| 到画面出现 | 1420–2072 ms（4 张） | 1389–1541 ms（4 张） |
| 没有编辑的照片（直接回相机 JPG） | 141 ms | 132 ms |

原因（读代码确认）：
- `preview.js` 的防抖是 120 ms，每次输入都会重置，所以手一直在动就一直不发请求。
- 松手和换照片时请求 `size=full`，服务器每次都对 4288×2848 全尺寸去马赛克再编 JPEG，不进缓存，所以「热」和「冷」一样慢。
- `stage.js` 的 `paintStage` 每次都 `replaceChildren` 整块重建 `<img>`，同一张预览在 DOM 里被加了两次，这就是机主说的「整块硬刷新」。
- 截图：`data/baseline-r1-adjust.jpg`。

## 2. 显卡原型（本机实测）

原型在 `proto/`。服务器只读调用 `studio/src/gxr_studio` 做一次烘焙，浏览器之后的每次调整都在 WGSL 着色器里算。按现有算法逐项对应：
- 曝光和色温色调：`tones.channel_gains`。
- 一维曲线 → YCbCr 矩阵 → (Cb,Cr) 复数增益网格 → BT.601：`chain._chroma_chunk`。
- 对比、高光、阴影、主曲线的 1021 点调子表：`tones.display_table`，PCHIP 移植到 JS。
- 黑点、饱和度、自然饱和度、暗角：`pixels.apply_extra`。
- LUT 后的调整：`pixels.apply_base`。
- 显示类与 Log 类 LUT：`spaces.Target.render`，四面体插值与 `cube.tetrahedral` 相同。
- 拉直和裁切：`geometry._straighten_coords`、`_sample`、`crop_valid`。

每个 Python 会落成 uint8 的地方，着色器都照样取整。

截图：`data/prototype-screenshot.jpg`。照片是 MOUNT R8051707，配方 05，曝光 +0.3、高光 −35、阴影 +25、自然饱和度 15、暗角 −20、S 形曲线、拉直 2.5°、裁切。面板上的曲线按钮没同步显示「S 形」，但画面里已经套了曲线。

### 2.1 拖动（本机实测）

真实鼠标 120 Hz，每轮 4 秒。逐帧数据在 `data/proto-drag-frames-*.json`，汇总在 `data/proto-drag.json`。

| 滑块 | 输入 | 出帧 | rAF 间隔 平均 / p95 / 最大 | 超过 1.5 帧的间隔 | 输入 → 显卡画完 p50 / p95 | 输入 → 下次刷新 p50 / p95 | 每帧 CPU 编码 |
|---|---|---|---|---|---|---|---|
| 曝光（配方 01） | 128 | 128 | 8.33 / 9.3 / 9.4 ms | 0 | 2.8 / 3.3 ms | 8.4 / 9.1 ms | 0.3 ms |
| 曝光（配方 04 + LUT） | 128 | 128 | 8.33 / 9.3 / 9.4 ms | 0 | 4.9 / 5.8 ms | 8.3 / 9.3 ms | 0.3 ms |
| 阴影 | 256 | 256 | 8.33 / 9.3 / 9.4 ms | 0 | 3.2 / 3.6 ms | 8.5 / 9.5 ms | 0.3 ms |
| 拉直 | 440 | 440 | 8.33 / 9.0 / 9.3 ms | 0 | 2.0 / 2.5 ms | 8.7 / 9.3 ms | 0.3 ms |

- 「出帧」= 输入数。每个值的变化都画出来了，没有被跳过的输入。帧率的上限是鼠标事件和滑块步长，不是显卡。
- 一帧显卡吞吐（颜色 + 几何，连续提交 60 次取平均）：输出 2560×1600 时 0.86–1.15 ms，3456×2234 时 0.89–0.97 ms。8.3 ms 的预算还剩约 7 ms。
- 「下次刷新」是显卡画完之后的下一个 rAF 时刻，近似屏幕上出现的时间。Chrome 不给真实上屏时刻。

### 2.2 换照片、显存、内存（本机实测）

| 情形 | 到第一帧 p50 / 最大 | 拆分 |
|---|---|---|
| 已在显存（LRU 8 张） | 14.7 / 22.6 ms（7 次） | 只是换绑定组 + 画一帧 |
| 第一次：下载服务器做好的 float16 代理（24.4 MB）+ 8 个配方表 | 82 / 176 ms（5 张） | 下载 53–149 ms，上传 10–15 ms |
| 第一次：下载 DNG 原字节（18.66 MB），显卡拆包 + 2×2 合并成 float32 代理 | 82.5 / 99.5 ms（6 张） | 下载 41–48 ms，上传 + 合并 19–32 ms |
| 第一次编译着色器管线 | 1559 ms（冷）；之后 10–19 ms | Chrome 有着色器缓存 |

| 内存 | 值 |
|---|---|
| Chrome GPU 进程常驻 | 162–167 MB（本机实测） |
| Chrome 全部进程 | 0.93–1.03 GB（本机实测，含 3 个渲染进程） |
| JS 堆 | 1.2 MB（本机实测） |
| 每张照片的显存 | float16 代理 24.4 MB + 颜色层 12.2 MB + 8 个配方表约 8 MB ≈ 45 MB；float32 代理 ≈ 69 MB（按纹理尺寸计算） |
| 缓存 8 张 | 360–550 MB（计算）。M1 Pro 是统一内存，这部分不完全反映在进程常驻里 |

### 2.3 WKWebView（Safari 和 Tauri 在 macOS 上的 WebKit）里的同一原型（本机实测）

`tools/wkwebview_probe.swift` 开一个小窗口，载入同一页面。
- 驱动方式是程序每个 rAF 改一次曝光，不是真实鼠标。
- WebKit 的 `performance.now()` 精度是 1 ms。
- 测量时 load average 35。

| 项 | 值 |
|---|---|
| `navigator.gpu` | 有，适配器正常 |
| rAF 间隔（空闲、拖动中） | p50 17 ms，p95 18–19 ms，即约 **60 Hz**。Chrome 在同一屏上是 120 Hz |
| 改参数 → 显卡画完 | p50 3 ms，p95 5 ms，最大 10 ms |
| 显卡每帧（颜色 + 几何） | 0.97–1.27 ms（与 Chrome 相同） |
| `rgba16float + display-p3 + extended` 画布 | 接受 |

60 Hz 的原因：WebKit 默认开着「Prefer Page Rendering Updates near 60fps」。
- Safari 用户可以在功能旗标里关掉；
- WKWebView 没有公开接口，只能用私有接口（例如 `tauri-plugin-macos-fps`）。

所以 macOS 上要 120 Hz，用 Chrome（浏览器模式），或在 Tauri 里用这个私有开关。

## 3. 颜色一致性（本机实测）

做法：
- 浏览器把着色器输出读回，裁切后的整幅画面缩放为 1。
- Python 参考用 studio 现有函数在同一份半分辨率码值上算（`proto/reference.py`），不做 JPEG，存无损 PNG。
- 逐像素算 ΔE2000，用 `gxr_studio.engine.colour.delta_e00`。
- 6 张 DNG × 8 组参数（`proto/paramsets.json`）共 45 对，每对 2144×1424（几何组 1608×1139）。Log LUT 组只跑 50mm。

参数组：
- s1：配方 01。
- s2：配方 02 + 曝光 +0.7、色温 +30、色调 −20、对比 +40、高光 −50、阴影 +40。
- s3：配方 04 + 曲线 + 黑点 20、饱和度 30、自然饱和度 25、暗角 −40。
- s4：配方 03 黑白 + 曝光 −0.5、对比 −30。
- s5：配方 04 + 显示类 LUT（sRGB）+ 曝光、饱和度、对比。
- s6：配方 01 + 显示类 LUT（Rec.709 → Gamma 2.4）+ 色温 −25、阴影 +30 + 曲线。
- s7：Log LUT（L-Log → Gamma 2.4）+ 曝光 −0.3。
- s8：配方 05 + 曝光 + 拉直 3.5° + 裁切。

| 参数组 | 对数 | **float32 代理**（DNG 字节在显卡上合并）<br>平均 / p95 / 最大 ΔE00 / 逐字节相同 | float16 代理（服务器下发）<br>平均 / p95 / 最大 / 逐字节相同 |
|---|---|---|---|
| s1 配方 01 | 6 | 0.0000 / 0 / 1.08 / 100.00% | 0.022 / 0 / 1.82 / 96.22% |
| s2 配方 02 + 调子 | 6 | 0.0000 / 0 / 0.97 / 99.99% | 0.017 / 0 / 1.49 / 96.69% |
| s3 配方 04 + 曲线 + 四项 | 6 | 0.0000 / 0 / 2.57 / 100.00% | 0.032 / 0 / 5.41 / 96.13% |
| s4 配方 03 黑白 | 6 | 0.0000 / 0 / 0.40 / 100.00% | 0.002 / 0 / 0.40 / 99.48% |
| s5 显示类 LUT | 6 | 0.0000 / 0 / 2.30 / 99.99% | 0.022 / 0 / 5.56 / 97.34% |
| s6 Rec.709 LUT + 曲线 | 6 | 0.0000 / 0 / 1.54 / 100.00% | 0.018 / 0 / 2.65 / 97.00% |
| s7 Log LUT（50mm） | 3 | 0.0000 / 0 / 1.18 / 100.00% | 0.015 / 0 / 2.09 / 97.27% |
| s8 拉直 + 裁切 | 6 | 0.0007 / 0 / 1.27 / 99.85% | 0.020 / 0 / 1.90 / 96.50% |
| **合计 45 对** | 45 | 平均 ≤0.0007，p95 = p99 = 0，最大 2.57；≥99.995% 像素差 ≤1 码值，个别像素最多 7 码值 | 平均 ≤0.032，p95 0，p99 ≤1.06，最大 5.56，ΔE>1 的像素 ≤1.12% |

- 「平均」和「p95」列取的是 6 张里最差的一张，「逐字节相同」取最低的一张。表里的 0.0000 是四舍五入后的值。
- float16 的残差全部来自代理图量化。让 Python 也吃同一份 float16 码值时，平均为 0，逐字节相同 ≥99.85%（`vs_python_f16_input`）。所以着色器本身与 Python 等价，产品里代理图用 float32，或在显卡上从 DNG 生成。
- 剩下零星 1 码值的差，来自取整边界上 float32 运算顺序不同。陡的 LUT 会把 1 个码值放大到 ΔE 2–4，但只是个别像素。
- WebKit（WKWebView，即 Safari 和 Tauri 在 macOS 上的引擎）同样跑了 2 张 × 全部参数组，共 15 对（`tools/wkwebview_probe.swift`，`data/delta-e-wkwebview*.json`）：
  - float32 路径：平均 ≤0.0004，p95 0，最大 2.39，≥99.995% 像素 ≤1 码值（个别最多 7）；
  - float16 路径：与 Chrome 相同（平均 ≤0.02）。
- 软件适配器（SwiftShader，CI 用）同样跑 45 对（float32）：平均 ≤0.0006，p95 0，最大 3.04，≥99.995% 像素 ≤1 码值（个别最多 7）。数据在 `data/delta-e-swiftshader-rawgpu.json`。
- 现有工作室自己也不一致。它的显示类 LUT 预览先把底图编成 JPEG q95 再套 LUT（`lut/photo.py` → `render_preview(quality=95)`），这一步本身就和无损参考差了不少：s5 平均 0.87–3.63、p95 4.0–11.0；s6 平均 0.41–2.22、p95 2.2–5.5。导出时没有这一步，所以现在的预览和导出对不上；显卡路径没有这个问题。

### 3.1 全尺寸导出一致性（本机实测）

显卡从 DNG 12 位打包字节开始，在着色器里依次做：拆包 → 白平衡 → MHC 5×5 去马赛克（逐项照 `raw/demosaic.py`，镜像延拓）→ 导出用 0.5 网格的配方链 → 成片调整。Python 参考用 `render_full` + 同一组成片函数。2 张（50mm R8051410、MOUNT R8051691）× 4 组（s1、s2、s3、s5），每张 4288×2848。

| 实现 | 平均 / p95 / 最大 ΔE00 | 逐字节相同 | ≤1 码值 | ΔE>1 的像素 |
|---|---|---|---|---|
| Chrome WebGPU | 0.0000 / 0 / 3.97 | ≥99.995% | 100% | ≤0.001% |
| 本机 wgpu（Metal，同一份 WGSL 文件） | 0.0000 / 0 / 3.63 | ≥99.995% | 100% | ≤0.001% |

## 4. Python 还在哪些环节、各要多久（本机实测）

`tools/py_stages.py`，DNG 已在系统缓存里，每项 3 次。

| 环节 | 耗时 | 备注 |
|---|---|---|
| 冷打开：读文件 | 2.4–3.0 ms（已缓存）；21–31 ms（首次） | |
| 冷打开：TIFF 解析 + 全文件 SHA-256 | 7.9 ms | |
| 冷打开：12 位拆包 | 19.6–41.8 ms | |
| 冷打开：半分辨率码值（归一化 + 白平衡 + 2×2 合并） | 68–85 ms | 现有预览不做去马赛克 |
| 冷打开：转正 + 转 float16 | 10 ms | |
| **冷打开到代理图就绪** | **108 ms** | 再传给浏览器还要 53–149 ms（24 MB） |
| 全尺寸 MHC 去马赛克 | 523–537 ms | 只在导出时 |
| 烘焙一个配方（预览网格 0.75） | 141–149 ms | 第一次看 8 个配方 ≈ 1.1 s |
| 烘焙一个配方（导出网格 0.5） | 294–303 ms | 现在每次导出都重烘，不缓存 |
| 改一个相机旋钮（resolve + 重烘） | 142 ms | 旋钮每动一格都要等 |
| 解析 .cube（33³ / 65³） | 45 ms / 370 ms | 每个 LUT 一次 |
| 每次改参数，代理图分辨率重算（不含 JPEG） | 配方 102–135 ms（中位），加四项 402 ms，几何 511 ms，LUT 1473–1657 ms | `data/python-preview-render-timings.json` |
| 全尺寸导出：去马赛克 + 配方链 | 0.96–1.15 s | |
| 全尺寸导出：+ 四项成片调整 | 再 +1.17–1.24 s | `apply_extra` 是逐步 uint8 的 numpy |
| 全尺寸导出：显示类 LUT | 8.5–8.9 s | 四面体 3.8–4.1 s + apply_base 1.6–3.4 s |
| JPEG q95 编码（PIL / libjpeg-turbo） | 37–71 ms | 比浏览器和纯 Rust 编码器都快 |
| 工作室导出接口（配方 01，含写 EXIF、fsync） | 2.36–2.81 s | load 17 时 |
| 工作室导出接口 + HDR 增益图 | 5.05–5.15 s | |

**后台批量生成代理图时，前台会不会被卡住**（`data/python-blocking.json`）：
- 前台请求：生成 1500 张照片的列表 JSON（纯 Python，要拿 GIL）+ 读一张缓存代理，每 50 ms 一次。
- 后台：3 个工作者在 1.5 s 内做完 24 张代理。

| 后台 | 前台 p50 / p95 / 最大 |
|---|---|
| 无 | 5.3 / 30.2 / 34.0 ms（机器本身负载的抖动） |
| 同进程 3 线程 | 6.6 / 8.3 / 24.9 ms |
| 进程池 3 进程 | 7.3 / 14.0 / 16.4 ms |

结论：numpy 大段计算会放开 GIL，后台生成代理不会明显卡住前台，进程池把最坏值再压低一些。真正会卡住前台的是代码里的锁：
- `RenderService._proxy` 在 `with self._lock:` 里解码 DNG。
- `_gate` 只允许 2 个并发渲染。

后台预生成如果走 `RenderService`，会和前台预览排队。做法是：
- 预生成放进独立进程池，写磁盘缓存；
- 前台只读缓存，不进那把锁。

**哪些能靠「导入后后台预生成 + 缓存」消掉**：
- 代理图：108 ms/张，3 个进程约 16 张/秒。
- 8 个配方的预览烘焙：1.1 s/单元，和照片无关，每个单元 × ISO 模型只做一次。
- 缩略图。
- HDR 增益图（导入后已经在后台做）。

**仍会让人等的**：
- 相机旋钮每动一格要重烘 142 ms。不到 Lightroom 的 1 秒，但滑块会变成约 7 帧/秒的跳动。
- 全尺寸导出 2.4–8.9 s，HDR 5 s，明显超过 Lightroom。显卡导出实测 0.17–0.37 s。

按「只有超过约 1 秒才建议换原生」的标准，需要换的只有导出（含 HDR）这一块；旋钮烘焙在 Rust 或显卡上估计 ≤10 ms（估计，未实现）。

## 5. 「后台不用 Python」能快多少（本机实测）

| 环节 | Python | 显卡（浏览器 WebGPU） | 显卡（本机 wgpu / Metal，同一 WGSL） | 倍数 | ΔE00 平均 / p95 / 最大 |
|---|---|---|---|---|---|
| 打开一张 DNG 到可调 | 108 ms 代理 + 53–149 ms 传输 ≈ 160–260 ms | DNG 下载 41–48 + 显卡拆包合并 19–32 = 73–100 ms（含第一帧） | 读文件 3 ms + 上传和合并约 20 ms ≈ 25 ms（估计，用导出实测的上传和显卡分段推算） | 1.6–3.6×（浏览器）；只比计算部分 108 vs 19–32 ms 是 3.4–5.7× | 0.0007 / 0 / 2.57 |
| 每次改参数 | 102–1657 ms（代理图分辨率，不含 JPEG） | 0.9–1.2 ms 显卡，输入到刷新约 8.4 ms | 同左（估计） | 约 85–1800× | 同上 |
| 全尺寸去马赛克 | 523 ms | 包含在下行 | 包含在下行 | | |
| 全尺寸导出（配方） | 0.96–1.19 s（库函数）；2.36–2.81 s（工作室接口） | 读 18–64 + 上传 9–21 + 显卡 18–49 + 读回 12–39 + JPEG 100–215 = 170–370 ms | 读 2.4–25 + 上传 5–12 + 显卡 28–39 + 读回 7–11 + JPEG 120–134 = 171–218 ms | 对库函数 4.4–7×；对工作室接口 11–16× | 0.0000 / 0 / 3.97 |
| 全尺寸导出（加四项） | 2.24–2.37 s | 同上 | 177–183 ms | 12–13× | 同上 |
| 全尺寸导出（显示类 LUT） | 8.5–8.9 s | 同上 | 177–186 ms | 46–50× | 同上 |

- 本机 wgpu 首次建设备 667 ms，只在程序启动时一次。
- 导出里 JPEG 编码占大头。纯 Rust `jpeg-encoder` 120–134 ms，浏览器 `convertToBlob` 100–215 ms，ImageIO 61–65 ms，PIL 37–71 ms。换成 libjpeg-turbo 绑定后，本机导出估计可到约 90 ms（估计）。

**Mac 上的上限参照 (c) Swift + Metal（本机实测，`data/swift-metal-reference.json`）**：
- Apple 自带的 CIRAWFilter 解 GXR DNG 全尺寸：首次 804 ms，之后 88–124 ms。
- 半尺寸草稿：62–67 ms。
- ImageIO JPEG q95：61–65 ms。
- 这是 Apple 的颜色，不是我们的配方，只用来说明原生框架的速度上限。我们自己的显卡管线已经在同一量级。

## 6. 没有 WebGPU 时的退路

| 退路 | 拖动时颜色变化 | 只动几何 | 换照片 | 颜色 | 来源 |
|---|---|---|---|---|---|
| 同一份 WebGPU 代码跑在 SwiftShader（纯 CPU 软件适配器） | 输入 → 画完 p50 129–409 ms、p95 260–560 ms，约 6–7 帧/秒 | p50 116 ms，约 30 帧/秒 | 已缓存 122–145 ms；首次 197–291 ms | 与 Python 一致（≤1 码值） | 本机实测，`data/proto-swiftshader.json` |
| 现有 Python 服务器出图（今天的工作室） | 0.8–1.0 s p50 | 同左 | 1.4–1.6 s | 预览 LUT 有 JPEG 误差 | 本机实测 |
| WebGL2（同一算法改写成 GLSL ES 3.00 片元着色器，`proto/engine_gl.js`，同一台 M1 Pro） | 每次输入都出帧；rAF 平均 8.33 ms、p95 10.2 ms；输入 → 显卡画完 p50 6.0–10.4 ms，输入 → 下次刷新 p50 8.4–16.2 ms、p95 10.3–18.5 ms；显卡每帧 1.5–2.7 ms | 输入 → 刷新 p50 8.7 ms | 已缓存 14–16 ms；首次 90–167 ms | 与 WebGPU 的 float16 路径完全相同：同输入时全部 ≤1 码值，平均 ≤0.0007 | 本机实测，`data/proto-webgl2.json`、`data/delta-e-webgl2.json` |

- SwiftShader 这一行是在本机 CPU 上跑的，同时有 load 8–12 的别的负载。
- WebGL2 没有计算着色器，所以只做了「服务器下发 float16 代理」这条路；从 DNG 字节在显卡上合并、显卡导出都需要 WebGPU。WebGL2 版每帧显卡时间约是 WebGPU 的 1.5–3 倍（同一台机器），仍在 120 Hz 预算内。
- 没有独显的老 Windows 机器只要有 D3D12 显卡，就走 WebGPU 正常路径，不用退路。
- 退路只给没有 D3D12/Metal/Vulkan 的机器，以及 Linux 上 Chrome 默认关着 WebGPU 的显卡。

## 7. 三种最终形态（按性能和效果）

详细打分、Windows 怎么做、HDR 支持、CI 方案都在 `ARCH.md`。简表：

| | (a) 网页 + 浏览器 WebGPU，后台 Python | (b) 网页/TS + Rust 核心（wgpu），同一 WGSL | (c) Swift + Metal（只作 Mac 上限参照） |
|---|---|---|---|
| 拖动 | 120 Hz，输入到刷新 8.4 ms（本机实测） | 同 (a)：预览在浏览器或 WebView 的 WebGPU 里 | 120 Hz（估计） |
| 冷打开 | 73–100 ms（浏览器从 DNG 字节做，本机实测） | 同 (a)；本机侧约 25 ms（估计） | 草稿 62–67 ms（CIRAWFilter 本机实测） |
| 导出 | Python 2.4–8.9 s；改由浏览器 WebGPU 导出则 0.17–0.37 s | 0.17–0.22 s（本机实测） | 约 0.1 s（估计） |
| 所见即所得 | Python 导出：两套实现，靠测试卡；浏览器导出：同一代码 | 同一份 WGSL，浏览器和本机都实测 ≥99.995% 像素 ≤1 码值 | 单一实现 |
| 颜色对上 Python | 是（本机实测） | 是（本机实测，浏览器和 wgpu 两边） | 需要把 WGSL 转成 MSL（naga 能转），估计能对上 |
| P3 / HDR | Chrome 和 WKWebView 都实测接受 `rgba16float + display-p3 + extended`，`(dynamic-range: high)` 为真；屏幕上是否真的亮于 SDR 白，截图无法证明，要人眼确认 | 同 (a)；导出的 Ultra HDR 在本机算 | 最好（CAMetalLayer EDR） |
| 120 Hz | Chrome 本机实测 120 Hz；Safari 默认约 60 Hz（WebKit 的 60 fps 偏好，用户可在功能旗标里关掉） | Chrome/浏览器模式 120 Hz（本机实测）；Tauri 的 WKWebView **本机实测 60 Hz**（rAF p50 17 ms），只能用私有接口解除 | 是 |
| Windows | Chrome/Edge 走 D3D12 | WebView2 或浏览器 + wgpu（D3D12/Vulkan） | 不能用 |

**推荐 (b)。**
- 拖动和打开上，(a) 和 (b) 一样快，因为都在同一个浏览器显卡管线里。
- 导出、批量、导入后预生成、HDR 增益图这些「不在浏览器标签页里」的重活，(b) 用同一份着色器在本机跑，实测 0.17–0.22 s。
- Windows 上 (b) 可以打成单个安装包，不需要机主朋友装 Python 和 uv。
- Python 保留在测试里当颜色参考：CI 里逐像素比较着色器输出和 Python。

## 8. 显卡上做不到逐字节一致的地方，以及做法

| 操作 | 现状 | 原因 | 做法 |
|---|---|---|---|
| 半精度代理 | float16 时个别像素最大 ΔE 5.6 | 码值量化 | 代理用 float32，或显卡从 DNG 直接生成（已实测 ≥99.995% 像素 ≤1 码值） |
| 取整边界 | 极少数像素差 1 码值；连续几步 uint8 取整（曲线、黑点、饱和度、暗角、陡的 LUT）会把个别翻转放大到 2–7 码值 | float32 运算顺序和 pow 等超越函数的精度（numpy 与 GPU 不同） | 接受；CI 门槛设「≤1 码值的像素 ≥99.99%，平均 ΔE ≤0.01」 |
| 显示类 LUT 的预览 | 现有预览比导出多一次 JPEG q95，平均 0.4–3.6 ΔE | `lut/photo.py` 用 `render_preview(quality=95)` 当底图 | 显卡路径直接用未编码的底图；Python 参考也应改成无损（这是给 studio 的建议，本轮没改） |
| HDR 增益图（导出） | 原型未做 | 需要 RAW 亮度层跟着几何走，并做 ISO 21496-1 封装 | 增益图的逐像素部分（亮度比、几何）放显卡；封装（`hdr/container.py`）是字节操作，留在本机核心。HDR 预览用 `rgba16float + extended` 画布 |
| 透视、畸变（`_warp_expanded`） | 原型只做了拉直 | 时间盒 | 同样是逐像素的取样坐标，放进几何着色器；有效区域的矩形计算（`fit_preset_in_valid` 等）在 CPU 上按参数算，不是逐像素 |
| 方向（Orientation ≠ 1） | 原型只处理 1（测试素材都是 1） | 时间盒 | 合并和去马赛克时按方向写坐标 |
| 去马赛克的差异 | 预览用 2×2 合并（与现有 Python 预览相同），导出用 MHC（与 Python 导出相同） | 两者本来就不同 | 保持；100% 放大时用全尺寸 MHC 纹理分块 |
| 日期戳、边框 | 原型未做 | 文字排版 | 预览用画布或 DOM 叠层；导出在本机核心排版后合成。像素级一致要用同一字体和同一排版代码 |
| 局部调整（以后） | 现在没有 | | 显卡计算着色器（引导滤波、蒙版）；Python 没有对应实现，以显卡实现为准 |
| 只有 JPG 的「近似」配方 | 原型未做 | | `finish.approx.apply_lut` 是 3D 表，直接成 3D 纹理 |

## 9. 怎么重跑

全部在仓库根目录执行。`S=/Volumes/Workspace/Scratch/tmp/projectricoh/studio-gpu-r1`，`TMPDIR=$S/tmp`。

```bash
# 0. 应用数据（理光数据只写到 scratch）和假卡
studio/.venv/bin/python research/studio_gpu_r1/tools/make_home.py $S/home
#    把 6 对 DNG+JPG 复制到 $S/volumes/FAKECARD/DCIM/100RICOH/（文件名见上文）

# 1. 基线：启动一份工作室，从假卡导入，再测
GXR_STUDIO_VOLUMES=$S/volumes GXR_STUDIO_LIBRARY=$S/library GXR_STUDIO_EXPORT=$S/export \
GXR_STUDIO_HOME=$S/home GXR_STUDIO_TOKEN=gpu-r1-local-only studio/.venv/bin/gxr-studio --no-browser --port 49711
node research/studio_gpu_r1/tools/baseline.mjs http://127.0.0.1:49711 gpu-r1-local-only \
  research/studio_gpu_r1/data/baseline-r1.json $S/chrome <照片 id,逗号分隔>

# 2. 烘焙 + Python 参考
studio/.venv/bin/python research/studio_gpu_r1/proto/bake.py $S/home $S/gpudata jlaunch:<DNG> ... l08firm:<DNG> ... \
  --lut "名字=输入空间:输出空间:<cube>"
studio/.venv/bin/python research/studio_gpu_r1/proto/reference.py $S/home $S/gpudata

# 3. 原型服务器 + 测量（阶段：smoke,hdr,switch,drag,readback,rawgpu,export,shot）
studio/.venv/bin/python research/studio_gpu_r1/proto/serve.py $S/gpudata $S/readback 49712
node research/studio_gpu_r1/tools/proto_measure.mjs http://127.0.0.1:49712/proto/index.html \
  research/studio_gpu_r1/data/proto-drag.json $S/chrome drag
#    CPU 退路：CHROME_EXTRA="--use-webgpu-adapter=swiftshader --enable-unsafe-swiftshader --enable-unsafe-webgpu"

# 4. 色差
studio/.venv/bin/python research/studio_gpu_r1/tools/compare.py $S/gpudata $S/readback out.json [--rawgpu|--full]

# 5. Python 各环节、阻塞测试
studio/.venv/bin/python research/studio_gpu_r1/tools/py_stages.py $S/home $S/gpudata out.json [--blocking-only]

# 6. 本机 wgpu（同一 WGSL）和 Swift 参照
node research/studio_gpu_r1/tools/dump_inputs.mjs $S/gpudata $S/native
CARGO_HOME=$S/cargo CARGO_TARGET_DIR=$S/target cargo build --release --manifest-path research/studio_gpu_r1/tools/native_wgpu/Cargo.toml
$S/target/release/native_wgpu $S/native/export.wgsl $S/native/jobs.txt $S/readback 3
swiftc -O research/studio_gpu_r1/tools/swift_ref.swift -o $S/swift_ref && $S/swift_ref <DNG> <rgba> 4288 2848

# 7. WebGL2 退路（同一测量脚本，换 URL）和 WKWebView（Safari/Tauri 的引擎）
node research/studio_gpu_r1/tools/proto_measure.mjs "http://127.0.0.1:49712/proto/index.html?gl=1" out.json $S/chrome drag,switch,readback
swiftc -O research/studio_gpu_r1/tools/wkwebview_probe.swift -o $S/wkwebview_probe && $S/wkwebview_probe http://127.0.0.1:49712/proto/index.html out.json
```

文件：

| 路径 | 内容 |
|---|---|
| `proto/index.html`、`engine.js`、`shaders.wgsl.js` | 原型界面、WebGPU 引擎、WGSL（预览、几何、合并、导出四个着色器） |
| `proto/engine_gl.js` | WebGL2 退路（同一算法的 GLSL ES 3.00 版；`index.html?gl=1`） |
| `proto/bake.py`、`reference.py`、`serve.py`、`paramsets.json` | 烘焙、Python 参考、静态服务、参数组 |
| `tools/` | CDP 驱动、基线、原型测量、色差、Python 各环节、本机 wgpu、Swift 参照 |
| `data/` | 全部实测 JSON、逐帧数据 `proto-drag-frames-*.json`、截图 |

配方表、LUT 表、代理图和读回像素是理光派生或第三方的数据，只放在 scratch，不进仓库。

## 10. 清理（已完成，2026-11-02 12:40）

- 进程：我启动的工作室（127.0.0.1:49711）已用 SIGINT 正常退出；原型静态服务（49712）已停止。
- Chrome 每轮都用 `Browser.close` 正常退出，WKWebView 和 Swift 探针跑完自行退出；检查时没有残留进程，也没有监听这两个端口的进程。
- 临时目录 `/Volumes/Workspace/Scratch/tmp/projectricoh/studio-gpu-r1/` 已整体删除，约 5.2 GB。里面有：
  - 临时图库、应用数据（g127 夹具提取的理光数据）、假卡上的 DNG 副本；
  - Chrome 用户目录；
  - 代理图、配方表、LUT 表、读回像素；
  - cargo 缓存和编译产物。
- Chrome 的 TMPDIR 指向那个临时目录，没有在内置盘留下 `code_sign_clone`（已查）。
- 没有改动 `studio/` 下任何源文件。`git status` 里 `studio/` 的改动来自另一个并行任务。有一条一次性的 `python -c` 没加 `PYTHONDONTWRITEBYTECODE`，可能刷新过 `studio/src/gxr_studio/lut/__pycache__` 里已被 git 忽略的 `.pyc`。
- 没有碰 49667 上机主正在用的工作室、`~/Pictures/GXR Studio`、`~/Pictures/GXR 导出`、`~/Library/Application Support/GXR Studio`、`/Volumes/RICOHDCX` 或任何存储卡。工作室的卷目录指向临时目录里的假卡。
- 没有任何 git 写操作。
- 仓库里只新增了 `research/studio_gpu_r1/` 下的代码、文档、实测 JSON 和两张截图（不含机主原有截图，共约 3 MB）。第三方 LUT 和理光派生数据没有进仓库。
