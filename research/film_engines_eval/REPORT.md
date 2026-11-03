可以评审

# spektrafilm、fotufilm 与你新给的 5 个 LUT：能不能进 GXR，能像到什么程度

2026-10-31。对象是 GXR 机身 1.51 + A12 50mm 的电脑模型。本轮只做研究和估算：
- 没碰相机、存储卡和 `/Volumes/RICOHDCX`，没生成上卡文件，没有 git 写操作，没开子代理。
- 没下载或运行任何网上的程序。两个项目的源码是通过 GitHub 网页和 API 读的文本。
- 下载的只有 LUT 数据文件和随附的许可、说明文本，都放在被忽略的 `local/downloads/`。

文中所有百分比都是**电脑预测**，不是相机实测。

## 先说结论

1. **你的 5 个 LUT 现在就能做成相机配方，而且会很像。**它们都是温和的"显示色进、显示色出"风格 LUT，和 04 本来只差 3.6–4.9 个色差单位。用相机自带的表近似后，剩下约 0.8–1.7。≤1 基本看不出，1–2 要并排细看才分得清。
   - 百分比只有 66–78%，是因为分母（04 和目标的差距）本来就小，并不代表不像。
   - 4 个哈苏里，HiContrast 和 HiContrast_LowSat 几乎一样（彼此只差 1.4），挑一个就够。
   - 建议先进 3 个：**Leica M9 STD**（余差 0.8–0.9）、**哈苏 HNCS HiContrast**（1.1）、**哈苏 HNCS LowSat**（1.5–1.7）。这三者彼此差 4.7–6.2，风格分得开。
2. **spektrafilm 这类"负片 + 相纸"的物理模拟，在相机表上只能做个大概。**
   - 相机表：50–80%，余差 2.4–3.9，并排能看出差别。
   - 机内 17³ 真 LUT：约 96–97%，余差 0.2–0.5，基本一样。
   - 结论和之前胡子 LUT 那一轮一致：要像，得等机内真 LUT；在那之前可以用电脑工作室从 RAW 出片。
3. **两个项目都没有发布官方 LUT 包。**
   - spektrafilm 自带 LUT 烘焙器（能出 `.cube`），但要自己装、自己跑。作者只在论坛发过 1 个 alpha 测试 LUT：Gold 200 冲印到 Supra Endura 相纸，V-Log 输入。
   - Hugging Face 上有第三方（NicePhoto）重烘的 14 个 spektrafilm LUT，CC BY-SA 4.0。我用的就是这批里的 8 个。
   - fotufilm **没有 LUT 导出**。要拿它的颜色，只能用它的命令行渲染一张恒等 Hald 图，再读回成 LUT。本轮规则不准运行，所以没有数字。
4. **不建议替换现有 8 个配方。**新外观等 `GXRFX.BIN` 效果层（每个效果每个单元 512 B 深层行）一起进，放在自建配方里。如果想马上试，只在测试卡上临时顶掉一个你最少用的。
5. **颗粒和光晕放不进 LUT。**
   - 光晕先在电脑工作室做：它要大半径模糊，机身上预计每张 1–8 秒，而且编码前入口还没上机验证。
   - 颗粒两边都能做：工作室现在就能做；机内等编码前入口（H40）的测速和只读、写回探测通过后再做，预计每张 0.5–3.5 秒。

---

## 1. 两个项目对比

| | **spektrafilm**（Andrea Volpato） | **fotufilm-engine**（DhaliwalX / MUA Studio） |
|---|---|---|
| 是什么 | Python 参考实现：从相机 RAW 的线性 RGB 重建光谱，模拟负片曝光、显影耦合剂、相纸印放、扫描 | Swift 引擎，带命令行、Mac App、Resolve 和 Final Cut 插件、浏览器编辑器；在 380–780 nm 的 81 个波长上算胶片响应 |
| 版本、活跃度 | 最新标签 v0.3.3（2026-06-06），1.3k 星，作者称"快速开发中" | v1.14.1（2026-10-28），140 星，发布频繁 |
| 胶片（彩色、黑白） | **20 个胶片档案**：富士 C200、Pro 400H、Provia 100F、Velvia 100、Superia X-TRA 400；柯达 Ektachrome 100、Ektar 100、Gold 200、Kodachrome 64、Portra 160/400/800（另有 800 推一档、推两档）、UltraMax 400、Verita 200D、Vision3 50D/200T/250D/500T。**没有黑白，没有 CineStill** | **47 个胶片档案**：Acros 100、HP5+、Tri-X 400、T-Max 100、FP4+、Delta 3200、Double-X 5222；Portra 400、Gold 200、Ektar 100、UltraMax 400、Kodacolor 100、Pro 160NS、Pro 400H、C200、Superia 200/400、Reala 100、Reala 500D、Phoenix 200、Lomo 100、3 种 Lomochrome；Provia 100F、Velvia 50、Astia 100F、Ektachrome E100、Kodachrome 25/64/200、Agfachrome 50/100/200；CineStill 400D/800T、Vision3 250D/500T、Eterna 500、Eterna Vivid 500、F-64D、Verita 200D；Aerochrome、Aerocolor、彩色红外；Instax Mini/Wide |
| 相纸 | 8 种：富士 Crystal Archive Type II；柯达 2383、2393、Ektacolor Edge、Endura Premier、Portra Endura、Supra Endura、Ultra Endura | 9 种负片相纸、片基（Ektacolor Edge、Endura Premier、Crystal Archive CA、2383、2393、Eterna-CP 3513DI/3521XD、EXR 5386、Agfa CP30），外加 2 种 Ilfochrome |
| 空间效果 | 颗粒（随机模型）、光晕、散射、耦合剂扩散（局部对比）、镜头、放大机、扫描模糊、锐化 | 颗粒（含多种颗粒模型和斑驳）、光晕（有回返和颜色控制）、乳剂扩散、耦合剂邻接效应、柔焦滤镜、眩光、色边、局部影调 |
| **现成 LUT** | **官方没有**（仓库和 Releases 都没有 `.cube`）。作者在论坛发过 1 个 alpha：Gold 200 冲印到 Supra Endura，V-Log 进、sRGB 出，33³。第三方 Hugging Face 有 14 个重烘版，sRGB 进出，33³ 16 位 | **没有**，也没有 LUT 导出功能 |
| 自己烘焙要什么 | 装它的 Python 3.13 环境，运行 `spektrafilm-lut build --film … --print … --input srgb --output srgb`；能出 `.cube`、`.3dl`、Hald PNG 和 Lumix 专用 `.cube` | 运行它的命令行，渲染一张恒等 Hald 图再读回。要关掉颗粒、光晕、扩散、耦合剂邻接、眩光和局部影调；还要把默认的 Auto Levels（逐张自动定标）换成 Reference Exposure 或 Graded Print 这类固定模式，否则同一张 LUT 每张照片都会不一样。这两条都是读源码得出的，没跑过 |
| LUT 里有没有空间效果 | 没有：烘焙器开 `lut_mode`，关掉所有空间和随机效果，所以 LUT 只有颜色和影调 | 同理，只能取颜色 |
| 期望的输入 | 运行时：场景线性 RGB。烘焙器支持 sRGB、Rec.709、线性、V-Log、S-Log3、F-Log/F-Log2、Apple Log 等二十多种编码（L-Log 不在注册表里） | 先解码成线性 Rec.2020；JPEG 按 sRGB 解码，RAW 走自己的解码 |
| 许可 | 代码 GPLv3；胶片档案和 LUT 用 CC BY-SA 4.0（2026-05-28 的序言 v1.1）。"不转售""不拿去训练商用 AI"写的是作者的请求，不是法律条款。旧版 v0.3.2 的 LUT 包（论坛那个 Gold 200）随附的是更早的自定许可：可商用、免费分享、不得出售，也不得放进付费插件 | 代码 Apache-2.0；47 个胶片档案 CC BY-SA 4.0，要署名 Fotufilm、链接 fotufilm.com，并保留 MUAStudio 版权声明；渲染出的照片不受档案许可约束 |

### 输入编码和 GXR 怎么对上

- **相机表配方**：不在乎 LUT 的输入是什么。工具先用 DNG 场景光或 04 的 JPEG 算出"目标长什么样"，再拟合相机表。
  - 场景线性、Log 输入的 LUT 吃 DNG 的场景 XYZ；
  - 显示色输入的 LUT 吃 04 的 JPEG 码。
- **机内真 LUT**：编码前入口拿到的是 04 渲染后的 8 位 YCbCr，也就是显示色。拟合 17³ 时直接学"04 输出 → 目标"，所以：
  - 显示色输入的 LUT 天然对得上；
  - 场景线性、Log 输入的 LUT 也能学，但 04 已经裁掉的高光和压掉的阴影救不回来。
- **你的 5 个 LUT**：文件名写的是 Rec709。实测它们的灰阶保持中性，0→0、1→1，带 S 曲线，所以是"显示色进、显示色出"的风格 LUT，不是 Log。
  - 主算法沿用胡子 LUT 的做法，把 04 的 sRGB 码直接当 Rec709 码喂进去；
  - 另算一组"按 Gamma 2.4 显示解码"的解释作对照，两种解释只差 0–4 个百分点，余差几乎一样。
- **spektrafilm 的 sRGB LUT 有两种用法**，表里两种都算了：
  - **接在 04 的 JPEG 后面**：相当于手机 App 的用法，04 的影调曲线叠上胶片曲线；
  - **直接吃场景线性光**：spektrafilm 本来的设计。实景余差更小，分母更大。
- **作者那个 V-Log LUT**：按 V-Log 吃 DNG 的场景光。它和 Hugging Face 的 Gold 200（场景版）结果接近，两个来源可以互相印证。

---

## 2. 相似度（全部是电脑预测）

方法和 `film_look_routes` 完全相同：
- 工具：`ceiling.py` 等 7 个文件原样复制自 `research/film_look_routes`（那边又来自 `lut_convert`），只把写入围栏改到本目录；
- 驱动脚本：新写的 `engines_ceiling.py`；
- 输入：50mm 的 04 模型、同一组 4 张 DNG 场景、同一套留出合成色（种子 20261023）和第 4 张整图留出；
- 百分比 = `1 − 中位色差(结果→目标) / 中位色差(04→目标)`；
- 机内 LUT 用 Q8.8 节点和三线性插值，平滑系数 λ=0.1；不模拟 4:2:2 色度共用和 JPEG 再压缩，`body_lut` 估过这部分约损失 1–1.5 个百分点。

**读表提示：**余差（最后两列）比百分比更直观。ΔE00 ≤1 基本看不出，1–2 要并排细看，2–3 仔细看能分辨，>3 一眼能看出。

### 2.1 你的 5 个 LUT（04 的 JPEG 码直接当 Rec709 码）

| LUT | 相机表（合成 / 实景） | 机内 17³（合成 / 实景） | 机内 33³ | 04→目标 ΔE00 | 相机表余差 | 机内 17³ 余差 | Gamma 2.4 解释下的相机表 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Leica M9 STD | 76.5% / 86.7% | 95.4% / 92.4% | 96.0% | 3.73 | **0.88** | 0.17 | 78.0%（余差 0.80） |
| 哈苏 HNCS | 75.1% / 81.7% | 94.0% / 89.3% | 95.5% | 3.64 | **0.91** | 0.22 | 77.1%（0.86） |
| 哈苏 HNCS HiContrast | 75.2% / 83.3% | 94.3% / 93.4% | 96.0% | 4.57 | **1.13** | 0.26 | 77.8%（1.05） |
| 哈苏 HNCS HiContrast LowSat | 66.4% / 83.3% | 94.5% / 93.2% | 95.8% | 3.59 | **1.21** | 0.20 | 70.1%（1.13） |
| 哈苏 HNCS LowSat | 65.9% / 78.4% | 96.1% / 91.9% | 96.9% | 4.87 | **1.66** | 0.19 | 68.8%（1.53） |

外观之间互相差多远（合成留出上的中位色差）：

| | 04 | HNCS | HiCon | LowSat | HiCon-LowSat | M9 STD |
|---|---:|---:|---:|---:|---:|---:|
| HNCS | 3.64 | — | 3.24 | 3.88 | 3.47 | 3.33 |
| HiContrast | 4.57 | 3.24 | — | 6.15 | **1.43** | 6.21 |
| LowSat | 4.87 | 3.88 | 6.15 | — | 5.85 | 4.66 |
| HiContrast LowSat | 3.59 | 3.47 | **1.43** | 5.85 | — | 5.97 |
| M9 STD | 3.73 | 3.33 | 6.21 | 4.66 | 5.97 | — |

- HiContrast 和 HiContrast LowSat 只差 1.4，并排细看才分得清，只留一个即可。
- HNCS 标准版和其余每一个都差约 3.3，处在中间位置。
- 另外，`LowSat` 那张把纯红压到 0.86、给纯绿加了 0.23 的蓝，算是有个性的"低饱和"，不是简单降饱和。

### 2.2 spektrafilm 的胶片

数据来源：Hugging Face `Norton0924/OpenSourceLuts`，版本 `484c3c1f`。8 个文件的 SHA-256 都与它的 manifest 对上了。它是 spektrafilm-lut 0.3.4 导出的版本，每个胶片配 1 种默认相纸；第三方在线性光里加了曝光增益，让中灰进出对齐。作者论坛那个 Gold 200 是原版。

| 胶片（相纸） | 用法 | 相机表（合成 / 实景） | 机内 17³（合成 / 实景） | 机内 33³ | 04→目标 | 相机表余差 | 17³ 余差 |
|---|---|---:|---:|---:|---:|---:|---:|
| Portra 400（Portra Endura） | 接 04 JPEG | 65.4% / 55.4% | 97.0% / 91.5% | 97.7% | 7.61 | 2.63 | 0.23 |
| | 场景光 | 77.2% / 75.9% | 95.8% / 94.4% | 97.2% | 11.07 | 2.53 | 0.46 |
| Portra 160（Portra Endura） | 接 04 JPEG | 69.2% / 57.8% | 97.5% / 92.8% | 98.0% | 8.85 | 2.73 | 0.22 |
| | 场景光 | 79.6% / 77.6% | 96.2% / 94.6% | 97.3% | 11.57 | **2.37** | 0.44 |
| Gold 200（Portra Endura） | 接 04 JPEG | 64.1% / 58.2% | 96.8% / 91.9% | 97.6% | 7.42 | 2.66 | 0.24 |
| | 场景光 | 77.2% / 75.6% | 95.9% / 94.3% | 97.2% | 10.90 | 2.49 | 0.44 |
| Gold 200（Supra Endura，作者论坛原版，V-Log） | 场景光 | 72.5% / 67.6% | 95.9% / 93.8% | 97.3% | 11.20 | 3.09 | 0.46 |
| UltraMax 400（Portra Endura） | 接 04 JPEG | 59.9% / 54.5% | 96.5% / 91.4% | 97.4% | 6.60 | 2.65 | 0.23 |
| | 场景光 | 76.9% / 76.5% | 95.9% / 94.2% | 97.3% | 10.75 | 2.48 | 0.44 |
| Ektar 100（Portra Endura） | 接 04 JPEG | 62.1% / 49.3% | 97.1% / 92.6% | 97.9% | 8.18 | 3.10 | 0.24 |
| | 场景光 | 72.3% / 71.0% | 96.1% / 94.0% | 97.4% | 11.33 | 3.14 | 0.44 |
| Pro 400H（Crystal Archive） | 接 04 JPEG | 60.1% / 45.0% | 96.7% / 92.5% | 97.7% | 7.39 | 2.95 | 0.24 |
| | 场景光 | 76.3% / 71.2% | 96.0% / 94.9% | 97.5% | 11.95 | 2.84 | 0.48 |
| Superia X-TRA 400（Crystal Archive） | 接 04 JPEG | 51.4% / 38.3% | 96.5% / 92.6% | 97.9% | 8.05 | 3.91 | 0.28 |
| | 场景光 | 70.5% / 67.7% | 96.1% / 94.5% | 97.6% | 12.23 | 3.60 | 0.48 |
| Vision3 500T（2383 电影拷贝片） | 接 04 JPEG | 71.2% / 58.8% | 97.5% / 94.7% | 98.1% | 9.51 | 2.74 | 0.24 |
| | 场景光 | 76.8% / 73.6% | 96.4% / 95.7% | 97.6% | 12.95 | 3.00 | 0.47 |

怎么读：

- **相机表的瓶颈**：负片 + 相纸会把色相按亮度扭转，还有通道间串扰，相机的 24 扇区和曲线表达不了。所以余差停在 2.4–3.9。和 `huzi_luts`、`film_look_routes` 里风格强的 LUT 是同一档。
- **机内 17³**：两种用法都在 96–97%，余差 ≤0.5。真 LUT 一旦通了，这些胶片都能做得很像。
- **哪些胶片其实很接近**（同一张合成留出上）：
  - 柯达这几支互相很近：Portra 400 与 Portra 160 差 1.3，与 Ektar 差 1.4；Gold 200 与 UltraMax 差 1.3。它们都印在同一种相纸上，所以"柯达负片味"选 1–2 个就能代表。
  - 真正风格不同的是：Superia X-TRA 400（富士相纸）、Pro 400H、Vision3 500T（电影拷贝片，钨丝灯平衡）。
- **两个 Gold 200 来源**（Hugging Face 重烘的场景版、作者论坛原版）的相机表和 17³ 数字接近（77% 对 72%，95.9% 对 95.9%）。说明第三方的曝光对齐没有改变大的结论。剩下的差别主要来自相纸不同：Portra Endura 对 Supra Endura。
- **CineStill 800T** 本质是去掉防光晕层的 Vision3 500T。颜色可以用 Vision3 500T 代表，它最有辨识度的红色光晕要单独做，见第 4 节。spektrafilm 没有黑白胶片；黑白要用 fotufilm 的档案，或沿用已有的 03 和富士 Acros 路线（`film_look_routes`：Acros 相机表约 98%）。

### 2.3 fotufilm

没有数字。它没有现成 LUT，要拿颜色就必须运行它的程序，本轮不允许。它也是"负片 + 相纸（或反转片直接看）"的物理模型，按同类模型推断：

- 相机表预计在 50–80%；
- 机内 17³ 预计约 96%。

这是推断，不是计算结果。它的独有价值在于 spektrafilm 没有的片种：黑白（Tri-X、HP5、Acros）、反转片（Velvia 50、Kodachrome、Ektachrome）、CineStill、Instax、Aerochrome。

### 2.4 和相机实测的差距

- 05/06 的历史：本工具预测 87.2/83.2%，相机实测 84.1/82.3%，实测低 1–3 个百分点。
- 机内真 LUT 还没有任何实测。`gr4_lut_ceiling` 里同样是 17³，从屏幕训练换到实体色卡，从 92–94% 掉到 80–83%。
- 所以上面"机内 17³"那一列，规划时宜按实测可能再低 5–12 个百分点来看。

---

## 3. 推荐

### 3.1 现在就值得进相机的（相机表近似，不需要机身更新）

| 优先 | 外观 | 理由 |
|---|---|---|
| 1 | **Leica M9 STD** | 余差 0.8–0.9，几乎原样；和 07 L-Chr、08 L-Viv 不同，是 M9 CCD 那种标准色 |
| 2 | **哈苏 HNCS HiContrast** | 余差约 1.1；在你的 5 个里离 04 最远之一，和 M9 STD 差 6.2，风格分得开 |
| 3 | **哈苏 HNCS LowSat** | 余差 1.5–1.7；低饱和、红色收、绿偏青，和前两者都差 4.7 以上 |
| 可选 | 哈苏 HNCS（标准） | 余差 0.9，但介于以上几个之间（各差约 3.3），可做"日常中性"一档 |
| 不必 | 哈苏 HNCS HiContrast LowSat | 与 HiContrast 只差 1.4，重复 |

### 3.2 等机内真 LUT 再进的

- spektrafilm 胶片：相机表余差 2.4–3.9 不够像；17³ 能到 96–97%。
- 第一批建议按"风格分得开"挑 4 个：
  - **Portra 400**（代表柯达负片那一组）；
  - **Superia X-TRA 400**（富士负片）；
  - **Vision3 500T**（电影感、钨丝灯；加上光晕就是 CineStill 800T 的味道）；
  - **Pro 400H**。
- 如果在真 LUT 之前就想在相机里有个"柯达负片味"，可以拿 **Portra 160（场景版）**先做相机表近似（余差 2.37，是这组里最好的）。但要知道它只是"像个大概"。

### 3.3 替换现有 8 个，还是等效果层

**不替换，等 `GXRFX.BIN` 效果层。**理由：

- 01–08 你都在用。新外观和它们并不重复：M9 STD 和 07/08 是两种徕卡，哈苏是新的风格。
- 这次的新外观在相机里需要的东西，正是效果层设计的内容：每个效果、每个单元一套 512 B 深层行，挂在自建配方上。5 个外观 × 3 个单元约 7.7 KB，卡上文件大小不是问题。
- 按 `research/g140_entries_design/DESIGN.md` §0，g140 只做第 1 层（名字和 10 个调节量）。效果层是第 2 层，设计里排在 g140 之后（方案 Y 约 +3.1–3.3 KB 主请求，超出现行上限，要先做预算决定和一次只读探测）。所以准确地说，要等"g140 之后的效果层"，不是 g140 本身。
- 想现在就看看效果：可以在**测试卡**上临时用 Leica M9 STD 顶掉一个你最少用的配方，日常卡不动。具体顶哪个由你定。
- `lut_convert` 只有 50mm 的实拍模型。28mm 和 MOUNT 沿用 50mm 的外观时，每个单元的深层行都要各自拟合，本轮没做。

### 3.4 颗粒和光晕怎么办

| 效果 | 机身编码前入口（H40，`0x2015F9D8`） | 电脑工作室 |
|---|---|---|
| **颗粒** | 预计一张主图 0.5–3.5 秒（预生成噪声块），或 0.8–5.2 秒（逐像素随机数），见 `film_look_routes` §4.3，工程估计、未测量。前提是 H40 的 P0 测速、P1b 只读、P1c 原样写回、P3 全帧都过。RAW+JPEG 下只改 JPEG，DNG 不受影响（静态推断）。原生场景 21 的颗粒在单元里，和 RAW 互斥（`grain_raw_feasibility`） | 现在就能做。可以按 spektrafilm、fotufilm 公开的思路做随亮度变化、按画幅缩放的颗粒（只参考方法，不抄 GPL 代码，见第 5 节） |
| **光晕、扩散** | 预计 1.1–8.1 秒（1/8 尺度模糊），对拍摄节奏影响明显，还要额外缓冲 | **建议先在这里做**。光晕要从亮部扩散出红色光圈，JPEG 高光已裁，但阈值取亮部就够用 |
| 优先级 | 颗粒先于光晕；两者都排在机内真 LUT 的 P0–P3 探测之后 | 光晕和 CineStill 风格优先 |

---

## 4. 许可说明

| 材料 | 你个人使用 | 放进工作室开源仓库 |
|---|---|---|
| **你的 5 个 LUT**（哈苏 HNCS ×4、Leica M9 STD；文件头 "ROGER WANG BEIJING 2026-05-14"） | 可以 | **许可不明**：哈苏、徕卡的配色加第三方作者，没有任何许可声明。原文件和由它们拟合出的配方数据都只放本地，不进开源仓库，除非拿到作者授权 |
| **spektrafilm 胶片档案和 LUT**（CC BY-SA 4.0） | 可以，渲染出的照片完全归你 | 可以随仓库分发，但要：①保留作者 Andrea Volpato、项目链接、许可文本；②改过的要注明"由谁修改"；③改过的数据仍是 CC BY-SA 4.0。作者的许可把"任何编码同一内容的派生物"都算进去，所以由它拟合出的相机深层行、`GXRFX.BIN` 里的对应条目，也应按 CC BY-SA 4.0 标注署名。ShareAlike 只约束这些数据文件，不会把工作室代码变成 CC BY-SA |
| **spektrafilm 代码**（GPLv3） | 自己运行没问题 | **不要把它的代码抄进工作室**，除非工作室整体改用 GPL。作者 README 还写着"受其方法直接启发的也算派生"，这超出了 GPL 的法律范围，但为免争议，工作室只参考公开论文和物理原理，不移植它的实现 |
| **论坛 Gold 200 包**（v0.3.2，随附旧版"spektrafilm License v1.0"） | 可以 | 旧许可允许"放进开源程序并附许可"，禁止出售、禁止放进付费插件。保守起见只放本地；需要时可以用新版烘焙器重出一个 CC BY-SA 版本 |
| **Hugging Face 重烘版**（CC BY-SA 4.0，NicePhoto 修改） | 可以 | 同 spektrafilm 档案，署名链上还要加 "Modified by NicePhoto" |
| **fotufilm 代码**（Apache-2.0） | 可以 | 可以引用或移植，要保留 LICENSE、NOTICE 和版权声明 |
| **fotufilm 胶片档案**（CC BY-SA 4.0） | 可以 | 署名 Fotufilm 并链接 fotufilm.com，保留 MUAStudio 版权声明，注明修改；派生数据保持 CC BY-SA |
| 胶片和品牌名（Kodak、Fujifilm、Portra…） | — | 只能用来说明"仿的是哪支片"，不能暗示官方认可；"spektrafilm""Fotufilm"也不能用作产品品牌 |

作者另有两条请求（不是法律条款）：不要把 LUT 本身当付费 LUT 包卖，不要拿 LUT 或它的输出训练商用 AI 模型。按"免费工作室、免费配方"的方向，这两条不冲突。

---

## 5. 文件

本目录：
- `REPORT.md`：本报告；`SHA256SUMS`：本目录受版本管理的文件的哈希；
- `engines_ceiling.py`：本轮的驱动脚本（读用户 cube、读 lut16、两种用法、调用 `ceiling.py`）；
- `pairwise.py`：外观之间的距离；`summarize.py`：汇总成表；
- `camera.py`、`ceiling.py`、`convert.py`、`cube.py`、`fit.py`、`spaces.py`：原样复制自 `research/film_look_routes`；`guard.py` 只改了写入围栏和临时目录。

被忽略的 `local/`：
- `downloads/hf-opensourceluts/`：8 个 `.lut16`，加 README、manifest、CHANGELOG 和许可文本；
- `downloads/spektrafilm-forum/`：原始 zip，只解出了 `.cube`、`bundle.json`、README、许可和 QA 报告文本；
- `engines-*/engines.json`、`engines-*.log`：逐个外观的完整结果；
- `summary.json`、`tables.md`：汇总；`pairwise.json`：外观之间的距离；`scene_cache/`：场景缓存。

下载数据的 SHA-256：

| 文件 | SHA-256 |
|---|---|
| `olut_P09_sk.lut16`（Portra 400） | `aabebbf1adece84929900d4ac57c4fa5d27fe1658c101458277b3f99bd49e5dd` |
| `olut_P06_sk.lut16`（Portra 160） | `2adc96d526254b81ac2ba27d7d677cda5ecfdb4b16345ff7ccc3c950909a10cf` |
| `olut_D17_sk.lut16`（Gold 200） | `7cca07d47c8668423f9d1eddd4eaee647dc3ea1ab8d97491472eefc37c3034b4` |
| `olut_D18_sk.lut16`（UltraMax 400） | `73845754c4c46289014e60c6a4d9320956e41abd3e960951663e1307f95caa9b` |
| `olut_P05_sk.lut16`（Ektar 100） | `181ce4aaa68e3ef77e6a4bf6ca014dbabaa5800d8c78ce76724a98a9e67d2be5` |
| `olut_P03_sk.lut16`（Pro 400H） | `a6f82ea7ad8e01aa949098aeab7e3184ddb15a92812b11b83e66ae710b996b54` |
| `olut_D12_sk.lut16`（Superia X-TRA 400） | `49d4b56cb8fb83decf55bf4a8424aede84d92112024f287911582828ad70fb79` |
| `olut_C13_sk.lut16`（Vision3 500T） | `c2ab04db3cb1e78be9f33a96a8f81dd8d852067c8a2b95ce30e5a3d50204721e` |
| `gold200_vlog.zip`（论坛原包） | `f1fe13f797e849608967184545ab7a1f22d3fdf7cf32602cfe651075f69e4b56` |
| `lut_v032_gold200_supraendura.cube` | `1759a35e4ac95103b690fbbb0ca8412086ede9d20cbde0adccddb36ce83514fd` |

你的 5 个 LUT（只读，原地未动）：

| 文件 | SHA-256 |
|---|---|
| `Hasselblad_HNCS_33_Rec709.cube` | `3a51694a9a07681fc5c5499c626c6f8e0077e8eeaf9bfc6044ff4d7b58d5289f` |
| `Hasselblad_HNCS_HiContrast_33_Rec709.cube` | `17936b9c8fa2247b701605d33689b06c9e73c35fab6386c66ea5c27a0c45bfea` |
| `Hasselblad_HNCS_LowSat_33_Rec709.cube` | `19f3837291b198d9733367aeb582651703bdbb00e081c83e0a8e742022feb5cc` |
| `Hasselblad_HNCS_HiContrast_LowSat_33_Rec709.cube` | `3d5a0e66f521349210c9a70c0da82c0c400840762fc0cc742039522e605fd5f4` |
| `Leica_M9_STD_33_Rec709.cube` | `e77d7a8e417e316b0e6d7133f58274ef5ff407b63a15a011107123ecf8052b1c` |

运行记录：
- 一共 4 次计算，都是单进程、`nice -n 10`，用 perl alarm 设超时（用户 LUT 3600 秒、spektrafilm 3600 秒、论坛 900 秒、汇总 600 秒）；
- 每个外观约 31–37 秒，没有失败；
- 临时目录在 `/Volumes/Workspace/Scratch/tmp/projectricoh/film-engines`，已删除。

参考链接：
- [spektrafilm](https://github.com/andreavolpato/spektrafilm)、[它的许可](https://github.com/andreavolpato/spektrafilm/blob/main/SPEKTRAFILM_LICENSE.txt)、[论坛 LUT 帖](https://discuss.pixls.us/t/spektrafilm-luts/57879)、[ART 桥接说明](https://artraweditor.github.io/SpectralFilmSimHowto)、[OFX 插件](https://spektrafilm.114c.de/)
- [fotufilm-engine](https://github.com/DhaliwalX/fotufilm-engine)、[它的 LICENSING.md](https://github.com/DhaliwalX/fotufilm-engine/blob/main/LICENSING.md)
- [Hugging Face OpenSourceLuts](https://huggingface.co/Norton0924/OpenSourceLuts)
