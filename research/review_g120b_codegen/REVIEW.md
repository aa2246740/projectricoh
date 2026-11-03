不可以上卡。

本结论只针对 gen 120b 的编译改码安全边界。824 个待审分支方向已逐项分类，其中 41 项仍涉及没有固定上界的导航循环，按题定第 4 类记为 P1。另有一个共享通信路径的精确行字节范围合同缺口。没有发现已证实的 P0。

审查对象为 `firmware/package_v36_g120b/SD_ROOT/GXRCE.DAT`，59,128 B，generation 120。DAT、最终 ELF 与解码字节已绑定；本轮定向执行直接读取该 DAT，没有构建新固件。未接触相机、存储卡或网络；全部新文件写入本目录。交互矩阵由另一位审查员负责，本轮没有重跑，也不据本报告宣称相机验收通过。

| 对象 | SHA-256 |
|---|---|
| 最终 DAT | `233e23f7b4c9426a267f02fae409d1d580ef940f2b9cccd0379d7f4a479e1607` |
| 最终 engine，49,576 B | `95e36cada1ff26a8a99300c0cf73abceab0a6a056d66bfcf3856221c0ca778e3` |
| 最终 ELF | `78486463e282d19966d75279d34aaf0b8630ddc798de14fd1c6dc11c0e8bb508` |
| 官方 gxr-151.zip | `3705984b8433c40d2ed4fd2600c11f03ed8a6de7dbe7f66efd38ee5ca15fc898` |
| 官方包内 ilaunch3 | `da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7` |

身份记录见 [identities.json](identities.json)、[official-check.json](official-check.json) 和 [runtime-binding.json](runtime-binding.json)。resident 本次不变，按任务给定事实处理。本报告中的 PC 均为重定位前 ELF／镜像偏移，运行时需加镜像加载基址。

P1-01：`ig_apply` 和 `a4_move` 的导航收尾循环没有固定轮数上界。

| 最终函数 | 循环头 | 回边 | 可重复的条件 |
|---|---|---|---|
| ig_apply | `0x8b54` | `0x8bd6` | 界面归属有效，事务继续成功，原生行号在 1..8 内持续变化且不同于上一槽。 |
| a4_move | `0x6104` | `0x6276` | 面板、参数和预览步骤成功，原生数值行在 1..11 内持续变化且不同于上一数值行。 |

循环内没有计数器、截止条件或递减预算。行号取值有限不能限制行号反复变化的次数。`ig_apply` 可在合法行 5、7 间重复，`a4_move` 可在原生行 6、8 间重复。保守控制流将 30 个 `ig_apply` 方向和 11 个 `a4_move` 方向归到此项；41 是受影响方向数，不是 41 个独立现场故障。

本轮执行最终 M32R 函数体，以明确列出的成功服务合同更新原生行号。行号在第 1、16、64 次更新后稳定时，两个函数均返回，ABI 检查通过。持续更新时，`ig_apply` 执行 799 次、`a4_move` 执行 95 次仍未返回，均到达 28,800 条指令的观察上限。循环边界的 SP 保持不变，本项没有把重复迭代写成栈增长。保留的 native 合并事件记录证明通信期间可出现两次同页箭头更新；连续相机输入和 RTOS 调度没有执行，因此这里是固定上界未获证明的 P1。gen 119 的 `ig_apply` 也保留同类循环。

证据：[loop-proof.json](loop-proof.json)、[loop-cases.json](loop-cases.json)、[最终 ig_apply 指令](instructions/ig_apply.txt)、[最终 a4_move 指令](instructions/a4_move.txt)。该项符合题定“循环没有上界”条件，单独足以阻止本次审查放行。

P1-02：B5、B20、B14 的半字访问尚未满足精确行字节范围合同。

这三行的逻辑长度均为 33 字节，但实际读写 17 个半字，即 34 个物理字节。B5 保留尾部一个相邻字节；B20、B14 从奇地址向下对齐，保留前端一个相邻字节。最终 GXMP 的边界标志明确记录这些处理，且三单元 GXMP 与 gen 117 完全相同。静态数据流、本轮模型记录及保留 native 记录都符合这些半字区间，未见任意地址来源。

题定要求访问长度不超过映射行，日志核对也要求落在映射行或 T 范围内。本轮没有把“相邻字节保持当前值”等同于“物理访问仍在 33 字节行内”。在未给出包含该相邻字节的已验证行范围合同前，此项仍记 P1。它是共享路径的范围证明缺口，未据此声称新增编译行为差异；方向级 B 对仍能闭合新旧等价义务，因此不额外增加 824 项中的方向计数。即使此共享合同另获解释，P1-01 仍未闭合。

证据：[maps.json](maps.json)、[rpc-provenance.json](rpc-provenance.json)、[rpc-directed-check.json](rpc-directed-check.json)、[rpc-log-check.json](rpc-log-check.json)。两个 P1 的机器可读记录见 [findings.json](findings.json)。

分类以一个主要风险类别记录每个方向；同一路径若可能到达多个边界，保留相关证据。未知的后续条件保留两种边，switch 使用对应表的实际目标。分类表给出输入代、函数、PC、方向、后继、最终 PC 对应、类别、状态、一句理由及逐项证据。P2 仅用于值计算、状态更新、拒绝返回及题定允许的自有界面字段，所在函数有作者 B 对或保留 native 证据；P2 不表示该方向已单独执行。

| 类别 | 总数 | 已闭合方向 | P1 方向 | P2 方向 |
|---|---:|---:|---:|---:|
| 1：RPC 地址和长度 | 216 | 216 | 0 | 0 |
| 2：文件服务 | 30 | 30 | 0 | 0 |
| 3：原生界面写入 | 2 | 2 | 0 | 0 |
| 4：循环和内存范围 | 49 | 8 | 41 | 0 |
| 5：计算和状态记账 | 527 | 0 | 0 | 527 |
| 合计 | 824 | 256 | 41 | 527 |

| 函数 | 总数 | 已闭合方向 | P1 方向 | P2 方向 |
|---|---:|---:|---:|---:|
| a4_move | 20 | 0 | 11 | 9 |
| apply_impl | 117 | 34 | 0 | 83 |
| apply_impl.constprop.0 | 116 | 34 | 0 | 82 |
| core_call | 30 | 30 | 0 | 0 |
| finish | 14 | 0 | 0 | 14 |
| ig_apply | 70 | 0 | 30 | 40 |
| ig_event | 49 | 34 | 0 | 15 |
| ig_init | 84 | 84 | 0 | 0 |
| ig_panel_abort | 3 | 0 | 0 | 3 |
| ig_panel_event | 3 | 0 | 0 | 3 |
| ig_panel_open | 53 | 0 | 0 | 53 |
| preview_cached | 2 | 0 | 0 | 2 |
| rv_call | 246 | 40 | 0 | 206 |
| ui_finish | 16 | 0 | 0 | 16 |
| view_owned | 1 | 0 | 0 | 1 |

| 方向级方法或状态 | 数量 |
|---|---:|
| P2 | 527 |
| OPEN_NO_FIXED_BOUND | 41 |
| B | 96 |
| B+C | 25 |
| UNREACHABLE | 11 |
| C | 34 |
| A+C | 84 |
| UNREACHABLE_FINAL_DOMAIN | 6 |

分类数据见 [classification.tsv](classification.tsv)、[classification.json](classification.json)、[classification-summary.json](classification-summary.json)。其中 578 项来自 gen 119→120，246 项来自 gen 118→119；集合检查要求与原始清单逐键完全相等，无遗漏或重复。41 个 P1 均留为 OPEN，不用成功样本替代循环上界证明。256 个 CLOSED 是下述明确合同内的局部闭合。

最终机器码的地址来源链如下。

1. `ig_init` 在 `0x81e8` 调用语义验证，成功后再检查连接单元的 pin。`0x8448` 完成 pin 比较，`0x8470` 才把 `image + BE32(selected_directory+12)` 存入 `g+44` 的 map 字段；`0x84e8/0x84ec` 最后建立 bound/ready。`apply` 在通信前检查 bound/ready。该链受初始化状态及声明的内存别名合同约束。
2. 行循环从 `M=g.data.map` 取 `M+32+12*j`；`0x4f14` 读取 M，`0x4f0c/0x4f20` 建立行步长 12、首行偏移 32。j 从 0 增到 8，`0x5114/0x5118` 在九行后退出。行长度只能取最终 GXMP 的 `[62,33,96,56,62,33,66,62,33]`；每行最大 48 个半字，九行合计 253 个半字。恢复读回使用同一行长度、起点和步长。
3. 半字游标从 `row.address & ~1` 开始，以 2 递增；局部索引从 `-(row.address & 1)` 开始，在索引不小于 row.length 后退出。`0x5068/0x5070/0x5074/0x5076` 是写循环的递增、比较与回边，恢复循环递增在 `0x51a4`。50mm 的 B5 从 `0x2012fffc` 跨到 `0x2013` 页，恢复路径的 `0x5190` 会更新 X 页；本轮同时比较了跨页第 92 个 RPC 失败的两代行为。
4. T 的页和偏移只来自 `BE16(M+28)`、`BE16(M+30)`，逻辑选择为 `0x12c0:0x2444`。T 写入前先成功选择并读取 T，写值只为 0 或 2。`t_store` 不接受另一个地址来源。
5. `svc@0x3f32 → core_call@0x317c → rv_call@0xa738 → rv_rpc8_native` 是唯一的 X/V/W 发送链。service 4 的 op 2/3/4 分别变为 V/W/X。`core_call` 把地址参数原样放入请求 +40，RPC 数据缓冲区长度为零；其他数据请求有 80 字节限制。底层没有单元区域检查，因此本轮以地图准入和上述游标来源为证明边界。

每个直接或间接发送调用点的函数、PC、命令和值来源列在 [rpc-provenance.json](rpc-provenance.json)，最终指令原始字节在 [instructions](instructions/)；全部跳转／调用清单在 [transfers.json](transfers.json)。最终产品的所有服务封装及七处带类型的间接调用见 [caller-domain.json](caller-domain.json)：`pn_call` 不发送 service 4，X/V/W 均经过上述单一路径。该证明没有把底层任意地址能力视为限制器。

作者 native 日志中，有 153 组保留完整 RPC 数组可重建页和游标，共 6,808 条 X/V/W：X 652、V 1,356、W 4,800。6,283 条满足精确行／T 选择，525 条为上述保留边界半字，超出已验证半字区间的记录为零。另有 18 个摘要数组、21 条摘要记录缺少地址状态或回复，明确排除，不能用累计 RPC 计数补成地址证据。各源文件的 SHA、状态、DAT 绑定见 [rpc-log-sources.json](rpc-log-sources.json)，逐条地址结果见 [rpc-events.tsv](rpc-events.tsv)。保留文件中存在未完成矩阵的前缀，本报告只使用其原始 RPC 记录，没有将这些矩阵声明为 PASS。

部分保留 native 记录使用名称修改前的 `438efcbd…` DAT。作者 [name-code-binding.json](../ux_preview_dot_r5/name-code-binding.json) 记录其 engine、ELF、重定位及生效行与最终 `233e23f7…` DAT 相同。本轮新增 apply/core 比较直接绑定最终 DAT 和最终 ELF。保留日志的半字边界观察仍不能消除 P1-02 的精确行范围缺口。

本轮闭合与定向检查如下，均没有实际文件或相机 I/O。

| 检查 | 数量／结果 | 闭合范围 |
|---|---|---|
| 局部 A 重算 | 136 项，114 项 A；与作者清单一致 | 96 改码、31 同码、5 新增、4 删除的义务清单；只声明局部 A。 |
| ig_init 平移检查 | 594 条旧指令对应 602 条新指令，A+C | 全部旧指令、边、调用返回点和数据引用保持对应；新增八条只写 `g.current` 的 `g+184..234`，不发送服务。 |
| apply 119/120 定向 B | 227 对，PASS | 三单元、八槽、恢复状态、微调边界、T 故障、行及跨页故障；核对返回、ABI、完整公共逐字节写值历史及完整远端模型状态。 |
| core 119/120 定向 B+C | 760 对，PASS | 请求转发和回复校验；五对 Fn2 数值行比较差异按明确 C 合同处理。 |
| rv_call 118/119 文件分支 B | 933 对，PASS | 只读 token、打开／读取／关闭、EOF、错误及限制；使用机器 ABI 的正确字段偏移。 |
| rv_call lease B | 5 对，PASS | 第 1..5 个自有块匹配，核对最终返回、ABI 及公共写值历史。 |
| 导航循环 | 8 个指令级案例 | 六个稳定输入案例返回；两个持续更新案例到达观察上限，P1 保留。 |

新增成对比较共 1925 对。每一对保留输入、两代边方向、停止条件和比较结果；B 闭合项在分类表中引用实际驱动该 PC+方向的案例。apply 的两代记录分别含 X 1,467、V 9,019、W 19,208；各有 214 个边界相邻字节检查，值均等于当前模型字节，未把其算成精确行内访问。调用服务、文件系统、分配器及会话边界使用脚本列出的共同合同；未执行实际卡、镜头固件或 RTOS。

证据分别为 [local-a-check.json](local-a-check.json)、[init-translation.json](init-translation.json)、[apply-check.json](apply-check.json)、[core-check.json](core-check.json)、[file-check.json](file-check.json)、[owner-check.json](owner-check.json)。[fixture-notes.json](fixture-notes.json) 记录保留测试脚本的字段及比较修正；`core-first-difference.json` 中的数值行差异属于 [core-C-cases.json](core-C-cases.json) 的有意改动，完整比较已纳入该合同。

其余闭合合同与守卫：H07 改为确认已有 live RAM，最终配方路径调用图 22 个函数及 88 条保留 native 记录中没有新增 RPC 或文件调用；原生关闭延续的功能验收仍由另一审查范围承担。合法对齐的固定 dispatcher 统一写回复头 `0x00010020` 和 status，其返回值与 status 一致，排除了五个不一致回复方向。无文件写能力时，文件 token 的唯一构造路径只建立 mode=0；读取／写入选择中的相反要求因此不可达。同一不可变请求中的成功 SD 身份读取排除稍后的全零身份方向。ASCII 扫描索引从 0 每次加 1、上限 255，错误字节出口要求 `i<n`，排除随后的 `i==n` 方向。最终调用点域还排除了产品不发出的 service 13、范围外 service 及 UI-list op 4。

对应证据：[contracts.json](contracts.json)、[reply-invariant.json](reply-invariant.json)、[file-mode-proof.json](file-mode-proof.json)、[file-sd-proof.json](file-sd-proof.json)、[ascii-loop-proof.json](ascii-loop-proof.json)、[caller-domain.json](caller-domain.json)。这些不可达论证依赖固定 API、独立请求／回复块和原生服务只写声明输出区的普通调用合同，未将任意独立调用者纳入结论。

527 个 P2 逐项保留在分类表。值计算不替换 map、行地址或长度；最终数据的三单元八槽、六个有效参数 ID、微调上下限、九行复制范围及 Engine 的 stock/live/staging 区间见 [calculation-contract.json](calculation-contract.json)。纯状态和拒绝返回方向引用原作者对应 B 组；题定允许的列表、光标、覆盖层、圆点和面板字段按自有界面处理。本轮没有把函数级覆盖误写为每个 P2 方向均执行。

审查从 2026-10-27 17:11:33 UTC 开始，时间盒截止 20:11:33 UTC。交付状态为分类和证据整理已结束、P1 未闭合。没有修改产品来尝试闭合 P1，也没有要求设备补验后继续放行。

脚本均在本目录，Python 使用 `/usr/bin/python3 -I -B`，`review_scope.py` 将写入限制在本目录并禁止 socket 连接。按依赖重跑顺序如下，命令只生成审查证据：

```sh
/usr/bin/python3 -I -B research/review_g120b_codegen/static_inventory.py
/usr/bin/python3 -I -B research/review_g120b_codegen/check_local_a.py
/usr/bin/python3 -I -B research/review_g120b_codegen/init_translation.py
/usr/bin/python3 -I -B research/review_g120b_codegen/loop_check.py
/usr/bin/python3 -I -B research/review_g120b_codegen/apply_check.py
/usr/bin/python3 -I -B research/review_g120b_codegen/core_check.py
/usr/bin/python3 -I -B research/review_g120b_codegen/file_check.py
/usr/bin/python3 -I -B research/review_g120b_codegen/owner_check.py
/usr/bin/python3 -I -B research/review_g120b_codegen/boundary_proofs.py
/usr/bin/python3 -I -B research/review_g120b_codegen/static_invariants.py
/usr/bin/python3 -I -B research/review_g120b_codegen/caller_domain.py
/usr/bin/python3 -I -B research/review_g120b_codegen/rpc_log_check.py
/usr/bin/python3 -I -B research/review_g120b_codegen/classify.py
/usr/bin/python3 -I -B research/review_g120b_codegen/write_review.py
/usr/bin/python3 -I -B research/review_g120b_codegen/verify_review.py
/usr/bin/python3 -I -B research/review_g120b_codegen/seal.py
```

[verification.json](verification.json) 检查 824 项集合、TSV/JSON 一致、证据路径、定向案例状态、最终产物绑定及已读取的既有输入哈希。[SHA256SUMS](SHA256SUMS) 覆盖本目录全部普通文件，按标准清单规则只排除自身；[sha-check.log](sha-check.log) 保留第一次标准校验输出，随后将该日志一并重新封存并再次校验最终清单。[checksum-selfcheck.json](checksum-selfcheck.json) 和终端结果记录最终校验状态。所有文件校验为 OK 后才交付本报告。
