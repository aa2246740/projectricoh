# GXR Studio v2 前端：第二阶段实现报告

更新：2026-10-30，第二轮（COPY.md 第 3.10 节补充裁定 2 落实）。

依据：`research/studio_v2/PRD.md` §10（合同修订 1）、`research/studio_v2/COPY.md`（第 3.9、3.10 节）、`research/studio_v2/ui/` 的设计稿。

范围：只改了 `studio/web/**`、`research/studio_v2/ui/**`，以及 `tests/test_web_*.py`。没有改 `studio/src`、`pyproject.toml`、`uv.lock`、README、docs、Makefile，没有做 git 写操作，没有开子代理，测试同一时间只跑一个进程。没有碰 `127.0.0.1:49667` 和 `~/Pictures/GXR Studio`。

## 1. 结论

- 第二轮（3.10）的十项裁定已经落实到 `studio/web`，逐条改动见 `COPY_DIFF.tsv`（第二轮的行依据写 `3.10-n`）。
- 自动化：`ruff check tests/` 通过；`ruff format --check tests/` 通过（34 个文件已格式化）；`test_web_frontend.py`、`test_web_m2_smoke.py`、`test_web_smoke.py` 共 44 项通过（第三轮后）。
- 浏览器（临时实例，每次全新 Chrome profile）：主流程、降级流程、旧版相机（第 131 代）、LUT 流程，`errors` 全部为空。
- 后端的 P0（sidecar 的 `frame` 键冲突）已修，第四轮用全新临时库和全新 Chrome profile 复验通过，不再手工补宽高（§2b）。
- COPY_GAPS.md §2 里有 7 项需要你定。

## 2. 第二轮（COPY 3.10）改动

| 3.10 | 改动 |
| --- | --- |
| 1 只有 JPG | 恢复面板里的「配方需要 RAW 文件」，下面小字「拍摄时将画质设为 RAW+JPEG」，按钮置灰。兜底的 `reason` 同文 |
| 2 导出面板 | 删除「精确」勾选框（固定 `precise = false`，烘焙表）和「导出内容」列表 |
| 3 配方旋钮 | 去掉「相机」标签；写不进旧版相机配方文件的 5 项打「仅电脑」（只在旧版相机上）；旧版下对比度、高光、阴影、饱和度的滑块限制在 ±5，不打标签；删除调整标题旁的「仅电脑」 |
| 4 LUT 与校准 | 「LUT 类型」→「输入色彩空间」；「推测」小标签（按文件名判断的理由放进提示气泡）；「示意图」→「示例照片」；「中位误差」→「色差」；「与 04 标准几乎相同」→「接近 04 标准」；计算方法和色块说明删除；色域「默认」；「项目文件夹」→「校准数据文件夹」标签；「请输入完整路径」；「已重建索引」 |
| 5 存储卡 | 状态行写「存储卡：有未导入的照片」；「发现存储卡」→「已插入存储卡」；多卡写「已插入 2 张存储卡，先导入「A」」；去掉「另有 N 张」 |
| 6 大图 | 「照片本身」统一为「原图」；快捷键表写「按住空格 / 查看原图」 |
| 7 单字选项 | 核对过，不用改 |
| 8 结果提示 | 删除「已重置」「已自动拉直」「没有可以撤销的内容」；撤销没有内容时按钮置灰（`aria-disabled`，浏览器中验证过）；「已存储为我的配方」→「已存储为「名称」」 |
| 9 通用错误 | 写出对象：「无法读取裁剪。请重试。」「无法读取编辑记录。请重试。」「无法读取这张照片。请重试。」「无法读取相机配方文件。请重试。」「无法自动纠正这张照片。请重试。」「无法读取 LUT。请重试。」等。删除未被引用的 `errorLine` |
| 10 图库 | 删除确认改为「删除「名称」？」，按钮 [取消] [删除]（目前只有「我的配方」能删） |

另外：`tests/test_web_frontend.py` 的 FORBIDDEN 列表更新（加入 3.10 删掉的说法，去掉已恢复的两句）；新增 `test_section_3_10_sentences_are_used_verbatim` 和 `test_recipe_and_adjust_tags_follow_3_10`。`tests/test_web_m2_smoke.py` 里「仅电脑」的断言改到 `recipes.js`。

## 2h. Sol 第二轮验收的前端部分（REVIEW-r2.md，第十轮）

- **R2-01 导出底图**：界面导出一律 `source=auto`，单张和批量都一样（`export.js`）。
- **R2-05 成片标签**：`X-GXR-Label` 的机器值换成中文：prediction 显示「电脑预测」，`X-GXR-Calibrated=0` 时再加「未校准」；approx 显示「近似」；original 不加小标签。界面上不出现英文机器值（`preview.js` 的 `stageLabels`）。
- **R2-06 导出错误**：单张导出原样显示后端的主句，有 `detail` 时进「详细信息」。批量导出每一张失败的原因都保留（`export.js`）。`errorBody` 把主句放在自己的元素里。
- **R2-09 撤销继承**：撤销快照记住装饰是「继承默认」还是「明确设置」，撤销时继承的写 `null`，不再把默认值固化成照片设置（`preview.js` 的 `undoChange`；改边框、时间戳、复原时记下明确设置）。
- **验证**：补了 camera 数据（第 138 代）和校准包到验收临时库，让预测路径和 R2-01 的触发条件都生效。`ui_acceptance` 0 错误、0 个 4xx；`ui_regression_r2`：两次导出都是 `source=auto`，成片标签显示「电脑预测」「未校准」，导出失败显示后端主句和「详细信息」（折叠）；`ui_latency_defaults_r2`：复原→撤销后 frame、stamp 都是 `null`（继承），改默认后显示 640 × 544。
- **注意**：`ui_regression_r2.mjs` 原来等待的是「导出失败。请重试。」，这与 R2-06 要的行为相反，所以我在副本里改成等待后端主句。批量导出的错误显示没有在浏览器里跑过。
- **未在本轮处理**：R2-10（纠正滑块松手后约 2.3 秒，后端图库锁）是后端的问题。
- 测试：`test_web_*.py` 共 61 项通过。新增 4 组：`source=auto`、成片标签、导出错误、撤销的继承。

## 2g. Sol 验收的前端部分（REVIEW.md，第九轮）

- **V2-05 按住空格看原图**：请求 `GET /api/photos/{id}/render?stage=original&size=preview`。接口不存在时，图片加载失败一次，退回原来的 `preview_url`（`stage.js`）。
- **V2-08 复原**：写 `frame: {style: "none"}`、`stamp: {enabled: false}`，不再写 null（`viewer.js`）。
- **V2-15 纠正预览**：旋转、翻转后的预览改用 preview 尺寸（`correct.js`）。拉直和滑块松手本来就不请求 full，没有改。
- **V2-16 边框缩略图**：4:3 的框，`object-fit: contain` 覆盖图库的 cover，完整显示成片（`app.css`）。
- **错误的「详细信息」**：`dom.js` 新增 `errorBody` 和 `toastError`。主句照常显示；后端给了 `detail` 时，下面是默认收起的「详细信息」。所有错误提示改走 `toastError`，LUT 面板的错误也保留 detail。
- **底部按钮的底边**：`.sticky-foot` 改为贴住面板底边（之前有 14px 的缝，内容会从缝里露出来）。
- **验证**：Sol 的 `ui_acceptance.mjs` 0 个错误、0 个 4xx；原图请求是新接口，尺寸 640 × 480（不带边框）；复原后边框 none、时间戳关、裁剪 [0,0,1,1]、0°；复原后刷新仍是 640 × 480（之前是 692 × 532）。`visual_check.mjs` 在 1360 和 1024 两个宽度下，7 张边框缩略图都是 contain，显示为 156 × 116。截图：`research/review_studio_v2/ui-frame-settled-1360.png`、`ui-frame-settled-1024.png`、`ui-space-original.png`。
- **没有覆盖到的**：「详细信息」的折叠区在浏览器里还没有被触发过（后端还没返回 `detail`）；按住空格的退回路径（接口 404 时）只有代码，没有实测。
- **测试**：新增 5 组（原图接口与退回、复原写 off 值、纠正预览用 preview、缩略图 contain、错误的 detail）。`test_web_*.py`：55 通过，2 失败，失败原因见下。
- **2 个失败**：`test_plug_in_import_gallery_crop_export` 和 `test_raw_only_photo_says_no_raw_and_export_falls_back_to_neutral`。两者都在导出时打开合成 DNG，报 `no full-resolution CFA IFD`，路径是 `finish/serve.py`（未跟踪的后端新流水线，01:26 才被改过）。前端没有改动这条路径。上一次全量跑时这两项通过，所以这是后端工作区里的回归，需要后端修。

## 2f. 面板底部按钮固定（第八轮）

- **边框**：[设为默认] 固定在底边。
- **调整**：[重置] 固定在底边。
- **配方**：[存储为我的配方] [写入存储卡] 在左，[重置] 靠右，固定在底边（顺序按 COPY 3.3）。配方的底部行原来放在可滚动的旋钮区里面，固定不住，现在挂在面板下面。
- **时间戳**：没有底部按钮（COPY 3.5 没有写），这一轮没有加。如果要一个底部按钮，请告诉我写什么。
- **复验**：全新库、全新 profile，`cdp_bottom_v3`：三个面板的底部按钮在内容滚动后仍然在面板可视范围内，JS 错误 0。截图 `frame-foot-v3.png`、`adjust-foot-v3.png`、`recipe-foot-v3.png`（放进 screenshots/phase2/）。
- 测试：新增 `test_bottom_buttons_are_sticky_in_frame_adjust_and_recipe_panels`，`test_web_*.py` 共 52 项通过。

## 2e. 在访达中显示的接口和「推测」标签（第七轮）

- **接口**：`POST /api/exports/{export_id}/reveal`，请求体为空，不带路径。单张导出用响应里的 `export_id`，批量导出用任务的 `id`（`export.js` 的 `revealButton`）。非 macOS 时后端返回 501，前端把后端的话原样显示。
- **验证**：浏览器里包了一层 fetch，拦下 `/reveal` 请求（回 404 桩，不打开访达）。单张和批量的请求地址分别是导出响应的 `export_id` 和任务 id，请求体为空；后端对没有的导出编号返回 404。截图 `28-export-reveal-single.png`、`29-export-reveal-batch.png`。
- **「推测」标签**：后端已如实带出 `input_space_guessed`。LUT 流程里，存成「我的配方」的卡片上显示「推测」（截图 `21-lut-saved-card.png`）。
- **DELETE /edit**：保持现状，不需要后端改。
- 测试：`test_reveal_posts_to_the_export_id_with_an_empty_body` 新增，`test_web_*.py` 共 51 项通过。没有追加 COPY_DIFF（没有新文案；`REVEAL_URL` 常量换成了函数，不是文案）。
- 没有真正点「在访达中显示」去打开访达（会在你的 Mac 上弹出窗口）；真实打开需要你在本机点一下确认。

## 2d. 界面修整（第六轮）

- **边框页**：卡片改两列（`minmax(0, 1fr)`，随面板收缩），不再横向溢出；颜色只剩三个色块，颜色名放在提示里，选中的色块有外圈（文字按钮删掉）。
- **裁切页底部**：「自动、向左旋转、水平翻转、重置、完成」固定在面板底边（`.sticky-foot`），内容滚动时也完整可见。
- **拉直**：左边「拉直」、右边「+1.0°」，和垂直、水平同一排法。
- **参考线**：下拉框「三等分 ▾」，选项顺序关、三等分、网格、黄金比例、黄金螺旋、对角线（G 键循环也按这个顺序）。
- **尺寸**：面板里不再写；「4179 × 2775」放在画面右下角（按原图像素算）。
- **照片条**：「2026-10-23 17:41」。
- **导入提示条**：导入完成时只留结果和 [关闭]，「请先推出存储卡」删掉（状态栏的「存储卡：可以推出」保留）。
- **画面蒙灰**：不是加载遮罩，是每次渲染都做的 0.15 秒淡入，淡入期间整张画面（连白边）半透明。现在去掉淡入，渲染完成后画面的透明度就是 1（浏览器里量过）。
- **复验**：全新库、全新 profile，`cdp_ui_v2`：横向溢出 0、卡片越界 0、颜色文字按钮 0、底部按钮全部可见、面板里没有尺寸行、JS 错误 0。截图 `01-viewer-recipe-final-v2.png`、`24-fresh-frame-set-v2.png`、`25-fresh-crop-straightened-v2.png`（放进 screenshots/phase2/）。
- 测试：`test_web_*.py` 共 50 项通过（新增 3 组）。没有追加 COPY_DIFF（按要求，没有新文案）。

## 2c. 复原与各面板的重置（第五轮）

- **复原**（`viewer.js` 的 `resetAll`）：先写 edit（配方、调整、曲线、几何、边框、时间戳），再写 crop（整张、0°）。两个请求依次发，接口没改。
- **裁剪的还原**（`preview.js` 的 `resetCropRemote`）：角度明写 `angle_deg: 0`。PUT /crop 不带角度时会保持原角度。
- **各面板的重置**：配方只清旋钮，调整只清调整和曲线，裁剪只清几何和裁剪，时间戳只清指定日期。浏览器里逐个验证过，其余面板不动。
- **顺手修了两处**：拉直刻度的下一帧绘制在照片已经离开后还会报错（`correct.js`，现在先看还在不在）；裁剪的「W × H 像素」之前按预览图算，现在按原图算（`crop.js`，显示 4288 × 2848）。
- **浏览器验证**（全新库、全新 profile）：布置（边框、配方 05、曝光 +1、拉直 +1°、框缩小）→ 各面板重置 → 复原。JS 错误 0；复原后 edit 无配方、拉直 0、边框无，裁剪框是整张（100%），角度 0。截图 `27-restore-crop-full.png`。
- **测试**：新增 `test_restore_resets_edit_then_crop_and_each_reset_touches_only_its_panel` 和 `test_pixel_size_text_is_counted_on_the_original_frame`。`test_web_*.py` 共 47 项通过。

## 2b. 第四轮（COPY 3.12）和 P0 复验

- **在访达中显示**（3.6、3.12-1）：导出完成后（单张和批量）显示 [在访达中显示]，打开这次导出的第一张。按钮已按 3.6 写好；接口后端还在做，前端占位是 `POST /api/exports/reveal`，请求体 `{ path }`，定了改 `export.js` 的 `REVEAL_URL` 这一处。接口没接通时点了会提示「无法在访达中显示。请重试。」。
- **附录 4 条**（3.12-3）：「双击归零」→「双击重置」（controls.js）；「关掉这条提示」→「关闭」（import.js）；「导入结束」→「导入完成」（import_summary.js）；校准数据文件夹输入框去掉占位文字（camdata.js）。其余词沿用。
- **「推测」标签**（3.12-2）：前端已按 `input_space_guessed` 显示，等后端如实带出。
- **示意图的临时映射**（3.11-5）：后端已改成「示例照片」，映射已删（3.12-4）。
- **P0 复验**：全新临时库 + 全新 Chrome profile，不手工补宽高，流程是导入 → 设边框 → 打开裁剪 → 拉直 +1° → 改裁剪框但请求不带 `angle_deg`（200，角度保留为 1°）→ 删除编辑（200）→ 再打开裁剪（裁剪框和 1715 × 1139 正常显示）。JS 错误 0，没有错误提示。截图 24–26。
- **观察**：删除编辑后，裁剪框的位置还留着（0.1–0.9），角度清零。要不要后端在删除编辑时也清掉裁剪，请后端确认。
- 测试：`test_web_*.py` 共 45 项通过（新增 `test_section_3_12_wording`）。

## 2a. 第三轮（COPY 3.11）改动

- LUT 文件过大：恢复为「无法读取 LUT。文件过大。」（3.11-3，重试解决不了的错误，第二句写原因）。
- LUT 结果：不再显示后端的 `res.caution` 长句；相似度旁加「电脑预测」小标签（3.11-6）。
- 没有改动：`api.js` 的兜底「无法完成操作。请重试。」保留（3.11-4）；「示意图」的临时映射保留，等后端改完再删（3.11-5）；「仅电脑」只在旧版相机上打、删掉「项目文件夹」按钮，都是 3.11-1、3.11-2 同意的。
- 测试：`test_web_frontend.py` 新增 `test_section_3_11_lut_wording`，FORBIDDEN 加入「标准色块」。`ruff check`、`ruff format --check`、静态检查、`node --check` 通过；`test_web_*.py` 共 44 项通过。
- 没有重新跑浏览器和截图（按要求不用再截全套）。

## 3. 第一轮（COPY 3.9）改动（保留）

- 「再点一次：全部归零」→ 检查 `adjust.js` 里的「重置」；「存为我的配方（即将推出）」→「存储为我的配方」（同一断言块，没点名，特此说明）。
- `tests/test_web_smoke.py`：标题断言「GXR 电脑工作室」→「GXR Studio」。
- 只有 JPG 的照片：配方整块变淡（第二轮改为面板里写一行说明，见 §2）。
- 舞台图片不可见的问题（`.pv-img` 改为 `display: block`）已确认修复。

## 4. 完成项（按面板）

- **配方**：内置 8 个（沿用相机里的名字）、强度、旋钮（档位来自 `/api/recipes`）、重置（单击）。三态：`full`、`approx`、`none`。跨单元或跨 ISO 显示「未校准」，提示「使用 A12 50mm 的颜色模型」。「存储为我的配方」「写入存储卡」为置灰占位，后者提示「暂不支持写入存储卡」。
- **调整**：曝光、对比度、高光、阴影、黑点、色温、色调、饱和度、自然饱和度、暗角；曲线编辑（拖动时写工作副本，松手才保存）。新增的四项在旧后端显示「暂不可用」。
- **裁剪**：预设（常用、社交媒体两组）、横向/纵向、缩放、参考线（关、三等分、黄金比例、黄金螺旋、对角线、网格）。拉直 ±45°，后端返回的错误原样显示。垂直、水平、畸变、向左旋转、水平翻转、自动拉直、重置。裁剪框拖动和缩放都约束在有效画面内。旧后端只有拉直标尺，其余显示「……自动暂不可用」。
- **边框**：7 种样式；颜色（白、黑、米白）；宽度（细、中、粗）；显示（标志、参数、日期）；文字（最多 24 字）；画布比例；设为默认。帧号由样式自带，没有单独开关（3.9）。
- **时间戳**：开关；内容；4 种日期格式；显示时间；指定日期（可重置）；使用文件修改日期时的说明（3.9 的 `date_note`）；字体；颜色；大小；位置；发光。
- **导出**：格式 JPEG、品质、尺寸、导出到、文件名「原名_gxr.jpg」。按钮「导出」「取消」；进度、完成、取消、失败句子按 3.6 和 3.9。
- **导入与图库**：空状态；导入进度、完成、取消、中断、磁盘空间不足、找不到存储卡；存储卡状态。
- **相机配方文件与校准数据**：引导句（3.9）；校准不匹配时主句是「校准数据与相机配方文件不匹配」，文件名和 SHA-256 收进「详细信息」。
- **LUT**：导入、推测空间、生成配方、存储为我的配方、我的配方列表（重命名、删除）。
- **设置与快捷键**：`?` 打开快捷键表；设置里有「校准数据文件夹」。
- **配色**：深色默认，跟随系统浅色，`data-theme` 可强制。
- **降级**：旧后端（新接口 404）时新功能显示「暂不可用」，旧功能照常。

## 5. 文件清单

新增（`studio/web/assets/`）：`caps.js`、`controls.js`、`correct.js`、`finish.js`、`frame_panel.js`、`geom.js`、`stage.js`、`stamp_panel.js`。

修改（`studio/web/`）：`index.html`、`assets/adjust.js`、`api.js`、`app.js`、`app.css`、`camdata.js`、`caps.js`、`correct.js`、`controls.js`、`crop.js`、`export.js`、`gallery.js`、`import.js`、`import_summary.js`、`look_notes.js`、`lut.js`、`onboarding.js`、`preview.js`、`recipes.js`、`stage.js`、`viewer.js`。`dom.js` 在工作区里也有改动，本轮没有动它。

测试：`tests/test_web_frontend.py`（新，纯函数和 COPY 硬规则）；`tests/test_web_smoke.py`、`tests/test_web_m2_smoke.py`（只改了旧文案断言）。

研究目录（`research/studio_v2/ui/`）：`COPY_DIFF.tsv`（第一轮对 HEAD 生成，第二轮的行追加在末尾）、`COPY_GAPS.md`（已落实、需要裁定、后端问题、未覆盖字符串附录）、本文件、`screenshots/phase2/`（25 张截图）。

## 6. 测试命令与结果

所有命令在 `studio/` 下执行。临时文件放在 `/Volumes/Workspace/Scratch/tmp/projectricoh/studio-v2-frontend/`（`TMPDIR`、`--basetemp`、Chrome 用户目录）。

| 命令 | 结果 |
| --- | --- |
| `uv run --frozen ruff check tests/` | All checks passed! |
| `uv run --frozen ruff format --check tests/` | 34 files already formatted |
| `uv run --frozen pytest tests/test_web_frontend.py tests/test_web_m2_smoke.py tests/test_web_smoke.py -q -p no:cacheprovider --basetemp=…/pytest` | 45 passed（第四轮后；第三轮是 44，第二轮是 43） |
| `uv run --frozen pytest tests/test_import_summary.py tests/test_fix_review.py tests/test_polish_p2.py tests/test_crop_guides.py -q`（附带，相关的后端文案测试） | 82 passed |
| `node --check` 各 `web/assets/*.js` 副本 | 通过 |
| 静态检查（`copy-pass/check_modules.py`，临时工具，不在交付里） | check ok |

注意：`tests/test_import_summary.py` 在第二轮开始前有 5 个断言失败（第 74 行的「未全部导入」、第 111 行的多卡名单），这两处是旧文案。之后它们已经被人改成 3.10 的写法（不是前端改的），现在 82 项全部通过。

### 浏览器验证（临时实例 `127.0.0.1:18767`，每次全新 Chrome profile）

| 脚本 | 结果 |
| --- | --- |
| `cdp_app.mjs`（主流程，`app-run-r9.log`） | `errors: []`。撤销：没有内容时 `aria-disabled="true"`，改动后为空。调整标题没有标签。导出面板没有「精确」和「导出内容」。只有 JPG：面板写「配方需要 RAW 文件」和「拍摄时将画质设为 RAW+JPEG」，8 个内置配方置灰，旋钮变淡，点击闪一下说明行。设置：「校准数据文件夹」标签；没有「项目文件夹」按钮；重建索引后提示「已重建索引」 |
| `cdp_degraded.mjs`（旧后端模拟，`degraded-run-r10.log`） | `errors: []`。新功能显示「暂不可用」；只有 JPG 的配方说明和置灰；只有 JPG 的调整可以保存，成片预览出图 |
| `cdp_legacy.mjs`（页面里把相机配方文件代数改成 131，`legacy-run.log`） | `errors: []`。对比度、高光、阴影、饱和度的滑块最大档为 `max=10`（11 档，即 ±5）；褪色、色温、色调、分离色调打「仅电脑」；没有「相机」标签。这是在浏览器里模拟的旧代数，真实的旧版相机配方文件没有测到 |
| `cdp_lut.mjs`（LUT 流程，`lut-run-r14.log`） | `errors: []`。导入文件名带 slog3 的 `.cube`：「输入色彩空间」旁是「推测」小标签，提示为「按文件名判断：文件名/标题里有“slog3”」。生成配方得到「色差 2.67」「大致」；存储后提示「已存储为「我的配方 1」」；删除确认是「删除「我的配方 1」？」，按钮 [取消] [删除]；确认后删除成功 |

第三轮起，LUT 结果不再显示后端的说明长句（`res.caution`，3.11-6），相似度旁是「电脑预测」小标签。

## 7. 已知问题

1. **P0：sidecar 的 `frame` 键冲突（后端，已修，第四轮复验通过）。** `sidecar.py:47` 把图像尺寸存成 `frame: {orientation, width, height}`，边框设置（`PUT /api/photos/{id}/edit` 的 `frame`）存的也是 `frame`，整块覆盖后尺寸丢失。之后 `GET /api/photos/{id}/crop` 返回 422 `no_frame_size`，界面显示「这张照片的尺寸未知，暂时不能裁剪」。本轮每次浏览器测试之前都手工把两张样本照片的宽高补回（4288 × 2848），只改了临时库，不是产品改动。后端已接收。
2. `DELETE /api/photos/{id}/edit` 和 `DELETE /api/photos/{id}/crop` 同样会清掉尺寸。前端已改用 `PUT` 回到原始状态（`preview.js` 里有注释）。
3. `PUT /crop` 不带 `angle_deg` 时拉直会被归零。前端每次都带上。后端已接收。
4. 只有 JPG 的照片：`/capabilities` 返回 `recipe: none`，选配方返回 409 `no_raw`。前端已置灰并显示说明行。
5. `/assets/*` 没有 `Cache-Control`，浏览器可能用旧的缓存脚本。本轮排查时，旧 profile 就出现过这种情况。后端已接收。改了前端后请强制刷新（⌘⇧R）。
6. 第 121 代相机配方文件的报错是四句话，按 3.10 需要改成「不支持第 121 代相机配方文件。请使用第 127 代或更新的版本。」。后端已接收。
7. 预览标签「示意图」由后端返回（`api/lut_routes.py:126`），前端临时映射成「示例照片」。
8. 「存储为我的配方」保存的卡片，后端的 `input_space_guessed` 对文件名猜出的空间为 false，所以卡片上没有「推测」标签（COPY_GAPS.md §2 第 6 项）。

## 8. 截图

- 交付副本：`research/studio_v2/ui/screenshots/phase2/`（25 张）。
- 原始文件：`/Volumes/Workspace/Scratch/tmp/projectricoh/studio-v2-frontend/shots/`。

| 文件 | 内容 |
| --- | --- |
| 01-viewer-recipe-final.png | RAW 照片，配方标签（全模式，旋钮不打「相机」标签） |
| 02-crop-uncropped.png | 裁剪，未裁切画面和裁剪框 |
| 03-crop-angle-fit.png | 拉直 +14°，裁剪框收进有效画面 |
| 04-frame-cards.png | 边框样式卡片 |
| 04b-stamp-panel.png | 时间戳面板 |
| 05-export-done.png | 导出完成 |
| 05a-export-panel.png | 导出面板：没有「精确」和「导出内容」 |
| 06-jpg-only-adjust.png | 只有 JPG：调整可以保存 |
| 06a-jpg-recipe-notice.png | 只有 JPG：「配方需要 RAW 文件」，内置配方和旋钮置灰，撤销置灰 |
| 07-gallery.png | 图库 |
| 08-light-viewer.png | 浅色配色 |
| 10–14（degraded-*） | 降级：配方、裁剪、边框、时间戳、调整的「暂不可用」 |
| 15-degraded-jpg-recipe.png | 降级下只有 JPG 的配方说明和置灰 |
| 16-degraded-jpg-adjust.png | 只有 JPG：调整后成片预览 |
| 17-settings-calibration.png | 设置：「校准数据文件夹」标签 |
| 18-rebuild-toast.png | 重建索引后的「已重建索引」 |
| 19-lut-space-guess.png | LUT：「输入色彩空间」旁的「推测」小标签，预览标签「示例照片」 |
| 20-lut-result.png | LUT 拟合结果 |
| 21-lut-saved-card.png | 存储后的「我的配方」卡片 |
| 22-recipe-delete-confirm.png | 删除确认：「删除「名称」？」[取消] [删除] |
| 23-legacy-recipe-knobs.png | 旧版相机（第 131 代，浏览器中模拟）：新四项不打标签，褪色、色温等打「仅电脑」 |

第四轮新增（全新临时库的复验流程）：`24-fresh-frame-set.png`（设边框后）、`25-fresh-crop-straightened.png`（拉直后）、`26-fresh-crop-reopened.png`（删除编辑后再打开裁剪）。

## 9. 临时实例与清理

- 临时实例（`127.0.0.1:18767`，临时库 `run/lib6`）：测试结束后已停止（PID 98275，`gxr-studio --no-browser --port 18767`）。
- Chrome 调试端口 9333：已关闭，本轮的 Chrome profile（`chrome-profile*`）已删除。
- 第四轮的复验用的是另一个临时实例（全新临时库 `run/lib7`，PID 34696），测试后已停止，Chrome 和 `chrome-profile-fresh` 已关闭、删除。
- 没有碰 `127.0.0.1:49667` 和 `~/Pictures/GXR Studio`。导出测试写到了临时的导出目录。
- 脚本和运行记录保留在 scratch 目录，便于复现；不属于交付物。

## 10. 没有覆盖的部分

- 没有跑全量 `make check` 或全部测试，只跑了 `test_web_*.py` 和附带的 4 个相关后端测试。
- 旧版相机配方文件只在浏览器里用「第 131 代」模拟，没有用真实的旧版文件测试。
- LUT 结果里「接近 04 标准」的分支没有遇到（这次的结果是「大致」），只做了代码检查。
- 没有在真实相机上验证，本轮只验证界面和接口的对接。
- COPY_GAPS.md §2 的 7 项需要你裁定，裁定之前前端保留现有文字。
