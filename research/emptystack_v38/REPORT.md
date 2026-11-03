可以交复审

# v3.8 / gen 137 验收报告（emptystack-wrap-v38-r3）

本轮接手前两轮（因模型或 provider 故障中断）的验收，跑完了剩余队列。对象：机身 v3.8（`ilaunch3`）+ DAT gen 137（`GXRCE.DAT`）。全部是电脑端（主机模型）验收，**没有任何相机实测**；没有碰相机、存储卡和网络，没有 git 写操作。

## 1. 身份核对（与任务描述一致）

| 项 | 值 |
| --- | --- |
| ilaunch3 | `d4fa3b46da137b8b7c7c703e66750a8249c0715271290c0fdb490a2f7a239a90`，校验和 6a7d99ef |
| GXRCE.DAT | `78dcbb9a2735cd84e55385683ce0296b97818ddf90f8b492d9003512dbeff3f8`，89,936 B |
| 常驻体（resident） | 7,908 B，余量 176 B；build id `79d8e2a2…` |
| 源码 | `firmware/resident_v38`、`firmware/engine_v54_g137`；输入指纹在每个任务开始和结束时各核对一次（`fences.check_inputs()`），全程一致 |
| 包 | `firmware/package_v38_g137/local/SD_ROOT`（30 个文件，28 个与固定基线逐字节相同，2 个为本版改动） |

## 2. 两项改动

### 2.1 空栈修复

源码差异见 `source-diff.txt`（`firmware/resident_v37 → resident_v38` 与 `engine_v53_g135 → engine_v54_g137`）。要点：

- **机身 `owned()`**（`resident/hooks.c`）：
  - 前：`count<1||count>2` 直接拒绝。
  - 后：`count>2` 才拒绝；`hook<=2`（H01/H02）且 `count==0` 时，只有 `RV_BYTE(0x2022f5ac)==8`（原生列表已是我们的 8 行）才接受；`hook>2` 且 `count==0` 一律拒绝。其余检查（魔数、版本、状态、忙标志、名称表、`205d9bf8`、`205d9c00`、tag 33、状态指针）全部保留。
  - 与任务描述相比多出一个条件：`0x2022f5ac==8`。更保守，不是缺陷。
- **机身 `rv_ui_capture(r, constructing)`**（`resident/shared.c`）：空栈只在 `constructing==1` 时通过，只有 `UI_LIST` op 1 传 1，其余调用点传 0。
- **DAT 服务层**（`engine_services/native_seed.c` 的归属判断、`engine_services/services.c` 的 op 1 首发）：构造阶段接受 `count==0`；首发时空栈还要满足 `input_fields==1 && input_sequence==entry_serial`；原生列表必须是库存名称表（`0x2022d610`）与 7 行（已有我们的列表时则必须是 8 行）。非 op 1 不接受空栈。
- 另有 `build_number 135→137` 三处（`gate.c`、`eng_data.c`、`ui_v2_data.c`）。

**真机证据对照**（`captures/diag-v37-field-20261030/READINGS.txt`）：拍后第一次打开时 count 0、tag FF、part 1、state 0x205A279C、库存名称表 + 7 行。empty_check 的进入形态与之一致（count 0、tag 255、state `0x205a279c`、part 1、names `0x2022d610`、rows 7、`ui_restore0`=0）。

**验收结果（电脑端）**

| 检查 | 50mm | 28mm | mount |
| --- | --- | --- | --- |
| artifact-final（静态，包/ELF/改动范围，与单元无关） | PASS | PASS | PASS |
| host-final（golden 13,330、domain 2,504、集成点 3,430，每单元 1,133/1,134/1,163） | PASS | PASS | PASS |
| empty-full：按现场形态进入后显示我们的 8 行，getter 0，光标 4；6 个负例（part0、part4、activity、native_state、names、rows）全部被拒绝 | PASS | PASS | PASS |
| part1（半按回到 part 1 的接受路径；写入 0） | ACCEPT_DONE | ACCEPT_DONE | ACCEPT_DONE |
| h07-parent：晚到的 S 写入 0、晚到的预览 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| h07-parent-preview：晚到的 S 写入 0、晚到的预览 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| safety（修正读取）8/8 | PASS | PASS | PASS |
| target-math（本机 M32R 解释执行，cases / 最大栈） | 1133 / 376 B | 1134 / 376 B | 1163 / 376 B |
| ownership 状态捕获（供 target-math 与通信复核） | PASS | PASS | PASS |

其余整体检查：layout PASS（28 字段）、code-check PASS_STATIC（公共函数 202、骨架相同 194）、word-policy PASS（名称 2,178、文本 1,142、违规 0）、target-gate PASS（6 例，晚到写入 0、晚到预览 0，首次 H01 为 mode 1、wb [9,9]、8 行）、通信复核 PASS（见 §5）。

safety 三条旧失败（panel_rollback、ready_warm、write_latch）按 `research/g129_safety_triage/REPORT.md` 的结论处理：用当前布局读取。具体做法见 §4.3。

### 2.2 列表循环

按 `research/ui_v2_design/DESIGN_r2_list.md` 方案 D：除数值页外全部循环；填充行第一条显示 `--------`，其余留空。

- `engine_v54_g137/.../adapter.c`：`uv_move` 的夹紧改成取模（`target=(target+count+delta)%count`），非相邻跳变 `delta=0`；填充行：`logical==count` 时写 `--------`。
- `engine_v54_g137/.../kv2/kv_ui.c`：`kv_ui_move` 对非数值页取模；数值页仍夹紧；`logical_text` 之后的第一条填充行写 `--------`。
- `uv_window` 不改。

**验收结果（电脑端）**

| 检查 | 结果 |
| --- | --- |
| list-final：窗口 144,177、移动 56,756、帧 4,054、填充 226、端点 2,814、适配层移动 1,153,416 | PASS |
| product-menus 旧套件（整条旧检查：首发、归属、9 行读取、拆分/Amt/端点序列、屏幕 0–6 全覆盖）50mm | PASS（`local/checks/review_g126/product-50mm.json`：314 帧、端点 8、邻接 39；28mm、mount 为 316 帧、端点 8、邻接 39）|
| product-menus 旧套件 + 新循环帧检查 28mm | PASS（单次完整运行，3,197 s）|
| product-menus 新循环帧检查 50mm | PASS（frames-only 单次运行，843 s；与上面的完整旧套件互补，见 §3）|
| product-menus mount | PASS（旧套件 + 新循环帧检查的单次完整运行，2,862 s；旧套件 316 帧、端点 8、邻接 39；循环帧 19 帧） |

新循环帧检查（`menu_frames.py`，证据 `menu-frames-<单元>.json`，共 19 帧）实际观察到的行为，50mm：
- L1（10 行）：首行向上 → 光标到末行 `MyRec`（窗口 top 2），预览配方不变（向量不变、slot 1）；末行向下 → 回首行，且预览首行配方。
- 配方卡 03（5 行）：首行向上 → 行 4，向下 → 行 0；第 6 行显示 `--------`，之后两行为空。
- 逐项列表 03（6 行）：同样循环；第 7 行 `--------`，之后一行空。
- 数值页 Cont（19 档）：+9 向上仍停在 +9，−9 向下仍停在 −9（不循环，`!` 保留）。
- 分组（9 行）：首行向上 → 末行 `LVI`（top 1）；向下回首行。
- 条目（空组，2 行）：循环；第 3 行 `--------`，其余空。
- 配方卡 Default 行按下后（`armed=1`），再移动会取消并回首行（`armed=0`）。

## 3. product_menus 失败的查明（任务第 2 项）

**结论：测试侧问题，不是产品缺陷。** 逐层查明：

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| 10:36 的运行：`KeyError: 'data.map'`（`product_checks.py` 的 `neighbors`），observations 0 | 推断为当时 wrapper 里核心布局夹具与当前布局的合并不全（该次运行的 wrapper 版本已无法还原）。现版 `run_existing.py` 已是 `dict(retained, **current)` 并带一致性断言（共有字段必须相等），本轮复跑越过该点 | 无需再改；本轮确认旧套件完整通过 |
| 本轮首次复跑（旧套件全部通过后，我们追加的帧检查报 `AssertionError`，且 `ValueError: dictionary update sequence…`） | 追加的帧检查（`menu_frames.py`）有两处测试侧错误：① 旧序列最后故意置了"通信失败"锁存（屏幕 6），我们没有清除就开始检查屏幕 0；② `published()` 返回的是行列表，却被当成字典转换 | 在 wrapper 里清除锁存（只清 `failed` 字节），帧记录改取旧套件自己记录的帧；加了带上下文的断言信息 |
| 同一轮：safety 读不到适配层布局 | 旧 safety 读 `current-adapter-layout.json`（绝对偏移，36 项），当前构建只有相对偏移 `adapter-layout.json`（28 项） | wrapper 增加映射，并在启动时断言夹具的 `bytes`、`ui` 与重新编译得到的布局一致，且 `ui.*` 偏移 = 相对偏移 + `ui` |
| 原 `queue-final.json` 的 target-math 条目 | 参数写成 `target 0`，而 `target_check.py` 需要 `--state <目录> --unit N`，立即退出码 2 | 新增 `queue-r3-extra.json`（ownership 捕获 ×3 + target-math ×3 + 帧检查），原条目的失败记录移入 `local/r3-state/superseded/` |
| 原 `queue-final.json` 的 communications 条目 | `audit_communications.py` 的模块级 `DAT` 仍指向 g135 包，找不到 gen 137 的记录组，断言失败；另外队列里没有产生通信记录的 ownership 捕获步骤 | `run_stage.py` 的模块级路径映射补上 `package_v37_g135 → package_v38_g137`；补跑 ownership 捕获生成 `complete-rpc-<单元>.json` |

**期望值的改动前后对比**

| 项 | 旧套件（改前） | 本轮（改后） |
| --- | --- | --- |
| 首发（首次发布 8 行、`adapter_published_rows`、`published_rows`） | 断言 | **不变** |
| 归属（`neighbors()` 邻接字节在每次设值前后不变；`nine_rows`；`check_state`） | 断言 | **不变** |
| 端点（数值页上下限：向量不变、光标不变、`!` 在光标行、无 W 写入 RPC） | 断言 | **不变**（数值页不循环，与新规则一致） |
| 屏幕 0–6 全覆盖、`controls(3)==[1,2,3,4,9]`、`0 not in controls(4)` | 断言 | **不变** |
| 列表首尾行为 | 无专门断言（`select()` 只做 ±1 单步移动，不触碰首尾） | **新增**：L1/配方卡/逐项/分组/条目首尾循环；填充行 `--------` 与其后空行；数值页不循环；L1 回绕时预览规则 |
| 旧套件任何已有断言 | — | 没有删除，没有降级，没有放宽 |

首发、归属、端点这类检查全部保留且通过。

## 4. 测试方法说明

### 4.1 运行方式

所有任务经 `r3_job.py` 单任务运行（同时最多 2 个进程），状态记录在 `local/r3-state/<任务>.json`，日志 `local/r3-<任务>.log`。每个任务前后都核对包与输入指纹。临时文件在 `/Volumes/Workspace/Scratch/tmp/projectricoh/v38-r3/`（结束时删除）。

### 4.2 product-menus 的拆分

单次完整运行（旧套件 + 帧检查）约 53 分钟/单元。50mm：首轮完整旧套件已全部通过（evidence `product-50mm.json`），随后帧检查发现上述测试侧错误，修好后用 frames-only 模式（`GXR_FRAMES_ONLY=1`，只做首次发布 + 帧检查，14 分钟）单独验证 50mm，没有再重跑 53 分钟的完整套件。28mm、mount 是修好后的单次完整运行。

### 4.3 safety

按 `research/g129_safety_triage/REPORT.md`：当前布局、当前 ready 偏移、r2 参考核心期望。`safety_cases_g135.py` 已含这些读取方式；本轮补上适配层布局映射后三个单元各 8/8（h01_switch_activity、h01_switch_state、list_rollback、panel_rollback、ready_warm、settings_recheck、write_latch、storage）。

## 5. 通信复核

`audit_records.py`（经 `audit_communications.py`）：1 组（gen 137 的 DAT）、30 个文件、48,890 条完整记录，缺失 0，三个单元各 PASS，失败 0（`evidence/rpc-summary.json`、`evidence/rpc-78dcbb9a2735.json`）。这是所有 product-menus 完成之后的最终复跑；之前在 menus 28mm/mount 未完成时跑过一次（28 个文件、21,395 条），同为 PASS，已被覆盖。

## 6. 已知局限

- 全是主机模型：M32R 解释执行 + 图形/设备叶子是模型。**相机实测一项都没有**。
- 空栈修复依赖拍后首开的现场形态与 `READINGS.txt` 一致（count 0、tag FF、part 1、库存名称表 7 行、`input_fields==1`、`input_sequence==entry_serial`）。后两个上下文条件来自模型，没有现场读数；若相机上这两个条件不成立，首发会被拒，退回库存列表（安全方向，无写入）。
- `adapter.c` 的 `uv_tags[4]`/`uv_letters[4]` 越界读风险（DESIGN_r2_list.md §1.2 第 4 点）本轮没有处理，也没有改产品源码。
- 适配层布局里 8 个非 `ui.*` 额外字段（retry、comm_failed、panel.* 等）取自 g135 夹具，struct 大小（3,920 B）和重新编译得到的 28 个字段全部一致，但这 8 个字段没有逐个重新编译验证。
- 旧脚本运行器会把 `TMPDIR` 改写到 `research/emptystack_v38/local/tmp`（仓库内），结束时已清空。
- 没有跑完整 81 组回归（任务没有要求）。

## 7. 刷机步骤与恢复

**刷机（用户操作，需先得到用户明确同意）**：
1. 把 `firmware/package_v38_g137/local/SD_ROOT` 的内容写到一张测试卡根目录（卡 B）。写完核对 `ilaunch3` 与 `GXRCE.DAT` 的 SHA256 与 §1 一致，卸载卡（不要弹出）。
2. **装上 50mm 镜头**（镜头规则已证实），装卡，开机时按住"+"和回放键，等刷写完成。
3. 版本号仍显示 1.51，属正常。
4. 刷完后按现场顺序验证：打开配方菜单 → OK 关闭 → 拍一张 → 再次打开，应看到我们的 8 行而不是库存列表；然后在 L1、配方卡、分组里按上/下检查首尾循环和 `--------`；数值页首尾不循环。

**恢复**：用卡 A（Stage2l-50mm 恢复卡），仍装 50mm，开机时按住"+"和回放键。

## 8. 文件

- 源码差异：`source-diff.txt`、`source-files.json`
- 本轮新增/修改的测试侧文件：`r3_job.py`、`queue-r3-extra.json`、`menu_frames.py`、`run_existing.py`、`run_stage.py`、`menus_debug_r3.py`（诊断用，已无用途）
- 结果：`local/r3-state/*.json`（`superseded/` 为作废的失败记录）、`menu-frames-<单元>.json`、`evidence/`、`local/checks/`
- 校验：`SHA256SUMS`（以仓库根为基准）
