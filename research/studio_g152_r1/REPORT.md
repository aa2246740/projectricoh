# 已支持第 152、153 代相机配方文件

Studio 工作树已加入 152、153 的发布包和测试包支持，并单独登记旧格式的 150。配方页依次显示 8 个内置配方、文件里的 Looks、文件里的「我的配方」。最终 `make check` 通过，1212 项测试通过，其中新代数测试 263 项，覆盖率 92.65%，无失败、错误、跳过或重跑。

基线为 Studio 自有仓库的 `main`，HEAD `e73a7af474e137b26862f252da0a8ad58b5d3793`。本轮没有提交、建分支或推送。工作开始时已先运行 `df -h /Volumes/Workspace`，再核对 APFS、可写、Volume UUID `14BE04EB-AF49-497E-B36A-B078B2F7C5E8`，可用约 1.0 TiB。

## 文件改动

| Studio 相对路径 | 改动 |
|---|---|
| `src/gxr_studio/camdata/datcodec.py` | 登记 150、152、153。校验 GXDP v2、GXFX 和 R3，展开 Look，保留文件内容供逐字节往返。 |
| `src/gxr_studio/camdata/knob_table.py` | 新增 R2、R3 整数档位和剂量读取。 |
| `src/gxr_studio/camdata/intake.py` | 不支持代数时列出全部已支持代数。 |
| `src/gxr_studio/render/params.py` | 编辑记录保留 Look、文件内用户配方的类型和内容摘要。 |
| `src/gxr_studio/render/recipes.py` | 从 DAT 读取名称、顺序、单元掩码和默认值，用原整数核心计算完整行。 |
| `src/gxr_studio/render/service.py` | 记录本次会话中不支持的代数，返回真实状态，使用已导入文件的菜单。 |
| `src/gxr_studio/api/camdata_routes.py` | 导入失败保留原数据，同时记录不支持的代数。 |
| `src/gxr_studio/api/finish_routes.py` | 区分缺配方文件、不支持代数、缺校准数据和缺 RAW。 |
| `src/gxr_studio/api/render_routes.py` | 保存配方前按当前文件校验条目身份和档位。 |
| `web/assets/camdata.js` | 不凭卡的存在推断缺 DAT，显示不支持的代数，导入后刷新状态。 |
| `web/assets/caps.js` | 支持重新读取照片的配方能力。 |
| `web/assets/preview.js` | 保留条目身份，各配方分别记住档位，导入后刷新菜单和能力，防止较早的请求覆盖新菜单。 |
| `web/assets/recipes.js` | 按文件顺序显示 Looks 和用户配方，分开判断 RAW 与数据状态，条目失效后仍能重新选择。 |
| `tests/g152_support.py` | 新增本机包定位和相机 C 参考编译工具。 |
| `tests/support/g152_reference.c` | 新增调用相机原解析器、R3 请求和整数核心的主机比较入口。 |
| `tests/test_g152.py` | 新增解析、往返、损坏拒收、整数行、名称和掩码、状态、编辑、预览及导出测试。 |
| `tests/test_camdata_api.py` | 更新不支持代数的精确文案断言。 |
| `tests/test_render.py` | 状态提示断言改为实际缺失项。 |
| `tests/test_web_frontend.py` | 固定文案检查使用「未导入相机配方文件」，去掉这次修正的错误卡状态文案要求。 |
| `README.md` | 更新已支持代数与文件内配方说明。 |

本目录保存可重跑的检查脚本、日志、摘要和本报告。没有把 DAT、552 B 行、照片或第三方 LUT 数据复制进 Studio 仓库。依赖和锁文件未变。

## 代数与六份包

当前登记的代数为 **127、129、131、135、137、138、150、152、153**。其余代数仍拒绝。新增的 7 个无本机数据依赖的用例分别拒绝 0、126、139、149、151、154、999。

| 包 | 大小 B | Looks | 用户条目 | SHA-256 |
|---|---:|---:|---:|---|
| 150 发布 | 87464 | 0 | 0 | `c4878f6600cec8b2dfe973c0888bc9c61bcd3a51e6d20a63e12c7dcceb3f9b78` |
| 150 测试 | 87464 | 0 | 3 | `68418fe71744c0fabd8dde7fcb88782631a71767521804b0cf580ebcbd4252c8` |
| 152 发布 | 90384 | 10 | 0 | `5ec4f1d2882cf30e1f3e82ffc8469fc7a4381867704e08a97951ba762aba4ac6` |
| 152 测试 | 90384 | 10 | 3 | `563c922711d4702a47724440537f9b29f4b5a920ab513dfffaf63a234955bc92` |
| 153 发布 | 90164 | 10 | 0 | `e6dab16235dd6fad870c6c6f4935a078351de10334e2145cc94e940598b7083b` |
| 153 测试 | 90164 | 10 | 3 | `5afc388902c9931d55c831e5afc27684d032193c9775e77a8509e9098e65ba7b` |

六份包均从指定的 `firmware/package_*` 目录读取。全部通过头和体 CRC、区段、行池、原厂 04、GXUI 绑定、条目规则以及 `pack(parse(raw)) == raw`。152、153 另校验 GXFX 的两个 CRC、内容 CRC、行值、引用、填充及单元掩码。包路径与每组输出摘要见 [byte_equality.json](byte_equality.json)。

150 沿用 GXDP v1 和 kv2 R2，并非 R3 的字节布局子集。本轮将它作为已有 R2 规则的独立代数登记。两份 150 与对应 152 的完整三个单元记录、映射、范围、GXUI 配置、用户条目及全部控制档位和剂量相同，24 个内置 552 B 条目逐字节相同。它没有 Looks。

152、153 的 R3 块均为 7904 B，SHA-256 `e91c8e0aa7b8dfefc4b662438acd3ca0a927a97099dc534c24f1dda32352e64c`。150 的 R2 块为 17384 B，SHA-256 `43405f6c5f63050505e958882dcd260f2a9e1f707d3b407860041787964992f9`。解析器先核对登记的块摘要，再从文件读取整数剂量。R3 的档位按相机规则从控制范围和步长恢复。旧代数继续由原有本机夹具测试覆盖。

## 完整 552 B 比较

参考侧直接编译 `engine_v60_g152` 和 `engine_v62_g153` 的 `gate.c`、`semantic.c`、`common.c`、`fx_pool.c`、`ui_v2_data.c`、`memory.c`、`kv_data.c`、`kv_ui.c`、`kv_math.c` 及原 CRC 函数。参考侧执行原解析器和 `uv_validate`，再用 `fx_expand`、`kv_data_request`、`kv_apply_work` 计算。Studio 侧执行 `CameraData.resolve`，比较全部 552 B，包含九行、T、A14/B14 和 CRC。

下表每格的 **4/4** 表示 152 发布、152 测试、153 发布、153 测试四份 DAT 均完全相同，共 120 组。每组两侧完整 SHA-256 在 `byte_equality.json` 中。

| Look | 50mm `jlaunch` | 28mm `qlaunch` | MOUNT `l08firm` |
|---|---|---|---|
| M9 STD | 4/4 相同 | 4/4 相同 | 4/4 相同 |
| HNCS HiCon | 4/4 相同 | 4/4 相同 | 4/4 相同 |
| Tri-X 400 | 4/4 相同 | 4/4 相同 | 4/4 相同 |
| Portra 400 | 4/4 相同 | 4/4 相同 | 4/4 相同 |
| Velvia 50 | 4/4 相同 | 4/4 相同 | 4/4 相同 |
| Kodachrome25 | 4/4 相同 | 4/4 相同 | 4/4 相同 |
| HNCS LowSat | 4/4 相同 | 4/4 相同 | 4/4 相同 |
| Vision3 500T | 4/4 相同 | 4/4 相同 | 4/4 相同 |
| instax mini | 4/4 相同 | 4/4 相同 | 4/4 相同 |
| Metropolis | 4/4 相同 | 4/4 相同 | 4/4 相同 |

每个 Look 的默认强度为 100，其余可用控制默认 0。范围、可选档位、到顶标记和隐藏控制检查与其基底的内置配方相同。60 个参数化用例还覆盖两个代数、三单元、十个 Look 的全部合法单控制档位，共 8846 次完整 552 B 比较，包含默认档位的重复比较。测试包的三个用户条目 `FCC-001`、`FCC*002`、`GRN*001` 在两个代数、三单元上另有 18 组默认行比较相同，默认控制值从 GXUI 恢复。

这证明主机上的整数展开和相机源码计算相同，不代替相机 ISP 的照片验证。MOUNT 继续显示「未校准」。

## 面板与文案

| 状态 | 面板显示 | 行为 |
|---|---|---|
| 尚未导入配方文件 | 未导入相机配方文件 | 显示导入入口，配方不可用。卡上已有文件也不声称缺文件。 |
| 文件代数不支持 | 不支持第 N 代，并列出支持代数 | 不同时声称缺 RAW，保留原已导入数据。尚无可用数据时在本次会话保留此原因。 |
| 照片没有 RAW | 配方需要 RAW 文件；拍摄时将画质设为 RAW+JPEG | 不再叠加缺配方文件的引导。 |
| 就绪 | 无阻塞原因 | 内置配方、Looks、用户配方可选。 |
| 缺校准数据 | 未导入校准数据 | 使用原有校准入口，不把它解释成缺 RAW。 |

新增或改动的可见文案如下。文件内名称不翻译。

| 位置 | 文案 |
|---|---|
| 不支持代数的导入错误和面板原因 | `不支持第 N 代相机配方文件。目前支持第 127、129、131、135、137、138、150、152、153 代。` |
| 配方页新增分组 | `Looks`、`我的配方`。 |
| 新增文件内名称 | `M9 STD`、`HNCS HiCon`、`Tri-X 400`、`Portra 400`、`Velvia 50`、`Kodachrome25`、`HNCS LowSat`、`Vision3 500T`、`instax mini`、`Metropolis`。 |
| 测试包用户条目名称 | `FCC-001`、`FCC*002`、`GRN*001`。 |
| 条目身份失效或不属于该单元 | `找不到这个配方。请重新选择。` |
| 请求的详细信息 | `配方类型无法识别。`、`配方条目无法识别。` |
| DAT 校验的详细信息 | `kv2 点表与已登记的不同`、`这一代需要 kv2 点表`。 |
| GXFX 校验的详细信息 | `效果区边界不合格`、`效果区头、尺寸或 CRC 不合格`、`效果条目或名称不合格`、`效果与单元基底不一致`、`效果行索引越界`、`效果引用的内置行索引越界`、`效果行数值不合格`、`效果内容 CRC 对不上`、`效果行引用、去重或填充不合格`。 |

这些原有文案改为在真实条件下使用，文字本身沿用：`未导入相机配方文件`、`还没有导入相机配方文件`、`请先导入校准数据`、`未导入校准数据`、`配方需要 RAW 文件`、`拍摄时将画质设为 RAW+JPEG`。`/api/render/status.hint` 现在返回对应的配方文件或校准数据原因，去掉了无条件声称卡上缺 DAT 的提示。沿用的损坏说明为 `相机配方文件读不出来或被改动。请重新导入后再试。`；校准说明为 `缺少校准数据`、`校准数据与相机配方文件不匹配`、`校准数据读不出来或被改动。请重新导入后再试。`。

固定 Playwright 1.61.1、Chromium 1228 已运行产品组件，覆盖上述状态、按钮顺序、Look 和用户条目选择、档位记忆、无效条目重新选择、较早请求晚返回、失败或成功导入后的刷新，以及多卡选择。浏览器接口使用隔离夹具响应，真实 DAT 导入、编辑、RAW 预览和导出另由 API 测试覆盖。[ui.json](ui.json) 保存结果。

## 检查与复跑

构建、测试和浏览器检查均以 `nice -n 10` 启动，验证作业最多两个并行，浏览器使用单进程参数。TMPDIR、pytest basetemp 和浏览器数据目录均位于 `/Volumes/Workspace/Scratch/tmp/projectricoh/studio-g152-r1/`。全量检查的 Ruff、mypy 缓存和覆盖率输出也定向到该目录。没有启动独立 Studio 服务，没有访问主人正在运行的实例、默认图库、默认导出目录或默认应用数据目录。

| 检查 | 结果 | 回执 |
|---|---|---|
| 初轮定点检查，五个测试文件 | 355 通过、1 失败。失败是旧测试仍要求缺数据提示包含「插入」；已按真实原因更新。 | `focused-initial.json`、`focused-initial.log` |
| 定点补测，名称和掩码、150 数据、状态、未知代数 | 15 通过、246 未选择。 | `focused-final.json`、`focused-final.log` |
| 最终代码的独立六包往返与 C 比较 | 6 包往返、120 组 Look、18 组用户条目通过，157 个所用输入摘要未变。 | `byte-equality-final.json`、`byte_equality.json` |
| 首轮 `make check` | 1203 通过、6 失败，覆盖率 92.27%。五项因旧代数规范化数据没有 DAT 模板而失败，一项是旧文案断言。 | `make-check.json`、`make-check.log` |
| 兼容性补测 | 12 通过、260 未选择。旧规范化数据继续可用；150、152、153 缺模板仍拒绝。 | `compatibility-final.json`、`compatibility-final.log` |
| 固定 Chromium 产品组件检查 | 5 种状态、2 种导入结果、6 次配方编辑、多卡选择、菜单晚返回均通过，页面错误 0。 | `ui-complete.json`、`ui.json` |
| 最终 `make check` | 1212 通过，失败、错误、跳过和重跑均为 0，覆盖率 92.65%，超过 85% 门槛。 | `make-check-final.json`、`make-check-final.log`、`checks.json`、`pytest.xml`、`coverage.json` |

全量检查中的 Ruff 检查和 163 个文件的格式检查、106 个 Python 源文件的 mypy、秘密扫描、Bandit、死开关、272 项仓库及分发包私有字节检查、11 个 Make 目标、文件尺寸、OpenAPI、两条导入约束、依赖、未用代码和重复代码检查均通过。最终日志仍有 3 条 pytest 警告，分别为拟合条件数、合成库测试的 SQLite 连接未关闭、Sentry 选项弃用。本轮未进一步处理这三条警告。Bandit 也报告了原注释格式提示，未报告检查失败。

浏览器初轮脚本把「无 RAW、但配方文件已导入」的按钮数误写成 8，修正为 21 后通过，原记录为 `ui-first.json`。继续检查错误出口时，又复现本轮新增刷新会清掉多卡选择的情况，见 `ui-multiple-before.json`。已把失败后的面板刷新限制在不支持代数的场景，保留多卡选择控件，同一脚本复测通过。

从 Studio 目录复跑，先重新核对外置卷身份并创建上述临时目录。核心命令如下：

```sh
export TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/studio-g152-r1
export PYTHONDONTWRITEBYTECODE=1 GIT_OPTIONAL_LOCKS=0 UV_OFFLINE=1
mkdir -p "$TMPDIR"
export RUFF_CACHE_DIR="$TMPDIR/ruff-cache" MYPY_CACHE_DIR="$TMPDIR/mypy-cache"
export GXR_STUDIO_HOME="$TMPDIR/check-home" GXR_STUDIO_LIBRARY="$TMPDIR/check-library"
export GXR_STUDIO_EXPORT="$TMPDIR/check-export" GXR_STUDIO_VOLUMES="$TMPDIR/check-volumes"
nice -n 10 uv run --frozen --offline --no-sync python ../research/studio_g152_r1/verify_data.py
nice -n 10 node ../research/studio_g152_r1/verify_ui.mjs
nice -n 10 uv run --frozen --offline --no-sync pytest -q tests/test_g152.py --basetemp="$TMPDIR/pytest-g152"
export COVERAGE_FILE="$TMPDIR/coverage-data"
export PYTEST_ADDOPTS="--force-reruns 0 --basetemp=$TMPDIR/pytest-check --junitxml=$TMPDIR/check.xml --cov-report=json:$TMPDIR/coverage.json"
nice -n 10 make check
```

原始运行的完整命令、时限、退出码、耗时、nice 和日志摘要在各个 JSON 回执里。真实 DAT、相机 C 源码或照片夹具缺失时，对应测试按仓库原有方式跳过。未知代数的合成头测试不依赖这些本机文件。

最终检查前后的 269 个 Studio 文件、Git 目录的 757 个文件摘要均相同，见 `source-final-before.json`、`source-final-after.json`。Studio 文件集合摘要为 `1b95dabf06b43b87a6b6bd281c7341289f342d6148a657ec6303cb81f068f741`。HEAD 与分支保持原值。`git diff --check` 通过。

## 边界与未做项

- 没有访问存储卡，也没有相机运行、上卡或刷机验证。
- 没有改 HDR 对齐、首次引导、底部禁用按钮提示、写卡或相机界面。
- 没有改照片的单元识别规则。主机比较为每个指定单元分别验证，实际照片仍沿用现有元数据识别。
- 没有扩大 28mm 或 MOUNT 的颜色校准范围。
- 浏览器均已关闭，未发现带本任务路径的残留进程或 `code_sign_clone` 目录。指定 Scratch 已删除，见 `cleanup.json`。

本轮从 2026-11-01 17:24 UTC 开始，约一小时内收尾，未超过三小时时限。改动保留在 Studio 工作树，供用户审阅和提交。报告及回执的文件摘要见 `SHA256SUMS`。


## 修复轮

本节按用户对独立复审的裁定修正 P1-02、P1-03 和不支持版本的主提示，替代前文对应的缓存与文案说明。前轮报告和原始回执保留。本轮从 2026-11-01 19:08:34 UTC 开始，时限 60 分钟。

P1-01 已撤回，没有改 `engine/data/final.json`、相关数据表或公开数据检查规则。该文件修前与修后 SHA-256 均为 `2d2793784b7cd99e6db9cd43351180017d15a493562a928c34e6a2d338e787f2`。

### 本轮文件

| Studio 相对路径 | 改动 |
|---|---|
| `web/assets/caps.js` | 能力缓存绑定数据版本。数据更新清空能力请求记录并递增版本计数，保留拍摄信息缓存。旧请求完成后，原调用者重读当前能力。 |
| `web/assets/preview.js` | 数据更新时清空菜单、在途 Promise 并递增菜单版本。旧请求无论成功或失败，都让等待者重读当前菜单。 |
| `tests/test_web_frontend.py` | 加入三项指定场景和两项旧请求失败变体，沿用 Node 模块测试方式。 |
| `tests/support/recipe_cache.mjs` | 用明确的请求完成顺序测试实际产品模块，不依赖定时等待。 |
| `src/gxr_studio/camdata/datcodec.py` | 将主提示分为需要更新和版本不支持两种，诊断文字单独生成。 |
| `src/gxr_studio/camdata/intake.py` | 不支持代数的诊断只放在 API `detail`。 |
| `src/gxr_studio/api/camdata_routes.py` | 从已读取的文件头取得本次会话的失败代数，不再依赖错误响应的额外字段。 |
| `src/gxr_studio/render/service.py` | 状态主句使用定稿文案；失败文件的代数与支持列表只在 `detail` 提供。 |
| `tests/test_camdata_api.py` | 更新旧文案断言，新增 126、139、151、154、200 五项真实 API 文案与诊断检查。 |
| `tests/test_g152.py` | 更新不支持代数的状态断言。 |
| `README.md` | 说明两种主提示及缓存更新行为。 |

报告目录中的 `verify_ui.mjs` 同步更新主提示夹具，新增本轮日志、JUnit、源码快照和汇总。产品依赖与锁文件未变。

### 修前与修后

先阅读并理解复审的 `minimal-cache-fix.diff`，再在产品模块上修正。除了复审补丁的成功响应路径，本轮也处理了旧菜单请求失败的路径；能力缓存另有随数据更新递增的计数，防止较早请求在版本变化后仍作为当前结果返回。

永久测试位于 `tests/test_web_frontend.py::test_recipe_cache_after_data_change`。测试加载实际 `state.js`、`camdata.js`、`caps.js`、`preview.js`，仅使用隔离接口响应。请求通过 Promise 明确释放，没有时间间隔轮询，也没有模拟产品缓存本身。

| 场景 | 修前观察 | 修后观察 |
|---|---|---|
| `previous-photo-after-import` | 返回照片 A 后仍为 `none`，能力请求只有 1 次。 | 返回 A 得到 `full`，能力请求 2 次，拍摄信息仍只请求 1 次。 |
| `data-change-pending-caps` | 等待者收到旧的 `none`，缓存也为 `none`。 | 等待者和缓存均为当前 `full`，请求共 2 次。 |
| `data-change-pending-catalog` | 等待者与缓存均为 0 个 Looks。 | 等待者与缓存均为当前 10 个 Looks，请求共 2 次。 |
| `data-change-pending-caps-error` | 等待者与缓存仍为旧请求的 `error`。 | 重读当前能力，均为 `full`。 |
| `data-change-pending-catalog-error` | 等待者收到旧请求的拒绝，缓存为空。 | 重读当前菜单，等待者与缓存均为 10 个 Looks。 |

修前 5 项全部失败，修后同一组 5 项全部通过。见 `fix-cache-before.json`、`fix-cache-before.log`、`fix-cache-before.xml` 与对应的 `fix-cache-after.*`。逐项对应和文件摘要在 `fix-scenarios.json`。

```sh
uv run --frozen --offline --no-sync pytest -q tests/test_web_frontend.py \
  -k recipe_cache_after_data_change --basetemp="$TMPDIR/pytest-cache"
```

随后缓存、文案和状态的定点检查为 28 项通过、331 项未选择，见 `fix-targeted-final.*`。定点初轮曾因新增测试放置位置错误，把原大文件断言留在新函数中，出现 5 项 `NameError`；已将断言移回原函数，没有删减断言，原日志保留为 `fix-targeted.*`。

### 定稿文案

- 文件代数比当前最大支持代数新时：`这个相机配方文件需要更新版本的 GXR 工作室。`
- 其它不支持的代数：`不支持这个版本的相机配方文件。`
- API `detail`：`第 N 代。支持第 127、129、131、135、137、138、150、152、153 代。`

主句不含代数数字或支持列表。不支持的导入响应只返回 `error`、`message`、`detail`。同一会话的状态也在 `detail` 保存诊断；已支持文件的代数元数据保持原用途。

### 最后一次完整检查

本轮只运行一次完整 `make check`，强制零重跑。仅通过临时 Make shell 将 import-linter 缓存定向 Scratch，其余检查命令按仓库 Makefile 执行。TMPDIR、pytest basetemp、Ruff、mypy、import-linter 和覆盖率工作文件都位于指定 Scratch；`GXR_STUDIO_HOME`、图库、导出和卷根均设置为独立测试目录。构建与测试由 `nice -n 10` 启动，最多两个验证作业并行，没有子代理或浏览器会话。

本轮唯一一次完整 `make check` 通过：1222 项测试通过，失败、错误、跳过和重跑均为 0，覆盖率 92.63%，超过 85% 门槛。缓存场景 5 项及 API 文案 5 项均在全量检查中通过。仍有拟合条件数、合成库 SQLite 连接未关闭、Sentry 选项弃用三条警告，本轮未处理这些警告。命令、时限、退出码和日志摘要在 `fix-make-check.json`，原始输出在 `fix-make-check.log`，JUnit 与覆盖率分别为 `fix-pytest.xml`、`fix-coverage-full.json`，核对后的汇总为 `fix-checks.json`。

本轮 TMPDIR 为 `/Volumes/Workspace/Scratch/tmp/projectricoh/studio-g152-r1/fix/`。实际 Make 命令如下，临时 shell 的原样副本为 `fix-check-shell.sh`。

```sh
nice -n 10 make check SHELL="$TMPDIR/check-shell.sh"
```

检查期间，270 个 Studio 文件与 Git 目录的 757 个文件摘要均未改变，见 `source-fix-check-before.json`、`source-fix-check-after.json`。冻结的 Studio 文件集合 SHA-256 为 `50deddfa740d11537ae5362019a11e5291331d5972393840cdfc5761b2809791`，分支仍为 `main`，HEAD 仍为 `e73a7af474e137b26862f252da0a8ad58b5d3793`。本轮开始前后的 Git 文件摘要也相同。`git diff --check` 通过。

Scratch 已删除，未发现本任务残留进程或 `code_sign_clone` 目录，见 `fix-cleanup.json`。没有访问相机卡、主人的运行实例或默认图库、导出、应用数据目录，没有 Git 写入。本轮约 28 分钟内收尾，未超过 60 分钟时限。
