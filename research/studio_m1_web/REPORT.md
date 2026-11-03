可以交复审

# studio-m1-web-r1 报告（GXR 电脑工作室 M1 前端）

实现 `research/studio_design/ARCHITECTURE.md` §14 的 S3：导入、图库、大图、裁切、导出，外加占位的配方/调整/相机页。
前端是纯 ES 模块，没有构建、没有 JS 依赖、没有外部资源（`studio/web/`）。
界面按 `UX.md` 与 `prototype.html` 的配色和流程做，冲突处以 `DECISIONS.md` 为准。

## 1. 交付物

| 路径 | 内容 |
|---|---|
| `studio/web/index.html` | 页面外壳：顶栏（照片 / 配方 / 相机）、横幅、提示条、视图、状态栏 |
| `studio/web/assets/app.css` | 暗色主题（颜色取自 prototype.html） |
| `studio/web/assets/app.js` | 启动、路由（`#/photos`、`#/photo/<id>`、`#/recipes`、`#/camera`）、全局快捷键、定时刷新 |
| `studio/web/assets/api.js` | 接口调用的唯一入口，错误统一成 `ApiError` |
| `studio/web/assets/state.js` `dom.js` | 共享状态与事件；小型 DOM 工具（`h()`、弹窗、提示、格式化） |
| `studio/web/assets/import.js` | 插卡发现、自动导入、轮询进度、横幅汇总、状态栏 |
| `studio/web/assets/gallery.js` | 图库：日期筛选、角标、多选、导出选中的 |
| `studio/web/assets/viewer.js` | 大图：左右切换、四个标签、撤销、还原原图 |
| `studio/web/assets/crop.js` | 裁切：比例、拖动位置、框的大小、拉直、还原、XPan 建议 |
| `studio/web/assets/export.js` | 导出表单（一张同步、多张后台任务轮询）、RAW-only 说明 |
| `studio/web/assets/onboarding.js` | 三张新手引导卡、标签第一次出现的提示、快捷键表、设置 |
| `studio/tests/test_web_smoke.py` | 9 个 pytest 冒烟测试（见第 3 节） |
| `research/studio_m1_web/MANUAL_CHECKLIST.md` | 手动检查清单（浏览器里逐项核对） |
| `research/studio_m1_web/browser_walkthrough.mjs` | 浏览器走查脚本（真实鼠标和键盘事件，见第 4 节；不属于 pytest） |
| `research/studio_m1_web/screenshots/` | 两张截图：图库、大图裁切 |
| `research/studio_m1_web/SHA256SUMS` | 以仓库根为基准的校验和 |

**后端：没有改 `studio/src/`。** 前端需要的接口都已经存在（`studio/README.md` 的接口表）。
没有 git commit；没有碰相机；没有启动子代理；没有联网；没有访问 `/Volumes/RICOHDCX` 或其他真实卡。

## 2. 对照任务要求

| 要求 | 结果 | 说明 |
|---|---|---|
| 插卡导入：横幅写「只读」，进度轮询，汇总（新增 / 跳过 / 读不出来），提示可以安全弹出 | 完成 | 走查中汇总为「新增 15 张，跳过 1 张，读不出来 0 张」，与接口一致。「跳过」= `seen_shots + duplicate_shots` |
| 图库按日期、可筛选；角标 DNG+JPG / 只有 JPG / 只有 DNG；多选；导出选中的 | 完成 | 角标三种都在走查中出现 |
| 大图左右键切换 | 完成 | |
| 裁切：比例（XPan 65:24、3:2、4:3、1:1、4:5、16:9、自由）；16:9 建议 XPan；拖动位置；拉直；还原；写进 sidecar | 完成 | 「自由」只能拖动和缩放，不能拖四个角（任务没要求） |
| 导出：尺寸、质量、进度、默认「原名_gxr.jpg」；只有 RAW 时用大白话说明 | 完成 | 导出弹窗和导出标签共用同一个表单 |
| 暗色、中文大白话、快捷键与 UX.md 一致、新手引导、M2/M3 占位标「即将推出」 | 完成 | 快捷键表与 UX.md §7 一致 |
| 假卡跑起来 | 完成 | `synthetic_card` 生成的假卡，`GXR_STUDIO_VOLUMES` 等指向临时目录 |
| 冒烟测试（不依赖浏览器） | 完成 | `studio/tests/test_web_smoke.py` |
| 手动检查清单 | 完成 | `MANUAL_CHECKLIST.md` |

## 3. 测试结果

```
$ cd studio && uv run pytest -q tests/test_api.py tests/test_crop.py tests/test_import.py tests/test_security.py tests/test_web_smoke.py
82 passed in 34.30s          （原有 73 个 + 新增 9 个）
```

新增的 9 个（`test_web_smoke.py`）：

- 页面与资源：外壳内容、静态资源可取、没有令牌拒绝（401）。
- 离线：`web/` 里没有任何 `http(s)://`；每个 `from './x.js'` 都指向存在的文件；`node --check` 通过（复制成 `.mjs` 再检查，不在源目录执行）。
- 用户流程（接口顺序与界面一致）：发现卡 → 摘要 → 导入（轮询到 done，文案含「可以安全弹出」）→ 再次摘要为 0 → 日期 / 照片 / 三种角标 → 缩略图和预览 → 裁切（3:2、XPan 带拉直、挪位置、版本冲突 409、超出画面 422、还原）→ 单张导出（文件名 `_gxr`）→ RAW-only 导出 409 → 批量导出（RAW-only 单独报错）→ 整棵卡的哈希前后一致。
- 设置与重建索引、取消不存在的任务返回带文字的错误。

全目录 `uv run pytest -q` 的最近一次结果是 `119 passed`，没有失败。
注意：`studio/tests/` 里还有别人新加的 `test_camdata.py`、`test_datcodec.py`、`test_engine_knobs.py`、`e0_support.py`、`golden/`，我没有改也没有检查它们。

## 4. 浏览器走查（真实鼠标和键盘）

用 Chrome 无头模式 + DevTools 协议驱动（`research/studio_m1_web/browser_walkthrough.mjs`）。
在全新的临时图库上，针对假卡 `synthetic_card` 的 16 个 shot 运行：

```
PASS: 50   FAIL: 0   浏览器错误记录: 0
```

覆盖的步骤：首次引导（跳过）→ 插卡自动导入、完成横幅、状态栏 → 图库 15 张、三种角标、日期筛选 → 多选后「导出选中的」弹窗 → 批量导出完成 → 大图 → ← / → 切换 → 点「3:2」保存进 sidecar → 鼠标拖动框，松手后位置保存 → ↑ 两次拉直 1.0° 保存 → 按住 / 松开 Space 隐藏和恢复裁切框 → 「还原原图」→ E 键切到导出 → 单张导出完成 → 只有 RAW 的照片显示原因并禁用导出 → `?` 打开快捷键表。

过程中发现并修好的两个问题：

1. 导入进度提示条悬浮在图库左下角，挡住了「导出选中的」按钮（点不到）。改成顶部的提示条，不再悬浮。
2. 「这张卡上的照片都导入过了」没有「知道了」按钮，关不掉；关掉后「发现相机卡」横幅又会立刻出现。改为：这张卡处理过就不再提示「发现相机卡」，「都导入过了」可以关掉。
3. 导入暂停或被打断后，卡已拔出时「继续导入」按钮点了没反应。改为卡不在时写「插回卡后可以继续」。
4. 「相机」里的裁切面板会把 `null` 当文字显示。改掉。

截图（`screenshots/`，都是修好后重新截的）：

- `01-gallery.png`：左侧日期列表和数量、三种角标、勾选框、顶部「配方 即将推出」、底部状态栏。
- `02-viewer-crop.png`：3:2 裁切框居中、框外变暗、右侧裁切面板（比例、框的大小、拉直、还原 / 完成）、「当前：3:2，裁出 640 × 427 像素」。

## 5. 没有验证的部分（复审请重点看）

- **真卡**：没有接触真实卡，所有导入都用假卡。读卡器、弹出、拔卡都是模拟的。
- **导入中拔卡 / 暂停 / 取消**：后端有测试，界面的横幅文案只在代码里核对，浏览器里没有走过。
- **16:9 建议 XPan**：假卡全是 4:3 或 3:2，没有 16:9 的照片，建议的显示只在代码里核对。
- **框的大小滑块**：代码路径在走查里没有点到（只走了比例、拖动、拉直、还原）。
- **版本冲突和超出画面的提示**：接口有测试，界面只核对了代码；没有在浏览器里触发过。
- **视觉**：只看了两张截图，没有在别的分辨率和浅色系统设置下看过。

## 6. 与设计文档不一致、或任务没给、需要决定的地方

1. **安全弹出卡**：后端没有弹出接口（`studio/README.md` 没有），所以界面只写文字说明「在访达里点弹出」，没有按钮。要做按钮，需要后端补接口。
2. **「自由」比例**：只能拖动位置和缩放大小，不能拖四个角改形状。UX.md 没有要求角拖动，所以没做。
3. **「看原图」**：M1 还没有调整，所以按住 Space 只是隐藏裁切框；等 M2 有了调整再接原图渲染。
4. **导出文件夹**：浏览器里没有原生选文件夹，只能手动输入完整路径（和后端要求一致）。
5. **配方、调整、相机写回**：只有占位页，标「即将推出」。M2/M3 的内容没有做。
6. **双击滑块归零**：只在拉直滑块上有效（M1 只有这一个滑块有「归零」语义）。UX.md §7 写的是所有滑块，M2 的滑块上再加。
7. **撤销**：只撤销裁切（最多 100 步，切换照片后清空，与 UX.md 一致）。
8. **缩放基准**：框的大小滑块以「比例与拉直确定的最大框」为 100%。打开一张已有裁切的照片时，基准是当前框，所以第一次拖滑块会以它为准。

## 7. 复现

```bash
cd studio
rm -rf /tmp/gxr-check && mkdir -p /tmp/gxr-check/{vol,lib,exp}
uv run python -m gxr_studio.devtools.synthetic_card /tmp/gxr-check/vol --no-real
GXR_STUDIO_VOLUMES=/tmp/gxr-check/vol GXR_STUDIO_LIBRARY=/tmp/gxr-check/lib GXR_STUDIO_EXPORT=/tmp/gxr-check/exp \
GXR_STUDIO_TOKEN=check123 uv run gxr-studio --no-browser --port 8790
# 另开一个终端：打开 http://127.0.0.1:8790/?token=check123，按 MANUAL_CHECKLIST.md 逐项核对
uv run pytest -q tests/test_web_smoke.py
```
