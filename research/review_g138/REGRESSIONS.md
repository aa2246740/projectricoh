# g138 完整 81 组回归

状态为 FINAL。

DAT SHA256：`88a4359b284ba5a9765a3dfb1177679ec4c4da0687d9f9a6fb3d31fe19acb02a`。

整组返回 0 且对应内层结果已写完，才记为 PASS。旧函数或旧页面约定的失败保留原退出码；当前替代检查单列，不能改写成原组 PASS。修正读取前的回执保存在 JSON 的 attempts 中。

已执行完整组 81/81。状态计数：PASS 69，STALE_LABEL_CONTRACT 6，STALE_RETIRED_FUNCTION 6。

| 家族 | 单元 | 组 | 返回码 | 秒 | 状态 | 回执及替代证据 |
| --- | --- | --- | ---: | ---: | --- | --- |
| 124 | 50mm | safety | 0 | 361.4 | PASS | [evidence/receipts/group124-50mm-safety-final-r2.json](evidence/receipts/group124-50mm-safety-final-r2.json) |
| 124 | 50mm | locked | 0 | 307.627 | PASS | [evidence/receipts/group124-50mm-locked-final-r2.json](evidence/receipts/group124-50mm-locked-final-r2.json) |
| 124 | 50mm | nested | 0 | 426.562 | PASS | [evidence/receipts/group124-50mm-nested.json](evidence/receipts/group124-50mm-nested.json) |
| 124 | 50mm | cutpoints | 0 | 238.459 | PASS | [evidence/receipts/group124-50mm-cutpoints-final-r2.json](evidence/receipts/group124-50mm-cutpoints-final-r2.json) |
| 124 | 50mm | exits | 0 | 940.934 | PASS | [evidence/receipts/group124-50mm-exits-final-r2.json](evidence/receipts/group124-50mm-exits-final-r2.json) |
| 124 | 50mm | transitions | 0 | 855.529 | PASS | [evidence/receipts/group124-50mm-transitions-final-r2.json](evidence/receipts/group124-50mm-transitions-final-r2.json) |
| 124 | 50mm | values | 0 | 1620.374 | PASS | [evidence/receipts/group124-50mm-values.json](evidence/receipts/group124-50mm-values.json) |
| 124 | 50mm | view-reentry | 0 | 1543.027 | PASS | [evidence/receipts/group124-50mm-view-reentry.json](evidence/receipts/group124-50mm-view-reentry.json) |
| 124 | 50mm | reentry-six | 0 | 1294.185 | PASS | [evidence/receipts/group124-50mm-reentry-six.json](evidence/receipts/group124-50mm-reentry-six.json) |
| 124 | 50mm | users | 0 | 363.576 | PASS | [evidence/receipts/group124-50mm-users.json](evidence/receipts/group124-50mm-users.json) |
| 124 | 50mm | project | 1 | 140.891 | STALE_RETIRED_FUNCTION | [evidence/receipts/group124-50mm-project.json](evidence/receipts/group124-50mm-project.json)；[HOST_C PASS](boundary-sweep.json) |
| 124 | 50mm | labels | 1 | 938.485 | STALE_LABEL_CONTRACT | [evidence/receipts/group124-50mm-labels.json](evidence/receipts/group124-50mm-labels.json)；[M32R_MODEL PASS_M32R](evidence/labels-current-50mm.json) |
| 124 | 50mm | half | 0 | 178.615 | PASS | [evidence/receipts/group124-50mm-half.json](evidence/receipts/group124-50mm-half.json) |
| 124 | 28mm | safety | 0 | 395.204 | PASS | [evidence/receipts/group124-28mm-safety.json](evidence/receipts/group124-28mm-safety.json) |
| 124 | 28mm | locked | 0 | 325.898 | PASS | [evidence/receipts/group124-28mm-locked.json](evidence/receipts/group124-28mm-locked.json) |
| 124 | 28mm | nested | 0 | 454.596 | PASS | [evidence/receipts/group124-28mm-nested.json](evidence/receipts/group124-28mm-nested.json) |
| 124 | 28mm | cutpoints | 0 | 260.132 | PASS | [evidence/receipts/group124-28mm-cutpoints.json](evidence/receipts/group124-28mm-cutpoints.json) |
| 124 | 28mm | exits | 0 | 992.244 | PASS | [evidence/receipts/group124-28mm-exits.json](evidence/receipts/group124-28mm-exits.json) |
| 124 | 28mm | transitions | 0 | 905.183 | PASS | [evidence/receipts/group124-28mm-transitions.json](evidence/receipts/group124-28mm-transitions.json) |
| 124 | 28mm | values | 0 | 1594.931 | PASS | [evidence/receipts/group124-28mm-values.json](evidence/receipts/group124-28mm-values.json) |
| 124 | 28mm | view-reentry | 0 | 743.835 | PASS | [evidence/receipts/group124-28mm-view-reentry.json](evidence/receipts/group124-28mm-view-reentry.json) |
| 124 | 28mm | reentry-six | 0 | 1219.234 | PASS | [evidence/receipts/group124-28mm-reentry-six.json](evidence/receipts/group124-28mm-reentry-six.json) |
| 124 | 28mm | users | 0 | 610.284 | PASS | [evidence/receipts/group124-28mm-users.json](evidence/receipts/group124-28mm-users.json) |
| 124 | 28mm | project | 1 | 130.948 | STALE_RETIRED_FUNCTION | [evidence/receipts/group124-28mm-project.json](evidence/receipts/group124-28mm-project.json)；[HOST_C PASS](boundary-sweep.json) |
| 124 | 28mm | labels | 1 | 155.194 | STALE_LABEL_CONTRACT | [evidence/receipts/group124-28mm-labels.json](evidence/receipts/group124-28mm-labels.json)；[M32R_MODEL PASS_M32R](evidence/labels-current-28mm.json) |
| 124 | 28mm | half | 0 | 158.278 | PASS | [evidence/receipts/group124-28mm-half.json](evidence/receipts/group124-28mm-half.json) |
| 124 | mount | safety | 0 | 366.6 | PASS | [evidence/receipts/group124-mount-safety.json](evidence/receipts/group124-mount-safety.json) |
| 124 | mount | locked | 0 | 313.456 | PASS | [evidence/receipts/group124-mount-locked.json](evidence/receipts/group124-mount-locked.json) |
| 124 | mount | nested | 0 | 433.348 | PASS | [evidence/receipts/group124-mount-nested.json](evidence/receipts/group124-mount-nested.json) |
| 124 | mount | cutpoints | 0 | 244.808 | PASS | [evidence/receipts/group124-mount-cutpoints.json](evidence/receipts/group124-mount-cutpoints.json) |
| 124 | mount | exits | 0 | 967.236 | PASS | [evidence/receipts/group124-mount-exits.json](evidence/receipts/group124-mount-exits.json) |
| 124 | mount | transitions | 0 | 861.473 | PASS | [evidence/receipts/group124-mount-transitions.json](evidence/receipts/group124-mount-transitions.json) |
| 124 | mount | values | 0 | 1608.462 | PASS | [evidence/receipts/group124-mount-values.json](evidence/receipts/group124-mount-values.json) |
| 124 | mount | view-reentry | 0 | 711.833 | PASS | [evidence/receipts/group124-mount-view-reentry.json](evidence/receipts/group124-mount-view-reentry.json) |
| 124 | mount | reentry-six | 0 | 1223.61 | PASS | [evidence/receipts/group124-mount-reentry-six.json](evidence/receipts/group124-mount-reentry-six.json) |
| 124 | mount | users | 0 | 612.663 | PASS | [evidence/receipts/group124-mount-users.json](evidence/receipts/group124-mount-users.json) |
| 124 | mount | project | 1 | 131.624 | STALE_RETIRED_FUNCTION | [evidence/receipts/group124-mount-project.json](evidence/receipts/group124-mount-project.json)；[HOST_C PASS](boundary-sweep.json) |
| 124 | mount | labels | 1 | 152.17 | STALE_LABEL_CONTRACT | [evidence/receipts/group124-mount-labels.json](evidence/receipts/group124-mount-labels.json)；[M32R_MODEL PASS_M32R](evidence/labels-current-mount.json) |
| 124 | mount | half | 0 | 158.629 | PASS | [evidence/receipts/group124-mount-half.json](evidence/receipts/group124-mount-half.json) |
| 126 | 50mm | safety | 0 | 375.527 | PASS | [evidence/receipts/group126-50mm-safety.json](evidence/receipts/group126-50mm-safety.json) |
| 126 | 50mm | locked | 0 | 315.864 | PASS | [evidence/receipts/group126-50mm-locked.json](evidence/receipts/group126-50mm-locked.json) |
| 126 | 50mm | nested | 0 | 433.995 | PASS | [evidence/receipts/group126-50mm-nested.json](evidence/receipts/group126-50mm-nested.json) |
| 126 | 50mm | cutpoints | 0 | 244.345 | PASS | [evidence/receipts/group126-50mm-cutpoints.json](evidence/receipts/group126-50mm-cutpoints.json) |
| 126 | 50mm | exits | 0 | 952.595 | PASS | [evidence/receipts/group126-50mm-exits.json](evidence/receipts/group126-50mm-exits.json) |
| 126 | 50mm | transitions | 0 | 868.434 | PASS | [evidence/receipts/group126-50mm-transitions.json](evidence/receipts/group126-50mm-transitions.json) |
| 126 | 50mm | values | 0 | 1599.98 | PASS | [evidence/receipts/group126-50mm-values.json](evidence/receipts/group126-50mm-values.json) |
| 126 | 50mm | view-reentry | 0 | 750.049 | PASS | [evidence/receipts/group126-50mm-view-reentry.json](evidence/receipts/group126-50mm-view-reentry.json) |
| 126 | 50mm | reentry-six | 0 | 1213.92 | PASS | [evidence/receipts/group126-50mm-reentry-six.json](evidence/receipts/group126-50mm-reentry-six.json) |
| 126 | 50mm | users | 0 | 607.459 | PASS | [evidence/receipts/group126-50mm-users.json](evidence/receipts/group126-50mm-users.json) |
| 126 | 50mm | project | 1 | 131.953 | STALE_RETIRED_FUNCTION | [evidence/receipts/group126-50mm-project.json](evidence/receipts/group126-50mm-project.json)；[HOST_C PASS](boundary-sweep.json) |
| 126 | 50mm | labels | 1 | 152.613 | STALE_LABEL_CONTRACT | [evidence/receipts/group126-50mm-labels.json](evidence/receipts/group126-50mm-labels.json)；[M32R_MODEL PASS_M32R](evidence/labels-current-50mm.json) |
| 126 | 50mm | half | 0 | 155.971 | PASS | [evidence/receipts/group126-50mm-half.json](evidence/receipts/group126-50mm-half.json) |
| 126 | 50mm | other-users | 0 | 537.272 | PASS | [evidence/receipts/group126-50mm-other-users.json](evidence/receipts/group126-50mm-other-users.json) |
| 126 | 28mm | safety | 0 | 371.905 | PASS | [evidence/receipts/group126-28mm-safety.json](evidence/receipts/group126-28mm-safety.json) |
| 126 | 28mm | locked | 0 | 310.03 | PASS | [evidence/receipts/group126-28mm-locked.json](evidence/receipts/group126-28mm-locked.json) |
| 126 | 28mm | nested | 0 | 434.445 | PASS | [evidence/receipts/group126-28mm-nested.json](evidence/receipts/group126-28mm-nested.json) |
| 126 | 28mm | cutpoints | 0 | 243.885 | PASS | [evidence/receipts/group126-28mm-cutpoints.json](evidence/receipts/group126-28mm-cutpoints.json) |
| 126 | 28mm | exits | 0 | 944.714 | PASS | [evidence/receipts/group126-28mm-exits.json](evidence/receipts/group126-28mm-exits.json) |
| 126 | 28mm | transitions | 0 | 871.26 | PASS | [evidence/receipts/group126-28mm-transitions.json](evidence/receipts/group126-28mm-transitions.json) |
| 126 | 28mm | values | 0 | 1579.016 | PASS | [evidence/receipts/group126-28mm-values.json](evidence/receipts/group126-28mm-values.json) |
| 126 | 28mm | view-reentry | 0 | 735.203 | PASS | [evidence/receipts/group126-28mm-view-reentry.json](evidence/receipts/group126-28mm-view-reentry.json) |
| 126 | 28mm | reentry-six | 0 | 1204.168 | PASS | [evidence/receipts/group126-28mm-reentry-six.json](evidence/receipts/group126-28mm-reentry-six.json) |
| 126 | 28mm | users | 0 | 608.713 | PASS | [evidence/receipts/group126-28mm-users.json](evidence/receipts/group126-28mm-users.json) |
| 126 | 28mm | project | 1 | 130.828 | STALE_RETIRED_FUNCTION | [evidence/receipts/group126-28mm-project.json](evidence/receipts/group126-28mm-project.json)；[HOST_C PASS](boundary-sweep.json) |
| 126 | 28mm | labels | 1 | 149.89 | STALE_LABEL_CONTRACT | [evidence/receipts/group126-28mm-labels.json](evidence/receipts/group126-28mm-labels.json)；[M32R_MODEL PASS_M32R](evidence/labels-current-28mm.json) |
| 126 | 28mm | half | 0 | 154.853 | PASS | [evidence/receipts/group126-28mm-half.json](evidence/receipts/group126-28mm-half.json) |
| 126 | 28mm | other-users | 0 | 524.272 | PASS | [evidence/receipts/group126-28mm-other-users.json](evidence/receipts/group126-28mm-other-users.json) |
| 126 | mount | safety | 0 | 359.563 | PASS | [evidence/receipts/group126-mount-safety.json](evidence/receipts/group126-mount-safety.json) |
| 126 | mount | locked | 0 | 305.833 | PASS | [evidence/receipts/group126-mount-locked.json](evidence/receipts/group126-mount-locked.json) |
| 126 | mount | nested | 0 | 425.923 | PASS | [evidence/receipts/group126-mount-nested.json](evidence/receipts/group126-mount-nested.json) |
| 126 | mount | cutpoints | 0 | 237.834 | PASS | [evidence/receipts/group126-mount-cutpoints.json](evidence/receipts/group126-mount-cutpoints.json) |
| 126 | mount | exits | 0 | 941.944 | PASS | [evidence/receipts/group126-mount-exits.json](evidence/receipts/group126-mount-exits.json) |
| 126 | mount | transitions | 0 | 849.279 | PASS | [evidence/receipts/group126-mount-transitions.json](evidence/receipts/group126-mount-transitions.json) |
| 126 | mount | values | 0 | 1568.756 | PASS | [evidence/receipts/group126-mount-values.json](evidence/receipts/group126-mount-values.json) |
| 126 | mount | view-reentry | 0 | 704.426 | PASS | [evidence/receipts/group126-mount-view-reentry.json](evidence/receipts/group126-mount-view-reentry.json) |
| 126 | mount | reentry-six | 0 | 1183.63 | PASS | [evidence/receipts/group126-mount-reentry-six.json](evidence/receipts/group126-mount-reentry-six.json) |
| 126 | mount | users | 0 | 601.14 | PASS | [evidence/receipts/group126-mount-users.json](evidence/receipts/group126-mount-users.json) |
| 126 | mount | project | 1 | 129.942 | STALE_RETIRED_FUNCTION | [evidence/receipts/group126-mount-project.json](evidence/receipts/group126-mount-project.json)；[HOST_C PASS](boundary-sweep.json) |
| 126 | mount | labels | 1 | 149.756 | STALE_LABEL_CONTRACT | [evidence/receipts/group126-mount-labels.json](evidence/receipts/group126-mount-labels.json)；[M32R_MODEL PASS_M32R](evidence/labels-current-mount.json) |
| 126 | mount | half | 0 | 154.386 | PASS | [evidence/receipts/group126-mount-half.json](evidence/receipts/group126-mount-half.json) |
| 126 | mount | other-users | 0 | 501.671 | PASS | [evidence/receipts/group126-mount-other-users.json](evidence/receipts/group126-mount-other-users.json) |

81 个槽位沿用原矩阵。两个家族的 values 和 transitions 槽位使用同一个当前运行器，保留各自执行回执，不称为两套独立实现。

复跑入口、读取修改和证据边界见 REVIEW.md、WRAPPER.md。
