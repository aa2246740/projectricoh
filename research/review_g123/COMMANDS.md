实际执行的 Python 主入口，重复次数来自 commands.jsonl。失败退出保留在 local 日志中；FAIL 不自动等于候选缺陷，分类见 REVIEW.md。

| 次数 | 命令 |
| --- | --- |
| 1 | `/usr/bin/python3 -I -B research/review_g123/run_cases.py suite --unit 50mm` |
| 1 | `/usr/bin/python3 -I -B research/review_g123/run_cases.py suite --unit 28mm` |
| 1 | `/usr/bin/python3 -I -B research/review_g123/run_cases.py suite --unit mount` |
| 1 | `/usr/bin/python3 -I -B research/review_g123/static_audit.py` |
| 1 | `/usr/bin/python3 -I -B research/review_g123/machine_verify.py` |
| 2 | `/usr/bin/python3 -I -B research/review_g123/lock_exits.py` |
| 1 | `/usr/bin/python3 -I -B research/review_g123/official_half.py --hook-trace --unit 50mm` |
| 3 | `/usr/bin/python3 -I -B research/review_g123/delta_audit.py` |
| 1 | `/usr/bin/python3 -I -B research/review_g123/codegen_safety.py` |
| 1 | `/usr/bin/python3 -I -B research/review_g123/locked_cases.py 50mm` |
| 1 | `/usr/bin/python3 -I -B research/review_g123/locked_cases.py 28mm` |
| 1 | `/usr/bin/python3 -I -B research/review_g123/locked_cases.py mount` |
| 1 | `/usr/bin/python3 -I -B research/review_g123/lock_cutpoints.py` |
| 1 | `/usr/bin/python3 -I -B research/review_g123/run_cases.py partial_reset --generation 121 --unit 50mm` |
| 1 | `/usr/bin/python3 -I -B research/review_g123/official_half.py --hook-trace --unit 28mm` |
| 1 | `/usr/bin/python3 -I -B research/review_g123/official_half.py --hook-trace --unit mount` |
| 1 | `/usr/bin/python3 -I -B research/review_g123/safety_cases.py` |
| 4 | `/usr/bin/python3 -I -B research/review_g123/binary_inventory.py` |
| 1 | `/usr/bin/python3 -I -B research/review_g123/lock_cutpoints.py --irq-enabled --cuts after_update_restore after_redraw_restore` |
| 1 | `/usr/bin/python3 -I -B research/review_g123/lock_exits.py --generation 121` |
| 1 | `/usr/bin/python3 -I -B research/review_g123/lock_nested.py` |
| 1 | `/usr/bin/python3 -I -B research/review_g123/lock_nested.py --cuts after_update_restore row_draw` |
| 1 | `/usr/bin/python3 -I -B research/review_g123/lock_nested.py --generation 121 --cuts record_failure_return --actions right left` |
| 1 | `/usr/bin/python3 -I -B research/review_g123/lock_nested.py --cuts record_failure_return --actions right left` |
| 1 | `/usr/bin/python3 -I -B research/review_g123/lock_nested.py --cuts before_redraw --actions right left` |
| 1 | `/usr/bin/python3 -I -B research/review_g123/boundary_audit.py` |
| 1 | `/usr/bin/python3 -I -B research/review_g123/h01_compare.py --generation 121` |
| 1 | `/usr/bin/python3 -I -B research/review_g123/h01_compare.py --generation 123` |
| 1 | `/usr/bin/python3 -I -B research/review_g123/lock_exits.py --actions raw_half` |
| 1 | `/usr/bin/python3 -I -B research/review_g123/lock_exits.py --generation 121 --actions raw_half` |
| 1 | `/usr/bin/python3 -I -B research/review_g123/lock_exits.py --actions raw_half --record-tag final` |
| 1 | `/usr/bin/python3 -I -B research/review_g123/lock_exits.py --generation 121 --actions raw_half --record-tag final` |
| 1 | `/usr/bin/python3 -I -B research/review_g123/summarize.py` |
| 2 | `/usr/bin/python3 -I -B research/review_g123/seal.py --seal` |

另运行以下只读预检与原始流核器。完整 shell 初始化、文件读取和内联汇总在本轮工具记录中。没有运行任何构建、打包或设备入口。

```sh
diskutil info /Volumes/Workspace
shasum -a 256 firmware/package_v36_g123/SD_ROOT/GXRCE.DAT
stat -f '%z %N' firmware/package_v36_g123/SD_ROOT/GXRCE.DAT
git status --short
/usr/bin/python3 -I -B research/g122_keep_list/audit_records.py --dat firmware/package_v36_g123/SD_ROOT/GXRCE.DAT --records research/review_g123/local/lock-cases research/review_g123/local/official-half-50mm-with-hooks.json research/review_g123/local/official-half-28mm-with-hooks.json research/review_g123/local/official-half-mount-with-hooks.json --output research/review_g123/evidence/rpc-audit.json --base-dir /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh
/usr/bin/python3 -I -B research/g122_keep_list/audit_records.py --dat firmware/package_v36_g123/SD_ROOT/GXRCE.DAT --records research/review_g123/local/cases/123-*.json research/review_g123/local/lock-cases research/review_g123/local/official-half-50mm-with-hooks.json research/review_g123/local/official-half-28mm-with-hooks.json research/review_g123/local/official-half-mount-with-hooks.json research/review_g123/local/nested/50mm-list-before_redraw-right.json research/review_g123/local/nested/50mm-panel-before_redraw-right.json --output research/review_g123/evidence/rpc-audit-expanded.json --base-dir /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh
```
