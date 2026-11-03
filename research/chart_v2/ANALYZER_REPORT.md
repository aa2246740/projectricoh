# chart-v2 实拍解析器交付报告

解析器、六配方闭环评分、漂移与跨页一致性诊断已交付。30 个合成识页场景全部通过，12 次强制回退也通过；指定旧照片的 14 对 RAW/JPEG 路径检查通过。新版色卡尚无相机实拍，本轮没有新版实测相似度，也没有相机验收结论。

在共享检出根目录运行这一条命令，输出只写新的 run 目录：

```bash
python3 -I -B research/chart_v2/analyze_chart_v2.py --input <dir> --manifest <json> --out research/chart_v2/local/runs/<name>
```

首尾编号与逐帧 manifest 的填写方法见 [ANALYZER_USAGE.md](ANALYZER_USAGE.md)，模板为 [analyzer_manifest.example.json](analyzer_manifest.example.json)。解析后先看 `quality.html` 的页号和取样框，再看评分 CSV 与 `stability.json`。

## 已核实

### 写入范围与封存输入

- `/Volumes/Workspace` 已挂载、可写，APFS，Volume UUID 为 `14BE04EB-AF49-497E-B36A-B078B2F7C5E8`，已读盘根 `AGENTS.md`。运行入口重复检查卷与 Git 忽略规则，拒绝已有 run 和 `local/runs/` 外的输出。输入路径逐级解析符号链接，在查询其他卷的目标前拒绝该路径。
- 本轮只在 `research/chart_v2/` 新增解析文件与 `local/` 证据。没有删除、移动或改写其他研究数据、captures、官方固件，没有操作相机、访问存储卡、生成上卡交付物、安装包、启动子代理或 commit/push。
- 9 个封存文件与 7 张页面共 16 个输入在工作前后哈希一致。旧 `SHA256SUMS` 的全部 36 项也重新核对通过。证据为 `local/analyzer_baseline.json`、`local/analyzer_validation.json`。
- 原有 `closed_loop`、定位器、DNG 解码器和实体卡脚本均未改写。冻结涉及 24 个上游来源，形成 22 个辅助副本；开发用副本在 `local/vendor/`，每次正式运行再把副本和哈希放到本 run 的 `vendor/`。BW 参考缓存、表解析结果、RAW 数字与所有配方目标数字均只留在本任务 `local/`。

### 识别、几何与取样

- 先调用未修改的 `locate_screen`。失败时检测棋盘外白框，拟合四角单应，再沿外白框边缘细化。回退只要求预期棋盘的相关性，不要求把模糊 BL 的格数判为 8。Hamming 页码与顶部 `Pn/6` 中数字的模板读取互相核对；两者明确冲突时拒绝识页，证据不足时不按颜色或文件顺序猜页号。
- Hamming 为扩展 SECDED，纠正单比特错误，拒绝已检出的双比特错误。差分读取正反两行，另保存两行各自的解码、同步位、弱对比格与纠错位置。顶部数字模板直接读封存页面，不依赖 OCR 安装。
- 白页用大面积连续近中性场识别，保留中央 ROI。DIOPTIX 由 `analyze_2e.detect_lattice` 在 RAW 的半分辨率 WB 亮度上找点阵，再映射回已验证的 JPEG 坐标。亮度使用 `DngScene` 的真实 CFA 相位、线性化与黑电平；底行必须满足 RAW 白到黑递减与中性检查，否则拒绝朝向。
- 每块按 `roi_bbox_px` 的投影多边形取样，JPEG 和各原生 CFA 通道均取 10% 至 90% 截尾中位数。另报告未截尾 JPEG 空间标准差、RAW 均值/标准差、样本数和 RAW 饱和比例。JPEG/RAW 配准失败、ROI 越界、元数据冲突或质量标记都会留下读数和排除原因。
- CSV 前八列严格为 `frame,page,patch_id,class,raw_rgb,jpeg_rgb,valid,spatial_sd`，另附 `sample_key`、单元、槽号、ISO、快门、光圈、白平衡和选择器字节。RAW 是减黑、按白电平归一、未做白平衡的相机原生 RGB。JPEG 以 8 位码值为单位，不把它混成 0 至 1 的线性值。

### 闭环评分与锚点诊断

- 薄适配层把每页固定 `ANCHOR_midgray` 命名为旧接口的 `G_L50`，其余调用冻结的 `Engine`、`Targets`、`score_record`、`summarize_slot`、`similarity`。无需修改 `closed_loop`。每张配方帧必须匹配同单元、同页、曝光与白平衡一致的 04；重复 04 留作诊断，不重复加权。
- 相似度沿用 `1 - median(slot→目标) / median(配对04→同一slot目标)`，分母低于 `0.25 ΔE00` 输出空值，负值保留。按配方和 24 个 15° 扇区输出，保留 ΔE00 中位数、p90、阈值占比、模型误差、不支持色块与覆盖缺口。扇区来自实拍 RAW 的 D65 场景色相，沿用 `measure.py`，不把色卡名义 Lab 扇区冒充固件 CbCr 扇区。
- 01/02 继续用 GR III 相对迁移目标与固定 0 EV，另外保留 ±0.3 EV 敏感性；03 用原有 GR IV HC 插值参考；05/06 用原有官方 Fuji LUT。模型和目标均带原有来源与支持域限制。04 是控制，不能把其条件反演得到的近零误差当作原机色彩保真度。
- 漂移比较每单元最早与最晚的 04 第 1 页共同有效锚点。跨页一致性比较六页同名锚点的原始读数，同时展示去除页公共 EV 后的差异，不修改评分数据。缺帧、缺页、锚点不足或曝光/白平衡变化时输出 `unknown`。

### 实际运行结果

| 检查 | 结果 | 证据目录，均在 `local/runs/` 下 |
|---|---|---|
| 六页 × 4 个基础场景 | 24/24 识页，最大 JPEG 通道误差 `0.538432/255`，最大几何误差 `1.608957 px`。 | `selftest-geometry-12-r2`、`selftest-geometry-34-r2`、`selftest-geometry-56-r2` |
| 六页组合干扰 | 6/6 识页，σ=10，透视、轻微旋转、暗角、噪声、全屏缩放/刘海留黑，再叠加类摩尔纹与闪烁条纹；最大 ROI 码值误差 `1.059/255`。 | `selftest-stress-r1` |
| 强制外白框回退 | 基础场景 6 次、组合干扰 6 次，全通过识页、最大 `5 px` 几何误差与 `3/255` 取样容差。基础场景回退最大几何误差 `0.458184 px`。 | 上述几何与 stress 目录 |
| 真正写出再解码的合成 DNG | 116 块全部有效，RAW 最大误差 `0.000180855`，JPEG 最大误差 `1.489282/255`；容差分别 `0.008` 与 `3/255`。 | `selftest-signal-r3` |
| 干扰、饱和与页码 | 59 项通过。摩尔纹与闪烁各标出 116 块，亮带标出 9 块；RAW 注入饱和比例为 1 并被排除。另含两张白页、48 个单比特纠错、3 个双比特拒绝、文字与机器码冲突拒绝。 | `selftest-signal-r3` |
| 六槽评分适配 | 10 项通过，六槽各输出 24 扇区。04 为 696 个有效块，01/02/05/06 各 232，03 为 160；03 的 72 块按旧目标支持域排除。由同一引擎生成的数据与模型中位差小于 `0.000009 ΔE00`，仅证明适配一致。 | `selftest-scoring-r2` |
| 漂移与均匀性夹具 | 缺少尾帧时为未知；注入 `0.08 EV` 漂移后检出；单锚点跨位置注入 `0.3 EV` 后检出差异。 | `selftest-scoring-r2/synthetic_stability.json` 与 `selftest.json` |
| 旧屏幕卡 | `R8051198` 至 `R8051204` 共 7 对，全部通过 DNG 解码、元数据与配准。没有调用新版识页或评分。 | `selftest-real-r2` |
| 旧 DIOPTIX | `R8051207` 至 `R8051213` 共 7 对，全部找到 24 块并通过 RAW 灰阶与朝向。 | `selftest-real-r2` |
| 完整 CLI 子进程 | 白页、04 第 1 页、漂移重拍共 3 对合成输入，成功导出全部 JSON/CSV/HTML；明确标 `partial`，拒绝覆盖旧 run，验证 37 张首尾编号映射，共 10 项通过。 | `selftest-cli-r4` |
| 真实目录自动分类 CLI | 7 张全部自动识为 DIOPTIX，CSV 168 行，其中 152 块有效；其余保留 JPEG 剪裁或疑似摩尔纹标记。无人工彩色槽号，评分明确为 `unassigned`。 | `cli-real-physical-r2` |

几何取样真值来自已知前向模型与真实单应矩阵，待测流程只得到图像，不得到几何提示。基础场景的目标不含噪声；组合干扰的真值包含已知 JPEG 周期污染，验证的是受扰 ROI 的读数恢复，不能解释为恢复了无干扰颜色。质量检测随后会排除可疑读数。

已查看合成屏幕卡和真实 DIOPTIX 的叠加框。T3 原生 `html_preview` 在 728 px 宽度检查最终质量页，内容高 2424 px，控制台无错误。详细 JSON 已折叠到页尾，首屏展示评分状态与漂移简表。证据为 `local/analyzer_html_preview.json` 及 `selftest-cli-r4/analysis/quality.html`。

环境为系统 Python `3.14.7`、numpy `2.4.3`、scipy `1.17.1`、Pillow `12.2.0`，所有 Python 命令均用 `-I -B`。未安装 rawpy 或其它依赖。

## 推断

- 外白框在细棋盘被模糊掉后仍保留低频结构，配合独立页码读取，比再次强制数 BL 格子更适合本色卡的回退路径。强制回退已经过合成验证，真实成功率仍待新版照片。
- 质量标记和漂移门限是拍摄重检提示。频谱峰只能说明疑似周期结构，不能证明 PWM；跨位置锚点差异也混有镜头暗角、视角、曝光与图像相关的屏幕响应，不能单独归因于显示面板。

## 未知

- 本轮没有新版实拍，尚不能报告用户实际 01/02/03/05/06 的相似度、三单元真实识页率、真实摩尔纹/条带的漏检误报率，或真实屏幕均匀性。
- 已核实 50mm 的 LensModel 自动识别；28mm 与 MOUNT 的真实 EXIF 字符串尚未核实。两者可用 manifest 明确单元，MOUNT 的镜头与镜头环光圈另记备注。
- 选择器字节只证明原生模式。`1` 无法区分 01/02/04/05/06；`3` 仅按本轮六配方约定推断为 03。EXIF 不能证明实际加载的 DAT，默认表和模型沿用 `measure.py`，不同表需明确传 `--table`。
- JPEG 沿用原评分器的 sRGB 解释。已有模型仅在 A12 50mm 的 ISO 200/1600 校准；旧 DIOPTIX 的 ISO 800 只验证读取和几何，不证明色彩模型已校准。实体卡仍要求既有 6×4 朝向与足够成像面积，不把有限旧样片当作任意朝向识别保证。

## 产出文件

| 新文件 | 用途 |
|---|---|
| `analyze_chart_v2.py` | 唯一正式运行入口，配对、manifest、元数据、取样、导出和质量页。 |
| `analyzer_geometry.py` | 页码双证据、白页、外白框定位回退与单应细化。 |
| `analyzer_scoring.py` | 原闭环目标/模型的薄适配，配方/扇区 CSV 和锚点诊断。 |
| `analyzer_runtime.py` | 卷与路径边界、冻结辅助副本、哈希和输入一致性。 |
| `analyzer_selftest.py` | 前向模型、合成 DNG、信号、真实旧数据、评分和 CLI 自检。 |
| `ANALYZER_USAGE.md`、`analyzer_manifest.example.json` | 使用命令、交换字段、首尾编号及逐帧清单模板。 |
| `ANALYZER_REPORT.md`、`ANALYZER_SHA256SUMS` | 本报告和全部本轮新增文件的哈希，清单自身除外。 |
| `local/analyzer_baseline.json`、`local/analyzer_validation.json`、`local/analyzer_html_preview.json` | 封存输入、汇总核验与原生 HTML 检查证据。 |
| `local/vendor/`、`local/vendor_manifest.json`、`local/runs/` | 私有辅助副本、所有测试与真实旧数据的输出；早期验证 run 保留。 |

## 复核命令

先核对交付物。下列命令只读取文件：

```bash
cd /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/chart_v2
shasum -a 256 -c ANALYZER_SHA256SUMS
shasum -a 256 -c SHA256SUMS
```

完整重跑使用新名称，不覆盖本轮证据：

```bash
cd /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh
python3 -I -B research/chart_v2/analyzer_selftest.py --part all --out research/chart_v2/local/runs/selftest-review
```

解析用户导入的新照片仍只需报告开头的一条命令。所有取样、检测、评分和报告输出均在该 run 内完成。
