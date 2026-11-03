修改后再合并

有 3 项 P1。公开数据项来自基线；两项 UI 问题是本轮尚未覆盖完整的缓存生命周期。不能据此把整个改动描述为 3 个新增回归，但它们都不满足本次给定的公开推送或状态验收门槛。

审查对象为 Studio HEAD `e73a7af474e137b26862f252da0a8ad58b5d3793` 上的 16 个已修改文件、4 个新文件。269 个源码文件及 757 个 Git 元数据文件的前后摘要完全相同。源码集合 SHA-256 为 `1b95dabf06b43b87a6b6bd281c7341289f342d6148a657ec6303cb81f068f741`。分支仍为 `main`，没有 Git 写入。

| P1/P2/P3 | 证据 | 最小修正 |
|---|---|---|
| P1-01：公开树和分发包仍保存完整 kv2 点表。基线已有。 | `src/gxr_studio/engine/data/final.json:220` 起保存 201 项控制的 3,430 个 `(level, dose)` 点，并非只有名称、档位或摘要。独立读取 150 的 R2 及 152、153 的 R3 后，所有点逐项相同。wheel 和 sdist 都原样收录该文件。见 [table-inventory-result.json](table-inventory-result.json) 和 [package-receipts.json](package-receipts.json)。因此，即使扫描器通过，仍违反本轮明确禁止公开 kv2 点表的要求。 | 从公开源码、wheel、sdist 移出完整剂量点表；从用户 DAT 读取并保存在仓库外的应用数据目录。升级时迁移既有本机表，保留旧规范化数据的兼容路径。未导入时的菜单只保存名称和档位元数据。给公开数据检查补上这种 JSON 表的检查，避免只检查二进制标识。 |
| P1-02：导入后，旧照片及尚未返回的能力请求仍可保留“不可用”。 | `web/assets/caps.js:43` 只按照片缓存；`web/assets/preview.js:173` 只刷新当前照片。复现：先浏览 RAW 照片 A、B，导入校准使当前 B 就绪，再返回 A。全局 `ready=true`，A 的 21 个配方按钮仍全部禁用，没有原因或导入入口；A 的能力接口只请求过 1 次。另将能力请求延迟至数据更新后返回，调用者仍收到 `recipe=none`，应为 `full`。见 [ui-review.json](ui-review.json) 的 `previous-photo-after-import`、`data-change-pending-caps` 和 [截图](previous-photo-after-import.png)。 | 能力缓存绑定 `data_version`；数据更新时清掉旧能力缓存；旧请求返回时若版本已变，重新读取当前版本，不能把旧结果交给仍在等待的视图。保留拍摄信息缓存即可。 |
| P1-03：数据更新不能阻止旧菜单返回给等待者。 | `web/assets/camdata.js:35` 只清空 `state.catalog`；`web/assets/preview.js:45` 只有显式 `refresh` 才清空在途 Promise 并增加版本。复现：旧菜单请求尚未返回时更新相机数据，随后释放旧响应。原调用者结束后，菜单仍为 0 个 Looks，应为 10 个。正在首次加载编辑状态、尚无 `view.ed` 时，当前 Viewer 刷新也不会替它再读菜单。见 [ui-review.json](ui-review.json) 的 `data-change-pending-catalog`，以及 `web/assets/viewer.js:357`。 | 数据更新时同时清空菜单、在途 Promise，并增加菜单版本。旧响应发现版本过期后，应让原调用者等待当前菜单，而不只是禁止写缓存。 |

两个 UI 问题的建议修正保存在 [minimal-cache-fix.diff](minimal-cache-fix.diff)。只在 Scratch 的两个 JS 副本中应用，原 Studio 未改；同组 21 项组件检查由 18 通过、3 失败变为 21 通过。三个失败用例分别对应 P1-02 的两条路径、P1-03 的一条路径，见 [ui-review-fixed-scratch.json](ui-review-fixed-scratch.json)。这份副本验证不代表产品已经修好。

公开数据检查中，已完整阅读 `tests/support/g152_reference.c`、`tests/g152_support.py`、`src/gxr_studio/camdata/knob_table.py` 和 `datcodec.py` 新常量。这些新增代码没有保存固件、552 B 行、stock 行、DAT 内容或第三方 LUT 数据；新增常量是布局、尺寸和 SHA-256。测试从 Studio 仓库外的 `firmware/` 读取本机文件。问题在既有 `final.json`，其 SHA-256 为 `2d2793784b7cd99e6db9cd43351180017d15a493562a928c34e6a2d338e787f2`。

复跑时间均为 2026-11-01 UTC。完整命令、超时、退出码、耗时及日志摘要在同名 JSON 回执中。

| 开始时间 / 耗时 | 检查 | 结果 |
|---|---|---|
| 18:37:11 / 715.347 秒 | `make check`，仅将 import-linter 缓存位置改到 Scratch；强制零重跑。 | 1,212 项通过，其中新模块 263 项；失败、错误、跳过、重跑均为 0，覆盖率 92.63%，3 条警告。包含 `private_bytes.py --tracked --dist`，输出 `private bytes: checked 272 files`。见 [make-check.log](make-check.log)、[pytest-check.xml](pytest-check.xml)、[checks.json](checks.json)。扫描器通过没有消除 P1-01。 |
| 18:45:56 / 4.009 秒 | 临时复制源码和测试，确认副本上一级没有 `firmware/`，运行整个新测试模块。 | 8 项通过、255 项正常跳过，退出 0。包代码也确认从副本加载。见 [portable-result.json](portable-result.json)、[pytest-portable.xml](pytest-portable.xml)。 |
| 18:48:33 / 3.849 秒 | 独立脚本编译原相机 C 参考，比较 Tri-X 400、instax mini。 | 152/153 发布及测试四份 DAT × 2 Looks × 3 单元 × 默认及两组多控制组合，共 72 次完整 552 B 相同。150 个 DAT/C/H 输入摘要前后未变。见 [independent-equality.json](independent-equality.json)。 |
| 18:47:51 / 1.348 秒 | 从 HEAD 加载旧解析器和旧 `CameraData`，与工作树比较 127、129、131、135、137、138。 | 六份文件往返、所有模块字段、48 槽位条目、内置菜单相同；默认及各控制两端共 2,556 次完整行比较相同。见 [old-generations.json](old-generations.json)。 |
| 18:53:28 / 3.787 秒 | 解析边界及真实 ASGI API。 | 六包的 130 个错误样本全部拒绝，覆盖未知代数、截断、CRC、超大文件、GXFX 容量/掩码/索引/边界及 R3 指针改动。66 次失败导入均为 422，旧应用数据文件集合及字节摘要不变。真实多卡 API 先拒绝第一张、再接受第二张，假卡文件摘要未变。见 [parsing-api.json](parsing-api.json)。 |
| 18:57:07 / 1.132 秒 | 固定 Playwright 1.61.1、Chromium 1228，加载真实产品 ES 模块及隔离接口响应。 | 五种状态、顺序、Look/用户选择、各自档位记忆、失效条目重新选择、导入刷新及多卡选择正例通过；21 项中有上述 3 个失败用例，页面异常 0。见 [ui-final-run.log](ui-final-run.log)、[ui-review.json](ui-review.json)。 |
| 18:57:25 / 0.959 秒 | 仅替换 Scratch 中的两个缓存模块，复跑同组检查。 | 21 项通过。见 [ui-fixed-strengthened-run.json](ui-fixed-strengthened-run.json)。 |

边界检查没有发现文件数据驱动的无界循环。GXFX 条目最多 48 个，每类效果行最多 127 个；主行池有固定上限。`knob_table.read` 的调用发生在 R2/R3 整块摘要校验之后。另运行 600 个重算外层 CRC 的单字节变体：178 个被拒绝，421 个引擎区改动及 1 个仍合法的范围元数据改动可往返；接受项的配方行、Looks 和点表均未改变，没有未处理异常。这不是“600 个损坏文件全部拒绝”的证据。

新测试的关键证据是原相机解析器、点表请求和整数核心产生的完整 552 B；它们不以 Studio 自己算出的 SHA 作为唯一预期。完整检查覆盖 120 组 Look 默认行及 60 组逐控制档位测试；本次独立补查另用了多控制组合。

旧代数的内置行计算未变，但不能说所有行为都不变：带 DAT 模板的数据现在可列出文件内用户配方，菜单响应增加 `looks`、`users`；129–138 的表指纹改为实际 DAT 块摘要，所以 `engine_pin` 会变化；状态提示和不支持代数响应也有意改变。旧规范化数据缺少 DAT 模板时的兼容路径仍在。

文案未另列 P2/P3。主界面的文件名、Look 名称和 `Looks` 分组沿用本次需求。`kv2 点表`、`效果行索引越界` 等技术用语属于 API 的 `detail`；当前导入控件只显示中文主句，并未把这些内容显示成主界面原因。编辑请求里的类型/条目标识诊断经通用错误组件显示时位于收起的“详细信息”。按要求没有评议已经计划修改的代数提示句。

初轮有两次 `make check` 因我隔离后的构建缓存缺少 hatchling/tomlkit 而在 pytest 前中止，补齐已有离线缓存后才进入上述完整检查。辅助脚本初轮的计数、夹具复用和 DOM 清理问题也保留了日志；最终结果以上表回执为准，没有把这些夹具问题列为产品缺陷。

未检查的范围：没有启动完整 HTTP 服务与完整 Viewer 联测；API 使用 ASGI TestClient，浏览器使用真实组件及隔离响应。没有重新证明相机 ISP 的照片结果、实体相机行为、上卡或刷机，也没有扫描全部 Git 历史。没有访问公开 GitHub、提交、合并或推送。

没有启动应用默认目录或访问主人的 `127.0.0.1:49667`、默认图库、默认导出目录、默认应用数据目录，没有访问 `/Volumes/RICOHDCX` 或其他真实卡。首次操作先运行了 `df -h`，并核对 Workspace 的 APFS、可写状态及指定 UUID。TMPDIR、pytest basetemp、浏览器配置和全部私有中间数据均位于指定 Scratch。2026-11-01 19:02:23 UTC 清理完成，Scratch 不存在，无任务残留进程，未发现本轮 `code_sign_clone` 或浏览器配置残留。见 [cleanup.json](cleanup.json)。验证与清理用时约 32 分钟。

复跑入口为 [run_review.py](run_review.py)、[verify_review.py](verify_review.py)、[verify_ui_review.mjs](verify_ui_review.mjs)。它们只向本审查目录和指定 Scratch 写入；原相机数据和参考源码始终在 Studio 仓库外读取。
