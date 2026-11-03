复审完成：不能上卡

开始时间：2026-10-31 15:47 UTC。时间盒约 3.5 小时。

- 输入已冻结，585 个文件。实现清单 165 项、两包各 30 项校验通过。
- 最终测试 DAT 为 2378a88c5f963ff58bb27e099d5e8668d721f043ce77d3f958b02d8e47c80dd5。
- 50mm 的 p101-partial、p101-five-mode4、p101-normal、t-boot 已通过。
- 50mm 和 28mm 的 offer-ok 已通过，比较九行、T 和完整 S。
- 当前两个前台测试槽位运行 jobs-a.json 和 jobs-b.json。后续为 jobs-c.json、jobs-d.json。
- 所有测试使用 nice -n 10、Python 后端和 offline.sb。没有访问相机、卡或网络，没有 Git 写操作，没有子代理。

运行器记录：初次共享解码缓存导致两个启动用例失败，已隔离缓存并重跑；初次静态结果文件和回执重名，已分开并重跑；沙盒内 diskutil 受原始设备读取限制，独立重建会使用父进程已核实的卷身份和同一设备号。原失败回执保留。

Fn2：直接向 OK/ADJ 处理器传 0x22 没有触发 H07；原厂任务分派 0x22 在当前模型条件下也没有进入 DAT。后续分别记录逻辑 H07 请求检查和原厂分派观察，不把它们混成物理 Fn2 验收。

16:44 UTC 更新：

- 三单元 offer-ok、P1-01 一行异常、GRN*001 均已通过。50mm 另有完整 5 号九行 + S=4 的首选 04 修复通过。
- 独立 S 边界 8 项通过，包括两种长度竞争、版本、尾部最后字节、指针、首/末单非零字节及 8 个锁状态组合。
- jobs-a.json 进入 s-retries-50mm，随后是 identity-users-50mm；jobs-b.json 进入 users-50mm，随后是 exits-ui-50mm。
- jobs-c.json 尚未启动，优先项为 busy-settings-exit、transient-busy-half 和 g138-busy-reference。疑点是 core:368-404 在 S 写入 BUSY 后仍置 committed/baseline，而 H07 可继续确认；待实际 DAT 退出用例决定等级和放行。
- jobs-c.json 还含独立重建、调用清单、实现记录审计、04 缓存显示观察、op5 单键重试观察、逻辑 Fn2 归属检查和全量读回故障用例。
- jobs-d.json 是三组独立抽查回归，尚未启动。

17:38 UTC 更新：

- jobs-a、jobs-b、jobs-c 均已结束，原失败与后续补充检查分别保留。
- 最终测试 DAT 的持续 BUSY + OK、瞬时 BUSY + 半按均复现半套参数，状态 OBSERVED_P1；判断不能上卡。
- g138 相同输入的 r2 对照完成，7 次 op 2 后 ERR，恢复 stock，不接受 5 号。首轮指令预算不足的结果仍为 FAIL。
- 04 预选缓存显示和单键 2 次 op 5 分别记录为 OBSERVED_P2。
- 逻辑 Fn2 三项、全量读回故障、DAT 双向替换和用户条目变更均完成。字形调用后恢复原厂 4 个 UI 字段记为继承清理观察，不把严格零写入断言的 FAIL 改为 PASS。
- 独立重建发布与测试 DAT 都逐字节相同；17 个服务调用点和原记录审计完成。
- jobs-d 的 safety 组已通过，IRQ cutpoints 与现行 labels 待完成；随后生成报告并核对冻结输入、删除指定 Scratch、封存校验清单。

2026-10-31T17:50:34.064842+00:00 最终更新：

- 报告、57 份参数用例汇总和三个独立回归组结果已生成；原 FAIL、OBSERVED 和 8 个跳过切点单列。
- 调用清单 r2 已完成，首轮隔离导入失败保留。32 份运行回执的日志、结果 SHA、生成时间和超时审计通过，并发峰值为 2。
- 最终冻结输入核对、临时目录删除和校验清单以 evidence/seal.json 为准。
