不可以切换

A 的原八个绑定反例已修复，但新增 P1-03 阻断切换：回调中替换父类 `Cpu.op` 后，Python 执行新方法，C 仍认为兼容并继续执行原生指令，寄存器和回调记录不同。B 的指定私有库也复现同一缺陷，因此 B 暂不合并。两者分别绑定下列最终库字节，未切换入口或修改被审对象。

| 被审输入 | SHA-256 |
| --- | --- |
| A，API 4 | `011de81d91788746320fcbbe6cc4e7a24f0e4b7f9861ace9ff20b305b3e288b1` |
| B，API 4，UI 审计开关另行核实 | `fd90b5ce232fba1f069e909e30880b96698ddc8f0a30a49f8f8011ee8b66f6b0` |
| 固定验收 g137 DAT | `78dcbb9a2735cd84e55385683ce0296b97818ddf90f8b492d9003512dbeff3f8` |

## P1-03：父类执行方法没有纳入兼容性保护

位置为 `tools/native_harness_c/ccore/backend.py:45` 和 `tools/native_harness_c/python_backend.py:126`；B 对应位置为 `tools/speedlab/harness_c_next/ccore/backend.py:45`。`core_methods` 固定了 `Core.op`，但它最后还调用 `super().op(...)`。替换 `_cpu.Cpu.op` 不会改变 `Core.op` 的函数、代码或接收对象，当前兼容性检查因此漏报。

这是正常的类方法替换。新方法先调用原父类方法，再修改 r9 并记录调用。一个用例在断点替换，另一个在全空间写追踪回调中替换；均执行真实指令字节和原解码器，没有伪造解码结果。两侧都执行两个指令包，C 的 `fallback_calls=0`，事后 `_c_compatible()` 仍为真。

| 独立反例 | 原 Python | A | B，审计开关为 1 |
| --- | --- | --- | --- |
| 断点替换父类 `Cpu.op` | r9=44，新方法调用 4 次。 | r9=0，新方法调用 0 次。 | r9=0，新方法调用 0 次。 |
| store 的写回调替换父类 `Cpu.op` | 当前包剩余 nop 和下一包两 slot 调用新方法，r9=39，共 3 次。 | r9=0，新方法调用 0 次。 | r9=0，新方法调用 0 次。 |

证据：[新增脚本](new_cases.py)、[A 两项原始差异](local/new-summary.json)、[B 独立绑定驱动](b_binding_cases.py)、[B 原始差异](local/b-binding/local/new-summary.json)。采集脚本退出 0 不代表等价；以上两项明确为 `equal=false`。

最小修正是在兼容性检查中同时固定 `Core.op` 实际委托的父类 `Cpu.op` 的函数和代码身份。回调后身份变化时应沿已有回退逻辑执行，并保留当前指令包剩余 slot 的顺序。修复后重跑这两项及已有等价门槛。本轮没有修改实现。

## 原 P1 与 API 门槛

| 核实项 | 本轮结果与边界 | 证据 |
| --- | --- | --- |
| 原 P1-01 的接收对象漏检 | 第一轮 `independent_cases.py`、`extended_cases.py` 测试体逐字节复制，19/19 一致，包含八个原失败。`method_same()` 现检查实际绑定方法类型、接收对象、函数和代码身份。原接收对象缺口已修，新增父类缺口单列为 P1-03。 | [15 项结果](local/independent-summary.json)、[补充 4 项](local/extended-summary.json)、[复制来源](local/copied-inputs.json) |
| 本轮另外四个一致样本 | 直接替换 `Core.op` 类方法、同对象绑定新函数、`functools.partial`、MMIO 中先换再恢复方法，均与 Python 一致。连同上述两个反例，本轮新增 6 项。 | [脚本](new_cases.py)、[结果](local/new-summary.json) |
| API 4 加载器 | 用真实封存 API 3 库和当前有效源码身份清单构造本地清单，确实走到 API 检查并报 `C core API differs`；随后当前 API 4 库正常加载。不是因旧源码 SHA 或坏路径被提前拒绝。 | [脚本](api_cases.py)、[结果](local/api-summary.json) |
| 原 P1-02 的环境身份缓存 | 原 `cache_cases.py` 测试体逐字节复制，当前 `content_cache.py` 逐字节复制。部署目标 14.0 返回 140000；改为 15.0 后换键，缓存与直接编译均返回 150000。两层依赖、参数、损坏库重建和两个线程请求只编译一次也通过。 | [脚本](cache_cases.py)、[结果](local/cache-summary.json) |
| 同一缓存对象跨 fork 后改环境 | 真实父进程和子进程使用同一继承缓存对象，子进程从 14.0 改为 15.0 后命中正确的新键并从真实库读出 150000，等于直接编译结果。为保持 fork 阶段父一子一，子进程回放父进程真实 15.0 编译时的工具探测及依赖扫描响应；子进程内没有再次运行编译器。该项是带明确工具响应夹具的 fork 缓存测试。 | [脚本](cache_fork.py)、[结果](local/cache-fork-summary.json)、[子进程记录](local/cache-fork/child.json) |
| trace 回退条件 | 六项全通过，控制样本确实快速写；条件、代码或回调改变时应保留的 Python 写回调均保留。 | [脚本](trace_cases.py)、[结果](local/trace-summary.json) |
| 默认入口 | 未设后端开关或显式 python 都保持纯 Python，坏 C 清单不影响构造。 | [结果](local/default-summary.json) |

静态已证：缓存格式为 3；每次 `compile()` 捕获环境，重新查询工具，身份查询、依赖扫描和实际编译共用该环境。它执行已选择的编译器，编译后核实依赖与工具字节。见 `tools/speedlab/content_cache.py:61`、`:65`。原环境过期问题没有在本轮重现。

## 独立固定验收与真实子进程回归

| 负载 | 实际执行及结果 | 证据 |
| --- | --- | --- |
| 固定 50mm，Python 对 A | 全部 189 个验收值相同，未排除字段；两侧均为 27,322,942 个指令包、42,299,447 个 op。原始验收 JSON 也逐字节相同，SHA 为 `40a01d3ff2d9d328380a6054cb7a6f8c29270e31686613a98bdb1b7e1f9b784d`。 | [驱动](fixed_accept.py)、[比较](local/fixed-comparison.json)、[Python 原始结果](local/fixed-python-50mm/local/accept-50mm.json)、[A 原始结果](local/fixed-c-50mm/local/accept-50mm.json) |
| view-reentry，Python 对 A | 每侧 28 个真实 fork 子进程全部完成，29 份 JSON 的 121,083 个值相同，均为 56,190,466 个指令包；A 的这些步骤全部进入 C。审计 tape 的 29 份文件、616 条事件、25,562 字节完全相同。 | [本轮复制驱动](legacy_next.py)、[比较](local/view-a-comparison.json)、[Python 运行记录](local/view-python-complete/summary.json)、[A 运行记录](local/view-a/summary.json) |
| view-reentry，B 审计开关 0 | 28 个子进程、29 份 JSON、616 条审计事件与同一 Python 子集一致。该运行是未开启过滤的对照。 | [比较](local/view-b-off-comparison.json)、[运行记录](local/view-b/summary.json) |
| view-reentry，B 审计开关 1 | 28 个子进程、29 份 JSON 的 121,083 个值与 Python 一致；56,190,466 个指令包全部进入 C。实际记录到 UI guard 和快速写，审计 tape 的 29 份文件、616 条事件、25,562 字节完全相同。 | [比较](local/view-b-comparison.json)、[运行记录](local/view-b-on/summary.json) |

子集固定为七个界面 L1、card、items、value、groups、entries、ERR，两个切点 entry、row_draw，以及 UP、DOWN 两键。保留原 UI 断言、嵌套影子调用、全空间写审计和步数上限。两侧先实际运行既有完整 v2 C 数学参考检查，再绑定数学参考和十个 int16 数值读取。没有把 28 个子进程写成全套 70 个子进程复验。

本轮未重跑 6,080+40 指令门槛、UBSan、完整 CPU tape 或完整三单元验收；这些既存证据的文件清单已复核，未计入本轮新增通过项。固定负载和子集一致不能覆盖 P1-03 的反例。

## B 暂不合并

当前 B 库同样在父类 `Cpu.op` 替换后产生不同结果，已违反本轮“任一受用运行方式出现差异即不放行”的标准。这是 A、B 共用的执行保护缺口；本轮没有发现 UI 范围过滤新增的结果差异。

静态已证：原 `runtime_guard.py:82` 的 `watch()` 先调用 `touches_ui()`，不相交就返回，命中才计算来源、增加计数或抛异常。C 的 `audit_filter.inc.h:36` 只实现这一步范围判断，`address + size` 用 64 位计算，条件与原七段范围及 `address >= 0x205d9c04` 的提前返回一致。命中返回 0 后仍执行原 Python 回调，没有把审计计数、PC/来源检查或异常移入 C。

初始 guard 同时检查原始文件 SHA、watch/helper 代码形状、全局与 builtins 身份、精确范围表，以及 `len`/`any`。运行中复核函数代码和 globals/builtins 字典版本；回调身份不符或版本改变则不跳过 Python。已知全空间审计可过滤后，A 中已有的寄存器暂存和计数合并路径也会启用。见 [A/B 差异](local/a-b-backend.py.diff)、[C 写过滤差异](local/a-b-trace_filter.inc.h.diff)、[源码位置与哈希](local/static-audit.json)。

主机已证：本轮自写 38 项。每段用对齐 CPU store 覆盖 lo、hi-4、hi 三点，并在断点回调里调用真实 `b.write()`，分别从 lo-1 和 hi-1 写四字节，验证跨界写确实进入原 watch；另测 helper、范围表和已注册 watch 的动态替换。跨界写走 Python 写入口，没有把它称为未对齐 CPU store 的原生执行证据。见 [脚本](boundary_cases.py) 与 [38 项结果](local/boundary-summary.json)。

审计证据另独立复核两层：

- 本轮新执行的 Python、A、B 开/关子集，均重新生成并解析 tape，逐项比较顺序、地址、PC、来源和字节，616 条全部一致。
- 对实现方已封存的完整 70 子进程审计 tape 重新读回哈希、解析记录并逐字节比较，71 份文件、994 条事件、41,186 字节相同；已封存少报变异为 993 条，独立比较器仍拒绝。该项是既存全套工件的重新比较，本轮没有重新执行该全套或重新编译变异库。见 [比较器](stored_tapes.py)、[结果](local/stored-audit-comparison.json)。

2.83 倍是实现方的既有五对测量，本轮没有重新认证该倍数。当前先关闭共同的 P1-03，再重跑上述两项反例和相应等价门槛。

## 输入、执行与清理

仓库根为 `/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh`。写入前已核实外置卷是可写 APFS，UUID 为 `14BE04EB-AF49-497E-B36A-B078B2F7C5E8`。开始时实现清单 39,127/39,127、冻结输入 804/804 全部通过。结束时 1,038 项执行输入及 39,127 项实现清单再次通过，清单身份未变。见 [开始清单复核](local/implementation-manifest.json)、[冻结输入](local/frozen-input-check.json)、[结束复核](local/inputs-after.json)。

所有测试入口使用 `nice -n 10 /usr/bin/python3 -I -B`。固定验收超时 1800 秒，view-reentry 超时 3600 秒，均超过题定实测时间三倍。工作负载串行，view-reentry 以前台 `waitpid` 等待一个 fork 子进程；编译辅助调用也串行。脚本 SHA、PID、nice、超时、退出码与耗时保存于 `local/*-started.json`、`local/*-process.json`，完整日志相邻。初始资料收集曾并发提交六个只读查询，违反两进程提交限制，随后改为串行；不能宣称整轮从未偏离该限制。

测试由 [内核禁网与写入规则](fence.sb) 和 [Python 审计规则](scope_guard.py) 约束。写入仅在本目录与指定 TMPDIR；未联网、访问存储卡、做 Git 写操作或开子代理。临时目录 `/Volumes/Workspace/Scratch/tmp/projectricoh/review-harness-c-r2` 已删除，收据确认没有遗留本轮工作进程，见 [清理收据](local/cleanup.json)。

保留三项驱动准备失败，未改记为通过：初版 fork 驱动让父进程先退出，执行工具返回但没有形成结果；初版 view 驱动缺本地 `round2` 导入而退出 99；初版既存 tape 比较器选错运行目录而退出 1。修正后的运行均用新名称保留原始结果；三份原驱动都与原入口记录中的 SHA 对应，见 [初版源码](local/initial-runner-copies/)、[view 原错误](local/view-python.log)、[tape 原错误](local/stored-audit.log)。B 第一次遗漏开关而以 0 运行，保留为明确标注的对照；随后以 1 独立重跑并核对实际 guard/快速写统计。

逐项结论见 [检查汇总](local/final-summary.json)，审查取舍见 [决策记录](decisions.tsv)。脚本、报告和原始证据均在 [SHA256SUMS](SHA256SUMS) 内，清单采用仓库根相对路径，不含清单自身。可从仓库根只读复核：

```sh
nice -n 10 /usr/bin/python3 -I -B research/review_harness_c_r2/delivery.py verify
```

证据限于本机主机执行与静态源码；相机、RTOS、存储卡和刷写未测试。快照不在本轮放行范围，未给其 `accepted=false` 增加任何通过结论。
