# 复跑与交接

本轮只生成电脑研究记录和本地配方库，不生成 DAT。官方 Acros 的独立交接见 [ACROS.md](ACROS.md)，交接后不因胶片库对照而改动那三条记录。

仓库根为 `/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh`。使用已有 `studio/.venv/bin/python`，不安装依赖、不联网。读取照片或固件的 Python 均加 `-I -B`，数值作业由 `common.py` 在导入数值库前检查 load1、拿任务计算租约，并把数学库限制为单线程。父进程已是 nice 15，子进程继承，不能再叠加 `nice -n 15`。

统一拟合队列只补缺项。每次恢复用新 tag，保留此前失败与结果。先确认没有旧调度器仍在派发，不能同时运行历史的 `library_batch.py`、`style_batch.py` 或 `pipeline.py`。

```sh
nice -n 15 studio/.venv/bin/python -I -B research/film_looks_r2/master.py \
  --tag new-unique-tag --max-workers 6 --confirm-admitted-weighting
```

队列按 `uptime` 的 load1 动态派发，大于 10 不开新计算，5–10 最多两个，小于 5 最多六个。已经运行的任务自然收尾。所有拟合起点和连续解都留在 `local/fits`；fast 迭代为 guarded_normal，入选两侧再做 reference exact。达到迭代预算不算收敛，最终报告保留这些起点数。

主库固定从黑盒与结构代理两条未加权路线中按整数训练损失选记录。敏感色加权只作独立对照，照片预算可以触发它的额外 exact 复核，但不会改变主配方选择。首轮混入加权主线的汇总与库清单保存在 `local/history/weighted-primary-first-pass/`；最终归档为 `full_library/unweighted_primary_v1/`，发布脚本会拒绝把加权对照当成主配方。

统一队列完成后，独立读取两侧最终 552 字节，逐点重放、重算分数，再刷新灰轴幅度和结构对照诊断。它不重新挑参数。

```sh
nice -n 15 studio/.venv/bin/python -I -B research/film_looks_r2/verify_batch.py \
  --tag final-replay-new-tag --max-workers 6
```

最后汇总、导出、核算整组容量并写报告。以下均为标准库脚本；报告的 `--final` 会拒绝缺少 60 份独立重放、48 份风格对照或完整配方导出的状态。

```sh
nice -n 15 /usr/bin/python3 -I -B research/film_looks_r2/summarize.py --require-complete
nice -n 15 /usr/bin/python3 -I -B research/film_looks_r2/export.py --require-complete
nice -n 15 /usr/bin/python3 -I -B research/film_looks_r2/capacity.py --require-complete
nice -n 15 /usr/bin/python3 -I -B research/film_looks_r2/write_report.py --final
nice -n 15 /usr/bin/python3 -I -B research/film_looks_r2/chart.py --require-complete
nice -n 15 /usr/bin/python3 -I -B research/film_looks_r2/seal.py
nice -n 15 /usr/bin/python3 -I -B research/film_looks_r2/seal.py --verify
```

`export.py` 不覆盖不同 SHA 的已导出配方。若改变目标、模型、参数域或算法，应另建版本目录，保留本轮原始证据。`summary.json` 会用统一阈值重分类历史风格回执，不依赖旧回执中的布尔结论。

核心交接文件都在 Git 忽略的 `local/`：

- `full_library_manifest.json` 包含 20 片 × 3 单元的最终 SHA、552 字节记录、来源/许可、flags、成绩与量化准入状态。
- `studio_installation_contract.json` 记录实际 base/flags 依赖、六个解析反例、04 pin、身份/状态及行池校验要求。
- `record_costs.json` 记录单条 Look 替换/新增及满配替换 06 的净字节；`capacity.json` 记录整组去重和七槽 flags 冲突。
- `analysis/`、`style_analysis/`、`final_verification/` 保留逐照片、分支、质量和独立重放证据。
- `weighted_controls_summary.json` 与 `weighted_verification/` 单独保留加权对照的 128 分支及颜色预算。只对 `summary.json` 中 `meets_color_and_overall_budget=true` 的单元调用 `weighting.py --film ORDINAL --unit UNIT`；通过者导出到 `full_library/weighted_optional_v1/`，不覆盖未加权主库。
- `comparison.html` 只含聚合成绩，可离线打开；对话展示须先经 HTML preview，再 render，无须服务器。
- `promote_shared_parser_probe.json` 是 18 个现有 Look 改用 flags7、R/G/B 共用一条曲线的解析正例；曲线池没有新增行。`locked_shared_flags7_handoff.json` 另记录最终锁定候选的前向/主机微调等价，属于候选 payload，不是 g158 DAT 或相机验收。

历史编码纠正见 `flags_repair.json` 与 `history/c100-enable-first-failure/`。旧模板从原厂 04 继承了关闭 C100 的 bit0，现已固定为共享 1、满配 7。纠正只改变 flags/Look 身份，不改任一拟合行、参数或起点，3305340 个 RGB 点逐值不变；原 exact 数值回执因此保留复用。最终重放队列还会编译已冻结的纯 C `kv_math.c`，检查默认 552 字节不变、影调微调后 C100 色度保留，并给出关闭 bit0 会回退原厂色度的反例。该主机数学检查不是相机执行。

候选尚无新实拍。模型通过、记录有效、DAT 有效、Studio 可替换和相机应用正确是不同验收层次。

`freeze.json` 记录研究开始时复制的输入与源码；运行时还使用既有 `recipe_redo_r1/local/source` 归档及原厂 C040 固件来源。最终封存另在 `external_runtime_sources.json` 记录这些外部依赖的哈希，`seal.py --verify` 会一并检查。该清单是最终状态记录，不冒充开始时已复制的额外冻结。

加权逐条复核完成后，运行 `nice -n 15 /usr/bin/python3 -I -B research/film_looks_r2/collect_weighting.py` 收集回执，再刷新 `write_report.py --final` 和封存。汇总脚本会拒绝主配方、分析或 C 数学二进制已变化的旧回执。未来重新计算须先把 `local/task_deadline.json` 更新为该次研究获准的截止时刻；本轮预算到期后数值入口会主动停止。
