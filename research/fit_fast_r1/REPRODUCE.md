# 复跑方法

> 这是第一轮的历史说明。第二轮起每个任务最多两个计算进程，下文的 `--workers 4` 会被 `tools/fit_fast/run.py` 拒绝。现行命令见 [round2/REPRODUCE.md](round2/REPRODUCE.md)；`guarded_normal` 的适用范围和最终 exact 复核方法见 [复审报告](../review_fit_fast_r2/REVIEW.md)。

以下命令从 `/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh` 执行。使用本机已有的 `/opt/homebrew/bin/python3`；依赖版本见 `environment.json`。没有为本任务安装依赖。首次运行从只读输入归档恢复依赖，并在私有目录编译 C 动态库。

## 原入口切换

保留原入口的 `--indices`、`--nfev`、`--keys`、`--full-fields`、`--physical-asym` 参数，把脚本路径换成 `tools/fit_fast/run.py`。默认仍为一个计算进程，自动设为 nice 至少 15，数值库单线程。JSON/NPZ 的目录层级与数据结构沿用原实现。为遵守原研究目录的写入边界，默认结果根目录为 `artifacts/downloads/fit-fast-r1/runs/default/`。后续读取器若硬编码原 LOCAL 路径，需要一并指定这个新根目录。

```sh
nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/run.py --indices 0 --nfev 100
```

独立输出和四进程由新增参数指定。`--full-fields` 需要 L0/L1 父结果；下例先计算这两层，再计算完整码域。常规码域的已声明控制起点只读复制到输出中，完整码域最终解不会复制。

```sh
ps -axo pid,nice,%cpu,etime,command | rg 'look_ceiling_r1/.*\.py|recovery_run.py|record_run.py|fit_fast/.*\.py'
nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/run.py --indices 0:12 --keys L0,L1 --workers 4 --output artifacts/downloads/fit-fast-r1/runs/review
nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/run.py --indices 0:12 --full-fields --workers 4 --output artifacts/downloads/fit-fast-r1/runs/review
```

对 `12:27`、`27:39`、`39:51` 分别重复这两步。不要一次启动多个批次；原研究作业活跃时只用一个计算进程。入口会再次检查进程表并拒绝超出门槛的并行启动。四进程启动器按给定目标顺序输出日志。

输出存在时，入口保留原实现的跳过行为。计时必须用新的 tag/输出目录；不要把续跑结果作为完整新鲜拟合的耗时。实验求解器需要显式 `--experimental-solvers`，其结果不具备默认路径的验收结论。

## 冻结与完整数值检查

```sh
/opt/homebrew/bin/python3 -I -B tools/fit_fast/freeze.py
nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/check_equivalence.py --directions
nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/check_published.py
```

若冻结检查报告源码改变，先执行 `freeze.py --sync`，再重跑完整数值检查。检查使用固定参数和合成输入；逐元素差异采用无损稀疏记录，未列出的坐标全部为零。完整参数向量、差异及照片预测留在忽略目录，公开回执只含统计与哈希。

## 新鲜全轮计时

`bench_round.py` 为每个目标创建独立输出，先执行 L0/L1，再执行完整码域 28 项。每个子任务超时 1,500 秒。它不复制已有完整码域解；参数选择仍只看训练数据。每条命令须串行执行。tag 必须尚不存在。

```sh
nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/bench_round.py --indices 0:12 --modes reference --workers 3 --tag review-ref-a
nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/bench_round.py --indices 12:27 --modes reference --workers 3 --tag review-ref-b
nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/bench_round.py --indices 27:39 --modes reference --workers 3 --tag review-ref-c
nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/bench_round.py --indices 39:51 --modes reference --workers 3 --tag review-ref-d
nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/bench_round.py --indices 0:12 --modes exact --workers 4 --tag review-fast-a
nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/bench_round.py --indices 12:27 --modes exact --workers 4 --tag review-fast-b
nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/bench_round.py --indices 27:39 --modes exact --workers 4 --tag review-fast-c
nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/bench_round.py --indices 39:51 --modes exact --workers 4 --tag review-fast-d
```

负载随每段记录在公开回执中，完整进程表保存在私有批次目录。基准父进程的 nice=15，再次调用 `nice -n 15` 后子进程实际 nice=20，参考和快速版一致。全轮结果采用四段活动墙钟之和；段间等待不计入计算时间，也不把求解器累计秒数冒充墙钟。

五次交替完整单目标计时与汇总：

```sh
nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/bench_round.py --indices 0 --modes reference,exact --workers 1 --repeats 5 --tag review-paired
/opt/homebrew/bin/python3 -I -B tools/fit_fast/summarize.py --reference review-ref-a,review-ref-b,review-ref-c,review-ref-d --fast review-fast-a,review-fast-b,review-fast-c,review-fast-d --paired-tag review-paired
```

## 保存后验收与串并行

同一 `verify_fits.py` 调用可以传入多个根目录，跨目录拒绝重复结果，并要求完整项数。以下引用此次已完成的计时目录；新复跑时替换 tag。

```sh
nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/verify_fits.py --root artifacts/downloads/fit-fast-r1/bench/full-exact-a/r0-exact --root artifacts/downloads/fit-fast-r1/bench/full-exact-b/r0-exact --root artifacts/downloads/fit-fast-r1/bench/full-exact-c/r0-exact --root artifacts/downloads/fit-fast-r1/bench/full-exact-d/r0-exact --reference artifacts/downloads/fit-fast-r1/bench/full-ref-a-final/r0-reference --reference artifacts/downloads/fit-fast-r1/bench/full-ref-b2/r0-reference --reference artifacts/downloads/fit-fast-r1/bench/full-ref-c/r0-reference --reference artifacts/downloads/fit-fast-r1/bench/full-ref-d/r0-reference --expected-fits 1530 --retained-controls --require-exact-records --tag exact-full
nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/check_parallel.py --tag review-parallel
```

保存后检查包括整数码域、θ 重建整数状态、整数状态重建预测、全部评分和逐照片评分、质量夹具，以及参考拟合的目标函数和四种指定指标。串并行检查比较完整结果 JSON（仅排除耗时字段）、预测归档 SHA-256 和输出顺序。

## 常驻 worker 和算法实验

`bench_pool.py` 与真实入口使用同一个常驻 worker。它为每个目标实际计算 L0/L1 和完整码域 28 项，用全新的目录，不读旧完整码域解。最终精确重测分为以下四段，每段外层另设 1,200 秒超时；各段逐个执行。

```sh
nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/bench_pool.py --indices 0:12 --modes exact --workers 4 --tag review-pool-a
nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/bench_pool.py --indices 12:27 --modes exact --workers 4 --tag review-pool-b
nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/bench_pool.py --indices 27:39 --modes exact --workers 4 --tag review-pool-c
nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/bench_pool.py --indices 39:51 --modes exact --workers 4 --tag review-pool-d
```

实验模式只是重跑失败候选，不能替换默认模式的验收结论。直接入口要求 --experimental-solvers；专用 benchmark 按所选模式显式启用实验选项。下例完整计算两种 LM，各自新建目录并记录源码与负载。

```sh
nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/bench_pool.py --indices 0:51 --modes cached_lm2,cached_lm_end --workers 4 --tag review-lm
nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/bench_solve.py --index 4 --start daily --key L4_C_pre_Y_before_Rafter --modes reference,exact,cached_lm2,cached_lm_end --nfev 100 --repeats 5 --tag review-algorithm
```

后一个命令在同一进程里交替实际求解，不把多进程收益算入算法倍数。它只代表一个配置，不等同于整轮或该配置的最终整数候选选择。

以下命令独立重算失败候选原 27 项的全部预测、质量夹具和 17 张照片评分，并写入逐项留出对照。预期退出码为 1，代表等价失败；不要只看保存重建合法。

```sh
nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/verify_fits.py --root artifacts/downloads/fit-fast-r1/pool-bench/final-pool/r0-cached_lm2 --reference artifacts/downloads/fit-fast-r1/bench/full-ref-a-final/r0-reference --reference artifacts/downloads/fit-fast-r1/bench/full-ref-b2/r0-reference --indices 0:27 --expected-fits 810 --require-integer-predictions --report-quality-differences --tag review-lm2
nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/check_parallel.py --indices 0,35,43,29,1,36,44,45 --nfev 10 --solver exact --tag review-pool-parallel
nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/check_score_cache.py
```

串并行检查的整数一致性只证明调度不改变该模式的结果，不能证明实验 LM 与参考拟合等价。八个目标使四个 worker 至少重用一次，默认在并行阶段前清空本任务依赖缓存，验证并发首次恢复。

常驻进程的输入回执含此前目标的已读输入。check_inputs.py 的 --allow-process-superset 仍要求参考的全部必要输入存在且 SHA 一致，并校验回执中每个额外输入的实时 SHA；仅允许增加历史 provenance，不允许缺失或替换必要输入。独立进程旧轮次继续用默认严格集合相等检查。

完整单目标剖析包含导入、两阶段实际求解、评分和保存；它有 profiler 开销，不用于速度倍数：

```sh
nice -n 15 /opt/homebrew/bin/python3 -I -B tools/fit_fast/profile_round.py --index 0 --solver cached_lm2 --tag review-profile
```

## 输出封存

全部数值任务完成后运行 `seal.py`。它逐文件调用只读的 `git check-ignore -v`，生成源码、回执和私有输出的哈希清单。清理仅限本任务 Scratch，且有活跃 fit-fast 数值任务时拒绝清理。

```sh
/opt/homebrew/bin/python3 -I -B tools/fit_fast/seal.py --clean
```

清理后再次运行拟合会重新创建本任务 Scratch。不要据此把后续运行视为仍处于本次封存状态。

封存后可以只读核对哈希，以下操作不导入运行时、不重建 Scratch：

```sh
shasum -a 256 -c research/fit_fast_r1/SHA256SUMS
shasum -a 256 -c artifacts/downloads/fit-fast-r1/SHA256SUMS
```
