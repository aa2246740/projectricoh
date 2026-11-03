不可以给用户试用（有 1 个 P0：导入出错时界面仍说"可以安全弹出卡了"。修法很小，改完复核后即可试用；其余没发现会丢照片的路径）

# review-studio-m2-r1：GXR 电脑工作室 M1+M2 独立复审

复审人：review 子代理（Sonnet 5.5），2026-10-30。只读复审，没有改 `studio/` 的任何文件。

## 0. 复审的是哪一版

- 复审开始时 `studio/` 里有 100 个文件（不含 `.venv`、`__pycache__`）。逐个文件的 SHA-256 在 `reviewed_files_at_start.sha256`；这份清单本身的哈希（相当于整个代码快照的指纹）：
  `0aa180a14a8c556ba8ec17168da07d96a8434bb87c644042d5fba857bdb12084`
- 复审结束时核对：这 100 个文件一个字节都没变。唯一的差别是多了 `studio/src/gxr_studio/lut/`（7 个文件，另一个任务在加 LUT），**不在本次复审范围内**，我没有读它。
- 对象：`studio/`（src、web、tests、`GXR Studio.command`、README）+ 设计文档（只对照，不逐条评）。8 份报告只用来对照数字（257 个测试、72 项走查），没有逐条评审。

## 1. 结论一句话

照片数据的底线是牢的：卡确实只读，复制先校验再登记，中途杀进程不会留下坏文件，导出不覆盖，本机服务的令牌 / Host / Origin / 路径校验都挡得住我试的所有攻击。**但出错时给用户的话是错的**：有文件没导进来，界面却说"可以安全弹出卡了"，用户很可能接着就格式化卡。这一条必须先改。另有 2 个 P1（损坏的编辑文件会卡死这张照片的裁切和导出；只有 RAW 的照片默认画面是电脑预测却没标）。

## 2. 问题清单

### P0

**P0-1　导入有文件没导进来时，界面仍然说"现在可以安全弹出卡了"，校验失败时还是绿色成功横幅**

- 现象（我测出来的）：
  1. 卡上一对 DNG+JPG，JPG 读不出来（权限/读卡器错误）：后端 `state=done`，`imported_shots=0`，消息"导入完成，共 0 张。现在可以安全弹出卡了。有 1 个文件没能导入…"。**这一对里完好的 DNG 也没有导入**（整对被丢弃，因为 `_import_shot` 里任何一个文件失败就 `_discard` 整对），而界面横幅只数 `unreadable`，DNG 一个字不提。
  2. 复制后读回校验不一致（读卡器不稳时会发生）：`verify_failed=['…R0000102.JPG']`，但 `web/assets/import.js` 的 `summarize()` 完全不看 `verify_failed`，横幅是**绿色**的"导入完成：新增 14 张，跳过 1 张…。现在可以安全弹出卡了。"，状态栏也写"卡：导入完成，可以安全弹出卡了"（`import.js:263`，只要 `state=='done'` 就写）。
  3. 即使是 `unreadable` 的情形，横幅在"N 张读不出来（已跳过，卡上的文件没有改动）"后面照样接"现在可以安全弹出卡了"，自相矛盾。
- 为什么是 P0：这是用户第一次拿真卡用。用户照着提示弹卡、回头格式化，没导进来的那几张就永久没了。概率不高（要读卡出错），后果是丢照片，而且修起来很便宜。
- 复现：`probe_a.py`（读不出来的情形，输出里 `FAIL 有文件读不出来时…` 和 `FAIL 读不出 JPG 时，好的 DNG 仍被导入`）；`probe_d.py`（校验失败情形，输出 `probe_d.out`）。界面文字是我按 `import.js` 的逻辑推出来的，没有在浏览器里点出来。
- 建议修法：
  1. `summarize()` 和 `renderCardStatus()`：只有 `state=='done'` **且** `unreadable` 和 `verify_failed` 都为空，才出"可以安全弹出"；否则红色横幅："有 N 张没有导进来，请先别格式化或清空这张卡。换个读卡器或重新插拔，再点「继续导入」。"并列出文件名。
  2. `_done_message`（后端）同样改；后端进度里加一个"没导进来的照片数"（按张算，不是按文件）。
  3. `_import_shot`：一对里只有一个文件坏时，把好的那个照常导入（或至少把整对计入"没导入"并报出来），不要悄悄丢掉。
  4. 加测试：校验失败 / 读不出来时 `summarize` 的文字里没有"安全弹出"。

### P1

**P1-1　编辑文件（`.gxrs.json`）损坏或被删除后，这张照片的裁切保存和导出都会失败，错误提示是英文异常**

- 现象：把一张照片的 sidecar 改成 `{ not json`，其余照常（缩略图、预览、照片文件本身都不受影响，哈希不变）。但：
  - `PUT /api/photos/{id}/crop` → 未捕获的 `SidecarCorrupt`，HTTP 500（界面只会显示"出错了（500）"）；
  - `POST /api/photos/{id}/export` → 同样未捕获，500。`routes.py:_export_source` 里明明为这种情况做了"编辑读不出来不挡导出"，但紧接着的 `_crop_for_export`（`routes.py:123`）直接 `sc.read`，没有保护，等于白做；
  - 批量导出这一张的错误文字是 `SidecarCorrupt: /完整/路径/R0000102.gxrs.json: Expecting property name…`；
  - `GET crop/edit`、`PUT edit` 返回 500 `sidecar_corrupt`，message 里是原始路径加 JSON 解析错误。
  sidecar 被用户删掉（不是损坏）走同一条路，结果一样。
- 影响：照片没丢，但用户拿不出这张图，也不知道怎么办。
- 复现：`probe_a.py`，输出里"sidecar 损坏 / PUT crop"和"单张导出"两行。
- 建议修法：`_put_crop`、`_crop_for_export` 捕获 `SidecarCorrupt`；导出时按"没有裁切、没有编辑"继续并在返回里带 `warning`；其余接口返回 422 白话："这张照片的编辑记录坏了，照片本身没事。点「修复这张」会清掉编辑记录重新开始。"错误里不要带路径和解析错误。

**P1-2　只有 RAW（没有配对 JPG）的照片：导入相机数据后，缩略图和大图画的是"原厂 04 的电脑模拟"，却没有任何"电脑预测"标记，而且大图下面写着"这里显示的是照片本身（不是预测）"**

- 事实：`thumbs.py` 对没有 JPG 的照片，在相机数据已导入时用 `RenderService.default_look`（电脑模拟）出图。我用 2 张真实 DNG（去掉 JPG）测：导入相机数据前后缩略图平均差 48.9/255（颜色明显变了），响应里没有 `X-GXR-Prediction`，前端没有任何地方读 `preview_kind`，`gallery.js` 里没有"预测"字样；大图在「裁切」「导出」页签下显示 `DEFAULT_NOTE`（`preview.js:10`）："这里显示的是照片本身（不是预测）"——对这类照片是错的。没导入相机数据时则是中性转换，也不是"照片本身"。
- 为什么算 P1：你的硬要求是"电脑预测"标签不能漏。导出文件（文件名 `_电脑预测`、EXIF 说明）和编辑页签里的标签都是对的，漏的是图库和大图的默认画面。GXR 一般拍 RAW+JPG，所以日常碰到的概率不大。
- 复现：`probe_c.py`（`FAIL 该缩略图/预览的响应带 X-GXR-Prediction 标记`，并打印"前端读取 preview_kind 的文件: 无"）。
- 建议修法：缩略图和预览接口对这类照片加 `X-GXR-Prediction` 和标签头；图库格子上加小角标"RAW·电脑模拟"；`DEFAULT_NOTE` 按 `preview_kind` 区分（RAW-only：已导入相机数据写"这是原厂 04 的电脑模拟，不是相机拍出的 JPG"，没导入写"这是中性转换，不是相机的颜色"）；按住 Space 的提示（"相机 JPG，或 RAW 的小预览"）同理改。

### P2

1. **`rebuild` 会覆盖损坏的 sidecar，没有备份。** `Library._rebuild_group` 读不出 sidecar 就直接写一份新的（`rev=0`），原来的裁切/配方/调整全丢，旧文件也没留。建议先改名成 `Rxxxx.gxrs.json.corrupt-<时间>` 再写新的，并在 rebuild 的返回里列出来。（复现：`probe_a.py` 末尾"sidecar 重建后 … 旧的损坏内容有备份？ 无"。）
2. **双击两次 `.command` 会同时跑两个服务，共用一个图库。** 端口随机所以不冲突，但 `Library.open()` 会清空 `.studio/tmp`，`run_import` 开头会清空 `.studio/staging`，会删掉另一个实例正在写的临时文件，导致对方导入失败或保存编辑失败（不会写坏文件，照片仍在卡上）。这条是读代码推出来的，我没有实测。建议在图库里放一个启动锁文件（`flock`），第二个实例直接说"工作室已经开着了，请回到第一个窗口"。
3. **令牌 cookie 不分端口。** 浏览器的 cookie 只认主机名，`127.0.0.1` 上别的本地服务（比如你开着的开发服务器）也会收到 `gxr_token`，两个工作室实例也会互相覆盖 cookie。有 HttpOnly 和 SameSite=Strict，风险很小。可选：cookie 名带上端口（`gxr_token_<port>`）。
4. **macOS 的"可移除的卷"访问权限没写进 README。** 第一次读卡时系统会问"终端想要访问可移除的卷上的文件"。点了"不允许"，`find_cards` 里的 `except OSError: continue` 会把它当成没有卡，界面一直写"卡：未插入"，没有任何提示。建议 README 第 2 步加一句，并在读 `/Volumes` 遇到 `PermissionError` 时给界面一个明确提示。
5. **批量导出里单张失败的提示是 `类名: 异常文字`**（`routes.py:439`），对用户没用。建议统一成白话 + 错误代码。
6. **导入标定要手敲项目文件夹的完整路径**（`camdata.js:167` 只有占位符）。服务知道自己在哪个仓库里，可以做一个"用工作室所在的项目文件夹"按钮或预填。第一次用的人这一步最容易卡住。
7. **「配方」页签标着"即将推出"，但配方功能已经在大图的页签里能用**（`index.html:18`、`app.js` 的 `renderRecipes`）。会让人以为没做完。建议把那个字样改成"我的配方（即将推出）"，或者去掉页签上的角标。
8. **导入相机数据和标定包时，"先 rename 旧目录再 rename 新目录"之间如果断电/被杀，会留下没有 `camera-data/` 的状态**（`store.py:99-102`，`calib.py:101-107`）。相机数据可以重新从卡导入；标定包现在只有开发机能重新导入，用户自己恢复不了。建议先 rename 新→`.next`，再用一次原子的 `os.replace` 目录对调，或启动时发现 `.old` 就恢复。
9. **`seen`（"见过的文件"）靠 卷标哈希+相对路径+大小+修改时间**。命中就一个字节都不读（`importer.py`）。FAT 的修改时间只有 2 秒精度，GXR 的 DNG 大小几乎相同；两张同名卷标（"NO NAME"）的卡如果恰好有同名、同秒的文件，后一张会被当成已导入而跳过。概率极低，但后果是静默跳过，建议卡标识里加上卷序列号，或首次见到时多比对一次内容哈希。
10. **多张卡同时插着只导第一张**（`import.js` 里 `cards[0]`），界面没有提示还有别的卡。
11. **`dest_dir` 接受任意绝对路径并 `mkdir -p`**（不能是卡和图库）。需要令牌才能调，风险有限；可以考虑限制在 `~/` 之下。
12. **没有 Content-Security-Policy 响应头。** 前端用 `h()` 建 DOM、没有拼 HTML 的地方（我 grep 过 `innerHTML`，只有曲线编辑器里拼数字的 SVG），所以现在没有 XSS；加 `default-src 'self'` 是便宜的第二道防线。
13. **`.command` 里没有 Homebrew 时只给了文档链接。** 可以顺带写上官方一行安装命令。当前提示本身已经够友好（见 §4）。

## 3. 逐项核对结果（"没问题"的部分，都是我自己跑出来的）

### 3.1 用户照片的数据安全

| 项 | 结果 | 依据 |
|---|---|---|
| 卡只读 | 通过 | 代码里对卡的唯一入口是 `CardReader.open_rb/scandir`；`audit` 钩子在**生产里也装着**，发现卡就登记保护。导入前后整棵卡目录（哈希、大小、mtime、目录 mtime）完全一致；审计里对卡的写入次数 0。我自己的探针往假卡里写文件，被钩子拦下（`EROFS`），说明钩子真在工作。 |
| 导入出错/中途出错时不写卡 | 通过 | 失败路径只动 `.studio/staging`；`test_kill_the_process_20_times`、`test_unplug_midway_then_resume`、`test_verify_failure_is_not_committed` 全过 |
| 先校验再登记 | 通过 | `stage_file`：边读边算 SHA-256 → 写 `.part` → fsync → 读回比对 → `os.replace` → 提交索引。图库里每个文件的磁盘哈希 = 索引哈希 = 来自卡的哈希；卡上每个不同内容都进了图库 |
| 中途杀进程 | 通过 | 残留只有 `.part`（下次清掉）和"已就位未入索引"的文件（下次同内容直接沿用）。20 轮随机 SIGKILL 的测试在我这边也过了 |
| 导出不覆盖 | 通过 | `claim_path` 用 `O_EXCL`，重名加 `-2`；导出两次得到两个文件；目标不能在卡上（含符号链接指向卡）、不能在图库里 |
| sidecar 损坏不影响照片本身 | 通过（但见 P1-1） | 损坏后照片文件哈希不变，缩略图/预览照常 |
| 空间不足 / 取消 | 通过 | 测试覆盖（`paused_no_space`、`cancel`） |

### 3.2 本机服务安全（`probe_a.py` 前 17 项，全过）

- 只监听 `127.0.0.1`：实际启动 `GXR Studio.command`，`lsof` 只看到 `127.0.0.1:<端口>`；用本机局域网地址访问，连不上。
- 无令牌 → 401；错令牌 → 401；API 不接受查询串令牌；`/?token=` → 303 + `HttpOnly; SameSite=Strict` cookie。
- 错 Host / 错端口 → 403；`Origin` 不对、`Origin: null`、`Sec-Fetch-Site: cross-site` → 403；只有 cookie 没有 Origin 的 POST → 403（挡跨站）；cookie + 同源 Origin 的 POST → 通过。
- 路径穿越：卡只能按 id 选；`/assets/../..`、`%2e%2e` → 404；`import-file` 试了 `/etc/passwd`、`/dev/zero`、`/dev/null`、空串、相对路径、`~/Library`、`/etc`，全是 4xx，不泄露文件内容；`calibration/import` 的清单文件名用白名单正则（不含路径）、先复制到临时目录再核哈希、`np.load(allow_pickle=False)`；`import-upload` 30 MB → 立刻 422（上限 96 KB，边读边拒）。没有 openapi/docs。设置接口里没有令牌。
- 没有任何 `eval`/`exec`/`subprocess`/`pickle`。
- 导出目录：可以写到任意其它绝对路径（见 P2-11），但不能是卡、图库。

### 3.3 理光字节

- `studio/` 和 8 个报告目录里（`git ls-files -co --exclude-standard`，共 165 个文件）没有 `.dat/.entry/.npz/.bin/.dng/.jpg`；`GXRCE001` 魔数只出现在解析代码里（`datcodec.py`、`intake.py`）；没有 ≥96 位的十六进制块。
- `engine/data/final.json`（27 万字节）是我们自己拟合的"档位 → 剂量"表（`level/dose` 数字），不是固件字节；`tests/golden/*.json` 只有哈希。
- 运行时：理光数据只在应用数据目录（`camera-data/`、`calib/`）。图库里没有 `.dat/.entry/.npz`。
- 导出：用真实 DAT 的全部 24 字节片段（`probe_b.py`）去扫导出文件、缩略图、`.studio/` 共 20 个文件，**0 命中**。导出的 EXIF 去掉了 MakerNote，只带原照片自己的 EXIF 和我们的说明。
- 提醒：`studio/` 整个目录现在在 git 里是**未跟踪**状态（`?? studio/`）。提交前请照 `.gitignore` 再看一遍；`/firmware/**/*.DAT` 已被忽略。

### 3.4 正确性

- XPan 65:24：4288×2848 上得到 4288×1583（API 的 `pixels` 和真正导出的 JPEG 像素都核了）；竖拍（480×640，EXIF 方向 6）得到又高又窄的条（236×639，比例 2.71）。
- EXIF 方向：竖拍的缩略图、预览、导出都是竖的，导出 EXIF 方向 = 1；`orient_array` 的 1–8 个方向我对照 TIFF 定义逐个看过。拉直：前端 CSS `rotate(+θ)` 和后端仿射变换同为顺时针；角度 ±10 通过、10.0001 拒绝。
- 曲线/曝光边界（`probe_b.py`，49 项全过）：曝光 ±5 通过，±5.0001/字符串/bool 拒绝；对比、高光、阴影 ±100 通过，101 拒绝；色温色调整数 ±100；曲线 2–16 点通过，1 点/17 点/x 重复/x 倒序/越界 256 拒绝，恒等曲线当作没有曲线，反相曲线通过；旋钮越界返回 422 `level_not_allowed`，**不钳位**；配方槽位 9、未知旋钮拒绝。所有 200 响应都能解成 3 通道图。
- 与引擎一致：用 g135 的 DAT + 开发机标定，烘焙预览对精确链：平均差 0.17/255，99.9 分位 4，最大 12。（和报告里"p99 ΔE00 ≤ 0.3"同量级。我没有重做 C 参数检查，那部分靠测试 `test_engine_c_parity.py` 全过。）
- 标签：预览响应头 `X-GXR-Prediction: 1`、`X-GXR-Label`；ISO 400/500 的真实样本正确标成"电脑预测（跨单元/跨 ISO，未标定）"；导出文件名 `…_电脑预测未标定.jpg`，EXIF 说明 `computer prediction (not camera-measured) … NOT calibrated`；`camera-jpg` 导出不带配方标签；没有相机数据时预览/导出返回 409 + 白话。漏标的只有 P1-2 那一处。
- 相机数据校验：翻转 1 字节、截断的 DAT 都 422 "已经损坏或被改动过…没有导入"，且已导入的 g135 原样不动；重复导入 `unchanged`。

## 4. 新手可用性

- README"三步开始用"的第 1 步我真的跑了：`GXR Studio.command --no-browser`（临时图库/应用数据目录/空卷根目录，**没有用真实目录**）。`uv sync --frozen` 秒过，打印带令牌的链接，用 curl 打开得到页面。第 2 步的"自动读进来"属实（插卡且有新照片就自动开始导入，`import.js:39`）。第 3 步里的「配方」要先导入相机数据 + 标定，而标定要手敲路径（P2-6），这一步对新手最陡。
- 没有 uv 的全新机器（我用去掉了 Homebrew 路径的副本模拟）：打印"没有找到 uv（装 Python 依赖用的小工具）。请先装一次：打开「终端」，运行 brew install uv …装好后再双击这个文件。"然后"按任意键关闭这个窗口…"，退出码 1。提示是大白话，窗口不会一闪而过。macOS 自带的 bash 3.2 下 `read -n 1 -p` 可用。
- 联网：第一次 `uv sync` 需要联网（README 已写）；`.python-version` 是 3.14，没有的话 uv 会下载。这台机器 3.14 已经有了。
- 错误提示：服务端给的 `message` 基本都是大白话（上面我试的各种 4xx 都是）。例外是 P0-1、P1-1 里提到的几处，以及 500。
- `.command` 在 Finder 里有执行权限（`-rwxr-xr-x`），`com.apple.provenance` 属性不会触发"无法验证开发者"；README 里写了遇到时右键打开。

## 5. 复现方式

全部用临时目录，进程内（Starlette TestClient，不开端口、不联网），`audit.forbid_volumes()` 保证碰不到 `/Volumes` 下除 `Workspace`、`Macintosh HD` 以外的卷。

```bash
cd <仓库根>
# 全量测试（257 个，约 3 分钟；我这边 257 passed in 185.63s）
cd studio && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q --basetemp=<临时目录>/pt
# 探针（输出已存在 probe_*.out）
studio/.venv/bin/python -I research/review_studio_m2/probe_a.py <临时目录>/a             # 安全 + 导入 + 导出 + sidecar 损坏（71 项，4 项 FAIL = P0-1、P1-1）
studio/.venv/bin/python -I research/review_studio_m2/probe_b.py <临时目录>/b <仓库根>   # 相机数据、渲染、边界、理光字节扫描（49 项全过）
studio/.venv/bin/python -I research/review_studio_m2/probe_c.py <临时目录>/c <仓库根>   # RAW-only 标签（1 项 FAIL = P1-2）
studio/.venv/bin/python -I research/review_studio_m2/probe_d.py <临时目录>/d            # 校验失败时的界面（复现 P0-1）
```

`probe_b.py`、`probe_c.py` 需要本机的 `firmware/package_v37_g135/local/SD_ROOT/GXRCE.DAT` 和 `captures/…/stage2c-first-run/` 样本、以及 `research/` 下的本地标定文件（都不在 git 里）。

## 6. 没做到的 / 限制

- **没有重跑浏览器走查**（`research/studio_integration/browser_walkthrough_integration.mjs`，72 项）。它需要 node + 服务 + Chrome 三个进程同时跑，超过"最多 2 个进程"。我用 §5 的 4 个进程内探针（共 124 项检查，其中 5 项失败即上面的问题）代替了后端和接口层；界面层的结论（横幅文字、标签）是读 `web/assets/*.js` 推出来的，没有在浏览器里点出来。建议修完后由你这边（或我下一轮，放宽进程数）再跑一遍走查，把 P0-1 的几种情形加进去。
- 没有测 28mm / MOUNT 的真实 DNG（没有样本，报告里也是这样说的）。
- 没有读 `studio/src/gxr_studio/lut/`（复审开始后才出现）。
- 没有联网；没有碰相机和真实卡。唯一碰过的非临时目录是只读的：`firmware/…/GXRCE.DAT`、`captures/…` 样本、`research/…` 标定文件。真实启动 `.command` 那次，我用环境变量把图库/导出/应用数据/卷根目录都指到了临时目录，并用 `lsof`、`ipconfig getifaddr`、对本机局域网地址的一次 `curl` 确认只监听回环；没有访问外网。
- 同时进程数：测试时只有 pytest；探针每次 1 个；启动 `.command` 那次是 bash → `uv run` → python 服务 + 一个短命的 curl（我把它算作 2 个并行工作）。
- 临时目录：全部放在 `Scratch/rv_studio_*`，结束时删除（见交付后一步）。
