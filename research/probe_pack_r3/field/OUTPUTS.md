交付文件位于当前 field 目录，原 probe3 包与照片只读。

| 文件 | 用途 |
| --- | --- |
| [QUICK_VERDICT.md](QUICK_VERDICT.md) | 首阶段重拍结论、八帧身份与分数。 |
| [FIELD_PROBE3.md](FIELD_PROBE3.md) | 完整响应、核形、彩块和模型边界。 |
| [HANDOFF_RECIPE_REDO.md](HANDOFF_RECIPE_REDO.md) | 配方重拟合接入和 OPEN。 |
| [全部文件绝对路径](local/OUTPUTS.json) | 列出本任务所有输出。 |
| [本地哈希清单](local/SHA256SUMS) | 绑定公开报告和全部本地证据。 |
| [主测 CSV](local/main-points.csv) | 312 行主测响应。 |
| [逐帧身份 CSV](local/frame-identities.csv) | 主测和三 ROI 身份、六模板最佳分数。 |
| [机器交接](local/recipe-redo-handoff.json) | 输入哈希、条件导数、包络及限制。 |
| [分量图](local/component-response.png) | 六个有符号响应的分量倍率。 |
| [核形图](local/kernel-response.png) | Y 与 RGB 反推的局部核。 |
| [彩块图](local/color-response.png) | 三类颜色的实测、预测和误差预算。 |
| [验收回执](local/acceptance.json) | 输入不变、忽略规则、参考复跑和清理。 |

复现脚本均在忽略的 local 内。按以下顺序运行，数值库线程数由脚本固定为 1。最多同时运行两个计算作业。

```sh
nice -n 15 studio/.venv/bin/python -I -B research/probe_pack_r3/field/local/analyze_probe3.py quick
nice -n 15 studio/.venv/bin/python -I -B research/probe_pack_r3/field/local/analyze_probe3.py rerun
nice -n 15 studio/.venv/bin/python -I -B research/probe_pack_r3/field/local/complete_probe3.py
nice -n 15 studio/.venv/bin/python -I -B research/probe_pack_r3/field/local/verify_and_budget.py
nice -n 15 studio/.venv/bin/python -I -B research/probe_pack_r3/field/local/deliver_probe3.py
nice -n 15 studio/.venv/bin/python -I -B research/probe_pack_r3/field/local/finalize_probe3.py
```

重跑前仍须核实 Workspace 卷的身份。最后的 finalize 清理本任务唯一 Scratch 并重写本地哈希清单，不清理其它任务目录。
