不可以上测试卡

gen 122 的两项 P1 在最终 gen 123 DAT 上已关闭。新增的当次 ERR 单行发布仍有一个 S 误写窗口，阻断本次放行；另有一个失去视图归属后的迟到重绘问题。

对象为 `firmware/package_v36_g123/SD_ROOT/GXRCE.DAT`，62,676 B，SHA256 `4ee9e6fefcd33619bcd763eacba9c56be4d3fb265b9e2ca0d73d49d59b8c1e64`。固定机身 SHA256 为 `50720c80696ca88f25dc25a85285acd0e0f19906e1d7da1dd404f6cc243f9008`。本轮仅审查 DAT 增量，没有操作相机、存储卡或网络，没有启动子代理。

## P0

未发现。

## P1

### P1-01：当次 ERR 单行仍在 inflight 内，重入方向键会绕过固定 resident 的保护并改写 S

位置为 `firmware/engine_v45_verify/candidate/containers/product/adapter.c:316`、`:317`、`:320`，`firmware/engine_v45_verify/candidate/engine_services/services.c:212`、`:218`，以及固定机身 `firmware/resident_v36/resident/hooks.c:31`、`:70`。

`keep_view()` 在引擎调用尚未返回时，把原八行列表或十一行面板改成一行，再调用原生重绘。面板的 `open` 和 `input_enabled` 已清零，但 resident 此时仍有 `inflight=1`。它的 H06/H08 提前返回保护只在原生行数等于 8 时跳过原生续程。一行 ERR 不满足这个条件，重入 H08 因而继续执行原生 Image setter。

复现使用最终 DAT、官方构造器和原生按键先确认配方 05；下一次方向键的首个 W 已在设备模型生效，但返回失败，随后所有补偿通信持续失败。在 ERR 的 `rv_native_draw` 入口安排第二个原生任务输入左或右方向键。CPU 模型 PSW.IE 为 1，没有手工写原生 UI，也没有替换 Image getter。

```sh
/usr/bin/python3 -I -B research/review_g123/lock_nested.py --cuts before_redraw --actions right left
```

四例均复现，列表和面板各两个方向。

- 重入前原生行数、光标、小圆点均为 1，`inflight=1`，锁定已发生。
- H08 记录为 `busy`，随后依次到达 `native_h08`、`native_setter_store` 和 `native_row_store`。
- 原生 PC `0x20268774` 把 `S+0x36e` 的 Image mode 从 1 写成 9。重入 RPC 为 0，外层返回后 mode 仍为 9。
- 原生 UI 的宿主直接写入数为 0，文件变更计数均为 0。这里的 S 变化来自实际执行的原生 CPU store。

影响是锁定后仍出现新的原生设置修改。mode 9 不符合该配方或标准 04 的设置，DAT 的永久锁存随后又阻止通信恢复，不能满足本轮要求的完整配方或纯 04 边界。把面板标记为停止输入，以及把三个行号都写回 1，均不足以阻止这条原生续程。

对照命令如下。

```sh
/usr/bin/python3 -I -B research/review_g123/lock_nested.py --generation 121 --cuts record_failure_return --actions right left
/usr/bin/python3 -I -B research/review_g123/lock_nested.py --cuts record_failure_return --actions right left
```

| 调度切点 | 原生行数 | 原生 H08 | S 的 Image mode |
| --- | --- | --- | --- |
| gen 121，列表锁定后、收尾前 | 8 | 被跳过 | 保持 1 |
| gen 123，列表锁定后、ERR 发布前 | 8 | 被跳过 | 保持 1 |
| gen 123，ERR 重绘入口 | 1 | 继续执行 | 左右方向均变成 9 |
| gen 121 和 gen 123，十一行面板锁定后、收尾前 | 11 | 两版均继续执行 | 左为 4，右为 5 |

最后一行是继承问题，不计作 gen 123 新增缺陷。新增回退是列表路径也失去了八行保护，且面板转成 ERR 后出现了同样的一行窗口。补充的 op 2 恢复 IRQ 后切点和原生行绘制切点也复现了方向键误写，记录保留在 `local/nested/`。

应先解决固定 resident 的八行保护与 DAT 单行发布之间的契约冲突，再把“锁定当次停止输入”记作通过。只有在外层调用结束后测试按键，覆盖不到这个窗口。

证据为 [列表向右](local/nested/50mm-list-before_redraw-right.json)、[列表向左](local/nested/50mm-list-before_redraw-left.json)、[面板向右](local/nested/50mm-panel-before_redraw-right.json)、[面板向左](local/nested/50mm-panel-before_redraw-left.json)、[gen 121 列表对照](local/nested/121-50mm-list-record_failure_return-right.json) 和 [最终重跑日志](local/lock-nested-confirmed-123-50mm.log)。命令因反例断言退出 1，这是候选行为失败。

## P2

### P2-01：op 3 恢复 IRQ 后仍能重绘已失去归属的 ERR 视图

位置为 `firmware/engine_v45_verify/candidate/engine_services/services.c:219`、`:220`，调用来自 `firmware/engine_v45_verify/candidate/containers/product/adapter.c:320`。

IRQ 内的旧归属核对和字段写入顺序正确。问题在它之后：`ui_list()` 恢复 IRQ，再直接用 `s->view_state` 调用原生重绘。最终编译码在 ELF `0x1958` 调用 IRQ 恢复，`0x195c` 继续执行，随后在 `0x1a10` 调用 `rv_native_draw`。

```sh
/usr/bin/python3 -I -B research/review_g123/lock_cutpoints.py --irq-enabled --cuts after_update_restore after_redraw_restore
```

在 op 3 的 IRQ 已恢复、PSW.IE 为 1 的续程切点，用第二个原生任务切到 activity 7，或通过原生状态函数切到 state 55。列表和面板共四例都继续调用旧 ERR 状态的原生重绘，并到达 `0x201ffb2c` 的行绘制流程，仍使用旧状态的 marker=cursor=1。

这四例的迟到 DAT UI 字段写入和被监视的原生 UI 字段写入确实都为 0。因此，原报告中的零字段写入结果不能证明没有迟到界面操作。这里确认的是旧 ERR 行仍进入原生绘制器；图形叶函数由宿主模型承接，未声称已观察到相机屏幕像素被覆盖。

op 3 的通用模式来自基线；gen 123 新增的锁定当次重绘也使用了它。本项没有宣称 gen 121 的其他重绘路径不存在同类窗口。相对 gen 121，新的 ERR 路径没有满足本轮“失去归属则不写当前界面”的要求。

op 2 恢复 IRQ 后立即失去归属的四个控制例均没有迟到重绘，说明 op 3 前的检查能挡住更早的切换。归属保证还需覆盖 op 3 恢复 IRQ 后到原生绘制入口的调度切点。

证据为 [列表切 activity](local/cutpoints-irq-enabled/50mm-list-after_redraw_restore-activity.json)、[列表切 state](local/cutpoints-irq-enabled/50mm-list-after_redraw_restore-state.json)、[面板切 activity](local/cutpoints-irq-enabled/50mm-panel-after_redraw_restore-activity.json)、[面板切 state](local/cutpoints-irq-enabled/50mm-panel-after_redraw_restore-state.json) 和 [汇总](evidence/lock-cutpoints-50mm-irq-enabled.json)。四个迟到重绘反例使该命令退出 1。

## 上轮反例和 H01 回退

全部结果来自最终 SHA，没有沿用阶段 A 的 DAT 运行结果。

| 检查 | 50mm | 28mm | MOUNT |
| --- | --- | --- | --- |
| 上轮九个反例 | 9/9 PASS | 9/9 PASS | 9/9 PASS |
| `partial_reset` 恢复配方 05 | RPC 805，W 253 | RPC 803，W 253 | RPC 803，W 253 |
| `deferred_half_recovered` | PASS | PASS | PASS |
| `deferred_confirm_busy`、`deferred_adj_busy` | PASS | PASS | PASS |
| `official_half.py --hook-trace` | PASS | PASS | PASS |
| 原有八个锁定案例 | 8/8 PASS | 8/8 PASS | 8/8 PASS |
| 正常已应用配方重开 | RPC 265，W 0 | RPC 264，W 0 | RPC 264，W 0 |

`partial_reset` 的 50mm gen 121 对照也重新运行，结果为 RPC 805、W 253，并恢复完整 05。撤销哨兵后的完整读回与基线一致。

所有 deferred 反例在 H01 核对失败时均回到七行，撤回引擎视图，不再显示未核对的八行配方。失败 H01 和紧接的按键均没有 W；整例记录中的 W 253 来自后续成功 H01 对配方 05 的恢复。完整原始半按由 `0x0d` 转为 `0x29`，没有调用 DAT，半按 RPC 为 0。

另在 50mm 上分别运行 gen 121 和 gen 123，比较持续通信失败、第七次读取切点失败、ready=0 三种条件，以及方向键、确认、ADJ 三个入口，共九对。原生行数、光标、小圆点、activity、overlay 和完整 S 摘要均一致。每对 H01 W=0、后续事件 W=0、RPC=0。[对照结果](evidence/h01-compare.json)支持第 2 项没有新增 W，也没有新增已应用配方显示。

50mm 的八个原生安全检查均通过，包含 H01 activity/state 切换、列表和面板 W 前失败保留、暖会话 ready 变化、原生设置核对及文件服务边界。H08/H06 的保留行为和 Shadow 标签没有回退。

普通 H07、ADJ、直接半按、释放和 DISP 后确认在外层锁定调用结束后没有调用原生 Image setter。完整原始半按的 S 变化与 gen 121 逐字节对照一致。这个结果限于调用结束后的退出，不能覆盖 P1-01 的 inflight 重入。

结果见 [上轮反例](local/cases/)、[原有锁定案例](local/lock-cases/)、[完整半按 50mm](local/official-half-50mm-with-hooks.json)、[完整半按 28mm](local/official-half-28mm-with-hooks.json)、[完整半按 MOUNT](local/official-half-mount-with-hooks.json)、[读回与回退计数](evidence/normal-and-fallback-counts.json) 和 [汇总](evidence/review-summary.json)。

## 源码、数据和编译码

两份源码 patch 均独立重新生成并逐字匹配。运行时差异仅涉及 adapter、core、core 声明、panel 标签和 UI list 服务这五个文件。构建入口、代号、路径与说明文件的辅助差异也在 patch 中。相对 gen 122 的六个改动源函数为 `keep_view`、`deferred_menu`、`eng_require_recheck`、`rebind_impl`、`validate_live` 和 `ui_list`。

最终 DAT 的 53,124 B 引擎段、`engine.bin` 和 ELF `.engine` 逐字一致，30 个编译源文件及工具摘要匹配。独立解包并重建三单元全部 48 个 552 B 条目，连同 CRC 字段、有效行、T、映射、配方记录和 metadata，均与 gen 121 相同。包内 29 个固定文件与 gen 120b 相同。

非引擎 DAT 差异也已分类：目录只移动四个指针，bank header 只变 generation 和 CRC，唯一绝对重定位仍指向 `rv_call`；其余 header 固定字段及映射、共享行池、metadata 相同。见 [源码与数据核对](evidence/delta-audit.json)。

二进制变化不能按“只有七段原始字节不同”理解。除六个源函数映射的七个编译区间，LTO 还改变了 `fresh`、`ig_init`、`ig_menu` 和 `rv_call` 四个载体。原因分别是 epoch helper 内联、Engine 清零长度从 2544 改为 2540、菜单 helper 内联，以及 `ui_list` 的 noinline 析出。相对 gen 122，113 个已有函数体在链接地址归一化后相同，另有 10 个已有函数体变化和一个析出的 `ui_list`。

`rv_call` 两处跳转表共 27 个目标逐项核对。两条 objdump unknown 都在表数据中，没有未分类的改动可执行字节。上述归一化清单和宿主执行不是全程序编译等价证明。

| 编译码类别 | 本轮结论 |
| --- | --- |
| 地址与长度 | 在增量边界内闭合。最终编译码完整读回生成器运行 889 例，覆盖三单元各通信失败切点、九行首中末字节差异及 T 差异。恢复叶函数和内联 settings 成功尾部是该单元检查的模型边界，实际恢复和原生设置另由原生案例检查。 |
| 文件操作 | 在增量边界内闭合。没有新增 storage 调用；原生服务 create、rename、delete、mark 返回 -12，只读句柄 write 返回 -10。实际会话 create、write、rename、delete、write_open 均为 0。没有把能力位缺失单独当作证明。 |
| 原生界面写入 | 未闭合。op 2 在 IRQ 内先核对旧归属再写新形状，早期失去归属的案例均无迟到字段写入；但 P1-01 的原生 S setter 和 P2-01 的迟到重绘仍可到达。 |
| 循环与内存 | 在增量边界内闭合。九行最大 96 B，条目末端 551≤552，导航仍为 16 轮，补偿仍为 4+2。新增描述符为 40 B，未新增循环。最大静态单帧 172 B，不代表相机 RTOS 栈高水位。 |

细目见 [编译边界复核](evidence/review-boundaries.json)、[编译读回 889 例](evidence/machine-verify.json)、[二进制变化清单](evidence/binary-inventory.json)。反汇编和原始字节均在 `local/`。

## 原始通信流、完整性与证据边界

直接使用未修改的 `research/g122_keep_list/audit_records.py`，没有传哨兵参数。第一次抽查本轮 24 个锁定记录及三个完整半按记录，去重后检查 18 条完整流。随后加入上轮全部反例和新的 S 误写记录，去重后检查 24 条完整流。两次均为三单元 PASS，故障摘要数为 0。X/V/W 地址、T 和半字边缘保留均通过。通信范围通过不代表 S setter 或视图归属正确，两个新问题另由原生执行轨迹证明。见 [首次复核](evidence/rpc-audit.json) 和 [扩展复核](evidence/rpc-audit-expanded.json)。

编排者给出的 7,620 项材料核对作为已知输入保留。本轮另冻结候选、基线、源码和工具材料，结束时逐项核对。`SHA256SUMS` 以仓库根为基准，覆盖冻结输入与本轮交付文件，排除清单自身。完整性和写入范围见 [integrity.json](integrity.json)。

本轮自写退出检查曾修正三个取证问题：原生任务前缀切走视图导致故障未命中；把原始键的复合返回结构误作带 `ok` 的单一结果；把原生半按任务对整个 S 的写入都判为错误。原始记录和日志保留，最终半按检查比较两版完整 S 变化，没有把这些工具失败记成候选缺陷。

已核实的是冻结产物、静态边界和原生机器码宿主模型中的行为。P1-01 使用第二个原生任务在 IRQ 可用的切点运行，P2-01 执行到原生行绘制边界。真实相机上的调度可达性、触发频率、曝光完成、物理屏幕像素和设置持久化均未验证。本轮没有重跑主矩阵或可选 24 命令，也没有扩大为色彩计算全域复审。

## 实际运行的命令

以下是主要验收和反例命令，执行记录含失败退出；完整逐次调用和重复次数见 [commands.jsonl](commands.jsonl) 与 [COMMANDS.md](COMMANDS.md)。所有 Python 均使用指定解释器。只在复审目录内复制并调整工具的输出路径，没有执行实现者的构建、打包或设备命令。

```sh
diskutil info /Volumes/Workspace
shasum -a 256 firmware/package_v36_g123/SD_ROOT/GXRCE.DAT
stat -f '%z %N' firmware/package_v36_g123/SD_ROOT/GXRCE.DAT
git status --short
/usr/bin/python3 -I -B research/review_g123/static_audit.py
/usr/bin/python3 -I -B research/review_g123/delta_audit.py
/usr/bin/python3 -I -B research/review_g123/binary_inventory.py
/usr/bin/python3 -I -B research/review_g123/machine_verify.py
/usr/bin/python3 -I -B research/review_g123/codegen_safety.py
/usr/bin/python3 -I -B research/review_g123/boundary_audit.py
/usr/bin/python3 -I -B research/review_g123/run_cases.py suite --unit 50mm
/usr/bin/python3 -I -B research/review_g123/run_cases.py suite --unit 28mm
/usr/bin/python3 -I -B research/review_g123/run_cases.py suite --unit mount
/usr/bin/python3 -I -B research/review_g123/run_cases.py partial_reset --generation 121 --unit 50mm
/usr/bin/python3 -I -B research/review_g123/official_half.py --hook-trace --unit 50mm
/usr/bin/python3 -I -B research/review_g123/official_half.py --hook-trace --unit 28mm
/usr/bin/python3 -I -B research/review_g123/official_half.py --hook-trace --unit mount
/usr/bin/python3 -I -B research/review_g123/locked_cases.py 50mm
/usr/bin/python3 -I -B research/review_g123/locked_cases.py 28mm
/usr/bin/python3 -I -B research/review_g123/locked_cases.py mount
/usr/bin/python3 -I -B research/review_g123/safety_cases.py
/usr/bin/python3 -I -B research/review_g123/h01_compare.py --generation 121
/usr/bin/python3 -I -B research/review_g123/h01_compare.py --generation 123
/usr/bin/python3 -I -B research/review_g123/lock_nested.py --cuts before_redraw --actions right left
/usr/bin/python3 -I -B research/review_g123/lock_nested.py --generation 121 --cuts record_failure_return --actions right left
/usr/bin/python3 -I -B research/review_g123/lock_nested.py --cuts record_failure_return --actions right left
/usr/bin/python3 -I -B research/review_g123/lock_cutpoints.py --irq-enabled --cuts after_update_restore after_redraw_restore
/usr/bin/python3 -I -B research/review_g123/lock_exits.py
/usr/bin/python3 -I -B research/review_g123/lock_exits.py --generation 121
/usr/bin/python3 -I -B research/review_g123/lock_exits.py --actions raw_half --record-tag final
/usr/bin/python3 -I -B research/review_g123/lock_exits.py --generation 121 --actions raw_half --record-tag final
/usr/bin/python3 -I -B research/g122_keep_list/audit_records.py --dat firmware/package_v36_g123/SD_ROOT/GXRCE.DAT --records research/review_g123/local/lock-cases research/review_g123/local/official-half-50mm-with-hooks.json research/review_g123/local/official-half-28mm-with-hooks.json research/review_g123/local/official-half-mount-with-hooks.json --output research/review_g123/evidence/rpc-audit.json --base-dir /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh
/usr/bin/python3 -I -B research/review_g123/summarize.py
/usr/bin/python3 -I -B research/review_g123/seal.py --seal
/usr/bin/python3 -I -B research/review_g123/seal.py --check
/usr/bin/shasum -a 256 -c research/review_g123/SHA256SUMS
```
