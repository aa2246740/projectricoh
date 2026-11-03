# 严格原生模式采用草稿

本候选位于 `tools/gxr_emulator_fast/strict_r2/`。原入口及已交付的 fix_r1 库没有替换。最终是否可交复审以 REPORT.md 首行为准；本草稿不授权其他任务改默认入口。

## 切换

使用新 Python 进程。只修改导入目录或启动脚本，不在进程内切换已经导入的模型。严格原生是本候选的新默认，四项修正仍默认关闭。

```sh
GXR_FAST_BACKEND=native GXR_FAST_POLICY=strict GXR_FAST_MODEL_FIXES='' \
GXR_EMULATOR_BATCH=1 nice -n 15 /usr/bin/python3 -I -B \
tools/gxr_emulator_fast/strict_r2/native_input_run.py \
--output-dir YOUR_PRIVATE_RESEARCH_OUTPUT --name NEW_NAME --budget 50000000
```

按键沿用 `--segment IDLE:N`、`--segment HALF=down:N`、`--segment HALF=up:N`，并支持原有 watch、stop-at、stop-task、stop-after 和检查点参数。输出目录和虚拟介质必须属于本任务，不能共享其他任务的可写文件。

低层固件驱动使用已登记的 `native_controls.prepare()`、`key()`、`watch_point()`、`engine_watch()` 和 `stop_at()`。prepare 接受机身文件、单元、设置文件及已声明的 ready/recovery 输入。设备类、四项模型修正和调度组合由交付登记表决定。运行期不开放增加登记项。

## 状态与扩展

设备、面板、观察器和 Flow 状态从构造结束起归原生引擎所有。构造输入会复制；读取容器得到复制的只读视图，不是会随执行更新的可变引用。给属性赋值，或对视图 append、update、add 等，都会报错。需要保存普通结果时显式调用 `native_controls.export_state()`，或读取驱动输出；这些是脱离引擎的导出副本。

以下用法必须使用参考后端：持有并修改设备容器、依赖对象共享关系、自定义 StepHook、未知 Python 回调、预装覆盖层、类或方法替换、包装与逐步调试。直接访问私有字段、原始 __dict__、登记表内部或从外部改写活跃虚拟介质不属于本合同。同一实例只由一个线程使用，不在执行期间改 Python 运行时或模型定义。

```sh
GXR_FAST_BACKEND=reference GXR_EMULATOR_BATCH=1 \
nice -n 15 /usr/bin/python3 -I -B \
tools/gxr_emulator_fast/strict_r2/launch.py --backend reference CALLER.py ARGUMENTS
```

旧 input_run 在严格模式下直接提示使用 native_input_run 或参考后端。`GXR_FAST_POLICY=auto` 显式保留旧的自动资格路径，没有把它修成任意 Python 扩展都等价的实现。该路径不属于本轮采用范围；自定义 Python 用法应选 reference。

## 快照与证据

完整快照使用 snapshots API。键包含所有参与模型的源文件全文哈希、四项覆盖层、登记表、已登记执行配方、后端、实际库、Python/架构和声明的文件输入。源码、模型选择或登记项变化时重建缓存，不能修改元数据接受旧快照。无法表示的共享可变对象及循环关系明确拒绝；需要这些关系的参考任务关闭快照复用。

native_input_run 的 `-stop.pkl` 保留既有 CPU 检查点格式，并增加原生身份和完整架构状态。续跑用本驱动生成的检查点及同一私有输出目录，名称换新。完整 C 模型、观察历史和控制状态的缓存使用 snapshots API，不能把旧 CPU 检查点当作完整整机快照。

驱动合并同一按键段内的执行窗口。现有回执中的停止步数保留原百万步窗口含义；恰好在百万步边界停止时仍记 1,000,000。`native_windows` 另记实际 C 执行窗口。评估原生比例用 `native_execution.stats.instructions` 除以本次新增步数 `steps-start_step`，续跑时不能除以包含前次执行的累计步数。

每个固件任务记录模块路径、源码和库 SHA256、模型选择、输入文件、总步数、原生指令、Python 总线/HLE 回调及业务停点。FAIL、OPEN、fault、DeviceBoundary、超时和未达到目标的预算耗尽均在相同输入的参考后端复核，保留第一次失败。登记表修改属于新实现，必须连同 C 模型重新验证和复审。

本合同覆盖宿主模拟器。成功完整官方恢复及实卡、刷写、断电、相机 RTOS/LCD、物理按键和拍摄仍须各自的验收证据。

本轮真实流程采用单元关闭、50mm 和 28mm 配方。登记表中的其他单元配置不等于这些流程已验证。迁入新的固件输入或停点时，先固定输入，比较参考后端的检查点和目标状态，再把该任务的回执作为采用依据。原 M2b/M2c 的可变 Python 调用方使用显式参考后端，不能把这些运行写成全程原生。
