# strict_r3 采用草稿

使用 `tools/gxr_emulator_fast/strict_r3/`，最终结论看上级 REPORT.md 第一行。strict_r2 的源码、库和既有登记流程没有替换。切换须使用新的 Python 进程，不能在已加载旧模块的进程内改路径。

严格原生仍只接受交付登记表中的设备、修正和钩子组合。自定义 Python、可变设备引用、私有状态操作和逐步调试使用 `GXR_FAST_BACKEND=reference`。旧 auto 路径不属于采用范围。FAIL、OPEN、fault、DeviceBoundary、超时及未达目标，按同一冻结输入和独立虚拟介质在参考端重跑，保留首个失败。

```sh
GXR_FAST_BACKEND=native GXR_FAST_POLICY=strict GXR_FAST_MODEL_FIXES='' \
nice -n 15 /usr/bin/python3 -I -B tools/gxr_emulator_fast/strict_r3/native_input_run.py \
--output-dir YOUR_PRIVATE_RESEARCH_LOCAL --name NEW_NAME --budget 50000000
```

Python 调用可用 `import native_input_run as input_run`，给该模块的 `OUT` 绑定本任务私有输出目录后调用 `run(args)`。参数和回执保持输入驱动接口。MOUNT 等单元配方使用 `native_controls.prepare`，不把 50mm 设置当作 MOUNT 输入。精确构造和按键示例见本目录 `scripts/mount_flow.py`。

标签按实际 UTF-8 字节长度无损存储，包含内嵌 NUL 的普通字符串也保留。非普通 str 和无法编码为 UTF-8 的标签在登记时拒绝。登记的长标签不会被缩成 127 字节。

完整快照使用 snapshots API 的 r3 格式。身份自动取自实际登记的断点、地址、标签、停止任务和 stop_after，以及实际初始化声明中的机身、单元 ROM、设置、ready/recovery 配置和键扩展。调用方的 Inputs 仍要固定文件输入；它不能替代实际配方核对。动态发现的返回地址属于执行状态，不作为新的初始化配方。

保存完整快照时，`context.controls` 只是一份导出，不是引擎状态来源。保存和校验均重新读取活跃控制；恢复通过登记接口原位恢复 ready 队列并保留 UnitLink 对象及所有权，随后导入 C 并读回核验。不能以改写导出副本控制恢复结果。

恢复必须构造相同配方的新机器。文件、模型、登记控制或源代码不同会在改写目标前拒绝。r2 完整快照不能直接迁入。CPU `-stop.pkl` 检查点仍是输入驱动自己的续跑接口，不是包含全部观察/控制历史的完整整机快照。

普通 Python 参考任务可能持有共享可变观察对象，部分中途完整快照会明确拒绝；这些组合不作为参考快照恢复通过。本轮用参考端连续执行对照原生的连续与恢复路径。

MOUNT 候选配方固定 `l08firm3`、g155b 机身/DAT、MOUNT Look1 设置和四项模型修正。采用范围以最终比较记录为准，包括冷启动、BOOT_RUN、ADJ/ADJ_RIGHT 分段及首次八行菜单。待机后的 HALF 引入未声明 HSP 请求，两端已在同一步复现 DeviceBoundary；不把该路径算作成功拍摄或扩大成任意按键支持。

所有结论仅为宿主模型。真实 MOUNT、RTOS/LCD、物理按键、拍摄、实卡和刷写仍须设备证据。
