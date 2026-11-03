下一轮先解决仍在主机热路径上的全空间写审计，再推进批量模拟器的设备原生化。

主机侧证据：固定 part1 的全部写审计可以使用已证明的 Harness.trace 提前返回条件；真实 view-reentry 另装 runtime_guard.watch。该组最终 C 版执行了全部 84,747,616 步，单次 CPU 从 791.41 秒降到 468.84 秒；子进程记录中的 fast_writes、native_state_steps、deferred_steps 都为 0。写回调是已定位的下一处限制，不能把固定 part1 的倍数外推到全套。

可独立尝试把冻结 runtime_guard.watch 的第一个 touches_ui 判断搬到 C：只在写入不触及原七个范围时走它已有的提前返回；命中范围时仍调用原函数，保持写来源检查、全部计数和异常。需要绑定 watch/helper 的代码、globals/builtins 版本及完整范围表；运行中换函数、改范围或改全局后必须同步回 Python。先做地址边缘、函数替换和范围变更的变异检查，再在 70 子进程套件中交替测五对。影子后端仍共享原 bytearray 和追踪列表。

模拟器新基线是已放行的 tools/gxr_emulator_batch，动态库 SHA 为 018a6d9731d54b6b27e6729d4a8903a4cab5b8763a0ce92467ad91e02d2d8c95。本轮没有改这个副本。继续实验必须先复制到 tools/speedlab 下，并在复制处修正 ROOT、库和输出路径。

第一个设备候选可限定为 IRQ 的 pending read/EOI 与定时器确认寄存器，先剖析 fast/batch 的 CPU 时间，再定实现范围。保持精确 StepHook 类型与设备声明门槛；普通包装、partial、转发对象、子类继续整链逐条执行。原生字段必须在任何 Python 回调、截止、断点、快照或故障前同步，转发回调后重新同步，不能仅在整批结束才回写。未确认的设备拓扑、被替换的 MMIO 回调、debug 档继续使用已放行路径。

C 可复用现有 bridge ABI；Rust 也可做独立候选，按相同负载的 CPU 秒和完整状态比较决定，不据语言名称估计速度。无论选哪种，都要重跑全状态哈希、M2b、M2c、g145 回放、实际变异和 research/emulator_batch/hook_cases.py，最后交由用户另开复审。这里是下一轮范围，不是已验证的原生设备实现。
