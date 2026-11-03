# GXR Studio 预览引擎：架构方案（studio_gpu_r1）

依据是 `REPORT.md` 里的实测。评估只看性能和效果，不把工作量或重写风险当作排除理由。Mac 和 Windows 是硬性要求，Linux 能用更好。

## 1. 性能预算

| 项 | 预算 | 原型实测（本机） | 现有工作室实测（本机） |
|---|---|---|---|
| 拖滑块：每次输入都出新帧 | 是 | 是（128–440 次输入，0 次跳过） | 否（4 秒 124 次输入只出约 4 帧） |
| 拖滑块：rAF 间隔 | 跟屏幕刷新：120 Hz 为 8.3 ms，60 Hz 为 16.7 ms；p95 ≤ 1.2 倍 | 平均 8.33、p95 9.3、最大 9.5 ms | — |
| 输入 → 上屏 | p95 ≤ 16 ms | 下次刷新 p95 9.1–9.5 ms | p95 1.6–1.75 s |
| 每帧显卡时间 | ≤ 4 ms（给 60 Hz 的老显卡留 4 倍余量） | 0.86–1.15 ms | — |
| 每帧主线程 | ≤ 2 ms | 0.3 ms | — |
| 换照片（已在显存） | ≤ 50 ms | 13–23 ms | 1.39–1.58 s |
| 换照片（第一次，DNG 在磁盘） | ≤ 150 ms | 73–100 ms | 1.4–2.1 s |
| 相机旋钮变一格（重烘配方） | ≤ 16 ms | 未做（Python 142 ms） | 142 ms + 出图 |
| 全尺寸导出 12 MP（不含写盘） | ≤ 300 ms | 171–218 ms（本机 wgpu），170–370 ms（浏览器） | 2.4–2.8 s，LUT 8.5–8.9 s |
| HDR 导出 | ≤ 600 ms | 未做 | 5.0–5.2 s |
| 颜色：显卡 vs Python 参考 | ≤1 码值的像素 ≥ 99.99%，平均 ΔE00 ≤ 0.01 | ≥99.995% 像素 ≤1 码值（个别最多 7），平均 ≤ 0.0007 | 预览 LUT 自身有 0.4–3.6 的偏差 |

## 2. 显卡 API：WebGPU，WebGL2 只做退路

选 WebGPU 的理由：

- **同一份着色器两边跑。** WGSL 在浏览器里由 Tint 编译，在本机由 naga（wgpu）编译。实测同一个 `export.wgsl` 文件，浏览器和本机 wgpu 的输出都有 ≥99.995% 像素与 Python 差 ≤1 码值。WebGL2 的 GLSL 在本机无法复用。
- **计算着色器。** 拆包、2×2 合并、MHC 去马赛克、以后的直方图和局部调整，都要计算着色器。WebGL2 只能用片元着色器绕路。
- **存储缓冲。** 配方表（4096×3 曲线 + 色度增益网格）按 `rec[]` 原样读，和 numpy 的取整、下标完全相同，所以能逐字节对上。
- **HDR 画布。** 只有 WebGPU 有 `toneMapping: { mode: "extended" }`（Chrome 129 起，见 Chrome 文档）。本机 Chrome 156 实测接受 `rgba16float + display-p3 + extended`，`(dynamic-range: high)` 为真。WebGL 没有对应的画布模式。
- **覆盖面（引用 gpuweb Implementation Status，2026-11 读取）：**
  - Chrome/Edge 113 起支持 Windows（D3D12）和 macOS；
  - Safari 26 起支持 macOS/iOS（WebKit 公告：Safari 26 在 macOS、iOS、iPadOS、visionOS 默认开启）；
  - Firefox 141 起支持 Windows，145 起支持 Apple Silicon 的 macOS 26；
  - Linux 上 Chrome 只对 Intel Gen12+（144）和 Wayland 下的 NVIDIA（147）默认开启。

WebGL2 退路：同样的逐像素算法写成 GLSL ES 3.0 的片元着色器。配方表放进 R32F 纹理，LUT 放进 RGBA32F 3D 纹理，都用 texelFetch 读。去马赛克和合并也可以用片元通道写 RGBA32F（要 EXT_color_buffer_float），这部分没有实现。

| 退路 | 速度 | 来源 |
|---|---|---|
| WebGL2 | 同一台 M1 Pro：每帧显卡 1.5–2.7 ms（WebGPU 是 0.86–1.15 ms），rAF 仍是 120 Hz，输入到刷新 p50 8.4–16.2 ms；颜色与 WebGPU 的 float16 路径相同 | 本机实测（`proto/engine_gl.js`） |
| 纯 CPU（SwiftShader，同一份 WebGPU 代码） | 颜色变化 6–7 帧/秒，几何约 30 帧/秒 | 本机实测 |
| 服务器出图（今天的做法） | 约 1 帧/秒 | 本机实测 |

## 3. 三种最终形态（性能和效果）

分数：5 最好，1 最差。分数后面的括号写依据。

| 维度 | (a) 网页 + 浏览器 WebGPU，后台 Python | (b) 网页/TS + Rust 核心（wgpu），同一 WGSL | (c) Swift + Metal（只作 Mac 上限参照，不候选） |
|---|---|---|---|
| 拖动帧率 | 5（120 Hz，输入到刷新 p50 8.4 ms，本机实测） | 5（预览同在浏览器或 WebView 的 WebGPU 里，同 (a)） | 5（估计） |
| 冷打开 | 4（浏览器读 DNG 字节在显卡上做，73–100 ms，本机实测；走 Python 代理是 160–260 ms） | 4–5（同 (a)；本机侧读文件 3 ms + 显卡约 20 ms，估计） | 5（CIRAWFilter 草稿 62–67 ms，本机实测） |
| 导出 | 2（Python 2.4–8.9 s；改由浏览器 WebGPU 导出可到 0.17–0.37 s，但离不开打开的标签页，批量和 HDR 仍在 Python） | 5（本机 wgpu 0.17–0.22 s，本机实测；JPEG 换成 libjpeg-turbo 估计约 0.09 s） | 5（约 0.1 s，估计） |
| 所见即所得 | 3（预览是 WGSL、导出是 Python，两套实现靠测试卡住；实测 ≥99.995% 像素 ≤1 码值） | 5（同一份 WGSL；浏览器和本机实测都 ≥99.995% 像素 ≤1 码值） | 5（单一实现） |
| 颜色对上 Python | 5（本机实测：Chrome 与 WKWebView） | 5（本机实测：浏览器、WKWebView、wgpu 三处） | 4（要把 WGSL 转成 MSL，naga 能转，未测） |
| P3 广色域 | 4（Chrome 和 WKWebView 的 WebGPU 画布 `display-p3` 都本机实测接受） | 4（同 (a)；导出可嵌 Display P3 ICC） | 5 |
| HDR（EDR） | 3（Chrome 和 WKWebView 都实测接受 `rgba16float + extended`；屏幕上是否真亮于 SDR 白要人眼确认；Windows 未测） | 3–4（预览同 (a)；Ultra HDR 导出在本机算，比 Python 快） | 5（CAMetalLayer EDR） |
| 120 Hz | 5（Chrome 本机实测 8.33 ms；Safari 默认约 60 Hz） | 4（浏览器模式用 Chrome 为 120 Hz；Tauri 的 WKWebView 本机实测 60 Hz，要用私有开关 `PreferPageRenderingUpdatesNear60FPSEnabled` 才到 120 Hz） | 5 |
| Windows | 4（Chrome/Edge 走 D3D12；要装 Python 和 uv） | 5（单个安装包；wgpu 走 D3D12/Vulkan；WebView2 是 Chromium） | 不能用 |
| Linux | 3（浏览器 WebGPU 只覆盖部分显卡，要 WebGL2 退路） | 3–4（wgpu Vulkan 本机侧没问题；WebKitGTK 的 WebGPU 没有确认，预览要退路，或用浏览器模式） | 不能用 |

**推荐 (b)。**
- 交互上和 (a) 相同。
- 凡是不在标签页里的重活，都用同一份着色器在本机跑：导出、批量、导入后预生成、HDR 增益图、缩略图。
- Windows 上不需要 Python 运行时。

(c) 只当 Mac 上的速度和 HDR 上限参照：
- 我们的显卡管线已经和 Apple 自带 RAW 管线在同一量级（全尺寸 88–124 ms 对 GPU 部分 28–39 ms）。
- HDR 显示上 (c) 仍更完整。

## 4. 推荐技术栈

| 层 | 选择 | 理由 |
|---|---|---|
| 界面语言 | **TypeScript** | 引擎里有大量 uniform 布局、纹理格式、缓冲偏移，类型能挡住一类错位 bug。tsc（或 tsgo）只在开发时检查。机主看到的 Cloudflare `tsrs`、theo `tsc-rs` 也只是更快的类型检查器，不影响运行速度 |
| 构建 | **Vite + pnpm** | WGSL 用 `?raw` 直接导入同一个 `.wgsl` 文件（Rust 侧用 `include_str!`），单一来源 |
| 界面框架 | **细粒度信号（SolidJS，或等价的 Svelte 5 runes）** | 拖动时只有一个数字文本节点和引擎 uniform 在变，不重建面板，没有虚拟 DOM 对比。原型用手写 DOM 证明了路径：每帧主线程 0.3 ms |
| 预览渲染 | WebGPU（`engine/` 包）+ WebGL2 退路 | 见 §2 |
| 本机核心 | **Rust + wgpu**（Metal / D3D12 / Vulkan） | 同一 WGSL；实测导出 171–218 ms |
| 外壳 | 两种都支持：①**浏览器模式**（核心起本机 HTTP 服务，用户自己的 Chrome/Edge，同今天）；②**Tauri**（macOS WKWebView、Windows WebView2） | 浏览器模式在 Chrome 里已实测 120 Hz。Tauri 在 macOS 的 WKWebView 本机实测 60 Hz，要 120 Hz 必须打开私有偏好 `PreferPageRenderingUpdatesNear60FPSEnabled=false`（现成插件 `tauri-plugin-macos-fps`）。Windows 的 WebView2 是 Chromium，预期同 Chrome（待实机）。Tauri 给 Windows 单安装包、原生文件对话框、没有本机端口和令牌。两种用同一套 TS 界面 |
| JPEG | libjpeg-turbo（`turbojpeg` crate）或 mozjpeg | 实测纯 Rust 编码器 120–134 ms，比 PIL（libjpeg-turbo）37–71 ms 慢 |
| Rust 的 WASM | 不需要 | 预览已经在显卡上；浏览器侧只需几十行 JS 解析 TIFF 找条带偏移 |

### 什么时候必须是 Rust（有数据的）

| 环节 | Python 实测 | 本机/显卡 | 说明 |
|---|---|---|---|
| 全尺寸导出 | 2.4–8.9 s | 0.17–0.22 s（wgpu 实测） | 超过 Lightroom 的约 1 秒，必须换 |
| HDR 导出 | 5.0–5.2 s | 未测；逐像素部分进显卡，估计 < 0.5 s | 必须换 |
| 旋钮重烘 | 142 ms/格 | 估计 ≤ 10 ms：`pretable.forward` 是逐点闭式运算，约 11.7 万个网格点，适合 Rust 或计算着色器 | 让旋钮也能连续拖 |
| 打开 DNG | 108 ms + 24 MB 传输 | 浏览器显卡 73–100 ms（实测） | 浏览器侧已解决，不依赖 Rust |
| 导入后预生成（代理、缩略图、增益图） | 108 ms/张代理；3 进程约 16 张/秒 | 估计 25–40 ms/张 | 导入时的后台等待 |
| DAT 编解码、相机数据 | 不是性能瓶颈 | — | 移到 Rust 只为单安装包；必须用现有 Python 用例逐字节对拍 |

## 5. 组件和数据流（b）

```
┌────────────────────────── TS 界面（Vite/pnpm，SolidJS） ──────────────────────────┐
│  面板/网格/裁切框（信号）  ──参数──▶  engine.set()  ──脏标记──▶  rAF 帧调度        │
│                                         │                                           │
│  engine/（WebGPU，WebGL2 退路）：资源 LRU、管线、color.wgsl / geo.wgsl / bin.wgsl    │
└─────────────────────────────────────────┬──────────────────────────────────────────┘
         DNG 字节、配方表、LUT 表（Tauri 自定义协议 或 本机 HTTP） │ 编辑写回（带 rev）
┌─────────────────────────────────────────▼──────────────────────────────────────────┐
│ Rust 核心：图库/SQLite、导入与卡、DNG 解析、配方烘焙、LUT 解析、导出（同一份 export.wgsl）│
│          缩略图与代理预生成（进程内线程池 + wgpu）、Ultra HDR 增益图与封装、DAT 编解码   │
└────────────────────────────────────────────────────────────────────────────────────┘
          Python（studio/src/gxr_studio）：只在测试和研究里，生成参考图、卡颜色
```

- WGSL 一份源码，按管线拆文件：`color.wgsl`（配方链 + LUT + 成片调整）、`geo.wgsl`、`bin.wgsl`、`export.wgsl`（拆包 + MHC + color）。
- 配方表只依赖（条目 SHA、ISO 模型、网格）。同单元同 ISO 的所有照片共用，显存里按条目 SHA 做 LRU。原型是每张照片各带 8 份，这是浪费。
- 预览分辨率：
  - 半分辨率代理 2144×1424，与现有预览相同。
  - 放大到 1:1 时，在显卡上对可见区域做 MHC。整幅 12 MP 实测 18–49 ms，所以按需整幅或分块都在预算内。

## 6. 界面状态：不整块重画

- **两类状态分开。**
  - 「编辑参数」是一个扁平的、可序列化的对象（与 sidecar 同构），由信号持有。
  - 「视图状态」包括当前照片、缩放、面板开合。
  - 引擎只订阅编辑参数。
- **拖动时只走一条快路径。** 输入事件 → `engine.set(partial)` → 置脏位（颜色或只几何）→ 下一个 rAF 画一次。合并同一帧里的多次输入；不发网络请求，不碰 DOM 树，只更新数值文本节点。
- **画布永不重建。** 换照片只换绑定组，换不掉的只有尺寸变化时的画布大小。叠层（裁切框、参考线、标签）是独立 DOM 或第二个画布，它们变化不触发重画照片。
- **提交与撤销。**
  - 松手 300 ms 后，把差量 PUT 到 `/edit`，带 `expected_rev`；冲突时合并或提示。
  - 撤销栈存参数快照，不存图像。
- **网格（照片墙）。** 虚拟滚动；缩略图来自磁盘缓存（核心用同一套 WGSL 生成，与编辑一致）；改了编辑的那一张只换它自己的格子。

## 7. 缓存

| 层 | 内容 | 键 | 大小 |
|---|---|---|---|
| 显存 | 代理纹理（float32 69 MB/张，或 float16 45 MB/张）、颜色中间层 | DNG SHA-256 | LRU，按机器定上限：16 GB 机器约 600 MB（8 张） |
| 显存 | 配方表 | 条目 SHA + ISO 模型 + 网格 | 每份约 1 MB（预览）、2 MB（导出） |
| 显存 | LUT 3D 表 | cube SHA + 空间版本 | 33³ 0.6 MB，65³ 4.4 MB |
| 磁盘 | 缩略图（长边 240 和 1024，WebP/JPEG） | DNG SHA + 编辑 digest + 引擎版本 + 相机数据版本（沿用现有键） | 每张 < 300 KB |
| 磁盘 | 配方烘焙结果 | 条目 SHA + ISO 模型 + 网格 + 引擎版本 | 每份 1–2 MB，导入后后台预生成本单元的 8 个 |
| 磁盘 | 代理图 | **不需要** | DNG 直接在显卡上做 2×2 合并，19–32 ms（实测），比从磁盘读 24–49 MB 代理还快 |
| 内存 | 最近 N 张 DNG 字节 | 路径 + mtime | 18.7 MB/张；预取左右相邻 2 张 |

预取：打开一张时，后台读入左右相邻的 DNG 并上传合并，使「下一张」落在「已在显存」那一档（13–23 ms）。

## 8. 一致性测试（能放进 CI）

| 层 | 做法 | 门槛 |
|---|---|---|
| 参考 | Python 现有函数（`chain.chroma_u8`、`apply_base`、`apply_extra`、`Target.render`、`render_full`、`warp`）生成参考图 | — |
| 浏览器着色器 | 无头 Chrome，`--use-webgpu-adapter=swiftshader`（Linux/Windows/mac 都能跑，不要显卡）。读回后与参考比 | ≤1 码值的像素 ≥ 99.99%，平均 ΔE00 ≤ 0.01。SwiftShader 实测 0.0006、≥99.995% 像素 ≤1 码值 |
| 本机着色器 | `cargo test` 跑 wgpu：Windows 用 D3D12 WARP（windows-latest 没有 Vulkan 驱动，wgpu 会选 WARP），Linux 用 lavapipe，mac 用 Metal | 同上。第三方项目报告 WARP 约 1% 像素有取整差，所以软件适配器单独记录，超过 ≤1 码值才失败 |
| 着色器编译 | 同一 `.wgsl` 用 Tint（Chrome）和 naga（wgpu）都编一遍 | 两边都要通过 |
| 性能回归 | 只在本机（真显卡）跑：每帧显卡时间、拖动 rAF、导出分段。CI 只记数，不设门槛 | 见 §1 |

测试数据：
- 理光派生字节不进仓库。CI 用 `devtools/synthetic_card` 的合成 DAT 和合成 DNG（灰阶、色块、细线、渐变）。
- 6 张真实 DNG 的全套对比只在本机发版前跑（本轮的 `tools/compare.py`）。

GitHub Actions 矩阵：
- `macos-latest`：Metal，如果虚拟机没有可用适配器，退到 SwiftShader。
- `windows-latest`：WARP + Chrome SwiftShader。
- `ubuntu-latest`：安装 `mesa-vulkan-drivers` 得到 lavapipe，加 Chrome SwiftShader。
- 每个任务都要断言「拿到了适配器」，没拿到就失败，不跳过。

## 9. Windows：怎么实现，会差在哪

| 项 | 做法 | 可能更差的地方 | 怎么确认 |
|---|---|---|---|
| 浏览器预览 | Chrome/Edge 的 WebGPU 由 Dawn 走 D3D12（113 起，gpuweb 状态页） | 核显（如 Intel UHD 620）每帧估计 2–5 ms（估计：每帧约 300 万像素 × 数百次运算），仍在 60 Hz 预算内 | 朋友机器上跑 `proto/` 的 drag 阶段 |
| Tauri | WebView2 = Chromium，WebGPU 应可用（只有 GitHub issue 里的佐证，没有微软官方文档；Xbox 上没有适配器） | 版本随系统 Edge 更新；企业策略可能关掉显卡加速 | 打包后在实机上跑 `navigator.gpu.requestAdapter()` 和 drag |
| 本机核心 | wgpu 默认 D3D12，可选 Vulkan；CI 用 WARP | 不同厂商驱动的取整差 | CI 门槛 + 实机跑 `native_wgpu` |
| HDR | WebGPU 画布 `rgba16float + extended`；导出 Ultra HDR | 要求 Windows「使用 HDR」打开；SDR 内容亮度滑块会改变 SDR 白；没找到 Chrome 在 Windows 上 `extended` 的平台说明 | 实机：`(dynamic-range: high)`、`extended` 画布上亮于白的色块是否更亮、Ultra HDR JPEG 在 Chrome 里是否显示 HDR |
| 广色域 | 画布 `display-p3`；Chrome 按显示器 ICC 做色彩管理 | 没有 ICC 或没开 Win11 自动色彩管理时，广色域屏上的颜色会偏 | 实机对照同一张 P3 测试图 |
| 高刷新率 | rAF 跟显示器刷新 | 多显示器不同刷新率时，Chrome 可能取主屏 | 实机看 rAF 间隔 |
| 字体（日期戳、边框） | 核心自带字体并排版 | 系统字体不同会让预览叠层和导出不一致 | 一致性测试加文字样张 |
| 卡和路径 | 核心枚举盘符（`config.py` 现在 Windows 卷枚举是空的） | — | 实机插卡 |

只能请机主朋友在 Windows 实机上确认的：
- WebView2 和 Chrome 里 WebGPU 是否可用，适配器名字；
- 拖动帧时间；
- HDR 开关前后 `extended` 画布和 Ultra HDR 图的显示；
- P3 测试图；
- 高刷新率屏的 rAF；
- 读卡与盘符；
- 安装包能否在没有 Python 的机器上直接运行。

## 10. Linux

- 本机核心用 wgpu Vulkan，没有问题。
- 预览：
  - Chrome 只对部分显卡默认开 WebGPU，其他走 WebGL2 退路；
  - Tauri 的 WebKitGTK 没有确认 WebGPU，同样走退路，或建议用浏览器模式。

## 11. 后台保留什么

| 功能 | 放哪 | 说明 |
|---|---|---|
| 导入、读卡、图库索引、sidecar | Rust 核心 | 现在 Python 的行为（锁、原子写、rev）作为规格，用现有 pytest 用例对拍 |
| DNG 解析 | Rust 核心（导出、预生成）+ 浏览器 JS（只找条带偏移） | |
| 配方计算（旋钮 → 552 B 条目 → 烘焙表） | Rust 核心，或计算着色器 | 现在 142 ms/格 |
| LUT 解析、空间识别 | Rust 核心 | 65³ 解析 370 ms，一次性 |
| 导出、HDR 增益图与封装 | Rust 核心（wgpu + libjpeg-turbo） | |
| 写卡、DAT 编解码 | Rust 核心（逐字节对拍 Python 后再切换） | 没有性能需求；只为单安装包 |
| Python | 测试里的参考实现、研究工具 | 迁移期间继续服务旧界面 |

## 12. 分步替换（每一步旧版都能用）

1. **引擎包 + 一致性测试。**
   - 把原型整理成 `engine/`（TS + `.wgsl`）。
   - 把 §8 的测试接进 CI。
   - 不改界面。
2. **新预览挂进现有工作室（开关控制）。**
   - 新增两个只读接口：取 DNG 原字节、取烘焙表（Python 先提供，带缓存）。
   - 大图区域改用 WebGPU 画布，面板仍是旧的 ES 模块，但滑块改走 `engine.set()`。
   - 没有 WebGPU 时回到旧的 `<img>` 路径。
   - 这一步就解决了拖动和换照片。
3. **单张导出走显卡。** 先在浏览器里做（实测 170–370 ms），批量和 HDR 仍走 Python。导出对拍测试进 CI。
4. **Rust 核心并行上线。**
   - 按现有 OpenAPI（`scripts/export_openapi.py`）逐个接口替换：导出和 HDR → 配方烘焙 → 预生成 → 导入和图库 → DAT。
   - 每换一个，Python 版留作回退和对拍。
5. **界面换成 TS + SolidJS。** 一个面板一个面板换（大图、调整、配方、裁切、边框、时间戳、导出、图库网格）。顺带重做按钮和控件样式（机主截图里的问题），用词沿用 `research/studio_v2/COPY.md`。
6. **Tauri 打包 Mac 和 Windows。** 浏览器模式保留。
7. **Python 退出产品**，只留在测试里。

## 13. 资料来源（2026-11-02 读取）

- WebGPU 各浏览器、各系统的实现状态：[gpuweb Implementation Status](https://github.com/gpuweb/gpuweb/wiki/Implementation-Status)
- WebGPU HDR 画布 `toneMapping: extended`（Chrome 129）：[What's New in WebGPU (Chrome 129)](https://developer.chrome.com/blog/new-in-webgpu-129)；[MDN GPUCanvasContext.configure](https://developer.mozilla.org/en-US/docs/Web/API/GPUCanvasContext/configure)
- Safari 26 的 WebGPU 与 HDR 图像：[WebKit：News from WWDC25](https://webkit.org/blog/16993/news-from-wwdc25-web-technology-coming-this-fall-in-safari-26-beta/)
- WebView2 的 WebGPU（只有 GitHub 讨论，没有官方文档）：[WebView2Feedback #1285](https://github.com/MicrosoftEdge/WebView2Feedback/issues/1285)、[#4138](https://github.com/MicrosoftEdge/WebView2Feedback/discussions/4138)
- WebKit 的 60 fps 偏好：[WebKit bug 272165](https://bugs.webkit.org/show_bug.cgi?id=272165)、[tauri-plugin-macos-fps](https://docs.rs/crate/tauri-plugin-macos-fps/0.1.0)
- wgpu 各平台后端：[gfx-rs/wgpu README](https://github.com/gfx-rs/wgpu)
- windows-latest 上 wgpu 落到 D3D12 WARP，WARP 有取整差（第三方项目经验）：[Pulsar-Native #1117](https://github.com/Far-Beyond-Pulsar/Pulsar-Native/issues/1117)
- Tauri 在 macOS 26 的 WKWebView 有 WebGPU（第三方项目把最低系统提到 macOS 26）：[musetric PR #1118](https://github.com/musetric/musetric/pull/1118)
