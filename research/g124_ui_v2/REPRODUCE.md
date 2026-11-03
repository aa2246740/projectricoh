# gen 124 主机复现

在仓库根执行。全部 Python 命令使用 macOS 自带解释器，不访问相机、卡或网络。原始字节、编译物和模拟运行输出只写本任务的 `local/`。

先核对冻结清单，再阅读报告：

```sh
/usr/bin/python3 -I -B research/g124_ui_v2/seal.py --check
```

隔离重建不改发布 DAT，结果必须与发布 SHA 相同：

```sh
/usr/bin/python3 -I -B research/g124_ui_v2/reproduce124.py
```

结果在 `firmware/engine_v46_ui/candidate/local/reproduce124/reproduction.json`。编译器、链接器和输入路径记录于各自的 `layout.json`。环境需要仓库现有的 M32R 工具链和本机 clang；没有安装步骤。

以下命令重新运行单元行为。把 `50mm` 分别替换为 `28mm` 和 `mount`。每个脚本直接运行，不受本次执行者三小时时间盒的剩余时长影响：

```sh
/usr/bin/python3 -I -B research/g124_ui_v2/ui_acceptance.py transitions --unit 50mm
/usr/bin/python3 -I -B research/g124_ui_v2/ui_acceptance.py values --unit 50mm
/usr/bin/python3 -I -B research/g124_ui_v2/run_cases.py suite --unit 50mm
/usr/bin/python3 -I -B research/g124_ui_v2/safety_cases.py --unit 50mm
/usr/bin/python3 -I -B research/g124_ui_v2/locked_cases.py 50mm
/usr/bin/python3 -I -B research/g124_ui_v2/lock_nested.py --unit 50mm --cuts record_failure_return after_update_restore before_redraw row_draw
/usr/bin/python3 -I -B research/g124_ui_v2/lock_cutpoints.py --unit 50mm --irq-enabled
/usr/bin/python3 -I -B research/g124_ui_v2/view_reentry.py --unit 50mm
/usr/bin/python3 -I -B research/g124_ui_v2/lock_exits.py --unit 50mm
/usr/bin/python3 -I -B research/g124_ui_v2/official_half.py --unit 50mm --hook-trace
/usr/bin/python3 -I -B research/g124_ui_v2/user_acceptance.py --unit 50mm
/usr/bin/python3 -I -B research/g124_ui_v2/project_boundary.py --unit 50mm
/usr/bin/python3 -I -B research/g124_ui_v2/label_acceptance.py --unit 50mm
```

用户变体由 `tool_acceptance.py` 生成，之后执行用户界面测试。它有 32 个合成条目；发布 DAT 仍为零条。纯算法检查比较旧版计算输出，未测试 knobs v2 r2。

```sh
/usr/bin/python3 -I -B research/g124_ui_v2/tool_acceptance.py
/usr/bin/python3 -I -B research/g124_ui_v2/algorithm_check.py
node research/ui_v2_design/selftest.js
/usr/bin/python3 -I -B research/g124_ui_v2/static_audit.py
/usr/bin/python3 -I -B research/g124_ui_v2/binary_inventory.py
/usr/bin/python3 -I -B research/g124_ui_v2/compiled_tables.py
/usr/bin/python3 -I -B research/g124_ui_v2/remaining_window.py
/usr/bin/python3 -I -B research/g124_ui_v2/memory_budget.py
/usr/bin/python3 -I -B research/g124_ui_v2/native_edges.py
/usr/bin/python3 -I -B research/g124_ui_v2/rpc_review.py
/usr/bin/python3 -I -B research/g124_ui_v2/codegen_safety.py
```

上面的重跑会改变证据文件，因此冻结清单之后会报变化；不要把重跑结果冒称为原冻结记录。发布前重新生成报告和清单：

```sh
/usr/bin/python3 -I -B research/g124_ui_v2/finalize.py
/usr/bin/python3 -I -B research/g124_ui_v2/seal.py
/usr/bin/python3 -I -B research/g124_ui_v2/seal.py --check
```

`run_unit.py` 是本轮有截止时刻的执行驱动，不是未来复审的入口。旧引擎目录中的继承脚本也不是 gen 124 验收入口。新旋钮的接入边界及尚未移植的内容见 `INTERFACE.md`。
