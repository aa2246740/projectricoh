# 重跑第二轮拟合和质量门

从 `/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh` 执行命令。使用已有的 `/opt/homebrew/bin/python3`，不安装依赖。

当前预算为两个计算进程、nice=15。`tools/fit_fast/round2/resource_budget.json` 保存操作者的限制，入口和进程池拒绝超过预算的启动。开始重计算前读取进程表。

```sh
ps -axo pid,ppid,ni,%cpu,etime,command | rg 'fit_fast/|look_ceiling_r1/.*py|recovery_run.py|record_run.py'
```

## 运行保守的条件回退方案

每个 tag 使用新目录。以下命令顺序计算 51 个目标，每批六个目标，每批最多 1,200 秒。协调器只推进有界批次，完整工作量为 1,530 项。每批的拟合进程退出后，一个验收进程检查逐项退步，随后才启动下一批。

```sh
env -u FIT_FAST_RCOND_FLOOR FIT_FAST_GUARD_FACTOR=normal nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/round2/paired_round.py --indices 0:51 --modes guarded_normal --workers 2 --chunk-size 6 --batch-timeout 1200 --quality-check --tag review-guard
```

每个目标实际重算 L0、L1 和 28 个完整码域配置。它只读复制原研究声明的常规码域控制起点，不读取完整码域最终解。候选参数选择仍由原入口执行，照片留出不参与拟合。

若一批出现训练、逐目标照片或质量夹具退步，协调器保留该批并停止候选版本。单批汇总统计下降不单独触发停止，最终汇总门在完整 1,530 项上判断。

## 验收完整保存产物

拟合协调器结束后执行质量门。`--rebuild` 从整数状态重建预测、照片评分和质量夹具，并检查码域、θ 到保存状态的对应关系。脚本拒绝缺项、重复项和保存格式变化。

```sh
env FIT_FAST_OUTPUT=/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/artifacts/downloads/fit-fast-r1/round2/evaluation nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/round2/quality_gate.py --sweep research/fit_fast_r1/round2/paired_review-guard.json --mode guarded_normal --tag review-guard-full --rebuild
```

逐项 JSON、CSV、逐照片对照和每项噪声数据保存在 `artifacts/downloads/fit-fast-r1/round2/quality/review-guard-full/`。公开回执只含计数、汇总评分与哈希。

训练噪声只来自固定参考整数像素的重复评分及不同求和顺序。容差为参考保存值、NumPy、逆序、`math.fsum` 和 `longdouble` 归约之间最大差的八倍，并设八 ULP 下限。优化路径差异不算数值噪声。

照片表保留每项 17 张照片。51 个目标逐个检查其选中组合及 L1，分别对照参考同一组合，照片相似度中位数允许下降 0.1 个百分点。全部 1,530 项均报告，单项相似度中位数最多下降 1 个百分点，全体中位数不得下降。汇总中位数和 P95 的权威指标是逐照片 ΔE00 评分，均不得上升；相似度 P95 仅报告。

没有最终组合清单时，验收表按训练整数目标最低选中组合，同分沿用原枚举顺序。`--selection-map` 可指定已冻结的索引到组合键映射。留出照片不参与选型。参考本来不可定义的相似度继续保留 `None`，双侧可定义性必须相同，全部照片的 ΔE00 仍参与汇总。

质量表检查渐变负亮度步数、超过 1 和 2 ΔE00 的整数跳变、最长相同输出段、最大相邻码跳变、色相反转和过拟合标记。现有失败的计数不能增加，原本通过的检查不能新增失败。过拟合同时检查保存入口和原报告的定义。

## 保留精确后端

直接入口仍默认使用精确后端。条件回退目前保持显式实验标记，完整质量门结论见本轮报告。

```sh
nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/run.py --indices 0 --nfev 100 --solver exact --output artifacts/downloads/fit-fast-r1/runs/review-exact
```

若使用多进程，给入口增加 `--workers 2`。完整码域先计算 L0、L1，再以相同输出根目录执行 `--full-fields`，步骤与第一轮相同。

## 比较同核数速度

以下命令交替计算两个版本。两边使用相同进程数、实际 nice=15、全新目录和相同工作量。各批的边界负载、每个 worker 的阶段负载、CPU 时间和源码副本都写入回执。

```sh
env -u FIT_FAST_RCOND_FLOOR FIT_FAST_GUARD_FACTOR=normal nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/round2/paired_round.py --indices 0:51 --modes reference,guarded_normal --workers 2 --chunk-size 6 --batch-timeout 1200 --tag review-paired
```

负载匹配规则预先固定：两边累计 worker CPU 与墙钟的比例相差不超过 20%；起止一分钟负载的均值相差不超过较低值的 20%，最小绝对允许差为 2。任一采样点的一分钟负载超过 10，则该对仅作诊断。回执保留所有轮次，不修正墙钟、不删除较慢记录，也不把子集倍数外推为整轮倍数。

误停恢复后的交付测速使用三个单元各一个目标、共 90 个不同配置，交替五次。以下命令重现这个子集，独立质量重建在每个拟合池退出后才运行。每侧累计 450 次拟合，不能称为 450 个不同配置。

```sh
env -u FIT_FAST_RCOND_FLOOR FIT_FAST_GUARD_FACTOR=normal nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/round2/paired_round.py --indices 0,36,44 --modes guarded_normal,reference --workers 2 --chunk-size 3 --repeats 5 --batch-timeout 1200 --quality-check --quality-rebuild --tag review-paired-subset
```

## 检查串并行并封存

所有拟合和验收进程退出后执行串并行检查。三个目标覆盖三个单元，并使两个 worker 发生复用。冷缓存检查会重建本任务的依赖快照。

```sh
/opt/homebrew/bin/python3 -I -B tools/fit_fast/round2/final_parallel.py --tag review-round2-parallel
```

这个不导入数值库的协调器保持 nice=0；检查器内部把实际拟合子进程设为 nice=15。不要在外层再加 nice，以免两次累加成 20。每次使用新标签，保留旧证据。外层最多等待 1,000 秒，超时仅终止它自己创建的进程组。

如需重跑单目标调用剖析，在其他数值进程退出后执行以下命令。它使用一个 nice=15 进程，导入运行时起最多 240 秒；Profiler 时长不用于速度倍数。

```sh
env FIT_FAST_TIMEOUT=240 nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/round2/profile_guard.py --index 36 --tag review-profile
```

封存命令扫描嵌套的公开回执、逐文件检查 Git 忽略规则并生成哈希清单。清理仅限本任务 Scratch。不要把封存命令的 stdout 重定向到文件，`seal.json` 是正式回执。

封存前可重跑合格产物和冻结参考的字节检查，以及计时范围的合成反例：

```sh
nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/round2/check_qualified_outputs.py
nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/round2/check_reference_outputs.py
nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/round2/check_timing_rules.py
```

```sh
nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/round2/seal_round2.py --clean
```

只读校验不会导入拟合运行时，也不会重建 Scratch。

```sh
shasum -a 256 -c research/fit_fast_r1/SHA256SUMS
shasum -a 256 -c artifacts/downloads/fit-fast-r1/SHA256SUMS
```
