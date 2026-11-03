# 来源核验记录

日期：2026-10-13。本目录只保存配方参数事实与文档元数据。既有报告只读：`docs/ROADMAP.md`、`research/frame_gr2/REPORT.md`、`research/recipes/REPORT.md`、`research/tone_curve/REPORT.md`。

## 配方来源

主样本为 [GR II 目录](https://ricohrecipes.com/ricoh-gr-gr-ii-recipes/) 与 [GR III 目录](https://ricohrecipes.com/ricoh-gr-iii-recipes/) 链接的 12 个 Collection。各 JSON 中 `recipes[].raw_parameters` 是采集到的参数段，名称按该参数段之前的 `Recipe:` 标题配对；跳过 Patron 的无参数记录。每页的 `html_sha256` 只用于固定采集输入，不证明作者原数值正确。网页完整正文与图片没有落盘。

[Candy Color 400](https://www.lukeptaylor.com/blog/candy-color-400-ricoh-gr-iii-film-recipe) 参数散列在 20 个原始参数行中。JSON 保留 `original_parameter_lines`，CSV 将大写标签转为统一英文标签，未改取值。

原文空值保留。GR II Bright Summer 只有 High Key 的鲜艳度，没有 Contrast／Sharpness，不补零。GR II Classic Analog 的 Effect Off 和 Image Settings Standard 分列保存。[Lomo 原文](https://ricohrecipes.com/the-lomo-collection/)、[Landscape 原文](https://ricohrecipes.com/the-color-landscape-collection/)。

## FRAME 文本新增线索

[README](https://github.com/Lyle-xub/FRAME-GR2) 当前文本 SHA-256：`1f9b6ad0ffc0bfb7df7122b7d1c37adcbd47ec3a2d16f63a27fb51ada1d1bc5a`。URL 是可变 main，以获取日期和哈希标识这次阅读；没有下载发布附件。

一条短原文引用：`保留默认曲线与矩阵`。这是 README WN1 更新记录第 280 行的作者说明。第 305 行说明复用原生暗角；第 303 行说明 HDF 与颗粒合并处理；第 349 行声明未提供实现源码。作者说法没有在本轮复现。行号对应此哈希的文本；后续 main 修改可能漂移。[直接 README 文本](https://raw.githubusercontent.com/Lyle-xub/FRAME-GR2/main/README.md)。

公开数值只包括浓度、颗粒和 HDF 枚举；没有以照片菜单猜其余范围。Release 的“近似转换”提示只证明存在转换分支，不能证明所有 LUT 都近似或确定转换模型。[Release](https://github.com/Lyle-xub/FRAME-GR2/releases/tag/v0.62.1-wn3)。

## 官方和技术文档

GR III 官方手册由网络读入内存，再用本地 `pdftotext` 读取；没有下载可执行软件。哈希见 `official-manual-metadata.json`。印刷页 87 为预设定义，148 为 WB ±14 与参数列表，89 为镜头光量／动态范围。该手册的预设列表早于后续新增负片／交叉冲印，应与[官方扩展记录](https://www.ricoh-imaging.co.jp/english/products/gr-3/firmup/)一起读。

GXR 原厂功能用既有 `research/recipes/sources/GXR_E.pdf` 与 `gxr_vup_en.pdf`。临时完整文本抽取已删除，仅在报告引用页码。A12 50mm 引擎名称用[官方比较 FAQ](https://www.ricoh-imaging.co.jp/english/r_dc/support/faq/bp/docs10/EDXR01000.html?sscl=f_n1fc01)核验。

GR III 架构文档的 raw 与网页缓存措辞有差别：raw 给出 SC2000／Cortex-A7，网页索引仍有未确认的 caveat。因此报告保留研究者结论而不认作本轮硬件鉴定。[系统文档](https://github.com/hhornbacher/gr3x-fw-hack/blob/main/docs/system.md)。

一个可见的资料冲突：部分社区 BLE 文档把 GR II 列入通用型号列表；[GR II 官方连接说明](https://www.ricoh-imaging.co.jp/english/support/man-pdf/gr-2.pdf)描述 Wi-Fi／NFC。报告不据此给 GR II 或 GXR 增加 BLE 能力，型号列表不能替代逐项硬件确认。

## 检索边界与未完成证据

检索词组覆盖 `Ricoh GR firmware hack github`、`Ricoh GR Digital firmware reverse engineering`、`FRAME-GR2 LUT 参数`、`Pentax firmware PHDK`、`Pentax K-3 III SC2000`、`Ricoh GR recipe decoder`、`Ricoh darktable negative film` 及配方作者／应用名称。

GitHub REST 树目录请求返回 `HTTP Error 403: rate limit exceeded`。改用公开 GitHub 网页和 raw Markdown 阅读，没有绕过登录或使用凭证。PentaxForums 部分页第一次 Web 读取报 `Internal Error`，可用搜索索引和后续能读取的原帖页面核对；无法读取的细节没有充当实施证据。`ergoadams/pentax-scripting/master/README.md` 返回 404，使用可读仓库首页，不推测 README 分支或文件名。

本轮没有进入 Google Drive 私有 POSI LUT 目录，没有下载其 LUT 包；算法结论仅按[作者原帖](https://www.reddit.com/r/Lumix/comments/1s5sxbv/i_reverseengineered_ricoh_gr_iis_positive_film/)记录。

GR DIGITAL I–III 的公开第三方色彩固件源码未检索到；GR DIGITAL IV 的正片／漂白跳过有官方功能证据。报告将负面检索结果与原厂能力分开，不能推论 GR DIGITAL 永远不可改。
