2026-10-25 P1 开始。卷身份、可写 APFS、df 已核实；冻结输入排除 decisions.tsv。
基线 resident payload 7800 B，root 256 B，窗口 8340 B，实余 284 B。
覆盖决定：默认启用；仅有效 CRC 的 CTL OFF 锁定停用；RPC 仅明确应用时准许。
H09 packet mutation 保持关闭。未构建机身镜像，未访问相机或卡。

2026-10-25 P1 停止，触发 resident 尺寸门槛。P1 未通过，不进入 P2–P6。

- 基线重编 payload 7800 B；首版 9560 B；共用绑定检查、表驱动 ready、删除重复探测并保留验证后，最终标准编译 9280 B。
- 最终四种配置分别为 Os 9280 B、Oz 9280 B、Oz/LTO 8976 B、禁止内联的 Oz/LTO 9220 B。链接脚本始终保留 200 B assertion，所有最终链接均拒绝输出 ELF。
- 最小方案加 root 为 9232 B，窗口 8340 B，余量 -892 B，距题定门槛还差 1092 B。没有扩大窗口、使用第二窗口或删去验证条件。
- 局部 C 检查通过 117 例、10966 次断言，启用 ASan/UBSan；H40 隔离桩通过 524 组寄存器/PSW/SP/分支向量；IRQ helper 通过 65536 组；两份空日志模板独立解码通过。
- 首次 C 检查发现测试替身的指针加减次序触发 UBSan，已把 ram+a-base 改为 ram+(a-base) 并重跑通过。原始 stderr 保存在 local/p1-checks/history/。初次 LTO 丢弃未被 C 引用的 pins，已加 used，最终 root/pins 两项链接断言均通过；尺寸断言仍失败。开发错误没有被当作停止理由。
- H40 检查使用相同汇编对象的隔离 ELF，C observer 为替身；不是完整 resident、连续原生入口或相机执行证明。主机 C 的分派坐标和 native 边界也是夹具，不计入 P5。
- P2 的纯 init、明确应用、service 隔离、黑匣子 flush/回执均未实施；P3 full-r10、P4 镜像、P5 矩阵/历史反例、P6 SD_ROOT 均未启动。
- 后续选择及字节目标见 REPORT.md 和 local/budget.json。这里只封存草稿、map、日志与检查脚本，未标为 STAGED_HOST_ONLY。
