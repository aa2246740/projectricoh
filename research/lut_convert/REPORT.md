转换工具已完成，并在八个徕卡官方 LUT 上跑出 50mm 的日常旋钮、T1、T2 假设对比。结果是整数条目的主机预测，没有相机验收；T1 受限，T2 不导出硬件条目。默认只用无 T 的旋钮，输出始终留在本任务 local/。

已核实：

- 工作卷为已挂载、可写 APFS，UUID 为 `14BE04EB-AF49-497E-B36A-B078B2F7C5E8`；下载前 `df -h` 显示约 20% 使用、1.4 TiB 可用。先读盘根 AGENTS.md，再写任务目录。没有安装依赖、启动子代理、sleep、轮询等待、提交或推送。
- 三份官方 ZIP 共八个 cube 已下载；没有执行下载目录中的任何内容。读取 Python 均用系统 `python3 -I -B`。全部官方固件、其他研究目录和捕获素材只读；未访问存储卡或相机，未制作卡容器。
- 1D、17/33/65 格 3D、DOMAIN、shaper+3D 和厂商 Log 公式已测试；实际 16 条候选由 Stage2l 原解析器在内存中验证，磁盘实际条目重新解码后与评分模型最大差为 1.42e-12 code。没有把临时完整表写成 DAT。
- `.gitignore` 的 `local/` 已由 `git check-ignore -v` 核对；所有理光派生曲线、矩阵、色表和条目只在 local/。文件名、mask、候选 schema 与 CRC 集成约束见 README.md。

推断：以下相似度都是量化后模型的误差缩减，严格为 `1 - median(候选到目标 ΔE00) / median(04 到目标 ΔE00)`。它不是原厂徕卡整机还原率。分母中位数低于 0.25 时保持 N/A。输入、灰锚、曝光没有为每个 LUT 自动匹配。两组随机色采用不同固定种子，最后一整张 DNG 不参与拟合。

| 文件 | 日常相似度 | 日常 ΔE00 中位/p90 | T1 相似度 | T1 ΔE00 中位/p90 | T2 假设相似度 |
|---|---:|---:|---:|---:|---:|
| Classic 2020 / 33 | 91.37% | 1.547 / 3.017 | 92.48% | 1.347 / 2.709 | 91.43% |
| Classic 709 / 33 | 91.25% | 1.568 / 3.133 | 92.35% | 1.371 / 2.815 | 91.26% |
| Natural 2020 / 33 | 94.24% | 1.019 / 2.272 | 94.07% | 1.049 / 2.266 | 94.37% |
| Natural 709 / 33 | 93.94% | 1.072 / 2.330 | 93.83% | 1.092 / 2.331 | 94.22% |
| Cine Viewing / 33 | 83.95% | 2.565 / 4.598 | 87.27% | 2.035 / 3.574 | 85.01% |
| Cine / 65 | 83.74% | 2.597 / 4.680 | 86.89% | 2.095 / 3.620 | 84.87% |
| Pure Viewing / 33 | 90.10% | 1.472 / 2.721 | 89.84% | 1.511 / 2.749 | 90.17% |
| Pure / 65 | 89.94% | 1.496 / 2.763 | 89.82% | 1.514 / 2.746 | 89.86% |

上表是合成留出色，不含训练像素。完整训练、留出、扇区、灰轴限制、求值次数和扫描结果均在每个 `results.json`、`sector_residuals.csv`。达到 100 次求值上限、未确认收敛的方案：Leica Cine Viewing LUT.cube / safe；Leica_Cine_Rec2020_LLog_to_Rec709_Gamma24_65_.cube / safe。这些结果只表示预算内近似。

四张实景 DNG 为：R8051131 ISO200；R8051144 ISO400；R8051145 ISO500；R8051147 ISO500。预览四列依次为 04 主机模拟、LUT 理想输出、日常旋钮预测、T1 预测；未把原有其他模式 JPEG 当作实拍 04。最后一帧是 ISO 500，用 ISO 200 前向模型做代理；本次照片也包含相近静物构图，因此下表只能作条件诊断，不是独立实拍泛化验收。

| 文件 | 日常相似度 | 日常 ΔE00 中位/p90 | T1 相似度 | T1 ΔE00 中位/p90 |
|---|---:|---:|---:|---:|
| Classic 709 / 33 | 87.92% | 2.010 / 3.171 | 94.68% | 0.885 / 1.898 |
| Natural 709 / 33 | 96.62% | 0.561 / 1.072 | 96.61% | 0.562 / 1.142 |
| Cine / 65 | 78.63% | 2.572 / 6.036 | 88.58% | 1.375 / 2.614 |
| Pure / 65 | 91.82% | 1.029 / 1.667 | 91.68% | 1.046 / 1.669 |

表达限制：

- 共同曲线、中性 Y 行和 24 个固定扇区不能分别控制同色相在不同亮度、饱和度下的所有变化。灰阶随明暗染色会被检测为日常旋钮受限，不能以高相似度藏掉它。
- T1 可以用三通道曲线改善部分明暗分色，但仍不等于任意 3D LUT，也不能复制徕卡传感器、镜头和空间处理。此版本需要 T 控制，未作新的生命周期或相机验收。
- T2 仅假设在扇区后按 Y 插值七点色度增益，1/64 取整；轴、端点、编码和插值均未实拍标定。只写 JSON 对比，不生成 T2 `.entry`，更不写 T。
- 当前 Engine 的原厂 04 在低彩度严格扫描中也会触发色相反转。候选保留扫描原值，不能把条目格式通过说成视觉安全通过。所有 `daily_eligible` 和 `camera_acceptance` 都为 false。
- 真黑白可走 03：共同曲线、通道混合、A20/B20。自动检测 .cube 的黑白 CLI 实跑也通过；safe 合成留出 ΔE00 为 1.934 / 4.856，mask=17、T control=2。 带色黑白不能用 03；任意“先混合再套非线性曲线”也不保证与硬件“曲线后混合”相同。

最终自检 11/11 通过。可表达效果在整数化后的结果为：

- exactly representable native tone reaches 98.5% after integerization：100.00%。
- exactly representable native sector reaches 98.5% after integerization：100.00%。
- 经过实际 .cube 文件读入和拟合：明暗 99.81%，局部扇区 99.80%。

局部扇区测试的全局分母几乎为零，所以全局百分比仍为 N/A；上面的扇区百分比只统计 04→目标 ΔE00>0.25 的受影响样本，其余扇区的绝对误差另存原报告。明暗分色测试同时要求限制被标出，并验证中性灰的 p90 误差仍大于 2，防止把不可表达效果误报为精确。首轮原始失败 8/11 已保留：黑白极坐标色差在零彩度处的导数改为可变的 L 分量；局部扇区测试修正了原本不稳定的百分比分母。另修正近零初值导致的极小信赖域，以及曲线搜索范围和中性轴初值；旧批次结果完整保留，不作为本报告数字。

彩色 LUT 的共同曲线灰轴也补了方向导数回归：在不允许偏离中性的参数空间内固定数值 Lab 色度为零，方向导数相对误差为 2.57e-10。实拍 04 JPEG 接口用原有 04 标签的三对图像跑过 identity LUT：反解有效比例分别为 99.94%, 100.00%, 99.99%，合成留出中位 ΔE00 为 1.73e-14，相似度因分母为零保持 N/A。这只是 JPEG 反解与转换接口检查，不是新配方实拍。

官方来源与许可：

| 官方文件 | 下载 SHA-256 |
|---|---|
| [pm-14626-Leica-Look-Up-Tables--Legacy-.zip](https://leica-camera.com/sites/default/files/pm-14626-Leica-Look-Up-Tables--Legacy-.zip) | `d1b51f98d45cce403b26888b586af42c7ae421840ce9c768ed841228678b5863` |
| [pm-28363-Leica-Cine.zip](https://leica-camera.com/sites/default/files/pm-28363-Leica-Cine.zip) | `7b92706701c5f25e5d23049f6c07aa264e691fd715942d4ef2d7499ecbbc64a6` |
| [pm-28364-Leica-Pure.zip](https://leica-camera.com/sites/default/files/pm-28364-Leica-Pure.zip) | `c989359a6e0d04de81371a844856329581516ff6d8a0fd96ba85242efbe592d8` |

下载页为 [Leica SL3 官方下载](https://leica-camera.com/en-US/photography/cameras/sl/sl3-black/downloads)。Legacy 输入为 L-Log/Rec.2020，分别输出 Rec.709 或 Rec.2020 Gamma 2.4。Pure/Cine 的 65 格文件名明确为 Rec.2020 L-Log→Rec.709 Gamma 2.4；对应 33 格与 65 格共同节点数值核对通过。Leica Looks 是另一套 FOTOS 分发工作流，未找到其通用公开 cube 或开放再分发许可，不把同名照片 Look 当作视频 LUT。详细名称、官方文档和下载失败证据见 SOURCES.md。

ZIP 内没有 LICENSE、README、EULA 或条款，也没有 comment；只能核实官方公开提供下载，不能据此声称开放许可或已获衍生配方再分发授权。本轮没有发布。Apple 白皮书返回登录页，Sony PDF 本地下载 403；Apple/Sony 曲线额外对照 OpenColorIO 官方源实现，未假称拿到了这两个厂商 PDF。

未知：新的候选在相机上的色差、退出恢复和日常稳定性；28mm/Mount 的具体标定适配；未标定 ISO 的响应；T2 的真实像素语义；Leica Looks 及下载 LUT 的衍生再分发授权。固定灰锚与 DNG→XYZ 的误差会影响迁移目标；本次没有重做这些既有研究，也没有把模型数字当成新标定。

用户提供文件和准确输入空间即可开跑；输出空间不明时要补充该声明。时长来自本机每个文件的一次执行，arm64，NumPy 2.4.3 / SciPy 1.17.1 / Pillow 12.2.0，计算线程设为 1。记录负载时为 10 核、load average 52.12 / 40.88 / 28.19，其他 worker 并行工作，不能将这些数值作为稳定性能基准。单文件计时包含读 cube、目标生成、三档拟合、整数验证和预览；共享 Engine/DNG 准备在计时外，收尾结果与 SHA 写入也在计时外。本轮每个 LUT 约 9.3–21.7 秒，首次另需模型和 DNG 准备；默认只做 safe 一档，详见 README.md。

| 文件 | 本次秒数 | safe/T1/T2 求值次数 |
|---|---:|---:|
| Classic 2020 / 33 | 13.63 | 24/12/12 |
| Classic 709 / 33 | 21.72 | 27/13/7 |
| Natural 2020 / 33 | 14.65 | 42/19/7 |
| Natural 709 / 33 | 12.95 | 34/16/7 |
| Cine Viewing / 33 | 15.96 | 100/13/22 |
| Cine / 65 | 15.34 | 100/11/19 |
| Pure Viewing / 33 | 10.56 | 25/17/12 |
| Pure / 65 | 9.26 | 21/16/13 |

| 产出 | 用途 |
|---|---|
| `convert.py`、`cube.py`、`spaces.py` | CLI、受限纯数据解析、输入/输出空间转换。 |
| `camera.py`、`fit.py`、`guard.py` | 50mm 前向模型适配、整数拟合、只写 local/ 的运行边界。 |
| `fetch_sources.py`、`batch_official.py` | 官方数据隔离下载与八个 LUT 的批处理。 |
| `selftest.py`、`verify.py`、`report.py` | 合成自检、实际条目字节复核、报告与哈希再生。 |
| `README.md`、`SOURCES.md` | 用户如何交 LUT，参数、公式和来源。 |
| `local/leica-complete/` | 八份结果、八张四列预览、24 份扇区表、16 条单条候选。 |
| `local/overview.html` | 可离线打开的自包含对照页，四种风格可切换。 |
| `local/selftest-complete/` | 最终 11 项自检与合成 LUT；原始失败另保存在 `selftest-r1/`。 |
| `local/e2e/bw-complete/` | 自动识别黑白的 CLI 结果和 03 候选。 |
| `local/verification.json` | 实际字节、模型重放、输入不变和下载哈希证据。 |
| `local/official_sources.json` | 原始 URL、许可状态、每个 ZIP 和 cube 的 SHA-256。 |
| `SHA256SUMS` | 本任务文件与两处本任务下载目录的完整交付哈希。 |

复核命令：

```bash
cd /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh
git check-ignore -v research/lut_convert/local/probe artifacts/downloads/leica-luts/probe
python3 -I -B research/lut_convert/selftest.py --out local/selftest-review
python3 -I -B research/lut_convert/verify.py
cd research/lut_convert
shasum -a 256 -c SHA256SUMS
```

最终批处理命令为 `python3 -I -B research/lut_convert/batch_official.py --max-nfev 100`；不会覆盖已有目录。重新生成报告与哈希前，先运行 `verify.py --skip-manifest --save local/verification.json`，再运行 `report.py`，最后不带参数复核 `verify.py`。需要新一轮数值时使用 `batch_official.py --out local/另一目录`，不要改写本轮证据。
