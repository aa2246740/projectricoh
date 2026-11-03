81 组完整回归表。下表只使用本轮 gen 129 的执行结果。

NA 表示最终代码没有相应旧调用点，不计为实际执行 PASS。缺少记录、时间盒停止和工具适配失败均不记通过。没有逐例汇总的完整套件只计一组通过。已有记录列仅表示已落盘的逐例记录数，不表示整组通过；分类见 JSON 的 partial_record_counts。

| 家族 | 单元 | 组 | 执行 | 返回码 | 秒 | PASS | FAIL | NA | 已有记录 | 结果 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 124 | 50mm | safety | FINISHED | 1 | 353.681 | 5 | 3 | 0 | 8 | FAIL_UNCLASSIFIED |
| 124 | 50mm | locked | FINISHED | 0 | 303.191 | 8 | 0 | 0 | 8 | PASS |
| 124 | 50mm | nested | FINISHED | 0 | 418.101 | 30 | 0 | 10 | 30 | PASS |
| 124 | 50mm | cutpoints | FINISHED | 0 | 227.783 | 8 | 0 | 8 | 8 | PASS |
| 124 | 50mm | exits | FINISHED | 0 | 1028.748 | 24 | 0 | 0 | 24 | PASS |
| 124 | 50mm | transitions | FINISHED | 1 | 68.115 | 0 | 0 | 0 | 0 | FAIL_UNCLASSIFIED |
| 124 | 50mm | values | FINISHED | 1 | 66.807 | 0 | 0 | 0 | 0 | FAIL_UNCLASSIFIED |
| 124 | 50mm | view-reentry | FINISHED | 1 | 84.198 | 0 | 0 | 0 | 0 | FAIL_UNCLASSIFIED |
| 124 | 50mm | reentry-six | FINISHED | 1 | 86.552 | 0 | 0 | 0 | 0 | FAIL_UNCLASSIFIED |
| 124 | 50mm | users | FINISHED | 1 | 0.273 | 0 | 0 | 0 | 0 | TOOL_ERROR |
| 124 | 50mm | project | FINISHED | 1 | 63.427 | 0 | 0 | 0 | 0 | TOOL_ERROR |
| 124 | 50mm | labels | FINISHED | 1 | 82.213 | 0 | 0 | 0 | 0 | FAIL_UNCLASSIFIED |
| 124 | 50mm | half | FINISHED | 0 | 87.655 | 1 | 0 | 0 | 0 | PASS |
| 124 | 28mm | safety | FINISHED | 1 | 399.61 | 5 | 3 | 0 | 8 | FAIL_UNCLASSIFIED |
| 124 | 28mm | locked | FINISHED | 0 | 290.456 | 8 | 0 | 0 | 8 | PASS |
| 124 | 28mm | nested | FINISHED | 0 | 413.506 | 30 | 0 | 10 | 30 | PASS |
| 124 | 28mm | cutpoints | FINISHED | 0 | 224.64 | 8 | 0 | 8 | 8 | PASS |
| 124 | 28mm | exits | FINISHED | 0 | 949.033 | 24 | 0 | 0 | 24 | PASS |
| 124 | 28mm | transitions | FINISHED | 1 | 64.24 | 0 | 0 | 0 | 0 | FAIL_UNCLASSIFIED |
| 124 | 28mm | values | FINISHED | 1 | 64.168 | 0 | 0 | 0 | 0 | FAIL_UNCLASSIFIED |
| 124 | 28mm | view-reentry | FINISHED | 1 | 82.925 | 0 | 0 | 0 | 0 | FAIL_UNCLASSIFIED |
| 124 | 28mm | reentry-six | FINISHED | 1 | 1.238 | 0 | 0 | 0 | 0 | FAIL_UNCLASSIFIED |
| 124 | 28mm | users | FINISHED | 1 | 0.26 | 0 | 0 | 0 | 0 | TOOL_ERROR |
| 124 | 28mm | project | FINISHED | 1 | 1.059 | 0 | 0 | 0 | 0 | FAIL_UNCLASSIFIED |
| 124 | 28mm | labels | FINISHED | 1 | 1.052 | 0 | 0 | 0 | 0 | FAIL_UNCLASSIFIED |
| 124 | 28mm | half | FINISHED | 0 | 88.692 | 1 | 0 | 0 | 0 | PASS |
| 124 | mount | safety | FINISHED | 1 | 328.839 | 5 | 3 | 0 | 8 | FAIL_UNCLASSIFIED |
| 124 | mount | locked | FINISHED | 0 | 288.961 | 8 | 0 | 0 | 8 | PASS |
| 124 | mount | nested | FINISHED | 0 | 431.908 | 30 | 0 | 10 | 30 | PASS |
| 124 | mount | cutpoints | FINISHED | 0 | 234.296 | 8 | 0 | 8 | 8 | PASS |
| 124 | mount | exits | FINISHED | 0 | 991.892 | 24 | 0 | 0 | 24 | PASS |
| 124 | mount | transitions | FINISHED | 1 | 132.613 | 0 | 0 | 0 | 0 | TOOL_ERROR |
| 124 | mount | values | FINISHED | 1 | 133.957 | 0 | 0 | 0 | 0 | TOOL_ERROR |
| 124 | mount | view-reentry | FINISHED | 0 | 734.755 | 1 | 0 | 0 | 0 | PASS |
| 124 | mount | reentry-six | FINISHED | 0 | 843.58 | 210 | 0 | 0 | 210 | PASS |
| 124 | mount | users | FINISHED | 1 | 0.307 | 0 | 0 | 0 | 0 | TOOL_ERROR |
| 124 | mount | project | FINISHED | 1 | 114.457 | 0 | 0 | 0 | 0 | TOOL_ERROR |
| 124 | mount | labels | FINISHED | 1 | 131.837 | 0 | 0 | 0 | 0 | FAIL_UNCLASSIFIED |
| 124 | mount | half | FINISHED | 0 | 88.82 | 1 | 0 | 0 | 0 | PASS |
| 126 | 50mm | safety | FINISHED | 1 | 342.614 | 5 | 3 | 0 | 8 | FAIL_UNCLASSIFIED |
| 126 | 50mm | locked | FINISHED | 0 | 306.989 | 8 | 0 | 0 | 8 | PASS |
| 126 | 50mm | nested | RUNNING | None | 0 | 0 | 0 | 0 | 0 | RUNNING |
| 126 | 50mm | cutpoints | RUNNING | None | 0 | 0 | 0 | 0 | 0 | RUNNING |
| 126 | 50mm | exits | RUNNING | None | 0 | 0 | 0 | 0 | 0 | RUNNING |
| 126 | 50mm | transitions | NOT_STARTED | None | 0 | 0 | 0 | 0 | 0 | INCOMPLETE |
| 126 | 50mm | values | NOT_STARTED | None | 0 | 0 | 0 | 0 | 0 | INCOMPLETE |
| 126 | 50mm | view-reentry | NOT_STARTED | None | 0 | 0 | 0 | 0 | 0 | INCOMPLETE |
| 126 | 50mm | reentry-six | NOT_STARTED | None | 0 | 0 | 0 | 0 | 0 | INCOMPLETE |
| 126 | 50mm | users | NOT_STARTED | None | 0 | 0 | 0 | 0 | 0 | INCOMPLETE |
| 126 | 50mm | project | NOT_STARTED | None | 0 | 0 | 0 | 0 | 0 | INCOMPLETE |
| 126 | 50mm | labels | NOT_STARTED | None | 0 | 0 | 0 | 0 | 0 | INCOMPLETE |
| 126 | 50mm | half | NOT_STARTED | None | 0 | 0 | 0 | 0 | 0 | INCOMPLETE |
| 126 | 50mm | other-users | NOT_STARTED | None | 0 | 0 | 0 | 0 | 0 | INCOMPLETE |
| 126 | 28mm | safety | NOT_STARTED | None | 0 | 0 | 0 | 0 | 0 | INCOMPLETE |
| 126 | 28mm | locked | NOT_STARTED | None | 0 | 0 | 0 | 0 | 0 | INCOMPLETE |
| 126 | 28mm | nested | NOT_STARTED | None | 0 | 0 | 0 | 0 | 0 | INCOMPLETE |
| 126 | 28mm | cutpoints | NOT_STARTED | None | 0 | 0 | 0 | 0 | 0 | INCOMPLETE |
| 126 | 28mm | exits | NOT_STARTED | None | 0 | 0 | 0 | 0 | 0 | INCOMPLETE |
| 126 | 28mm | transitions | NOT_STARTED | None | 0 | 0 | 0 | 0 | 0 | INCOMPLETE |
| 126 | 28mm | values | NOT_STARTED | None | 0 | 0 | 0 | 0 | 0 | INCOMPLETE |
| 126 | 28mm | view-reentry | NOT_STARTED | None | 0 | 0 | 0 | 0 | 0 | INCOMPLETE |
| 126 | 28mm | reentry-six | NOT_STARTED | None | 0 | 0 | 0 | 0 | 0 | INCOMPLETE |
| 126 | 28mm | users | NOT_STARTED | None | 0 | 0 | 0 | 0 | 0 | INCOMPLETE |
| 126 | 28mm | project | NOT_STARTED | None | 0 | 0 | 0 | 0 | 0 | INCOMPLETE |
| 126 | 28mm | labels | NOT_STARTED | None | 0 | 0 | 0 | 0 | 0 | INCOMPLETE |
| 126 | 28mm | half | NOT_STARTED | None | 0 | 0 | 0 | 0 | 0 | INCOMPLETE |
| 126 | 28mm | other-users | NOT_STARTED | None | 0 | 0 | 0 | 0 | 0 | INCOMPLETE |
| 126 | mount | safety | NOT_STARTED | None | 0 | 0 | 0 | 0 | 0 | INCOMPLETE |
| 126 | mount | locked | NOT_STARTED | None | 0 | 0 | 0 | 0 | 0 | INCOMPLETE |
| 126 | mount | nested | NOT_STARTED | None | 0 | 0 | 0 | 0 | 0 | INCOMPLETE |
| 126 | mount | cutpoints | NOT_STARTED | None | 0 | 0 | 0 | 0 | 0 | INCOMPLETE |
| 126 | mount | exits | NOT_STARTED | None | 0 | 0 | 0 | 0 | 0 | INCOMPLETE |
| 126 | mount | transitions | NOT_STARTED | None | 0 | 0 | 0 | 0 | 0 | INCOMPLETE |
| 126 | mount | values | NOT_STARTED | None | 0 | 0 | 0 | 0 | 0 | INCOMPLETE |
| 126 | mount | view-reentry | NOT_STARTED | None | 0 | 0 | 0 | 0 | 0 | INCOMPLETE |
| 126 | mount | reentry-six | NOT_STARTED | None | 0 | 0 | 0 | 0 | 0 | INCOMPLETE |
| 126 | mount | users | NOT_STARTED | None | 0 | 0 | 0 | 0 | 0 | INCOMPLETE |
| 126 | mount | project | NOT_STARTED | None | 0 | 0 | 0 | 0 | 0 | INCOMPLETE |
| 126 | mount | labels | NOT_STARTED | None | 0 | 0 | 0 | 0 | 0 | INCOMPLETE |
| 126 | mount | half | NOT_STARTED | None | 0 | 0 | 0 | 0 | 0 | INCOMPLETE |
| 126 | mount | other-users | NOT_STARTED | None | 0 | 0 | 0 | 0 | 0 | INCOMPLETE |

| 附加套件 | 采用记录 | 执行 | 返回码 | 秒 | PASS | FAIL | OBSERVED | 结果 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| history123-50mm | history123-50mm | FINISHED | 0 | 758.071 | 1 | 0 | 0 | PASS |
| settings_cases-50mm | settings-r6-50mm | FINISHED | 0 | 551.715 | 36 | 0 | 0 | PASS |
| history122-50mm | history122-50mm | FINISHED | 0 | 234.793 | 1 | 0 | 0 | OBSERVED |
| history123-28mm | history123-28mm | FINISHED | 0 | 767.199 | 1 | 0 | 0 | PASS |
| settings_cases-28mm | settings-r6-28mm | FINISHED | 0 | 561.35 | 36 | 0 | 0 | PASS |
| history122-28mm | history122-28mm | FINISHED | 0 | 233.171 | 1 | 0 | 0 | OBSERVED |
| history123-mount | history123-mount | FINISHED | 0 | 781.315 | 1 | 0 | 0 | PASS |
| settings_cases-mount | settings-r6-mount | FINISHED | 0 | 546.469 | 36 | 0 | 0 | PASS |
| history122-mount | history122-mount | FINISHED | 0 | 241.148 | 1 | 0 | 0 | OBSERVED |

复跑前的首次结果保留在 regressions.json 的 prior_attempt、对应 local 目录和 manual-results.json 中。没有用独立的窄范围检查替代完整旧套件。

汇总时间：2026-10-29T02:23:14.577390+00:00。
