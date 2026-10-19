# Stage 1a probe v2 的阻断记录

v2 停在 R2。当前证据没有证明一个能在本次更新启动的所有可能挂钩之前生效的 guard，因此没有编写补丁汇编、链接脚本或生成 ELF、bin、刷机包。

`spec.json` 记录未通过的设计状态，不能传给 `scripts/build_code_patch.py`。官方 `ilaunch3` 与其他 28 个文件没有变化，既有包没有变化。

已完成的工作在 [REPORT.md](../../research/stage1a_probe_v2/REPORT.md)。[audit_guard.py](../../research/stage1a_probe_v2/audit_guard.py) 可复跑官方字节、更新标志、41 个公共初始化回调及 13 个调用点核对。[replay_guard.py](../../research/stage1a_probe_v2/replay_guard.py) 用小型 M32R 指令解释器重放两段官方代码，验证 OR 置位语义和更新入口判定。它没有执行 v2 固件。

恢复实施前，需要补齐 REPORT.md 的 R2 证明缺口。合并两份 ISO 生产函数是优先考虑的稳定槽位方法；目前没有选定槽位或声称容量、ABI 验证通过。
