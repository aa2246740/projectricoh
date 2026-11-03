在仓库根目录运行。全部 Python 都要求 `-I -B`；脚本只写本目录和 `artifacts/downloads/bridge_public_r1/`。离线重跑不访问网络，也不调用固件构建、相机或卡。

```sh
python3 -I -B research/bridge_public_r1/pipeline.py run
```

这会解析已有公开参考，重提取两份 DPReview RAW 和灰阶，拟合两机响应，计算日光桥接情景，按 ceiling 原指标传播目标变化，并重生成报告与校验和。现有研究和原始照片都通过 SHA-256 冻结。`decisions.tsv` 不读、不写、不纳入冻结。

新增一张完整的真实 ColorChecker 照片时，用一条命令录入并重算。四角按预览中的 TL、TR、BR、BL 填写，边界包住 6 × 4 色块区，排除外围黑框。示例是本轮 GR IV 的已核实几何；其他照片必须先检查自己的预览并换掉坐标。

```sh
python3 -I -B research/bridge_public_r1/pipeline.py add-chart \
  --camera griv \
  --dng artifacts/downloads/dpreview-gr4-studio/gr4_studio_daylight_iso100.dng \
  --preview artifacts/downloads/dpreview-gr4-studio-preview/gr4_studio_preview.jpg \
  --corners '[[650,137],[949,137],[949,331],[650,331]]' \
  --formulation post2014
```

对新的 GXR A12 50mm 完整色卡 RAW，改用 `--camera gxr`、其实际文件和坐标。色卡须为真 ColorChecker Classic，并按生产版本选择 `pre2014` 或 `post2014`。DFOPTIX CC24 没有已知光谱，不能放入这个估计器。参考版本未核实时应分别跑两种版本，并将结果保留在各自 `local/` 副本内。

`add-chart` 在本研究的 `local/chart_override_<camera>.json` 登记覆盖输入，原有文件仍保持原位。`run` 遇到覆盖输入会继续采用它。默认报告描述本轮两张 DPReview 文件；换图后须同步审阅报告中的场景说明，不能把自动生成的说明当成新照片的事实。

代码入口及证据：

- `extract.py` 和 `extract_griv.py` 从原生 CFA 提取，保留裁切、黑电平、饱和、ROI、遮挡和空间梯度。PNG 取样图在 `local/`。
- `prepare_data.py` 只把下载内容当数据解析；下载中的 Python 表格仅用 AST 字面量读取。
- `estimate.py` 用公共相机 PCA、色卡 RAW 和软 ColorMatrix 约束估计光谱；按颜色家族留出。`local/sensitivity_intervals.csv` 是情景区间，不是实测置信区间。
- `bridge.py` 在 Munsell 训练集拟合线性及曝光齐次的平滑根多项式；Munsell 留出集和所有自然物光谱用于评估。
- `propagate.py` 直接复用冻结 `gr4_lut_ceiling/style.py` 的函数，保持既定相对风格目标与 ΔE00 指标。它重算改变目标后的分子和分母，没有重拟合 LUT，也没有把中位色差相加。
- `diagnostics.py` 用两个独立解码器对照 GR IV RAW、检查 GXR 12 位解包，并登记来源、灰阶和器件推断。
- `verify.py` 检查证据、冻结与所有下载的摘要；`seal.py` 写最终 `SHA256SUMS`。

公开下载通过 `fetch.py` 的只读 GET，保存到各自独立新目录，URL、日期、HTTP 状态、摘要在 `local/sources.json`。站点失败原样登记；DPReview 新 RAW 由协调者浏览器取得，本 worker 从未重下载。所有 `local/` 均被 Git 忽略，含志愿者衍生风格与诊断，不得公开提交。

```sh
shasum -a 256 -c research/bridge_public_r1/SHA256SUMS
```

校验和相对仓库根目录，覆盖本轮代码、报告、证据和新下载。执行重跑会更新证据和摘要，完成后再核验即可。
