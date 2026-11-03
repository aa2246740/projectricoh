可以交复审

Studio 已支持第 154、155 代发布包和测试包，配方面板按文件顺序显示十个 Looks 和已存配方。最终 `make check` 全过：1,513 项通过，失败、错误、跳过、重跑均为 0，覆盖率 92.69%。两个代数测试模块共 554 项。完整行、真实 API、面板和缓存检查均通过，指定 Scratch 已清理。

Studio 基线为 `main`，HEAD `e6738e862ece103006e1b15615b6901892cae624`。改动保留在工作区，没有 Git 写操作，没有子代理。

实现登记了 154/155 的 GXDP v2 / GXFX / R3、平铺列表容量限制与 MOUNT fix B，以及 155 的 69,632 B 代码上限。154 保留 65,536 B 上限。GXFX 的行容量取自实际文件；机身绑定标识和 ABI 逐字节保留。

| Studio 相对路径 | 改动 |
| --- | --- |
| `src/gxr_studio/camdata/datcodec.py` | 登记 154/155 的 Profile，按代数限制代码长度，校验每个单元的平铺列表容量。 |
| `src/gxr_studio/camdata/knob_table.py` | 按 Profile 恢复 MOUNT 的非 04 配方对 50mm 控制记录的引用。 |
| `src/gxr_studio/render/recipes.py` | 将当前代数的控制规则交给读取器，沿用已有 Looks 和用户条目入口。 |
| `tests/g152_support.py` | 增加 154/155 包路径及原 C 源码入口；保留六包 `PACKAGES`，新增十包 `ALL_PACKAGES`。 |
| `tests/support/g152_reference.c` | 增加相机原验证入口与内置配方计算入口。 |
| `tests/test_g152.py` | 扩展新包往返、缺模板、损坏、完整行和 API 目录检查；未知代数样本改为 156。 |
| `tests/test_g154_g155.py` | 新增实际尺寸、MOUNT fix B、完整行、列表容量、内层损坏、失败保留和版本刷新检查。 |
| `tests/test_camdata_api.py` | 更新支持列表，保留两条主提示，未来代数样本改为 156。 |
| `README.md` | 说明新增支持、MOUNT 规则、列表容量和只读范围。 |

没有变更依赖和锁文件。没有把固件、DAT、完整行或第三方 LUT 数据复制进 Studio。参考侧直接读取项目 `firmware/` 路径，私有中间文件只写入指定 Scratch。

| 包 | DAT B | 代码 B | Looks / 用户 | SHA-256 |
| --- | ---: | ---: | ---: | --- |
| 154 release | 89,624 | 64,728 | 10 / 0 | `3c63ae08a1387af9aa5c7d30107a17e37ec743b592c6f8833e70374e8b760449` |
| 154 test | 89,624 | 64,728 | 10 / 3 | `ac4263a0083aff1f04ab1433029b7ba354d67083ad09292f2af49bbc59abb83e` |
| 155 release | 86,632 | 65,668 | 10 / 0 | `308c7096b535ab4ce08407311439494b496dea2b4b855e228b8c8a1e2acd046c` |
| 155 test | 89,508 | 68,544 | 10 / 3 | `a1e731f1751135d074af469f4e21f7b5eeedf1da7cd8ac0c4171d06654fa6f45` |

154 的 GXFX 行容量为 `8/28/32/32`，155 为 `0/16/12/12`，两代实际使用均为 `0/10/9/10`。用户格式槽位仍为 32；每个单元按可见 Looks 数 K 校验 `U <= min(32, 40-K)`。当前 K=10 时，0/30 条用户记录通过，31/32 条拒收；八个样本在三个单元上与相机原验证入口一致。

MOUNT 的 01–03、05–08 控制表按各代原 `kv_data_recipe` 规则引用 50mm，04 仍取 MOUNT。01 的 Amount 档位为 `0/25/50/75/100/125/150`，Satu 上限为 +6。实际基底和原厂 04 仍来自该单元，完整行由原整数核心计算。

四份文件各有十个 Looks，测试包各有三个用户条目。120 组 Look、18 组用户和 96 组内置默认完整行，以及 31,040 次单控制档位比较均与各代原 C 引擎逐字节相同。单控制计数包含默认档位的重复比较。相机参考侧编译各自的 `engine_v63_g154` / `engine_v64_g155`，调用原 gate、semantic、`uv_validate`、`fx_expand`、`kv_data_request` 和 `kv_apply_work`。比较覆盖全部 552 B，包含九行、T、A14/B14、身份及 CRC；回执只保存 SHA-256。

九个旧代数 127/129/131/135/137/138/150/152/153 的解析字段、往返、菜单和 3,834 次内置默认及控制端点结果与 `e6738e8` 相同。PR #12 原入口的六包往返、120 组 Looks、18 组用户条目也已通过。旧入口只在运行时将输出定向本轮 Scratch，没有改写原报告目录。

固定 Playwright 1.61.1 / Chromium 1228 的产品组件检查通过 12 个面板、138 次选择，页面异常为 0。浏览器已关闭。

新包的 64 个 CRC、截断及有效外层 CRC 的结构错误样本均拒收。四包共八次失败上传保留原应用数据的文件集合和字节、原菜单及 `data_version`。连续导入 153 release、154 test、155 release、155 test 后，版本、用户条目与 MOUNT 控制信息均更新。五个实际 ES 模块缓存场景覆盖旧照片、在途能力和目录请求的成功及错误返回。

主提示沿用 `这个相机配方文件需要更新版本的 GXR 工作室。` 和 `不支持这个版本的相机配方文件。`；代数及支持列表只放 API `detail`。缺 DAT、缺 RAW、缺校准的单原因判断沿用 PR #12，并在全量检查中覆盖。

第一轮完整 `make check` 为 1,513 项通过、覆盖率 92.69%、三条既有警告，见 `make-check-initial.*`。随后仅调整测试助手的集合常量，保留 `PACKAGES` 的原六包范围，扩展测试改用 `ALL_PACKAGES`，再复跑原六包入口和最终全量检查。

最终全量于 2026-11-02 02:58:06–03:12:49 UTC 执行，1,513 项通过，失败、错误、跳过、重跑均为 0。覆盖率为 `11078 / 11952 = 92.68741633199464%`，超过 85% 门槛。仍有拟合条件数、合成库 SQLite 连接未关闭、Sentry 选项弃用三条既有警告。Ruff 检查与 164 文件格式检查、106 源文件 mypy、安全扫描、275 文件及分发包私有字节检查、Make 目标、文件尺寸、OpenAPI、导入边界、依赖、未用代码与重复代码检查均通过。

初轮定点检查为 648 通过、2 失败。我把 MOUNT 04 也误写成应等于 50mm，正确规则是仅非 04 配方引用 50mm；已修正这两项预期。原日志保留为 `focused.*`，修正后定点 8 项通过，最终全量也覆盖了它们。没有删除原失败回执。

| 检查 | 已有结果 / 回执 |
| --- | --- |
| 四包往返及 C 完整行 | PASS，`byte-equality.json`、`data-final.*`。 |
| 九代与基线比较 | PASS，`old-generations.json`。 |
| PR #12 原六包入口 | PASS，`pr12-equality.json`、`pr12-run.*`。 |
| 四包三单元产品面板 | PASS，`ui.json`、`ui-run.*`。 |
| 无本机数据的隔离副本 | 8 通过、546 按原因跳过，`portable-final.*`。 |
| 修正后定点检查 | 8 通过、110 未选择，`focused-final.*`。 |
| 第一轮全量 | 1,513 通过，92.69%，`make-check-initial.*`。 |
| 最终全量 | 1,513 通过，92.69%，零失败、错误、跳过、重跑；`make-check.*`、`checks.json`。 |

测试和构建以 `nice -n 10` 启动，pytest 串行，最多两个验证作业同时运行。TMPDIR、pytest basetemp、浏览器配置、Ruff、mypy、import-linter 和覆盖率工作文件均定向 `/Volumes/Workspace/Scratch/tmp/projectricoh/studio-g154-g155-r1`。缺本机 DAT、C 源码或 clang 时，相关永久测试按原因跳过；本轮正式全量没有跳过。隔离副本的 546 项跳过专门验证这条规则。

首个动作是 `df -h /Volumes/Workspace`，随后确认 APFS、可写、卷 UUID `14BE04EB-AF49-497E-B36A-B078B2F7C5E8`。外部中断后于 02:36:35 UTC 继续，先确认无本任务残留进程，Scratch 为空；按新的 85 分钟时限，截止为 04:01:35 UTC，见 `resume.json`。本轮在时限内收尾。

`check_results.py` 已确认 272 个 Studio 文件在最终检查前后完全相同，142 个输入文件与 801 个 Git 元数据文件前后完全相同。HEAD 与分支未变，`git diff --check` 通过。逐文件摘要在 `source-check-before/after.json`、`inputs-before/after.json`、`git-before/after.json`。本目录 `SHA256SUMS` 绑定报告、证据、九个 Studio 改动文件及输入文件。

2026-11-02 03:14:24 UTC 清理完成，删除 21,657 个临时文件、3,801,620,284 B。指定 Scratch 不存在，无本任务残留进程和打开的文件句柄，浏览器已关闭，见 `cleanup.json`。

从 Studio 目录复跑，先核对外置卷；运行器也会在写入前校验卷 UUID、APFS 和可写状态，并设置全部隔离路径。运行顺序如下，最终仍须删除 Scratch。

```sh
/usr/bin/python3 -I -B ../research/studio_g154_g155_r1/run_checks.py data-final uv run --frozen --offline --no-sync python -B ../research/studio_g154_g155_r1/verify_data.py
/usr/bin/python3 -I -B ../research/studio_g154_g155_r1/run_checks.py pr12-run uv run --frozen --offline --no-sync python -B ../research/studio_g154_g155_r1/verify_pr12.py
/usr/bin/python3 -I -B ../research/studio_g154_g155_r1/run_checks.py ui-run node ../research/studio_g154_g155_r1/verify_ui.mjs
/usr/bin/python3 -I -B ../research/studio_g154_g155_r1/run_checks.py portable-final uv run --frozen --offline --no-sync python -B ../research/studio_g154_g155_r1/verify_portable.py
/usr/bin/python3 -I -B ../research/studio_g154_g155_r1/run_checks.py make-check make check
/usr/bin/python3 -I -B ../research/studio_g154_g155_r1/check_results.py
```

检查清单的方式是在项目根运行：

```sh
/usr/bin/shasum -a 256 -c research/studio_g154_g155_r1/SHA256SUMS
```

本次实现范围内没有未决缺陷。g155 绑定尚未发布的 v3.10 机身；后续若复审改变 DAT 布局，需要更新登记并重跑对照。面板检查加载真实 ES 模块和实际 DAT 目录，接口响应隔离；真实导入及状态由 ASGI 测试覆盖，没有完整 Viewer 浏览器联测。

没有访问正在运行的 Studio、主人图库、导出或应用数据目录，没有访问真实存储卡。没有相机、上卡、刷机或相机 ISP 成像验收。工作室没有读取相机内的 40 B 记忆，也没有新增开机自动套用状态。
