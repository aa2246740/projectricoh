可以交付

2026-10-31，对 `studio` 基线 `e6952acb89de95e089c8e7080c5d92de99057cc4` 上的未提交工作区做第四轮定点复验。上一轮的 6 项部分关闭项和 3 项 R3 问题均已关闭。本轮未发现新增 P0、P1、P2。原有两个 P2 也已关闭，没有剩余 P2 影响交给用户日常整理、调整和导出照片。

主机已证：真实 HTTP API、实际前端控件和导出文件均通过复验。方向反例使用带非对称色块的合成 Orientation=6 JPG，以及配有合成 DNG 的 RAW+JPG；另用既有 GXR 样本回归。此结论针对本机 GXR Studio，不表示相机固件、实体存储卡或 Linux 环境已验收。

## 1. 逐项状态

| 编号 | 本轮状态 | 证据与结果 |
| --- | --- | --- |
| R3-01，P1 | 已关闭 | JPG 与 RAW+JPG 均通过原始尺寸、长边 512、2048、4096 的真实 HTTP 导出。另分别在界面点击“长边 2048 像素”并实际导出。文件尺寸、Orientation=1、红色色块位置均正确，见[API 像素核对](r4-evidence/orientation-api-r4.json)、[界面请求](r4-evidence/ui-orientation-r4.json)、[界面产物核对](r4-evidence/orientation-ui-artifacts-r4.json)。 |
| R3-02，P2 | 已关闭 | 8 组日期格式和时间开关保留全部 24 字；6 组字形边界均在画布内。仅替换末尾“北京”为“上海”时，图库缩略图、样式缩略图、预览和导出的像素均不同，见[字形边界](r4-evidence/stamp-r3.json)、[HTTP 后缀复验](r4-evidence/stamp-http-r3.json)。 |
| R3-03，P2 | 已关闭 | 原先 5 个请求均返回 422，主句统一为“请求无效。请刷新页面后重试。”，范围原因保留在非空 `detail`。39 项请求全部合规，见[完整记录](r4-evidence/copy-api-r3.json)。 |
| V2-19 | 已关闭 | 新测试检查真实导出接口的尺寸、EXIF 和色块重心，检查完整字形边界，并比较不同后缀的缩略图、预览及导出。当前整套测试通过；在独立进程内重新注入旧故障后，3 个相应测试都在目标断言处失败，见[断言敏感性](r4-evidence/test-sensitivity-r4.json)、[方向故障日志](r4-evidence/sensitivity-0.log)、[字形故障日志](r4-evidence/sensitivity-1.log)、[后缀故障日志](r4-evidence/sensitivity-2.log)。 |
| V2-12 | 已关闭 | 原先格式化截字和缩略图绘制截字均已消除，见[格式与边界](r4-evidence/stamp-r3.json)、[四路实际输出](r4-evidence/stamp-http-r3.json)。 |
| V2-17 | 已关闭 | 本轮剩余的 5 个非法参数主句已统一，39 项请求没有残留违规；与 r3 比较，前端文件没有变化，见[请求记录](r4-evidence/copy-api-r3.json)、[本轮变动清单](r4-evidence/changes-since-r3.json)。其余文案审计沿用 r3 的已关闭结果。 |
| R2-02 | 已关闭 | 原始尺寸和指定长边分支均保持竖拍方向；两种输入的界面 2048 导出也通过，见[API 核对](r4-evidence/orientation-api-r4.json)、[JPG 界面](r4-evidence/ui-PORTRAIT_JPG-2048-r4.png)、[RAW+JPG 界面](r4-evidence/ui-PORTRAIT_PAIR-2048-r4.png)。 |
| R2-04 | 已关闭 | 格式化保留全文，实际小图布局不越界，后缀更改能改变四路输出的像素，见[边界](r4-evidence/stamp-r3.json)、[HTTP 反例复验](r4-evidence/stamp-http-r3.json)。 |
| R2-07 | 已关闭 | 预览 quality=29、导出 quality=0/101、long_edge=63/30001 的原反例全部关闭；39 项返回均为 422 且主句合规，见[请求与响应](r4-evidence/copy-api-r3.json)。 |

## 2. 方向导出的实际结果

输入 JPG 的存储像素为 640×480、Orientation=6。以下尺寸是重新打开导出文件后读取的像素尺寸，全部文件的 Orientation 为 1。

| 输入 | 原始尺寸 | 长边 512 | 长边 2048 | 长边 4096 |
| --- | --- | --- | --- | --- |
| JPG | 480×640 | 384×512 | 480×640 | 480×640 |
| RAW+JPG，source=auto | 480×640 | 384×512 | 480×640 | 480×640 |

2048 和 4096 大于原图长边，因此保持原尺寸。8 次 API 导出均使用 `camera-jpg`，红色色块均位于转正后的右上角，重心与独立转正参考图的最大坐标误差小于 0.007 像素。见[逐项尺寸、EXIF、色块和产物 SHA-256](r4-evidence/orientation-api-r4.json)。

界面操作分别打开 JPG 和 RAW+JPG，点击“导出”页签、“长边 2048 像素”和实际“导出”按钮。捕获的两次请求均为 `long_edge=2048`、`source=auto`、quality=85，HTTP 200，界面显示“已导出 1 张”。两份实际文件均为 480×640、Orientation=1，色块重心最大坐标误差小于 0.154 像素。见[操作与网络记录](r4-evidence/ui-orientation-r4.json)、[文件核对](r4-evidence/orientation-ui-artifacts-r4.json)及[实际 JPG 产物](r4-evidence/ui-PORTRAIT_JPG-2048-r4.jpg)、[实际 RAW+JPG 产物](r4-evidence/ui-PORTRAIT_PAIR-2048-r4.jpg)。

## 3. 快速回归和覆盖率核实

| 检查 | 独立结果 | 证据 |
| --- | --- | --- |
| make check | 退出码 0；497 passed、0 failed、0 skipped，3 条 warning；检查总耗时 368.05 秒。覆盖 8115/8868 行，91.51%，门槛仍为 85%。 | [日志](r4-evidence/make-check.log)、[JUnit](r4-evidence/checks.junit.xml)、[覆盖率原始数据](r4-evidence/coverage-full.json)。 |
| portable_check.py | 退出码 0；359 passed、138 skipped，3 条 warning；62.83 秒。覆盖 7808/8868 行，88.05%。模块来自 Scratch 源码快照，相邻 firmware、captures、research 均不存在。 | [结果](r4-evidence/portable.json)、[日志](r4-evidence/portable.log)、[覆盖率原始数据](r4-evidence/coverage-portable.json)。 |
| ui_acceptance.mjs | 退出码 0；页面错误和失败响应均为空。JPG 配方禁用、曲线拖动、复原、1024/1360 宽度下的边框卡片回归通过。 | [结果](r4-evidence/ui-acceptance.json)。 |
| r2 导出脚本 | regression_r2.py、ui_regression_r2.mjs 均退出码 0。RAW、JPG、RAW+JPG 的原图、调整、配方、装饰分支通过；JPG 配方按能力限制不可用。单张导出使用 auto，错误原因和收起的详情仍保留。 | [API 回归](r4-evidence/regression-r2.json)、[界面回归](r4-evidence/ui-regression-r2.json)。 |
| r3 导出矩阵 | matrix_r3.py 退出码 0；36 组中 2 组 JPG 配方按能力限制拒绝，其余 34 组 full 与导出尺寸一致，`failures=[]`；8 组指定尺寸方向核对全部通过。 | [矩阵](r4-evidence/matrix-r3.json)。 |
| r3 界面补充 | ui_extra_r3.mjs 退出码 0，页面错误为空。继承与明确关闭的 8 个状态符合预期；批量两张成功，失败批次逐项保留原因和默认收起的详情。 | [结果](r4-evidence/ui-extra-r3.json)。 |
| 旧图库及几何 | baseline_fixture.py、acceptance.py、geometry_r2.py 均退出码 0。基线重新造出的旧图库首次读取时 sidecar 和媒体不变，旧编辑保留并可导出；10 组几何画布与有效区域回归通过。 | [旧图库/API](r4-evidence/acceptance.json)、[几何](r4-evidence/geometry-r2.json)。 |

修复方自述的 497 passed 已复现；覆盖率没有逐字复现。本轮全量为 91.51%，低于自述 91.54% 的 0.03 个百分点；portable 为 88.05%，高于自述 88.04% 的 0.01 个百分点。报告采用本轮实际覆盖行数和日志，不把差异当作测试失败，也没有为了对齐数字重跑整套检查。portable 是本机 macOS 源码隔离测试，没有运行 Linux CI。

两套检查的 warning 类别均已出现在 r3：多项式拟合的 RankWarning、未关闭测试数据库的 ResourceWarning、Sentry 参数的 DeprecationWarning。本轮没有新增 warning 类别；ResourceWarning 的具体触发位置会随垃圾回收时机变化，见两轮检查日志。

新增断言的故障注入只作用于独立测试进程内的函数。跳过 EXIF 转正时，方向测试在长边 512 的尺寸断言失败；把字号下限恢复为 8 时，字形测试报告右界 335 超过画布宽 192，后缀测试报告 thumb 像素相同。这 3 次退出码 1 是预期结果，不属于产品回归。首版注入包装错误隔离了字形观察器的全局变量，修正后重新核实了目标失败点；首版记录保留为 `harness-attempt1-*`，未用于关闭判定。

## 4. 新问题（R4-xx）

| 编号 | 严重度 | 问题与影响 | 证据 |
| --- | --- | --- | --- |
| 无 | 无 | 本轮定点复验和规定的快速回归未发现新增问题，未分配 R4 编号。 | [定点汇总](r4-evidence/focused-summary-r4.json)、[检查汇总](r4-evidence/quality-summary-r4.json)、[脚本退出码](r4-evidence/script-runs-r4.json)。 |

## 5. 复跑命令

持久证据保留了 r3 及相关 r2 脚本。旧脚本中的输出文件名仍带 r2/r3，所在目录为本轮 `r4-evidence`。适配内容见[harness-origins.json](r4-evidence/harness-origins.json)：临时根目录改为 r4，浏览器脚本增加实际进程和 user-data-dir 核对；acceptance.py 跳过超出本轮定点范围的实际 Finder 打开动作，其余 API 检查不变。R3 原脚本没有改写。

在不存在本轮临时目录的前提下准备脚本和环境：

```bash
STUDIO=/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio
REVIEW_TMP=/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-v2-r4
EVIDENCE="$STUDIO/../research/review_studio_v2/r4-evidence"
test ! -e "$REVIEW_TMP"
mkdir -p "$REVIEW_TMP/evidence"
cp "$EVIDENCE"/*.py "$EVIDENCE"/*.mjs "$REVIEW_TMP/evidence/"
export TMPDIR="$REVIEW_TMP" PYTHONDONTWRITEBYTECODE=1
export XDG_CACHE_HOME="$REVIEW_TMP/cache" UV_CACHE_DIR="$REVIEW_TMP/uv" UV_NO_SYNC=1
export RUFF_CACHE_DIR="$REVIEW_TMP/ruff" MYPY_CACHE_DIR="$REVIEW_TMP/mypy"
export PYLINTHOME="$REVIEW_TMP/cache/pylint"
cd "$STUDIO"

# 顺序运行 make check 和 portable_check.py，保留 85% 门槛。
# Scratch Makefile 副本只增加缓存参数。
.venv/bin/python -B "$REVIEW_TMP/evidence/run_required_r4.py"
.venv/bin/python -B "$REVIEW_TMP/evidence/run_script_r4.py" \
  baseline_fixture.py acceptance.py stamp_r3.py geometry_r2.py
.venv/bin/python -B "$REVIEW_TMP/evidence/test_sensitivity_r4.py"

# 留在本终端运行临时实例，不使用正式实例。
.venv/bin/python -B "$REVIEW_TMP/evidence/temp_server.py"
```

临时实例输出新端口后，在另一个终端设置同样的 STUDIO、REVIEW_TMP 和环境变量，顺序运行：

```bash
cd "$STUDIO"
.venv/bin/python -B "$REVIEW_TMP/evidence/run_script_r4.py" \
  regression_r2.py matrix_r3.py api_contract_r3.py stamp_http_r3.py \
  ui_acceptance.mjs ui_regression_r2.mjs ui_extra_r3.mjs \
  ui_orientation_r4.mjs orientation_api_r4.py
```

run_checks.py 执行 `make -f <Scratch>/Makefile.acceptance check`，其中明确使用 `lint-imports --cache-dir=<Scratch>/imports`、`pylint --persistent=n`，pytest basetemp、coverage、uv、ruff、mypy 缓存均放在本轮 Scratch。所有成组检查和脚本的外层超时均为 1800 秒，大于历史耗时的 3 倍；pytest 不开并行 worker，最多两组测试任务同时执行，HTTP 服务阶段的客户端脚本串行运行。结束时向本次 server-ready.json 记录的 PID 发送 SIGINT，确认退出后只删除本轮临时目录。

## 6. 边界与收尾

本轮与 r3 收尾相比只涉及 4 个后端文件和 2 个测试文件，见[变动清单](r4-evidence/changes-since-r3.json)。开验与收尾的 218 项产品文件 SHA-256 全部相同，两个 DAT 输入哈希和所用原验收脚本哈希不变；未改产品代码，未做 Git 写操作，未开子代理，未用 sleep 轮询。

测试没有读写真实图库，没有访问 127.0.0.1:49667 或实体存储卡。临时服务使用 127.0.0.1:49804，收尾主动发送 SIGINT 后已退出。四次前端测试均使用固定 Playwright 1.61.1、Chromium Headless Shell revision 1228，实际 user-data-dir 均位于本轮 Scratch；所有本轮 Chromium 进程已退出。见[完整性记录](r4-evidence/final-integrity-r4.json)、[界面浏览器记录](r4-evidence/ui-orientation-r4.json)和各 `browser-*.json`。

验收证据已保存到 `r4-evidence`，指定临时目录已删除，见[清理结果](r4-evidence/cleanup-r4.json)。持久证据的哈希清单见[EVIDENCE-SHA256.json](r4-evidence/EVIDENCE-SHA256.json)。
