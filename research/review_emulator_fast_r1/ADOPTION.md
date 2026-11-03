本版本暂不作为默认模拟器。需要原生速度的任务可以显式选择它，但必须遵守以下使用范围，并保留 Python 参考复核结果。

环境变量在启动新 Python 进程前设置。调用方须从 `tools/gxr_emulator_fast` 导入模块，并启用 `set_mode("fast")` 和 `set_batch(True)`。

```sh
GXR_FAST_BACKEND=native GXR_EMULATOR_BATCH=1 GXR_FAST_MODEL_FIXES='' \
  nice -n 10 /usr/bin/python3 -I -B tools/gxr_emulator_fast/launch.py \
  --backend native CALLER.py ARGUMENTS
```

参考复核使用相同输入、相同修正列表和独立的可写虚拟介质。

```sh
GXR_FAST_BACKEND=reference GXR_EMULATOR_BATCH=1 GXR_FAST_MODEL_FIXES='' \
  nice -n 10 /usr/bin/python3 -I -B tools/gxr_emulator_fast/launch.py \
  --backend reference CALLER.py ARGUMENTS
```

四项修正默认全关。需要时用逗号选择 `nand-word,preview-link,sd-long-response,nand-read-tail`。参考进程也要设置同一列表。模型修正改变模拟假设，不能据此认定相机行为。

以下用法必须显式选择参考后端，直到对应 P1 关闭。

- 调用方删除、裁减或重新组合设备调度链，包括把 `step_hook` 设为 `None`，或只保留基础调度层。
- 调用方跨 `cpu.run()` 保存设备状态中的字典、列表、集合等可变对象引用，并读取或修改这些引用。当前原生同步会替换对象，且连续运行会漏掉旧引用上的修改。
- 状态中的计数或截止步超出原生算术范围。本次 `BootSerial.clock` 的大整数被静默截短；传输编码本身通过，设备算术仍须选择参考后端。
- 调用方使用尚未闭合的模型、未知覆盖层或未声明钩子。原生版已有部分自动回退，但回退资格检查尚未覆盖全部调度链组合。
- 调用方在构造 CPU 前安装或包装模型方法。当前自动识别会把继承已知标记的包装函数误认成已移植模型，不能依赖自动回退。
- 需要逐步调试、完整写入观察或其他未获逐项等价证明的扩展。

结果须记录实际执行路径。保留 `cpu.library_path` 的 SHA256、模型列表和源码 SHA256，以及原生驱动的 `instructions`、`python_bus_calls`、`hle_callbacks` 和 `batch_stats`。环境变量写了 `native`，不代表该段全部在 C 执行。

原 M2b/M2c 重启用例仍保留一次 Python 停点回调。它可作为明确记录的混合执行边界，不能标成全程 C 或零 Python 回调。

原生结果出现 FAIL、OPEN、DeviceBoundary、fault、超时、预算耗尽或无法解释的停点，都要在 Python 参考上复核。使用同一份冻结输入和独立介质，从冷启动或已独立核对的同后端检查点重跑。保留首次失败，分别记录程序行为、模型边界和后端差异。两个后端在同一失败终点一致，只证明该失败的等价性。

快照当前还需要调用方补足约束。

- 所有文件输入传入 `pathlib.Path`，包括机身、DAT、单元 ROM、SD 种子、设置输入、NAND 种子和驱动脚本。`Inputs` 把普通字符串当作配置值，不会读取字符串所指文件的内容。
- `Inputs` 显式加入构造完成后的 `cpu.model_revision`。当前 `identity()` 没有自行读取该实际配置，省略它时，切换修正开关仍能命中旧快照。
- 同时绑定调用方模型参数和所有覆盖层源码。构造后不得更换输入或修改运行源码。
- 使用 `Cache(root)` 的输入键目录；每个任务和后端使用独立命名空间。快照由新建实例加载，核对压缩数据、展开数据、整机指纹和完整 SD 种子哈希。不得改写元数据来接受不同版本或不同后端。
- 初次复用一个检查点时，从冷启动独立跑到相同检查点，再比较全部寄存器、内存、设备、观察历史、NAND 和 SD 字节。续跑结果还要与直接运行对照。保留种子、快照、元数据、驱动和输入清单，便于重跑。

未声明回调的快照应被拒绝。长流程每段控制在 30 分钟内；超过时先拆成检查点。正式结论不得使用来源不明的历史快照或仅供调试的续跑结果。

本说明只适用于宿主模拟器。它不包含存储卡、FAT32 实卡、刷写、断电、相机 RTOS 时序、LCD、拍摄或物理机恢复的验收结论。
