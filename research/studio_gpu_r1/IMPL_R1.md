# GXR Studio 显卡预览：第 1、2 步实现（IMPL_R1）

1. **做了什么：**
   - 第 1 步：TS + WGSL 的预览引擎（`frontend/`，Vite + pnpm），产物 `web/assets/gpu/engine.js` 已构建、跟改动一起提交，双击启动不用装 Node。
   - 第 2 步：后台加了 6 个只读接口；大图换成 WebGPU 画布，滑块直接交给引擎。由功能开关 `gpu_preview` 控制，暂时默认关。
   - 一致性测试进了 `make check` 和 CI，在 Chrome 的 SwiftShader 软件显卡上跑，不需要真显卡。
2. **在现有工作室里实测（真实 GXR DNG，显卡 Chrome）：**
   - 拖滑块每次输入都出帧，120 Hz 不掉帧，从输入到上屏中位 7.9–8.5 ms，p95 ≤ 10.1 ms。旧版要等 0.8–1 秒。
   - 换下一张 38–78 ms，回看 21–79 ms。旧版 1.4–1.6 秒。
   - 第一次跳到还没预热的照片要 0.4–0.9 秒，超出 150 ms 预算。测量时机器负载在 14–60 之间。
3. **颜色一致性：**
   - 合成数据 10 个用例，在 SwiftShader 上全部像素 ≤ 1 码值。
   - 本机真实 DNG 14 个用例：平均 ΔE2000 ≤ 0.0004，p95 = 0；JPG 路径逐字节相同。
   - RAW 路径有 ≤ 0.001% 的像素差 2–4 码值，拉直边缘有 1 个像素差 24 码值，所以没有做到「全部 ≤ 1」，原因见第 4 节。
   - 另外更正：上一轮报告里「全部 ≤ 1 码值」是四舍五入造成的，已改正。
4. **`make check`：**完整通过。876 个通过，697 个跳过（工作树里没有本机相机数据和样本夹具，CI 上也一样），覆盖率 89.81%（门槛 85%）。新模块 91–100%。
5. **能交复审。** 要复审定的四件事：颜色门槛怎么写、首次冷打开超预算、开关默认值，以及 Windows 和 CI 还没有实际跑过。

## 1. 改动（工作树 `/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview`，分支 `feat/gpu-preview`，未提交）

| 位置 | 内容 |
|---|---|
| `frontend/`（新） | `package.json`（vite 8.3.5、typescript 7.0.2、@webgpu/types 0.1.74，精确版本）、`pnpm-lock.yaml`、`.npmrc`（等 7 天）、`tsconfig.json`、`vite.config.ts`、`src/engine.ts`、`src/tones.ts`、`src/index.ts`、`src/shaders/{common,color,geo,bin,present}.wgsl` |
| `web/assets/gpu/engine.js`（新，构建产物，37 KB） | 提交进仓库；`make check` 重新构建并逐字节核对 |
| `web/assets/gpu_stage.js`（新） | 走显卡还是服务器的判断、数据加载和缓存、左右预取、唯一画布 |
| `web/assets/preview.js`、`stage.js`、`app.css` | `schedulePreview` 先问 `gpu_stage.route()`；大图区在显卡接手时放画布，裁剪框照旧叠在上面；画布底色用设计系统的 `--stage-dark #2a2a2a` |
| `src/gxr_studio/gpu/`（新） | `source.py`（RAW 布局、场景色彩仿射）、`tables.py`（烘焙表和 LUT 表的字节）、`box.py`（成片裁切框） |
| `src/gxr_studio/api/gpu_routes.py`（新） | 6 个只读接口，见下 |
| `src/gxr_studio/render/service.py` | `preview_bake()`（与 `render_preview` 共用缓存）、`warm_preview_bakes()`（后台预热 8 个内置配方） |
| `src/gxr_studio/finish/geometry.py` | 把 `crop_valid` 的取整拆成 `crop_box()`，行为不变 |
| `src/gxr_studio/flags.py`、`app.py`、`pyproject.toml` | 开关 `gpu_preview`（默认关）、注册路由、`gxr_studio.gpu` 进 import-linter 的两条约束 |
| `tests/` | `test_gpu_parity.py`（显卡对拍）、`test_gpu_api.py`（接口和服务器数据）、`test_gpu_frontend.py`（JS 调子表与 Python 一致、路由分支）、`gpu_support.py`、`support/gpu_harness.mjs` |
| `scripts/check_frontend.py`、`Makefile`（`make web`，`make check` 加一步）、`.github/workflows/ci.yml`、`.gitignore`（`/frontend/node_modules/`） | 构建核对和 CI |
| `docs/` | `dependencies.md`（前端依赖和许可）、`feature-flags.md`、`architecture.md`、`openapi.json`（重新生成）；`AGENTS.md` 加了说明和 `make web` |

### 只读接口

| 接口 | 内容 | 缓存 |
|---|---|---|
| `GET /api/photos/{id}/gpu` | 开关状态、RAW 布局（或不支持的原因）、JPG 链接、Log LUT 要的场景色彩仿射 | 布局按 DNG SHA-256 在进程里缓存 256 张 |
| `GET /api/photos/{id}/raw?v=<sha>` | DNG 原字节 | `immutable`，链接带 SHA |
| `GET /api/photos/{id}/camera-jpg?v=<sha>` | 相机 JPG 原文件 | 同上 |
| `GET /api/photos/{id}/bake?recipe=…` | 预览网格的配方烘焙表（float32）+ `X-GXR-Bake` 描述（标签、是否已标定） | 服务器 `_bakes` LRU；ETag / 304 |
| `GET /api/luts/{cube_id}/table` | LUT 3D 表 + 空间矩阵 | ETag 带空间版本 |
| `POST /api/photos/{id}/gpu/box` | 给定几何和裁切，成片在颜色层上的裁切框和有效区 | 前端按参数缓存 |

### 构建产物是否提交

提交。`web/assets/gpu/engine.js` 是 Vite 库模式产物（一个文件，不引用其他模块，不连外网），跟源码一起进仓库。
- 机主用「GXR Studio.command」、`make dev` 或 `uv run gxr-studio`，都直接用这个文件，不需要 Node。
- 改 `frontend/` 的人需要 Node 22+ 和 pnpm，跑 `make web` 再提交。
- `make check` 里的 `scripts/check_frontend.py` 会重新构建到临时目录，逐字节比较，再跑 `tsc --noEmit`。
- 没装 Node 时本地跳过并提示；CI 设了 `GXR_REQUIRE_FRONTEND=1`，必须通过。

## 2. 什么时候走显卡，什么时候回到服务器

分支与 `finish/serve.py color_image`（base=auto）和 `lut/photo.py` 一一对应（`gpu_stage.decide`，`tests/test_gpu_frontend.py` 里 17 个分支逐条测）。

| 情况 | 走哪条路 |
|---|---|
| RAW + 配方（含旋钮） | 显卡：DNG 字节在显卡上拆包、归一化、白平衡、2×2 合并、按 Orientation 转正 → 配方链 → 调整 |
| RAW + JPG，没有配方 | 显卡：相机 JPG 由浏览器解码（按 EXIF 方向），实测与 PIL 逐字节相同 → apply_base → apply_extra |
| **只有 JPG** 的照片（没有 DNG），没配方 | 显卡，同上一行 |
| **只有 JPG** 的照片，选了配方（近似） | **服务器**（`finish/approx` 的近似表还没进显卡） |
| 只有 RAW、没配方 | 显卡：原厂 04 |
| 显示类 LUT（sRGB / Rec.709 / Gamma 2.4 输入） | 显卡，底图同上 |
| Log 类 LUT | 显卡，只限 50mm 的 RAW（与 `lut_needs_raw` 一致）；MOUNT/28mm → 服务器（会报原来的错误） |
| LUT 带一维表，或输出是 Log | 服务器 |
| **竖拍（Orientation 5–8）** | 显卡；转正在合并时做，实测 Orientation 8 的 GXR DNG 与 Python 一致 |
| 拉直、90° 旋转、水平翻转、裁切（含比例框收进有效区） | 显卡；裁切框由服务器按与 `finish_array` 相同的规则算（只算蒙版，几毫秒） |
| **透视、畸变** | 服务器 |
| 成片里有**边框**或**时间戳**（含默认装饰） | 服务器；裁剪页的未裁切画面仍走显卡 |
| **HDR 增益图** | 预览本来就不显示 HDR（只在导出），两条路一样；导出不受影响 |
| 原图（按住空格） | 服务器（原来的 `<img>`） |
| 浏览器没有 WebGPU、开关关着、显卡设备丢失、数据加载失败 | 服务器 |

开关：`flags.json` 里 `{"gpu_preview": true}`。默认值按要求留到复审再定，现在默认关。开关关着时不创建 WebGPU 设备。

## 3. 在现有工作室里实测

### 环境

- 工作树代码，临时图库（端口 49731）。
- 7 张真实 GXR DNG + JPG：50mm 的 R8051410、R8051448、R8051312，MOUNT 的 R8051691、R8051699、R8051707，竖拍 R8051711（Orientation 8）。
- 其中 6 张设了配方（含 MOUNT 的旋钮），R8051699 没编辑（走相机 JPG）。
- Chrome 156，显卡 `ANGLE Metal Apple M1 Pro`；WebGPU 适配器 `apple / metal-3`，不是软件适配器。
- 内建屏 120 Hz。
- 用 CDP 发真实鼠标事件，在「调整」页拖滑块，每次 4 秒、120 Hz。
- **机器同时很忙：**load average 三次分别是 59、14–24、46，有 6 个以上别的 Python 进程各占 30–40% CPU。

### 拖动（`impl/studio-measure-r{1,2,3}.json`，逐帧数据在 `*-frames-*.json`）

| 滑块 | 输入数 / 出帧数 | rAF 间隔 平均 / p95 / 最大 | 超过 12.5 ms 的间隔 | 输入 → 显卡画完 p50 / p95 | 输入 → 下次刷新 p50 / p95 | 页面里的服务器图 |
|---|---|---|---|---|---|---|
| 曝光（r2） | 124 / 124 | 8.33 / 9.0 / 9.4 ms | 0 | 3.6 / 4.5 ms | 8.3 / 8.5 ms | 0 |
| 阴影（r2） | 252 / 252 | 8.33 / 8.9 / 9.4 ms | 0 | 4.0 / 5.0 ms | 8.5 / 9.0 ms | 0 |
| 饱和度（r2） | 252 / 252 | 8.33 / 9.2 / 9.4 ms | 0 | 3.7 / 5.0 ms | 8.4 / 9.1 ms | 0 |
| 曝光（r3，负载 46） | 124 / 124 | 8.33 / 10.0 / 10.4 ms | 0 | 3.9 / 5.2 ms | 7.9 / 8.9 ms（最大 45） | 0 |
| 阴影（r3） | 252 / 252 | 8.33 / 9.9 / 10.4 ms | 0 | 4.1 / 5.9 ms | 8.3 / 10.1 ms | 0 |
| 饱和度（r3） | 252 / 252 | 8.33 / 10.0 / 10.4 ms | 0 | 3.7 / 4.3 ms | 8.3 / 9.7 ms | 0 |
| 旧版（上一轮基线） | 124 次输入只出约 4 帧 | — | — | — | 0.79–1.05 s / 1.63–1.75 s | — |

拖动时不发任何出图请求，页面里没有服务器图。

### 换照片（改 hash → 新照片第一帧画完，含工作室原有的 /api/photos、/edit、/crop 等请求）

| 情形 | r2（负载 14–24） | r3（负载 46） | 预算 |
|---|---|---|---|
| 下一张（看了 1.5 秒，左右已预取） | 34–47 ms | 38–78 ms | ≤ 150 ms ✔ |
| 回看（已在显存） | 27–56 ms | 30–79 ms | ≤ 50 ms：负载低时满足，负载 46 时 p50 66 ms |
| 跳到不相邻、但所在单元已预热的照片 | — | 51、63 ms | ≤ 150 ms ✔ |
| 跳到不相邻、所在单元还没预热（服务器第一次烘焙） | 282 ms（JPG）、891 ms（MOUNT + 配方 05） | 403 ms、883 ms | ✘ 超预算 |
| 打开工作室后的第一张 | 926 ms | 2244 ms（新 Chrome 用户目录：着色器第一次编译） | ✘ |
| 旧版 | 1.39–1.58 s（每次都重算全尺寸） | | |

冷跳转的拆分（重启服务器后逐个请求，`curl`）：
- `/api/photos/{id}` 109 ms（第一次访问数据库）；
- `/gpu` 33 ms（解析 DNG）；
- 18.7 MB 原字节 58 ms；
- **配方烘焙 354 ms**（Python 第一次建模型 + 烘焙）。

所以剩下的等待主要是 Python 第一次烘焙。现在的做法和以后的办法：
- 第一次请求某张照片时，后台预热它所在单元、所在 ISO 模型的 8 个内置配方；
- 浏览器预取左右相邻照片的源图和配方表；
- 要让任意跳转都进预算，下一步可以导入后预热全部单元，或按 ARCH 第 4 节把烘焙搬到 Rust 或计算着色器（估计 ≤ 10 ms，未实现）。

## 4. 颜色一致性

### CI 用的合成数据（`tests/test_gpu_parity.py`，Chrome 无头 + SwiftShader，本机实测 7.9 s）

输入全是合成的：
- 合成 DNG：12 和 16 位、奇数裁切相位、GRBG、2×2 黑电平、Orientation 1/6/8；
- 合成配方烘焙表；
- 合成 17³ cube（sRGB、Rec.709 → Gamma 2.4、L-Log 三种空间）；
- 合成相机色彩矩阵；
- 带 EXIF 方向的合成 JPG。

参考值用生产函数算：`chain.chroma_u8`、`finish_array`、`lut.photo._apply`、`half_res_codes`、`load_jpeg`。

| 用例 | 平均 ΔE | 逐字节相同 | ≤1 码值 | 最大码值差 |
|---|---|---|---|---|
| raw12_tone | 0 | 100% | 100% | 0 |
| raw16_o6_curve_extra | 0.000004 | 99.9987% | 100% | 1 |
| raw_o8_display_lut | 0.00002 | 99.9935% | 100% | 1 |
| raw_log_lut | 0.00001 | 99.9974% | 100% | 1 |
| jpg_o6_adjust | 0 | 100% | 100% | 0 |
| jpg_rec709_lut_curve | 0.00002 | 99.9942% | 100% | 1 |
| jpg_untouched | 0 | 100% | 100% | 0 |
| raw_geometry_ratio（拉直 4.2° + 旋转 90° + 翻转 + 3:2） | 0.00001 | 99.9963% | 100% | 1 |
| raw_free_crop | 0.000009 | 99.9957% | 100% | 1 |
| raw_uncropped_straighten | 0.00002 | 99.9922% | 100% | 1 |

测试门槛写成「≤1 码值的像素 ≥ 99.99%，平均 ΔE ≤ 0.01」，不写成「全部 ≤ 1」，理由见下一节。

### 本机真实 DNG（只在本机跑，`impl/parity-real-r1.json`）

浏览器里调用工作室真正的 `gpu_stage.route()`（与拖滑块同一条路：开关、照片信息、烘焙表、LUT 表、裁切框都走真实接口），读回成片纹理，与生产函数算的参考图比较。

| 用例 | 尺寸 | 平均 ΔE | p95 | 最大 ΔE | 逐字节相同 | 最大码值差 |
|---|---|---|---|---|---|---|
| a 配方 01（50mm） | 2144×1424 | 0.00001 | 0 | 0.93 | 99.998% | 1 |
| b 配方 02 + 调子 | 2144×1424 | 0.00003 | 0 | 0.96 | 99.995% | 1 |
| c 配方 04 + 曲线 + 四项 | 2144×1424 | 0.00002 | 0 | 2.30 | 99.997% | **4** |
| d MOUNT + 旋钮 + 暗角 | 2144×1424 | 0.00001 | 0 | 1.37 | 99.998% | **2** |
| e 显示类 LUT | 2144×1424 | 0.00001 | 0 | 1.46 | 99.997% | **3** |
| f Log LUT（L-Log 65³） | 2144×1424 | 0.00001 | 0 | 1.08 | 99.998% | 1 |
| g 相机 JPG + 调整 | 4288×2848 | 0 | 0 | 0 | 100% | 0 |
| h 相机 JPG + LUT | 4288×2848 | 0 | 0 | 0 | 100% | 0 |
| i 竖拍（O=8）+ 配方 05 | 1424×2144 | 0.00002 | 0 | 0.95 | 99.997% | 1 |
| j 竖拍 JPG + 调整 | 2848×4288 | 0 | 0 | 0 | 100% | 0 |
| k 拉直 3.5° + 自由裁切 | 1608×1139 | 0.0002 | 0 | 0.40 | 99.93% | 1 |
| l 拉直 −2° + 旋转 90° + 翻转 + 3:2 | 1282×1923 | 0.0003 | 0 | 1.19 | 99.94% | 1 |
| m 裁剪页未裁切 + 拉直 7.25° | 2144×1424 | 0.0004 | 0 | 9.56 | 99.93% | **24（1 个像素）** |
| n 没编辑的相机 JPG | 4288×2848 | 0 | 0 | 0 | 100% | 0 |

**没做到「全部 ≤ 1 码值」的原因：**

1. **连续几步 uint8 取整会放大 float32 的取整翻转（c、d、e）。**
   - Python 每一步（曲线、黑点、饱和度、自然饱和度、暗角、LUT 后的 apply_base）都落成 uint8，着色器照做。
   - 但 GPU 的 pow、log2 和运算顺序与 numpy 不逐位相同，前一步偶尔翻转 1 个码值。
   - 后面的饱和度、暗角、陡的 LUT 把它放大到 2–4 码值。
   - 只出现在 ≤ 0.001% 的像素上，平均和 p95 不受影响。
   - 要逐位一致，得在着色器里复刻 numpy/libm 的超越函数，不现实。
2. **拉直后的有效区边界（m）：**
   - Python 用 float64 判断取样点是否在 `[-1e-3, W-1+1e-3]` 内，着色器只有 float32。
   - 落在边界 1e-4 像素以内的点会判反，这张图上只有 1 个像素：一边是填充色，一边是图像。
   - 试过在着色器里用双 float（fma 误差项）算坐标，GPU 编译器把误差项优化掉了，没有用，已撤回。
   - 只出现在裁剪页的未裁切画面上；成片按有效区收框，不受影响。

**更正上一轮：**`REPORT.md` 初版写的「全部像素 ≤ 1 码值」，是把占比四舍五入到 4 位小数后得到的 100%。原始数据里有个别像素差 2–7 码值（预览 45 对中 16 对、导出 8 对中 4 对，占比 < 0.005%）。`REPORT.md`、`ARCH.md`、`PROGRESS.md` 已改正，并在 REPORT 开头加了更正说明。

## 5. CI 和 Windows

已写进 `.github/workflows/ci.yml`，**这里没有推送，所以 CI 一次也没在 GitHub 上跑过**：
- `check` 作业（ubuntu-latest）：装 pnpm 10.33.2、Node 22，跑 `pnpm -C frontend install --frozen-lockfile`，再 `make check`。环境变量 `GXR_REQUIRE_FRONTEND=1` 和 `GXR_REQUIRE_GPU_TEST=1` 让构建核对和显卡对拍必须真跑：找不到 Chrome 或拿不到适配器就失败，不跳过。
  - ubuntu-latest 自带 Google Chrome。
  - Linux CI 上加了 `--no-sandbox` 和 `--disable-dev-shm-usage`。
- 新增 `gpu-parity` 作业（windows-latest、macos-latest）：跑 `test_gpu_parity.py` 和 `test_gpu_frontend.py`。
  - Windows 上 Chrome 的 WebGPU 软件适配器是 SwiftShader（Vulkan），不是 D3D12 WARP。
  - 所以它证明的是着色器算法在 Windows 版 Chrome 上一致，不能代替 D3D12 实机。

只能请机主的朋友在 Windows 实机上确认的，清单见 `ARCH.md` 第 9 节。这一步相关的：
- Chrome 或 Edge 的 `navigator.gpu` 能拿到 D3D12 适配器；
- 开开关后拖滑块不掉帧；
- 竖拍和 JPG 的方向正确；
- 窗口缩放和高分屏下画布清晰。

## 6. `make check`

在工作树里跑完整的 `make check`，结果为 `exit 0`，耗时 5 分 47 秒。各项：
- ruff lint 和格式、mypy strict（111 个源文件，无问题）；
- scan_secrets、bandit；
- dead_flags（3 个开关都有引用）、private_bytes（`--tracked --dist`，301 个文件）；
- check_agents_md（12 个目标）、large_files、export_openapi `--check`；
- **check_frontend**（重新构建的产物与提交的逐字节一致，`tsc --noEmit` 通过）；
- lint-imports（2 条约束都保持，`gxr_studio.gpu` 已加进去）、deptry、vulture、pylint 重复代码检查（10.00/10）。

测试：876 个通过，697 个跳过，用时 5 分 29 秒。跳过的是需要本机 g127 DAT、标定文件、`captures/` 样本的测试，工作树和 CI 上都没有这些数据。覆盖率 89.81%：

| 模块 | 覆盖率 |
|---|---|
| `api/gpu_routes.py` | 97% |
| `gpu/box.py` | 100% |
| `gpu/source.py` | 91% |
| `gpu/tables.py` | 92% |
| `render/service.py` | 90% |

整轮测试跑到一半时又改了 `gpu_stage.js`：开关先于建设备、设备丢失后回到服务器、换配方表不闪、裁切框失败回到服务器。改完后单独重跑了 `test_gpu_frontend`、`test_gpu_parity`、`test_gpu_api`、`test_web_smoke`、`test_web_frontend`，120 个全部通过，并在工作室里复查了开关开和关两种状态。

公开仓库检查：
- private_bytes 按内容扫描通过；
- 新文件里没有理光字节、没有机主照片：测试素材全部是合成的，真实 DNG 的对拍脚本和结果放在本仓库的 `research/studio_gpu_r1/impl/`，没进 gxr-studio；
- 新依赖只有 3 个前端开发依赖（MIT、Apache-2.0、BSD-3-Clause），传递依赖的许可都写进了 `docs/dependencies.md`，其中 lightningcss 是 MPL-2.0，只在构建机运行，不进产物。

## 7. 已知问题和下一步

- 首次冷打开（没预热的单元）0.4–0.9 s，超出 150 ms 预算。
  - 原因是 Python 第一次烘焙配方，含模型加载。
  - 办法：导入后预热全部单元；或者按 ARCH 把烘焙搬进 Rust 或计算着色器。
- 新 Chrome 用户目录第一次编译着色器约 1.5 s，之后 Chrome 有缓存。
- 显存预算固定 640 MB（源图 LRU）。老显卡或 Windows 核显上可能要按 `adapter.limits` 调小。
- 显示时缩小用 2×2 超采样，没有 mipmap。JPG 底图（4288 宽）缩到窗口时，细节的抗锯齿比浏览器 `<img>` 略差。只影响显示，不影响读回和导出。
- 设计系统：这一步只有画布区域换了设计系统的舞台灰（`#2a2a2a`，画布外的空白和底色）。按钮和面板按要求留给第 5 步。
- 设备丢失和数据加载失败时会自动回到服务器出图，但还没有专门的界面提示。

## 8. 本机脚本（不进 gxr-studio）

| 文件 | 用途 |
|---|---|
| `impl/cases.json`、`impl/parity_page.mjs`、`impl/parity_ref.py` | 真实 DNG 对拍：在工作室页面里调用 `gpu_stage.route()`，读回成片，再用生产函数算参考图 |
| `impl/measure_studio.mjs` | 在现有工作室里实测拖动和换照片（真实鼠标、真实接口） |
| `impl/parity-real-r1.json`、`impl/parity-synthetic-swiftshader.txt` | 颜色结果 |
| `impl/studio-measure-r{1,2,3}.json`、`*-frames-*.json` | 拖动、换照片的原始数据和逐帧数据 |

## 9. 清理

结束时：
- 我启动的工作室（49731）已用 SIGINT 退出；
- Chrome 每次都正常关闭；
- 临时目录 `/Volumes/Workspace/Scratch/tmp/projectricoh/gpu-preview-r1/` 已删除（临时图库、应用数据、DNG 副本、Chrome 用户目录、读回像素）。

工作树里保留以下内容，都已被 git 忽略：
- `.venv`、`frontend/node_modules`，供 CI 以外的人构建；
- 跑测试时生成的 `.coverage`、`.mypy_cache`、`.ruff_cache`。

没有做任何 git 写操作。
