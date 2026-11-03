# GR 机内 RAW 显像测试卡

已完成离线注入、GR III 三风格预测、JPEG 自动对位、径向校正和目标回填工具。可外发的是两张以 bastibe 公共 GR III DNG 为容器的合成卡。GR IV 仅提供注入工具，验证成品留在 `local/`。本轮没有真机或存储卡验收，不能据此认定 GR III、IIIx、IV 都会识别。

## 1. 交付和复现

从仓库根目录运行。所有 Python 命令使用隔离模式，并禁止写字节码。

```sh
python3 -I -B research/gr_incamera_dev/run_all.py
python3 -I -B research/gr_incamera_dev/verify.py --record
```

`run_all.py` 重建默认的两份 GR III 卡、一份本地 GR IV 卡、预测、测试和三份校验和。它只使用本机已有的 NumPy、SciPy、Pillow、imagecodecs 和 C 编译器，不安装依赖、不联网。完整环境版本保存在 `local/verification.json`。

主要文件如下。

| 文件 | 用途 |
|---|---|
| `inject.py`、`tiff_io.py`、`sof3.c` | 原位写入 RAW、维护全部 IFD、编码无损 JPEG、替换预览。 |
| `chart.py` | 生成原生 RGGB 色块、灰阶、径向探针和定位码。 |
| `predict.py` | 使用已有 GR III 冻结前向模型生成三种风格的预测 JPG。 |
| `analyze.py` | 从 JPG 定位、取样、估计径向增益，输出 `gr-relative-targets/1`。 |
| `export_targets.py` | 把相对目标绑定到真实请求及其 04 基准，输出 `closedloop-targets/1`。 |
| `test_codec.py`、`dry_run.py`、`verify.py` | 编码往返、完整干跑、封存及复核。 |
| `HELPER_ZH.md` | 可直接转发的中文协助说明。 |

给协助者的文件位于 `artifacts/gr-incamera-dev/`：`GR3_colour.DNG`、`GR3_tone.DNG`、`给机主的说明.txt` 和 `SHA256SUMS`。两个 DNG 都保留原容器的文件长度，压缩数据后的原分配空间清零，没有遗留原照片 RAW 或三个已知预览的尾部数据。它们是普通 DNG 文件，不是固件文件。

这两张默认 GR III 卡的 SHA-256 为：

```text
65cba60d66031bebe9e9edf226f58646f24b8c572557b703139ad05afa2a33e7  artifacts/gr-incamera-dev/GR3_colour.DNG
dcf103338a3834db902d58a082ddac39e6f21d57d2c420a4c2132c6145fb1694  artifacts/gr-incamera-dev/GR3_tone.DNG
```

外置卷已核对为可写 APFS，UUID 为 `14BE04EB-AF49-497E-B36A-B078B2F7C5E8`，并运行了 `df -h /Volumes/Workspace`。写派生数据前先创建了两处 `.gitignore`，以 `git check-ignore -v` 确认生效。本任务的写入全部在两个新目录内，没有接触其他卷、相机或卡，没有 Git 提交。

封存时发现范围外有并发变动：新增 `research/gr_pairs/` 文件，既有 `decisions.tsv` 哈希也改变。没有更新起始快照或回滚这些内容。本任务实际读取的输入哈希均未改变。`verify.py` 默认要求产物、忽略规则和所有只读输入通过，并单列范围外状态；`--strict-workspace` 还会要求整个范围外工作区与起始快照完全相同，当前并发工作区不满足这一项。

## 2. 色块定义与覆盖

先读取了 `artifacts/downloads/calib16/16位校色DNG/使用说明.md`。其中 64³ 布局的级值为 `round(i*65535/63)`；这个容器身份和线性 ProPhoto 坐标不能直接用于 GR。当前卡重新从 GR 的原生 ColorMatrix、AsShotNeutral、黑白电平和 RGGB 相位建立 RAW。

采用 DNG 双光源矩阵的倒色温插值，保留 AnalogBalance 和有效 CameraCalibration，再把 AsShotNeutral 对应白点适应到 D50。目标场景色先定义在 D65 Lab，经 XYZ 和色适应转换后，用相机到 XYZ 矩阵的逆矩阵得到未白平衡的相机 RGB。该数学链复用 `gr_evalsets` 中现有的纯色彩函数；矩阵及每块数值只存入忽略目录。

- 灰阶卡有 388 个主灰阶，含黑、近黑、对数暗部、线性中高光和名义白端点，另有 96 个中心参考与 160 个径向探针，共 644 块。这里的中性是 AsShotNeutral 比例的原生 RAW，不是三个 CFA 通道取相同码值。
- 色彩卡有 35 个色相、5 个明度、4 个饱和度，共 700 块。红、品红、蓝、紫使用更密的角度。另有 18 块肤色、植物、天空与常见场景色，96 个中心灰阶参考、160 个径向探针，以及 12 个跨半径同色留出块，共 986 块。
- 每块为 88×88 RAW 像素，中心 ROI 为 32×32，距色块边缘 28 像素，格距 104。RGBA 之类的显示像素不参与 RAW 构造，两块绿色 CFA 平面分别按自己的黑电平量化。
- 主样本限制在半对角线归一化半径 0.65 以内。肤色及重点红、蓝、紫、品红排在更靠中心的位置。四个有方向编码的方形标记用于 DNG 裁切坐标到 JPG 的对位，JPEG 中缺任何一个都拒绝猜测。

这不是把 262,144 个微小块硬塞进一张相片。大块中心要隔开去马赛克、锐化和降噪影响，因此用两张卡覆盖阶调和颜色。跨半径留出块只校验空间校正，不进入目标训练。

### 可达域筛选的实际含义

先要求目标位于线性 Rec.2020 D65 的非负、有界原色组合内，再要求 ColorMatrix 反算的三个相机通道均非负，且不超过归一化 RAW 的 0.96。各色相与明度先二分搜索联合色域的最大色度，再取其 0.20、0.45、0.70、0.95。灰阶单独覆盖白端点。Rec.2020 比 sRGB 宽，这批主色块包含 sRGB 外的颜色。

边界搜索中，超出 Rec.2020、反算负相机响应及超过 RAW 余量的候选均被剔除。实际计数与边界值保存在卡清单的 `boundary_checks`，没有把超界值夹回可用区伪装成原目标。肤色等名称是合成场景色定义，不是实测反射光谱。

ColorMatrix 只有三刺激值近似，不能恢复 GR 传感器的光谱灵敏度。上述规则提供一个保守的可用集合，不能证明它等于真实 GR 的完整光谱可达域，也不能保证每个点都能由某种 D65 照明下的自然表面反射产生。非负 Rec.2020 原色组合有物理加色解释；相机通道的精确光谱对应关系仍未知。要收紧到实测相机光谱轨迹，需要传感器光谱响应或实测光谱数据。本轮没有编造这项证据。

## 3. 径向增益与对位

半径定义与已有 GR IV 分析一致：距裁切中心的欧氏距离除以半幅对角线，角落为 1。先使用已知的 0.5/0.7/0.85/1.0 半径增益 0.23/0.48/0.75/1.13 EV，在每个 2×2 CFA 四元组上对信号预补偿，黑电平不缩放。因此主色块在预期的机内增益之后接近均匀，而不是把暗角变化误当作阶调。

160 个径向探针使用 16 种灰，每种在多个方位和半径重复，故意不预补偿。实际中心半径和每块位置随原生裁切尺寸保存，不把“接近 0.93”冒充正好在该半径。96 个参考块靠近中心，覆盖可逆阶调范围。

回读时每种风格分别拟合单调的中性输出曲线，反算探针的有效曝光，再稳健拟合共同标量径向增益。JPG 不直接除以 `2**EV`：工具先通过该风格的中性曲线反算，扣除实际增益与预补偿的残差，再正向映射。截断、平阶、超出参考范围和污染 ROI 均标为不支持，原始配对数值仍保留。

彩色校正还假设“线性色彩级随输入整体缩放，其后为可分离阶调”。12 个同色跨半径留出块检查这项假设；至少 4 对可用，校正后 ΔE00 中位须小于 1.5，p90 小于 3，才能把色彩卡的归一化结果标为可拟合。灰探针要求足够半径覆盖、80% 以上内点和低于 0.06 EV 的内点残差。失败时保留原始同位置相对观测，不输出可信的中心归一化色彩目标。

对位使用四个编码标记的边框和方向，联合拟合单应变换，支持 JPEG 的旋转、缩放和小幅投影变换。每个中心 ROI 检查边界、有效像素尺寸和内部标准差。镜头的非线性几何校正、局部阶调和有色镜头阴影仍需真机数据检验；四角残差本身不能证明整幅图所有像素都已精确对齐。

## 4. DNG 注入与结构保全

已抽查的 GR III 与 GR IV 模板都是 14 位、predictor 1、Pt 0、两个 1×1 分量的 SOF3 单条带。编码器生成合法的 DC Huffman 表、负差值幅度、16 位特殊类别、FF 字节填充及结束补位。原分量 ID、SOF 尺寸和马赛克顺序均保留。

注入只在原分配空间内写入，不重建 IFD，不增加指针，不追加重排数据。只有 RAW 与预览字节、对应长度字段，以及显式选择的已知隐私字段会改变。剩余空间清零。改变范围之外做逐字节比较；IFD 数量、顺序、类型、count、IFD 偏移、外部字段偏移、条带偏移、文件长度、RAW 尺寸、黑白电平、ActiveArea、DefaultCrop、CFA 和 WB 均复核。

当前通用 RAW 分段代码可描述条带与瓦片，但本轮只验收了这两份单条带模板。多条带预览、未知 Opcode、LinearizationTable、非 RGGB、不同精度、旋转裁切或新 JPEG 无法放回原空间时明确拒绝。不能据此宣称已验收所有 IIIx 或 IV 固件变体。

三处预览默认全部替换：IFD0 的 160×120 RGB 缩略图、全尺寸 YCbCr JPEG 预览，以及 MakerNote 中独立的 720×480 JPEG。尺寸、预览指针和色度子采样保持原样，JPEG 质量在原容量内选择。预览是与色块内容一致的 DNG 色度学预览，不宣称它等于机内 Standard。

`--previews keep` 仅用于本地同机容器诊断。它会保留原照片的回放内容，可能让相机显示旧照片、沿用缓存或拒绝不一致文件；不得把这类文件当作完成的公共合成卡。默认外发路径强制替换预览。

本轮合法性证据为有界 TIFF 遍历、完整 IFD 对比、现有 C/Python 解码器、独立 imagecodecs 解码以及所有预览可解码。系统没有 `dng_validate`，未做 Adobe DNG SDK 验证，也没有以电脑通过替代相机识别。

## 5. 隐私与同机容器流程

公共 GR III 版使用用户已核实的 bastibe 放弃版权模板。其下载 receipt 里仍有早期“照片许可未明确”的保守记录，本轮采用本任务给定的已核实授权，没有修改 receipt。原照片 RAW 和三个已知预览都已替换。MakerNote 中机型、固件、成像状态和未知字段保留，不伪造相机显像经历。

GR IV 的 `local/GR4_colour_PRIVATE.DNG` 只用于本地验证，不是可外发的匿名成品。`--privacy known-fields` 中性化下列已知字段，保持长度和 IFD 不变；完整实际改动清单在 `local/cards/GR4_colour_PRIVATE.json` 的 `privacy_fields_changed`。

| 字段组 | 处理 |
|---|---|
| TIFF/EXIF 时间、子秒和时区 | 已识别的文本时间改为中性值。 |
| 标题、Artist、Copyright、Owner、机身/镜头序列和 CameraSerialNumber | 存在时按原类型与长度覆盖。 |
| GPS 子 IFD | 保留 IFD 及版本字段，定位数值和识别文本中性化。两份当前模板只有 GPS 版本，没有实际坐标。 |
| MakerNote `0x0006`、`0x0007` | 日期与时间中性化。 |
| MakerNote `0x001d`、`0x0229` | 已知序列字段中性化。 |
| MakerNote `0x0251` | 机身自定义名称改为中性名称，已检查已知机主名不再存在于此字段。 |

未知 MakerNote 二进制块没有被猜测性清空，可能仍有复制的标识、计数、时间或场景统计。ColorMatrix、AsShotNeutral、黑白电平、机型身份、固件版本、镜头和显像处理状态不做匿名替换，它们可能参与识别或成像。没有证据证明哪些私有字段可以任意改动后仍被相机接受。因此 `privacy_audit_complete=false`，工具禁止把任何 GR IV 或其他机主模板写进外发目录；不会把“已擦几个字段”当作完整匿名化。

首选流程是“私下接收机主自己的原生 DNG → 本地注入 → 保留同机身份及结构 → 私下发回同一机主 → 回传原始 JPG”。这种流程避免了第三方容器归属不匹配，但原文件仍含隐私，不能公开。它也不能在电脑端保证相机一定识别。

```sh
python3 -I -B research/gr_incamera_dev/inject.py \
  research/gr_incamera_dev/local/incoming/机主原文件.DNG \
  --kind colour --privacy same-owner \
  --out research/gr_incamera_dev/local/return/机主原文件.DNG
```

试读成功后再注入灰阶卡。需要同时放两张时，使用两个不同文件编号的自有 DNG，避免同名覆盖及重复编号缓存。输入只读，输出不能与输入相同。工具不会向卡写入。

## 6. 预测与回读

预测直接读取 `gr_evalsets` 的冻结共享中性模型，并逐项确认与 `color_fit_v2/gr_round5` 使用的三种风格矩阵和曲线一致。不执行旧脚本，避免旧脚本把缓存写到其他 research 目录。模板 AsShotNeutral 用于白平衡，模型曝光尺度保持原冻结值；不会再次乘 BaselineExposure 造成重复曝光。额外的径向增益明确标为此次测试的空间假设。

Standard、Positive、Negative 的 JPG、逐块浮点预测与设置保存在 `local/predictions/GR3_tone/` 和 `local/predictions/GR3_colour/`。模型仍缺 MultiAxial、局部阶调和真实去马赛克/锐化/降噪。这些文件只能验证工具路径，不能成为新增真机目标。额外 `hc_bw.JPG` 是带显式标识的玩具黑白函数，只验证分析工具能消费黑白图，不是 GR 高对比黑白预测。

收到机主原图后，用与回传 DNG 哈希绑定的卡清单分析。真实相机入口要求 EXIF/MakerNote 风格身份与命令标签一致、机型匹配且各风格 WB 一致，记录滑块供核对；无色彩配置的非 sRGB JPG 拒绝，带 ICC 的 JPG 先转换到 sRGB。原文件不修改。

```sh
python3 -I -B research/gr_incamera_dev/analyze.py \
  research/gr_incamera_dev/local/cards/机主原文件.json \
  --style standard=research/gr_incamera_dev/local/incoming/标准.JPG \
  --style positive=research/gr_incamera_dev/local/incoming/正片.JPG \
  --style negative=research/gr_incamera_dev/local/incoming/负片.JPG \
  --style hc_bw=research/gr_incamera_dev/local/incoming/高对比黑白.JPG \
  --out research/gr_incamera_dev/local/analysis/机主回传.json
```

没有某种风格就省略它。每种风格分别保存原始中心 RGB、中心归一化 RGB、D50 Lab、ΔLab、色度比、色相差、配准残差、径向模型、裁切与平阶标记。接近无色或黑白输出时不计算无意义的色相差。Standard 截断可能让 Standard 到风格的关系不再单值，因此完整配对始终带已知 RAW 输入；不能把所有样本强塞进一个无条件 3D LUT。

同一 DNG、同一位置的风格与 Standard 配对，消除了跨拍摄曝光不一致，也不需要先确定绝对场景反照率。它没有消除“变换随 Standard 明度变化”的事实；迁移到 GXR 时，中灰锚、白平衡和照明条件仍会影响查询位置。工具始终保留 `metering_anchor_determined=false`。

## 7. closedloop-targets/1 回填

默认分析 JSON 本身就是可供拟合器使用的密集 RAW/Standard/风格配对目标。若要接入现有闭环，提供 `closedloop-target-requests/1` 与真实的 04 Lab 锚，不生成 Nominal04 替身：

```sh
python3 -I -B research/gr_incamera_dev/export_targets.py \
  --analysis research/gr_incamera_dev/local/analysis/机主回传.json \
  --requests research/gr_incamera_dev/local/目标请求.json \
  --anchors research/gr_incamera_dev/local/04锚.json \
  --out research/gr_incamera_dev/local/closedloop_targets.json
```

锚文件使用 `gr-incamera-anchors/1`。其 `frames` 以请求 key 索引，每项必须包含完全相同的 `labels`、`dng_sha256` 和 `lab_by_ev`。01/02 的后者必须有 `-0.3`、`0.0`、`+0.3` 三组真实 04 Lab，03 只需 `0.0`。可运行的结构示例在 `local/dry_run/anchors.json`，它是合成演示，不是 GXR 真值。

回填同时要求目标帧和同槽 04 基准。输出的 slot、标签、DNG 哈希及 EV 行绑定请求，原有消费者不需要修改。色彩采用 round5 的相对 L* 变化、色度比例与色相旋转，低色度和黑白采用明示的 ab 差值。常规查询在已测 Standard D50 Lab 中取四近邻，最近距离超过 8 ΔE76 时标为不支持，不无界外推。EV 行用各自 04 锚重新查询，不复制 0 EV 充数。

此插值约定不是新的绝对测光校准，也没有宣称解决了跨相机光谱匹配。不同模型、白平衡或来源的目标不应混用。预测和真机目标禁止混合导出。所有输出保留 `firmware_ready=false`、`deployable=false`。

## 8. 电脑验证与证据分层

编码器通过 32 组小图的三解码器逐值往返，覆盖 2/8/14/16 位、单/双分量、零值、最大值、极值交替和随机数据，包含 FF 填充与 16 位特殊差值。三份最终 DNG 从文件内重新提取 SOF3，用现有 C 解码器和独立解码器检查全部 RAW 样本，并核对设计 RAW 哈希。

完整干跑经过最终 DNG 解码、模型出 JPG、保存后的 JPG 再读取、自动对位、提色、径向拟合、相对目标、回填导出及原有 `closed_loop.Targets` 的构造和消费入口。六个请求条目含各槽 04 基准，20 项消费者读取/拒绝检查通过。另验证 90° 旋转、缩放、投影变化、缺标记、缺基准、错误 DNG 哈希、缺 EV 行与 GR IV 误外发拒绝。

`local/dry_run/summary.json` 保存逐项测量和门槛。JPG 回读对比的是同一个冻结模型的浮点块预测，误差包含 8 位量化、JPEG 和 RAW 量化，不是“模型与真机的误差”。径向干跑还把真实增益故意放大 15%，分别检查估计误差和扣除后色块误差，避免仅证明先验与自身抵消。

灰阶主块的三风格回读 ΔE00 中位为 0.05–0.07，p90 为 0.13–0.16；色彩主块为 0.23–0.27，p90 为 0.51–0.62。旋转缩放后的全部取色 p90 小于 0.04 ΔE00，投影变换后的中心位置误差最大小于 2 像素。15% 径向扰动的增益恢复误差小于 0.03 EV，三种风格扣除后的主色块中位误差均下降。小图编码测试全部使用合法像素序列；没有对 DNG 结构或相机做模糊测试。

证据边界如下。

| 层次 | 本轮状态 |
|---|---|
| 原始输入只读、Git 范围、忽略规则、哈希 | 由 `verify.py` 复核。 |
| TIFF/SOF3/IFD、预览、最终 RAW 样本 | 电脑端结构和逐值验证通过。 |
| 模型预测、自动对位、径向校正、回填消费 | 合成干跑通过。 |
| GR III / IIIx / IV 识别测试卡并机内显像 | 未运行。 |
| 回传数据改进 GR/GXR 模型或固件 | 尚无新的真机 JPG，未验收。 |

原有 bastibe 三种 JPG 的 MakerNote 已抽查，风格身份与 Standard/Positive/Negative 一致，`0x0062` 均有显像过程值，记录在 `local/bastibe_style_metadata_spotcheck.json`。没有把本轮合成预测的 JPG 伪装成这些真机文件。

## 9. 不识别时的尝试顺序

1. 先确认协助者原始 DNG 能在同一机身正常显像，保留原文件名和原 DCIM 子目录。公共 GR III 容器被拒时，优先切换协助者自己的机型、固件和机身容器。
2. 先只试一张色彩卡。两个不同的自有原生 DNG 分别注入两张卡，排除文件编号、同名替换和相机目录缓存。任何操作都先备份，不能覆盖唯一原片。
3. 默认保持所有 IFD 和三处预览一致。若确认是回放预览限制，只在本地同机版本试 `--previews keep`，接受显示旧照片的后果，再观察 RAW 显像是否确实读了新色块。此分支不提供公共成品。
4. 模板布局不受支持、压缩数据放不进原分配空间，或相机仍拒绝时停止。换另一张正常的自有 DNG再注入，记录机型、固件、原片能否显像、回放现象和报错。不要尝试畸形 IFD、假指针、模糊测试、固件修改或卡修复。

未知项包括同机校验、MakerNote 完整性校验、预览一致性校验、文件缓存、私有 RAW 摘要和实际镜头空间处理。当前两个模板没有额外 RAW 摘要字段；未来出现未支持的摘要时不能照此宣称相机可接受。电脑上同构且能解码，并不保证相机愿意显像。

## 10. 这批真机数据能补什么

回传同一张合成 RAW 的多风格 JPG，可补齐现有自然场景里稀缺的红、品红、蓝、紫、高饱和色及密集灰阶，验证 GR III 模型在色卡以外的范围，分离全局阶调、色相/饱和度与空间响应。多明度和饱和度数据能检验只按色相分区是否足够，以及局部或 MultiAxial 行为是否仍有系统残差。

GR IV 的正片目前缺乏完整固件模型，这条路径可直接得到机身渲染目标，不必先逆出固件模型。它还可以在同一套输入上比较 GR III 和 IV 的 Standard 基线与相对风格变化；应分别保存每台机身和各自 WB/DR 条件，不能把机型差异自动视为风格差异。

相对定义避开了绝对测光锚的前置依赖，但不会自动解决跨机型的曝光坐标、白平衡、光谱或截断歧义。最终判断须来自机主发回的原始 JPG。

## 11. 校验和基准

所有校验和清单的路径都以仓库根目录 `/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh` 为基准，不以清单所在目录为基准。

- 公开的 `research/gr_incamera_dev/SHA256SUMS` 覆盖本目录公开源码、文档、忽略规则及交付目录的 `.gitignore`。
- `research/gr_incamera_dev/local/SHA256SUMS` 覆盖全部本地派生文件和忽略交付文件。原始输入单独在 `local/inputs.json` 记录起始 SHA-256，验证时再次读取原文件。
- `artifacts/gr-incamera-dev/SHA256SUMS` 覆盖该交付目录的文件，供发出前校验。校验和文件自身和 `local/verification.json` 不纳入哈希，避免循环依赖；后者每次验证都会刷新。

新增或重建产物后，先验证输入与范围，再用 `verify.py --seal --record` 封存。普通 `verify.py --record` 只检查现有清单，不能自动接受哈希变化。没有照片像素数组、投稿人文件或固件派生数组进入公开源码和报告。
