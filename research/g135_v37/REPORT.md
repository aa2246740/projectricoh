可以交复审

gen 135（knobs v2 + H07 服务层归属修复 + v3.7 半按重新出现修复）的主机验收队列已全部跑完，没有产品断言失败。上一轮留下的 ownership_settings 50mm "复跑失败"已查明为测试侧问题，不是产品问题（见下）。尚未做的是完整 81 组回归，以及所有相机端行为。

## 身份

| 项目 | 值 |
| --- | --- |
| GXRCE.DAT | `57743bc105bc3d51b7fa65b44efd90afb022b2356d4e7846d470cc0c641c438a`，89,572 B，generation 135 |
| ilaunch3（v37 body） | `d00607405a5bd33290f99e9eda20df31a46386b6e0891cd5e62b15a9e3376283` |
| 冻结输入 | 57,183 项，开工与收尾两次核对均无变化 |
| 包 | 30 个文件，28 个固定文件与 gen 120b 及 package_v37_redisplay 相同；`verify_delivery.py` 重跑结果与 `evidence/delivery.json` 一致 |

## 尺寸

| 项 | gen 131 | gen 135 |
| --- | --- | --- |
| DAT | 89,556 B | 89,572 B |
| engine.bin | — | 60,652 B |
| 第七段 | 20,776 B | 20,776 B（逐字节相同） |
| BSS | 10,684 B | 10,684 B |
| 主请求 | 107,744 B | 107,760 B |
| 上限 / 余量 | 108,124 B / 380 B | 108,124 B / 364 B |

## 差异

相对 gen 131（完整补丁 `source-change-vs-g131.patch`，`evidence/codegen-four-categories.json`）：
- 五个源文件变化：`services.c`、`native_seed.c`（part 判断），`gate.c`、`eng_data.c`、`ui_v2_data.c`（只把 build 号 131 换成 135）。
- 构建侧：`common.py`（resident 指向 resident_v37，围栏路径）、`build131.py` → `build135.py`、`pack.py`（build 号）。
- 变化函数共 5 个：`ui_view`、`rv_view_owned`、`gxr2_tweak_layout`、`eng_data_accept`、`uv_validate`。
- 203 个编译函数中 200 个骨架与 gen 131 相同；`rv_view_owned`、`rv_call`、`rv_api` 各多 2 条指令（代码增长 +8 B）。
- 未变函数 18 个（settings、storage、make_plan、apply_impl、write_word、ig_menu、ig_apply、ig_event、ig_panel_open 等）正文逐字相同。
- 头部 43 字节不同（generation、resident id 等）。

相对 `engine_v52_redisplay`：`services.c` 与 `native_seed.c` 的 part 判断改动与 v52 相对其 gen 127 底座的改动逐行相同（`check_delta.py` 断言通过）。v52 的其余内容不在本版中；本版基底是 gen 131。

## 结果

| 项目 | 单元 | 结果 |
| --- | --- | --- |
| 半按修复（`accept.py`，v37 body） | 50mm / 28mm / mount | 均 ACCEPT_DONE：正常开 8 行；part 1 时原厂 7 行，重显后回到我们的 8 行、光标 4；强制 part 0/4 时 `jl_delta=1`；面板 8 行；写入全为 0 |
| H07 h07-parent | 三个 | 返回码 0；晚到 S store 0、晚到预览 0；首发 mode=1、WB=9/9、8 行 |
| H07 h07-parent-preview | 三个 | 同上，均为 0 |
| ownership_settings | 三个 | 本轮重跑均返回 0（50mm 另有一次诊断复跑也为 0），postcheck 0 |
| product-menus（新脚本 `product_menus.py`） | 三个 | 返回码 0，status PASS |
| ├ 视图 | | 每个单元记录 314 帧：全部 8 行，每行 ≤ 8 个字符；L1 逻辑行数 10；覆盖 7 种界面 |
| ├ 项目集 | | 03 为 [1,2,3,4,9]，04 不含 0 |
| ├ 端点 | | 4 个控件 × 2 端共 8 次：停住、向量不变、光标不动、行内显示 `!`、无 W 命令 |
| ├ Splt（04、06） | | 0→+1→0→−1→0：九行、C/D、T 全部与期望一致，相邻字节未变（共 39 个相邻检查）；另有 06 Amount 100→0→100 |
| target-math（目标 M32R 抽样） | 三个 | 返回码 0；抽样 1,133 / 1,134 / 1,163 项 |
| 主机金标准 | | 13,330 例（domain 2,504）经集成计算路径逐字节一致；`host-results.json` PASS |
| S 计划 | 三个 | 3,430 个菜单点与 gen 127 参考逐字节相同；24 个默认值、18 个 amount=0、66 个重置序列通过 |
| 旧 safety 套件（修正读取） | 50mm / 28mm / mount | 各 8/8 |
| 通信复核（`audit_records.py`） | 三个 | PASS，完整记录 48,890 条，prefix_writes 0；三个单元均 PASS |
| 编译码四类检查 | | PASS_STATIC，DAT 与 ELF 绑定（ELF `1ca0b9ab…`） |
| 布局 / 目标闸门 | | layout-only、target-gate 通过 |

旧 safety 的修正读取为：当前布局文件、当前 ready 偏移（g+4844）、r2 参考核心期望（`safety_cases_g135.py` 与 `r2_oracle.py`，基于 `g129_safety_triage` 的补丁）。三条旧失败（panel_rollback、ready_warm、write_latch）这次都通过。

## ownership_settings 50mm 复跑失败的原因

上一轮 queue2.log 里失败的那一行实际是 **product-menus-50mm**：它与 ownership_settings 共用同一脚本，所以结果文件和日志名都叫 `ownership_settings---unit-50mm`，覆盖了原来通过的记录。失败发生在我自己写的 postcheck `product_post.py`：它用 `capture_state.h01_restore` 手工拼出的原生状态来代替 ownership 场景之后的下一次原生开菜单，随后对第 4 行按 DISP，界面停在 L1（screen 0），没有进入 04。三次运行结果一致。

排查：
- 不做恢复（直接用 ownership 场景结束时的状态）也一样：此时原生是 7 行，视图不是我们的。
- 手工恢复后是 8 行，但 DISP 仍不打开。
- 用被保留模型自带的 `m.reopen`（g129/g131 的做法）得到同样的下一次原生开菜单后：mode=1、WB=9/9、8 行、匹配 04、pending 0，随后 DISP 立即进入 04（screen 1）。证据：`evidence/reopen-open-50mm.json`。
- 在正常首发打开的会话里，三个单元的完整菜单检查全部通过。

结论：手工拼的 H01 恢复状态与真实的下一次原生打开不等价，属测试侧问题，不是产品缺陷。已弃用 `product_post.py`，队列里的 product-menus 改用 `product_menus.py`（正常首发会话）。我没有再往下追手工状态里具体是哪个原生字段让 DISP 被消费；真实路径已证明正确，不影响结论。

## 本轮对工具的改动（都在围栏内）

- `run_existing.py`：`research/g135_v37` 下的脚本归入 review_g126 的结果目录（该目录的写围栏只覆盖它）。改动前后两批结果的 runner 哈希不同，`result-*.json` 里各自记录。
- 新增：`product_menus.py`、`safety_cases_g135.py`、`r2_oracle.py`、诊断脚本 `dbg_open.py`、`reopen_open.py`；`queue.json` 的 product-menus 三项改指 `product_menus.py`。
- `safety_cases_g135.py` 去掉了补丁里的 `triage_rpc_tail` 字段：它只是完整 RPC 记录的片段，通信复核器只接受完整记录。三个单元的 write_latch 已重跑（均 PASS），首次复核 FAIL 即由此字段引起，与产品无关。
- 删除了 `engine_v53_g135/candidate/__pycache__`（Python 3.14 的字节码缓存，会让 `check_delta` 的文件集断言失败，与产品无关）。
- 早先失败的 product-menus-50mm 三行仍留在 `local/checks/review_g126/runs.jsonl`，属作废记录；诊断文件移到 `local/debug/`。

## 范围与限制

写入围栏只允许 `firmware/engine_v53_g135`、`firmware/package_v37_g135`、`research/g135_v37`，拒绝网络。没有访问相机、存储卡或网络，没有启动子代理，同时最多 2 个模拟进程。理光字节只在被忽略的 `local/`。

- 静态已证：身份、源码差异、编译码、包与尺寸。
- 主机已证：上表各项（M32R 主机模型，图形和设备叶函数为模型）。
- 未知：相机端的调度、显示、拍摄、存储持久性和物理断电表现。
- 待定：完整 81 组回归未运行。

时间盒 2.5 小时已略有超出（最后的 write_latch 重跑与通信复核）。
