停止构建并交回决定，未产出通过验收的 gen 120 卡包候选。

三项状态为：P1-01 未修复，已证明 H07 关闭路径需要修改 resident；P1-02 未修复，初版在首次 W 前持续失败时仍无提示；编译改码闭合为 INCOMPLETE。实际机身 resident、官方固件及本轮冻结的既有输入均保持原样，本轮只在三个获准目录内修改配方构建副本和测试材料。遗留风险是 H07 仍会恢复、撤掉原生其他菜单，错误提示仍有缺口，完整回归与 A/B/C 未完成，诊断产物不可上卡。

## 停止原因与原生机器证据

初版已把通信归属监视推广到 Fn2、H07 和面板入口。三个单元的 Fn2 首次通信切换均通过，切换后迟到 UI 写入为 0，单元保持完整 04。

但在三个单元的真实 OK 路径上，配方包均到达 `release_view`，返回 `RV_CONSUMED`、reply.status=`RV_OK` 后，resident 仍执行 `rv_ui_abort` 和原生关闭出口。每例都有 9 次切换后 UI 写入；官方其他菜单构造完成时 activity=7、overlay=21，收尾后 overlay=0。单元是完整 04，W=0，root 保持 READY=3，排除了配方部分写入或退役引发这一关闭的解释。

| 单元 | Fn2 首次通信切换 | OK 首次通信切换 | 证据 |
| --- | --- | --- | --- |
| A12 50mm / jlaunch | PASS，0 次迟到 UI 写入 | FAIL，9 次迟到 UI 写入 | [Fn2](native/entry-switch-50mm-fn2-at1.json)、[OK](native/entry-switch-50mm-ok-at1.json) |
| 28mm / qlaunch | PASS，0 次迟到 UI 写入 | FAIL，9 次迟到 UI 写入 | [Fn2](native/entry-switch-28mm-fn2-at1.json)、[OK](native/entry-switch-28mm-ok-at1.json) |
| MOUNT / l08firm | PASS，0 次迟到 UI 写入 | FAIL，9 次迟到 UI 写入 | [Fn2](native/entry-switch-mount-fn2-at1.json)、[OK](native/entry-switch-mount-ok-at1.json) |

原生其他菜单由第二 CPU 上下文运行官方 item-7 arm `0x202BA380→0x202BA3C8` 和构造器 `0x20285E00` 打开，两个上下文共享 RAM、使用独立栈。正常菜单、光标和 resident 状态未手工预置，`0x20271FEC` 固定返回替身已移除。通信、文件和部分系统边界仍是模型；没有触碰相机或存储卡。

根因在冻结 v3.6 的 [hooks.c](../../firmware/resident_v36/resident/hooks.c)。它在调用配方包前把 `f[11]` 保存为局部 `keep`。配方包返回后，只要 H07 的 `keep==0`，就执行 `rv_ui_abort`，并把出口改成 `rv_close_07`。这两处没有再次确认菜单归属。

| 冻结机器 PC | 动作 |
| --- | --- |
| `0x20052990` | 把调用者保存帧中的 keep 装入受 ABI 保护的 r12。 |
| `0x200529C4` | 调用 `rv_engine`。 |
| `0x20052AA4` | `RV_CONSUMED` 路径再次检查已保存的 r12。 |
| `0x20052AAC` | keep=0 时调用 `rv_ui_abort`。 |
| `0x200529EC` | 选择 `rv_close_07`，覆盖原来的 `rv_skip_07`。 |

`RV_PASS`、`RV_CONSUMED`、`RV_CLOSE_AND_PASS`、`RV_FAULT` 四个合法返回值在 keep=0 时都会进入恢复和关闭流程；域外返回值又会被 `rv_engine` 转为 `RV_FAULT`。reply 没有取消该收尾的字段。因此，在遵守现有 ABI、保存寄存器和调用者栈约定的配方包接口内，返回值无法解决这一项。只清除恢复记录也不能阻止后续原生关闭出口。

需要由 resident 在 `rv_engine` 返回后、恢复或原生关闭前再次核对菜单归属。若归属已变，应保留跳过当前旧事件的出口，且不写原生其他菜单。该修改超出本轮授权，故触发用户指定的停止条件。[机器反汇编](resident-h07-machine.txt)、[逐单元证据与四返回值结论](resident-h07-constraint.json)。

## resident 字节预算

| 项目 | 从原 ELF 和链接脚本重读的值 |
| --- | ---: |
| 代码起点 | `0x2005276C` |
| 代码末端 | `0x20054638` |
| 代码长度 | 7,884 B |
| root 起点／长度 | `0x20054700` / 256 B |
| 总窗口／已占用 | 8,340 B / 8,140 B |
| 实际间隔／链接要求保留 | 200 B / 200 B |
| 保持现有断言时允许的代码净增长 | 0 B |

`resident.ld` 的断言仍要求代码末端不超过 `0x20054700 - 200`。若 H07 归属复核增加 N 字节，必须在 resident 内回收至少 N 字节，才能保留这 200 字节。新检查的实际编译增量未知；依照停止条件，没有编译修改版 resident，也没有降低保留空间。[可重跑预算检查](resident_constraint.py)、[预算 JSON](resident-byte-budget.json)。

## 另外两项及未完成的验收

P1-02 的初版尝试只增加 `ENG_IO` 提示锁定条件，但真实 50mm 第一次通信及后续通信持续失败时，`finish` 收到的是 `ENG_REJECTED=1`。该次为零 W、完整 04，root 最终 DISABLED=6，下次仍只有原生七行。这个实际状态说明初版没有修好 P1-02；停止后未再改码或构建。[原生记录及 finish 参数](native/failure-boundary-50mm-at1.json)。

gen 119→初版 120 共 132 个逐名符号义务，100 个共享改码、31 个共享同码、1 个新增。122 项通过本地 A 检查；其余 9 个改码函数和新增 `start_view` 未完成 B/C。`rv_call` 的 119→120 变化通过 A，但 118→119 的遗留分支义务仍未闭合。追加的 dispatcher 差分在停止前只完成部分服务，进度记录明确为 INCOMPLETE，不计作全函数通过。[逐名表](codegen-closure.tsv)、[状态 JSON](codegen-closure.json)、[A 原始记录](codegen-inventory.json)、[遗留项追加进度](previous_delta/service-completion.json)。

| 验收项目 | 状态 |
| --- | --- |
| 三单元 Fn2 首次通信切换 | PASS，仅此指定点。 |
| 三单元 OK 首次通信切换 | FAIL，已证明 resident 依赖。 |
| ADJ、H07 keep=1、半按及全部通信切换点 | INCOMPLETE，停止后未继续。 |
| 首次 W 前持续失败提示 | FAIL，已重现 50mm 第 1 次；其余未跑完。 |
| 部分写入后持续失败和完整回归矩阵 | INCOMPLETE。 |
| 零文件写入审计 | 已运行 native 记录的五项计数均为 0；完整机器码审计未完成。 |
| 全部 A/B/C 与依赖闭合 | INCOMPLETE。 |

没有把本地 A、包文件一致或局部零写入计数等同于完整验收。[局部文件计数](partial-file-observations.json)、[停止状态](task-stop.json)。阅读版 source.patch 使用中性质检用语，原始差分逐字节保存在 [十六进制来源记录](source-patch-provenance.json)。

## 产物身份与校验

初版 gen 120 DAT 为 `b22928a818c02d2e2534164853f83f587ae06341390fe4059b5efb0e7dcf64ed`，59,188 B，距 64 KiB 上限余 6,348 B；engine 为 49,636 B，BSS 为 9,720 B。它是未通过验收的诊断版本。

v3.6 机身 ilaunch3 保持 `50720c80696ca88f25dc25a85285acd0e0f19906e1d7da1dd404f6cc243f9008`；resident build id 保持 `b779cc756a740506415ca5df8eb5c8f08e1b04ea9d8c4c614f7ae971e92b94f7`，ABI 保持 `d7387c3670059c325186de3af1b3d5c6`。官方 ZIP 为 `3705984b8433c40d2ed4fd2600c11f03ed8a6de7dbe7f66efd38ee5ca15fc898`，其中原版 ilaunch3 为 `da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7`。

曾组装的 30 个文件含 28 个逐字节等于官方 ZIP 的伴随文件，其余 29 个文件与 gen 119 卡包相同；配方、records、metadata、map 和 pin 均相同。触发停止条件后，已把该诊断包移到 `firmware/package_v36_g120/unaccepted/`，不保留顶层 `SD_ROOT`，以免误当交付候选。[初版包校验](package.json)、[数据相等](data-equality.json)、[诊断版本快照](partial-runs/initial-candidate/manifest.json)。

输入清单先核 SHA 再读取。gen 119b 的 12,279 项、作者 r2 的 7,650 项和 gen 117 r2 的完整清单均逐项核验；受保护输入前后核对见 [input-integrity.json](input-integrity.json)。原始命令输出、初版失败和停止记录均保留。所有 Python 使用 `/usr/bin/python3 -I -B`，未启动子代理，未使用等待循环。

三份目录清单均逐项重读自检：[研究清单](SHA256SUMS)、[构建树清单](../../firmware/engine_v41_ux/EVIDENCE_SHA256SUMS)、[未验收包清单](../../firmware/package_v36_g120/SHA256SUMS)。[自检结果](manifest-selfcheck.json) 记录文件数；每份清单按惯例不包含自身。

交回决定：是否另行授权修改 resident 的 H07 归属收尾，并要求代码净增长不超过 0 B、继续保留 200 B。获准前，本轮保持停止状态。
