修改后再采用

现有 1,530 项的质量结论成立，可以按已经验收的输入、起点和流程用于迭代。扩大到新起点时，`guarded_normal` 会返回条件门全部通过、整数训练目标却比原 exact 路径差的解。本次已复现，原始冻结模型也给出同一个 exact 对照。先补适用范围、逐流程质量检查和最终 exact 复核约定，再扩大切换；无需恢复参数逐位相同要求。

本次只审拟合和电脑预测。没有构建 DAT，没有访问存储卡、相机、网络或实时 `studio/`，也没有验证相机颜色。所有写入都在本目录，数值产物和冻结依赖恢复都在被忽略的 `artifacts/`。计算最多两个进程，实际 nice=15，数值库单线程。

## P1：条件门会放过退步的新起点

位置：`tools/fit_fast/guarded.py:41-68`、`tools/fit_fast/engine.py:184-195`。当前回退检查矩阵条件数和特征分解残差，没有检查最终整数候选相对 exact 的质量。

反例使用原目标索引 7、`L2_C_pre_fullfields`、158 个参数、`nfev=100`。目标、权重、边界、正则化和停止阈值不变；起点来自原声明的常规码域控制，加确定性扰动，并裁到原边界内。两边均按原规则，从求解终点、初始整数状态、父层整数状态中按训练目标取最小；两边最终都选 `refit`。不是直接拿未筛选的优化器终点比较。

| 指标 | 原 TRF/SVD | guarded_normal |
| --- | ---: | ---: |
| 最终整数训练目标 | 13.192236336279116 | 13.194836938535039 |
| 求解器连续 cost | 6.816269703212392 | 6.814754644446067 |
| 17 张照片相似度的中位数 | 74.19111580358127% | 73.99711980650515% |
| 残差评估次数 | 27 | 42 |
| 状态 | success，ftol 停止 | success，ftol 停止 |

训练退步 **0.002600602255922624**，参考归约噪声 **5.684341886080802e-14**。照片中位相似度下降 **0.19399599707611515 个百分点**。本项不是原完整矩阵的最终选中组合，因此不能把这个下降直接算成原 102 项选中组合门失败；它说明该配置被新流程选中时必须重查 0.1 pp 门。

普通分解的最小 `rcond(H)=2.7148827275247234e-7`，高于默认门槛 `sqrt(158×eps64)=1.873046918209871e-7`；最大后向残差只有 `5.2482208697897486e-15`，低于 `128×158×eps64`。没有回退。连续 cost 反而更低，因此用 `success`、连续 cost 或“不差于自己的整数初值”都不能发现这项相对 exact 的退步。

独立新进程重复得到同一差值。再用冻结的原始 `reference.Problem` 重跑，exact 的 θ 和整数预测与快速前向加 exact 路径完全相同。两边整数字段合法，`packed → unpack → predict` 也重建出同一反例，不是保存前后误差。

起点 SHA256 为 `bd4af80453b4667d63c48f3edf81d87b9ad9c2c6124b2dd93b3d79fefee5314f`，完整输入和状态在 `artifacts/solver_probes/neighbor-start-07-3-1/states.npz`。原声明控制起点的生成、两组固定 RNG 及边界裁切均保留在评审脚本中，没有调低条件门槛。

另一个新起点 `start-07-3` 的训练目标改善 0.0005207441、照片中位相似度改善 0.0492003 pp，但灰阶夹具的 `jump_gt_1_de00` 增加 1，`longest_identical_output_run` 增加 3。这也通过全部条件检查。数值可靠的分解仍会沿不同优化路径走到不同整数状态。

复现命令从仓库根执行，依次运行；仅写本评审的忽略目录：

```sh
env REVIEW_RUN=reproduce-training nice -n 15 /opt/homebrew/bin/python3 -I -B research/review_fit_fast_r2/probe_neighbors.py --case neighbor-start-07-3-1 --index 7 --replay-only --label reproduce-training
env REVIEW_RUN=reproduce-original nice -n 15 /opt/homebrew/bin/python3 -I -B research/review_fit_fast_r2/check_original_counterexample.py
env REVIEW_RUN=reproduce-scores nice -n 15 /opt/homebrew/bin/python3 -I -B research/review_fit_fast_r2/score_case.py --case neighbor-start-07-3-1 --index 7
env REVIEW_RUN=reproduce-fixture nice -n 15 /opt/homebrew/bin/python3 -I -B research/review_fit_fast_r2/score_case.py --case start-07-3 --index 7
```

证据：`artifacts/solver_probes/neighbor-start-07-3-1/result.json`、`artifacts/replays_neighbor-start-07-3-1.json`、`artifacts/counterexample_original_reference.json`、`artifacts/scored_neighbor-start-07-3-1.json`、`artifacts/scored_start-07-3.json`。

关闭条件：把“已通过条件门”与“该流程质量已验收”分开记录。保留当前已验收流程供快速迭代；新单元、目标、起点生成方式或模型配置先做本流程的成对质量检查。训练退步、夹具退步或最终 exact 确认失败时，受影响流程回到 exact。不得只把本例的 rcond 门槛往上挪一点就宣称所有新流程安全。最终候选复核方法见下文。

## P2：None 的逐项检查可以漏掉真实的绝对误差上升

位置：`tools/fit_fast/round2/quality_gate.py:260-265, 309-315, 144-162`。参考相似度中位数为 `None` 时，单项和选中组合/L1 的检查直接通过；ΔE00 只参加全体照片分布的中位数和 P95 检查。

在本轮真实的 26,010 行照片表上，保持训练和夹具不动，只对某个 `L1` 的 17 张照片同时提高 ΔE00 median、P95、max，仍有以下漏检：

| 目标索引 | 每张照片 ΔE00 增加 | 单项与 L1 门 | 全体 ΔE00 门 |
| --- | ---: | --- | --- |
| 30 | 0.1 | 通过 | 通过，统计量未变 |
| 38 | 0.1 | 通过 | 通过，统计量未变 |
| 46 | 0.5 | 通过 | 通过，统计量未变 |

这是评分表的定向变异，证明比较规则存在缺口；不声称当前求解器生成了这三份坏配方，也不声称伪造分数能通过 `--rebuild`。另有一个完整合成评分分布：17 张 `None` 照片全部增加 0.5 ΔE，其余样本不动，仍通过同一汇总函数。单个目标可以留在全体分位数之外。

当前交付的 90 个 `None` 拟合没有被这个缺口掩盖：它们的预测 NPZ 与参考逐文件 SHA 相同，1,530 条 `None` 照片行的 ΔE00 也相同。这里应补的是后续流程的规则，不能把当前 1,530 项判成失败。

关闭条件：保留 `None`，不要补成 0 或 100；对这类目标逐项检查绝对 ΔE00，在最终选中组合和 L1 上至少分别比较 17 张照片 median/P95 的中位数和 P95。按单元、目标和现有照片组独立判定，不能靠其他目标的改善抵消。若沿用当前“不退步”合同，容差只覆盖评分归约噪声。

```sh
env REVIEW_RUN=reproduce-none nice -n 15 /opt/homebrew/bin/python3 -I -B research/review_fit_fast_r2/probe_gate.py
```

证据：`artifacts/gate_negative_cases.json`，包含所有尝试过的增量与汇总统计。

## P2：recipe-redo 与 MOUNT 三曲线要按实际调用路径验收

位置：`tools/fit_fast/engine.py:193`、`tools/fit_fast/solver.py:171-174`。`guarded_normal` 只在 `Problem.solve()` 的 L2 及以上调用 `guarded.solve()`；L0/L1 仍走原 SVD。直接调用 `solver.least_squares()`，即使环境写着 `guarded_normal`，也会返回原 SciPy 求解器。

因此 recipe-redo 当前 L0/L1 的三条曲线不会因为这个名称就使用普通分解。其 `GuardedProblem` 的色相罚项优化器也不能拿本轮 1,530 项来代替本地验收。现有质量门还硬编码每项 17 张照片、每目标 30 个配置、索引 0:51；没有照片的 28mm 流程会明确报错，而不是已经通过了某种质量等价检查。

本次另测了 48 个合法扰动起点、24 个 recipe-redo 新训练输入的成对求解。48 项里 37 项未回退，训练退步 0 项；24 项里 20 项未回退，训练退步 0 项。48 项中发现的整数分叉促成了前面的相邻起点反例。24 项只借用 recipe-redo 的新 `x/want/sw`，保留 fit-fast 冻结模型并换入该目标的矩阵行；未运行 recipe-redo 整套色相罚项、插值筛选、552 B 编码和最终确认。因此它们是数值补充样本，不能当作 recipe-redo 全流程通过。

关闭条件：每个适配器保存实际 solver 分支、模型、起点策略和质量门的哈希。L0/L1 如继续走 exact，应写明实际路径；以后改成普通分解、接入新的色相罚项或新增横轴时，重测该调用路径。28mm 缺照片时明确记录合成验收范围，不能凑成旧的 17 张照片合同。

```sh
env REVIEW_RUN=reproduce-starts nice -n 15 /opt/homebrew/bin/python3 -I -B research/review_fit_fast_r2/probe_solver.py --kind starts --limit 48 --nfev 100
env REVIEW_RUN=reproduce-redo nice -n 15 /opt/homebrew/bin/python3 -I -B research/review_fit_fast_r2/probe_solver.py --kind redo --limit 24 --nfev 100
```

证据：`artifacts/solver_starts_summary.json`、`artifacts/solver_redo_summary.json`。

## P3：回退动作可靠，LAPACK 异常仍会直接报错

独立强制第 1 个因子、第 3 个因子的 rcond 失败，以及第 1 个因子的后向残差失败，均从同一原初值完整重跑 SVD，得到与 exact 相同的 θ 和 cost。缓存没有把已经走偏的状态带入重启。

`guarded.py:44` 的 `la.eigh()` 若抛 `LinAlgError`，外层只捕获 `UnreliableNormalMatrix`，不会重启 SVD。这是显式失败，不会静默交付坏解。若要承诺普通分解不可用时仍自动继续，应把这类分解失败也转入原初值 SVD 重启，且保留错误原因。

```sh
env REVIEW_RUN=reproduce-fallback nice -n 15 /opt/homebrew/bin/python3 -I -B research/review_fit_fast_r2/check_fallback.py
```

证据：`artifacts/fallback_checks.json`。

## P3：顶层复跑说明仍含已经禁止的四进程命令

`research/fit_fast_r1/REPRODUCE.md:13-21` 仍建议 `--workers 4`，而 `tools/fit_fast/run.py:119-121` 读取当前预算后会拒绝超过两个进程。第二轮专用说明 `research/fit_fast_r1/round2/REPRODUCE.md` 已写对。顶层应标为历史说明并明确指向第二轮文档，避免按本轮必读文件复制出无法运行的命令。本评审没有执行这些超预算命令。

## 已独立核实的交付范围

完整质量门通过，重建 1,530 个整数模型、67,624,200 个点、26,010 组逐照片分数和全部质量夹具。原训练目标、质量夹具和照片分数相同，训练噪声表也与原回执逐字节相同。全部 1,530 个预测 NPZ 与参考 SHA 相同。这里把字节相同作为这批产物的观测证据，没有改成新质量门。

参考的 3,060 个 JSON/NPZ 又对照第一轮封存的私有清单；清单哈希由 `round1_delivery.tar.gz` 中的 `seal.json` 锚定。没有只信任实施者写的通过字段。

新鲜的 90 项串行/双进程复跑通过，非耗时 JSON 与预测归档 SHA 一致，覆盖目标 0、36、44、三单元、worker 复用及冷依赖缓存。原 90 项记录的 JSON、NPZ 和输出顺序也独立重读通过，见 `verification.json` 和 `artifacts/parallel-independent/summary.json`。评审复跑调用原 `run.worker()`，仅重定位 I/O，由本目录协调器安排进程；原主 CLI 的 stdout 调度通过重读原日志核对，不把本目录协调器冒充原 CLI 调度测试。

本次没有重测速度。报告的原始 1.838880 来自原始参考入口与候选的 90 个不同配置、五次配对，全部超载，属于诊断；它不是 guarded_normal 相对已有快速 exact 前向的独立增益，也不是 1,530 项正式整轮倍数。

源码与数据冻结回执见 `INPUT_SHA256SUMS.initial`、`INPUT_SHA256SUMS`、`input_stability.json`。评审中另一个任务改过 `research/recipe_redo_r1/fit_one.py`，前后 SHA 已记入 `companion_drift.json`；本报告不批准这次伴随集成改动。主审的 fit-fast 源码、冻结参考和实际数值输入按清单独立核对。

最终反例复跑额外记录了实际读取的 52 个依赖，包括相机表、标定缓存和厂商模型依赖。与原轮次目标 7 的输入回执共有 44 个路径，43 个 SHA 相同；唯一不同的是本轮受审的 `tools/fit_fast/engine.py`。原输入回执自身也对照第一轮封存清单核验，数值数据差异没有混进反例。

## 最终进入 DAT 的 exact 复核应做什么

1. 冻结每个最终配方的单元、目标输入、训练与留出分组、基线 552 B、横轴、模型配置、约束、正则化、停止阈值、起点生成方式和全部源文件 SHA。显式选原 TRF/SVD 的 `exact`。不要在新目标上与旧目标的参考结果比较。
2. 由 exact 重跑原来声明的全部起点、父层/已有可行整数候选及全部横轴分支，保持原训练选择规则。把快速候选作为额外起点和可保留整数候选；原起点仍须执行。只从快速终点继续优化，不能作为独立参考对照。
3. 按训练加权整数 ΔE00 平方选择候选，比较量化、保存、解码后的状态。快速候选相对这些 exact 候选的最佳值若退步超过固定参考像素的归约噪声，最终使用通过质量检查的 exact 候选，并记录受影响流程需要回到 exact。不要用连续 `opt.cost`、success、nfev 或参数位相同替代这一检查。
4. 对最终明确列出的配方组合逐项比较真实留出。保留选中组合/L1 的 0.1 pp 门和本流程已有的单元、照片组/整场景规则；`None` 改走逐项目标的绝对 ΔE00 门。重建全部固定渐变、色相环及过拟合标记，不能用全体中位数盖住一个配方。求解达到预算上限时保留状态；不能因为调用了 exact 就把有限求解说成全局最优。
5. 从最终实际 552 B 记录解码重算训练、留出和夹具；核对整数域、三曲线开关、R/G/B 节点及模型对应关系。随后进入 DAT 构建时，解包检查 DAT 内对应记录与验收记录的字节/哈希。此处不要求 θ 或另一份配方逐位相同，要求写入 DAT 的就是验收过的记录。
6. 保存 fast/exact 配方、起点、选择理由、差值、状态、输入/源码/记录 SHA 和逐项验收回执。最终 exact 确认覆盖电脑模型与包装内容；上卡及相机响应继续按各自已有流程验收。

本反例追加了两次 exact 确认：从快速浮点终点和其整数状态继续求解，均找到训练目标 **13.159248137431392**，比原冷起点结果更低。这说明快速候选作为额外起点有价值，也说明最终应保留全部候选并重新验收。具体记录在 `artifacts/final_confirmation_probe.json`。

```sh
env REVIEW_RUN=reproduce-confirmation nice -n 15 /opt/homebrew/bin/python3 -I -B research/review_fit_fast_r2/check_confirmation.py
```

## SHA256SUMS

```text
ef020bb4d2d9db2d6551dc7dfdc7c3a1d5e009ac003a0e54773795773a1c9c19  tools/fit_fast/run.py
4820dab0496a6fe0f79e36ecbbb0f24a335131fa6fe6ee71443e42bac467f606  tools/fit_fast/solver.py
0e3d71330d10dad8b7e142371d4b35b715a2baab32d7762cc9967948e278057f  tools/fit_fast/guarded.py
9f874628a26372885e0570f57120761392f42f80f59bd5ee476458183940a255  tools/fit_fast/round2/quality_gate.py
b25b85b850e750842d1c41c46dd519f0876c52fe656cf65303095c2569281530  research/review_fit_fast_r2/round2/quality_independent-full.json
7c84c5faacf16e7ed5b16d53d4c9460f8c08d60fd4a5f5b77fcfdf28be2308ba  research/review_fit_fast_r2/verification.json
063aa533c426b15ee1f772199b8745fdbe5c1efc015f5599eb18d39322da42ad  research/review_fit_fast_r2/artifacts/solver_probes/neighbor-start-07-3-1/states.npz
12085d258fbbe2e31c4478281244f604eae3b47ee7224660922892f96f1b2dff  research/review_fit_fast_r2/artifacts/counterexample_original_reference.json
99e69e71a37fad0cf90d1ae564cd24114b546421cac0bdb3459f4d4b1085d5ee  research/review_fit_fast_r2/artifacts/scored_neighbor-start-07-3-1.json
34782441408f108e38ff96ad87c2b3735b3b8fcb15ce27cc44fc822e121ba7a7  research/review_fit_fast_r2/artifacts/gate_negative_cases.json
0db7522df8a893ac4a8acc9460fc44af744cf749f77771fcaaaa4c5b4649df30  research/review_fit_fast_r2/artifacts/parallel-independent/summary.json
```

完整清单 [SHA256SUMS](SHA256SUMS) 绑定本文、评审脚本、主审源码和忽略目录中的数值证据。清单自身的 SHA 单列在 [seal.json](seal.json)，避免自引用。全部路径相对仓库根。复跑会产生新证据，应另行封存。

```sh
shasum -a 256 -c research/review_fit_fast_r2/SHA256SUMS
```
