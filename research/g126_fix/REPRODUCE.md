# gen 126 复现

从仓库根执行，Python 固定为 `/usr/bin/python3 -I -B`。本目录脚本把输出限制在本任务三个新目录；原有目录只读。没有相机、存储卡或网络步骤。

gen 124 的实际重建脚本是 `firmware/engine_v46_ui/candidate/reproduce124.py`。原文档 `research/g124_ui_v2/REPRODUCE.md:14` 给出的同目录路径不存在。该原文档保持只读。本任务用下列包装脚本复现 gen 124，输出写到新目录，避免原脚本在基线目录产生文件。

```sh
cd /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh
/usr/bin/python3 -I -B research/g126_fix/reproduce.py --generation 124
/usr/bin/python3 -I -B research/g126_fix/reproduce.py --generation 126
```

两次重建分别比较冻结 DAT、引擎、重定位及 48 槽位有效行，报告在 `evidence/rebuild-124.json` 和 `evidence/rebuild-126.json`。

首次发布的三个单元各四例包含无输入控制、七行阶段的两个方向键、八行发布后恢复 IRQ 的方向键。记录保留原生瞬时写入，成功条件是发布后和确认退出后的计划相符，以及预览服务调用时的计划相符。

```sh
/usr/bin/python3 -I -B research/g126_fix/cold_reentry.py --unit 50mm
/usr/bin/python3 -I -B research/g126_fix/cold_reentry.py --unit 28mm
/usr/bin/python3 -I -B research/g126_fix/cold_reentry.py --unit mount
/usr/bin/python3 -I -B research/g126_fix/cold_reentry.py --generation 124 --case before_publish --tag=-reference
/usr/bin/python3 -I -B research/g126_fix/cold_reentry.py --generation 121 --case before_publish --tag=-reference
```

三单元完整套件包含 gen 122 的九个反例、gen 123 的锁定退出和重入切点、七视图六键 210 例、逐屏矩阵、档位端点及 32 个只读用户条目。`batch.py` 调用的脚本复制自只读复审目录，改动包括本代路径、代号、中性名称和同一最终 DAT 的完成记录复用。原始输出在 `local/`，每个命令的退出码在 `commands.jsonl`。日志重名时脚本拒绝覆盖，复跑请换 `--tag`。

部分较长套件提前执行，原批次走到对应套件时只复用已完成且 SHA 相同的记录。同单元同套件的输出由主机文件锁串行写入，避免两个执行进程重复写文件；这不改变固件的锁定规则。需要重新执行已通过套件时，先将该套件的完成摘要移到本目录的 local 留存，再换日志标签。

```sh
/usr/bin/python3 -I -B research/g126_fix/tool_acceptance.py
/usr/bin/python3 -I -B research/g126_fix/mac_cli_rejections.py
/usr/bin/python3 -I -B research/g126_fix/batch.py --unit 50mm --tag=recheck
/usr/bin/python3 -I -B research/g126_fix/batch.py --unit 28mm --tag=recheck
/usr/bin/python3 -I -B research/g126_fix/batch.py --unit mount --tag=recheck
/usr/bin/python3 -I -B research/g126_fix/settings_cases.py --unit 50mm
/usr/bin/python3 -I -B research/g126_fix/settings_cases.py --unit 28mm
/usr/bin/python3 -I -B research/g126_fix/settings_cases.py --unit mount
/usr/bin/python3 -I -B research/g126_fix/cold_exit.py --unit 50mm
/usr/bin/python3 -I -B research/g126_fix/cold_exit.py --unit 28mm
/usr/bin/python3 -I -B research/g126_fix/cold_exit.py --unit mount
/usr/bin/python3 -I -B research/g126_fix/transition_discipline.py --unit 50mm --irq-enabled
/usr/bin/python3 -I -B research/g126_fix/transition_discipline.py --unit 28mm --irq-enabled
/usr/bin/python3 -I -B research/g126_fix/transition_discipline.py --unit mount --irq-enabled
```

设置补充案例用明确的外部设置模拟输入分别改变 Image mode、两条 WB 及三字段组合，再走原生发布、OK 或 ADJ。失败案例只在现有 settings 或 preview 服务边界返回失败；记录恢复失败当次的设置、退出方式及下一次打开。失败案例的文字观察不提前断言配方正确，完整计划在函数返回后单独核对。

```sh
/usr/bin/python3 -I -B research/g126_fix/static_audit.py
/usr/bin/python3 -I -B research/g126_fix/compiled_tables.py
/usr/bin/python3 -I -B research/g126_fix/binary_inventory.py
/usr/bin/python3 -I -B research/g126_fix/codegen_safety.py
/usr/bin/python3 -I -B research/g126_fix/native_edges.py
/usr/bin/python3 -I -B research/g126_fix/audit_rpc.py
/usr/bin/python3 -I -B research/g126_fix/finalize.py
shasum -a 256 -c research/g126_fix/SHA256SUMS
```

通信复核由未修改的 `research/g122_keep_list/audit_records.py` 执行，`finalize.py` 分开默认 DAT、用户变体和参考代的原始完整流，不把切点摘要当成完整通信流。`SD_ROOT` 指向同目录 `local/SD_ROOT`，30 个实际交付文件均放在 `local/`。哈希清单的路径以仓库根为基准。
