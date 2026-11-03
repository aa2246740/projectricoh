# 回归表

闭合 11/11。PASS 要求整组退出码 0 且子项全部通过；CLOSED_KNOWN_P2 保留退出码 1，只接受已明确认可的卡片标题差异。

| 原组 | 实际运行 | 原始退出码 | 状态 | 秒 |
| --- | --- | --- | --- | --- |
| group124-28mm-values | final-values-124-28mm | 0 | PASS | 1630.898 |
| group124-mount-values | final-values-124-mount | 0 | PASS | 1634.59 |
| group126-50mm-values | final-values-126-50mm | 0 | PASS | 1634.496 |
| group126-28mm-values | final-values-126-28mm | 0 | PASS | 1724.324 |
| group126-mount-values | final-values-126-mount | 0 | PASS | 1726.445 |
| group124-28mm-users | group124-28mm-users-r3 | 1 | CLOSED_KNOWN_P2 | 601.25 |
| group124-mount-users | group124-mount-users-r3 | 1 | CLOSED_KNOWN_P2 | 610.96 |
| group126-28mm-users | resume-users126-28mm | 1 | CLOSED_KNOWN_P2 | 667.124 |
| group126-28mm-other-users | group126-28mm-other-users | 0 | PASS | 529.77 |
| group126-mount-users | group126-mount-users | 1 | CLOSED_KNOWN_P2 | 612.28 |
| group126-mount-other-users | group126-mount-other-users | 0 | PASS | 523.6 |

每个 values 整组要求四个数值子项、L1、Default、返回光标共 7 项。数据文件路径及逐项检查在 regressions-final.json。

| 抽样 | 原始退出码 | 状态 |
| --- | --- | --- |
| resume-empty-28mm | 0 | PASS |
| resume-empty-mount | 0 | PASS |
| h07-parent-50mm | 0 | OBSERVED |
| resume-ownership | 0 | PASS_HOST_PREDICATES |
| resume-native-events | 0 | PASS_HOST |

列表首尾及数值端点的当前 M32R 菜单检查：PASS。

历史 r6 的前三组为 6/7 子项通过，只有 L1 旧期望失败；最后两组实际为返回 -15、各 2 项通过。历史返回码与新结果分开保留。

所有 observations=0 的旧结果均按错误文件、子项文件和标题记录重新归类，未将它解释为 0 个用例执行。
