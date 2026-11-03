不可以上测试卡

首次发布前的七行窗口仍可让重入方向键写原生 Image mode，随后八行界面指向 04，却保留 mode=5。这项继承 P1 阻断本轮放行。gen 123 的一行 ERR 问题在已发布八行视图上未再出现，不能替代首次发布过渡检查。

对象为 `firmware/package_v36_g124/SD_ROOT/GXRCE.DAT`，58,196 B，SHA256 `ebf07faa3c5b8dcec411da7f7217fb58488adafb942045999bd2cdf7ce98f803`。只换 DAT，固定机身为 v3.6，SHA256 `50720c80696ca88f25dc25a85285acd0e0f19906e1d7da1dd404f6cc243f9008`。结论针对 B 测试卡的主机复审，不表示相机、存储卡、LCD、曝光完成或实体断电已经验收。本轮没有访问设备、存储卡或网络，没有启动子代理。

## P0

未发现。

## P1

### P1-01：首次发布前仍为七行，重入 H08 可写 Image mode，随后八行 04 不再核对该状态

位置为 `firmware/engine_v46_ui/candidate/containers/product/adapter.c:472`、`:474`，`firmware/engine_v46_ui/candidate/containers/product/src/firmware/engine/core/eng_core.c:566`，以及固定 resident `firmware/resident_v36/resident/hooks.c:28`、`:31`、`:70`。八行实际写入在 `firmware/engine_v46_ui/candidate/engine_services/services.c:220`。

从干净模型启动，经官方构造器首次进入 Image 列表。在 DAT `list_bind` 入口、八行尚未发布时，用另一个原生任务执行方向键。此时 activity=8、state=56、inflight=1、PSW.IE=1，但原生仍是七行，`ui_block=0`、`ui_restore[0]=0`。

```sh
/usr/bin/python3 -I -B research/review_g124/cold_reentry.py --tag=-recheck
/usr/bin/python3 -I -B research/review_g124/cold_reentry.py --generation 121 --tag=-baseline-recheck
```

命令在复现 Image 写入时按断言返回 1。无输入控制、八行发布后恢复 IRQ 的控制例另列。

最终 DAT 的向下键反例经过 `native_h08`、`0x20268768` 和 `0x20268774`。resident 将 H08 记为 busy，但 `early()` 因行数不是 8 而没有跳过原生续程。PC `0x20268774` 把 `S+0x36e` 从 1 写成 5，另有 `0x20268798` 的同值写入。重入 RPC 为 0，host UI writes 为 0，Image getter 没有 stub。

外层继续发布八行，光标和圆点均为 4，Image mode 却仍为 5；标准 04 要求的 mode 是 1。九行和 T 仍匹配 04，失败点是原生模式。因此这不是图形闪烁或仅合成 WB 输入的差异。根因是首次会话 `committed=0` 且 `recheck=0`，`validate_live()` 在 `eng_core.c:566` 直接返回成功。确认退出也不核对该模式，模式 5 保留，确认 RPC 为 0。

向上键的最终 mode 仍为 1，但同样经过 Image setter 并写 `S+0x36e`，也不满足不得触及的要求。该例最终配方比较成功不能代替零写入检查。

无重入控制保持 mode=1、八行、光标 4。将同一方向键移到首次八行发布后、恢复 IRQ 的续程，原生 setter 被跳过，mode 保持 1。此前通过的 210 例全部从已经发布的八行视图开始，覆盖不到首次发布前这个七行切点。

gen 121 的首次发布前向下键也留下 mode=5，向上键也有同值写入。这是继承缺陷，不是 gen 124 新增回退；本轮明确要求检查发布过渡及完整配方或纯 04，故仍阻断放行。该反例独立执行的是 50mm，没有声称在相机或另外两单元上实测。

影响是首次界面能在未锁定、未报警的状态下指向 04，但原生 Image mode 与 04 不同，并可确认退出。需先处理首次发布前的原生输入和最终状态核对，再复跑该反例。只在已发布八行的入口增加检查不足以关闭本项。

证据见 [独立核查汇总](evidence/cold-publication-verified.json)、[最终 DAT 向下键](local/cold-reentry-final/124-50mm-before_publish-right.json)、[同值写入](local/cold-reentry-final/124-50mm-before_publish-left.json)、[八行后的控制](local/cold-reentry-final/124-50mm-after_publish_restore-right.json) 和 [gen 121 原始对照](local/cold-reentry/121-50mm-before_publish-right.json)。


## P2

### P2-01：最后归属检查之后仍可绘制旧视图，并写原生绘制全局变量

位置为 `firmware/engine_v46_ui/candidate/engine_services/services.c:223`、`:224`，桥接目标见 `firmware/engine_v46_ui/candidate/engine_services/bridges.S:41`。原监视范围 `research/g124_ui_v2/ui_trace_scope.py:2` 没有包含 `0x205d4f64`。

复现时，在最终检查已通过的 `rv_native_draw` 入口，以第二个原生任务切到 activity 7 或 state 55，再恢复旧任务。列表和数值页各两例均继续进入旧行绘制器 `0x201ffb2c`。最终机器码的原生 PC `0x201fd392` 还向 `0x205d4f64` 写入 32 位的 0。该变量由原生绘制前缀从当前描述项的 `+8` 取值，供后续行号映射使用。

```sh
/usr/bin/python3 -I -B research/review_g124/window_consequences.py
/usr/bin/python3 -I -B research/review_g124/window_consequences.py --generation 121
/usr/bin/python3 -I -B research/review_g124/native_draw_audit.py
```

影响是旧页绘制仍可能覆盖新页，且不能把结果描述成“只有像素操作”或“零原生状态写入”。本轮八个对照例没有迟到的 S 写入、Image setter、当前菜单光标或行数写入。图形叶函数仍由模型承接，没有观察实体 LCD。

gen 121 的四个同类切点也发生同一个原生全局写入和旧行绘制。这里没有发现相对 gen 121 新增的设置误写。gen 124 新加的恢复 IRQ 后归属复查挡住了更早的切换；最后检查到绘制之间仍非原子。此项保留为继承限制，不按 gen 123 的 S 误写 P1 处理。

证据见 [两代原生写入对照](evidence/native-draw-consequences.json)、[原始逐次记录](local/window-consequences/) 和 [正确大端反汇编](local/native-draw-prefix.disasm)。

### P2-02：主机复现文档中的重建路径不存在

位置为 `research/g124_ui_v2/REPRODUCE.md:14`。按文档执行下列命令，解释器返回 2，报 `No such file or directory`。

```sh
/usr/bin/python3 -I -B research/g124_ui_v2/reproduce124.py
```

实际脚本位于 `firmware/engine_v46_ui/candidate/reproduce124.py`。影响是文档中的隔离重建步骤无法直接复跑，未改变发布 DAT。本轮使用 [rebuild_exact.py](rebuild_exact.py) 将服务编译、引擎编译和完整打包全部导向本目录 `local/`，所得 DAT、引擎、重定位和 48 槽位有效行均与冻结候选逐字相同。

证据见 [原命令失败日志](local/documented-rebuild-path.log)、[隔离重建结果](evidence/rebuild-exact.json) 和 [输出路径调整](local/rebuild/routing.patch)。建议修正文档路径。

## 八行、端点和撤回

`adapter.c:320` 固定发布八行，`services.c:173` 在服务入口拒绝所有非八行形状。L1 十项、配方卡、逐项列表、十一档数值页、分组、空组条目、只读用户条目和 ERR 共用该入口。短视图补一个空格，不发布零长度文字。运行路径没有 `list_bind(2)`，旧十一行面板未被调用。

已发布视图的八行纪律通过；首次发布过渡不通过，见 P1-01。OK 和 ADJ 退出时，固定 resident 在 DAT 调用结束后、IRQ 关闭期间恢复原生七行，并清空 `ui_restore[0]`。七种视图的 21 个退出案例均未经过 Image setter。半按关闭叠层时可暂留隐藏的八行描述，等待后续原生构造。未核对的 H01 回退原生七项，没有显示为已应用配方。这些原生接管状态没有被计作八行 DAT 视图通过。

首尾方向键确实先产生循环后的原生行号，再由 DAT 夹到逻辑端点。数值页上键加、下键减，开放 −5…+5；±6…±9 拒绝。33 行和 19 行是最终 M32R 窗口函数的合成边界检查，实际数值页为十一档，没有冒称为 19 档相机实测。

证据见 [退出行数轨迹](evidence/row-transitions-50mm-irq.json)、[逐屏矩阵](evidence/transitions-50mm.json)、[端点与档位](evidence/values-50mm.json) 和 [M32R 边界](evidence/project-boundary-50mm.json)。后者实际运行 1,693 个档位案例和 8,686 个窗口案例，逻辑行数覆盖 1 至 33。

## 重入和锁定

50mm 上独立执行七种视图、五个切点、六种按键，共 210 例。切点为 DAT 入口、列表服务入口、恢复 IRQ 后续程、绘制桥入口、原生行绘制入口。全部以 PSW.IE=1 重入。35 个原始半按由 `0x0d` 转为 `0x29`，均实际到达 inflight H07。所有重入的 Image setter、`S+0x36e` 写入和新增引擎 RPC 均为 0。半按任务自身可改 S 的其他拍摄字段；其余五键的整段 S 均不变。

六键矩阵的 L1 外层停在 MyRec，数值页外层动作是 DISP，用来隔离发布切点。它没有替代带实际事务的方向键重入矩阵。后者另行复跑。两个旧 op 2 更新阶段已删除，锁定重入的十个旧组合、归属切换的八个旧组合均单列为 `REMOVED_UPDATE_PATH`，没有计作触发成功。

| 本轮复跑 | 50mm | 28mm | MOUNT |
| --- | --- | --- | --- |
| gen 122 九个反例 | 9/9 | 9/9 | 9/9 |
| 原生安全边界八例 | 8/8 | 8/8 | 8/8 |
| 锁定八例 | 8/8 | 8/8 | 8/8 |
| 锁定重入，实际切点 | 30/30 | 30/30 | 30/30 |
| IRQ 开启时切换视图 | 8/8 | 8/8 | 8/8 |
| gen 123 lock_exits | 24/24 | 24/24 | 24/24 |
| 逐屏六键 | 42/42 | 42/42 | 42/42 |
| 档位、端点、Default 和返回 | 7/7 | 7/7 | 7/7 |
| 事务移动时七视图方向键重入 | 70/70 | 未完成本轮复跑 | 未完成本轮复跑 |

50mm 锁定退出最初在命令时限内留下 20 例，随后仅补齐余下四例。逐屏矩阵也仅补齐缺失的 ERR 案例。合并结果按每例实际 DAT 身份和记录哈希核对，没有将超时命令改成成功。详见 [210 例独立核查](evidence/reentry-verified-50mm.json)、[锁定退出 24 例](evidence/lock-exits-124-50mm.json) 和 `local/` 中的原始案例。

## 通信、写入和只读用户条目

十二个原始源码函数未去除属性或空白，逐字比较均相同：`deep`、`apply_impl`、`rpc`、`t_read`、`t_store`、`write_word`、`recover_confirmed`、`make_plan`、`settings_match`、`validate_live`、`rebind_impl`、`eng_require_recheck`。完整读回仍核对九行和 T，没有回到 gen 122 的哨兵方案。`record_failure` 不在这十二个函数内，已核对其新的短码编码。

未修改的 `research/g122_keep_list/audit_records.py` 独立复核了材料中默认 DAT 的 109 条去重完整流，以及用户变体的三条完整流。本轮复跑的完整流另行审计，默认 DAT 去重后为 84 条，用户变体为 6 条。三单元均有原始流，协议失败为 0，没有传入哨兵参数。33 B 行和奇地址半字仍可覆盖一个邻字节，尝试 W 时必须保留最近读回的邻字节。

新增 UI 与 GXUI 没有新增 S 写入地址。应用仍经过原 `make_plan` 和 settings 服务。实际三单元初始化能力为 `0xe7fff`，无文件写能力；create、rename、delete、mark 返回 −12，只读句柄 write 返回 −10。全部所审会话的 create、write、rename、delete、write_open 计数为 0。Mac 工具写本地新 DAT 与固件文件写能力是两个边界。

默认 DAT 有零条用户记录。32 条变体 SHA256 为 `9dc6ff30d64c1b12ca6bfd15baf3acd227358358006392e333114c35d8807c38`，引擎与默认包相同。三单元均实际走过 FCC 组的 25 条，以及另外七个底子的单条用户记录，合计 32 条。应用后的九行、T、Image mode、该模式的 S 设置计划和编码后的两条 WB 均核对；OK、ADJ、半按退出及重开保留效果。运行前后的用户元数据逐字不变。Default 只改会话草稿，不写 DAT。

无首次发布重入的冷启动模型没有自动应用用户记录，九行、T、Image mode 为 04。P1-01 证明一旦首次发布前被重入，Image mode 可变为 5，不能保证完整配方或纯 04。该 harness 的上电 WB 是合成输入，没有由原生完整开机建立，也没有所有上电设置、EEPROM 或实体断电后的全状态证明。永久通信失败时仍可能留有部分 W，系统显示 ERR 并锁定，不把该状态记为完整配方成功；这一故障边界继承 gen 121。

Mac 工具实际生成、列出和清空变体，定长不变，清空后逐字回到默认 DAT。163 个非法条目通过数据边界拒绝，27 条真实 CLI 拒绝路径另外通过，包括重封全部 CRC 后破坏配方绑定。拒绝后没有留下输出或覆盖输入。ERR 的 43,008 个合法元组全部往返。knobs v2 r2 未接入，预留参数非零仍拒绝。

证据见 [十二函数原始跨度](evidence/critical-12-exact.json)、[本轮默认流](evidence/rpc-rerun-default-complete.json)、[本轮用户流](evidence/rpc-rerun-users-complete.json)、[Mac CLI 拒绝](evidence/mac-cli-rejections.json)，以及 `evidence/users-*.json`、`evidence/other-users-*.json`。

## 编译码四类检查

最终 DAT 引擎段、`engine.bin` 和 ELF `.engine` 逐字相同。隔离重编服务及产品、PIC 平移链接和完整重打包均得到相同 DAT SHA。48 个新增或改动 C 函数逐项绑定至编译函数区间；`eng_project_compute` 的无调用包装被 LTO 删除，未记作已执行。五个跳表的 45 个目标均在已分类代码中，两处解码异常属于表数据，没有未分类的可执行异常。

| 类别 | 本轮闭合范围 |
| --- | --- |
| 地址与长度 | 固定三单元九行映射、552 B 输出、24×48 B GXUI 配置、32×24 B 用户记录、八个 9 B 文本槽、八行发布和最终 M32R 档位与窗口边界。 |
| 文件操作 | 新适配器无存储调用，三单元直接服务拒绝实际执行，会话文件变更计数全零。 |
| 原生界面写入 | 未闭合。已发布八行的 210 例及事务方向键重入通过，首次发布前仍有 P1-01 的 Image setter 写入。末端绘制另保留 P2-01。 |
| 循环与内存 | 八行文字、11 个参数、24 配置、最多 32 用户均有固定界限；导航最多 16 轮，补偿仍为 4+2；重编栈记录全部为静态帧，无 VLA。 |

引擎 46,660 B，BSS 8,844 B，DAT+BSS 为 67,040 B，低于 114,688 B 界限。模型冷启动分配合计 77,168 B，包含保留的 loader 工作区和头部。重编最大单帧为 260 B，不能由单帧或模型堆数字推断相机 RTOS 的总栈、总堆余量。

证据见 [48 函数与四类义务](evidence/compiled-review.json)、[最终编译表](evidence/compiled-tables.json)、[内存预算](evidence/memory-budget.json)、[单帧对照](evidence/stack-compare.json) 和 `local/compiled/`、`local/rebuild/`。

## 测试状态来源

仓库确有手工预置：`tools/native_harness/scenarios.py:310` 在 `negative_hand_type()` 中直接写 `0x2022f71c=5`，是旧代负例。`tools/native_harness/harness.py:100` 也有固定 Image getter stub。gen 124 的正向绑定 `firmware/engine_v46_ui/native_binding.py:50` 在运行前移除该 stub，通过官方构造器和原生按键建 UI。本轮所列正向路径的 host UI writes 均为 0，没有调用该负例。

设备行复位、通信失败、S 初始输入、字体、图形叶函数和操作系统边界均是模型。补充的 IRQ 原始半按先遇到未建模的 RTOS trap；失败集中在 HALF。最终模型只补正常任务上下文、任务号和消息提交边界，保留原生转换、分派和 H07，并强制检查 H07 见证。没有用界面值预置或 Image getter 假返回制造通过。早期失败、环境归类和最终 210 例全部保留。

## 与 gen 121 的比较

P1-01 的首次发布错误在 gen 121 同样存在，未将它标成 gen 124 新增回退，但它仍阻断本轮明确的状态约束。三单元映射和 48 个打包槽位与 gen 121、gen 123 相同。gen 121 的十一行数值面板在 inflight 重入时没有八行保护，gen 124 改为八行。gen 122 的部分复位漏检、未核对八行配方仍能退出，以及 gen 123 当次一行 ERR 误写均未在本轮对应旧反例中重现。

现场操作有代价：从 L1 到数值页由一次 DISP 变为三次，数值方向改为上加下减。初始化单帧从 gen 121 的 164 B 变为 260 B；全程序最大单帧从 176 B 变为 260 B，但内联结构不同，不能据此断言整个调用链更深。DAT+BSS 从 71,104 B 降至 67,040 B。P2-01 的末端绘制窗口仍存在。

固定 resident 的 H01 提前退出、真实按键连发、LCD、实际调度频率、拍摄结束及实体断电尚未复核。本轮没有宣称修复 gen 121 拍后首次七行的现场根因。

## 输入完整性与实际命令

本轮独立核对材料清单 11,162 项、卡包清单 30 项，29 个固定文件与 gen 120b 相同。冻结输入及后续只读栈记录的最终复核见 [integrity.json](integrity.json)。只写 `research/review_g124/`。理光原始字节、反汇编和运行原始流均位于 `local/`。

实际运行的命令及返回码见 [COMMANDS.md](COMMANDS.md) 和 [commands.jsonl](commands.jsonl)。`SHA256SUMS` 路径以仓库根为基准，覆盖本轮输出和被冻结输入，排除清单自身。早期解释器缺口、超时、合并器读取旧记录身份字段的失败，以及文档路径拒绝均原样保留，未改成候选通过。
