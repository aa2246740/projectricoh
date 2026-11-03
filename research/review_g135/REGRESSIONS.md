# 81 组完整回归表（review-g135-r1）

结果列：PASS = 返回码 0；FAIL_* = 返回码非 0 且已归类（依据列）；NOT_RUN = 时间盒内没有跑到；不把未跑、工具适配失败或设计变化记为产品通过。
全部由本复审自己的运行器 `runner.py` 对 gen 135 DAT（57743bc1…）+ v3.7 机身执行；旧脚本未改。归类依据与修正读取见 PORT_NOTES.md、WRAPPER.md。

| 家族 | 单元 | 组 | 返回码 | 秒 | 结果 | 依据 |
| --- | --- | --- | --- | --- | --- | --- |
| 124 | 50mm | safety | 1 | 341 | FAIL_ORIGINAL_READ | 原读取：陈旧布局文件 + 旧偏移 2523 + 旧数学期望（panel_rollback / ready_warm / write_latch）。修正读取（safety_cases_g135.py）三单元各 8/8，见 safety-corrected 行。 |
| 124 | 50mm | locked | 0 | 302 | PASS |  |
| 124 | 50mm | nested | 0 | 442 | PASS |  |
| 124 | 50mm | cutpoints | 0 | 235 | PASS |  |
| 124 | 50mm | exits | 0 | 1026 | PASS |  |
| 124 | 50mm | transitions | 1 | 310 | FAIL_OLD_DESIGN_TEXT | 第 66 行起断言旧卡片页文字 ['<5 F-CC','C 0 H 0 ','S 0 V 0 ','Default',…]；新设计卡片页为 C/H、S/F、V/W、T/P、Amt、Default。修正读取复制品 port-transitions 50mm/28mm 各 42/42 PASS。 |
| 124 | 50mm | values | 1 | 481 | FAIL_OLD_DESIGN_TEXT | 旧 ±5（11 点、零在第 5 位）、旧 11 字节向量；新设计每个 control 一张点表（−9…+9）、10×int16 向量、Amount=100。修正读取复制品 port-values 50mm：4 个 control 的 ±9 步进和 clamp、L1 虚拟滚动、Default 双击 PASS；back-from-second-pair 的光标期望是旧导航记忆（见 PORT_NOTES）。 |
| 124 | 50mm | view-reentry | 0 | 748 | PASS |  |
| 124 | 50mm | reentry-six | 0 | 807 | PASS |  |
| 124 | 50mm | users | 1 | 0 | TOOL_PREREQ | 需要先有 evidence/user-tool.json；产生它的 tool_acceptance.py 调用的 user_entries.py 不在 gen 135 源码树，其 ui_data.py 拒绝 >64 KiB / 非 127 的 DAT（ValueError 'invalid DAT envelope'）。非产品断言。 |
| 124 | 50mm | project | 1 | 114 | FAIL_RETIRED_FUNCTION | symbol_pc('uv_levels') → KeyError：函数在 gen 129 起不存在。范围边界检查由 boundary_sweep.py（集成计算路径，18,484 个非法值全部拒绝且输出未改）重做。 |
| 124 | 50mm | labels | 1 | 138 | FAIL_OLD_DESIGN_TEXT | label_acceptance.py:12 断言旧 03 号配方的三行布局；新设计 03 为 Cont/High/Shad/Fade/Filt。未修正读取（需要重做用例，不是改常量），由 product-menus 与 boundary_sweep 代替。 |
| 124 | 50mm | half | 0 | 156 | PASS |  |
| 124 | 28mm | safety | 1 | 330 | FAIL_ORIGINAL_READ | 原读取：陈旧布局文件 + 旧偏移 2523 + 旧数学期望（panel_rollback / ready_warm / write_latch）。修正读取（safety_cases_g135.py）三单元各 8/8，见 safety-corrected 行。 |
| 124 | 28mm | locked | 0 | 296 | PASS |  |
| 124 | 28mm | nested | 0 | 418 | PASS |  |
| 124 | 28mm | cutpoints | 0 | 220 | PASS |  |
| 124 | 28mm | exits |  |  | NOT_RUN |  |
| 124 | 28mm | transitions |  |  | NOT_RUN | 第 66 行起断言旧卡片页文字 ['<5 F-CC','C 0 H 0 ','S 0 V 0 ','Default',…]；新设计卡片页为 C/H、S/F、V/W、T/P、Amt、Default。修正读取复制品 port-transitions 50mm/28mm 各 42/42 PASS。 |
| 124 | 28mm | values |  |  | NOT_RUN | 旧 ±5（11 点、零在第 5 位）、旧 11 字节向量；新设计每个 control 一张点表（−9…+9）、10×int16 向量、Amount=100。修正读取复制品 port-values 50mm：4 个 control 的 ±9 步进和 clamp、L1 虚拟滚动、Default 双击 PASS；back-from-second-pair 的光标期望是旧导航记忆（见 PORT_NOTES）。 |
| 124 | 28mm | view-reentry |  |  | TIMEBOX |  |
| 124 | 28mm | reentry-six |  |  | TIMEBOX |  |
| 124 | 28mm | users | 1 | 0 | TOOL_PREREQ | 需要先有 evidence/user-tool.json；产生它的 tool_acceptance.py 调用的 user_entries.py 不在 gen 135 源码树，其 ui_data.py 拒绝 >64 KiB / 非 127 的 DAT（ValueError 'invalid DAT envelope'）。非产品断言。 |
| 124 | 28mm | project | 1 | 111 | FAIL_RETIRED_FUNCTION | symbol_pc('uv_levels') → KeyError：函数在 gen 129 起不存在。范围边界检查由 boundary_sweep.py（集成计算路径，18,484 个非法值全部拒绝且输出未改）重做。 |
| 124 | 28mm | labels | 1 | 138 | FAIL_OLD_DESIGN_TEXT | label_acceptance.py:12 断言旧 03 号配方的三行布局；新设计 03 为 Cont/High/Shad/Fade/Filt。未修正读取（需要重做用例，不是改常量），由 product-menus 与 boundary_sweep 代替。 |
| 124 | 28mm | half | 0 | 159 | PASS |  |
| 124 | mount | safety |  |  | NOT_RUN | 原读取：陈旧布局文件 + 旧偏移 2523 + 旧数学期望（panel_rollback / ready_warm / write_latch）。修正读取（safety_cases_g135.py）三单元各 8/8，见 safety-corrected 行。 |
| 124 | mount | locked | 0 | 295 | PASS |  |
| 124 | mount | nested | 0 | 427 | PASS |  |
| 124 | mount | cutpoints | 0 | 224 | PASS |  |
| 124 | mount | exits |  |  | NOT_RUN |  |
| 124 | mount | transitions |  |  | NOT_RUN | 第 66 行起断言旧卡片页文字 ['<5 F-CC','C 0 H 0 ','S 0 V 0 ','Default',…]；新设计卡片页为 C/H、S/F、V/W、T/P、Amt、Default。修正读取复制品 port-transitions 50mm/28mm 各 42/42 PASS。 |
| 124 | mount | values |  |  | NOT_RUN | 旧 ±5（11 点、零在第 5 位）、旧 11 字节向量；新设计每个 control 一张点表（−9…+9）、10×int16 向量、Amount=100。修正读取复制品 port-values 50mm：4 个 control 的 ±9 步进和 clamp、L1 虚拟滚动、Default 双击 PASS；back-from-second-pair 的光标期望是旧导航记忆（见 PORT_NOTES）。 |
| 124 | mount | view-reentry |  |  | NOT_RUN |  |
| 124 | mount | reentry-six |  |  | NOT_RUN |  |
| 124 | mount | users | 1 | 0 | TOOL_PREREQ | 需要先有 evidence/user-tool.json；产生它的 tool_acceptance.py 调用的 user_entries.py 不在 gen 135 源码树，其 ui_data.py 拒绝 >64 KiB / 非 127 的 DAT（ValueError 'invalid DAT envelope'）。非产品断言。 |
| 124 | mount | project | 1 | 110 | FAIL_RETIRED_FUNCTION | symbol_pc('uv_levels') → KeyError：函数在 gen 129 起不存在。范围边界检查由 boundary_sweep.py（集成计算路径，18,484 个非法值全部拒绝且输出未改）重做。 |
| 124 | mount | labels | 1 | 131 | FAIL_OLD_DESIGN_TEXT | label_acceptance.py:12 断言旧 03 号配方的三行布局；新设计 03 为 Cont/High/Shad/Fade/Filt。未修正读取（需要重做用例，不是改常量），由 product-menus 与 boundary_sweep 代替。 |
| 124 | mount | half | 0 | 163 | PASS |  |
| 126 | 50mm | safety |  |  | NOT_RUN | 同 124/safety。 |
| 126 | 50mm | locked | 0 | 295 | PASS |  |
| 126 | 50mm | nested | 0 | 409 | PASS |  |
| 126 | 50mm | cutpoints | 0 | 237 | PASS |  |
| 126 | 50mm | exits | 0 | 989 | PASS |  |
| 126 | 50mm | transitions |  |  | NOT_RUN | 同 124/transitions；修正读取见 port-transitions。 |
| 126 | 50mm | values |  |  | NOT_RUN | 同 124/values。 |
| 126 | 50mm | view-reentry | 0 | 758 | PASS |  |
| 126 | 50mm | reentry-six | 0 | 853 | PASS |  |
| 126 | 50mm | users | 1 | 0 | TOOL_PREREQ | 同 124/users。 |
| 126 | 50mm | project | 1 | 110 | FAIL_RETIRED_FUNCTION | 同 124/project。 |
| 126 | 50mm | labels | 1 | 135 | FAIL_OLD_DESIGN_TEXT | 同 124/labels。 |
| 126 | 50mm | half | 0 | 160 | PASS |  |
| 126 | 50mm | other-users | 1 | 0 | TOOL_PREREQ | 同 124/users。 |
| 126 | 28mm | safety |  |  | NOT_RUN | 同 124/safety。 |
| 126 | 28mm | locked | 0 | 294 | PASS |  |
| 126 | 28mm | nested | 0 | 420 | PASS |  |
| 126 | 28mm | cutpoints | 0 | 222 | PASS |  |
| 126 | 28mm | exits |  |  | NOT_RUN |  |
| 126 | 28mm | transitions |  |  | NOT_RUN | 同 124/transitions；修正读取见 port-transitions。 |
| 126 | 28mm | values |  |  | NOT_RUN | 同 124/values。 |
| 126 | 28mm | view-reentry |  |  | NOT_RUN |  |
| 126 | 28mm | reentry-six |  |  | NOT_RUN |  |
| 126 | 28mm | users | 1 | 0 | TOOL_PREREQ | 同 124/users。 |
| 126 | 28mm | project | 1 | 110 | FAIL_RETIRED_FUNCTION | 同 124/project。 |
| 126 | 28mm | labels | 1 | 137 | FAIL_OLD_DESIGN_TEXT | 同 124/labels。 |
| 126 | 28mm | half | 0 | 165 | PASS |  |
| 126 | 28mm | other-users | 1 | 0 | TOOL_PREREQ | 同 124/users。 |
| 126 | mount | safety |  |  | NOT_RUN | 同 124/safety。 |
| 126 | mount | locked | 0 | 294 | PASS |  |
| 126 | mount | nested | 0 | 435 | PASS |  |
| 126 | mount | cutpoints | 0 | 225 | PASS |  |
| 126 | mount | exits |  |  | NOT_RUN |  |
| 126 | mount | transitions |  |  | NOT_RUN | 同 124/transitions；修正读取见 port-transitions。 |
| 126 | mount | values |  |  | NOT_RUN | 同 124/values。 |
| 126 | mount | view-reentry |  |  | NOT_RUN |  |
| 126 | mount | reentry-six |  |  | NOT_RUN |  |
| 126 | mount | users | 1 | 0 | TOOL_PREREQ | 同 124/users。 |
| 126 | mount | project |  |  | TIMEBOX | 同 124/project。 |
| 126 | mount | labels | 1 | 130 | FAIL_OLD_DESIGN_TEXT | 同 124/labels。 |
| 126 | mount | half | 0 | 157 | PASS |  |
| 126 | mount | other-users | 1 | 0 | TOOL_PREREQ | 同 124/users。 |

汇总：FAIL_OLD_DESIGN_TEXT 8，FAIL_ORIGINAL_READ 2，FAIL_RETIRED_FUNCTION 5，NOT_RUN 24，PASS 30，TIMEBOX 3，TOOL_PREREQ 9（共 81 组）。

## 附加套件与独立复跑

| 项目 | 单元 | 返回码 | 秒 | 结果 | 说明 |
| --- | --- | --- | --- | --- | --- |
| history123 suite（9 例） | 50mm | 0 | 773 | PASS | 9/9 例 wait_status 0，DAT 57743bc1… |
| history123 suite（9 例） | 28mm | 0 | 799 | PASS | 9/9 例 wait_status 0，DAT 57743bc1… |
| history123 suite（9 例） | mount | 0 | 778 | PASS | 9/9 例 wait_status 0，DAT 57743bc1… |
| settings_cases（36 例，r2 参考核心） | 50mm | 0 | 532 | PASS | 36/36 |
| settings_cases（36 例，r2 参考核心） | 28mm | 0 | 519 | PASS | 36/36 |
| settings_cases（36 例，r2 参考核心） | mount | 0 | 568 | PASS | 36/36 |
| history122（9 条/单元） | 50mm | 0 | 223 | PASS | 逐条判断见 HISTORY122.md（27/27） |
| history122（9 条/单元） | 28mm | 0 | 224 | PASS | 逐条判断见 HISTORY122.md（27/27） |
| history122（9 条/单元） | mount | 0 | 224 | PASS | 逐条判断见 HISTORY122.md（27/27） |
| safety 修正读取（safety_cases_g135.py） | 50mm | 0 | 348 | PASS | 8/8；原读取 5/8（见上表 safety 行） |
| safety 修正读取（safety_cases_g135.py） | 28mm | 0 | 345 | PASS | 8/8；原读取 5/8（见上表 safety 行） |
| safety 修正读取（safety_cases_g135.py） | mount | 0 | 349 | PASS | 8/8；原读取 5/8（见上表 safety 行） |
| accept.py 复跑（accept_rerun.py） | 28mm | 0 | 229 | PASS | ACCEPT_DONE；part 1 重显 8 行、光标 4、强制 part 0/4 时 jl_delta=1；写入全 0 |
| accept.py 复跑（accept_rerun.py） | mount | 0 | 230 | PASS | ACCEPT_DONE；part 1 重显 8 行、光标 4、强制 part 0/4 时 jl_delta=1；写入全 0 |
| accept 扩展：part 0…7 全部取值（accept_parts.py） | 50mm | 0 | 372 | PASS | 仅 part 1、2 被接受（jl_delta=0），0/3/4/5/6/7 均 jl_delta=1 |
| accept 扩展：part 0…7 全部取值（accept_parts.py） | 28mm | 0 | 373 | PASS | 仅 part 1、2 被接受（jl_delta=0），0/3/4/5/6/7 均 jl_delta=1 |
| accept 扩展：part 0…7 全部取值（accept_parts.py） | mount | 0 | 389 | PASS | 仅 part 1、2 被接受（jl_delta=0），0/3/4/5/6/7 均 jl_delta=1 |
| native_checks preview-window（修正切点，0xd228） | 28mm | 0 | 124 | OBSERVED | OBSERVED：核对之后换视图，预览仍进入（P2-03 重新复现） |
| native_checks preview-deferred（修正切点，0xd200） | 28mm | 0 | 154 | PASS | 核对之前换视图：无写入、无预览、pending=1、重开恢复八行 |
| native_checks pending-read（修正切点，0xd200） | 28mm | 0 | 169 | PASS | 同上，外加一次读错误返回与元数据恢复 |
| native_checks h07-parent | 28mm | 0 | 112 | PASS | 晚到 S 写入 0、晚到预览 0 |
| native_checks h07-parent-preview | 28mm | 0 | 111 | PASS | 晚到 S 写入 0、晚到预览 0 |
| native_checks settings-check | 28mm | 0 | 141 | PASS |  |
| product_menus.py 独立复跑 | 50mm | 0 | 2375 | PASS | 帧序列与实现者记录逐字节相同（50mm 314 帧、28mm 316 帧） |
| product_menus.py 独立复跑 | 28mm | 0 | 2416 | PASS | 帧序列与实现者记录逐字节相同（50mm 314 帧、28mm 316 帧） |
| ui_acceptance transitions 修正读取 | 50mm | | | PASS | 42/42 例 |
| ui_acceptance transitions 修正读取 | 28mm | | | PASS | 42/42 例 |
| ui_acceptance values 修正读取 | 50mm | 1 | 1637 | 6/7 PASS，1 项设计变化 | 四个 control 的 ±9 步进与 clamp、L1 虚拟滚动、Default 双击 PASS；back-from-second-pair 的旧光标期望 (1,1) 不成立，新设计回到刚用过的那一对 (1,2)，只断言屏幕与光标，记为设计变化 |
| ui_acceptance values 修正读取 | 28mm | -15 | 1316 | 部分 | 四个 control 的步进 4/4 PASS 后被我终止（让出进程槽）；其余三个快速用例未跑 |

原样（stale 偏移）与修正后的 preview 窗口三例见 PORT_NOTES.md §3；有效记录为 `-port2`。

## 时间盒内没有闭合的组（如实列出，均不记通过）

共 27 组：124/28mm/exits（NOT_RUN）；124/28mm/transitions（NOT_RUN）；124/28mm/values（NOT_RUN）；124/28mm/view-reentry（TIMEBOX）；124/28mm/reentry-six（TIMEBOX）；124/mount/safety（NOT_RUN）；124/mount/exits（NOT_RUN）；124/mount/transitions（NOT_RUN）；124/mount/values（NOT_RUN）；124/mount/view-reentry（NOT_RUN）；124/mount/reentry-six（NOT_RUN）；126/50mm/safety（NOT_RUN）；126/50mm/transitions（NOT_RUN）；126/50mm/values（NOT_RUN）；126/28mm/safety（NOT_RUN）；126/28mm/exits（NOT_RUN）；126/28mm/transitions（NOT_RUN）；126/28mm/values（NOT_RUN）；126/28mm/view-reentry（NOT_RUN）；126/28mm/reentry-six（NOT_RUN）；126/mount/safety（NOT_RUN）；126/mount/exits（NOT_RUN）；126/mount/transitions（NOT_RUN）；126/mount/values（NOT_RUN）；126/mount/view-reentry（NOT_RUN）；126/mount/reentry-six（NOT_RUN）；126/mount/project（TIMEBOX）。

其中 TIMEBOX 是调度器在时间盒到点时终止的作业（group124-28mm-view-reentry、group124-28mm-reentry-six 刚起跑，group126-mount-project 已跑 92 s）。
没有跑到的都是下列已在 50mm（两个家族）通过或已归类的套件在其他单元 / 家族上的重复：lock-exits、view-reentry、reentry-all-keys 在 50mm 两个家族均 PASS；transitions / values 的行为部分已由修正读取复制品覆盖；原读取 safety 的三条假失败已由修正读取三单元 8/8 覆盖。
