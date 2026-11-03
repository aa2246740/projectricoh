未生成 v3.4 镜像或 SD_ROOT。P1 触发尺寸停条件，P4–P6 未启动；本目录状态为 STOPPED_P1_SIZE，不是 STAGED_HOST_ONLY。

最小 resident payload 8976 B，加 root 256 B 为 9232 B。原窗口 8340 B，实际余量 -892 B，距要求的 200 B 还差 1092 B。失败 map、源码、局部测试和后续选项在 [resident 报告](../resident_v34/REPORT.md)，封存状态见 [STAGING_BLOCKED.json](local/STAGING_BLOCKED.json)。没有扩大窗口、增加第二窗口或绕过链接断言。

v3.3 输入已重算，未修改：

```text
ilaunch3 v3.3    7f01e7535a0c3ebe84bf2d7a060590b24b19f0e1065afc7fe1762973f3f08546
full-r9 / 111    7fc825755406c8dccd49d49277098afedd478ec45260d53893bf0c55d0ab6e7b
v3.4 ilaunch3    不存在
full-r10 / 112   不存在
```

本轮仅有 117 个许可/CTL 局部 C 用例、524 个隔离 H40 桩向量及 65536 组 IRQ 检查通过，不能作为镜像或产品验收。镜像 diff、checksum/更新路径审计、28 个兄弟文件包核对、连续原生入口、历史反例和 ISO100 全事务测试均未运行。

未来目标行为是原厂启动、人工进入后加载、OK/Fn2 明确应用、记忆只定位光标；默认启用，仅有效 CRC 的 OFF 控制文件停用至冷启动。OFF 的 -1 读取歧义保留。日志计划写 GXRBX0.BIN/GXRBX1.BIN，相关引擎代码尚未实施，当前相机不会因本目录产生任何变化。

首刷前必须先关闭 resident 的 1092 B 缺口、实施并验收 P2–P6、取得独立审查和用户刷写授权，再核对正式包与恢复包哈希。当前没有可刷文件。未访问相机或存储卡，全部输出只在两个新目录，摘要在 SHA256SUMS。
