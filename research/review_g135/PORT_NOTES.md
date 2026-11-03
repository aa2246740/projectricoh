# 旧套件的“修正读取”：修正前后与依据

原则：旧脚本文件不改（`research/review_g12x/*`、`research/review_g127/*` 保持原样）。需要改读取时，只在 `research/review_g135/legacy/` 放**复制品**，复制品里每个按键、归属、锁定、RPC、邻字节、写入计数断言都保留，只改“读的是旧布局、旧偏移、旧显示文字、旧数学期望”的地方；每处改动都在下表列出前后值和依据。

## 1. safety_cases（g124 / g126，三单元）——用实现者已有的修正读取
文件：`research/g135_v37/safety_cases_g135.py`（基于 `research/g129_safety_triage` 的补丁，我未改动，对照 `research/review_g126/safety_cases.py` 的 diff 核对过）。

| 用例 | 原读取 | 修正读取 | 依据（本复审核对） |
| --- | --- | --- | --- |
| ready_warm | 固定读 `g+2523`，得 3（用例要求 1） | 读 `layout.json` 的 `ready` = 4844，得 1 | 当前布局 `ready` 2523→4844（本复审独立重编的 layout.json 与实现者逐字节相同） |
| write_latch | `MATERIALS/local/layout/*.json`，即源码目录里陈旧的 gen 124 / 126 布局：`uncertain` 2527、`write_started` 2538 等 21 个字段全部偏移 | 读 `OUT/local/layout/*.json`（当前构建） | 21 个核心字段与 34 个适配层字段的偏移全部变化（逐项对比在 `layout-diff.json`；adapter-layout.json 里 ui.* 为相对 ui 基址的偏移，换算后与重编的 current-adapter-layout.json 一致） |
| panel_rollback | 期望由旧调节数学算出（`ux.expected_entry`） | 期望由冻结 r2 C 源码的参考核心算出 | Cont=0 时新旧逐字节相同；Cont=−1 时旧期望与新核心在两条曲线行上不同（triage 已量化），其余七行相同 |

结果：原读取三单元各 5/8（同样三条）；修正读取三单元各 8/8，各跑两遍（第一遍运行器元数据写入被围栏拒绝，案例结果有效；第二遍 `-r2` 返回码 0）。

## 2. ui_acceptance（transitions、values）——复制品 `legacy/ui_acceptance_g135.py`
旧套件按旧显示设计硬编码：卡片页四行（`C 0 H 0 `、`S 0 V 0 `、`Default`），项目页三到四项，数值页 ±5（11 个点，零在第 5 位）。新设计（knobs v2）：卡片页 `C/H`、`S/F`、`V/W`、`T/P`（按配方）加 `Amt` 和 `Default`，项目页最多八项，数值页每个 control 一张点表（Cont/High/Shad/Satu 为 −9…+9，共 19 点，零在第 9 位）。依据：`EXPECTATIONS.md`（g129 复审）、`probe_ui.json`（本复审在实际 DAT 上读出的新显示）。

| 位置（旧脚本行） | 修正前 | 修正后 |
| --- | --- | --- |
| transitions：卡片页标签 (66) | `['<5 F-CC','C 0 H 0 ','S 0 V 0 ','Default',' ',' ',' ',' ']` | `['<5 F-CC','C 0 H 0','S 0 F 0!','V 0 W 0','T 0 P 0','Amt 100%','Default',' ']` |
| transitions：项目页标签 (69) | `['<5 F-CC','Cont   0','High   0','Shad   0','Satu   0',' ',' ',' ']` | `['<5 F-CC','Cont   0','High   0','Shad   0','Fade!  0','Satu   0','Warm   0','Tint   0']` |
| transitions：项目页 DISP 后光标 (70) | `(3,5)` | `(3,9)`（零在 19 点表的第 9 位） |
| transitions：数值页高亮行 (72) | `labels[5]=='Cont   0'` | `labels[physical]=='Cont   0'` |
| transitions：数值页 UP/DOWN 光标 (73) | `(3,4)` / `(3,6)` | `(3,8)` / `(3,10)` |
| values：起点 (106) | `cur==5` 且 `levels==[0]*11` | `cur==9` 且 `levels==[100]+[0]*9` |
| values：步进 (107–115) | 值 1…5、再 4…−5，`cur==5−value`，上限标签 `! +5`/`! -5`，低端 `cur==10` | 值 1…9、再 8…−9，`cur==9−value`，`! +9`/`! -9`，低端 `cur==18`；`levels[控制 id]=value`，控制 id (1,2,3,5) |
| values：返回项目页 (118) | 光标 `1+param` | 光标 (1,2,3,5)[param]（项目页里 Fade 占第 4 行） |
| values：Default (146–152) | `goto(1,3)`；`levels==[1]+[0]*10`；`labels[3]=='Sure?'` | `goto(1,6)`；`levels==[100,1,0,…]`；`labels[6]=='Sure?'`；回到 `[100]+[0]*9` |
| scroll：`match(8,[0]*11)` (131) | 11 字节旧向量 | `[100]+[0]*9` |

保持不变：每个视图每个键 (UP/DOWN/DISP/OK/ADJ/HALF) 的 (screen,cur) 期望、OK/ADJ/HALF 之后的 overlay=0 与行数 7、重开后 slot/levels 相同、ERR 页在失败后无 RPC 且 S 字节不变、`!`/clamp 行为、`match()` 对全部 552 B 的逐字节比较（参考核心换成冻结的 r2）。

### values 的运行结果
50mm：四个 control 的 ±9 步进与 clamp 各 27 步（每步对全部 552 B 与冻结 r2 核心逐字节比较）PASS；L1 虚拟滚动 PASS；Default 双击（Sure? 武装 / 解除 / 复位到 `[100]+[0]*9`）PASS；`back-from-second-pair` 的 `(1,1)` 期望不成立：从项目页返回卡片页时光标回到刚用过的那一对（`(1,2)`，见 `probe-back.json`），这是导航记忆的设计变化，该用例只断言屏幕与光标，不含归属 / RPC / 写入内容，记为设计变化而不是通过。28mm：四个 control 的步进 4/4 PASS，随后我为了让出进程槽终止了该运行（其余三个快速用例未跑，见 cancelled.jsonl）。

## 3. native_checks（preview-window / preview-deferred / pending-read）——复制品 `legacy/native_checks_g135.py`
旧脚本把预览切点写死在 gen 127 镜像偏移：`0xa354`（最终归属核对的 `bl rv_settings_owned`）和 `0xa35c`（`bl rv_native_preview` 之前的 `ldi r0,#0`）。gen 135 镜像里这两处早已不是这两条指令（原脚本 `switched=false`，三组按原样跑只是空转失败）。

| 用例 | 修正前（gen 127 偏移） | 修正后（gen 135 镜像） | 依据 |
| --- | --- | --- | --- |
| preview-window | `0xa35c` | `0xd228`，并断言该处字节为 `60 00 f0 00` (`ldi r0,#0`) | `objdump`：`d224 bl rv_irq_restore; d228 ldi r0,#0; d22c bl rv_native_preview` |
| preview-deferred、pending-read | `0xa354`（核对本身，IRQ 开） | `0xd200`，并断言 `fe 00 04 cd` (`bl rv_irq_save`) | gen 135 的最终核对在 `rv_irq_save`(d200) … `rv_irq_restore`(d224) 之间，IRQ 关；“核对之前、IRQ 开”的位置是 d200 |

同时运行器把 `native_checks_g135.py` 也按 `native_checks` 处理（核心字段 `busy/uncertain/pending` 的偏移重绑）；第一次修正只改了切点，没有改运行器，读出的 `busy 15 / uncertain 30 / pending 191` 是读错偏移的垃圾值，已作废（见 `native-*-28mm-port` 记录）。有效记录是 `-port2`。

## 4. 未修正读取、按设计变化归类的套件
- `label_acceptance`：断言旧 03 号配方三行布局 (`C 0 H 0 `/`S 0 `/`Default`)，且“填充行不可选”用 Shad 之后的 DOWN 来验证。新设计里 03 有 Cont/High/Shad/Fade/Filt 五项，Shad 后面是 Fade。意图（黑白配方不显示饱和度、填充行不可选）需要重新设计用例，不是改几个常量。**未修正**；已用 `product_menus.py` 的 314/316 帧（全部 8 行、≤8 字符、03 的项目集 [1,2,3,4,9]）和 `boundary_sweep.py`（03 的 Satu 被拒）代替。
- `project_boundary`：直接调用旧函数 `uv_levels`/`uv_window`（`symbol_pc('uv_levels')` → KeyError）。这两个函数在 gen 129 起不存在，输入范围改由整数点表在 `eng_project_compute` 里校验。原意图（范围边界、非法值拒绝、输出不变）由 `boundary_sweep.py` 在集成计算路径上重做。
- `user_acceptance` / `other_users`：需要先跑 `tool_acceptance.py` 产生 `evidence/user-tool.json`；该脚本调用 `user_entries.py`（gen 135 源码树里没有）和 `candidate/ui_data.py`（只接受 ≤64 KiB、generation 127 的 DAT，gen 135 的 DAT 为 89,572 B）。**不是产品断言失败**，是用户条目命令行工具未随新格式更新，见 REVIEW.md。
