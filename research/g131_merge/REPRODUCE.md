# 重建并复核 gen 131

续跑 g131-merge-h07-r2 时先核对身份，不重建上一轮产物。冻结输入清单为 `inputs.json`；源码差异为 `source-change-vs-g129.patch`；上一轮 DAT 为 `5ca22d7b3115c9d7a4a556ee1fcb9105b7768e9fac4250873ea10689f1db3980`，89,556 B。

```sh
/usr/bin/sandbox-exec -f research/g131_merge/write-fence.sb /usr/bin/python3 -I -B research/g131_merge/verify_delivery.py
/usr/bin/sandbox-exec -f research/g131_merge/write-fence.sb /usr/bin/python3 -I -B research/g131_merge/verify_source.py
```

本轮开工还逐项核对了 28,614 个冻结输入、12 个改动函数正文、91 个未变源文件、完整源码差异与 ELF 哈希。身份结果和源文件哈希保存在 `evidence/resume-start.json`。任一身份变化即停止。

第 19 至 37 项全部重跑。第 24 项的旧残留不计结果。以下调用顺序执行后续队列，常规单项限制为 3,600 秒，阶段项为 7,200 秒。

```sh
/usr/bin/sandbox-exec -f research/g131_merge/write-fence.sb /usr/bin/python3 -I -B research/g131_merge/run_existing.py --queue research/g131_merge/queue.json --job-index 19
```

队列结束后先按文末命令复核通信，再运行 `resume_review.py`，它逐项检查全部 38 项、19 项续跑来源、7 项继承窗口及最终 DAT 绑定，并写入 `evidence/queue-complete.json`。`finalize.py` 会再调用该检查，生成完整结果表和以仓库根为基准的 SHA256SUMS。

```sh
/usr/bin/sandbox-exec -f research/g131_merge/write-fence.sb /usr/bin/python3 -I -B research/g131_merge/resume_review.py
```

在仓库根运行以下命令。系统围栏只允许写入本任务的三个目录，并拒绝网络。

```sh
/usr/bin/sandbox-exec -f research/g131_merge/write-fence.sb /usr/bin/python3 -I -B firmware/engine_v51_g131/candidate/build131.py
/usr/bin/sandbox-exec -f research/g131_merge/write-fence.sb /usr/bin/python3 -I -B research/g131_merge/package.py
/usr/bin/sandbox-exec -f research/g131_merge/write-fence.sb /usr/bin/python3 -I -B research/g131_merge/verify_delivery.py
/usr/bin/sandbox-exec -f research/g131_merge/write-fence.sb /usr/bin/python3 -I -B research/g131_merge/verify_source.py
```

先运行 50mm 的首个目标用例，再运行顺序队列。

```sh
/usr/bin/sandbox-exec -f research/g131_merge/write-fence.sb /usr/bin/python3 -I -B research/g131_merge/run_existing.py --timeout-seconds 3600 research/review_g126/layout_only.py
/usr/bin/sandbox-exec -f research/g131_merge/write-fence.sb /usr/bin/python3 -I -B research/g131_merge/run_existing.py --crc-implementation native --timeout-seconds 3600 research/review_g127/native_checks.py --case h07-parent --unit 50mm --crc-mode native
/usr/bin/sandbox-exec -f research/g131_merge/write-fence.sb /usr/bin/python3 -I -B research/g131_merge/run_existing.py --queue research/g131_merge/queue.json
```

队列依次运行目标切点、主机金标准、布局与编译码检查、继承窗口、三个单元的归属与冷重入检查、目标计算，以及 50mm 批组。任务在同一进程中切换，编译和执行保持顺序。

`preview-window` 的旧检查返回码原样保留。该用例允许继续记录后续项目。补充观察使用 `observe_window.py`，在最终 ELF 的 `rv_native_preview` 桥接入口改变模拟父视图，再统计原生预览入口和 S 写入。补充观察失败会停在当前队列项。

`capture_state.py` 在归属检查成功后建立 H01 的八行原生父视图，再复核重开；旧归属用例故意留下的七行非归属状态不作为 H01 的进入前提。它同时保存目标内存。`target_check.py` 读取这些内存和最终 DAT，逐项执行目标计算；目标 CRC 和整数辅助函数均走最终 M32R 指令。

队列结束后运行以下命令。

```sh
/usr/bin/sandbox-exec -f research/g131_merge/write-fence.sb /usr/bin/python3 -I -B research/g131_merge/verify_wrapper.py
/usr/bin/sandbox-exec -f research/g131_merge/write-fence.sb /usr/bin/python3 -I -B research/g131_merge/audit_communications.py
/usr/bin/sandbox-exec -f research/g131_merge/write-fence.sb /usr/bin/python3 -I -B research/g131_merge/collect.py
/usr/bin/sandbox-exec -f research/g131_merge/write-fence.sb /usr/bin/python3 -I -B research/g131_merge/finalize.py
```

`prepare.py` 记录首次复制与合并，只用于尚无 `engine_v51_g131` 的目录。常规重建从 `build131.py` 开始。

wrapper 继承 g130 的按名称或 generation 字段绑定与 CRC 选择。新增适配定位只读辅助模块、绑定目标编译器给出的状态字段、执行同会话后检查，并按队列顺序切换进程。它不整体替换整数。ASCII 上限仍为 126，旧检查的断言保持启用。

重跑会更新结果文件。只有检查都绑定当前 DAT 后，才运行 `finalize.py` 更新报告和 SHA256SUMS。完整 81 组回归交后续复审。

settings_cases 与批组的旧参考接口使用 `reference_v2.py` 适配十维旋钮值。其 3,430 点接口复核命令如下，旧比较断言保留。wrapper 两个版本的身份和范围保存在 `evidence/runner-revisions.json`。

```sh
/usr/bin/sandbox-exec -f research/g131_merge/write-fence.sb /usr/bin/python3 -I -B research/g131_merge/reference_v2.py
```


本轮时间盒续跑断点：第 32 项。先复核冻结输入、源码和 DAT 身份，再执行以下命令；未完成项的旧残留不算结果。

```sh
/usr/bin/sandbox-exec -f research/g131_merge/write-fence.sb /usr/bin/python3 -I -B research/g131_merge/run_existing.py --queue research/g131_merge/queue.json --job-index 32
```

队列结束后复核运行 audit_communications.py、collect.py、finalize.py。
