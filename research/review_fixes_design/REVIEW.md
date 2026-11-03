修改后再实现

有 1 个 P1：三个缓存写入入口漏掉了 H07 错误处理后成功保留视图的返回路径，resident 仍会恢复游标，缓存却没有恢复。MOUNT 改查 50mm 旋钮记录的方案可以保留。其余意见列为 P2，实现时处理。

本次只评设计，不给任何 DAT、g150 或 g152 作上机判定。`g151_design` 只是历史目录名，两项修复应在 g152 定稿后选用新的代数。

评审对象为 `research/g151_design/DESIGN.md`，SHA256 为 `a835f091fee28b7244f3e66f9aaf4c5c5446f70563586171f9307362b266d5a5`。其 `SHA256SUMS` 的 10 项在开始时全部匹配。源码、原型差异和原结果均只读；复审自己的脚本、结果和清理记录与本文件一起交付。

P1-01 位于 [DESIGN.md:70](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/g151_design/DESIGN.md:70)、[DESIGN.md:101](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/g151_design/DESIGN.md:101) 和 [design-A-B.diff:37](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/g151_design/prototype/design-A-B.diff:37)。设计把 H07 的缓存恢复放在 `ui_finish(result == RV_CLOSE_AND_PASS)`，但 H07 的 `keep=0` 在返回 `RV_CONSUMED` 时同样关页。

具体代码链如下，行号均按本轮只读源码。对应 [adapter.c](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/firmware/engine_v58_g150/candidate/containers/product/adapter.c:135)、[hooks.c](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/firmware/resident_v38/resident/hooks.c:95) 和 [shared.c](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/firmware/resident_v38/resident/shared.c:74)。

```text
resident_v38/resident/hooks.c:89            H07 设置 args[8]=7、args[9]=keep
engine_v58_g150/.../adapter.c:550           eng_check_settings 失败，返回 finish(r,status)
engine_v58_g150/.../adapter.c:140-142       keep_view 成功，直接返回 RV_CONSUMED
engine_v58_g150/.../adapter.c:364-366       重画成功，缓存仍为 DAT 高亮行
resident_v38/resident/hooks.c:100           H07 && keep==0，调用 rv_ui_abort
resident_v38/resident/shared.c:83-84        恢复原厂 7 行和游标，不写缓存
```

同类遗漏还在 `adapter.c:370-373`：`ui_finish(RV_FAULT)` 可以经 `keep_view()` 成功返回，在到达新增的 `result == RV_CLOSE_AND_PASS` 判断之前就离开了函数。原型没有修改 `finish()` 或 `keep_view()`。因此正常 OK/MENU 的原型结果不能证明这些错误返回也修好了。

复审动态结果见 [h07-results.json](h07-results.json)。该检查在 50mm 主机模型上使用真实 g150 DAT 与 v3.8 resident 指令，只让一次设置读取返回错误，随后恢复正常服务。实际顺序为 `ig_event → finish → keep_view → h07_close`，没有经过 `ui_finish` 或 `release_view`；关页后游标为 5/5、缓存为 4，原厂 `0x201CA75C..0x201CA778` 随后把游标从 5 改成 4。此间 S 区 4096 B 相同，单元 W 为 0。它确认了这条控制流可达，结合原型差异可确认新增三个调用都不会执行；它不是新 DAT 的实现验收。

最小修改是让 H07 `keep=0` 的全部最终返回汇合到缓存恢复操作，或在 `keep_view()` 最后一次重画成功后，针对 `n.entry==7 && n.request.args[9]==0` 补写缓存。必须晚于最后一次 `list_bind()`，否则重画又会把缓存改成高亮行。`keep=1`、H06 和 H08 继续保留菜单时，缓存仍须等于当前高亮行。给该路径增加三单元用例，记录返回码、实际恢复入口、缓存写入 PC，以及后续原厂读取片段的结果。

按其余门槛看，两项差异没有增加配方提交阶段；B 仍先算出完整 552 B 条目，再走既有提交流程。没有发现这两项改动新增半套配方或写错设置对象的路径。实际发布仍受 8 行检查约束。放行用例需要补齐和修正下列预期；这些是针对本设计差异的静态结论，不替代另一轮对 g150 的整体复审。

逐项复核结果如下。

| 项目 | 判断与依据 |
| --- | --- |
| 普通 H07 关页 | 新调用位于 `ui_finish` 清理 `active` 前，先写缓存，再返回 resident 恢复游标，顺序正确。P1-01 所述提前返回不在这条链内。 |
| DAT 主动放弃视图 | `release_view` 开头的调用早于 `es_ui_abort`，常规恢复链顺序正确。原函数仅在 `!n.failed` 且列表仍匹配时调用 `es_ui_abort`，不能把进入 `release_view` 一概写成已经恢复。依据为 `adapter.c:75-87`。 |
| `ig_panel_abort` 与 `ig_stop` | 前者走 `ui_finish(RV_CLOSE_AND_PASS)`；后者的新调用早于 `eng_menu_close`。直接测试这两个入口时，还要执行实际调用者承担的 resident 恢复步骤，不能把 DAT 入口返回当成游标已恢复。依据为 `adapter.c:569-577`。 |
| 别的视图当前或列表已失去归属 | `cursor_cache` 在关 IRQ 区内同时检查 `rv_view_owned()` 和当前状态。前者校验 lease、epoch、列表来源、名称表、行数、part、栈顶和活动类型；后者只允许 Image 状态或自己的快照。没有发现新增写其他视图缓存的入口。依据为 `adapter.c:296-300`、`engine_services/native_seed.c:2-23`。 |
| 写入与恢复的临界区 | 缓存写入和归属检查处于同一临界区；resident 的恢复另开临界区，两者不是同一段关 IRQ 区。普通 H07 从 DAT 返回到恢复之间没有 RPC 或会让出的原厂调用，但包含 resident 的返回检查。设计可依赖同一按键任务的顺序，不能把主机结果写成所有 RTOS 调度情形的证明。 |
| resident 自行退役 | `hooks.c:75`、`:92` 和 `resident.c:52-70` 都能在 DAT 运行前或返回检查时转到 `rv_retire → rv_ui_abort`。三个 DAT 写入点无法覆盖这些路径，范围不只 H08。见下方 P2。 |
| 原始半按 | 已有冻结结果的 raw 0x0D 经原厂消息分发后变为逻辑 0x29，没有 DAT 入口，游标对和缓存仍一致，列表仍为 8 行。这支持“隐藏而未撤回列表”的主机结论；它与直接送 H07 的逻辑半按是两种路径。依据为 `cache_paths.py:42-51` 及两份缓存结果 JSON。 |
| 隐藏后重显 | H01 首发路径重新发布游标，并写缓存；`rv_ui_capture` 仅在 `ui_restore[0]==0` 时采集原游标，重复 H01 不覆盖旧恢复目标。依据为 `adapter.c:329-350`、`shared.c:61-73`。本轮 50mm 原始半按后为 5/5/5、8 行，无 DAT 入口；part 1 重显实际进入 `ig_menu` 后为 2/2/2、8 行，`ui_restore[11]` 仍为 5。只将此序列用于核对缓存、游标及恢复目标，见 `native-results.json`。 |
| 拍照后再打开 | 新打开路径会重设缓存，这一点有源码依据。但被引用的旧用例先显式调用 `rv_ui_abort`，再建立 part 1 或空栈形态，不能证明从本次半按隐藏状态经过完整拍照后的所有转换。依据为 `g135_v37/accept.py:147-156` 和 `emptystack_v38/empty_check.py:44-54`。P9 要分别记录重开前是否仍有恢复记录，再验证实际结果。 |

MOUNT 的四条数据流均使用新的查询入口，没有发现能用旧 MOUNT 旋钮记录计算并提交的现行路径。

| 数据流 | 文件与行号 | 复核结果 |
| --- | --- | --- |
| 开机预选 | `engine_v58_g150/.../core/eng_core.c:735-739` | 完整记录核对后还调用 `kv_data_request`。旧 MOUNT 独有档位不再被预选；DAT 头 CRC 变化也会使旧记录失效。 |
| 用户条目最终检查 | `engine_v58_g150/.../adapter.c:485-489` | 每条都调用 `kv_data_request`，全部通过后才置 `initialized`。不合法条目使整个 DAT 被拒，不会先应用其中一部分。 |
| 界面默认值、范围、档位及文字 | `engine_v58_g150/.../kv2/kv_ui.c:14-15`、`:33-45`、`:142-157`、`:208-215`、`:364-375` | 经 `kv_data_recipe`、`kv_data_find` 或 `kv_data_request`；后两者也调用 `kv_data_recipe`。按记录偏移取 item/point 的调用都使用该查询返回的 `first_item`。 |
| 引擎计算 | `engine_v58_g150/.../core/eng_core.c:172-182` | 先调用 `kv_data_request`，再以实际单元的 stock 和配方条目计算。局部映射不会改变 `g.data.unit`、记录身份、单元 map 或 S 设置计划。 |

表中的 core 文件为 [eng_core.c](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/firmware/engine_v58_g150/candidate/containers/product/src/firmware/engine/core/eng_core.c:172)。`adapter.c` 与 [kv_ui.c](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/firmware/engine_v58_g150/candidate/containers/product/kv2/kv_ui.c:14) 位于 `candidate/containers/product` 下。

`uv_validate()` 确实还有旧范围的直接读取，见 `ui_v2_data.c:48-69`，但它是附加格式和范围检查，之后仍有上述旋钮合法性检查，不会把旧档位送入引擎。旧面板的 `eng_metadata()` 只剩源码调用；本轮查看 g150 与当前 g152 ELF 的符号表，未见该函数及旧面板的打开、关闭和事件函数。不能只凭 map 中仍列出 object 文件就断言旧面板可达。

`kv_data_open()` 在 `kv_data.c:120-145` 直接核对全部 24 条物理记录，不经查询映射。把映射放在 `kv_data_recipe` 的参数范围检查之后、记录偏移计算之前，能保持整块校验和 MOUNT 04 的语义。

复审用正确的 52 B `KvRequest` 独立编译主机 C，对原始数据和仅改变查询映射的版本各跑一遍。结果见 [knob-results.json](knob-results.json)。七个目标配方按旋钮分别枚举的合法档位数依次为 148、151、90、153、160、153、150。映射后 MOUNT 与 50mm 的完整 request 相同；Amount=100 时，01、02、03、05、07、08 的完整 552 B 条目相同，06 仅有设计列出的 T1 字节差异。50mm、28mm 及 MOUNT 04 与原版本相同。另有 2,034 个双旋钮端点/中点组合，MOUNT 与 50mm 的 request 全部相同；这些组合没有在本轮作全部 552 B 条目比较，正式验收仍须按设计补齐。

Amount≠100 使用各自 04 没有发现新增的设置风险。`project_compute` 把实际单元的 `g.stock` 传入 `kv_apply_work`，`kv_math.c:66-99` 处理 Amount，之后才处理其余剂量。0 到 100 是向本单元原厂端点混合，100 以上按原算法延伸并限幅，输出不同属于该设计的明确行为。Amount=0 且其余旋钮为默认值时等于本单元 04；其他旋钮非默认时，后续阶段仍会修改这个端点，验收不能一概要求输出等于纯 04。

49 个 MOUNT 单 Amount 非 100 档位的输出都与显式传入 MOUNT stock/base 的主机 C 参照逐字节相同；改用 50mm stock 的参照在这 49 项中都不同。三个单元共有 18 项可用 Amount=0 的端点检查，输出均等于各自 stock。03 和 04 没有 Amount 旋钮，不计入此数。这证明了端点选择，未证明真机色彩或真实拍摄效果。

给实现者的 P2 注意事项如下。

1. 修正原型 C/Python 结构声明。`prototype/knob_alias_check.py:15-16` 将 `dose` 声明为 9 项，结构为 48 B；实际 `kv_math.h:8-13`、`:32` 为 10 项、52 B，最后一项是菜单未使用的 Tone 剂量。本轮独立检查最初沿用旧声明时两次以 139 结束，改为 10 项并在调用前核对 C/Python 的 `sizeof` 后通过。原始结果不应继续作为正式验收依据。本轮重跑支持映射方案，但正式工具仍须修好。失败和修正记录见 `review-check-failures.json`。

2. 更正 `DESIGN.md:91-95`、`:155-158` 的退役范围和用例预期。产品版打开后缓存为配方高亮行，探测卡则已在打开时写原行，所以 `retire_at_ok` 的 5/5/5 预期不能照搬。三个镜头的确认结果见 `native-results.json`。把 DAT 没有运行的退役情形统一记录为 v3.8 resident 遗留，覆盖 OK、DISP、H08、隐藏后重显及返回检查；不要仅对 H08 作例外。此项按既有 resident 限制记 P2，不把它升级为本设计新增的设置损坏。

3. 细分 `release_view` 的错误场景。在 `n.failed` 为真、重画失败、入口为 H06/H08 时，原代码不会执行 `es_ui_abort`，resident 收到 `RV_CONSUMED` 也不会恢复。此时提前把缓存写为 home 会使仍保留的 ERR 列表与缓存暂时不一致。应把新增写入绑定到实际撤回列表的分支；H07 `keep=0` 则在最终关闭处处理。ERR 仍阻止配方应用，但不要把这条链误记成已恢复为原厂 7 行。依据为 `adapter.c:81-87`、`:370-375`、`:521` 和 `hooks.c:95-100`。

4. 22+3+13 是场景目录，不能直接当成充分性证明。保留三单元、普通关页、全部 UI 层级、归属丢失、RPC 重入和七类回归，并补上 P1-01 的错误返回矩阵。`keep=0/1`、`RV_CONSUMED/RV_CLOSE_AND_PASS`、`keep_view` 成功/失败都要有可观测结果。小页和 ERR 页的逻辑行数可小于 8，实际发布行数必须始终为 8，撤回后才恢复为原厂 7 行。先失败后通过应逐个列明旧版预期，归属负例和未改行为本来就会通过，退役遗留也不能混入“新版全部通过”。依据为 `DESIGN.md:124-180` 和 `engine_services/services.c:57-62`。

5. 修正 06 的 T1 预期。`DESIGN.md:235`、`:251` 不能对所有旋钮状态无条件断言 C/D 等于 MOUNT 04、控制字为 `0x0002`。本轮在 Amount=100、Splt=+1、其余默认时得到 mask=7、控制字 `0x0000`、C/D 与 stock 不同，见 `knob-results.json` 的 `mount06_split_plus1`。`kv_math.c:181-186` 在 Splt 剂量非零时启用 T1，这是既有算法行为。保留本次查询映射的范围，把未启用 Splt 的基准情况与启用后的完整计算参照分别列为判据。

6. 明确 S 区比较的控制组。`DESIGN.md:132` 的“4096 B 与不改缓存时相同”不能直接比较 g150 与新代数所有场景：导航会保存 S+0xFD4 记录，其中包含 DAT 头 CRC 和记录 CRC，代码变化本身就使这些字节不同。A 应在同一设置语义和同一 B 版本下作成对比较；可从相同运行状态的副本检查新增缓存写入，也可分别严格验证 40 B 记录，再比较其余 S 字节及完整单元行/T。不能只忽略整条记录或只比较 W 次数。编码依据为 `core/eng_core.c:283-294`。

7. P8 要走原始半按后的直接重显序列；P9 的完整拍照序列与按拍后形态建立的夹具应分别记结果。当前引用的旧脚本包含显式恢复或预置状态，不能替代本次隐藏后拍照的连续路径。真机物理按键、拍照、RTOS 和 LCD 仍未知，本轮没有访问设备。

8. 在 g152 定稿上移植两个逻辑改动，重新确定数据块和容量基线。当前 `engine_v60_g152/.../kv2/kv_data.h:9-13` 已是 7,904 B 的 R3 块，`looks_data.py:18-40` 从旧数据生成压缩表。保留 g152 自己的块字节和校验，不能把 g150 的 17,384 B、`GXKV2R2`、`43405f6c…` 哈希约束直接带过去。缓存三个原函数仍在，P1-01 的补齐也应移植；增加 Looks 列表、进入卡片、回到 Looks 及关闭场景。`project_compute` 的 Looks 路径仍先经过 `kv_data_request`，见 g152 `core/eng_core.c:174-190`。

9. +224 B、+20 B 和余 1,760 B 只属于原 g150 原型。g152 尚在实现，当前读取的 manifest 中主请求为 106,376 B，已经高于本设计采用的 106,124 B 门槛。该开发快照不用于判定 g152 定稿；两项修复必须在定稿和新错误路径处理加入后，按最终 DAT 重测装载请求、段长与余量。快照哈希见 `static-results.json`。

本轮验证与边界以同目录 JSON 为准。未修改源码、原型或包，未执行 Git 操作、网络请求、子代理或真实介质访问。编译和 M32R 检查串行运行，`nice=10`，子进程同步等待；运行沙盒禁止网络及指定目录以外的写入。冻结输入复核与临时目录清理结果见 `cleanup.json`。

复审脚本曾在装载前绑定 DAT 断点，导致重显入口日志断言失败；改为装载后绑定后，四项原生路径检查完整通过。该失败与前述 48 B 结构声明失败均保留在 `review-check-failures.json`，没有计入通过结果。新实现的 22+3+13 场景、全部回归和完整拍照序列均未在本轮执行。
