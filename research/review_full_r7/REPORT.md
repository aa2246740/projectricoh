不可以上卡

R6-02 已修复；阻断是原生高亮被写成新的开机记忆。R6-01 的高亮本身和 F02 仍按题设接受，不据此重复否决。

审查文件为 `firmware/engine_v33d/local/card_update/GXRCE.DAT`，generation 109，62,228 B。实算 SHA-256：

```text
ff1a4d32a23456464e340ac6cf67f95a582a58e61f2860f21e070c1b1509b237
```

P1 · R7-01：直接确认原生高亮会覆盖原记忆，影响下一次开机。

场景：50mm 或 Mount 记住 01 Posi，重新从 tag 32 进菜单。01 已完整恢复，原生高亮却落在 02。没有滚动，直接按 OK，GXLS 从 slot=1/gen=1 变成 slot=2/gen=2；再次开机打开菜单，恢复 02 Nega。Fn2 后按 MENU 同样把 02 写入记忆。记忆 03 则变成 04。96 项入口检查中，56 项复现覆盖；单纯 MENU 保留原记忆。

依据为 `firmware/engine_v33d/containers/product/adapter.c:454` 先应用 native cursor，`:460` 关闭时调用记忆保存，`:292-300` 只比较新旧槽，没有区分原生初始化与用户选行。实际候选 `ig_event` 的 `0x80BC-0x80C8`、`0x8128-0x8140`、`0x81AC-0x81B4` 也保留该顺序。见 [01→02](local/logs/attack-attacks-reflexive-0-1-g105-1-1.log)、[03→04](local/logs/attack-attacks-reflexive-2-1-g105-3-1.log)。

记忆覆盖在 v33b 已存在，v33d 把写入推迟到关闭，仍未消除。full-r3 的原生高亮差异没有 GXLS 的跨开机后果。本项按题设单独报告持久化损害；应保护未经用户选行确认的原记忆，或另行明确接受这项持久化限制，不能只凭“高亮继承”关闭。

P2 · R7-02：旧 DAT 只有浏览零写，显式保存 GXTS 仍会写。

场景：IROM 已是 109，卡上保留 108。安装返回 CONFLICT；选择 05，Fn2 改 Cont，再按 OK，仍有一次 create、三次短 write、一次 rename。移除旧 DAT 后冷加载 109，Cont=3 继续生效。两镜头、两种 rename 均复现。依据为 `adapter.c:284` 的冲突保护只管 GXLS，`:319-330` 的 GXTS 保存没有此判断。见 [旧 DAT 保存](local/logs/attack-attacks-older-explicit-save-0-1-g108-default.log)。因此不能宣称旧 DAT 的全部操作零写；若验收只要求浏览零写，原门槛通过。

P2 · R7-03：菜单未关闭就关机会丢掉本次选择，恢复更旧的完整配方。

场景：记忆是 01，打开列表选到 08，未关闭就断电。下一次打开菜单恢复 01，不是刚才的 08，也不是 04。8×8 配方组合中，224 个不同槽组合均恢复完整旧记忆，没有混合行数据。依据为 `adapter.c:302-312,460`，只有关闭路径调用保存。见 [01→08 未关闭](local/logs/attack-attacks-deferred-0-1-g105-1-8.log)。若“最后配方”指最后实际应用的槽，而非最后关闭时保存的槽，这一行为不满足该措辞。

P2 · R7-04，题设豁免：03 在没有有效 GXLS 时留下原生 B&W。

断电投影保留 S、重置模块行，再打开菜单：03 留下 selector=3、S+0x645/646=3/4、WB=9/9；模块已是 stock 行，既非完整 03，也非纯 04。50mm、Mount 均复现，见 [Mount 03](local/logs/attack-attacks-power-2-1-g105-3-0.log)。此项按要求不阻断，未把另一个任务尚未交付的 Standard 数据算入本候选。

其余核验结果：

- R6-02 的隔离成立。744 次 GXLS 逐操作故障后，同次开机的 Fn2、同行重选、换行、GXTS 保存、关闭、重开和冷加载均通过。另有独立读写攻击，覆盖首次记忆加载失败、EOF、过量返回、读回字节损坏，以及 write/delete/rename 已生效再报错。未见 GXLS 故障设置 RF_UNCERTAIN 或停用引擎。依据为 `engine_services/services.c:83,92,138` 和 [独立结果](local/independent-attacks.json)。GXTS 本身的故障仍按既有规则处理，未宣称它们一律不停用。
- 写策略成立。滚动零写；记忆为 01 的 01→08→01，关闭后仍零写；实际换槽后 OK、MENU、H07 强制关闭各一次事务。不关闭的 OK 延后保存。主机短写配置下，一次事务为一次 create、三次 write、一次 rename，不是“一次 write”。见 [会话计数](local/logs/attack-revision-write-policy-0-1-g105-default.log)。96 次 write/close/rename 前后重入没有嵌套引擎调用、重复保存或丢掉 committed 外观；184 份中断文件映像冷加载只采用完整 A/B，忽略 TMP。
- 默认 S 状态逐槽核对。01、02、04、05、06、07、08 均写 selector=1、WB=9/9，不写 native colour/B&W 参数；03 额外写 B&W 的 3/4。全 4 KiB S 比较及全部配方切换未见其它引擎写入。03 的 B&W 参数在转回 Standard 后仍留在非活动字段，不能称为“全 S 清零”；它们不改变 selector=1 的当前输出。无 GXLS 的其余七槽投影均为纯 04；有有效 GXLS 的八槽均恢复完整配方。见 [断电结果](local/power-cycle-results.json)。
- 高亮表与官方字节一致。S=1/3/4/5/6/9/10 分别映射 02/04/06/07/05/01/03，其余输入先被 getter 改成 1，再高亮 02。独立执行 getter 全部 256 个输入；官方文件 getter 偏移 `0x2271EC`，枚举偏移 `0x23C2AC`，cursor stores 在 `0x23C358/364`，tag 33 push 在 `0x23C3A4`。见 [逐字节执行](local/getter-execution.json)。OK/Fn2 的持久化后果见 R7-01。
- R4-01/R4-02 未回归。旧绑定单份/双份首次新保存、有效副本保留、连续保存、双份 1,024 B 残缺安装及 840 次 GXTS 故障恢复满足断言。50mm/Mount 各八行，28mm 原生七项；首次 menu_open 才自动应用，load 本身不应用。105/106/107/108 的升级、空 IROM 首装、移除 DAT 后 IROM 109 冷加载、旧 DAT 浏览及强制关闭零写均通过。见 [232 项流程](local/acceptance-results.json)、[补充回归](local/extra-regressions.json)。
- 数据和身份核对通过。独立 Python 与完整 C 对 144 槽展开一致；相对 v33b，48 槽 entry、record、metadata、160 B binding 全等。运行源码相对 v33b 只改 adapter/services；另独立保留 full-r3 差异。80 B trust、7,772 B resident payload、build/ABI 和 pins 均相同；批准机身实算为 `05b46ee65f4861f2e09e9b7c519cbcc2dffb195158a40c3bb033540b36a98d8c`。容器引擎段与现有 ELF/bin 全等，重定位平移通过。见 [文件证据](local/artifact-results.json)、[源码比较](local/independent-source-comparison.json)。
- M32R 类型对象独立测得主块 80,924 B、工作区 1,460 B。首装含头 212,652 B；已有 UI snapshot 时 214,632 B。文件距上限余 3,308 B，engine=53,204 B、BSS=11,192 B，均未越界。这些是申请量，不是相机堆余量。卡流程仍要求关机删旧 DAT/OK，只换新 DAT；未改 resident/body，也未执行上卡。见 [目标布局](local/target-layout.json)。

未核实：真实相机首次产品容器加载、候选 M32R 实际执行、完整原生 UI/快门时序、文件错误的全部副作用、物理掉电持久化、连续堆和照片颜色。重入检查证明主机 C 无嵌套和忙等，不能证明原生同步 I/O 不会拖慢快门。历史容器入口接到当前 C，未执行历史引擎机器码；断电检查是文件/S 映像投影。没有新增 P0 证据，不据主机通过宣称无变砖风险。

共 2,874 次有清单的主机行为运行，另有三次向量程序；返回 0 包含反例断言成立，不代表全部安全通过。13,313 个冻结输入未变，decisions.tsv 排除。只写本目录；未重建或重封装候选，未访问相机卡、刷机、安装包、使用子代理、sleep、轮询、commit 或 push。理光派生字节全部在忽略的 `/local/`。

复核入口如下，不要重跑 freeze 覆盖起始证据：

```sh
/usr/bin/python3 -I -B research/review_full_r7/review.py check-delivery
```

完整复跑顺序为 review.py 的 inspect、native、compile、layout、acceptance、faults-last、faults-tweak；attacks.py 的 prepare、sessions、extra、older_save；最后 review.py finalize。所有 Python 均使用 `/usr/bin/python3 -I -B`。交付摘要见 [SHA256SUMS](SHA256SUMS)。
