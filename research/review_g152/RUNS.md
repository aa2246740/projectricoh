本轮作业均经 offline.sb，nice=10；时间来自运行器的 monotonic 计时。

| 模块与参数 | 结果 | 秒 | 运行回执 |
| --- | --- | ---: | --- |
| `equivalence` | PASS | 3.091 | [runs/equivalence-18535.json](runs/equivalence-18535.json) |
| `format_checks` | PASS | 1.374 | [runs/format_checks-18665.json](runs/format_checks-18665.json) |
| `control_parity` | PASS | 3.016 | [runs/control_parity-18697.json](runs/control_parity-18697.json) |
| `unverified_checks --unit mount --original late` | PASS | 262.030 | [runs/unverified_checks-18731.json](runs/unverified_checks-18731.json) |
| `unverified_checks --unit 50mm --original late` | PASS | 263.645 | [runs/unverified_checks-18929.json](runs/unverified_checks-18929.json) |
| `independent_cases snapshot-race --unit mount --kind T` | PASS | 157.005 | [runs/independent_cases-22111.json](runs/independent_cases-22111.json) |
| `independent_cases snapshot-race --unit 50mm --kind rows` | PASS | 157.790 | [runs/independent_cases-22112.json](runs/independent_cases-22112.json) |
| `independent_cases static` | FAIL | 0.275 | [runs/independent_cases-23674.json](runs/independent_cases-23674.json) |
| `independent_cases after-refusal --unit mount` | FAIL | 302.405 | [runs/independent_cases-23791.json](runs/independent_cases-23791.json) |
| `independent_cases after-refusal --unit 50mm` | FAIL | 306.122 | [runs/independent_cases-23792.json](runs/independent_cases-23792.json) |
| `independent_cases static` | PASS | 1.047 | [runs/independent_cases-26964.json](runs/independent_cases-26964.json) |
| `independent_cases reject --unit mount` | FAIL | 0.975 | [runs/independent_cases-27288.json](runs/independent_cases-27288.json) |
| `independent_cases after-refusal-stock --unit mount` | FAIL | 293.680 | [runs/independent_cases-27289.json](runs/independent_cases-27289.json) |
| `identity_checks --unit mount` | PASS | 887.748 | [runs/identity_checks-29928.json](runs/identity_checks-29928.json) |
| `independent_cases reject --unit mount` | PASS | 775.121 | [runs/independent_cases-29927.json](runs/independent_cases-29927.json) |
| `independent_cases static` | PASS | 1.147 | [runs/independent_cases-36515.json](runs/independent_cases-36515.json) |
| `independent_cases isolated-area --unit mount` | FAIL | 0.078 | [runs/independent_cases-36564.json](runs/independent_cases-36564.json) |
| `ui_checks rows49 --unit mount` | PASS | 408.669 | [runs/ui_checks-36563.json](runs/ui_checks-36563.json) |
| `independent_cases isolated-area --unit mount` | PASS | 100.823 | [runs/independent_cases-36797.json](runs/independent_cases-36797.json) |
| `independent_cases text12 --unit mount` | PASS | 220.049 | [runs/independent_cases-40288.json](runs/independent_cases-40288.json) |
| `ui_checks empty --unit mount` | PASS | 229.461 | [runs/ui_checks-40292.json](runs/ui_checks-40292.json) |
| `independent_cases static` | PASS | 1.000 | [runs/independent_cases-42773.json](runs/independent_cases-42773.json) |
| `independent_cases bw --unit mount` | PASS | 250.927 | [runs/independent_cases-42821.json](runs/independent_cases-42821.json) |
| `apply_checks --unit 50mm` | PASS | 504.330 | [runs/apply_checks-42822.json](runs/apply_checks-42822.json) |
| `t0_late_checks --unit mount` | PASS | 272.490 | [runs/t0_late_checks-46615.json](runs/t0_late_checks-46615.json) |
| `ui_checks error --unit mount` | PASS | 227.570 | [runs/ui_checks-46616.json](runs/ui_checks-46616.json) |
| `knob_checks refusal --unit 50mm` | PASS | 247.471 | [runs/knob_checks-49190.json](runs/knob_checks-49190.json) |
| `unverified_checks --unit mount --transition effect-other-base --timing capture-invalid` | PASS | 139.931 | [runs/unverified_checks-49191.json](runs/unverified_checks-49191.json) |

作业累计 6019.272 秒，最大并发 2，收尾存活测试数 0。
