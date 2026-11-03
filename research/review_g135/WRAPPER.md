# 重绑与执行边界（review-g135-r1）

## 做法
- 运行器 `runner.py` 是 `research/g135_v37/run_existing.py`（g130_fix 版的 g135 改写）的复制品，只做名称或字段重绑：generation 的命名赋值、命名参数、`setup(generation=…)` 的参数默认值与选项集合、DAT 头的 `from_bytes` 字段比较。**不整体替换整数**。同一函数里与代号同值的 ASCII 上限 126 不被改写：所有重绑记录在 `local/checks/*/binding-*.json`，只出现在 `setup`、`run_cases.state`、`lock_nested.main`、`lock_exits.run`、`cold_reentry.case`、`build_package.main`，从未出现在 `ui_test_support.py`（两处 `32<=…<=126` 的所在文件）。
- 与实现者运行器相比，我做的改动（均写在 `runner.py`，实现者文件未动）：
  1. 输出根改为 `research/review_g135/local/checks/<家族>`；`g135_v37` 与 `legacy` 目录下的脚本归入 `review_g126` 家族（该家族的支持层写围栏只覆盖自己的结果目录）。
  2. 源代号按脚本目录取（review_g124 → 124、review_g126 → 126、review_g122 → 122、review_g123 → 123），不再一律 126。
  3. `algorithm_check.Algorithm` 换成冻结的 r2 C 源码参考（`r2_oracle.py`，与 g129 复审与 g135 实现者的同名文件逐字相同）；`ui_test_support.Session` 装上新 UI 读取器 `ui_adapter.py`（20 B 调节向量、八行文本字段、10 个 control、新项目集）。
  4. g122/g123 历史套件没有自己的 UI 支持层：像 g127/g129 复审那样改用 g126 支持层，`MATERIALS` 指向 `review_g126`；g122 的 `--reference-expectations` 把 `setup` 的代号强制为 135（旧套件自己要求它的 121 底座）。
  5. 旧 `setup` 里对旧 DAT 字节长度的断言（62,676 / 63,380）按“DAT 的 st_size 字段”改为 gen 135 的 89,572；这是 g129 复审没有处理、导致 history123 无法起跑的一处。
  6. 用户条目命令行 `user_entries.py` 不在 gen 135 源码树里：映射到本目录 `legacy/user_entries_g135.py`（只改了它加载的 `ui_data.py` 路径）。结果见 REVIEW.md（该工具读不了 gen ≥129 的 DAT）。
  7. 错误文件名带参数，避免并行同脚本互相覆盖（从 28mm 起生效）。
- `--crc-implementation host`：首次装载后装入经链式探针核对的主机 CRC 回调；`native`：全程执行目标 CRC 指令（H07 两组用 native，同实现者队列）。
- 旧脚本一律不改。需要改读取的只有两类：**基于复制品的修正读取**（`legacy/ui_acceptance_g135.py`，见 PORT_NOTES.md）和实现者已有的 `safety_cases_g135.py`（按 g129 triage 补丁；本复审另用它跑三个单元，并保留“原读取”的对照）。
- 一处读取旧布局的来源：`research/review_g12x/local/layout/*.json` 是旧版源码目录里的陈旧布局文件，`MATERIALS` 指向它们（`safety_cases.py`、`run_cases.py`）。原读取的 safety 因此读到 gen 124/126 的偏移（`ready` 2523 对 4844 等 21 个字段），这就是 triage 的 (b) 类。其余套件读 `OUT/local/layout/…`，由运行器指向本次重新编译的当前布局（`local/checks/review_g126/local/layout`，与实现者的 layout.json 逐字节相同，独立编译所得）。

## 执行边界
- 一个调度器：`schedule.py`（第 1 段，13 组）→ `schedule_v2.py`（第 2 段）→ `schedule_v3.py`（第 3 段，按 `priority.json` 重排）。三段之间旧调度器先暂停、再终止，正在跑的作业被下一段按进程号接管；每段同一时刻只有一个调度器。每组超时 4200 s，最多 3 个模拟进程。
- 例外（如实记录）：两次短暂超过 3 个进程：(a) 调度器 2 个 + 手动冒烟 history123 一次叠加 history122 一次（<2 分钟）；(b) boundary_sweep（clang 编译 + 约 1 分钟计算）运行期间调度器已有 3 个。均已停止，未再发生。
- OS 围栏 `write-fence.sb`：只允许写 `research/review_g135` 和 `research/g135_v37/local`（例外，**未使用**；所有输出都在 review_g135/local），拒绝网络。没有访问相机、存储卡、网络，没有启动子代理。
- 终止的作业：`product-menus-mount`（SIGTERM，为给回归组让出进程槽；实现者该单元结果 PASS 保留，见 cancelled.jsonl）。
