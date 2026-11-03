可以交复审

# S6：M2 渲染后端（studio-render-s6-r1）

DNG 现在能套相机配方和旋钮，再叠加曝光、白平衡偏移、画面对比/高光/阴影和主曲线。预览走烘焙，导出可走烘焙或精确链。全部颜色结果标"电脑预测"。完整测试 **206 个全部通过**（原来 177 个 + 新增 29 个），没有改 `studio/web/`，没有改 engine / camdata 的算法，没碰相机和真实的卡，没联网，没 commit。

数字全是本机（M 系列 Mac、4 个工作线程）上的**单次实测**，不是承诺；原始数据在 `bench.json`，脚本在 `tools/bench.py`。

## 1. 先说一个与设计文档不同的决定

ARCHITECTURE §5.2 写的是"一维曲线 + 33³ 三维表"。我照做了（`chain.bake_model`，四面体插值，灰轴在网格对角线上），**实测过不了验收线**，所以线上用的是另一种烘焙，33³ 留作对照：

| 烘焙方式（24 个配方里最差的一个，40.8 万个像素：4 张样本照片 + E0 的 4 个场景 + 合成色立方体） | p99 ΔE00 | 最大 ΔE00 | 8 位最大码值差 |
|---|---|---|---|
| 三维表 33³（§5.2 原方案） | 2.33 | 4.96 | 19 |
| 三维表 49³ | 1.45 | 3.96 | 12 |
| 三维表 65³ | 1.01 | 3.23 | 8 |
| **色度增益网格，间距 1.0** | 0.39 | 1.14 | 3 |
| **色度增益网格，间距 0.75（预览用）** | **0.23** | 0.65 | **2** |
| **色度增益网格，间距 0.5（导出用）** | **0.11** | 0.34 | 1 |

原因：`Model.predict` 里"矩阵 → 色表"的色表只依赖 (Cb, Cr) 两个数，而且是线性矩阵之后才进色表（`chain.py` 顶部有结构说明）。所以只需要把色表那一步烘成 (Cb, Cr) 平面上的复数增益 G(c) = 输出色度/输入色度（双线性插值再乘回输入色度），矩阵部分保持精确。三维网格要在 RGB 立方体里表达色表绕灰轴的色相依赖，网格越粗越吃亏。

- ΔE00 比较的是**未量化的浮点输出**（量化噪声两边都有）。8 位输出的差见表里最后一列：预览网格最多差 2 个码值，约 12% 的像素有至少一个通道差 1 码（在最差配方上；整幅图实测只有 8.6%）。量化后的 p99 ΔE00 最大 0.89，这主要是 1 码翻转在暗部/蓝色通道上的 ΔE，不是烘焙误差。
- 加上曝光、色温/色调、画面对比/高光/阴影、主曲线之后，同一组比较的最差 p99 = 0.23（`with_adjustments_preview_grid_worst_p99`）。
- 因为不再有 3D 表，显示域调子表不是折进表里，而是烘焙之后逐像素查表；所以拖曲线不需要重新烘焙。
- "烘焙"里 `Model.predict` 的后半段没有复制研究代码：三维对照用 `Model` 的浅拷贝（`pre` 原样通过）直接调 `predict`；色度烘焙取系数的几行与 `predict` 逐字相同，24 个条目逐个对拍（`test_chroma_bake_error_budget_on_all_24_recipes`，用 E0 场景输入和合成色点，p99 ≤ 0.3、最大码值差 ≤ 3 的门槛写在测试里；上表的 40 万像素版本在 `tools/bench.py`）。

## 2. 验收对照

| 项 | 结果 |
|---|---|
| 烘焙误差 p99 ΔE00 ≤ 0.3（与精确链比） | **通过**：预览 0.23 / 导出 0.11（最差配方、最差分位）。33³ 三维表**不通过**（2.33），见 §1 |
| 烘焙最大码值差 ≤ 2 | 预览网格 2、导出网格 1（含合成极端色）；三维 33³ 为 19 |
| 预览延迟 p50 < 400 ms（半分辨率 2144×1424，经 HTTP） | **通过**：曝光滑块 p50 106 ms（p95 118）；白平衡 109（125）；曲线/调子 119（128）；**旋钮变化（每次都重新烘焙）p50 271 ms（p95 324）**；换配方 237（248）；同一组参数再来一次（结果缓存）0.8 ms；拖动期 `max_edge=800` 的曝光滑块 18 ms。旋钮变化的内部拆分（中位数）：烘焙 138 + 套用 88 + 编码 9 ms；首次打开一张照片多一次解码（约 125 ms，冷启动整体约 0.5 s） |
| 全分辨率导出耗时（4288×2848，12 MP） | 烘焙（间距 0.5）JPEG：**1.4 s**；PNG：2.0 s；**精确链（逐像素 `predict`，`precise: true`）：21.2 s**。都含读 DNG、条带去马赛克、裁切、编码、写盘 |
| 默认参数下与 E0 研究渲染逐像素一致 | **精确链：一致，逐字节**——24 个配方 × E0 的 4 个场景输入，输出与 `Model.predict(quantize=True)` 字节相同；E0 黄金清单（`render_frames.json`）每 12 张抽 1 张（40 多张），哈希全对；整幅半分辨率图（305 万像素）精确链输出 = `predict` 输出。**烘焙路径不是逐字节一致**：整幅图上 8.6% 的像素差 1 个码值，最大码值差 1，p99 ΔE00（量化后）0.77，这是 §1 的烘焙误差，不是别的 |
| 曲线为恒等时与无曲线逐字节相同 | 通过（恒等直线在解析时就被当作"没有曲线"，调子表为 None，链完全不经过它；测试里还用显式表对拍） |
| 曝光 +1 EV 等价于链输入 ×2（含 4095 夹紧） | 通过（`test_exposure_is_input_gain_with_clamp`） |
| 原有 177 个测试 | 全部通过；全量 206 passed（2 分 50 秒） |

### 附带两个小修复（S4 遗留）

只有 DNG 的照片，缩略图和预览不再用 DNG 里 160×120 的小图：改用半分辨率路径（2×2 合并的码值 → 缩到目标尺寸 → 没有任何编辑时的样子）。导入了相机数据就是该单元原厂 04 的电脑模拟，没有就是中性预览；半分辨率读不出来（假 DNG、截断文件）才退回内嵌小预览。缓存文件名带变体（`<id>-256-r…` / `-n`），相机数据变化后缩略图自己重画。**缩略图和 `/preview` 不跟随用户的编辑**（它们是缓存，键不含编辑），有编辑的图用 `/render`。

## 3. 做了什么

**`studio/src/gxr_studio/render/`（新）**

- `params.py`：sidecar 里 `recipe` / `adjust` / `curve` 的解析和范围校验（曝光 ±5 EV，其余 ±100；曲线最多 16 点，PCHIP 单调插值）。
- `recipes.py`：`Menu`（final.json，不含理光字节，没导入相机数据也能列配方）和 `CameraData`（读 camdata 并逐文件核 SHA-256、条目 CRC）。旋钮档位 → `engine.menu.request` → `engine.knobs.apply`，档位不合法直接报错不钳位；03 没有饱和等、04 没有 Amount、到顶标记都由 final.json 驱动。
- `tones.py`：电脑专用调整。曝光与色温/色调是输入端的 R、G、B 增益（暖 = R 升 B 降，品红 = R、B 同升）；画面对比/高光/阴影与主曲线合成**一条**显示域表。这些调子函数是我定义的（平滑 S 曲线、两个钟形权重，±100 时仍单调，黑白场不动），**没有对照过任何参考**，界面上应标"仅电脑"。
- `chain.py`：精确链、色度烘焙（线上）、三维烘焙（对照）。
- `service.py`：渲染服务。三层缓存（解码后的码值图、烘焙结果、渲染结果），键按 §5.3（源 SHA-256、方向、调整、配方条目 SHA-256、曲线、引擎版本、目标宽度、裁切）；同一组参数不重复计算（测试断言了解码/烘焙/渲染次数）。同时最多 2 个渲染在跑，计算用 4 个线程。
- `edits.py`：sidecar 读写（原子写、`rev` 乐观并发，其余键原样保留，裁切与编辑互不覆盖）。

**API（`api/render_routes.py`，新；`api/routes.py`、`app.py` 小改）**

- `GET /api/render/status`、`GET /api/recipes`（3 单元 × 8 底子，带每个旋钮的档位表、到顶标记、Amount 步长；没导入相机数据也能列，只是没有条目 SHA）。
- `GET/PUT/DELETE /api/photos/{id}/edit`：读写配方、旋钮、调整、曲线；返回里分开列出 `scope.camera` 与 `scope.computer_only`，并附 `render`（标签、是否已标定、原因、实际生效的档位）。
- `GET /api/photos/{id}/render`（按 sidecar）和 `POST …/render`（请求体里的 `recipe/adjust/curve` 盖过 sidecar，不落盘，拖滑块用）；参数 `max_edge`、`crop`、`exact`、`quality`；`ETag` = 渲染键，支持 304；头里 `X-GXR-Prediction: 1`、`X-GXR-Calibrated`、`X-GXR-Label`（百分号编码的中文）、`X-GXR-Cache`、`X-GXR-Timing`。
- 导出 `POST …/export` 多了 `source`（`auto` / `recipe` / `camera-jpg` / `neutral`）和 `precise`。`auto`：有编辑（配方、调整或曲线）或只有 RAW 且相机数据可用时从 RAW 渲染，否则照旧用相机 JPG；没有相机数据时 DNG-only 仍是 S4 的中性预览。文件名 `原名_gxr_电脑预测.jpg` / `原名_gxr_电脑预测未标定.jpg`，EXIF ImageDescription 写明 "computer prediction (not camera-measured)…"（只能是 ASCII）；返回里 `prediction: true`、`calibrated`。
- 没有相机数据或标定包：预览/导出返回 **409**，`error` 为 `camera_data_missing` / `camera_data_invalid` / `calibration_missing`，`message` 写"请先插入装有配方程序（GXRCE.DAT）的存储卡，或导入官方固件包…"，并带完整 `status`。

**标签口径（M2 验收 6）**：50mm、ISO 恰为 200 或 1600、配方与镜头单元一致 = "电脑预测"；其它一律 "电脑预测（跨单元/跨 ISO，未标定）"，并列出原因。单元由 EXIF 镜头名判断（`50mm` → jlaunch，`28mm` → qlaunch，含 `mount` → l08firm，认不出 → 标未标定）；PUT 时配方单元与镜头单元不一致会被拒绝（`unit_mismatch`）。28mm / MOUNT 沿用 A12-50 的模型。ISO 选模型：< 566 用 ISO 200 的，否则 ISO 1600 的（200 与 1600 的几何中点；`camdata.calib.model_for` 自己只认 ==1600，我传的是已经归并过的值）。

## 4. 没有做 / 需要知道的

1. **标定包没有用户导入入口。** `camdata.calib.import_calibration` 只能从研究目录（`dev_sources`）导入，应用数据目录里没有 `calib/` 时，预览返回 `calibration_missing`。相机数据（DAT）的导入入口也还没有 API。这两个导入路径是下一步（前端 S7 之前或同时）要补的，我没有在这里做（任务只要求返回明确状态）。
2. **样本 DNG 的 ISO 是 400 / 500**，所以本机真实样本上预览全部标"未标定"；"已标定"路径只在 ISO 200/1600 的数据（测试里用元数据）验证过。**28mm / MOUNT 一张 DNG 都没有**，镜头名到单元的映射、它们的解码与白平衡都没有验证。
3. 只支持 `recipe.kind = builtin`（底子 + 旋钮）。用户配方、LUT 配方是 M3。曲线只有主曲线，没有分通道。
4. 色度烘焙的网格范围由 8 个立方体角算出来（`ConvexHull`），只算套用时用得到的格点；B&W 03 增益恒为 1（与 `predict` 的 conditional 色度假设一致，这个假设本身仍是"可能"，不是相机验证过的）。
5. `ApiError` 多了可选的 `extra`；`export.export_shot` 多了 `use_raw`；`export.crop_image` 从 `_finish` 里拆出来（行为不变）；`raw.Renderer` 多了默认为空的 `description`。`photo_json.preview_kind` 对 DNG-only 仍是 `"dng-preview"`（原有测试断言它，含义现在是"没有 JPG 的预览"）。
6. 全量测试里有一次 `test_import.py::test_kill_the_process_20_times` 失败：被杀掉的导入进程在 `.studio/thumbs/` 里留下 `.thumb-*.tmp`，重开图库时没有清掉。这是缩略图临时文件原本就放在 thumbs 目录、杀进程时机刚好撞上的老问题（不是新逻辑引起，但我之后才看到）。已把缩略图临时文件改放 `lib.tmp_dir`（每次打开图库清空），改后该测试连跑 3 次通过，全量也通过。这个测试本来就依赖杀进程的时间点，仍可能偶发，别当成确定性结论。

## 5. 附带测得的数（诊断，不是验收）

- **半分辨率合并 vs 全分辨率去马赛克后缩小**（ARCHITECTURE U3，R8051144，同一条 04 链，ΔE00）：全图 p50 1.48 / p90 4.15 / p99 8.15；平坦区（58% 像素）p50 1.67 / p90 4.11。差异看起来是逐像素噪声而不是偏色：各通道均值差 ≤ 0.12 码（总量约 550），9×9 局部均值差的中位数 < 0.8 码。原因（R/B 在半分辨率里是单个采样、去马赛克后是邻点插值再平均）我没有进一步验证，只能说"不是系统偏差"。
- **04 电脑模拟 vs 相机 JPG**（4 张样本，ISO 400/500，用了哪个配方未知，标"电脑预测 vs 相机 JPG"）：中位 ΔE00 2.7 / 9.7 / 7.1 / 3.7，p90 6.9 / 14.6 / 14.0 / 7.9。不能据此说模型准或不准：样本拍摄用的配方和 ISO 标定都对不上。

## 6. 文件

- 新增：`studio/src/gxr_studio/render/{__init__,params,recipes,tones,chain,service,edits}.py`、`studio/src/gxr_studio/api/render_routes.py`、`studio/tests/test_render.py`、`research/studio_render_s6/{REPORT.md,bench.json,SHA256SUMS,tools/make_home.py,tools/bench.py}`。
- 修改：`api/errors.py`、`api/routes.py`、`app.py`、`export.py`、`library/thumbs.py`、`raw/render.py`（均在 `studio/src/gxr_studio/` 下）。
- 测试里的理光数据现场从本机固件打包目录提取到临时目录；仓库里没有新增理光字节（`bench.json` 只有统计数）。
- 复现：`studio/.venv/bin/python -m pytest -q`（在 `studio/` 下）；`studio/.venv/bin/python research/studio_render_s6/tools/bench.py bench.json`（约 15 分钟）。
