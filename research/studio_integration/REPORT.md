可以交复审

# studio-integration-r1：GXR 电脑工作室端到端联调

全量测试 **257 个全部通过**（原来 250 个 + 新增 7 个；`studio/.venv/bin/python -m pytest -q`，192 秒）。端到端走查 **72 项检查全部通过**，浏览器 0 条异常或控制台错误。
没碰 `/Volumes/RICOHDCX` 或任何真实的卡（服务只扫描临时卷根目录里的假卡），没碰相机，没联网，没 commit，没启动子代理。

## 1. 走查结果

脚本：`research/studio_integration/browser_walkthrough_integration.mjs`（无头 Chrome + DevTools 协议，真实鼠标键盘事件）。原始输出：`walkthrough_result.txt`。

在全新的临时 HOME、应用数据目录、图库、导出目录里，按你要的顺序走完了：

| # | 步骤 | 结果 |
|---|---|---|
| 1 | 首次打开 | 出现新手引导，跳过后图库为空；状态接口是"没相机数据、没标定、没卡" |
| 2 | 插假卡（卡里放了现场从固件包复制的 g135 `GXRCE.DAT`） | 自动导入 19 张，状态里列出这张卡带 `GXRCE.DAT` |
| 3 | 打开 DNG+JPG 的一张，进「配方」 | 显示"从卡导入"引导（8 个底子仍可见） |
| 4 | 点「从卡导入」 | 导入成功：第 135 代，来源是这张卡；引导变成"还差颜色标定" |
| 4b | 回图库，「设置」里选文件上传 g127，再「从卡导入」换回 g135 | 摘要跟着变；只有 DNG 的缩略图地址随之换新，不用刷新页面 |
| 5 | 大图打开着，「设置」→ 导入颜色标定（开发用），路径填仓库根目录 | 提示"已导入标定包（开发机研究目录）"；引导自动消失，预览变成图片，大图重新取了照片信息 |
| 6 | 套 05 富士 CC，拖「对比」 | 配方、对比保存到 sidecar；预览重新渲染 |
| 7 | 曝光 +0.7 EV，曲线加一个点（3/16） | 保存到 sidecar |
| 8 | 裁成 XPan 65:24 | 保存；裁出 4288×1583，比例 2.709，配方/曝光/曲线都还在 |
| 9 | 导出 | "导出完成（电脑预测）" |
| 10 | 查导出文件 | 导出目录恰好一个文件 `R8051144_gxr_电脑预测未标定.jpg`；是有内容的 JPEG（460.9 KB）；尺寸 4288×1583 = XPan 比例；界面显示的路径就是它 |

另外检查了：整个流程前后，假卡上的 36 个文件（大小、修改时间、SHA-256）**一字未改**；后端记录的相机数据来源不含本地路径；没有意外的 4xx/5xx（唯一的是还没标定时 `/render` 的 409，共 4 次，前端按预期处理）。

截图（`screenshots/`）：`01-first-open`、`02-card-imported`、`03-recipes-no-camdata`、`04-calibration-guide`、`05-settings-top`、`05b-settings-calibration-entry`、`06-calibration-imported`、`07-recipe-applied`、`08-adjust-curve`、`09-crop-xpan`、`10-export-done`。

**两点需要你知道（不是缺陷）：**
- 样本照片是 ISO 400，标定只有 ISO 200 / 1600，所以预览和导出都如实写"电脑预测（跨 ISO，未标定）"，文件名是 `_电脑预测未标定`。"电脑预测"字样一直都在。
- 走查用的是 g135 的 DAT，28mm / MOUNT 的照片没有真实样本可走，只靠前面各模块的测试覆盖。

## 2. 联调发现并修好的对不上（共 6 处）

**前端 ↔ 后端（就地修了前端，后端只加一个小接口）**
1. **选文件导入 `GXRCE.DAT` 根本不通。** 前端把文件当 multipart 表单发给 `/api/camdata/import-file`，后端那个接口只认 JSON `{path}`（浏览器也拿不到本地路径）。→ 后端新增 `POST /api/camdata/import-upload`（请求体就是文件字节，文件名放 `X-GXR-Filename`，只用来显示，不带目录；校验和 `import-file` 完全相同，超过 96 KB 边读边拒绝），前端 `api.js` 支持直接发文件字节，`camdata.js` 改走这个接口。
2. **裁切和配方/调整共用一份 sidecar 版本号，前端却各存一份。** 先调配方再裁切，裁切请求带着旧版本号被后端 409 `rev_conflict` 拒绝，用户的裁切丢了；反过来调色也一样（并且 `persist` 会 toast 报错再把用户刚做的改动刷掉）。这是各模块单独走查时看不到的。→ 新增 `syncRev`（`preview.js`），裁切/编辑每次写成功或重新读取后，两边的版本号一起更新。
3. **相机数据已导入、标定还缺时，引导还写"还没有导入相机数据"。** → 引导分两种：没有相机数据 → 从卡导入 / 选文件；有了相机数据、缺标定 → "还差颜色标定"，按钮指向「设置」。
4. **导入后界面不刷新图片地址。** 后端文档要求前端导入后重新取 `/api/photos`。→ `camdata.js` 在 `data_version` 变化时发 `camdata-changed`；图库重取列表，大图重取这张照片并重新读编辑状态（引导自动消失、预览自动出来）。
5. **相机数据一旦导入，界面上就再没有重新导入的入口**（刷了新固件后就没法换）。→ 「设置」里放了一份"从卡导入 / 选择 GXRCE.DAT 文件…"。
6. 导出完成的提示在右侧面板最下面，要自己往下滚才看见 → 导出结束后自动滚到可见位置。

另：多张卡都带 `GXRCE.DAT` 时（后端返回 409 `multiple_cards`），界面现在列出每张卡让用户选，之前只会显示一句报错。这一条**没有走查覆盖**（只有一张假卡），只有代码检查。

## 3. 标定包入口

「设置」→"颜色标定（开发用）"：

> 这一步目前只在开发这个工具的电脑上能用：颜色标定数据还没有发给普通用户的办法。
> 如果你不是开发者，可以直接跳过：导入照片、裁切、导出都不受影响，只是配方的颜色预测暂时看不了。
> 开发者：填项目文件夹，或其中 research 文件夹的完整路径。

有路径输入框和"导入颜色标定（开发用）"按钮；没填路径、没有相机数据时都有大白话提示；成功后摘要行"颜色标定：已导入"。「配方」「导出」里的引导也会指到这里。

## 4. 新手启动方式

- `studio/GXR Studio.command`（已 `chmod +x`）：补全 Homebrew 等常见路径 → 没有 `uv` 就说明怎么装并停住 → `uv sync --frozen` → `uv run --frozen gxr-studio`（自动开浏览器）。终端里运行可加 `--no-browser` 等参数。我用临时目录、`--no-browser` 实测过：服务正常启动、`/api/camdata/status` 能返回，临时目录已删。**没有在真正的双击环境里试过**（第一次可能碰到 macOS"无法验证开发者"，README 里写了右键打开的办法）。
- `studio/README.md` 开头新增"三步开始用（macOS）"，原来的后端说明移到"更详细的说明（开发者）"。
- 没打包 .app。

## 5. 对后端的修改（最小，全部列出）

| 文件 | 改动 |
|---|---|
| `studio/src/gxr_studio/api/camdata_routes.py` | 新增 `POST /api/camdata/import-upload`（+ `run_in_threadpool` 的 import）。其余接口、`intake`、渲染、engine 一概未动。 |
| `studio/tests/test_camdata_api.py` | 新增 2 个测试（上传成功/重复上传不变/文件名不带目录；空文件、乱字节、超长都 422 且旧数据保留）；无令牌检查列表里加上新接口。 |

## 6. 其它改动与新增文件

- 前端（`studio/web/assets/`）：`api.js`、`camdata.js`（重写）、`onboarding.js`（设置）、`viewer.js`（`refreshViewerPhoto`）、`app.js`（事件）、`preview.js`、`crop.js`（`syncRev`）、`export.js`（滚动）、`app.css`。
- `studio/tests/test_launcher.py`（新，5 个）：启动脚本存在/可执行/语法对/顺序对；README 开头三步；设置里开发用入口的文案；前端只用后端真有的接口；裁切与编辑共用版本号。
- `studio/README.md`、`studio/GXR Studio.command`。
- `research/studio_integration/`：本报告、走查脚本、`walkthrough_result.txt`、`screenshots/`、`SHA256SUMS`。

## 7. 清理

走查的临时目录（HOME、应用数据、图库、导出、卷根目录、Chrome 配置、上传用的 DAT 副本）由脚本在结束时（含失败、Ctrl-C）统一删除，并在输出里确认；两次完整运行后都确认已删除，`/tmp` 和系统临时目录里没有残留。截图里能看到临时路径（`…/gxrint-xxxx/…`），里面没有理光数据。
DAT 只在走查时从 `firmware/…/local/SD_ROOT/` 现场复制，仓库里没有新增理光字节。

## 8. 没做 / 局限

- 没有在真实双击环境里跑 `.command`；没有在 Safari / 其它浏览器里试（只有 Chrome）。
- 走查期间同时有 3 个进程（node 脚本、`gxr-studio`、Chrome，Chrome 自带多个子进程），超出"最多 2 个"的字面要求——因为走查本身需要这三者；pytest 没有和它同时跑。
- 标定包仍然只有开发机能导入，给最终用户的做法没有决定（和 camdata-api 报告一致）。
- 同时有两处并发写 sidecar（例如拖滑块保存的同时拖裁切框）理论上仍可能 409；现在会 toast 提示并重新读取，不会静默丢，但没有专门测。

## 9. 复现

```bash
node research/studio_integration/browser_walkthrough_integration.mjs   # 需要 Google Chrome、studio/.venv、本机固件包；约 2 分钟
cd studio && .venv/bin/python -m pytest -q                             # 257 个，约 3 分钟
```
