# GXR 电脑工作室 v2 · 前端实现计划（第二阶段）

状态：第一阶段产物（设计师，2026-10-30）。第二阶段只有编排者通知后才开始，实现写进 `studio/web/`。
配套：`DESIGN.md`（界面怎么长）、`prototype.html`（可点击原型，实现时对照它的行为）、`CONTRACT_REQUESTS.md`（还没定的接口，先看它）。
合同以 `research/studio_v2/PRD.md` 为准。本文件不改接口。

---

## 0. 前提与边界

- 只改 `studio/web/`（`index.html`、`assets/*.js`、`assets/app.css`），以及 `research/studio_v2/ui/`。
- 不用构建工具，不加第三方依赖。ES 模块、手写 DOM，和现在一样。
- 不改 `api.js` 的错误格式（`ApiError`，`message` 是给人看的中文）。
- 「界面行为保持不变，除非这次任务就是改界面」（`studio/AGENTS.md`）。这次改的是大图里的标签和画面，图库、导入、相机页、配方页（`lut.js`）不动。
- 不改已经在页面里对上的 DOM id（AGENTS.md 的规定）。新增的 id 用新前缀。
- 第一阶段的原型只演示大图。图库、相机页、配方页不在原型里，它们的行为以现在的为准。

---

## 1. 文件改动清单

### 1.1 新增

| 文件 | 内容 | 能不能在 node 里单独测 |
|---|---|---|
| `assets/frame_geom.js` | 纯函数：`frameSpec(frame, W, H)`（边框四边宽度，单位和照片一样）、`stampText(photo, stamp)`（日期格式、时间、文字）、`stampPos(corner, margin)`、`canvasRatio(name)`、`colorOf(name)` | 能（没有 DOM） |
| `assets/geom.js` | 纯函数：`canvasDims(photo, rot)`、`inValid(x, y, cw, ch, deg)`、`fitRect(rect, cw, ch, deg)`（框收进有效画面，等比缩小）、`maxRect(...)`、`rotateRect90(rect)`、`flipRectH(rect)`、`presetRatio(id, portrait)` | 能 |
| `assets/correct.js` | 「裁切与纠正」面板里的纠正部分：拉直刻度盘（`ruler`）、垂直/水平/畸变滑块、旋转/翻转按钮、「自动」、「还原裁切和纠正」 | 否（有 DOM） |
| `assets/stage.js` | 画面组装：`buildStage(view, mode)` 生成「成片预览」「裁切中」「原图」三种画面（DOM），以及裁切框（`cropBox`）和它的拖动、四角缩放 | 否 |
| `assets/frame_panel.js` | 「边框」标签：样式卡片、选项、「设为默认」 | 否 |
| `assets/stamp_panel.js` | 「时间戳」标签 | 否 |
| `assets/caps.js` | 接口探测和缓存：`/api/frames`、`/api/defaults/finish`、`/api/photos/{id}/capabilities`、`/api/photos/{id}/meta`。每个接口只探测一次，失败就记下来，降级用 | 否 |
| `assets/copy.js` | 所有给人看的中文文案（常量），便于做「没有英文术语」的检查 | 能 |

### 1.2 修改

| 文件 | 要改什么 |
|---|---|
| `assets/viewer.js` | 标签从 4 个变成 6 个（配方、调节、裁切、边框、时间戳、导出），`TABS` 数组改成 DESIGN 1.2 的顺序和快捷键（R、A、C、F、T、E）。`setTab` 记住 `lastTab`，「完成」回到它。空格键按住看原图（`showOriginal`，现有）。底下的照片条和底栏按 DESIGN 1.4 调整。`renderSide` 里每个标签的 pane 换成新模块。 |
| `assets/crop.js` | 只留「比例、横竖、辅助线、框的大小、框的拖动和缩放、还原裁切」。纠正部分移到 `correct.js`。`applyCrop` 里 `plain = view.showOriginal \|\| EDIT_TABS.includes(view.tab)` 这一行要删掉：现在只有「裁切」标签才显示未裁切画面（DESIGN 1.3）。`recomputeDefault` 里的 `flip` 参数改名（见 `CONTRACT_REQUESTS.md` 第 1 条）。`nudge` 的范围从 ±10 放宽到 ±45（PRD 第 2 节）。 |
| `assets/preview.js` | 所有标签都请求「成片预览」（`stage=final`），只有「裁切」请求 `stage=uncropped`。`runPreview` 的请求 body 带上完整草稿：`recipe`、`adjust`、`curve`、`geometry`、`crop`、`frame`、`stamp`。`EDIT_TABS` 的含义要改（不再是「整张原图」）。`defaultNote`、`renderNote` 的标签规则按 DESIGN 4.4 改。`BASE_NAMES`、`KNOB_NAMES` 保留。`adjustBody` 加上 `black_point`、`saturation`、`vibrance`、`vignette`。 |
| `assets/adjust.js` | 分三组：光线（曝光、对比、高光、阴影、黑点）、颜色（色温、色调、饱和度、自然饱和度）、效果（暗角），然后是曲线。`saveAdjust`、「全部归零」的键列表要包含四个新键。 |
| `assets/recipes.js` | 三种状态（`full` / `approx` / `none`，来自 `caps.js`）。`none` 时 8 个底子和微调用 `aria-disabled="true"` 且整块变淡，点击先拦住（捕获阶段）再显示原因。`approx` 时显示琥珀色提示卡。`NEW_TONE_KNOBS` 等列表保留。 |
| `assets/export.js` | 导出面板加「这次会导出：」列表（DESIGN 第 7 节）和批量导出的一句话。导出前先 `await ed.save`（把还没写完的草稿保存完），否则导出的是旧的。 |
| `assets/look_notes.js` | 加「近似」的文案（`approx`）。现有函数保持不变（有 node 测试在 `studio/tests/` 里用它）。 |
| `assets/app.css` | 配色改成变量：深色沿用现有值，浅色用 DESIGN 13.2 的表。新增组件：边框卡片、刻度盘、比例菜单、裁切框的角手柄、提示卡（琥珀/灰）、时间戳的开关和位置选择器。`.side` 宽度改成 380px。 |
| `index.html` | 一般不用改。如果要加 `<meta name="color-scheme">` 可以加。 |

### 1.3 不动

`gallery.js`、`import.js`、`import_summary.js`、`camdata.js`、`lut.js`、`onboarding.js`（只改文案时除外）、`dom.js`、`state.js`、`api.js`、`app.js`（路由和全局键，只在 `viewerKeys` 里接上新键）。

---

## 2. 状态模型

每张照片一份（沿用 `view` / `view.ed`）：

- **已保存的状态**：`GET /api/photos/{id}/edit` 和 `GET /api/photos/{id}/crop` 读回来的内容，连同 `rev`。
- **草稿**：滑块拖动时还没保存的值。拖动时只改草稿、请求画面；松手（`change`）后才 `PUT`。
- **画面模式**：`view.tab === 'crop'` → `uncropped`；按住空格 → `orig`；其它 → `final`。切换模式不改草稿。

版本号（`rev`）：`/crop` 和 `/edit` 共用。任何一边写成功，两边都要 `syncRev`（现有 `syncRev` 已经这样做）。409 时自动重读，提示「这张照片刚被改过，已经重新读取。请再改一次。」

写入顺序：同一张照片的写入排队（现有 `persist` 用 `ed.save` 链，保持）。

---

## 3. 面板与接口对照

| 面板 | 读 | 写（PUT） | 画面 | 说明 |
|---|---|---|---|---|
| 配方 | `GET /api/recipes`（现有）、`GET /capabilities`（新）、`GET /edit` | `PUT /edit {recipe}` | `final` | 三态见 DESIGN 4.2；`recipe` 的 `levels` 和 `memory` 保持现有写法 |
| 调节 | `GET /edit` | `PUT /edit {adjust, curve}` | `final` | 四个新键见 PRD 第 3 节；`adjust` 的 `wb` 结构保持 |
| 裁切（比例、框） | `GET /crop` | `PUT /crop {preset, rect, orientation, expected_rev}` | `uncropped` | 横竖字段名待定（合同第 1 条） |
| 裁切（纠正） | `GET /edit` 里的 `geometry` | `PUT /edit {geometry}`；自动：`POST /geometry/auto` | `uncropped` | 合同第 10、12 条；`straighten` 同步到 `crop.angle_deg` 由后端做 |
| 边框 | `GET /api/frames`、`GET /edit` | `PUT /edit {frame}`；默认：`PUT /api/defaults/finish` | `final` | 合同第 4、5 条 |
| 时间戳 | `GET /api/frames`、`GET /api/photos/{id}/meta` | `PUT /edit {stamp}` | `final` | 合同第 4、11 条 |
| 导出 | `GET /edit` | `POST /api/photos/{id}/export`、`POST /api/export`（现有） | — | 先等保存完成；合同第 7 条（近似的文件名） |
| 照片条 | `GET /api/photos/{id}`（现有，`date_source`、`has_raw`） | — | — | 「日期是估计的」用 `date_source` |

### 3.1 渲染请求

```
POST /api/photos/{id}/render?stage=final&size=preview     （拖动中）
POST /api/photos/{id}/render?stage=final&size=full        （松手后）
POST /api/photos/{id}/render?stage=uncropped&size=preview
```

body（草稿）：`{recipe, adjust, curve, geometry, crop, frame, stamp}`，只带有的键。
（合同第 2 条：PRD 写的是 `GET`，但没有草稿就看不到拖动效果，这里要求保留 `POST`。）

响应头：
- `X-GXR-Label`：画面标签（现有；`final` 时用它显示「电脑预测」「近似」等）。
- `X-GXR-Calibrated`：现有。
- `X-GXR-Valid-Rect: x,y,w,h`：拉直、透视、畸变之后有效画面的范围（归一化）。**`uncropped` 必须有**（合同第 3 条）。没有时用 `geom.js` 的拉直近似（只算拉直，透视忽略）。

### 3.2 预览节奏（PRD 验收：松手后 1.5 秒内看到新图）

- 拖动：防抖 120 毫秒，`size=preview`，用 `AbortController` 取消旧请求（现有做法）。
- 松手：立即请求 `size=full`。
- 旧图保持显示，直到新图到了（不闪白）。新图到了才 `URL.revokeObjectURL` 旧的。
- 失败：画面下面写红字「预览没成功：（原因）」，给「重试」，上一张好图保留并变暗（DESIGN 4.5、10）。
- 画面的宽高比来自图片本身的 `naturalWidth` / `naturalHeight`，不要依赖响应头。

### 3.3 裁切框的几何（`geom.js`）

- 画布：`canvasDims(photo, rot)`，`rot` 为奇数时宽高互换。
- 框的坐标：归一化到画布（rot90 和翻转之后、拉直之后、裁切之前）。
- 收进有效画面：`fitRect` 以框的中心为准等比缩小，二分查找 30 次（现在原型里就是这样写的，见 `prototype.html` 的 `fitRect`）。
- 旋转 90°（逆时针）：`(x, y, w, h) → (y, 1−x−w, h, w)`。
- 左右翻转：`(x, y, w, h) → (1−x−w, y, w, h)`。拉直的值不变。
- 比例锁定时的四角缩放：宽度来自拖动，高度 = 宽 / 比例（换算到像素再换回归一化）。

---

## 4. 探测与降级

`caps.js` 在打开大图时探测一次（同一会话里缓存），每个接口的状态分三种：`ok`、`missing`（404 或网络错误）、`error`（500 等）。

| 接口 | `missing` 时 | `ok` 但缺字段 |
|---|---|---|
| `GET /api/frames` | 边框、时间戳面板显示「这部分还没准备好（电脑端版本较旧）」，控件全部禁用，不写任何新键 | 缺的选项不显示 |
| `GET /api/defaults/finish` | 「设为默认」禁用，写明原因 | — |
| `GET /api/photos/{id}/capabilities` | 用 `/api/photos/{id}` 的 `has_raw` 和现有的 `render.reason === 'no_raw'` 推断：有 RAW → `full`；没有 RAW → `none`（不做 `approx`） | `reason` 缺失时只用固定文案 |
| `GET /api/photos/{id}/meta` | 用 `/api/photos/{id}` 里的 `captured_at`、`date_source`；光圈等参数不显示 | 缺的字段隐藏（PRD 4.3） |
| `POST .../render` 的草稿键 | 如果响应头里没有 `X-GXR-Valid-Rect`，纠正用拉直近似，透视不做 | 这种情况下界面不额外提示（已在合同里列出） |

降级原则（DESIGN 10）：某一块不可用，只让那一块写明「还没准备好」，其它功能照常用。不弹窗。不写假的数字。

---

## 5. 时间戳和边框的几个实现细节

- 日期格式的四种写法在 `frame_geom.js` 的 `stampText` 里；格式的中文名和示例从 `/api/frames` 读（合同第 4 条）。没有接口时的固定列表只作为文案兜底，不写回 sidecar。
- 日期来源：默认用拍摄时间；`date_override` 为 `null` 表示用拍摄时间。没有拍摄时间时（`date_source === 'mtime'`）在时间戳面板写「这张照片没有拍摄时间，用的是文件修改时间」。
- 时间戳字体：数码管是 DSEG7 Classic（OFL），字体文件由后端提供。界面里没有字体文件时用 `Menlo` 回退，不要求和设计稿像素级相同。
- 边框的文字和标志由**后端渲染**（预览和导出用同一条管线）。前端的 `frame_geom.js` 只用来做「缩略卡片」的示意和布局计算（比如要不要显示 `样式 · 中` 这一行），不做最终渲染。
- 「不加边框」的表示：合同第 4 条定下来之前，前端按 `style: 'none'` 写。

---

## 6. 键盘

- 新增 `F`（边框）、`T`（时间戳）。`R A C E` 保留。
- 裁切中：`[` 逆时针转 90°（可选，不做也可以）。
- 「翻转」没有快捷键。
- 滑块获得焦点时，←/→ 和 ↑/↓ 归滑块（现有 `isRangeFocused` 的规则，把刻度盘也算进去）。

---

## 7. 实施顺序（建议）

每一步都能单独运行、单独验收。前一步没完成，后一步可以先不做，但不能破坏前一步。

1. **标签和画面模式**：6 个标签、成片预览 / 裁切中 / 原图三种画面、状态行、照片条、底栏。只用现有接口（`render` 先用现有 body）。验收：切到裁切标签画面变成整张；离开变回成片预览；空格按住看原图。
2. **调节四个新项**（依赖合同第 9 条的方向约定）。验收：四个滑块拖动时预览变化；两端方向正确。
3. **配方三态**（依赖 `capabilities`）。验收：`full` 不变；`approx` 有琥珀卡和「近似」标签；`none` 整块变淡，点击有反应。
4. **裁切与纠正**（依赖合同第 1、2、3、10、12 条）。验收：刻度盘拖动和 ←/→ 都能用；垂直、水平、畸变、旋转、翻转、自动、还原都能用；框不出现空白角（有有效区域时）。
5. **边框**（依赖第 4、5 条）。验收：六种样式都能选；选项按样式变化；「设为默认」存下；不加边框可以选回。
6. **时间戳**（依赖第 4、11 条）。验收：开关、内容、四种日期格式、日期改成…、字体、颜色、大小、位置、发光都能用。
7. **导出**（依赖第 7 条）。验收：「这次会导出：」列表和实际导出一致；导出前草稿已保存。
8. **浅色和深色、无障碍、文案**。验收：两套配色的对比度 ≥ 4.5:1；文案检查（见第 9 节）；焦点可见。

---

## 8. 测试

- **纯函数**（`frame_geom.js`、`geom.js`、`stampText`）：node 测试。放哪里取决于合同第 13 条。测什么：边框四边宽度随长边的比例（细 2% / 中 4% / 粗 7%）；`fitRect` 收进后 4 个角都在有效区域里；旋转 4 次回到原位；翻转两次回到原位；四种日期格式；缺拍摄时间时用文件时间。
- **界面**：参考原型的自测方法（`prototype.html` 的验证过程）：无头 Chrome + DevTools 协议，捕获运行时异常，逐项点击，截图检查版式。自测脚本放在 `/Volumes/Workspace/Scratch/tmp/projectricoh/<任务名>/`，用完删除（PRD 第 9 节）。
- **PRD 验收**（后端负责数值，前端负责界面）：8 个底子的预览变化；每个调节滑块两端像素变化；JPG 照片的三种状态；松手后 1.5 秒内有新图。
- **不新增依赖**。浏览器测试用的 Chrome 是已经装好的。

---

## 9. 文案检查（DESIGN 第 11 节）

实现完后，在 `studio/web/` 里搜一遍：
- 不应该出现：`preview`、`render`、`crop`、`straighten`、`sidecar`、`EXIF`、`LUT`（在界面文字里，不在代码标识符里）、`EV`、`sRGB`、`seg7`、`Cont`、`Satu`、`Space`、`undo`、`reset`。
- 允许：`JPG`、`RAW`、`RAW+JPEG`、`RAW+JPG`、`GR`、`XPan`、`Instagram`、`RICOH GXR`（照片上的字）、键帽符号。
- 代码里的英文标识符不受限制；界面上的字符串（`textContent`、`placeholder`、`title`、`aria-label`）要检查。

---

## 10. 风险

1. **有效区域**：拉直和透视之后，`uncropped` 的画面边缘是空的。没有 `X-GXR-Valid-Rect` 时，框的收缩只对拉直准确。这是最需要后端配合的一条。
2. **草稿和已保存的不一致**：导出、切换照片时，草稿必须已经写完。忘了 `await ed.save` 会导出旧的。
3. **键的冲突**：`F`、`T` 是新的。和浏览器、系统的快捷键没有冲突；`G`、`O` 在裁切中才生效，不影响别的标签。
4. **性能**：`size=preview` 的小图每次拖动都请求。图库里有大图时，后端要保证小图路径够快（PRD 不限，建议 300 毫秒以内）。
5. **旧的 sidecar**：`crop.angle_deg` 必须继续有效（PRD 第 2 节）。前端读到 `geometry.straighten` 为空时回退到 `crop.angle_deg`。
6. **后端没好**：每一步都有降级（第 4 节）。最坏情况是某个面板显示「还没准备好」，其它照常用。

---

## 附录 A：配色对比度（WCAG，脚本计算）

计算方法：相对亮度公式（WCAG 2.x）。脚本：`tools/contrast_check.py`（`python3 tools/contrast_check.py` 可以复核）。结果如下。

| 用途 | 前景 | 背景 | 对比度 | 结论 |
|---|---|---|---|---|
| 深色 正文 | `#e8e8ea` | `#1b1c1f` | 13.92:1 | 通过 |
| 深色 次要字 | `#9a9ca3` | `#1b1c1f` | 6.21:1 | 通过 |
| 深色 次要字（画布底） | `#9a9ca3` | `#121315` | 6.78:1 | 通过 |
| 深色 金字 | `#e8b04a` | `#1b1c1f` | 8.71:1 | 通过 |
| 深色 按钮字 | `#1d1606` | `#e8b04a` | 9.18:1 | 通过 |
| 深色 警告字 | `#e0a13a` | `#1b1c1f` | 7.57:1 | 通过 |
| 深色 错误字 | `#e06a5a` | `#1b1c1f` | 5.18:1 | 通过 |
| 深色 成功字 | `#6cc487` | `#1b1c1f` | 8.02:1 | 通过 |
| 浅色 正文 | `#1c1d21` | `#ffffff` | 16.84:1 | 通过 |
| 浅色 正文（画布底） | `#1c1d21` | `#f3f3f5` | 15.20:1 | 通过 |
| 浅色 次要字 | `#5d616a` | `#ffffff` | 6.21:1 | 通过 |
| 浅色 次要字（面板 2） | `#5d616a` | `#ececef` | 5.26:1 | 通过 |
| 浅色 加深的金字 | `#8a5d10` | `#ffffff` | 5.75:1 | 通过 |
| 浅色 加深的金字（面板 2） | `#8a5d10` | `#ececef` | 4.87:1 | 通过 |
| 浅色 按钮字 | `#1d1606` | `#b8861f` | 5.53:1 | 通过 |
| 浅色 警告字 | `#94600a` | `#ffffff` | 5.33:1 | 通过 |
| 浅色 错误字 | `#b42f1f` | `#ffffff` | 6.24:1 | 通过 |
| 浅色 成功字 | `#237a45` | `#ffffff` | 5.33:1 | 通过 |

注意：浅色的金色（`#b8861f`）只用于底色和滑块，文字用加深的 `#8a5d10`。

---

## 附录 B：原型自测记录（第一阶段）

在无头 Chrome 里加载 `prototype.html`，通过 DevTools 协议逐项操作（脚本不进仓库）。结果：

- 页面加载后没有任何运行时异常或控制台错误。
- 大图：六个标签正常切换；进入「裁切」后画面变为整张未裁切画面，框和四个角手柄都出现。
- 拉直：刻度盘聚焦后 ←/→ 每次 0.1°，数值正确（10 次后为 1.0）。
- 旋转 90°：画布变竖，裁切框的像素数随之变化。拉直 1.0° 时，框按几何关系缩到约 0.9746 倍（与理论值一致）。
- 「自动」：给出建议值，提示文字正确。
- 边框：六种样式和「不加边框」都能切换；信息条的底部条、胶片黑边的橙字、拍立得的手写文字都出现。
- 时间戳：开关打开后显示 `'26 10 23`（默认格式）。
- 只有 JPG（不能用）：8 个底子 `aria-disabled`，点击后提示卡闪动并写出原因；整体强度和微调块整体变淡（修正后）。
- 只有 JPG（可近似）：琥珀色提示卡和「近似（这张没有 RAW）」标签出现。
- 第二张照片（无拍摄时间）：照片条出现「日期是估计的」。
- 浅色、深色两套配色都能切换；截图检查浅色的白色边框在浅灰舞台上清楚可见。
- 边框一览（7 张）和三种裁切（3 张）都能显示，同一种边框在三种裁切下比例一致。

未验证（需要后端或真实数据）：真实 RAW 的配方预览；数码管字体（原型用等宽字体示意）；透视和畸变的精确效果（原型只用 CSS 变换示意）。
