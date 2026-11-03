在仓库根执行。所有 Python 均使用 `/usr/bin/python3 -I -B`，无需网络或设备。先核对交付清单；重跑会改动证据文件，应先保存本轮清单及记录。

```sh
/usr/bin/shasum -a 256 -c research/g123_fix/SHA256SUMS
```

构建使用本机已有的 M32R 工具链。`implement.py` 从 gen 122 和 gen 121 生成最终源码，包含锁定显示增量；已核对重新生成的源码逐字节相同。以下步骤只写本任务三个输出目录。

```sh
/usr/bin/python3 -I -B research/g123_fix/implement.py
/usr/bin/python3 -I -B firmware/engine_v45_verify/candidate/build123.py
/usr/bin/python3 -I -B research/g123_fix/build_package.py
/usr/bin/python3 -I -B research/g123_fix/check_artifacts.py
/usr/bin/python3 -I -B research/g123_fix/static_audit.py
/usr/bin/python3 -I -B research/g123_fix/codegen_safety.py
```

验收分两阶段，不能混用 SHA。阶段 A 的两个 P1、完整主矩阵、官方半按、H01 条件与入口组合、W 前保留视图已在 `0a687c3427bb23125cd8b88855cedcf80639ce625152931ab2251e382325fabe` 上通过。记录、执行脚本和该阶段 DAT/ELF 冻结在 `local/p1-verified/`；其中 `SNAPSHOT_SHA256SUMS` 以仓库根为基准。

最终 DAT 是 `4ee9e6fefcd33619bcd763eacba9c56be4d3fb265b9e2ca0d73d49d59b8c1e64`。按补充裁决，仅重跑三个单元各八项锁定相关检查。可按单元重跑；每条命令顺序运行本地主机案例，不启动 Agent。

```sh
/usr/bin/python3 -I -B research/g123_fix/locked_cases.py 50mm
/usr/bin/python3 -I -B research/g123_fix/locked_cases.py 28mm
/usr/bin/python3 -I -B research/g123_fix/locked_cases.py mount
```

本轮实际使用 `run_batch.py locked` 并发执行三个单元，该批次有固定截止时间。以后重跑应使用上面的单元命令，或在新的审查输出目录设定自己的截止时间。不要覆盖冻结记录后仍沿用旧清单。

最终增量的完整通信日志只从 `local/lock-cases` 读取。直接复用编排者的核器，不传哨兵参数。

```sh
/usr/bin/python3 -I -B research/g123_fix/rpc_review.py all
/usr/bin/python3 -I -B research/g123_fix/check_auditor.py
/usr/bin/python3 -I -B research/g123_fix/final_open_counts.py
```

`rpc_review.py all` 的实际展开命令记录在 `evidence/rpc-review-all-command.json`，调用入口为 `research/g122_keep_list/audit_records.py`，显式传入最终 DAT、`local/lock-cases` 与输出路径。

阶段 A 的主矩阵、复审反例、H01 各入口分别与冻结 DAT 复核。以下包装命令传入 `local/p1-verified/artifact/GXRCE.DAT`，不会将旧日志冒充最终 SHA 的记录。

```sh
/usr/bin/python3 -I -B research/g123_fix/rpc_review.py matrix
/usr/bin/python3 -I -B research/g123_fix/rpc_review.py counterexamples
/usr/bin/python3 -I -B research/g123_fix/rpc_review.py h01
```

阶段 A 的执行命令在该阶段的 `*-commands.json` 和日志中。入口为 `run_batch.py required/official/first/keep/safety/matrix`。完整官方半按入口是 `official_half.py --hook-trace --unit <单元>`。889 项 M32R 读生成器检查也属于冻结阶段，其核心源码在最终增量中不变；本轮没有将该项写成最终 SHA 的重新执行。

两行探针只运行 `local/probe` 内保留的探针 DAT 和 ELF。它证明现有服务与固定构造器把光标和小圆点写成同一行，因此最终候选采用裁决允许的原生列表回退。

```sh
/usr/bin/python3 -I -B research/g123_fix/probe_short_list.py
```

可选 24 条命令的每单元结果见 `optional-24-commands.tsv`。为优先完成 P1 和锁定增量而停止，其余命令未记 PASS。

`finalize.py` 核对冻结阶段清单、最终增量源码差异与锁定结果，再汇总报告和根路径清单。它不会执行未跑的验收，也不会把未完成命令算作通过。

```sh
/usr/bin/python3 -I -B research/g123_fix/finalize.py
/usr/bin/shasum -a 256 -c research/g123_fix/SHA256SUMS
```
