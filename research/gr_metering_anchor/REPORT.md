# GR 测光中灰与 01、02、03 的锚点

现有资料不足以支持重锚，建议暂时保留 01、02、03，补一组点测灰卡。没有找到一张能确认“GR III 或 GR IV 在零补偿下，点测这块灰”的照片。

若假设 GXR 和 GR 在应用各自 BaselineExposure 后具有相同的测光中灰量，GR IV 的条件估计是自身 Standard 118 点上方 **+0.565 EV**，Standard 约 **144 码**。GR III 的同一计算约为 +0.557 EV。这是假说结果，不能当作已量到的 GR 测光目标。

用于后续验证的粗敏感范围取 −0.3 至 +0.9 EV，对应 GR IV Standard 约 105 至 160 码。它覆盖下文互不等价的假说与场景权重的不确定性，不是统计置信区间，也不是已证实的上下界。现有证据连应提亮还是压暗都未判明。

## 1. 本轮读了哪些帧

在指定共享仓库中只写本目录，临时数据只写 `/tmp/gr_meter/`。首次写入前，`diskutil info /Volumes/Workspace` 确认卷已挂载、可写、APFS，UUID 为 `14BE04EB-AF49-497E-B36A-B078B2F7C5E8`，并运行了 `df -h`。首先创建本目录 `.gitignore` 的 `local/` 规则，随后用 `git check-ignore` 验证。

共找到 42 个既有 DNG 路径，其中一份论坛 DNG 是逐字节重复件，得到 41 个唯一 DNG。34 个属于本题的 GR III、GR IV 和 GR IV HDF；另有 1 个 IIIx 和 6 个 2013 GR 作旁证。此外读取了两张既有官方 GR IV JPEG。没有下载新的 RAW、JPEG 或固件。

每个唯一 DNG 都重新完整解码，C 解码器与独立 Python 前两行校验的差异均为零。统计每隔 8 个传感器像素抽取完整 RGGB 四元组，记录分位数、均值、裁切和中央区域。它们是抽样 RAW 统计，不是全像素精确直方图。每帧原文件 SHA-256 在解码前后相同。

逐帧曝光程序、曝光模式、测光、EC、BV、SOS、REI、DR、RAW 统计和场景假设都在 [逐帧表](local/frame_table.md)、[完整 TSV](local/frame_table.tsv) 与 [逐帧 JSON](local/frames.json)。[缩略图联系表](local/contact_sheet.jpg) 只用于识别场景，未公开照片。

| 帧组 | 数量 | 曝光和测光记录 | DR 与限制 |
|---|---:|---|---|
| A 高对比黑白 | 1 | S，ISO 100，1/30 s，f/5，EC 0，多分区 | 有效 DR 关，菜单字节为 Auto；窗边地砖明暗悬殊。 |
| A 正片 | 1 | S，ISO 100，1/30 s，f/14，EC 0，多分区 | 有效 DR 关；天空白云不是均匀灰目标。 |
| A 负片 | 1 | A，ISO 200，1/500 s，f/4.5，EC 0，多分区 | 有效 DR 开；店铺立面反射率未知。 |
| B 六模式 | 6 | ExposureProgram=1、ExposureMode=1，ISO 320，1/10 s，f/2.8，EC 0，多分区 | DR 开，菜单字节为 On；简报称 P，与文件标签冲突。六帧是一个玩偶场景，不能计作六次测光标定。 |
| 额外投稿 R0000097 | 1 | ExposureProgram=3、ExposureMode=1，ISO 500，EC −0.7，多分区 | 标签解释有冲突，DR 开；阴天屋顶与亮天空，无外部 JPEG。 |
| 论坛 G4000030 至 32、G4000048 至 57 | 13 | 全部 ExposureProgram=1、ExposureMode=1，EC 0，多分区 | 6 张 DR 开，7 张关；咖啡馆、灯、花、教堂和街景。 |
| 论坛 GR002809 至 17 | 9 | 全部 ExposureProgram=1、ExposureMode=1，EC 0，多分区 | 2 张 DR 开，7 张关；GR002813 的两个 DNG 路径是同一文件。 |
| bastibe Target | 1 | P，ISO 100，1/500 s，f/5.6，EC 0，中央重点 | DR 有效关闭；同一 RAW 生成三张模式 JPEG。 |
| Have Camera Will Travel GR IV | 1 | A，ISO 100，1/640 s，f/2.8，EC 0，多分区 | DR 关；晴天海边，仅有 DNG 及内嵌预览，无灰卡。 |
| IIIx 与 2013 GR | 7 | 已读取完整元数据及 RAW 统计 | 不把其他机型借用的 118 点或暗角模型用于 III、IV 结论。 |
| 官方 GR IV 正片、负片 JPEG | 2 | 正片 EC −1，负片 EC −0.7；没有对应 RAW | 正片 DR 关、负片开；高低键等也有改动，不能作 Standard 测光标定。 |

35 个现代 GR DNG 均为 `SensitivityType=1`，SOS 数值等于 ISO；REI 和 ISO Speed 独立标签缺失。标准 EXIF `BrightnessValue` 也全部缺失。GXR R8051188 的该敏感度种类标签缺失，因此不能仅凭 EXIF 声称两机都按同一种 SOS 标定规则工作。[EXIF 字段定义](https://exiftool.org/TagNames/EXIF.html) 支持这些枚举的解读。

MakerNote `0x0017` 与 EXIF 测光记录一致，现代 GR 中只有 bastibe 为中央重点，其余为多分区，没有点测。`0x0069` 第一字节记录有效 DR 开关；第二字节按既有 Pentax 定义解读为 1=On、2=Auto。GR IV 菜单含义仍属于跨机型字段推断，原始短记录保留在本地。[Pentax 字段定义](https://exiftool.org/TagNames/Pentax.html) 是解读依据。

35 帧都有 146 字节的 `0x0206` AEInfo，但现有解析器只认识其他长度的 Pentax 布局。本轮没有把其中任意字节命名为 BV 或 AE 目标。完整记录只留在 `local/`。

M 标签本身也不能证明测光未参与。可能有一次按压 AE、自动 ISO、按表手动设定或重新构图；这些操作没有现场记录。它们共同留下的是曝光结果，不是可逆的 AE 日志。

## 2. 场景统计为什么还不能给出测光锚

本轮沿用 `gr4_modes` 的 RAW 定义。`c` 已减黑位并除以白位范围，`n` 为 AsShotNeutral。

```text
u0 = (cR/nR + 2cG/nG + cB/nB) / 4
u  = u0 × 2^BaselineExposure
u_c = u × 既有暗角补偿模型，画面中心的增益为 1
delta_GR = log2(u_m,GR / u_118,GR)
```

为每一帧给出条件估计时，假设相机的多分区测光可由白平衡后、暗角补偿后的场景算术均值代替，再减掉 EXIF EC。中央 60% 宽高窗给出另一种权重。相机的真实空间权重、颜色权重和高光保护不满足这个已知模型，故这些数不能直接叫作 AE 目标。

34 张目标机型的整图代理值从 −0.686 到 +2.218 EV，相对各自参考 118 点计算。高值主要来自亮天空、教堂和浅色建筑；有灯、彩色花束和深阴影的场景又给出另一种结果。不能把这个分布的平均值当作 GR 的中灰标定。

仅在 bastibe 同一张 RAW 内，整图均值代理为 +1.115 EV，中央窗为 +0.187 EV，中心小圆为 −0.548 EV。未知测光权重造成的差别远大于所讨论的约 0.38 EV。这是本线的死路：帧的 RAW 统计可测，测光时所认定的中灰量不可由它唯一反推。

旧 `gr4_modes` 曲线结果在本轮作为既有输入使用，没有宣称重新拟合它们。它们的快照和 SHA-256 在 [输入记录](local/input_sources.json)。论坛来源见 [原分析的来源说明](../gr4_modes/REPORT.md)。

## 3. bastibe 色卡能确定的数

本轮从原 DNG 和三张完整 JPEG 重新读取了六灰 ROI。D4 的 Standard 平均编码亮度为 **114.84**，正片为 99.12，负片为 127.66。Standard 六灰两端为 36.87 和 211.56。完整六灰的 RGB、亮度、标准差、RAW 值和 ROI 坐标留在 [bastibe_greys.json](local/bastibe_greys.json)。

三张 JPEG 都记录 P、中央重点、EC 0、ISO 100、1/500 s、f/5.6。Standard 和正片固件为 1.60，负片 JPEG 为 1.71。它们属于同一 RAW 的机内显像，不是三次独立测光。

[作者在固定提交的说明](https://raw.githubusercontent.com/bastibe/Darktable-Film-Simulation-Panel/d6effd55cf37ce208c24cf8d072ac14028ca289b/README.md) 写明侧向正午日光、用白纸设白平衡、机内转换不同模拟。作者没有说明点测 D4。画面中的色卡只占中央一部分，周围大面积白纸会影响中央重点测光。因此 114.84 可以说明“这次曝光的 D4 接近 118”，不能证明“GR 必把点测中灰放在 118”。

## 4. BaselineExposure 只支持条件计算

GXR 的本轮工作锚为 `u_m=0.10250885`，原生 row 5 在约 420 输入码输出 137.3。GXR 本身的原生 JPEG 链没有乘 DNG 的 +0.3 EV；这里乘它，只为检验跨机型的共同量假说。

GXR 的 118 点为 `320/4095`。直接 RAW 比例给出 +0.39154 EV。任务沿用的约 +0.38 EV 来自富士模型减去固定截距后的 +0.381923 EV。本报告比较 GR 的 RAW 比例时使用前一个约定，两者相差不到 0.01 EV。[GXR 测量报告](../um_measurement/REPORT.md) 给出了这两个量的出处。

[Adobe DNG 规范 1.7.1 的 BaselineExposure 条目](https://raw.githubusercontent.com/Autoenhance-ai/adobe-dng-sdk/main/DNG_Spec_1_7_1_0.pdf) 定义的是 RAW 转换器曝光控制的默认零点，不是机内 AE 常数。本轮读取已有规范副本的印刷页 36、37，没有下载新文件。

### 4.1 假设两机的 BE 后测光中灰量相同

```text
共同量 K = 0.10250885 × 2^0.3 = 0.12620320
GR IV 118 点 = 0.08532166
delta_GR_IV = log2(K / 0.08532166) = +0.564765 EV
```

该假说给 GR IV Standard 约 143.86 码。GR III 色卡的 118 点为 0.08577678，同一假说给 +0.55709 EV。仅改变已有低 ISO 118 点，GR IV 条件结果约为 +0.53 至 +0.58 EV，GR III 约为 +0.53 至 +0.63 EV。这些窄范围只表示曲线与样本差异，没有包含“共同量假说是否成立”的误差。

以 DR 关的 BE −0.505966 和 B 的 DR 开、BE +0.488342 计算，假说要求的 GR IV 测光 RAW 分别为 0.17922 和 0.08996，后者约为前者的 0.502 倍。已有曲线的 118 点在不乘 BE 的 RAW 上分别为 0.12116 和 0.06082，也近似减半，渲染记账一致。

这不是一次实拍的 DR 切换测光验证。现有帧没有控制同一灰卡、同一 ISO、同一测光构图来切换 DR；而且另一个假说也能通过同样的记账检查。

### 4.2 假设两机在 DR 关时的未缩放 RAW 中灰相同

若 GR IV 的测光 RAW 也是 GXR 的 0.10250885，乘 GR 的 −0.505966 后约为 0.07219。相对 118 点得到 **−0.241 EV**，Standard 约 **107.21** 码。DR 开时再让 RAW 降到约 0.05146，同样能维持 BE 后结果。

两种规则都不违反现有 DR 曲线，却把 Standard 中灰预测成 144 与 107。BaselineExposure 本身不能选出哪条规则正确。更不能直接把两机 BE 相差约 0.806 EV，当作 GXR 配方应移动的量。

高 ISO 还有例外。论坛 GR IV 的 DR 开帧 BE 约为 +0.406，GR III 的约为 +0.306，并非一律 +0.49。没有据此外推统一的 DR 或 AE 修正。[逐 Standard 帧计算](local/baseline_per_standard_frame.json) 保留了全部可用 118 点与这些差异。

## 5. 公开资料与固件线索

[GR III 规格](https://www.ricoh-imaging.co.jp/english/products/gr-3/spec/) 和 [GR IV 规格](https://www.ricoh-imaging.co.jp/english/products/gr-4/spec/) 都把感光度标为 Standard output，并列出多分区、中央重点、点测、高光重点四种测光。[Imatest 的敏感度测量说明](https://docs.imatest.com/docs/sensitivity_ei) 解释了 SOS 使用接近 118 的参考输出，也依赖处理曲线与已知照度。SOS 标签支持“118 是标准化参考”的假说，不能替代本机的点测实验。

[GR III 手册](https://www.ricoh-imaging.co.jp/english/support/man-pdf/gr-3.pdf#page=65) 的印刷页 63 说明点测只看窄区域，且测光可以与 AF 点联动。印刷页 89 说明低于 ISO 200 时高光校正不起作用。印刷页 52 还说明 M 档的一次按压 AE。这些设置足以解释普通照片为什么不能直接还原一次中心点测。本轮检查的相关条目没有给出 Standard 点测灰卡的 JPEG 数字。

[理光官方作者 Ninzaburo](https://www.grblog.jp/en/article/3555/) 说自己常用约 −0.7 EV 防高光，但有时图像因此过暗，继而比较多分区和高光重点。负补偿习惯确实存在，其目的包括保护高光和选择影调，不能反推中灰固定高了 0.7 EV。

[Kari Post 的 GR III 实拍评测](https://www.karipost.com/blog/2020/09/06/the-little-camera-that-could-an-uncomprehensive-review-of-the-ricoh-gr-iii/) 则常在 RAW 拍摄中加 +0.3 至 +1 EV。[Digital Camera World 的 GR IV 评测](https://www.digitalcameraworld.com/cameras/compact-cameras/ricoh-gr-iv-review) 肯定高光重点对明亮户外场景的作用，但所查段落没有受控灰卡码值。用户习惯不能提供一个统一的 GR 校正量。

公开测量检索的死路也保留了。以 GR III、GR IV 加 metered grey、gray card、118、measured ISO 检索，未取得带完整设置的点测灰卡 DNG 与 Standard JPEG 数值。结果中的旧 GR、GR Digital 和白平衡灰卡讨论未当作 III、IV 标定。DPReview 的 GR IV 评测只返回 `Just a moment...`，未使用正文。[GR IV 官方手册](https://www.ricoh-imaging.co.jp/resources/english/support/man-pdf/gr-4_en.pdf) 被远程阅读器以 `Content length is too large: 10485761+` 拒绝，按本题的大文件限制没有另行下载。旧 CIPA PDF 地址不可读，2020 草案目录也没有给出该条目的下载文件。完整 URL 与失败记录在 [公开资料记录](local/public_sources.json)。

固件线只检查已有 GR III 2.10 和 GR IV 1.11 解码镜像，前后 SHA-256 均与既有清单一致。静态确认了 `AeAlgorithm.cpp` 的字符串及窄范围 ARM 引用：GR III 字符串 VMA 为 `0x53c20d94`，引用附近为 `0x5347b370`、`0x5347b3bc`；GR IV 为 `0x53eb5310`，附近为 `0x53674c14`、`0x53674c90`。这些位置落在分配、清零和断言，未识别出灰阶目标及单位。

既有 GammaTuning 的 118 是阶调生成锚，不能据此命名为 AE 中灰。固件线到此停止，没有继续展开整个 AE 调用图，也没有运行目标代码。[静态结果](local/static_ae.json) 与相邻反汇编均在 `local/`。

## 6. 对配方的建议和最小补拍

建议是“需要更多数据，暂保留现行行”，不是已证明两机测光相同。01、02、03 的 JPEG 域转移仍有依据，缺的是 GR 自身测光锚。富士 LUT 的 117 设计点不能直接充当 GR 测光目标。本轮不推荐非零平移，因此没有生成移位候选行，也没有构建 DAT。[敏感度计算](local/anchor_sensitivity.json) 只列假说，不含可部署行。

最小新增数据是同一台 GR III 或 GR IV 的 **1 张 DNG 加 1 张 Standard JPEG**。给机主的拍摄要求是：

1. 用均匀、无反光的哑光灰卡覆盖整个点测区域，最好铺满画面。避免卡面阴影、强反光和混合光。
2. 设 A 档、f/4、ISO 100、EC 0、中心点测，关闭 AE 与 AF 点联动，不锁曝光后重新构图。
3. 设 Standard 默认滑杆，固定白平衡，关闭高光校正、阴影校正、HDF 和滤镜。保存原始 DNG 与机内 sRGB JPEG，不经过编辑或聊天软件转码。
4. 随文件记录机型、固件，以及上述设置确已采用。若方便，再重复拍一组检查测光重复性。

这两份文件就能直接测 S_GR，并由现有 Standard 曲线反推相对 118 点的 EV。若愿意再补三张 JPEG，用同一 RAW 在机内生成默认 Positive、Negative、Hi-Contrast B&W 即可，不必让每种模式重新测光。要独立检查 DR，再加 ISO 200 下 DR 关、开的两组 Standard DNG 与 JPEG，其他条件固定。

若新数据支持非零位移，再按已有 v3 重铺方法生成 01、02、03 的候选行、逐点误差和六灰预测，并把所有源字节和派生数组留在 `local/`。本轮的“静态确认”不代表这些曲线已在 GXR 上验收。

## 7. 时间预算、复跑与交付

| 证据线 | 时间上限 | 结果 |
|---|---:|---|
| 逐帧 EXIF、MakerNote 与 RAW | 25 分钟 | 41 个唯一 DNG 解码和统计；无合格点测灰卡，AEInfo 未知。 |
| bastibe 色卡 | 10 分钟 | 六灰重测；曝光目标没有现场见证。 |
| BaselineExposure | 10 分钟 | 两个不等价规则均可解释 DR 记账，不能当作证明。 |
| 公开资料 | 20 分钟 | 查到测光机制和相反的补偿习惯；未取得合格中灰测量。 |
| 可选固件线 | 8 分钟 | 两个镜像、窄范围引用；未定位 AE 目标。 |
| 报告与校验 | 15 分钟 | 检查输入哈希、忽略规则、JSON 和交付清单。 |

各线交错执行，上限不等于实际耗时，不能将它们相加当作本轮用时。41 帧的解码及统计脚本实测合计约 109 秒；总墙钟时间另记在 `metrics.json`。[证据台账](local/evidence_ledger.json) 包括每条死路。

从仓库根目录复跑，所有生成文件仍只进本目录和指定临时目录：

```sh
python3 -I -B research/gr_metering_anchor/local/analyze_frames.py --inventory
python3 -I -B research/gr_metering_anchor/local/analyze_frames.py --start 0 --stop 41
python3 -I -B research/gr_metering_anchor/local/build_tables.py
python3 -I -B research/gr_metering_anchor/local/static_ae.py
python3 -I -B research/gr_metering_anchor/local/calculate.py
python3 -I -B research/gr_metering_anchor/local/verify.py
```

现有原图、论坛样本和固件位于原仓库或既有 `/tmp` 目录；这些文件是复跑前提，未复制为公开交付。`local/inputs/` 冻结了本轮使用的小型曲线与行数据。公开文件只有本报告、[metrics.json](metrics.json) 和 `.gitignore`。私有材料的逐文件 SHA-256 见 [local/SHA256SUMS](local/SHA256SUMS)，校验结果见 [local/verification.json](local/verification.json)。没有 Git commit，没有接触相机或 SD 卡，没有改写其他 worker 的目录。
