不可以上测试卡

gen 126 新增的发布后设置恢复，会在原生菜单已经切走后继续写旧配方设置。三个单元均复现，gen 124、gen 121 的相同切点没有迟到设置写入。本项 P1 阻断测试卡放行。原厂七行窗口的瞬时写入另列为继承限制，不作为本版新增问题。

审查对象为 `firmware/package_v36_g126/SD_ROOT/GXRCE.DAT`，58,360 B，generation 126，SHA256 `a855adcf3aaeaaa427b5ea43816c2cb7acd71fc9ceb7973bf8db3af8d6b1610d`。固定机身 v3.6 SHA256 为 `50720c80696ca88f25dc25a85285acd0e0f19906e1d7da1dd404f6cc243f9008`。本报告仅针对只换 DAT、使用测试卡 B 的增量审查。

所有“原生重放”均指固定机身 M32R 指令在主机模型中执行。没有访问相机、存储卡或网络，没有启动子代理。预览入口能证明调用时的设置计划，不能证明 LCD 图像、曝光完成、真实 RTOS 调度或实体断电。

## P0

未发现。

## P1

### P1-02：八行发布后失去菜单归属，新增恢复仍修改 S 并请求预览

位置为 `firmware/engine_v47_fix/candidate/containers/product/adapter.c:328`、`:331`，`firmware/engine_v47_fix/candidate/containers/product/src/firmware/engine/core/eng_core.c:561`、`:569`。实际写入位于 `firmware/engine_v47_fix/candidate/engine_services/services.c:275`。`eng_core.c:59` 的 epoch 比较不核对当前原生 activity；服务的 `current()` 在 `services.c:17` 只核对会话 epoch。

复现步骤：

1. 从干净模型经官方原生构造器首次打开 Image 菜单，在 DAT `list_bind` 入口插入原生向下按键事件。此时为七行、inflight=1，原厂 setter 把 mode 从 1 改为 5。
2. 外层继续发布八行。在 `RV_UI_LIST` 成功返回的续程，用另一个原生任务执行 `0x202ba380…0x202ba3c8` 和 ADJ 构造器 `0x20285e00`，切到 activity 7，overlay 从 32 变为 21。没有给 UI、resident 或引擎状态赋值。
3. 恢复旧任务。gen 126 继续进入新增 `eng_check_settings()`，随后调用 settings 服务 op 2 和 preview 服务 op 1。

```sh
/usr/bin/python3 -I -B research/review_g126/ownership_settings.py --generation 126 --unit 50mm
/usr/bin/python3 -I -B research/review_g126/ownership_settings.py --generation 126 --unit 28mm
/usr/bin/python3 -I -B research/review_g126/ownership_settings.py --generation 126 --unit mount
/usr/bin/python3 -I -B research/review_g126/ownership_settings.py --generation 124 --unit 50mm
/usr/bin/python3 -I -B research/review_g126/ownership_settings.py --generation 121 --unit 50mm
/usr/bin/python3 -I -B research/review_g126/verify_findings.py
```

三个单元的最终 DAT 均在 activity=7、state=56 时，由 PC `0x2070f380` 依次写 `S+0x6dd=9`、`S+0x6de=9`、`S+0x36e=1`。该 PC 对应最终 ELF `rv_call` 内的 `0xa4ac`，即原设置服务的编译写入循环。gen 124、gen 121 的相同切点均为零迟到 S 写入，mode 保持原厂方向键留下的 5。文件变更计数和 host UI writes 均为零，Image getter 没有假返回。

这项差异来自新增的旧任务恢复，不能归入原厂瞬时写入。用户切到其他原生菜单后，旧配方任务仍修改设置并请求预览。当前恢复只有会话 freshness 检查，没有把实际设置写入与当前原生菜单归属绑定。修复需要在恢复及最终设置写入边界处理归属丢失，并复跑此切点；只核对恢复后的配方值不足以关闭本项。

证据见 [独立核验](evidence/findings-verified.json)、[50mm](local/ownership-settings/126-50mm.json)、[28mm](local/ownership-settings/126-28mm.json)、[MOUNT](local/ownership-settings/126-mount.json)、[gen 124 对照](local/ownership-settings/124-50mm.json) 和 [gen 121 对照](local/ownership-settings/121-50mm.json)。这里只证明模型中的原生任务交错结果，未证明真机上的触发频率或可达性。

## P2

### P2-03：增量范围不满足 validate_live 逐字保持的约束

位置为 `firmware/engine_v47_fix/candidate/containers/product/src/firmware/engine/core/eng_core.c:583`、`:610`，恢复状态位的变化位于同文件 `:575`、`:576`。对照位置是 `firmware/engine_v46_ui/candidate/containers/product/src/firmware/engine/core/eng_core.c:563`。

```sh
/usr/bin/python3 -I -B research/review_g126/delta_exact.py
```

原始源码跨度保留属性和空白后，`validate_live()` 与 gen 124 不相同。旧实现内联设置核对，恢复后清 `previewing`；新实现调用 `eng_check_settings()`，该函数恢复原 `previewing` 并据此选择 stage。实际增量包含这个改写，不能表述为仅在两个调用点增加调用，其余关键函数全部逐字不变。

九行及 T 的完整读回部分逐字相同。其余核对的 14 个函数均逐字相同，包括 `deep`、`apply_impl`、`rpc`、T 读写、写入、补偿、`make_plan`、`settings_match`、重新绑定及 recheck。这里没有把非等价源码直接判为配方计算错误；影响是超出了明确的冻结范围，且需单独审查恢复后的浏览和确认语义。

证据见 [原始跨度比较](evidence/delta-exact.json) 和 [完整源码差异](source-change-vs-g124.patch)。

## 继承限制

gen 124 P1-01 的正常发布后最终状态缺口已在所列切点恢复；固定机身的七行窗口仍允许原厂 setter 写 `S+0x36e`。正常保持 Image 菜单归属时，本轮三个单元各四个切点均恢复到纯 04：发布后和 OK 退出后 mode=1、WB=9/9、九行及 T 相符，最后一次预览入口的计划也相符。原厂写入仍可观察，不能宣称零瞬时写入。其真机可达性由 `research/reentry_reachability` 的另一项研究确认，本轮不代替该研究作结论。

gen 124 P2-01 的末端绘制窗口仍存在。gen 126、gen 121 的列表及面板、activity 及 state 切点共八例均进入旧行绘制器，并由原厂 PC `0x201fd392` 写全局 `0x205d4f64=0`。这些设置已经匹配的旧窗口案例没有迟到 S 写入，不能据此覆盖 P1-02 的设置恢复分支。见 [原生绘制后果](evidence/native-draw-consequences.json)。

预览服务失败后，S 可以已经恢复，下一次打开只因设置匹配而不再请求预览。位置是 `firmware/engine_v47_fix/candidate/containers/product/src/firmware/engine/core/eng_core.c:352`、`:566`。gen 126 三个单元及 gen 124 的独立对照均观察到重开时预览请求和原生预览调用为零。gen 124 在重开核对时触发该失败，gen 126 在新增发布后核对时触发；两者复用同一个 `apply_impl` 失败边界。运行 `preview_reopen.py --generation 126 --unit 50mm` 和 `preview_reopen.py --generation 124 --unit 50mm` 可复现，Python 前缀均为 `/usr/bin/python3 -I -B research/review_g126/`。影响是重开的设置检查通过，不能证明失败的预览刷新已经补做。本版服务失败套件的通过条件只证明设置、锁定及重开，不能计作成功刷新预览。见 [gen 126 对照](evidence/preview-reopen-126-50mm.json) 和 [gen 124 对照](evidence/preview-reopen-124-50mm.json)。永久通信失败后的部分 W、ERR 和锁定规则也仍是继承边界。

gen 124 P2-02 的原复现文档脚本路径错误仍保留在只读目录。实际入口是 `firmware/engine_v46_ui/candidate/reproduce124.py`。本轮使用输出受限的 `research/review_g126/reproduce.py` 隔离重建 gen 124、gen 126，两代均得到各自冻结 DAT、引擎、重定位及 48 槽位有效行的逐字一致结果。

## 改动范围和编译码

最终 DAT 内引擎、`engine.bin` 及 ELF `.engine` 逐字一致，源码、头文件和编译工具哈希均与构建记录匹配。两代服务 C、H、汇编及链接脚本逐字相同；29 个固定卡包文件与 gen 120b 逐字相同。独立核对实现材料 SHA 清单 13,765 项、卡包清单 30 项均通过。

本包三个单元的 24 条实际配方记录均为原生 mode=1，实际设置计划是 Image mode 和两个 WB 字段。其他原生模式的专属字段分支只做未改源码及编译码核对，不列作本包真实记录的运行覆盖。

实际有七个新增或改动 C 函数：`list_bind_impl`、`ig_event`、`eng_check_settings`、`validate_live` 及三处 generation 校验。101 个编译函数的归一化指令相同，六个不同，另新增 `eng_check_settings`。`ig_panel_open` 和 `rv_call` 的差异只有随引擎增长 164 B 平移的跳表基址；五个跳表共 45 个目标已与汇编表达式及最终链接值核对，未分类可执行解码异常为零。

| 检查类别 | 结论 |
| --- | --- |
| 地址与长度 | 固定 552 B 配方、原设置租约、最多 16 个计划字段及既有 S 地址未扩展；九行和 T 的映射及完整读回未变。 |
| 文件操作 | 没有新增存储调用，实际运行的文件变更计数为零；三单元直接服务边界结果随后并入回归表。 |
| 原生界面写入 | 未闭合。P1-02 已在三个单元证明失去当前原生菜单归属后的设置写入和预览请求。 |
| 循环与内存 | 新辅助函数没有循环或分配；计划至多 16 项、九行、16 轮导航及 4+2 次补偿界限未变，重编栈帧均为静态。 |

DAT 58,360 B，BSS 8,844 B，合计 67,204 B，低于 114,688 B 界限。最大单函数静态帧为 260 B，与 gen 124 相同。新辅助函数自身有 116 B 静态帧，不能用“最大单帧未变”推断调用链或 RTOS 总栈没有增长。

证据见 [源码与最终产物绑定](evidence/static-audit.json)、[跳表](evidence/compiled-tables.json)、[编译函数差异](evidence/binary-inventory.json)、[静态类别检查](evidence/codegen-safety.json)、[栈帧对照](evidence/stack-compare.json)、[gen 126 重建](evidence/rebuild-126.json) 和 [gen 124 重建](evidence/rebuild-124.json)。自动静态类别脚本的 PASS 不覆盖本轮新发现的 P1。

## 回归、通信与实际命令

本节在本轮运行结束后填入实际数量和返回码。各测试结果只从 `research/review_g126/` 的新运行记录取值，不采用实现目录的通过汇总。长套件由每单元独立进程执行，同单元同套件用文件锁避免重复写入；后续命令可以读取本轮同一最终 DAT 已完成的记录。

## 相比 gen 124 和 gen 121

正常保持 Image 菜单归属时，gen 126 修复了首次发布后 mode 与 04 不符的结果，也给未提交会话的 H07 增加核对。P1-02 则是两个基线都没有的迟到设置恢复，现场表现存在变差路径。

相对 gen 124，DAT 及驻留占用增加 164 B，BSS 不变；每次列表发布和 H07 增加设置核对及相关计算、租约调用。本轮不把主机执行时间当作相机延迟。相对 gen 121，DAT+BSS 从 71,104 B 降到 67,204 B，但初始化最大单帧从 164 B 增到 260 B；八行界面及多级操作的变化是 gen 124 已有行为。

## 输入保护与清单

本轮只写 `research/review_g126/`，理光原始字节、反汇编和原始运行流均留在 `local/`。输入冻结及结束复核、实际命令列表和以仓库根为基准的 `SHA256SUMS` 在封存时生成。结论不代表相机、卡、LCD、实际调度、拍摄结束或实体断电已验收。
