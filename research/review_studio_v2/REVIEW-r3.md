不能交付

验收对象是 `studio` 仓库基线 `e6952acb89de95e089c8e7080c5d92de99057cc4` 上的未提交工作区，日期为 2026-10-31。第二轮待复验的 19 项中，13 项已关闭、6 项部分关闭。新增及扩展反例共 3 项，其中 1 项 P1、2 项 P2，未发现 P0 原文件损坏。

交付阻塞是 R3-01：零编辑竖拍照片选择导出尺寸后仍会丢失方向。原始尺寸导出已修好；长边 2048、4096 以及直接指定 512 的分支仍失败，JPG 和 RAW+JPG 都受影响。另有长时间戳在缩略图上截字、非法参数文案未统一两个 P2。

主机已证：`make check` 为 496 passed、覆盖率 91.24%，其中 `test_web*` 共 61 项通过。源码隔离检查为 358 passed、138 skipped、87.74%；缺系统字体模拟为 357 passed、139 skipped、87.72%。85% 门槛没有降低。218 项产品文件的开验和收尾哈希相同，未改产品代码，没有 Git 写操作。首次质量检查更新了指定临时目录之外的工具缓存，执行偏差单列在第 7 节，不能声称本轮完全满足临时写入边界。

## 1. 第二轮部分关闭的 V2 项

| 编号 | 状态 | 本轮结果与证据 |
| --- | --- | --- |
| V2-01 | 已关闭 | 未选配方的 RAW+JPG 从实际界面单张、批量导出都发送 `source=auto`，产物为 `camera-jpg`。调整、曲线、配方、装饰均进入导出，34 个可渲染组合的 full 与导出尺寸相同。见 [矩阵](r3-evidence/matrix-r3.json)、[单张界面](r3-evidence/ui-regression-r2.json)、[批量界面](r3-evidence/ui-extra-r3.json)。方向残留单列 R3-01。 |
| V2-03 | 已关闭 | 640×480 和 1600×1200 的 10 组几何画布尺寸全部与实际 warp 相同，保存框内无效像素均为 0。1600×1200、垂直 +80 为 1794×1217，畸变 +70 为 1352×1098；旋转后的 API frame、uncropped 和方形裁剪也一致。见 [几何蒙版](r3-evidence/geometry-r2.json)、[API 几何结果](r3-evidence/acceptance.json) 的 `geometry`。 |
| V2-08 | 已关闭 | 界面复原后明确保存 none/false，成片回到 640×480。原先继承的照片撤销后 frame/stamp 回到 null；修改默认值并刷新后变为 640×544。原先明确关闭的照片，复原、撤销和更换默认值后仍为 none/false、640×480。见 [界面状态](r3-evidence/ui-extra-r3.json) 的 8 个 `states`、[API 状态](r3-evidence/default-states-r3.json)。 |
| V2-12 | 部分关闭 | 日期、时间和 24 字拼接不再截短，4 种日期格式与时间开关的 8 组检查全部保留全文，480×640 的实际排版也在画布内。但 192×256 的图库缩略图仍截掉后缀，见 R3-02、[字形边界](r3-evidence/stamp-r3.json)、[HTTP 后缀反例](r3-evidence/stamp-http-r3.json)。 |
| V2-15 | 已关闭 | 真实垂直滑块松手到最终图像显示，5 次中位 0.646 秒，范围 0.613–0.647 秒。均为 preview 尺寸，保存和图像请求成功，显示图像的原生 fetch 来源参数与保存值一致。见 [计时](r3-evidence/ui-latency-r3.json)、[锁跟踪](r3-evidence/lock-trace-r2.json)。 |
| V2-17 | 部分关闭 | 前后端文案审计已重跑，前端 443 条中文字符串无禁用术语候选。运行时机器标签和导出错误已修；39 个非法参数请求仍有 5 个主句不符合 COPY 3.13-2，见 R3-03、[API 结果](r3-evidence/copy-api-r3.json)、[全文清单](r3-evidence/COPY_VIOLATIONS-r3.tsv)。 |
| V2-18 | 已关闭 | 导出 JSON 的 `render_label` 为机器枚举，另有 `render_text`；运行时 OpenAPI 与文件相同。成片响应带机器标签和校准位，实际界面显示“电脑预测”“未校准”，没有 original/prediction 原文。见 [API 验收](r3-evidence/acceptance.json) 的 `openapi`、[界面结果](r3-evidence/ui-regression-r2.json) 的 `predictionBadge`。 |
| V2-19 | 部分关闭 | 自动建议、画布尺寸、竖拍帮助函数和字体可移植性已有测试，质量门禁通过。但 `tests/test_finish.py:211` 的时间戳渲染断言仍只要求画面变化，方向测试只直接调用 `write_with_exif`，未覆盖实际带尺寸参数的导出。现有断言没有拦住 R3-01、R3-02。见 [检查日志](r3-evidence/make-check.log)、[字形边界](r3-evidence/stamp-r3.json)、[尺寸导出](r3-evidence/matrix-r3.json)。 |
| V2-20 | 已关闭 | 源码隔离目录没有相邻 firmware、captures、research，覆盖率 87.74%；整套缺字体模拟也过 85%，不是只跑一个测试。见 [portable 结果](r3-evidence/portable.json)、[缺字体结果](r3-evidence/portable-no-cjk.json) 及各自日志。未运行 Linux CI 或重新安装依赖。 |

## 2. R2-01 到 R2-10

| 编号 | 状态 | 本轮结果与证据 |
| --- | --- | --- |
| R2-01 | 已关闭 | 实际单张与批量请求均为 auto。未选配方的 RAW+JPG 导出 `camera-jpg`、`original`；有配方时矩阵返回 prediction。见 [单张](r3-evidence/ui-regression-r2.json)、[批量](r3-evidence/ui-extra-r3.json)、[矩阵](r3-evidence/matrix-r3.json)。 |
| R2-02 | 部分关闭 | 非对称 Orientation=6 的零编辑 JPG，原始尺寸导出已为 480×640、Orientation=1；选择长边 512/2048/4096 后仍失败，RAW+JPG 相同，见 R3-01。见 [尺寸反例](r3-evidence/matrix-r3.json) 的 `sized_orientation`、[实际界面](r3-evidence/ui-extra-r3.json) 的 `portraitExport`。 |
| R2-03 | 已关闭 | 超过 1200 像素的画布不再放大固定留量，10 组输出尺寸和蒙版核对全部通过。见 [geometry-r2.json](r3-evidence/geometry-r2.json)。 |
| R2-04 | 部分关闭 | 原来的格式化截字已修，8 组格式都保留 24 字；实际缩略图在最小字号处仍放不下全文。原始原因已修，用户仍能遇到截字结果，见 R3-02、[格式与边界](r3-evidence/stamp-r3.json)、[HTTP 反例](r3-evidence/stamp-http-r3.json)。 |
| R2-05 | 已关闭 | 实际成片状态为“电脑预测 / 未校准 / 成片”；原图不显示机器枚举。见 [界面记录](r3-evidence/ui-regression-r2.json)、[截图](r3-evidence/ui-prediction-label-r2.png)。 |
| R2-06 | 已关闭 | 单张导出到图库时，界面保留后端主句与 1 个默认收起的详细信息。批量两张失败时，逐项保留照片名、原因及 2 个默认收起的详情。成功批量两张均完成。见 [单张记录](r3-evidence/ui-regression-r2.json)、[批量记录](r3-evidence/ui-extra-r3.json)、[批量截图](r3-evidence/ui-batch-errors-r3.png)。 |
| R2-07 | 部分关闭 | 原 35 个请求中的 34 个已统一；quality=29 的预览仍返回专用主句。扩展的 4 个非法导出参数也未统一，均正常返回 422，见 R3-03、[39 项记录](r3-evidence/copy-api-r3.json)。 |
| R2-08 | 已关闭 | portable 测试使用随仓库提供的字体子集及许可。测试进程清空产品字体候选，同时让系统字体路径的 `is_file` 返回 false，整套源码隔离测试 357 passed、139 skipped、87.72%。额外跳过的是 macOS 系统字体集成检查。见 [模拟脚本](r3-evidence/r3_no_cjk.py)、[日志](r3-evidence/portable-no-cjk.log)。这是本机模拟，不是 Linux 实跑。 |
| R2-09 | 已关闭 | “复原→撤销”恢复 frame/stamp 的 null 继承状态；默认改成新边框后成片为 640×544。明确关闭分支始终保留 none/false。见 [界面状态](r3-evidence/ui-extra-r3.json)。 |
| R2-10 | 已关闭 | 松手到最终显示 5 次全部低于 1.5 秒。独立锁跟踪中，fitted_crop 尚在运行时，预览 get_shot 只等待 0.00006 秒，保存和预览都为 200。见 [正式计时](r3-evidence/ui-latency-r3.json)、[锁跟踪](r3-evidence/lock-trace-r2.json)。 |

## 3. 新问题与扩展反例

| 编号 | 严重度 | 文件:行 | 说明与证据 | 建议 |
| --- | --- | --- | --- | --- |
| R3-01 | P1 | [finish/serve.py:388](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio/src/gxr_studio/finish/serve.py:388)、[export.py:283](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio/src/gxr_studio/export.py:283) | R2-02 的尺寸分支仍丢失方向。Orientation=6、存储像素 640×480 的零编辑 JPG，预览为 480×640；long_edge=512 导出 512×384，正确应为 384×512。2048、4096 即使不用缩小，也导成 640×480、Orientation=1。JPG 与 RAW+JPG 各 3 个尺寸反例，实际界面点“长边 2048 像素”也复现。`_decode` 先忽略 EXIF 方向，重新编码后方向已丢，后面的 exif_transpose 无法补救。见 [矩阵](r3-evidence/matrix-r3.json)、[截图](r3-evidence/ui-portrait-sized-export-r3.png)、[实际错误产物](r3-evidence/orientation-wrong-export-r3.jpg)。 | 在尺寸处理前按数据自身的 EXIF 转正像素，再缩放和编码；让原始尺寸与指定长边共用方向处理。用非对称 Orientation=6 输入覆盖实际 API 和界面的尺寸选择，包括尺寸大于原图的情况。 |
| R3-02 | P2 | [finish/stamp.py:143](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio/src/gxr_studio/finish/stamp.py:143)、[finish/stamp.py:149](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio/src/gxr_studio/finish/stamp.py:149) | R2-04 的格式化截字已修，绘制阶段仍在缩略图上截字。合法的日期+时间+24 字中文在 192×256 画布上缩到 8 像素后，字形右界为 274，仍直接绘制。真实 HTTP 中，仅将末尾“北京”改为“上海”，图库缩略图和样式缩略图逐像素相同，预览和导出则不同，证明尾字没有画进缩略图。见 [边界记录](r3-evidence/stamp-r3.json)、[HTTP 记录](r3-evidence/stamp-http-r3.json)、[缩略图](r3-evidence/stamp-http-gallery_thumb-r3.png)。 | 让字号与边距随缩略图尺寸缩放，或先在能容纳全文的画布上排版再缩小。检查完整字形边界，并用同长度不同后缀的文字核对缩略图、预览和导出。 |
| R3-03 | P2 | [api/render_routes.py:170](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio/src/gxr_studio/api/render_routes.py:170)、[export.py:69](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio/src/gxr_studio/export.py:69)、[export.py:71](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio/src/gxr_studio/export.py:71) | R2-07 仍有一个原反例和四个扩展反例。预览 quality=29，导出 quality=0/101、long_edge=63/30001，仍返回专用主句。前端预览没有该品质输入，导出滑块限制 60–100，尺寸只有原始/2048/4096，因此这些值都属于 COPY 3.13-2 的“界面上点不到的错误”。5 项均为 422；导出 4 项还没有 detail。见 [39 项结果](r3-evidence/copy-api-r3.json)、[逐项字符串](r3-evidence/COPY_VIOLATIONS-r3.tsv)。 | 在这些 API 参数边界统一返回“请求无效。请刷新页面后重试。”，把具体范围放到 detail。保留 COPY 明文允许的例外。 |

## 4. 统一流水线与旧图库回归

[矩阵](r3-evidence/matrix-r3.json) 共 36 个组合：真实 GXR 横幅输入和非对称 Orientation=6 合成竖幅输入，各覆盖 RAW、JPG、RAW+JPG，以及零编辑、调整、配方、装饰、旋转、组合编辑。两项 JPG 配方请求按能力限制拒绝，其余 34 项均成功读取 preview、full、图库 thumb 并导出。这里只把合成 DNG 用作方向和流水线夹具，不当作真实相机拍摄证据。

| 输入 | 零编辑 | 调整 | 配方 | 装饰 | 向左旋转 |
| --- | --- | --- | --- | --- | --- |
| 真实 RAW-only | 04 标准，4288×2848 | 生效 | 08 生效，完整尺寸 | 生效，4632×3192 | 2848×4288 |
| JPG-only | 相机 JPG，640×480 | 生效 | 不可用，409 | 生效，692×532 | 480×640 |
| 真实 RAW+JPG | 相机 JPG，4288×2848 | 生效 | RAW 08 生效 | 生效，4632×3192 | 2848×4288 |
| 合成竖幅 RAW / JPG / RAW+JPG | 原始尺寸导出均为 480×640 | 方向正确 | RAW 两项方向正确，JPG 不可用 | 方向正确 | 均为 640×480 |

34 项 full 与导出尺寸全部相同。按同一目标尺寸缩小后，preview/export 的平均 ΔE00 最大为 0.9287，full/export 最大为 0.2065，thumb/export 最大为 2.6290；这些是本组输入在缩放与 JPEG 编码后的实测差异，不表示逐像素相等。指定长边的竖幅零编辑反例不在上述原始尺寸通过范围内，见 R3-01。长时间戳也未满足三处显示一致，见 R3-02。

第一版图库由本轮 `git show e6952ac` 取出的源码重新创建，基线模块路径记录在 [baseline-fixture.json](r3-evidence/baseline-fixture.json)。5 张照片、7 个媒体文件，首次打开时 5 份 sidecar 内容相同、媒体哈希相同，GET edit/crop 正常。旧 RAW 的配方 08、旋钮记忆、调整和曲线保留，重存裁剪仍保留 +3.5°，导出 640×640；旧 JPG 保留 −2°和调整，可导出 360×640。见 [acceptance.json](r3-evidence/acceptance.json) 的 `v1_open` 和两个 `v1_write_export_*`。

还复跑了默认装饰缓存、原图比较、导出 EXIF、有效区域、样式卡片布局和 Finder 路径登记检查。默认值改变后缩略图 URL 和内容均改变；未知导出、目录外链接、同目录替换链接均拒绝，授权的一次真实“在访达中显示”返回 200。见 [acceptance.json](r3-evidence/acceptance.json)、[focused.json](r3-evidence/focused.json)、[visual-check.json](r3-evidence/visual-check.json)。

## 5. 滑块耗时与文案审计

正式计时在质量检查和矩阵结束后单独运行，10 逻辑核机器另有任务，1 分钟 load average 为 4.01–4.77。输入为真实 RAW+JPG、未选配方，底图为相机 JPG，与第二轮滑块场景一致。五次垂直值依次为 13、15、17、19、21。

| 次数 | 松手到最终显示 | 保存 | 显示图像来源核对 |
| --- | --- | --- | --- |
| 1 | 0.6132 秒 | 200 | 通过 |
| 2 | 0.6470 秒 | 200 | 通过 |
| 3 | 0.6460 秒 | 200 | 通过 |
| 4 | 0.6372 秒 | 200 | 通过 |
| 5 | 0.6469 秒 | 200 | 通过 |

计时起点是浏览器 pointerup，终点是最终可见图像的 load 后两个动画帧；后续等待保存与 networkidle 用来核验结果，没有计入显示耗时。观察脚本记录原生 fetch 返回 Blob 的来源、状态、参数和哈希，核对保存值，未改产品文件。独立 profile 不计入五次计时：渲染约 0.431 秒，其中几何 warp 为 0.213 秒、相机 JPG 读取与缩小为 0.157 秒，当前主要成本是重采样和图像读取。见 [计时原始记录](r3-evidence/ui-latency-r3.json)、[profile](r3-evidence/preview-profile-r3.txt)。

计时脚本的早期尝试有动态图像节点、已释放 Blob URL 和响应关联失败，均单独保留在 attempt 文件中，没有当作产品故障或混入五次结果。正式观察改为记录最终可见 Blob 的原生 fetch 来源。另修正了批量按钮选择器歧义，并在默认状态检查中等待预览稳定；产品代码没有因此改动。见 [观察假设与诊断](r3-evidence/latency-harness-premise.txt)。

`copy_audit.py` 原样复跑抽取 140 个错误表达式、16 个候选；其中 15 个是上一轮脚本写死行号的人工项，不能照搬旧评语。清空旧行号表后剩 1 个动态 fallback 候选，沿调用链检查未确认新的可达文案缺陷。补充脚本另抽取前端 443 条中文字符串与 14 个后端状态字段，前端禁用术语候选为 0。实际界面验证标签、单张与批量错误；39 个非法参数补测留下 R3-03 的 5 项。见 [原审计日志](r3-evidence/copy-audit.log)、[复核库存](r3-evidence/copy-r2-inventory.json)、[补测结果](r3-evidence/copy-api-r3.json)。不能用静态审计返回 0 代替这些运行时反例。

## 6. 复跑命令

所有脚本中的临时根目录均固定为本轮 Scratch。先把本报告旁的证据脚本复制进去。使用仓库现有锁定虚拟环境，不安装依赖、不运行 setup。

```bash
STUDIO=/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio
REVIEW_TMP=/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-v2-r3
EVIDENCE=/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_v2/r3-evidence
export TMPDIR="$REVIEW_TMP" PYTHONDONTWRITEBYTECODE=1
export XDG_CACHE_HOME="$REVIEW_TMP/cache"
mkdir -p "$REVIEW_TMP/evidence"
cp "$EVIDENCE/"*.py "$EVIDENCE/"*.mjs "$REVIEW_TMP/evidence/"
cd "$STUDIO"

# 完整检查。run_checks.py 使用 Scratch 中的 Makefile 副本，
# 只增加 import-linter 缓存目录和 pylint --persistent=n，检查与 85% 门槛不变。
.venv/bin/python -B "$REVIEW_TMP/evidence/run_checks.py"
.venv/bin/python -B "$REVIEW_TMP/evidence/portable_check.py"
.venv/bin/python -B "$REVIEW_TMP/evidence/portable_check_no_cjk.py"

# 基线重新造库；acceptance.py 会真实调用一次 Finder。
.venv/bin/python -B "$REVIEW_TMP/evidence/baseline_fixture.py"
.venv/bin/python -B "$REVIEW_TMP/evidence/acceptance.py"
.venv/bin/python -B "$REVIEW_TMP/evidence/geometry_r2.py"
.venv/bin/python -B "$REVIEW_TMP/evidence/stamp_r3.py"
.venv/bin/python -B "$REVIEW_TMP/evidence/copy_audit.py"
.venv/bin/python -B "$REVIEW_TMP/evidence/copy_r2.py"

# 在另一终端、使用同一 TMPDIR 启动临时实例；不使用正式实例。
.venv/bin/python -B "$REVIEW_TMP/evidence/temp_server.py"
```

临时实例启动完成并生成 `server-ready.json` 后，在原终端顺序执行：

```bash
.venv/bin/python -B "$REVIEW_TMP/evidence/matrix_r3.py"
node "$REVIEW_TMP/evidence/ui_latency_r3.mjs"
.venv/bin/python -B "$REVIEW_TMP/evidence/http_suite_r3.py"

# 停止临时实例后运行锁与 profile 诊断。
.venv/bin/python -B "$REVIEW_TMP/evidence/lock_trace_r2.py"
```

完整检查、portable 和成组回归的外层超时为 1800 秒，完整检查实耗 373.54 秒；修正缓存参数后的两个静态命令另跑通过，未重复全套测试。源码隔离的标准、缺字体两次分别耗时 64.22、63.83 秒。Playwright 为固定 1.61.1，Chromium Headless Shell revision 1228，所有浏览器启动均调用 `launchPinnedChromium`；实际 user-data-dir 位于本轮 Scratch，见 [进程记录](r3-evidence/browser-process.json)。

## 7. 执行偏差与收尾

首次 `make check` 的验收包装脚本漏掉 import-linter 和 pylint 的缓存参数，04:16 更新了以下既有工具缓存。这是验收执行偏差，不是产品问题；产品文件清单不包含这些缓存，因此“218 项产品文件未变”不能证明全部写入都在 Scratch。

- `studio/.import_linter_cache/b8d11fd27c2119d3b5d573dfcf0374971ffd59b0.data.json`。
- `studio/.import_linter_cache/gxr_studio.meta.json`。
- `/Users/wu/Library/Caches/pylint/gxr_studio_1.stats`。

没有开验前的缓存副本，无法恢复原内容，也没有删除共享缓存。后续以 `lint-imports --cache-dir=<Scratch>/imports` 和 `pylint --persistent=n` 复跑相关检查通过，三份既有缓存的哈希和修改时间没有再变；交付的 `run_checks.py` 已加入同样参数，首次脚本另存为 `run_checks_first_r3.py` 供追溯。见 [偏差记录](r3-evidence/cache-fence-deviation.json)、[修正后复跑](r3-evidence/cache-redirect-run.json)。

临时实例和本轮 Chromium 已关闭，本轮 Scratch 与两轮遗留的 Scratch 验收目录已删除。没有读写真实图库、访问 127.0.0.1:49667 或存储卡；正式实例未操作。218 项产品文件、7 个基线媒体文件及两份相机配方文件输入哈希未变，原 23 份 R2 脚本哈希未变。见 [最终完整性](r3-evidence/final-integrity-r3.json)、[清理记录](r3-evidence/cleanup-r3.json)、[持久证据清单](r3-evidence/EVIDENCE-SHA256.json)。
