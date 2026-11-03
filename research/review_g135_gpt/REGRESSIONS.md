# 回归表

原始 81 组逐项保留。PASS 指本轮实际返回 0；沿用项只表示首轮记录及清单已核对。旧断言失效的组保留原返回码，替代检查不改写成原组通过。RECOVERED_REPORT 表示完整子项报告已复原，但没有外层进程退出回执；不计严格闭合。其秒数来自末份报告时间戳与启动记录之差。

| 家族 | 单元 | 组 | 首轮 | 本轮 | 退出回执 | 执行状态 | 秒 | 实际脚本 / 证据 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 124 | 50mm | safety | FAIL_ORIGINAL_READ | 未独立重跑 |  |  |  |  |
| 124 | 50mm | locked | PASS | 沿用已校验的首轮证据 |  |  |  |  |
| 124 | 50mm | nested | PASS | 沿用已校验的首轮证据 |  |  |  |  |
| 124 | 50mm | cutpoints | PASS | 沿用已校验的首轮证据 |  |  |  |  |
| 124 | 50mm | exits | PASS | 沿用已校验的首轮证据 |  |  |  |  |
| 124 | 50mm | transitions | FAIL_OLD_DESIGN_TEXT | 未独立重跑 |  |  |  |  |
| 124 | 50mm | values | FAIL_OLD_DESIGN_TEXT | 未独立重跑 |  |  |  |  |
| 124 | 50mm | view-reentry | PASS | 沿用已校验的首轮证据 |  |  |  |  |
| 124 | 50mm | reentry-six | PASS | 沿用已校验的首轮证据 |  |  |  |  |
| 124 | 50mm | users | TOOL_PREREQ | 卡片标题差异已记录，其余断言完成 | 1 | FINISHED | 610.852 | research/review_g124/user_acceptance.py；local/jobs/group124-50mm-users/ |
| 124 | 50mm | project | FAIL_RETIRED_FUNCTION | 未独立重跑 |  |  |  |  |
| 124 | 50mm | labels | FAIL_OLD_DESIGN_TEXT | 未独立重跑 |  |  |  |  |
| 124 | 50mm | half | PASS | 沿用已校验的首轮证据 |  |  |  |  |
| 124 | 28mm | safety | FAIL_ORIGINAL_READ | 未独立重跑 |  |  |  |  |
| 124 | 28mm | locked | PASS | 沿用已校验的首轮证据 |  |  |  |  |
| 124 | 28mm | nested | PASS | 沿用已校验的首轮证据 |  |  |  |  |
| 124 | 28mm | cutpoints | PASS | 沿用已校验的首轮证据 |  |  |  |  |
| 124 | 28mm | exits | NOT_RUN | PASS | 0 | FINISHED | 956.967 | research/review_g124/lock_exits.py；local/jobs/group124-28mm-exits/ |
| 124 | 28mm | transitions | NOT_RUN | PASS | 0 | FINISHED | 892.365 | research/review_g135/legacy/ui_acceptance_g135.py；local/jobs/group124-28mm-transitions/ |
| 124 | 28mm | values | NOT_RUN | 子项结果已复原，退出回执未留存 | 未留存；运行器报告 1 | RECOVERED_REPORT | 1695.313 | research/review_g135/legacy/ui_acceptance_g135.py；local/jobs/group124-28mm-values/ |
| 124 | 28mm | view-reentry | TIMEBOX | PASS | 0 | FINISHED | 730.858 | research/review_g124/view_reentry.py；local/jobs/group124-28mm-view-reentry-r2/ |
| 124 | 28mm | reentry-six | TIMEBOX | PASS | 0 | FINISHED | 841.63 | research/review_g124/reentry_all_keys.py；local/jobs/group124-28mm-reentry-six/ |
| 124 | 28mm | users | TOOL_PREREQ | NOT_STARTED |  | NOT_STARTED |  |  |
| 124 | 28mm | project | FAIL_RETIRED_FUNCTION | 未独立重跑 |  |  |  |  |
| 124 | 28mm | labels | FAIL_OLD_DESIGN_TEXT | 未独立重跑 |  |  |  |  |
| 124 | 28mm | half | PASS | 沿用已校验的首轮证据 |  |  |  |  |
| 124 | mount | safety | NOT_RUN | PASS | 0 | FINISHED | 355.997 | research/g135_v37/safety_cases_g135.py；local/jobs/group124-mount-safety/ |
| 124 | mount | locked | PASS | 沿用已校验的首轮证据 |  |  |  |  |
| 124 | mount | nested | PASS | 沿用已校验的首轮证据 |  |  |  |  |
| 124 | mount | cutpoints | PASS | 沿用已校验的首轮证据 |  |  |  |  |
| 124 | mount | exits | NOT_RUN | PASS | 0 | FINISHED | 947.792 | research/review_g124/lock_exits.py；local/jobs/group124-mount-exits/ |
| 124 | mount | transitions | NOT_RUN | PASS | 0 | FINISHED | 875.548 | research/review_g135/legacy/ui_acceptance_g135.py；local/jobs/group124-mount-transitions/ |
| 124 | mount | values | NOT_RUN | 子项结果已复原，退出回执未留存 | 未留存；运行器报告 1 | RECOVERED_REPORT | 1711.115 | research/review_g135/legacy/ui_acceptance_g135.py；local/jobs/group124-mount-values/ |
| 124 | mount | view-reentry | NOT_RUN | PASS | 0 | FINISHED | 704.655 | research/review_g124/view_reentry.py；local/jobs/group124-mount-view-reentry-r2/ |
| 124 | mount | reentry-six | NOT_RUN | PASS | 0 | FINISHED | 883.899 | research/review_g124/reentry_all_keys.py；local/jobs/group124-mount-reentry-six/ |
| 124 | mount | users | TOOL_PREREQ | NOT_STARTED |  | NOT_STARTED |  |  |
| 124 | mount | project | FAIL_RETIRED_FUNCTION | 未独立重跑 |  |  |  |  |
| 124 | mount | labels | FAIL_OLD_DESIGN_TEXT | 未独立重跑 |  |  |  |  |
| 124 | mount | half | PASS | 沿用已校验的首轮证据 |  |  |  |  |
| 126 | 50mm | safety | NOT_RUN | PASS | 0 | FINISHED | 366.801 | research/g135_v37/safety_cases_g135.py；local/jobs/group126-50mm-safety/ |
| 126 | 50mm | locked | PASS | 沿用已校验的首轮证据 |  |  |  |  |
| 126 | 50mm | nested | PASS | 沿用已校验的首轮证据 |  |  |  |  |
| 126 | 50mm | cutpoints | PASS | 沿用已校验的首轮证据 |  |  |  |  |
| 126 | 50mm | exits | PASS | 沿用已校验的首轮证据 |  |  |  |  |
| 126 | 50mm | transitions | NOT_RUN | PASS | 0 | FINISHED | 894.553 | research/review_g135/legacy/ui_acceptance_g135.py；local/jobs/group126-50mm-transitions/ |
| 126 | 50mm | values | NOT_RUN | NOT_STARTED |  | NOT_STARTED |  |  |
| 126 | 50mm | view-reentry | PASS | 沿用已校验的首轮证据 |  |  |  |  |
| 126 | 50mm | reentry-six | PASS | 沿用已校验的首轮证据 |  |  |  |  |
| 126 | 50mm | users | TOOL_PREREQ | 卡片标题差异已记录，其余断言完成 | 1 | FINISHED | 600.04 | research/review_g126/user_acceptance.py；local/jobs/group126-50mm-users-r4/ |
| 126 | 50mm | project | FAIL_RETIRED_FUNCTION | 未独立重跑 |  |  |  |  |
| 126 | 50mm | labels | FAIL_OLD_DESIGN_TEXT | 未独立重跑 |  |  |  |  |
| 126 | 50mm | half | PASS | 沿用已校验的首轮证据 |  |  |  |  |
| 126 | 50mm | other-users | TOOL_PREREQ | PASS | 0 | FINISHED | 527.917 | research/review_g126/other_users.py；local/jobs/group126-50mm-other-users/ |
| 126 | 28mm | safety | NOT_RUN | PASS | 0 | FINISHED | 359.821 | research/g135_v37/safety_cases_g135.py；local/jobs/group126-28mm-safety/ |
| 126 | 28mm | locked | PASS | 沿用已校验的首轮证据 |  |  |  |  |
| 126 | 28mm | nested | PASS | 沿用已校验的首轮证据 |  |  |  |  |
| 126 | 28mm | cutpoints | PASS | 沿用已校验的首轮证据 |  |  |  |  |
| 126 | 28mm | exits | NOT_RUN | PASS | 0 | FINISHED | 962.878 | research/review_g126/lock_exits.py；local/jobs/group126-28mm-exits/ |
| 126 | 28mm | transitions | NOT_RUN | PASS | 0 | FINISHED | 882.582 | research/review_g135/legacy/ui_acceptance_g135.py；local/jobs/group126-28mm-transitions/ |
| 126 | 28mm | values | NOT_RUN | 子项结果已复原，退出回执未留存 | 未留存；运行器报告 1 | RECOVERED_REPORT | 1702.761 | research/review_g135/legacy/ui_acceptance_g135.py；local/jobs/group126-28mm-values/ |
| 126 | 28mm | view-reentry | NOT_RUN | PASS | 0 | FINISHED | 749.791 | research/review_g126/view_reentry.py；local/jobs/group126-28mm-view-reentry/ |
| 126 | 28mm | reentry-six | NOT_RUN | PASS | 0 | FINISHED | 870.039 | research/review_g126/reentry_all_keys.py；local/jobs/group126-28mm-reentry-six/ |
| 126 | 28mm | users | TOOL_PREREQ | NOT_STARTED |  | NOT_STARTED |  |  |
| 126 | 28mm | project | FAIL_RETIRED_FUNCTION | 未独立重跑 |  |  |  |  |
| 126 | 28mm | labels | FAIL_OLD_DESIGN_TEXT | 未独立重跑 |  |  |  |  |
| 126 | 28mm | half | PASS | 沿用已校验的首轮证据 |  |  |  |  |
| 126 | 28mm | other-users | TOOL_PREREQ | NOT_STARTED |  | NOT_STARTED |  |  |
| 126 | mount | safety | NOT_RUN | PASS | 0 | FINISHED | 360.749 | research/g135_v37/safety_cases_g135.py；local/jobs/group126-mount-safety/ |
| 126 | mount | locked | PASS | 沿用已校验的首轮证据 |  |  |  |  |
| 126 | mount | nested | PASS | 沿用已校验的首轮证据 |  |  |  |  |
| 126 | mount | cutpoints | PASS | 沿用已校验的首轮证据 |  |  |  |  |
| 126 | mount | exits | NOT_RUN | PASS | 0 | FINISHED | 947.143 | research/review_g126/lock_exits.py；local/jobs/group126-mount-exits/ |
| 126 | mount | transitions | NOT_RUN | PASS | 0 | FINISHED | 874.237 | research/review_g135/legacy/ui_acceptance_g135.py；local/jobs/group126-mount-transitions/ |
| 126 | mount | values | NOT_RUN | NOT_STARTED |  | NOT_STARTED |  |  |
| 126 | mount | view-reentry | NOT_RUN | PASS | 0 | FINISHED | 712.212 | research/review_g126/view_reentry.py；local/jobs/group126-mount-view-reentry/ |
| 126 | mount | reentry-six | NOT_RUN | PASS | 0 | FINISHED | 816.334 | research/review_g126/reentry_all_keys.py；local/jobs/group126-mount-reentry-six/ |
| 126 | mount | users | TOOL_PREREQ | NOT_STARTED |  | NOT_STARTED |  |  |
| 126 | mount | project | TIMEBOX | 旧入口已归类，替代检查通过 | 1 | FINISHED | 119.394 | research/review_g126/project_boundary.py；local/jobs/group126-mount-project/ |
| 126 | mount | labels | FAIL_OLD_DESIGN_TEXT | 未独立重跑 |  |  |  |  |
| 126 | mount | half | PASS | 沿用已校验的首轮证据 |  |  |  |  |
| 126 | mount | other-users | TOOL_PREREQ | NOT_STARTED |  | NOT_STARTED |  |  |

## 首轮未闭合的 27 组

闭合 22/27。以下组仍未闭合，不能记为通过。

- group124-28mm-values。
- group124-mount-values。
- group126-50mm-values。
- group126-28mm-values。
- group126-mount-values。

其中三组值域报告见 evidence/recovered-groups.json：每组四个逐档检查、L1 滚动与 Default 通过；返回第二行的旧期望失败，实际为 (1,2)，符合 DESIGN.md 的分层光标记忆。缺少退出回执，仍列在未闭合项内。

## 用户条目

本轮执行闭合 3/9，通过 1/9，另有 2 组保留卡片标题差异。工具检查与界面组分列；工具通过不能代替界面组。

- group124-28mm-users 仍未闭合。
- group124-mount-users 仍未闭合。
- group126-28mm-users 仍未闭合。
- group126-28mm-other-users 仍未闭合。
- group126-mount-users 仍未闭合。
- group126-mount-other-users 仍未闭合。
