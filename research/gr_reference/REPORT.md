# GR 色彩与配方参考研究

核验日期：2026-10-13。目标机型：GXR 机身＋A12 50mm，官方固件 1.51。只研究公开网页、文档和已有报告；没有下载或运行第三方固件、App、可执行文件，没有连接相机，没有修改目录外的文件或提交 Git。

## 结论

建议把 v1 定位为“有独立记录的 GXR 原厂色彩配方”，把 v2 定位为“可调曲线、颜色映射和局部质感的 GR 风格”。本次整理了 **59 条有原始参数来源的配方**。正片、负片预设占 27/59；GR III 系列 39 条中，37 条使用非零清晰度，38 条使用非零高光对比。单靠 GXR 的全局对比度和五色色相，无法表达这些独立控制。[配方及逐行来源](recipes.csv)、[全部统计](STATISTICS.md)。

最值得直接借鉴的是 [bastibe/Darktable-Film-Simulation-Panel](https://github.com/bastibe/Darktable-Film-Simulation-Panel)：它公开颜色卡、机内渲染参考和风格文件，说明如何把色调曲线与颜色映射分开拟合。这个方法可用于测量 GXR 自身，而不依赖另一机型的固件地址。FRAME-GR2 最接近产品目标，但公开的是功能说明，核心算法与记录格式仍未知。[FRAME-GR2](https://github.com/Lyle-xub/FRAME-GR2)。

按本文的乐观结构模型，v1 可表达 55.3% 的参数需求，完整配方候选为 2/59（3.4%）；只增加曲线与暗角，参数需求覆盖升至 71.1%，完整候选仍是 2/59。v2 若再完成底片颜色拟合、动态范围近似、黑白滤镜与清晰度，可达 53/59（89.8%）完整候选。**这些是功能规划上限，成片复刻率尚未测量**；不能把 89.8% 当作固件可行性或视觉相似度。[计算规则与逐条缺口](coverage.csv)、[计算结果](coverage.json)。

## 1. 架构边界与调查范围

### 1.1 需要修正的引擎名称

官方对比表将 GXR A12 50mm 和 GR DIGITAL III 的图像处理引擎都列为 **GR ENGINE III**，S10 列为 Smooth Imaging Engine IV。任务背景中的“GXR 使用 Smooth Imaging Engine III”不适用于此次 A12 50mm 目标。[官方对比 FAQ](https://www.ricoh-imaging.co.jp/english/r_dc/support/faq/bp/docs10/EDXR01000.html?sscl=f_n1fc01)。M32R 按本项目已有离线研究作为控制 CPU 前提；本轮没有重做指令集或芯片鉴定。引擎商品名、控制 CPU 和图像处理硬件是三个不同层次。

| 机型 | 有来源的架构信息 | 对 GXR 的意义 |
|---|---|---|
| GR DIGITAL I／II | 官方分别提供功能扩展固件；II 使用 GR Engine II。[II 宣传册](https://www.ricoh-imaging.co.jp/english/r_dc/support/brochure/pdf/gr_digital2.pdf)、[I 固件说明](https://www.ricoh-imaging.co.jp/english/r_dc/download/firmware/grd/procedure_win.html) | 交互与保存方式参考；本轮未找到可核验的自定义色彩固件源码 |
| GR DIGITAL III | GR ENGINE III，与 A12 50mm 同一引擎名称。[官方比较](https://www.ricoh-imaging.co.jp/english/r_dc/support/faq/bp/docs10/EDXR01000.html?sscl=f_n1fc01) | 是研究原厂五色色彩控制的近亲；传感器和模块结构不同，不能证明二进制兼容 |
| GR DIGITAL IV | GR ENGINE IV，原厂已有 Positive Film、Bleach Bypass 及暗角细分档位。[官方宣传册](https://www.ricoh-imaging.co.jp/english/r_dc/support/brochure/pdf/gr_digital4.pdf)、[功能扩展说明](https://www.ricoh-imaging.co.jp/english/r_dc/download/firmware/docs/grd4_vup_en.pdf) | 比 GR III 更接近旧式 Image Settings，值得作为下一轮静态对比对象；本轮没有获取其固件 |
| GR／GR II | GR II 为 GR ENGINE V；ricohdec 文档显示 GR 更新包有嵌套容器。[官方 GR II 宣传册](https://www.ricoh-imaging.co.jp/english/support/pdf/gr2.pdf)、[ricohdec](https://github.com/crypto512/ricohdec) | FRAME 的 UI、传输和成像阶段可参考；地址、指令、容器不能直接移植 |
| GR III／IIIx | GR ENGINE 6；公开研究记录 Linux／Yocto、相机守护进程，SC2000／Cortex-A7 是研究者的芯片识别结论，未由本轮拆机核验。[官方发布](https://news.ricoh-imaging.co.jp/rim_info2/2019/20190222_019929.html)、[系统研究](https://github.com/hhornbacher/gr3x-fw-hack/blob/main/docs/system.md) | Linux、动态库、Wi-Fi／BLE 接口不能套用到 GXR 的 M32R 固件 |
| GR IV | GR ENGINE 7；公开研究涉及 RTOS 与嵌入式 Linux、工厂脚本、型号资源。[官方产品页](https://www.ricoh-imaging.co.jp/english/products/gr-4/feature/)、[GR IV 研究](https://github.com/radium-wang/ricoh-gr4-firmware-analysis-and-feature-expansion) | 参考持久化、脚本和证据方法；无已确认的 GXR 对应接口 |
| Pentax K-30、K-S1／K-S2、K-3 III 等 | PHDK／pfwtool／K-3 III 论坛记录多代解码与调试方法；K-3 III 研究者报告 SC2000、RTOS＋Linux。[PHDK](https://github.com/i-am-shodan/PHDK)、[pfwtool](https://github.com/twang2218/pentax-firmware-tool)、[K-3 III 第 51 帖](https://www.pentaxforums.com/forums/32-digital-processing-software-printing/464577-pentax-k-3-markiii-reveal-hacking-4.html) | 可研究容器家族和工厂脚本。没有证据支持“所有 Pentax 都与 GR/GXR 共用同一引擎和颜色算法” |

调查覆盖 GitHub、Gist、Ricoh 官方、GR official、PentaxForums、Reddit 和作者博客。关键词包含各代机型＋`firmware hack`、`reverse engineering`、`recipe`、`LUT`、`Pentax PHDK`、`Milbeaut`。以下是本轮找到且有直接来源的 29 个项目／资料入口，不宣称穷尽全部互联网项目。GR DIGITAL I–III 未找到公开、可复核的自定义色彩固件实现；这只是检索结果，不是不存在的证明。检索与访问限制见 [来源记录](sources/NOTES.md)。

### 1.2 项目盘点

“公开源码”表示看到了公开代码文件或项目声明，不表示本轮运行过。作者实机声明与第三方评论均不等于本项目独立复现。

| # | 项目与直接来源 | 可自定义／研究什么 | 实现已知程度与源码 | 对 GXR 的借鉴程度 |
|---:|---|---|---|---|
| 1 | [FRAME-GR2](https://github.com/Lyle-xub/FRAME-GR2) | 16 槽、负片、LUT、扩展参数、颗粒、合成 HDF | 作者声明；机内实现未公开 | 高：产品与阶段设计；代码移植依据不足 |
| 2 | [crypto512/ricohdec](https://github.com/crypto512/ricohdec) 及 [jokob fork](https://github.com/jokob/ricohdec) | GR／Theta 固件容器解码 | C 源码；README 展示嵌套负载 | 中：格式研究，不提供配方实现 |
| 3 | [yeahnope/gr_unpack](https://github.com/yeahnope/gr_unpack) | GR III 包头、帧与压缩块 | Python 源码及格式说明公开 | 低：GR III 容器；对 GXR 地址无直接价值 |
| 4 | [hhornbacher/gr3x-fw-hack](https://github.com/hhornbacher/gr3x-fw-hack) | 系统、IPC、共享内存、运行环境探索 | 工具、mock 和分析公开；作者说明电脑环境不等于完整硬件启动 | 中：找参数到图像处理接口的方法 |
| 5 | [radium-wang/GR IV 研究](https://github.com/radium-wang/ricoh-gr4-firmware-analysis-and-feature-expansion) | 容器、RTOS／Linux、工厂脚本、关机画面 | 源码与研究记录公开；新材料有非商业许可证；非通用相机 SDK | 中：实验设计与证据边界，未提供色彩改造 |
| 6 | [h0hmj/GR IV XPAN 修改](https://gist.github.com/h0hmj/31d6f3d711a1840b53290f6a3c69801c) | 4:3 改全宽宽幅裁切 | 作者报告实机验证；公开重建步骤／工具 | 中：预览与成片需分别验证；不增加色彩参数 |
| 7 | [PHDK](https://github.com/i-am-shodan/PHDK) | K-30 内存、显示、调试入口 | 公开 C/C++、补丁与研究；功能进展以 README 为限 | 中：定位入口的方法；Cortex 结论不能套用 M32R |
| 8 | [PentaxFirmwareTool](https://github.com/i-am-shodan/PentaxFirmwareTool)／[MooseV2](https://github.com/MooseV2/pfwtool_html)／[twang2218](https://github.com/twang2218/pentax-firmware-tool) | Pentax 解密、解压、K-S1／S2 资源提取 | 工具源码公开；属于同一工具家族 | 中：打包与资源研究，无新增 recipe 证据 |
| 9 | [ergoadams/pentax-scripting](https://github.com/ergoadams/pentax-scripting) | 至少 K10D 的机内脚本与函数位置 | 文档／例子公开；跨型号适用性未知 | 中：搜索脚本解释器；GXR 是否有入口未知 |
| 10 | [K-3 III reveal/hacking 论坛](https://www.pentaxforums.com/forums/32-digital-processing-software-printing/464577-pentax-k-3-markiii-reveal-hacking-4.html) | 工厂菜单、TTL 启动脚本、系统布局 | 作者文字／日志；第 51 帖脚本找到但显示未成功 | 中：相似平台研究；没有色彩 recipe 成功证据 |
| 11 | [dm-zharov/ricoh-gr-bluetooth-api](https://github.com/dm-zharov/ricoh-gr-bluetooth-api) | 参数、状态、GPS、无线连接 | GATT 与枚举文档公开；型号需逐字段核验 | 低：GXR 无对应无线硬件；有助理解配方传输与成像解耦 |
| 12 | [clyang/GRsync](https://github.com/clyang/GRsync) | GR II／III Wi-Fi 原图同步 | 公开桌面代码；HTTP 传输 | 低：不是新增机内配方 |
| 13 | [GReat-Image-Downloader](https://github.com/adriantache/GReat-Image-Downloader) | GR III／IIIx 照片下载 | 公开 App 代码 | 低：文件传输，不解锁图像处理 |
| 14 | [Nielk74/ricoh-gr3-android](https://github.com/Nielk74/ricoh-gr3-android) | 遥控、传图、JPEG／DNG 手机端 film lab | Kotlin 公开；作者明确 BLE 唤醒 AP 有受限路径 | 中：将手机后期与机内 JPEG 分清；不证明新机内预设 |
| 15 | [Grid／作者技术说明](https://lucas.io/grid/making-of-grid/) | GR IV 配方读写、GR III 等传图 | BLE＋Wi-Fi；协议说明公开，完整 App 源码未确认 | 中：配方字段、连接流程；无 GXR 无线移植路线 |
| 16 | [GRade／作者发布帖](https://www.reddit.com/r/ricohGR/comments/1vit037/grade_is_now_live_build_recipes_and_send_them_to/) | 配方库、JSON／QR、GR IV 自定义槽写入 | 作者称 BLE 写入；源码未确认；WB 偏移写入限制由作者报告 | 中：配方格式与能力判断；不是固件算法 |
| 17 | [GR Recipe Studio](https://grrecipestudio.com/compatibility) | 配方编辑、社区、支持机型比较／写入 | 商业 App 说明；实现源码未确认 | 中：型号／固件能力表与部分支持的表达 |
| 18 | [Ritchie’s Ricoh Recipes](https://ricohrecipes.com/ricoh-recipes-app/) | 原厂参数配方库、收藏、离线查询 | 作者明确 App 不连接相机；配方参数公开，App 源码未确认 | 高：本次主样本库；不可把抄参数当算法移植 |
| 19 | [Luke Taylor/Candy Color 400](https://www.lukeptaylor.com/blog/candy-color-400-ricoh-gr-iii-film-recipe) | 原厂 Positive Film 的完整参数组合 | 作者参数与样片；不是改固件 | 高：第二作者样本，可检查主样本偏差 |
| 20 | [Frame Recipe Lab](https://www.framerecipelab.com/ricoh-gr-recipes/) | GR III／IIIx 配方与参考图 | 网页目录；源码／成像算法未确认 | 中：外部调校参考，未计入 CSV |
| 21 | [RicohCookBook](https://ricohcookbook.com/) | 归属原作者的配方、收藏排序、builder | 作者称按收藏排序；方法与独立统计未核验 | 中：发现来源与流行线索；不把聚合页重复计样本 |
| 22 | [Sean-hsj/ricoh-gr-recipes](https://github.com/Sean-hsj/ricoh-gr-recipes/blob/main/README.en.md) | 意图到配方的 Skill、型号／菜单标签校验 | Skill／验证脚本公开；生成建议不是实机效果证据 | 中：配方 schema 与禁止跨代无效参数 |
| 23 | [richadams/ricoh-gr3-metadata](https://github.com/richadams/ricoh-gr3-metadata) | MakerNote 参数、recipe 比对、uncrop | ExifTool 配置、实验数据与方法公开 | 高：一项参数一组 JPEG 的差分定位方法；偏移不能直接给 GXR |
| 24 | [ovibobi/ricoh-recipe-decoder](https://github.com/ovibobi/ricoh-recipe-decoder) | 从 GR III／IIIx JPEG 读配方 | 网页实现公开，基于浏览器 ExifTool；README 的源码发布说明可能滞后 | 高：导出／核验工具交互；解码不是恢复完整 ISP 算法 |
| 25 | [pbeens/Tag-Ricoh-GR-Recipes](https://github.com/pbeens/Tag-Ricoh-GR-Recipes) | Image Tone 写关键词 | 公开桌面源码，调用 ExifTool | 中：记录实际拍摄预设；Image Tone 不自动等于自定义 recipe 名 |
| 26 | [bastibe/Darktable-Film-Simulation-Panel](https://github.com/bastibe/Darktable-Film-Simulation-Panel) | Standard、Positive／Negative、Vivid、Retro 等外部仿真 | 公开 styles、颜色卡参考、Lua；用 darktable-chart 拟合曲线＋颜色查表 | 最高：可复用测量方法，适用于 GXR 自身标定 |
| 27 | [GR II POSI 逆向作者帖](https://www.reddit.com/r/Lumix/comments/1s5sxbv/i_reverseengineered_ricoh_gr_iis_positive_film/) | 正片曲线、亮度相关饱和度、系数与 LUT | 作者称 IDA＋DCU；没有公开可复核的地址／完整重建源码 | 中：多项式与亮度相关颜色的搜索假说，未独立验证 |
| 28 | [GR official/Image Control](https://www.grblog.jp/en/article/2192/)／[官方功能扩展](https://www.ricoh-imaging.co.jp/english/products/gr-3/firmup/) | 参数的可见效果与固件新增负片／颗粒 | 官方文字／对比图；算法源码不公开 | 高：参数定义和允许组合的依据 |
| 29 | [bonyback1/sony-pmca-ricoh-mod](https://github.com/bonyback1/sony-pmca-ricoh-mod) | Sony 上的 GR 风格、WB、gamma、3×3 矩阵 | 公开补丁源码；作者声称硬件 ISP hook，未经本轮验证 | 中：跨平台阶段分解；Sony 非共享引擎，不能移植寄存器 |

另有 [pkTriggerCord](https://github.com/asalamon74/pktriggercord) 的 Pentax USB／SCSI 文档可辅助区分“设置传输”和“成像算法”。本轮仅作为传输外围资料，不计入上表 29 项。也没有把 Theta 的解包成功算作 GXR 改造成功。

### 1.3 FRAME-GR2 深挖

下表是作者公开的参数名与明确写出的范围。未公布范围的项目保留未知，不借用 GR III 的 ±4 补齐。[README](https://github.com/Lyle-xub/FRAME-GR2#02-让光影多一点触感)、[Release](https://github.com/Lyle-xub/FRAME-GR2/releases/tag/v0.62.1-wn3)。

| 参数 | 公开范围／状态 |
|---|---|
| 风格浓度 | 0–10；5 原始强度，10 两倍，0 关闭自定义变换 |
| 高低调、高光对比度、阴影对比度 | 名称已公开；最小值、最大值、步进未知 |
| 色相、饱和度、对比度、锐度、周边光量 | 名称已公开；数值范围未知 |
| 颗粒强度／大小 | 强度 0–4，大小 1–3 |
| HDF | 关、弱、中、强；软件合成，不是 GR III HDF 的物理滤镜 |
| 机内滤镜位置 | 16 个；作者称可管理并持久保存 |

格式为 `.cube`、兼容 XMP 和项目 JSON；没有公开 LUT 网格尺寸、1D／3D 支持边界、输入色域／gamma、XMP 字段子集或 JSON schema。Release 提到有些导入需近似转换，说明不能假设任意 LUT 都逐点原样在机内执行。[Release 修复说明](https://github.com/Lyle-xub/FRAME-GR2/releases/tag/v0.62.1-wn3)。

作者公开的实现线索包括负片保留曲线与矩阵、原生渐晕路径、HDF 与颗粒合并处理。它们指向多阶段处理，但没有给出函数位置或算法。[README 更新记录](https://github.com/Lyle-xub/FRAME-GR2#详细公告与更新记录)。

App 经相机 Wi-Fi 上传；机内保留滤镜，手机脱离后继续用。素材传输有 CRC、序号、偏移和读回，WN3 素材正文上限 16 KiB；该上限指图片／动画／音效，不能推成 LUT 容量。[README 无线素材记录](https://github.com/Lyle-xub/FRAME-GR2#详细公告与更新记录)。公开的 SD 离线 LUT 导入是用户请求，未找到实现说明。[Issue #2](https://github.com/Lyle-xub/FRAME-GR2/issues/2)。

独立证据边界：本轮只确认公开说明与仓库文件形态。机内原图、取景、持续保存、性能与 RAW 无损均未独立复现。GR 一代适配也只是请求。[Issue #1](https://github.com/Lyle-xub/FRAME-GR2/issues/1)。GXR 的 SD 配方编辑更值得先研究已有 Card 记录，因为 GXR 没有这些无线硬件。

## 2. 配方数据与统计

### 2.1 样本定义与来源

`recipes.csv` 含 59 行：Ritchie 公开的 20 条 GR／GR II、38 条 GR III／IIIx，加 Luke 的 Candy Color 400。Ritchie 与 `ricohrecipes.com` 是同一作者／来源，未重复计算；Reggie’s Color Negative 被其收录，算一条。付费隐藏配方没有取值，不计入。[GR II 目录](https://ricohrecipes.com/ricoh-gr-gr-ii-recipes/)、[GR III 目录](https://ricohrecipes.com/ricoh-gr-iii-recipes/)、[Luke 原文](https://www.lukeptaylor.com/blog/candy-color-400-ricoh-gr-iii-film-recipe)。

“流行”按广泛使用的公共配方库和被社区引用的配方定义，未声称这是下载量最高的 59 条。[社区引用 Ritchie／Luke](https://www.reddit.com/r/ricohGR/comments/15lwpf9/gr_3_recipes/)、[Reggie／Royal Supra 讨论](https://www.reddit.com/r/ricohGR/comments/1mm7nyc/whats_the_one_recipe_apart_from_reggies_negative/)。58/59 来自主来源，样本明显偏向该作者；没有按点赞／拍摄量加权，不能外推全体 GR 用户偏好。

每行有名称、来源、适用机型、底片预设、全部公开参数、WB 及两轴偏移、ISO 和曝光建议。`wb_ab_signed` 正为 A，负为 B；`wb_gm_signed` 正为 G，负为 M。原作者没有写出的字段为空，未假定为零；Off、N/A 保持原文。参数段和页面 SHA-256 保存在 `sources/*.json`；仅保存参数事实，没有保存整篇博客或照片。

保留的原文异常包括曝光范围 `+2/3 to 0`、`-0 to +2/3`，以及 GR II Hi-Contrast B&W 的 Contrast -2；不擅自纠正。GR II 的 1–9 与 GR III 的 -4–+4 不混作统一尺度。汇总的 ALL 范围只是观察并集，机型分表才用于映射。`Std` 归 Standard、`BW Monotone`／`Black & White` 归 Monotone，仅用于统计，不覆盖 CSV 原值。全部分类值和频次见 [statistics.json](statistics.json)。

### 2.2 关键分布

| 底片预设 | 全部 59 条 | GR II 20 条 | GR III 系列 39 条 |
|---|---:|---:|---:|
| Positive Film | 20（33.9%） | 6 | 14 |
| Negative Film | 7（11.9%） | 0 | 7 |
| Standard | 5（8.5%） | 1 | 4 |
| Retro | 5（8.5%） | 2 | 3 |
| Cross Process | 5（8.5%） | 3 | 2 |
| Monotone | 4（6.8%） | 2 | 2 |
| Bleach Bypass | 3（5.1%） | 2 | 1 |
| Hi-Contrast B&W | 3（5.1%） | 1 | 2 |
| Vivid | 2（3.4%） | 0 | 2 |
| Hard Monotone | 2（3.4%） | 0 | 2 |
| B&W (TE) | 2（3.4%） | 2 | 0 |
| High Key | 1（1.7%） | 1 | 0 |

数值及来源可逐行追到 [recipes.csv](recipes.csv)。所有 GR III 预设的官方列表包含 Soft Monotone 和 HDR Tone，但本样本使用次数均为 0；Custom 1/2 是保存包装，不能当独立底片风格计数。[官方预设列表](https://www.ricoh-imaging.co.jp/english/products/gr-3/feature/03.html)。

| 参数 | GR III 系列写明／非零使用 | 常用值与观察范围 |
|---|---|---|
| 饱和度 | 33/39，33 非零 | +4 为 12 条，+2 为 9 条；范围 -4～+4 |
| 色相 | 33/39，30 非零 | -2 为 6 条；范围 -4～+4 |
| 高低调 | 39/39，36 非零 | +1 为 15 条，+2 为 8 条；范围 -4～+4 |
| 对比度 | 39/39，38 非零 | +4 为 11 条；范围 -4～+4 |
| 高光对比 | 39/39，38 非零 | -4 为 18 条，-3 为 7 条；范围 -4～+4 |
| 阴影对比 | 39/39，37 非零 | +4 为 15 条，-4 为 10 条；范围 -4～+4 |
| 锐度 | 39/39，29 非零 | -1／+1 各 11 条，0 为 10 条；范围 -4～+4 |
| Shading | 39/39，9 非零 | 0 为 30 条，-1 为 6 条；范围 -1～+2 |
| 清晰度 | 39/39，37 非零 | +2 为 11 条、-2 为 9 条；范围 -4～+4 |
| 染色／黑白滤镜／颗粒 | 染色 3、滤镜 3、颗粒 6 非零 | 颗粒 1、2、3；不能把分类编号当连续色相 |
| 高光／阴影修正 | 高光 39，阴影 38 启用 | 高光 On 37、Auto 2；阴影 Low 14、Medium 13、High 8、Auto 3 |
| 周边光量修正 | 39/39 On | 与风格 Shading 是两个参数 |

GR II 20 条中，17 条用动态范围补偿，6 条用弱／中暗角。全部 59 条都写了 WB＋偏移；GR III 两轴观察范围 ±14，GR II ±8。14 条使用指定 Kelvin，范围 2500–10000K。全部关闭降噪；这支持把可保存的 NR Off 放进配方 schema，但不代表所有场景都应关闭降噪。[机型分表及频次](STATISTICS.md)。

## 3. 从成像阶段拆解 JPEG 风格

这里是用于研究的功能模型，不声称恢复了 GXR／GR III 固件的实际调用顺序。传感器校正、去马赛克、降噪、颜色转换和风格渲染可能交织；白平衡和曝光在 RAW 阶段与 JPEG 后期的效果也不同。曲线与颜色映射可以分别测量，已有工具将它们分开输出。[darktable-chart 官方说明](https://docs.darktable.org/usermanual/3.8/en/special-topics/darktable-chart/overview/)、[bastibe 方法](https://github.com/bastibe/Darktable-Film-Simulation-Panel)。

| 阶段 | GR III 参数／开关 | 功能解释及证据 |
|---|---|---|
| 拍摄与输入 | ISO、曝光补偿、Highlight Correction | 决定进入管线的信号；高光保护涉及采集／处理，已剪白的输入不能仅靠曲线恢复。[手册 p.64、89](https://www.ricoh-imaging.co.jp/english/support/man-pdf/gr-3.pdf) |
| 白平衡 | WB 模式／手动／Kelvin、A–B／G–M、AWB in Tungsten Light、WB Fine-tuning | 改变通道比例、自动白点与色偏；GR III 两轴 ±14。[手册 p.69–73、148](https://www.ricoh-imaging.co.jp/english/support/man-pdf/gr-3.pdf) |
| 颜色映射 | 底片预设的基础颜色、Saturation、Hue、Color Tone | 全局饱和度／色相，及效果专用色调；矩阵、分色或查表是可测试的实现候选，官方没有披露具体算法。[官方参数列表](https://www.ricoh-imaging.co.jp/english/products/gr-3/feature/03.html) |
| 色调映射 | Contrast、Contrast (Highlight)、Contrast (Shadow)、High/Low Key、Shadow Correction | 曲线整体斜率、亮／暗段响应、中间调位置与提亮暗部；后三者与曝光补偿不能直接互换。[GR official 对比](https://www.grblog.jp/en/article/2192/) |
| 局部细节 | Sharpness、Clarity、HDR Tone Level、高 ISO／慢快门 NR | 锐化偏边缘；清晰度与 HDR Tone 涉及局部对比的表现。邻域算子不能被一张只看单像素 RGB 的 LUT 完整替代。具体半径和核未知。[手册预设说明](https://www.ricoh-imaging.co.jp/english/support/man-pdf/gr-3.pdf)、[官方 Clarity 对比](https://www.grblog.jp/en/article/2192/) |
| 空间光量 | Shading、Peripheral Illumination Correction | 前者是创作效果；后者校正镜头周边光量。都依赖像素位置，不能当成普通全局曲线。[手册 p.89](https://www.ricoh-imaging.co.jp/english/support/man-pdf/gr-3.pdf) |
| 黑白与染色 | Filter Effect、Toning | 滤镜改变不同颜色转成灰度的权重；染色给黑白结果添加颜色，两者不等价。GR III 有依预设而异的参数。[官方参数列表](https://www.ricoh-imaging.co.jp/english/products/gr-3/feature/03.html) |
| 纹理 | Grain Effect | 增加可见颗粒；官方后续固件扩展到黑白设置。强度值 1/2/3 是配方作者的写法，原厂菜单含 Off 和三级，不能推出 GXR 有同一噪声算法。[官方固件扩展](https://www.ricoh-imaging.co.jp/english/products/gr-3/firmup/) |
| JPEG 输出 | sRGB／AdobeRGB、像素、质量、压缩 | 输出空间与有损压缩会影响比较，应固定条件。[手册 p.84](https://www.ricoh-imaging.co.jp/english/support/man-pdf/gr-3.pdf) |

主色彩九项范围通常是 -4～+4，包含零共九个值。GR official 文中写 “8 steps” 是两端相隔八步，不应解释成八个可选值。不同预设可调项目不同，不能把九项统一强行应用给所有黑白／效果预设。[GR official](https://www.grblog.jp/en/article/2192/)。

### 3.1 各底片预设需要哪些阶段

“官方”栏是菜单或产品描述；“拟合假说”是给 GXR 实现的研究方向，未经固件或成片测量证实。下表的原厂风格描述依据 [手册 p.87](https://www.ricoh-imaging.co.jp/english/support/man-pdf/gr-3.pdf)；新增预设依据 [官方功能扩展](https://www.ricoh-imaging.co.jp/english/products/gr-3/firmup/)；完整列表依据 [产品页](https://www.ricoh-imaging.co.jp/english/products/gr-3/feature/03.html)。

| 预设 | 官方可见效果 | GXR 拟合假说／涉及阶段 |
|---|---|---|
| Standard | 标准画质 | 基础颜色映射＋基础曲线＋细节，不能假设各代 Standard 完全相同 |
| Vivid | 鲜明、清晰的颜色 | 增强饱和度、曲线与锐度；需测量分色差异 |
| Positive Film | 高饱和正片感 | 曲线＋非均匀颜色响应；不能简化为“饱和度＋4” |
| Negative Film | 负片打印的褪色感和明确颜色 | 黑点／中间调／高光过渡＋颜色映射；暖亮部／冷阴影是待测假说，不是官方算法承诺 |
| Monotone | 黑白 | 颜色到灰度权重＋曲线；Filter Effect 在灰度生成前发挥功能 |
| Soft Monotone | 柔和黑白 | 低反差曲线，是否另有空间柔化未知 |
| Hard Monotone | 硬朗黑白 | 灰度＋更强曲线／局部响应，具体算法未知 |
| Hi-Contrast B&W | 高反差，类似高感／迫冲颗粒感 | 激进曲线＋灰度＋纹理；颗粒感可能来自预设，不能只看 Grain Effect 是否为零 |
| Bleach Bypass | 低饱和、高对比 | 饱和度抑制＋曲线＋可选色调，分色方式需测量 |
| Retro | 旧照片感 | 曲线／黑位＋颜色映射＋染色；官方未公开配方系数 |
| HDR Tone | 绘画感、精细对比增强 | 局部对比／色调压缩，不能以一张全局曲线保证复刻 |
| Cross Processing | 交叉冲印效果，新增可选色调 | 通道曲线／分色和明暗映射；算法与 GR II／GXR 场景版相同与否未知 |
| Custom 1／2 | 保存其他 Image Control 的调整组合 | 数据与 UI 包装，没有额外成像阶段 |

GR II POSI 作者给出了三次多项式与亮度相关饱和度的说法，可作为寻找“运行时生成曲线”的线索。但未公开足以重建的全部证据，不能把它认作 GXR 或 GR III 的已知算法。[作者帖](https://www.reddit.com/r/Lumix/comments/1s5sxbv/i_reverseengineered_ricoh_gr_iis_positive_film/)。其“亮度相关变换不能用 RGB LUT 表达”的绝对说法也不能直接采纳：固定、无邻域、无历史状态的逐像素变换可采样为 3D LUT；空间锐化、暗角和随机颗粒则需要其他输入。这是数学上的表达能力判断，不是对其实现的复现。

## 4. 映射到 GXR 与目标参数集

### 4.1 原厂已有、近似与缺失

GXR 已有能力的直接依据是 [机身手册 p.59–60、71–72、86–90、129–134](https://www.ricoh-imaging.co.jp/english/r_dc/support/manual/pdf/gxr/GXR_E.pdf)、[Image Settings FAQ](https://www.ricoh-imaging.co.jp/english/r_dc/support/faq/bp/gxr/05/gxr05012.html)、[1.50 补充说明](https://www.ricoh-imaging.co.jp/english/r_dc/download/firmware/docs/gxr_vup_en.pdf)。以下“近似”不代表原厂含同名菜单。

| GR 需求 | GXR 原厂／近似办法 | 缺口与需解锁阶段 |
|---|---|---|
| WB 模式＋A/B、G/M | 原厂模式、Manual、Detail 和两轴补偿已有 | GR 的 Shade／多种荧光灯／指定 Kelvin 不全是一对一菜单；Detail 刻度和 WB 增益关系、两轴范围需核验 |
| Saturation | 全局 Vividness 已有 | 同一数字跨引擎不代表同一增益，需要颜色卡标定 |
| Global Hue | 红、橙、绿、蓝、洋红各自 Hue 已有，可同向调 | 五个区段边界、遗漏色域、亮度依赖未知；同调只能是近似，不能当全局旋转 |
| 分色饱和度／色相 | 五色各自 Vividness／Hue，10 项 | 原厂没有每色明度、黄／青独立项、明暗分色；需颜色映射入口／通道曲线／亮度相关分色 |
| Contrast／Sharpness | 原厂已有 | GR 档位不能直接复制，需各档实际响应 |
| 高低调、高光／阴影对比 | 全局 Contrast 只能耦合改变 | 需要控制曲线黑白端点、亮暗段、中间调；现有扫描没有确认曲线表，可能动态生成 |
| Positive／Negative／Retro／Bleach Bypass | 用 Vivid／Natural／Setting 1/2 调饱和度、五色、WB 可做方向近似 | 必须测量基础曲线＋颜色响应；仅新增预设名不产生该风格 |
| Monotone／Toning | B&W、B&W (TE) 有；TE 有 sepia/red/green/blue/purple | GR 色调范围与染色强度需映射；彩色 Retro 的染色不能直接用黑白 TE |
| 黑白颜色滤镜 | WB 改通道比例可能改变灰度，只能试验近似 | 原厂 TE 是结果染色；需找到灰度转换前的通道混合权重 |
| Shading／Vignetting | Cross Process／Toy Camera 场景已有暗角 | 需要脱离场景自动曝光，接入 P/A/S/M 的配方；亮暗双向支持及参数范围未知 |
| Peripheral Illumination Correction | 本轮原厂资料未确认同等独立开关 | 需 A12 50mm 的空间增益图；创作暗角与校正必须分开 |
| Highlight／Shadow Correction、GR II DR Compensation | 本轮 A12 50mm 文档没有确认等效独立控制 | 可用曲线近似暗部映射；真正保高光需采集或线性 RAW 阶段，不能恢复已丢信号 |
| Clarity | Sharpness 改边缘，Soft Focus 仅场景效果 | 局部对比／大尺度细节入口；不能用 Sharpness 档位冒充 |
| Grain | 无已确认独立颗粒设置 | 输出前纹理／噪声合成；需控制亮度、强度、尺度与种子 |
| HDF | Soft Focus 可作视觉方向参考 | 软件辉光需空间滤波与亮部掩模；官方 GR III HDF 是物理滤镜，无法用固件增加物理器件。[官方 HDF](https://www.ricoh-imaging.co.jp/english/products/gr-3/special/hdf/index.html) |
| 配方保存与调用 | Setting 1/2、My Settings、Box／Card 有 | 16 个独立颜色记录仍是新功能；My Settings 是否复制同一 Setting 的内部数组尚未确认。[已有保存报告](../recipes/REPORT.md) |

曲线缺口引用 [已有首轮扫描](../tone_curve/REPORT.md)，本轮未重复二进制扫描。它只证明该搜索没有确认曲线表，不证明 GXR 不支持曲线。

### 4.2 按样本覆盖收益排序

表中次数是“每条配方是否提出这项非零／非 Off 需求”，不是人的使用率，也不能相加当配方数。常数基础预设、WB 与 NR 是例外，计入一个必要配置请求。共享曲线／颜色阶段一次可服务数个参数。[逐条需求](coverage.csv)、[统计脚本](analyze_recipes.py)。

| 优先级 | 缺失能力与受影响样本 | 判断 |
|---:|---|---|
| 1 | 底片颜色／曲线拟合 46/59；其中 Positive＋Negative 27/59 | 优先提供可调底片基础，别只增加槽数量 |
| 2 | 曲线控制：高光 38/59、阴影 37/59、高低调 36/59 | 同一曲线入口可能提供三项功能；跨代档位需校准 |
| 3 | 清晰度 37/59 | 决定完整配方上限；即使曲线和颜色都补齐，省略它会丢 37 条 |
| 4 | 高光保护 39/59、阴影修正 38/59、GR II DR 17/59 | 先区分采集高光保护与曲线提暗部，不能混成 Contrast |
| 5 | 周边光量修正 39/59；创作暗角合并需求 15/59 | 校正可能成为模块基线；创作暗角从现有场景路径研究 |
| 6 | Grain 6/59；黑白滤镜 3/59；彩色染色 3/59 | 颗粒影响剩余完整覆盖；滤镜／染色虽少，可能与颜色入口共同实现 |

按完整配方收益，曲线与颜色必须成组考虑。多个缺口同时存在时，只补一项，完整覆盖率可能不变；不能因此说这项没有价值。细节样本是 Ritchie B&W Collection 的六个 Grain 配方，[原文](https://ricohrecipes.com/the-bw-collection/)、[Analog Collection](https://ricohrecipes.com/the-analog-collection/)。

### 4.3 v1 目标参数集

以下是拟议 schema 的语义字段，没有声称已经定位固件字节：

```text
recipe_name, recipe_id, schema_version, module_id
base_image_setting
vividness, contrast, sharpness
color[orange, green, blue, red, magenta].{hue, vividness}  # 共 13 项色彩数值
wb_mode, wb_detail_or_manual_reference, wb_ab, wb_gm
monochrome_toning_type, monochrome_toning_vividness      # 仅适用 B&W (TE)
noise_reduction                                      # 使用原厂选项
optional_capture = {exposure_compensation, iso_policy} # 用户主动纳入才随配方切换
```

数值存原厂枚举／原始刻度；对外可显示居中的九档，但未核对编码前不假定存储为 -4～+4。保留 9 级与旧 FAQ 5 级冲突。白平衡字段虽有官方菜单，实际存储、精度与独立配方调用仍待实现。彩色模式的五色数组与 B&W 参数是条件分支，不假定能够同时堆叠。[GXR FAQ](https://www.ricoh-imaging.co.jp/english/r_dc/support/faq/bp/gxr/05/gxr05012.html)、[机身手册](https://www.ricoh-imaging.co.jp/english/r_dc/support/manual/pdf/gxr/GXR_E.pdf)。

现有路线图的 16 记录、ADJ 列表、重启保存属于交互和数据功能。v1 主要色彩验证应先测原厂各档 JPEG 响应，再给配方 GXR 自己的名字；“类似 Positive Film”只能注明近似。[现行路线图](../../docs/ROADMAP.md)。

### 4.4 v2 目标参数集

建议在 v1 上增加以下语义控制，数值范围为设计建议，需用实测确定 GXR 的有效刻度：

- `base_profile`、基线颜色矩阵／分色映射、真正的全局 Hue。先拟合 Positive、Negative，再按样本频次做 Retro／Bleach／Cross。五色不足时再考虑新增分色与亮度依赖，不能预先承诺任意 3D LUT。
- `tone_curve`、`high_low_key`、`contrast_highlight`、`contrast_shadow`。UI 可沿用 GR 的 -4～+4；底层可以是控制点、系数或硬件寄存器，形式尚未知。曲线要可单独校准，不与白平衡混写。
- `shading` 与 `peripheral_correction` 分开；前者是风格，后者是 A12 50mm 基线校正。
- `highlight_protection`、`shadow_lift`、`dr_policy`。保高光若只能靠曝光策略，应明确告诉用户会影响曝光；不能偷偷以曲线替代。
- `clarity`、`mono_filter`、彩色／黑白 `toning`。清晰度是完整配方覆盖的必要项，接口与开销未知。颗粒可作 v2 后续扩展，6/59 样本依赖它。

这是研究建议。支持它的依据是样本缺口和可分离测量方法，不是硬件能力已经验证。[样本缺口](coverage.csv)、[darktable-chart 方法](https://docs.darktable.org/usermanual/3.8/en/special-topics/darktable-chart/overview/)。

### 4.5 覆盖率的定义与敏感性

为避免主观声称“像胶片”，计算分两种指标：

1. 参数需求覆盖率：每条记录中每个非零／非 Off 风格参数算一个请求；基础预设、WB 模式、WB 两轴和 NR 控制各算一个必要配置请求。ISO 与曝光建议独立列出，不计成新增成像能力。共 797 请求，各请求等权，不能等同视觉重要性。
2. 完整配方候选率：这条配方所有已写明需求都有控制类别可表达才计一条。空字段不创造需求，因此这是上限；基础预设同名只按类别视作 native，没证明颜色相同。WB 模式与两轴按可标定近似处理，不代表 GR 的数值可直接填到 GXR。

| 假设能力 | 参数需求覆盖 | 完整配方候选 | 关键前提 |
|---|---:|---:|---|
| v1 原厂控制 | 441/797 = 55.3% | 2/59 = 3.4% | WB／档位近似标定成功；两条是 Monochrome Negative、Cyanotype |
| v1＋曲线＋创作暗角 | 567/797 = 71.1% | 2/59 = 3.4% | 只解锁四个控制类别，不凭空补底片／动态范围／清晰度 |
| 再补底片颜色、染色、黑白滤镜、动态范围／镜头校正近似 | 754/797 = 94.6% | 22/59 = 37.3% | 底片拟合、采集保护／曲线近似都成功；仍无清晰度与颗粒 |
| 建议 v2，再加清晰度 | 791/797 = 99.2% | 53/59 = 89.8% | 以上前提全成立，允许跨引擎近似；剩六条需要颗粒 |
| 再加颗粒 | 797/797 = 100% | 59/59 = 100% | 仅表明覆盖所采字段；仍不是像素等价或真实照片通过率 |

源码、各条缺口和分母见 [analyze_recipes.py](analyze_recipes.py)、[coverage.json](coverage.json)、[coverage.csv](coverage.csv)。这些假设越多，数字越乐观。若要求“完全等效原厂成像算法”，本轮没有一条 GXR 实测，实证覆盖率未知，不能写成 3.4% 或 89.8%。若 v2 只能解锁曲线／暗角，必须采用第二行，不能采用第四行。

## 5. 主要未知与下一轮可验证问题

1. GXR 五色调节、Contrast、Sharpness、WB 的真实函数与硬件写入位置，机身／模块的责任分界仍未知。先将每个控制的 JPEG 响应分开测量，再追数据流。[既有曲线扫描](../tone_curve/REPORT.md)。
2. GR 预设的完整曲线、矩阵、亮度相关饱和度、局部处理未由公开作者说明证明。借鉴 bastibe 的颜色卡＋RAW/JPEG 配对方法，增加灰阶、肤色、多光源和不同曝光，避免一张颜色卡过拟合。[公开标定项目](https://github.com/bastibe/Darktable-Film-Simulation-Panel)。
3. FRAME 的 `.cube` 接受范围、近似损失、机内文件格式、RAW 路径、读回语义、耗时和容量仍未知；SD 离线 LUT 尚没有公开完成证据。[FRAME Release](https://github.com/Lyle-xub/FRAME-GR2/releases/tag/v0.62.1-wn3)、[Issue #2](https://github.com/Lyle-xub/FRAME-GR2/issues/2)。
4. GXR 现有暗角能否在 P/A/S/M 启用、是否进入预览与成片的同一位置，以及是否影响 DNG，需要实际调用关系和后续用户授权的照片证据。此轮没有操作相机。[GXR 补充说明](https://www.ricoh-imaging.co.jp/english/r_dc/download/firmware/docs/gxr_vup_en.pdf)、[路线图](../../docs/ROADMAP.md)。
5. 高光保护与曲线修正、机内滤镜与 App 后期必须分开验收。GXR 的 DNG 仍应保持原厂 RAW 语义；FRAME 的原图下载声明不足以证明其成像路径没有改 RAW。[FRAME Release](https://github.com/Lyle-xub/FRAME-GR2/releases/tag/v0.62.1-wn3)。

## 6. 本轮交付与复核

- `recipes.csv`：59 条配方；全部参数与来源。
- `sources/*.json`：13 个配方页面的参数事实、获取时间和页面哈希；另有项目／官方文档元数据。
- `STATISTICS.md`／`statistics.json`：全部参数、预设频次与机型分表。
- `coverage.csv`／`coverage.json`：每条配方的缺失控制和各方案上限。
- `collect_recipes.py`：公开文本采集，`--offline` 用保存事实重建 CSV。
- `analyze_recipes.py`：验证最小样本数、唯一性、来源、GR III 数值范围，重算统计与覆盖。

```sh
python3 -B research/gr_reference/collect_recipes.py --offline
python3 -B research/gr_reference/analyze_recipes.py
```

在线刷新另运行 `collect_recipes.py`，只抓公开配方网页。此次已完成来源参数到 CSV 的离线重建、统计重算、名称／模型去重与 59 行校验。没有完成颜色卡拟合、JPEG/DNG 对比或机内行为验证。
