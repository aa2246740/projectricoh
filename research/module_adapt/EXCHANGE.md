交换格式已落地，`calibrate.py` 直接读取色块 JSONL 和帧 JSON。所有运行输出只能放在本目录的 `local/`；这些 JSON 都是主机分析数据，没有卡文件导出器。

每行色块包含以下字段。`page + patch_id` 是目标匹配键，不能用行号替代。

| 字段 | 约定 |
|---|---|
| `frame` | 帧 JSON 中的稳定帧 ID。 |
| `page` | 屏幕页 ID，整数或字符串。不同重复照片沿用同一页 ID。 |
| `patch_id` | 色块 ID，整数或字符串。必须保留 chart_v2 的原 ID；可另存 `sample_key`。 |
| `class` | 字符串，如 color、neutral、skin、validation 或 chart_v2 的 category。 |
| `raw_rgb` | 三通道相机原生 RGB 均值，已减黑电平，再按有效白电平范围归一，未白平衡、未去马赛克、未变色域。两种绿色先按有效样本加权合并。 |
| `jpeg_rgb` | sRGB JPEG 的三通道 ROI 均值，范围 0..255。JPEG 像素是 8 位，均值可为小数。 |
| `valid` | JSON 布尔值。无效记录保留；无效记录的数值字段可为 null，拟合器跳过它。 |
| `spatial_sd` | 推荐 `{"raw_rgb":[Rsd,Gsd,Bsd],"jpeg_rgb":[Rsd,Gsd,Bsd]}`，单位分别与 raw_rgb、jpeg_rgb 相同。兼容 JPEG 三通道 SD 或单个 SD；兼容模式没有 RAW 空间均匀性检查。不是标准误差。 |

帧文件的顶层为 `{"schema":"ricoh-module-frames/1","frames":{帧ID:帧元数据}}`。

| 帧元数据字段 | 约定 |
|---|---|
| `module` | `50mm`、`28mm`、`mount` 三选一。 |
| `iso` | 整数。模型入口目前只接受每次单独标定 ISO 200 或 1600。 |
| `shutter_s` | 曝光秒数，如 1/60 写成数值 0.0166666667。 |
| `aperture_f` | 实际光圈值。Mount 必须由操作者确认，手填的 EXIF Lens Info 不证明镜头实际光圈。 |
| `white_balance` | 对象，至少包含 `mode` 和三通道正数 `gains`。RAW 仍按未白平衡保存，拟合器在内存里乘 gains。手动 WB 的 gains 可由 DNG AsShotNeutral 的倒数并以 G=1 归一得到。另保留 WB 补偿、色温和原始标签。 |
| `selector_bytes` | 对象，包含 `recipe_slot`、`image_setting`、`raw13`、`type26_control`。04 要求 Standard、control=2；13 个原生参数必须与所用模型状态一致，否则拒绝拟合。raw13 顺序见下一段。 |
| `source_kind` | 正式数据写 `camera`，模拟数据写 `synthetic`。 |
| `color_space` | 本流水线使用 sRGB JPEG。保留原始 EXIF 色域标签，Adobe RGB 不能直接当 sRGB。 |
| `lens_id` | Mount 必填，使用能区分实物镜头与转接环的稳定 ID。固定镜头单元也建议填。 |
| `corrections` | Mount 必须固定并记录周边光量、R/B 色彩阴影和畸变设置；其它影响 JPEG 的设置也原样保留。 |

raw13 的顺序为 contrast、sharpness、vividness、orange/green/blue/red/magenta saturation、orange/green/blue/red/magenta hue。它保存原生字节，不是菜单显示的 1..9。实际可读取的完整示例由 `selfcheck.py` 生成在 `local/selfcheck/noiseless_frames.json`，其 `source_kind` 明确为 synthetic。

独立目标文件顶层为 `{"schema":"ricoh-module-targets/1","whitepoint":"D65","source":"目标来源与版本","samples":[...]}`。每个 sample 包含 page、patch_id、slot、target_lab，可选 baseline_target_lab。Lab 必须是 D65；若从 ICC PCS D50 输入，先作已记录的色适应。未提供 baseline_target_lab 时，以同一目标计算原厂 04 分母。提供时必须说明其与配方目标的关系，不能混用分母。

屏幕 PNG/P3 设计色与相机原生 RAW 不同。P3 数据只用于排页、覆盖检查和独立目标生成；不能把 P3 的三个数字填到 raw_rgb。脚本不会从设计 RGB 猜测相机 RAW。

从仓库根目录使用以下流程。`--patches`、`--frames`、`--calibration`、`--targets` 接受本检出内的绝对路径或相对仓库根路径；`--output` 相对本任务目录，且必须落在 local/。

```sh
python3 -I -B research/module_adapt/extract.py

python3 -I -B research/module_adapt/calibrate.py fit-04 \
  --patches research/module_adapt/local/incoming/patches.jsonl \
  --frames research/module_adapt/local/incoming/frames.json \
  --unit 28mm --iso 200 --holdout-page 6 \
  --output local/calibration/28mm_iso200.json

python3 -I -B research/module_adapt/calibrate.py fit-recipe \
  --patches research/module_adapt/local/incoming/patches.jsonl \
  --frames research/module_adapt/local/incoming/frames.json \
  --unit 28mm --iso 200 --slot 05 \
  --calibration research/module_adapt/local/calibration/28mm_iso200.json \
  --targets research/module_adapt/local/incoming/targets.json \
  --output local/refit/28mm_05.json
```

50mm 新拍的各配方用于更新配方响应残差。先按相同步骤标定 50mm 的 04，然后逐槽运行：

```sh
python3 -I -B research/module_adapt/calibrate.py learn-50mm-residual \
  --patches research/module_adapt/local/incoming/patches.jsonl \
  --frames research/module_adapt/local/incoming/frames.json \
  --unit 50mm --iso 200 --slot 05 \
  --calibration research/module_adapt/local/calibration/50mm_iso200.json \
  --output local/priors/50mm_05.json
```

随后可在 fit-recipe 命令增加 `--residual-prior research/module_adapt/local/priors/50mm_05.json`。六近邻插值在 log2 输入 RGB 中进行，最近距离超过 0.5 时不用该点的先验，并报告数量。借用 50mm 的残差是假设，不会被标成 28mm 或 Mount 实拍。

fit-04 默认为 4 基函数仿射残差，可用 degree=2 改为 10 基函数二次残差。优先按完整页留出，只有一页时才按稳定 patch_id 哈希留出。重复帧中同一个色块不会分到训练和验证两侧。fit-recipe 则按完整 15° 色相带留出；报告预测用三个折拼接评分。

第一版配方拟合开放 Y 行的两个自由度和 24 对对称扇区系数，写回整数后评分。03 只调 Y 行，06 保留现有 T1 三条曲线。A/B 曲线节点、row20、matrix 色度行和 T1 节点不在这版求解器里重新优化。06 若灰阶或明度相关残差未通过，需要另开分通道曲线重拟合，不能用色表掩盖。

分析 JSON 保留 firmware_ready=false、deployment_allowed=false。拍完 04 只能约束单元输入映射；新单元的扇区响应导数、T1 机内行为与配方实拍仍需后续验证。
