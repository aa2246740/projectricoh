可以上卡。仅针对本次 v3.6 BODY。

v3.5 的唯一固件阻断 P0-01 已修复。独立重放的两个 H08 故障反例、双向滚动反例及 H06/H08 重入均未再进入危险原生续体；规定的旧场景结果与 v3.5 相同。没有发现新的固件回归。另确认一处非阻断的旧 harness 诊断断言过时，详见后文。

审查日期为 2026-10-27，台北时间。审查对象是 `ilaunch3` SHA-256 `50720c80696ca88f25dc25a85285acd0e0f19906e1d7da1dd404f6cc243f9008`。本结论是用户指定的 body 差量审查，不替代 gen 117 重绑、最终整卡包或实机验收。本轮没有访问相机、卡或真实 IROM，没有刷机，没有使用子代理；所有写入留在本目录。结束时核对 10663 个冻结文件，内容均未变。

## P0 的独立结果

从实际包加载 v3.6 resident 与菜单机器码，移除原生 `0x20271FEC` 固定返回 1 的替身。真实 getter 会读取、校验 S 模式。测试使用原 gen 116 DAT，仅在文件边界的内存副本中重绑 resident build id 并重算头 CRC，`0x100` 起的全部 payload 不变。没有生成新 DAT。

viii-b 按原序列执行：应用 01，原生重开 ADJ，仅破坏 detached UI snapshot magic 一位，再按 `0x20`。本次 H08 检查失败后，根状态为 6，flags 为 `0xA3`，原因仍是 `RV_CHECK_UI=7`。S+0x36E 保持 1，`0x202BB96C` 执行 0 次，未观察到 `0x20268774/0x20268798` 的模式回写。故障前后的 01 深层摘要都为：

```text
19a2f5a0a52a203de1f198be11054da0c31706eec7e352822b4d2320aae62455
```

首次发布、尚未 OK 的同类故障也保持模式 1，原生 H08 续体 0 次，深层写入 0 次。这一项保持的是原厂 04，不能写成“已经应用完整 01”。`0x1F` 方向的坏快照反例同样保留 01。

另用同一套真实 getter 重放 v3.5 作阳性对照，仍得到模式 5、H08 续体 1 次和未变的 01 深层行。因此本轮 harness 能检出旧 P0，没有用最终 S=1 掩盖中途原生回写。

证据为 [viii-b](h08-retire-adversarial.json)、[首次发布](h08-first-adversarial.json)、[双向滚动](scroll-both-adversarial.json)、[v3.5 阳性对照](baseline-control-adversarial.json)。

## 场景表

H07/H08 列分别统计 `0x202871DC` 和 `0x202BB96C`。所有当前 v3.6 主矩阵均使用真实模式 getter；diag_early 在根初始化后一直为 0。

| 序列 | 最终 S+0x36E | 深层结果 | H07 / H08 续体 | 根状态 / flags | 判断 |
|---|---:|---|---|---|---|
| i：01 → OK → MENU。 | 1 | 01 | 0 / 0 | 3 / 0xa2 | 与 v3.5 好结果相同。 |
| ii：01 → OK → 滚动并尝试 02 → OK → MENU。 | 1 | 01 | 0 / 0 | 3 / 0xa2 | 与 v3.5 相同；列表已关闭，02 未选中。 |
| iii：01 → OK → 只滚动 → MENU。 | 1 | 01 | 0 / 0 | 3 / 0xa2 | 与 v3.5 好结果相同。 |
| iv：01 → OK → Fn2 → OK → MENU。 | 1 | 01 | 0 / 0 | 3 / 0xa2 | 与 v3.5 相同；关闭后 Fn2 不打开编辑器。 |
| v：01 → OK → 关闭 → 重开 ADJ → 02 → OK → MENU。 | 1 | 02 | 0 / 0 | 3 / 0xa2 | 确实应用完整 02。 |
| vi：01 → 主 MENU → Image Settings → 原生模式。 | 阻塞前为 1 | 阻塞前为 01 | 0 / 0 | 3 / 0xa2 | BLOCKED，与 v3.5 相同的系统链表模型缺口。 |
| vii：真实 ig_event 的 inflight 内嵌套 H07，再 MENU。 | 1 | 01 | 0 / 0 | 3 / 0xa2 | 与 v3.5 好结果相同。 |
| viii-a：01 → 重开 → 坏快照先由 H07 检出，再使用 ADJ。 | 1 | 01 | 0 / 0 | 6 / 0xa3 | 与 v3.5 好结果相同。 |
| viii-b：01 → 重开 → 坏快照先由 H08 检出 → MENU。 | 1 | 01 | 0 / 0 | 6 / 0xa3 | P0 已关闭，完整 01 保留。 |
| first_fault：首次发布，未 OK，坏快照先由 H08 检出。 | 1 | 无配方深层写入 | 0 / 0 | 6 / 0xa3 | 保持纯 04，深层写入为 0。 |

序列 ii 的 `moves_to(02)` 实际返回 false，不能声称第二次 OK 切换了 02。真正切换由序列 v 覆盖，02 深层摘要为 `e50a09a1ea5199b1f33479fc4be41ccb61de03466a6636ed84e40ab7b7d46269`。另独立展开 DAT，逐字节核对 01、02、04 各九行共 503 B，以及 T 的 2 B 控制值，全部相同。

主 MENU 的原厂 state-9 入口仍在 `0x2005F4C0` 读未建模链表，报 `unmapped memory 0x8/4`。未手写系统链表或游标跨过它，完整主 MENU 选择仍未验收。这是基线已有的模型阻塞，没有当成相机故障或通过项。

证据为 [主矩阵](adversarial.json)、[机器可读表](scenario-table.json)、[深层字节](deep-rows-comparison.json)、[主 MENU 阻塞](menu-native-adversarial.json)。

## Guard、顺序和出口

实际 `early.isra.0` 位于 `0x20053FB4`。先检查 `RF_PUBLISHED`。H07 保留关闭出口；H06/H08 只有固定原生计数字节 `0x2022F5AC == 8` 才修改帧。入口已经排除 H03/H04/H05/H09，其余小于 6 的 hook 在 helper 返回，因此不存在 H09 被错判成 H08 的可达路径。`RV_BYTE` 是 volatile 读取。

| 提前返回路径 | 本轮实际执行 | 结果 |
|---|---|---|
| H08 rv_check 退役。 | viii-b、首次发布及双向故障。 | 当次跳过，模式和深层行保持；退役恢复七行。 |
| H06 rv_check 退役。 | 坏快照后调用真实 Fn2 入口。 | H06 续体 0 次，最终七行，完整 01 保持。 |
| inflight。 | 在真实 ig_apply 内分别嵌套原生 H06/H08。 | inflight 实际为 1；续体均为 0，嵌套调用返回成功。 |
| RF_BUSY。 | 仅对根 flags 注入 busy 位，执行真实 H06/H08。 | 两条路径均命中 busy gate，没有 S 写入。 |
| !owned。 | 八行仍在时仅清零根 ui_restore[0]，执行真实 H06/H08。 | 两条路径均命中 owned gate，没有 S 写入。 |
| disabled 且八行仍在。 | 明示破坏恢复标记及快照，让真实退役无法收回八行，再调用 H06/H08。 | 两条路径均命中 disabled gate，没有 S 写入。 |
| 已恢复七行。 | 真实退役后重新打开，滚动并确认；另调用 Fn2。 | Natural=10、黑白=3，H08 续体共 2 次；H06 续体也放行。 |

busy、ownership、恢复记录故障都是标注的测试注入。嵌套测试控制中断点和测试栈，证明真实指令下的可达分支，不证明相机调度一定会在该时刻重入。

顺序在实际机器码中是 `0x200528B0` 调用 early，`0x200528BC` 才调用 retire。early 只读取 flags、hook 和固定计数字节，写共享保存帧的 f[1]/f[7]；它不读 session 或失效 UI 分配，也不调用引擎。retire 收回原生表、清空会话并禁用本次启动；其恢复过程只用根内恢复记录和固定 native slots，不读取这个保存帧。因此先确定本次八行调用的 skip，再退役，不会留下继续访问已退役对象的出口。busy、!owned、disabled 的分支在调用 early 前也没有恢复行数。

H06 的 `rv_skip_06=0x20052BB4` 先弹出 hook 保存的 LR，再跳 `0x202BE6A8`。该原生尾部把 r8 作为返回值，再恢复 LR、r11、r10、r9、r8。f[7] 正是共享帧中的 r8，置零符合这个出口。H08 的 `rv_skip_08=0x20052C2C` 也先弹出 hook LR，再跳 `0x202BCF58`，完整弹回 fp、LR、r12 至 r8。H07 的 `rv_close_07=0x20052BE8` 保留调用方 LR，调用原生 layer 后返回，不进入原生 setter。

七条独立分支探针逐项检查 SP 和 r8 至 r13；实际 inflight 内的 H06/H08 另在恢复被中断 CPU 之前检查这些寄存器，均平衡。正常 OK 和随后提前 MENU 的 H07 也各核对一次。共享桩保存、恢复 PSW；未把整个原生函数入口至出口的条件位不变当作契约。

证据为 [七条分支](guard-matrix-adversarial.json)、[H06 重入](reachability-adversarial.json)、[实际 inflight 寄存器](inflight-register-balance.json)、[H06 退役](h06-fault-adversarial.json)、[七行 H06](native7-h06-adversarial.json)、[七行原生选择及 H08 重入](extra-adversarial.json)、[H07 寄存器](h07-register-balance.json)、[helper 机器码](early.asm)、[resident 桩](resident/disassembly.log) 及 `native_h06.asm/native_h08_exit.asm`。

## P3 删除和非阻断发现

resident 实际链接的运行代码已无 diag_early 读取；root+232 仅保留布局，根重置时清零。H09 的实际 observer 读 root+7 的 grain，再进入 rv_grain；引擎 grain_snapshot 仍调用 es_grain_commit。gen 116 黑盒代码对 diag_early 的读取只写入报告字段，不控制应用、grain 或恢复。当前 v3_checks.c 的有关断言已经改为诊断值为零，ASan/UBSan 通过。

P2-01：`firmware/image_v36/harness_scenarios/run_v35.py:166` 仍要求 inflight_h07 的诊断低 16 位等于 `0x307`。本轮实际调用该 helper，先通过关闭出口、模式保持、没有原生 setter 的判断，随后输出：

```text
FAIL inflight_h07 ('diag', '0x0')
```

所以“所有 host/harness 正确性断言都不依赖旧诊断写入”这一说法不成立。这个 helper 被它自己的 main 引用，但当前 run_v36_checks.py 的四个阶段不调用它。用户可见后果是单独运行旧 helper 时得到假失败；它没有造成相机行为回归，不阻断本次 body。应更新该辅助断言，以出口、续体及模式为依据。原 resident.h 的诊断注释也已过时；本轮按只读规则保留原文件。

证据为 [实际 helper 输出](legacy-assertion.stdout.log)、[断言记录](legacy-diag-assertion.json) 和 [源码差分](delta-source.diff)。本轮未修 builder 文件；这一测试报错本身不需要回刷。设备恢复规则统一列在文末。

## 重建、ABI 和二进制边界

| 对象 | 字节数 | SHA-256 |
|---|---:|---|
| genuine 1.51 ilaunch3。 | 3993340 | `da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7` |
| 独立重建 v3.6 ilaunch3。 | 3993340 | `50720c80696ca88f25dc25a85285acd0e0f19906e1d7da1dd404f6cc243f9008` |
| 独立重建 resident.elf。 | 10672 | `5d66184ce33f280aa370ebfc1753fe74e8ad398f01558406909733cec779acff` |
| 原 gen 116 DAT，只读测试输入。 | 66488 | `1e033dfbcc3ca0bec0e1e5befbdb5579950e9aa8aacfbfd56f8c7342b9a97864` |

官方 ZIP SHA-256 是 `3705984b8433c40d2ed4fd2600c11f03ed8a6de7dbe7f66efd38ee5ca15fc898`。正向构建与原生执行始终使用 genuine 官方输入，没有把 `04168d00…` mutant 当官方。image verify 生成并拒绝错误 recovery 等负例，不作为正向输入。

resident 与 ilaunch3 都逐字节复现。build id 为 `b779cc756a740506415ca5df8eb5c8f08e1b04ea9d8c4c614f7ae971e92b94f7`。ABI 独立按原 ABI 域及三个头文件重算为 `d7387c3670059c325186de3af1b3d5c6`；resident.h、abi.h、engine_services.h 与 v3.5 全字节相同，trust.json 仅 resident_build_id 不同。运行源码只有 hooks.c 改动；另外只有构建路径及 build-id 域、host 用例改变，21 个其余 resident/engine-services 文件相同。

resident.ld:22 与 v3.5 完全相同，仍断言代码末端不超过 `0x20054700 - 200`。实际末端 `0x20054638`，payload 7884 B，root 前 200 B，门槛内可再增加 0 B。独立尺寸重跑得到旧逻辑 7880 B、只删 P3 后 7832 B、v3.6 为 7884 B，确认回收 48 B、净增 4 B，没有挪用 reserve。

| 比较 | 不同字节 | resident 内 | 七个 hook 内 | 0x16C 校验内 | 窗口外 |
|---|---:|---:|---:|---:|---:|
| v3.6 对官方。 | 7606 | 7567 | 36 | 3 | 0 |
| v3.6 对 v3.5。 | 6953 | 6944 | 7 | 2 | 0 |

七条 BRA 均从实际 ilaunch3 解码至 ELF 的 H01/H02/H05/H06/H07/H08/H09 符号。其他 hook 和原生 ADJ 两个数据字段未改。30 个 boot/OSD 窗口逐字节等于官方。提取反汇编的驻留区和原生指令地址也核对了相应文件偏移加 `0x2004AE00`。

从文件 0x200 起，按 `sum(byte[i] * (i%6+2)) mod 2^32` 独立重算，官方为 `0x6ACDB212`，v3.5 为 `0x6A7FF8D4`，v3.6 为 `0x6A7FEFC5`，都等于 0x16C 字段。

最终 `image_v36/local/package/SD_ROOT` 实际只有 ilaunch3。审计候选的 SD_ROOT 有 29 个官方名字，其中 28 个同伴文件逐字节等于 genuine ZIP，候选 ilaunch3 也等于最终 body。三项 body 交付清单全部核对。30 文件整卡包尚未在这个 body 交付目录组装，不能说它已经验收；gen 117 与整卡包属于另一个审查范围。

证据为 [独立重建](resident-rebuild.json)、[源码与 ABI](delta-source.json)、[原始差分](delta-source.diff)、[二进制检查](structural.json)、[窗口摘要](windows.json)、[尺寸重跑](byte-accounting/size.json) 及 [image verify](image/verification/verification.json)。

## 28mm、remember-last 和掉电

28mm 在 ready=0、link=1 时首次 H01 保持七行、state=0、flags=2，没有 attempt 锁。用原生就绪 setter 写 1 后，当前列表仍为七行；关闭再打开才变八行。50mm 首次打开就是八行。五组 ready/link 与 MOUNT 门禁全部保持七行，没有文件打开或 RPC，也没有锁死后续尝试。

掉电检查仍是 body 侧模型。本轮让真实 gen 116 指令通过内存文件边界保存 02；下次冷启动仅保留实际生成的文件字节与上一轮 S，重新加载原生 UI、root 和官方单元行。首次 H01 前为 Standard=1、官方深层行；读回 GXLS 后高亮 02，但仍无深层写入；OK 后的完整 02 与上次实际深层摘要完全相同。remember-last 仍只记住高亮槽，没有变成开机自动应用。

因此冷启动模型仍满足“纯 04，或确认后的完整配方”。本次 H08 退役故障也保持完整 01，排除了旧 P0 的未选中 Setting2 混合态。用户后来主动选择原生 Natural/B&W 时，旧深层行仍在，这是 v3.5 已有行为；本轮没有把“原生选择可用”说成“已恢复原厂深层行”。实体断电、持久化介质及拍摄效果未验收。

证据为 [五组门禁](p2-adversarial.json)、主矩阵中的 28mm_retry，以及 [两次冷启动模型](power02-adversarial.json)。

## 实际执行和保留记录

所有 Python 都使用 `/usr/bin/python3 -I -B`。构建和映像工具先复制并改输出路由；原 harness 只读导入，显式重定向结果、路径门禁和 decode 缓存。原文件均只读。改动记录在 `script-routing.diff`、`build-routing.diff`、`structural-routing.diff`、`power-binding.diff`、`scroll-expectation.diff` 与 `size-routing.diff`。各次 argv、退出码和耗时见 `*.execution.json`、`executions-*.json`。

| 本轮执行 | 实际结果 |
|---|---|
| resident 原源码、原 GCC/LD 和参数独立重建。 | ELF 全字节相同，build id 相同。 |
| v3_checks.c，ASan/UBSan。 | `PASS_HOST checks=157249 ASan+UBSan=1 engine=double native_m32r=0`。 |
| image_v36/verify.py 的隔离副本。 | `VERIFICATION_PASS deterministic_files=68 rejections=14/14 objdump_branches=7 protected_unchanged=3003`。 |
| tools/native_harness/conformance.py。 | `PASS python backend conformance unrecognised instruction 0x103000`，最后一段是预期的未知指令拒绝项。 |
| 原 scenarios.py。 | 20 项，0 violations，0 errors。这组使用旧 body/旧代 DAT，不替代当前矩阵。 |
| run_v36_checks.py matrix / faults / guards / supplement 的隔离副本。 | 四阶段全部完成；各子命令退出 0。supplement 中主 MENU 仍按上述原有 BLOCKED 记录。 |
| guard_matrix.py、native7_h06.py、inflight_balance.py、h07_balance.py。 | 新 guard 的分支、合法七行操作和寄存器平衡通过。 |
| power02.py、baseline_control.py、measure_size.py。 | 记忆槽/冷启动、旧 P0 阳性对照及尺寸重跑通过。 |
| legacy_assertion.py。 | 证实旧 helper 因期待诊断 0x307 而假失败；测试包装器以“成功复现过时断言”退出 0。 |

首轮结构脚本沿用旧包的 30 文件假设，按实际 body 单文件与审计 29 文件布局修正后重跑通过。首轮双向脚本加载了旧版本“最终模式应为 5”的反例断言，实际轨迹已为 1；首轮掉电模型误把文件边界切回旧 build-id 头，loader 拒绝后未保存 02。两项原始失败日志、JSON 和解释留在 [initial-routing-failures](initial-routing-failures/explanation.json)。修正仅涉及审查脚本期望与同一份内存 header 重绑；随后完整重跑 faults 阶段及 power02。没有修改固件来消除这些失败。

主矩阵的外层 runner 与子进程曾共用 stdout 文件名，外层退出行覆盖了子输出开头。覆盖前保存的原始首行是 `matrix.stdout.first-line.raw`；`matrix.stdout.full.log` 用该原始首行和原文件余部还原，原文件也保留。完整判断以逐步 JSON 和独立 acceptance 为准。

本轮实际执行了 resident、engine 和相关原生菜单指令。文件、RPC 单元、绘图及部分系统调用仍是 harness 边界模型，CRC 有原 harness 的等价加速。静态读取的内容包括 v3.5 基线报告、原反例、失败尺寸方案以及 builder 的 reachability 等证据；当前结论使用本目录重新执行的结果，没有拿 builder 自报代替验收。

## 刷入与恢复

本结论只放行上述哈希的 body 部分。统一机身刷入时必须挂 50mm，gen 117 与最终整卡包仍由各自审查覆盖。若设备需要恢复，固定使用卡 A 的 Stage2l-50mm，关机、挂 50mm，按住「+ 和回放」开机。本轮没有执行刷入或恢复。
