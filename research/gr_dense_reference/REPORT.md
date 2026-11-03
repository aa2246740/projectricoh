# GR 密集机内显像参考，r1

已生成 4 张主 DNG、1 张先行验收 DNG。主卡共有 8,685 个颜色样本，连同中性、径向与留出控制共 9,825 块。离线 RAW 逐值往返、三处预览、IFD 保全、三风格预测 JPEG 回读和轻微模糊检查通过。机主只需每张原 DNG 显像标准、正片、负片各一次，主会话共 12 张 JPEG。相机识别及真实显像尚未验证，先行小样是强制门槛。

## 覆盖与旧屏幕色环的差别

| 项目 | 本包 | 旧 hue_ring 屏幕设计 |
|---|---:|---:|
| 主颜色点 | 8,685 | 144 |
| 定明度色环 | 120 色相，每 3° | 72 色相，每 5° |
| 明度层 | 12、24、36、48、60、72、84、94 | 45、65 |
| 每个色相、明度的色度层 | 自身边界的 8%、25%、50%、75%、90%、98% | 每明度只取共同上限的 85% |
| 完整色环网格 | 5,760 点，每色相 48 点、每明度 720 点 | 144 点 |
| ≥90% 自身边界 | 1,920 点 | 没有此采样层 |
| 150–270°，含两端 | 41 色相、1,968 点，其中近边界 656 点 | 25 色相、50 点 |
| C*≥40 | 1,379 个预测 Standard 色环点 | 0；两圈 C*=23.17/30.77 |
| 相机原生 RAW 晶格 | 13³ = 2,197 点，三个通道独立变化 | 无 |
| Standard 输出晶格 | 9³ 候选 729，反解接受 728 | 无 |

色环明度、色相和色度均指冻结部分模型的 Standard 输出 CIELAB D65。旧色环数字指屏幕发光设计，两者不是同一物理坐标，表格比较采样密度与范围，不比较实测精度。新色环最大设计 C*=123.80，1,986 点超过旧圈最大 C*。相机 RAW 晶格另有 2,105/2197 点在原生 DNG 比色矩阵下超出 sRGB，生成时没有显示器或 Rec.2020 门槛。公开 coverage.json 给出每个色相、明度和相对色度层的计数；逐块坐标只在 local/。

## 能做什么，不能承诺什么

这套有限晶格补齐约定的全部采样点；“完整”不代表测遍连续色空间、所有光谱、白平衡、ISO、DR、机型和固件。相机响应立方体覆盖黑白归一化通道 0.0005–0.98，留 2% 高光余量，未采字面上的 0 与 1 极端。部分 RAW 组合未必对应自然反射光谱，仍可测试相机数值管线。

它消除屏幕翻拍、摩尔纹、Night Shift 与显示设备色域限制，并让同一 RAW、同一位置的 Standard 和两种风格一起回传。旧 gr_hdfchart 的有效正片 105 块中 86 块、负片 95 块中 77 块没有 Standard 支持；本流程直接索取对应 Standard。相机输出自身的截断仍会发生，截断的 Standard 不能反演成唯一 RAW。

按任务给定的既有测量，密集数据可望让正片接近约 85% 的数据充分时上限；本轮没有测到新的相似度提升。正片从 85% 到 95% 仍受相机引擎与跨机转移桥约束，参考数据不能修复这些限制，也不承诺 95% 正片。负片、Classic Chrome、Classic Neg. 更可能受益于明度与饱和度覆盖；本包只采 Standard/Positive/Negative，CC/CN 仍需各自目标与迁移验证。

已知的是每块写入的原生 RAW 及其最终量化值。Standard 坐标由现有前向模型反解，真实去马赛克、WB、空间校正和完整机内引擎是否落在预测坐标，仍需回传 JPEG 确认。预测器缺少 MultiAxial、局部阶调和真实去马赛克、锐化、降噪；离线预测图绝不能作为新真机训练目标。camera_acceptance=false、firmware_ready=false、deployable=false。

## 交付位置与开发流程

`git check-ignore -v artifacts/gr-dense-reference/probe.DNG` 未匹配规则，只有旧 artifacts/gr-incamera-dev/ 自己的规则生效。因此依照本任务要求，全部数据退回 `research/gr_dense_reference/local/public/`。未在 artifacts/gr-dense-reference/ 写文件，也未改仓库根忽略规则。新研究目录的 .gitignore 精确包含 local/，已用 git check-ignore 确认。

所有五份 DNG 使用指定 bastibe GR III 1.60 公共容器，SHA-256 d41bf7988052a17ac1722d111525b946d1ffc239052d28fca664b00b6cec63b1。原 RAW 和全部三处已知预览均替换，空余分配区清零。公共容器授权依据本任务给定的已核实事实，没有重解释早期下载 receipt。没有读取 GR IV 原片生成变体；可用 inject.py --private-template 在 local/private/ 生成同机主版本，未知 MakerNote 隐私仍不得外发。

机主可直接收到 local/public/ 内五份 DNG、OWNER_ZH_EN.txt 和 SHA256SUMS。R0900001.DNG 为 38 块小样，240×240 色块、64×64 中心 ROI、四个定位标记。小样保留与原模板相同的 31,498,641 字节长度以保全 IFD，因此“微型”指验收内容和操作量，不是更小的字节数。小样只显像 Standard；研究者读回确认后，再做另外四份。

主卡色块 80×80、格距 96、灰缝 16、中心 ROI 32×32，距边缘 24 像素。每张有可见 17 级灰阶、96 个中心参考、160 个未预补偿径向探针、12 个同色空间留出点和四角方向码。底色是中性 0.15 级 RAW；主块采用原型的逐四元组径向预补偿。位置固定随机化，避免色相与画面位置绑定。

采用“一份 DNG 连续保存三种风格 JPEG”，不生成伪造风格元数据的三份 RAW。[Ricoh 官方手册印刷页 100–101](https://www.ricoh-imaging.co.jp/english/support/man-pdf/gr-3.pdf#page=101) 说明 RAW 显像可选择白平衡和图像控制，并保存新 JPEG；据此回到同一原 DNG 重复三次。官方流程支持重复保存的判断不等于这个合成容器已被相机接受。机型不匹配或不识别时停在小样，不要求机主继续整套。

默认滑杆顺序为键、对比、高光、暗部。Standard 0/0/0/0，Positive -1/+3/-1/-2，Negative +1/+1/0/-1，其余适用滑杆为 0。保留原片 WB、增减感 0、sRGB、6000×4000、原片校正设置；HDF 关。短版操作与 5 步 PASS/FAIL 见 OWNER_ZH_EN.txt。

## 离线验证实测

最终五份 DNG 均从文件重新抽出 SOF3，以原 C 解码器和 imagecodecs 独立解码器检查全部 24,839,168 个 RAW 样本，再与重新执行设计器生成的完整马赛克逐值比较。每块无 RAW 白端裁切，黑白电平范围合法；四张主卡的布局、每个设计值和定位码也逐项重建核对。外部目录全部只读。

| 检查 | 结果 |
|---|---|
| 原文件长度、IFD 图、IFD/字段/条带偏移、裁切、CFA、WB | 五份一致 |
| 新 RAW 逐值解码、两种独立解码器、旧图尾部清零 | 五份通过 |
| IFD0 RGB 缩略图、全尺寸 JPEG、MakerNote JPEG | 五份均可解码，三处均替换 |
| 理想 RAW 与量化 RAW 的三风格预测差 | 最大 0.250 ΔE00 |
| 保存 JPEG 后重新对位取色 | 最差 p90 0.808 ΔE00 |
| 额外 2 像素高斯模糊、JPEG Q90 4:2:2 | 最差 p90 0.074 ΔE00；四角齐全 |
| 四张卡三风格径向增益恢复 | 全通过；最大误差 0.0147 EV |
| 5,760 色环点的解码后 Standard 映射 | L、C 各自严格递增；最大 L* 误差 0.0185 |
| 中性 4,096 级扫描 | 三风格逐通道单调，不要求饱和端仍严格递增 |
| GR 相机能识别并显像 | 未运行；小样 gate 尚未通过 |

上述 ΔE00 只衡量同一冻结模型中的 RAW 量化、JPEG 和取色误差，不是预测器对真实 GR 的误差。Standard 网格反解刻意避免主色环被大面积模型截断，但相机域极值仍会使某种风格输出截断。下面计数以所有主颜色点和每张 17 级灰阶为分母，包含极值测试。近端点指任一通道 ≤2 或 ≥253/255；硬截断指预测浮点通道到 0 或 1。

| 风格 | 主点及灰阶 | 预测硬截断 | 预测近端点 |
|---|---:|---:|---:|
| standard | 8753 | 2126 | 2490 |
| positive | 8753 | 2902 | 3113 |
| negative | 8753 | 2599 | 2759 |

回传分析保留同位置的 RAW/Standard/风格原始观测。只有中性径向拟合和同色空间留出门槛通过，才允许使用中心归一化结果；不支持的色块不会夹值后冒充有效样本。offline_validation.json 是聚合统计，完整逐块预测、设计和分析只在 local/。

## 复用、复现与边界

通过 sys.path 导入 gr_incamera_dev 的 common、chart、inject、predict、analyze、verify；只把输出常量与临时目录重定向到本任务 local/。不运行原目录的初始化或批处理入口，不改写其源码。沿用原 CFA、SOF3 编码器、双解码、原位注入、三预览替换、冻结模型、方向码对位、中性 LUT 径向拟合及 gr-relative-targets/1。

同时复用了 gr_pairs/gr_webpairs 的同 RAW 配对与默认滑杆约定、gr4_modes 的空间补偿约定、contrib_gr_analysis 的 C 解码器与 MakerNote 读数、hue_ring 的旧布局统计、color_references 的公共容器来源，以及 closed_loop 的目标格式边界。原型已有 export_targets.py 可继续消费真实分析结果，但需要真实 04 锚；本轮没有捏造锚、回拟配方或导出固件。

从仓库根目录运行；所有命令使用隔离 Python。首次构建会创建不可自动重置的输入基线。已有基线若发现输入改变会拒绝，不会自动接受新哈希。

```sh
python3 -I -B research/gr_dense_reference/run_all.py
python3 -I -B research/gr_dense_reference/verify.py
```

分段复核每次重新做最终 DNG 解码、设计重建、范围和 JPEG 往返，再用绑定源码/模型/DNG 哈希的回执汇总：

```sh
python3 -I -B research/gr_dense_reference/verify.py --card 1
# 同样依次运行 --card 2、3、4、5
python3 -I -B research/gr_dense_reference/verify.py --final
```

首次全部验证通过后用 --final --seal 生成校验和。普通验证只核对现有清单，不会静默重封。SHA256SUMS 覆盖公开代码、报告、聚合统计与说明；DNG_SHA256SUMS 单列五份 DNG。local/SHA256SUMS 封存设计、预测和本地证据，排除 local/tmp 与可刷新 verification.json；交付目录自己的 SHA256SUMS 覆盖 DNG 和机主说明。所有哈希路径相对仓库根目录。

受保护目录起始快照共 1,343 个文件：captures/ 657、gr_incamera_dev/ 83、gr_pairs/ 425、hue_ring/ 128、artifacts/downloads/ 50，另核对 276 个既有跟踪文件和实际复用输入。verify.py 对五个目录内容、新增/删除与哈希做相等断言，复用输入改变同样失败。封存期间检测到范围外 decisions.tsv 哈希变化，未回滚、未重置基线，起止摘要留在 local/outside-changes.json 与 verification.json。默认验证单列这类无关范围外差异；--strict-workspace 会失败。因此本轮不声称整个共享仓库未变。写入审计拒绝本任务目录外的文件写操作，C 子进程的全部工作路径和 TMPDIR 也在 local/tmp。

公开内容检查拒绝图片/二进制类型、48 字节以上内嵌 byte 常量、长数值数组、逐块颜色字面量、像素 JSON 和编码图片，并用内存中的反例确认拒绝逻辑。它是针对本交付的检查，不是通用隐私证明。没有把任何模型系数、曲线、固件派生字节、图片或逐块数组写入公开文件。未 git add/commit，没有相机、SD、固件或设备命令访问。

## 回传检查入口

将机主附件原样保存到本目录 local/incoming/ 后，先验证小样。JPEG 缺 RICOH 元数据、ImageTone 错误、非默认滑杆、DNG 哈希不同、灰阶反转或定位失败都会拒绝。小样需要机主确认新文件确由相机 RAW 显像产生；仅靠元数据和网格不能密码学证明它不是预览缓存。

```sh
python3 -I -B research/gr_dense_reference/readback.py --card 1 \
  --dng research/gr_dense_reference/local/incoming/R0900001.DNG \
  --style standard=research/gr_dense_reference/local/incoming/acceptance.JPG \
  --out research/gr_dense_reference/local/incoming/acceptance-pass.json
```

主卡同理使用 --card 2 至 5，并提供三次 --style，分别为 standard=、positive=、negative=。readback.py 在小样 gate 通过后才处理主卡；直接调用旧分析器不能替代这个交付门槛。真实 JPEG 到位前，本包只达到离线包完成状态。
