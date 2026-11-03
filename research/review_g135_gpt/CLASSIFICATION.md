# 首轮 24 组归类的独立核对

8 组旧显示、5 组旧入口、2 组旧读取、9 组工具前提，共 24 组。原错误均不能直接判作 gen 135 产品断言失败；每组的替代覆盖仍单独记账。

| 家族 | 单元 | 组 | 独立判断与依据 |
| --- | --- | --- | --- |
| 124 | 50mm | safety | 原 ready=2523、旧布局和旧对比度期望不适用。目标编译器复核 ready=4844、uncertain=4848、write_started=4859；修正读取保留原恢复与锁存断言，见 layout-current.json、safety 组与 g129 triage。 |
| 124 | 50mm | transitions | 旧卡片与项目文字不符新设计，旧零位为 5，新零位为 9。新卡片显示 C/H、S/F、V/W、T/P、Amt、Default。原两个家族的函数合同相同，适配未减少断言；实际 transitions 结果见回归表。 |
| 124 | 50mm | values | 旧 ±5、十一字节向量和全零默认值不符新设计。当前四项按实际点表步进，向量为十个 int16，Amount 默认 100。返回卡片光标须保留各层记忆；旧 (1,1) 与新 (1,2) 分开记录，实际结果及导航观察见本轮证据。 |
| 124 | 50mm | users | 原组缺少 user-tool.json，未进入产品断言。旧工具拒绝当前 DAT 外层格式。新 users_gxui.py 保留 GXUI v1 记录，工具验收已通过；本轮界面结果见回归表，原工具失败不改记产品通过。 |
| 124 | 50mm | project | 原组先查 uv_levels 即停止，尚未进入产品断言。uv_levels 的旧十一字节接口已被新点表替代；uv_window 仍在最终 ELF 的 0x250，不能称为退役。完整计算边界与实际 M32R 窗口分别补证，见 boundary-sweep.json、windows.json。 |
| 124 | 50mm | labels | 旧 03 卡片和 Shad 后为空白的断言不适用。当前三单元 03 控件精确为 [1,2,3,4,9]，即 Cont/High/Shad/Fade/Filt；Shad 后应为 Fade。隐藏 Satu 的拒绝由计算边界补证，填充与窗口规则见实际 M32R 窗口及菜单记录；原组不记 PASS。 |
| 124 | 28mm | safety | 原 ready=2523、旧布局和旧对比度期望不适用。目标编译器复核 ready=4844、uncertain=4848、write_started=4859；修正读取保留原恢复与锁存断言，见 layout-current.json、safety 组与 g129 triage。 |
| 124 | 28mm | users | 原组缺少 user-tool.json，未进入产品断言。旧工具拒绝当前 DAT 外层格式。新 users_gxui.py 保留 GXUI v1 记录，工具验收已通过；本轮界面结果见回归表，原工具失败不改记产品通过。 |
| 124 | 28mm | project | 原组先查 uv_levels 即停止，尚未进入产品断言。uv_levels 的旧十一字节接口已被新点表替代；uv_window 仍在最终 ELF 的 0x250，不能称为退役。完整计算边界与实际 M32R 窗口分别补证，见 boundary-sweep.json、windows.json。 |
| 124 | 28mm | labels | 旧 03 卡片和 Shad 后为空白的断言不适用。当前三单元 03 控件精确为 [1,2,3,4,9]，即 Cont/High/Shad/Fade/Filt；Shad 后应为 Fade。隐藏 Satu 的拒绝由计算边界补证，填充与窗口规则见实际 M32R 窗口及菜单记录；原组不记 PASS。 |
| 124 | mount | users | 原组缺少 user-tool.json，未进入产品断言。旧工具拒绝当前 DAT 外层格式。新 users_gxui.py 保留 GXUI v1 记录，工具验收已通过；本轮界面结果见回归表，原工具失败不改记产品通过。 |
| 124 | mount | project | 原组先查 uv_levels 即停止，尚未进入产品断言。uv_levels 的旧十一字节接口已被新点表替代；uv_window 仍在最终 ELF 的 0x250，不能称为退役。完整计算边界与实际 M32R 窗口分别补证，见 boundary-sweep.json、windows.json。 |
| 124 | mount | labels | 旧 03 卡片和 Shad 后为空白的断言不适用。当前三单元 03 控件精确为 [1,2,3,4,9]，即 Cont/High/Shad/Fade/Filt；Shad 后应为 Fade。隐藏 Satu 的拒绝由计算边界补证，填充与窗口规则见实际 M32R 窗口及菜单记录；原组不记 PASS。 |
| 126 | 50mm | users | 原组缺少 user-tool.json，未进入产品断言。旧工具拒绝当前 DAT 外层格式。新 users_gxui.py 保留 GXUI v1 记录，工具验收已通过；本轮界面结果见回归表，原工具失败不改记产品通过。 |
| 126 | 50mm | project | 原组先查 uv_levels 即停止，尚未进入产品断言。uv_levels 的旧十一字节接口已被新点表替代；uv_window 仍在最终 ELF 的 0x250，不能称为退役。完整计算边界与实际 M32R 窗口分别补证，见 boundary-sweep.json、windows.json。 |
| 126 | 50mm | labels | 旧 03 卡片和 Shad 后为空白的断言不适用。当前三单元 03 控件精确为 [1,2,3,4,9]，即 Cont/High/Shad/Fade/Filt；Shad 后应为 Fade。隐藏 Satu 的拒绝由计算边界补证，填充与窗口规则见实际 M32R 窗口及菜单记录；原组不记 PASS。 |
| 126 | 50mm | other-users | 原组缺少 user-tool.json，未进入产品断言。旧工具拒绝当前 DAT 外层格式。新 users_gxui.py 保留 GXUI v1 记录，工具验收已通过；本轮界面结果见回归表，原工具失败不改记产品通过。 |
| 126 | 28mm | users | 原组缺少 user-tool.json，未进入产品断言。旧工具拒绝当前 DAT 外层格式。新 users_gxui.py 保留 GXUI v1 记录，工具验收已通过；本轮界面结果见回归表，原工具失败不改记产品通过。 |
| 126 | 28mm | project | 原组先查 uv_levels 即停止，尚未进入产品断言。uv_levels 的旧十一字节接口已被新点表替代；uv_window 仍在最终 ELF 的 0x250，不能称为退役。完整计算边界与实际 M32R 窗口分别补证，见 boundary-sweep.json、windows.json。 |
| 126 | 28mm | labels | 旧 03 卡片和 Shad 后为空白的断言不适用。当前三单元 03 控件精确为 [1,2,3,4,9]，即 Cont/High/Shad/Fade/Filt；Shad 后应为 Fade。隐藏 Satu 的拒绝由计算边界补证，填充与窗口规则见实际 M32R 窗口及菜单记录；原组不记 PASS。 |
| 126 | 28mm | other-users | 原组缺少 user-tool.json，未进入产品断言。旧工具拒绝当前 DAT 外层格式。新 users_gxui.py 保留 GXUI v1 记录，工具验收已通过；本轮界面结果见回归表，原工具失败不改记产品通过。 |
| 126 | mount | users | 原组缺少 user-tool.json，未进入产品断言。旧工具拒绝当前 DAT 外层格式。新 users_gxui.py 保留 GXUI v1 记录，工具验收已通过；本轮界面结果见回归表，原工具失败不改记产品通过。 |
| 126 | mount | labels | 旧 03 卡片和 Shad 后为空白的断言不适用。当前三单元 03 控件精确为 [1,2,3,4,9]，即 Cont/High/Shad/Fade/Filt；Shad 后应为 Fade。隐藏 Satu 的拒绝由计算边界补证，填充与窗口规则见实际 M32R 窗口及菜单记录；原组不记 PASS。 |
| 126 | mount | other-users | 原组缺少 user-tool.json，未进入产品断言。旧工具拒绝当前 DAT 外层格式。新 users_gxui.py 保留 GXUI v1 记录，工具验收已通过；本轮界面结果见回归表，原工具失败不改记产品通过。 |

依据：`research/knobs_v2_engine_design/DESIGN.md`；`research/g129_safety_triage/REPORT.md`；本目录 `evidence/static-review.json`、`family-contracts.json`、`port-contracts.json`、`layout-current.json`、`boundary-sweep.json`、`windows.json`、`nav-memory.json` 和逐组记录。

需要更正首轮说明：五组 project 停止的直接原因是 uv_levels 缺少旧入口；uv_window 保留，首轮关于两个函数都不存在的说法不成立。该说明错误属于复审证据问题，不能据此判定固件窗口故障。
