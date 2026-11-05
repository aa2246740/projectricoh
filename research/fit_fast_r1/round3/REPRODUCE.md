# fit-fast 第三轮复跑

从 `/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh` 执行。使用现有 Python 和依赖，不访问相机、SD 卡或网络。所有数值命令带 `-I -B`，实际计算进程 nice 15，数值库单线程。

先确认 Workspace 卷为已挂载、可写的 APFS，UUID 为 `14BE04EB-AF49-497E-B36A-B078B2F7C5E8`，并读取 `/Volumes/Workspace/AGENTS.md`。检查当前负载和已有计算，不停止其他任务。

```sh
diskutil info /Volumes/Workspace
uptime
ps -axo pid,ppid,ni,%cpu,etime,command | rg 'fit_fast/|look_ceiling_r1/.*py|spawn_main'
```

## 训练 Jacobian 诊断

诊断只取训练像素、训练目标、训练权重和常规码域控制起点。目标 50 缺少部分常规控制时，递归提升常规祖先；每项记录起点类型与 SHA。它不读保存的完整码域解，也不读留出评分。初始 Jacobian 统计不冒充整个优化轨迹的统计。

每个 tag 用新目录。计算中断后，`--resume` 只接受该诊断目录内已完整保存的 30 项目标统计，不恢复拟合结果。

```sh
env FIT_FAST_OUTPUT=/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/artifacts/downloads/fit-fast-r1/round3/diag-runtime nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/round3/diagnose.py --indices 0:51 --tag rerun-diagnosis
env FIT_FAST_OUTPUT=/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/artifacts/downloads/fit-fast-r1/round3/structure-runtime nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/round3/structure.py --indices 0:51 --tag rerun-structure
nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/round3/summarize.py --census artifacts/downloads/fit-fast-r1/round3/diagnosis/rerun-diagnosis/census.json --structure artifacts/downloads/fit-fast-r1/round3/structure/rerun-structure/summary.json --tag rerun-diagnosis
```

逐项秩、奇异值端点、列尺度、弱方向能量和分块统计保存在忽略目录；公开 JSON 只含分布统计和 SHA。

## 显式启用保守路径

默认仍为 `exact`。交付候选 `round3_direct` 在 L3/L4 从原初值直接使用参考 SVD，L2 沿用现行 guarded_normal，L0/L1 保留参考 SVD。全层 `round3_qr` 原型已在 540 项质量门中失败，不能沿用其先导 90 项的通过结论。仅 L3 用 QR 的 `round3_l3_qr` 也未通过整数训练门。QR 实验对完整 n×n 上三角矩阵做 SVD，不截断小奇异值；残差通过 Householder 反射投影。原初值、边界、正则化、TRF 接受步、停止阈值、整数候选选择、评分和保存规则不变。

单目标先跑 L0/L1，再在同一根目录跑完整码域。每次验收使用新输出目录，不能沿用已有完整码域解。

```sh
nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/run.py --indices 0 --keys L0,L1 --solver round3_direct --experimental-solvers --workers 2 --output artifacts/downloads/fit-fast-r1/round3/manual-rerun
nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/run.py --indices 0 --full-fields --solver round3_direct --experimental-solvers --workers 2 --output artifacts/downloads/fit-fast-r1/round3/manual-rerun
```

`--solver exact` 恢复第一轮快速前向加原 SVD。`--engine reference --solver exact` 使用冻结模型与原优化器。`round3_qr`、`round3_auto` 和 `round3_l3_qr` 是其他显式实验组合，不能沿用 `round3_direct` 的质量或测速结论。

## 全量配对与参考复核

协调器为每个目标实际重算 L0/L1 和 28 个完整码域组合，只复制原流程声明的常规控制起点，不复制完整码域最终解。两个模式按批次交替，均两个计算进程、nice 15。计时从 worker 池创建到加入结束，包含进程启动、两阶段拟合、整数选择、评分、夹具和保存，不含协调器复制和核对源码的时间。JSON 字段 `cli_wall_seconds` 保存的正是这段 worker 池墙钟。

```sh
env -u FIT_FAST_RCOND_FLOOR FIT_FAST_GUARD_FACTOR=normal nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/round3/bench.py --indices 0:51 --modes round3_direct,reference --workers 2 --chunk-size 6 --tag rerun-full-paired
```

配对负载门与第二轮相同：worker CPU/墙钟比例之比不超过 1.2；两侧起止 load1 均值之差不超过 `max(2, 较低值×20%)`；任一阶段边界 load1 大于 10 则排除。原始记录全部保留，不用 CPU 时间修正墙钟，不把子集倍数外推为全量倍数。

对三个单元各一个目标、共 90 个不同配置重复五次，用下列命令单独测原参考倍数或第二轮增量。它们各是 450 次拟合/侧，仍只有 90 个不同配置。

```sh
env -u FIT_FAST_RCOND_FLOOR FIT_FAST_GUARD_FACTOR=normal nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/round3/bench.py --indices 0,27,35 --modes reference,round3_direct --workers 2 --chunk-size 3 --repeats 5 --tag rerun-reference-subset
env -u FIT_FAST_RCOND_FLOOR FIT_FAST_GUARD_FACTOR=normal nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/round3/bench.py --indices 0,27,35 --modes guarded_normal,round3_direct --workers 2 --chunk-size 3 --repeats 5 --tag rerun-r2-subset
```

全量质量先与冻结结果比较，再与本轮新跑的冻结参考比较。`quality.py` 原样执行当前 `round2/quality_gate.py`，不更改门槛；退出后才逐字段列出所有整数变化。完整 1,530 项、26,010 张逐照片比较、`None` 绝对 ΔE00 门及保存产物重建都保留。

```sh
nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/round3/quality.py --sweep artifacts/downloads/fit-fast-r1/round3/runs/rerun-full-paired/summary.json --mode round3_direct --tag rerun-full-quality --rebuild
nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/round3/quality.py --sweep artifacts/downloads/fit-fast-r1/round3/runs/rerun-full-paired/summary.json --mode round3_direct --reference-sweep artifacts/downloads/fit-fast-r1/round3/runs/rerun-full-paired/summary.json --reference-mode reference --tag rerun-fresh-reference --rebuild
```

质量脚本只做验收，不参与拟合路径选择。整数差异写入 `artifacts/downloads/fit-fast-r1/round3/quality/<tag>/integer_changes.json`，逐条包含目标、配置、字段下标及两侧值。原质量门的详细训练和逐照片表继续保存在 `artifacts/downloads/fit-fast-r1/round2/quality/<tag>/`。

```sh
env FIT_FAST_OUTPUT=/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/artifacts/downloads/fit-fast-r1/round3/selfcheck-runtime nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/round3/selfcheck.py
```

## 4、6、8 进程扩展

仅在机器空闲且 load1≤5 时运行。先结束本任务的其他计算；不与质量重建或两进程拟合并发。每种并发均覆盖 51 个目标，使用新目录，按吞吐比较。入口和 worker 池会拒绝高负载启动，并在扩展期间 load1 上升到 5 以上时停止。未完整跑完的并发不报倍数。

```sh
nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/round3/bench.py --indices 0:51 --modes round3_direct --workers 2 --chunk-size 51 --idle-scaling --tag rerun-scale-2
nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/round3/bench.py --indices 0:51 --modes round3_direct --workers 4 --chunk-size 51 --idle-scaling --tag rerun-scale-4
nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/round3/bench.py --indices 0:51 --modes round3_direct --workers 6 --chunk-size 51 --idle-scaling --tag rerun-scale-6
nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/round3/bench.py --indices 0:51 --modes round3_direct --workers 8 --chunk-size 51 --idle-scaling --tag rerun-scale-8
```

本机为 M1 Pro，10 个物理核。扩展吞吐与同进程数的算法提速分别报告。

独立剖析另跑，不计入算法倍数：

```sh
nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/round3/profile.py --index 36 --solver round3_direct --tag rerun-profile
```

## 重现两个被拒绝的 QR 试验

以下均为失败试验，不作交付提速。每个 tag 使用新目录。第一组在 540 项中出现训练与夹具退步，第二组在 900 项中出现训练、单项留出与夹具退步。

```sh
env -u FIT_FAST_RCOND_FLOOR FIT_FAST_GUARD_FACTOR=normal nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/round3/bench.py --indices 0:18 --modes round3_qr --workers 2 --chunk-size 6 --tag rerun-rejected-fullqr
nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/round3/quality.py --sweep artifacts/downloads/fit-fast-r1/round3/runs/rerun-rejected-fullqr/summary.json --mode round3_qr --indices 0:18 --tag rerun-rejected-fullqr-quality --rebuild
env -u FIT_FAST_RCOND_FLOOR FIT_FAST_GUARD_FACTOR=normal nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/round3/bench.py --indices 0:30 --modes round3_l3_qr --workers 2 --chunk-size 6 --tag rerun-rejected-l3qr
nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/round3/quality.py --sweep artifacts/downloads/fit-fast-r1/round3/runs/rerun-rejected-l3qr/summary.json --mode round3_l3_qr --indices 0:30 --tag rerun-rejected-l3qr-quality --rebuild
```

训练反例的隐式/显式投影及参考精修对照，只读取训练数据和常规控制起点：

```sh
env FIT_FAST_OUTPUT=/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/artifacts/downloads/fit-fast-r1/round3/projection-runtime nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/round3/probe_projection.py --index 11 --tag rerun-projection
```

训练起点的提前结束计数可用交付的私有诊断脚本复跑；它不读取完整码域解或留出评分字段：

```sh
env FIT_FAST_SOLVER=exact FIT_FAST_OUTPUT=/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/artifacts/downloads/fit-fast-r1/round3/termination-runtime nice -n 15 /opt/homebrew/bin/python3 -I -B artifacts/downloads/fit-fast-r1/round3/termination_census.py
```

独立配对的负载门汇总使用交付私有脚本，要求同一组配置至少五次合格配对。它不接受不同子集混成五次，也不使用保存的 eligibility 标志替代实际负载重算：

```sh
nice -n 15 /opt/homebrew/bin/python3 -I -B artifacts/downloads/fit-fast-r1/round3/timing_summary.py --sweep artifacts/downloads/fit-fast-r1/round3/runs/rerun-r2-subset/summary.json --quality research/fit_fast_r1/round3/quality-rerun-full-quality.json --output research/fit_fast_r1/round3/timing-rerun.json
```

## 本轮实际产物与最后封存

本轮候选来自 `runs/direct-full`，覆盖 51 目标；新参考的前 12 目标来自 `runs/full-paired` 的 reference 批次，其余 39 目标来自 `runs/fresh-rest`。合并只建立索引，不构造计时配对；不能把这三次不同时间的运行拼成提速比。全部路径都相对 `artifacts/downloads/fit-fast-r1/round3/`。

以下脚本只读取已完成批次。每一侧必须恰好有 51 个不同目标、1,530 个主配置及预测归档；参考缺半批时会拒绝合并。`fresh-confirm` 已存在时改用新 tag，不覆盖旧质量回执。

```sh
nice -n 15 /opt/homebrew/bin/python3 -I -B artifacts/downloads/fit-fast-r1/round3/assemble_final.py
nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/round3/quality.py --sweep artifacts/downloads/fit-fast-r1/round3/final-sweep.json --mode round3_direct --reference-sweep artifacts/downloads/fit-fast-r1/round3/final-sweep.json --reference-mode reference --tag fresh-confirm --rebuild
```

本轮训练分块统计复用已封存的训练 Jacobian 诊断，不读取拟合后的完整码域结果。它另给出每块秩范围、零列数分布和 TRF 缩放坐标中最弱方向的能量分布。

```sh
nice -n 15 /opt/homebrew/bin/python3 -I -B artifacts/downloads/fit-fast-r1/round3/block_summary.py
```

最后停止本任务的数值计算，再生成报告和第三轮专用封存。封存器检查冻结参考 69 个源文件、第二轮锚定的 1,663 个输入、最终批次记录的输入哈希、源码快照、完整质量回执和所有私有文件的 Git 忽略规则。它不重写第一轮或第二轮的封存。源码补丁按第二轮已封存的 run.py、workers.py 加第三轮新文件生成，保留在私有目录，未做 Git 暂存或提交。

```sh
nice -n 15 /opt/homebrew/bin/python3 -I -B artifacts/downloads/fit-fast-r1/round3/all_saved_changes.py
nice -n 15 /opt/homebrew/bin/python3 -I -B artifacts/downloads/fit-fast-r1/round3/final_report.py --verdict 不能采用
nice -n 15 /opt/homebrew/bin/python3 -I -B artifacts/downloads/fit-fast-r1/round3/final_audit.py
nice -n 15 /opt/homebrew/bin/python3 -I -B artifacts/downloads/fit-fast-r1/round3/check_seal.py
```

第三轮时间预算从 2026-11-04 01:26:30 UTC 到 05:26:30 UTC。计时协调器在预算内停止启动新一侧，保留未成对的半批；正式算法倍数只由负载匹配和工作量完整性决定。

实际增量计时为 `runs/incremental-five/summary.json`，基线 guarded_normal，候选 round3_direct，固定索引 0、27、35。计划五次，05:17 UTC 后不再启动新一侧。最终有三次完整配对，每侧 270 次拟合；另有候选单侧 90 次拟合保留并排除。三次配对全部超载，原始比中位数 0.943、范围 0.898–0.969，不能据此声称正式提速或回归。完整质量已用本轮新参考复核；计时摘要绑定 `quality-fresh-confirm.json`。
