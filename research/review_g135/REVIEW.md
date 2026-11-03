可以上测试卡

结论只对 gen 135 的这一对文件成立：`GXRCE.DAT` `57743bc105bc3d51b7fa65b44efd90afb022b2356d4e7846d470cc0c641c438a`（89,572 B，generation 135）和 v3.7 机身 `ilaunch3` `d00607405a5bd33290f99e9eda20df31a46386b6e0891cd5e62b15a9e3376283`。它的意思是：可以写到测试卡 B 上让用户上机试，不是放行发布；全程没有碰相机、存储卡和网络，没有启动子代理。

没有发现新的 P0/P1。上一轮阻断放行的 H07 父层问题（P1-02）在 gen 135 上不再复现（我复跑了 28mm 一个单元的 h07-parent 与 h07-parent-preview；另两个单元沿用实现者的记录）。仍然开着的都是继承问题：首次发布前的七行窗口（P1-01）、最终核对后的预览窗口（P2-03，本轮在新镜像上重新复现）、末端重绘窗口、普通预览失败后的重开。完整回归没有全部跑完，如实列在后面；没跑到的组和跑了但不是产品断言失败的组都不算通过。

静态已证：源码差异、身份绑定、包与尺寸、重新编译的布局。主机已证（M32R 指令模型，设备与图形叶函数为模型）：下面各表。未知：相机上的调度、显示、拍摄、存储持久性、真实堆布局。

## 问题表

| 级别 / 编号 | 新或继承 | 问题与状态 | 复现方式 |
| --- | --- | --- | --- |
| P1-01 | 继承 | 首次发布之前的七行窗口，OPEN。源码相同；真实调度可达性未定。另见 redisplay 报告里实现者自己列的剩余风险：OK 关闭→拍摄→推 ADJ 时真机进入 H01 的 part 值没有实测；H01 先发布后判断归属，归属不成立时会出现“八行名表 + 原厂 getter”的混合状态（v3.6 起就有）。 | 在 H01 发布八行之前插入方向键事件，观察原生七行列表的 store，再观察发布和恢复（`research/review_g126/cold_reentry.py`，g129 复审的 focus-cold 四案）。它不在 81 组里，本轮没有重跑，状态沿用。 |
| P2-03 | 继承 | 最终归属核对之后、进入原生预览之前换视图：预览照常进入（`previews` 1→2，`overlay` 32→21），无 S 写入。OPEN，已在 gen 135 镜像上重新复现。 | `research/review_g135/legacy/native_checks_g135.py --case preview-window --unit 28mm --crc-mode native`（经 `runner.py --crc-implementation native`）；切点 `0xd228`。注意旧脚本把切点写死在 gen 127 镜像偏移，原样运行会空转，见 PORT_NOTES §3。 |
| g124/P2-01 | 继承 | 末端重绘窗口，OPEN。绘制路径源码未变；本轮未重跑绘制本体。 | 同 g127 复审：在原生绘制调用之前失去归属，观察旧行绘制器与 `0x201fd392` 对 `0x205d4f64` 的 store。 |
| P2-04 | 继承 | 普通预览服务失败后的重开刷新，待核对。`pending-read` 与 `preview-deferred` 两例（切点移到 `rv_irq_save` 之前）通过：切换后 pending=1、无写入、无预览，重开恢复八行。这只覆盖归属丢失，不推及所有普通 I/O 失败。 | `native_checks_g135.py --case pending-read / preview-deferred`。 |
| g129/P2-01 | 继承，内存风险 | 主请求 107,760 B 需要连续块；真机剩余连续堆未实测。见“尺寸与堆”。 | `research/review_g135/heap_check.py`；`captures/diag-v21-field-20261029/READINGS.txt`。 |
| g135/P2-01 | 新，工具链 | 用户条目命令行工具不随 gen ≥129 的源码树交付，且其 `ui_data.py` 拒绝 gen 135 的 DAT（`len>65536` 与 `generation!=127`，放宽这两条后仍在第七段长度处失败）。`users` / `other-users` 共 9 组因此无法执行（`evidence/user-tool.json` 缺失）。不是产品断言失败，但意味着新格式下的用户条目没有命令行构建路径，也没有回归覆盖；GXUI v1→v2 的转换只剩 g129 复审当时的主机抽样。 | `fenced.sh runner.py research/review_g124/tool_acceptance.py` → `ValueError: invalid DAT envelope`（`firmware/engine_v53_g135/candidate/ui_data.py:91`）。 |
| g135/P2-02 | 新，交付整洁 | (a) `firmware/engine_v53_g135/resident/` 是 gen 131 时的旧副本，其中 `hooks.c` 仍只认 part 2；真正的 v3.7 常驻在 `firmware/resident_v37`。DAT 的身份只由 `build135.py` 里对 `resident_v37/…/trust.json` 的断言绑定，已核对 DAT 头与 ilaunch3 里都是 v37 的 id（`4a26168b…`），没有旧 id；风险是日后有人按 g135 目录重建常驻。(b) `firmware/engine_v53_g135/candidate/__pycache__/ui_data.cpython-314.pyc` 在实现者清理之后又出现（时间戳 03:45:55，早于我第一次计时的 03:53；是 Python 3.14 的缓存，我只用 `/usr/bin/python3 -I -B`（3.9，不写字节码），也没有导入过它），会让 `check_delta.py` 的文件集断言再次失败。(c) REPORT.md 写“每个单元 314 帧”，实际 50mm 314、28mm 316、mount 316（我独立复跑的 50mm / 28mm 与实现者逐字节相同）。 | `diff -rq firmware/engine_v53_g135/resident firmware/resident_v37/resident`；`ls firmware/engine_v53_g135/candidate/__pycache__`。 |
| g135/P2-03 | 新，验证工具 | 旧套件里读旧布局 / 旧偏移的地方（safety 的陈旧布局文件与 `g+2523`、`native_checks` 写死的镜像偏移、`setup` 里 62,676 / 63,380 的旧 DAT 长度断言）不改读取就会产生假失败。已逐处列出并修正读取，没有删除任何首发、归属、半按、锁定、RPC、邻字节检查。风险是以后的人直接用原样旧脚本得到“失败”或空转。 | 见 PORT_NOTES.md、WRAPPER.md。 |

三条 safety 旧失败（panel_rollback、ready_warm、write_latch）本轮在 gen 135 上用原读取重新得到同样的三条（124 家族 50mm 逐条核对，28mm 返回码同为 1），用修正读取三单元各 8/8，与 `research/g129_safety_triage` 的定性一致（测试侧：旧布局、旧偏移、旧数学期望）。

## 1. 源码差异（相对 gen 131）

我自己对 `firmware/engine_v51_g131` 与 `firmware/engine_v53_g135` 做了 `diff -rq`（排除 `local`、`__pycache__`），只有这些文件不同，其余逐字节相同：

- 三处 part 判断：
  1. 常驻机身 v3.7 的 `owned()`（`ilaunch3`，不在引擎树里；接受的 part 取值由 `accept_parts.py` 在 0…7 上实测为恰好 1 和 2）：与 gen 120b 的机身相比只有 102 字节不同，分三块：校验和 (`0x16e–0x16f`)、`owned()` (`0x9118–0x9165`，对应 `0x20053F18–65`)、resident build id (`0x9808–0x9827`)，没有别的。
  2. `candidate/engine_services/services.c`：`rv_view_owned` 里 `RV_BYTE(0x205a280f)!=2` → `!=2 && !=1`。
  3. `candidate/engine_services/native_seed.c`：同一判断拆成 `!=2 && !=1`。
  后两处相对 g131 的增删行与 `engine_v52_redisplay` 相对其 gen 127 底座的增删行逐行相同（我对 `diff -u` 的增删行做了比较）。
- v37 身份绑定：`candidate/common.py` 的 `UPSTREAM` 指向 `resident_v37`；`build135.py` 与 `build131.py` 唯一不同的两行是 trust 文件路径和 `resident_build_id` 断言（`4a26168b…`）。DAT 头 `[80:112]` 等于该 id，`ilaunch3` 里该 id 出现 1 次、旧 id 出现 0 次，ABI id 也匹配。
- generation 135 下的四处同步：`gate.c`（`build_number==135 && n==8 && length==20776`）、`eng_data.c`（第七段 20,776）、`ui_v2_data.c`（`build_number!=135`）、`pack.py`（`build==135`），每处只把 131 换成 135。
- 构建侧：`common.py`（resident 指向 v37，围栏路径）、`build131.py`→`build135.py`。

DAT 与 gen 131 的差异：第 0 段（引擎）+16 B (60,636→60,652)，第 3、4 段各有 5、10 个字节不同（含义未逐字节追查），第 1、2、5、6 段逐字节相同；第七段 20,776 B 与 gen 131 逐字节相同，其中 GXKV2R2 块与 `firmware/kv2_modules/data_ui/local/gxkv2r2.bin` 逐字节相同；头部 50 个字节不同（长度、CRC、generation、resident id、入口与段表）。`engine.bin`（SHA 前缀 `05067322…`）在 DAT 里恰出现一次，`full-r13/GXRCE.DAT` 与包内文件相同。包 30 个文件，28 个固定文件与 gen 120b 及 `package_v37_redisplay` 相同，`CARD_SHA256SUMS` 全部匹配。实现者的 `SHA256SUMS` 153 项我全部核对为 OK。重新编译的布局（`layout_only.py`）与实现者的 `layout.json` 逐字节相同。独立证据：`package-check.json`、`layout-diff.json`。

## 2. 完整回归与附加套件

见 [REGRESSIONS.md](REGRESSIONS.md)（81 组 + 附加套件）与 `regressions.json`。方法、重绑边界与进程数见 [WRAPPER.md](WRAPPER.md)；修正读取的前后对照见 [PORT_NOTES.md](PORT_NOTES.md)。

81 组的结果（每组由本复审自己的运行器、对 gen 135 DAT + v3.7 机身执行；旧脚本未改）：

| 结果 | 组数 | 内容 |
| --- | --- | --- |
| PASS | 30 | locked、nested、cutpoints、half：两个家族 × 三个单元共 24 组；lock-exits、view-reentry、reentry-all-keys：50mm 两个家族共 6 组 |
| 已归类、非产品断言失败 | 24 | 原读取 safety 2（50mm、28mm 的 124；三条假失败，修正读取三单元各 8/8）；旧显示设计 8（labels 6、124/50mm 的 transitions 与 values 各 1）；已退役函数 5（project，`uv_levels` 不存在）；工具前提缺失 9（users / other-users） |
| 时间盒内未闭合 | 27 | NOT_RUN 24、TIMEBOX 3：28mm / mount 上的 lock-exits、view-reentry、reentry-all-keys，以及 transitions / values / 原读取 safety 的其余单元，逐组名见 REGRESSIONS.md 末尾 |

没有出现任何无法归类的失败，也没有把设计变化、工具缺失或没跑到的组记为通过。对设计变化的套件，我做了修正读取的复制品并跑出了结果（transitions 50mm / 28mm 各 42/42 PASS；values 50mm 的 ±9 步进、clamp、虚拟滚动、Default 双击 PASS，仅 back-from-second-pair 一个旧光标期望是导航记忆的设计变化）。附加套件：history123 三单元 9/9，settings_cases 三单元 36/36，g122 的 27 条历史记录按 gen 135 契约逐条判断全部 PASS（[HISTORY122.md](HISTORY122.md)），safety 修正读取三单元 8/8。

没跑到的 27 组里没有哪一组是 gen 135 改动专属的：半按相关的 half 组在三个单元、两个家族上都 PASS，part 判断本身有 accept / accept_parts 覆盖，H07 有 h07-parent 与 h07-parent-preview 覆盖。我把“28mm / mount 的 lock-exits / view-reentry / reentry-all-keys 没跑”作为未闭合项交给下一轮，而不是写成通过。

## 3. 抽样独立复跑

- `accept.py`（半按修复，v3.7 机身）：28mm、mount 各 `ACCEPT_DONE`。我另外把强制 part 的循环从 `(0,4)` 扩到 0…7（`accept_parts.py`，三单元）：只有 part 1、2 被接受（`jl_delta=0`、八行），0/3/4/5/6/7 均 `jl_delta=1`，每次闸门命中 2 次；写入全为 0。
- `h07-parent` 与 `h07-parent-preview`（28mm，native CRC）：晚到的 S store 0、晚到的预览 0。
- `product_menus.py`（50mm、28mm 独立复跑）：帧序列与实现者的记录逐字节相同；mount 因为占进程槽被我终止（实现者该单元 PASS 保留）。
- `boundary_sweep.py`（我自己写的，替代已退役的 `uv_levels` 范围测试）：自行编译主机引擎库，3 个单元 × 8 个配方 × 10 个 control，接受 3,469 个点（表内点和默认值），拒绝 18,484 个表外值（−40…+40、±127/128、255/256、32767、−32768、±1000），拒绝时输出缓冲 552 B 全部未被改动；未列入配方的 control 非默认值全部拒绝 (3,510)；非法配方号 0/9/10/255/256/65535 全部拒绝。

## 4. 尺寸与堆

| 项 | 值 |
| --- | --- |
| 主请求 | 107,760 B = 1,104 + align4(89,572 + 10,684) + 6,144 + 256（我独立算出，与实现者一致） |
| 设计上限 / 余量 | 108,124 B / 364 B（0.34%）；gen 131 为 107,744 B，+16 B |
| resident 固定上限 | 122,192 B，余量 14,432 B |
| 原生块跨度 | 加载区 620 + 主块 107,772 + UI 快照 1,980 = 110,372 B；262,144 B 池空池时剩 151,772 B 连续 |

真机读数（`captures/diag-v21-field-20261029/READINGS.txt`，generation 132 的诊断 DAT，主请求 55,896 B，开机后第一次打开和拍一张之后各一次，两次相同）：空闲链哨兵的 next = `0x207124DC`，减去池基址 `0x20704800` 为 56,540 B，**恰好等于** 哨兵 12 + 加载区 620 + 诊断主块 55,908（`heap_check.json` 逐项核对）。能由此得出的：这两个时刻没有任何原生块排在我们的会话块之前，也没有原生块紧贴在它后面（否则第一个空闲块的起点会后移）。读数页显示的是 `BADR0000`：读取器在边界 / 哨兵阶段就判了失败，没有走到逐块核对（失败原因本身我没有追查），所以不能由它推出“整池里没有其他原生块”，更不能推出拍摄、回放、USB 时的峰值。在这个前提下 gen 135 的会话（多出 51.9 KB）落在同一起点，之后至少还有 151,772 B 连续；最大的已知原生请求 77,336 B 放得下。

仍然成立的风险（继承自 g129 的堆报告，数值按 107,760 B 重算）：调整文本读取在打开失败时漏掉 32 KiB 的释放，连续三次后剩 53,396 B，不够 77,336 B 的后续请求；两次后剩 86,188 B，够。堆报告里的最紧并存模型剩 7,248 B，再要 32 KiB 会失败。这些并存在真机上是否可达仍未知；若加载阶段分配失败，常驻会退役，菜单不出现、看到原厂项（本次开机不再重试）。364 B 的余量意味着任何后续修复只要再增加 0.4% 就会碰到设计预算。

## 5. 局限

- 没有相机、LCD、拍摄、物理断电和真实 RTOS 调度证据。
- 没有独立重跑：通信复核 (48,890 条)、target-math / gate 阶段、GXUI v1→v2 转换（见 g135/P2-01）。
- 进程数：两次短暂超过 3 个（见 WRAPPER.md），均已停止。终止了两个作业（product-menus-mount、port-values-28mm），见 `cancelled.jsonl`。
- 上机提示：首先看 ADJ 里有没有八行配方菜单。只看到原厂项说明加载阶段分配失败（堆），不是菜单逻辑；恢复用卡 A + 50mm（“+ & playback”，机身 v3.7 要带着 50mm 刷）。
