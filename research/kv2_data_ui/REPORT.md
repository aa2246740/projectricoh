可以集成

# kv2-data-ui-r1 实现报告

本结论适用于任务 A 的整数数据模块和任务 C 的纯菜单模型。2026-10-29 在 macOS arm64 上，以 Apple Clang 21.0.0 执行优化版及 ASan/UBSan 版测试，两版结果一致，均无诊断。37 个只读输入的长度和 SHA256 在测试前后保持一致，清单见 [inputs.json](inputs.json)。

本轮只写 `firmware/kv2_modules/data_ui` 和 `research/kv2_data_ui`。现有引擎文件保持原状，没有生成 DAT，也没有操作相机、存储卡或网络。构建和测试串行运行，执行器规划编译命令后依次运行编译器及链接器，每次只有 Python 执行器和一个工具进程。

## 数据块与请求

数据块位于 [gxkv2r2.bin](../../firmware/kv2_modules/data_ui/local/gxkv2r2.bin)，`local/` 由模块自己的 `.gitignore` 忽略。

| 项目 | 实际值 |
|---|---|
| 魔数与版本 | `GXKV2R2` 加 NUL，版本 1 |
| 大端布局 | 64 B 头、24 × 16 B 配方、201 × 16 B 项目、3,430 × 4 B 点 |
| 配方、项目、点起点 | 64、448、3,664 |
| 总长 | 17,384 B |
| CRC32 | `c8fb1b5b`，计算时清零偏移 16 的四字节 |
| SHA256 | `43405f6c5f63050505e958882dcd260f2a9e1f707d3b407860041787964992f9` |

[generate.py](../../firmware/kv2_modules/data_ui/generate.py) 从冻结 JSON 生成块，按原路径编译 r2 的 `dump_tables.c`，先比较 JSON 与实际 C 表，再将生成块逐字段读回比较。CRC 调用 gen 127 的 `common.c` 和 `engine_services/crc.c` 中的原函数，并与 Python CRC 结果交叉核对。旧 Python 脚本未执行、未复制。

`kv_data_open` 检查固定计数、步长、区间、四字节对齐、CRC 和全部保留字段。配方索引严格对应 `unit×8+slot−1`，项目连续覆盖，显示顺序必须为本配方 control 集合的无重复排列。验证还检查冻结范围、提前到顶标志、Amount 百分比序列、默认点、剂量域、递增点及点区连续覆盖到块尾。区间检查使用 `offset <= total && length <= total-offset`。

`kv_data_request` 使用 `int16_t v[10]`，按 r2 项目顺序精确查点，成功返回 0，拒绝返回 -1。未开放 control 必须保持其默认值，隐藏 Amount 为 100，其余为 0。失败保持整个输出不变。请求固定 `wb_method=0`、`tone_method=0`、`dose[9]=0`。

## 菜单模型

[kv_ui.h](../../firmware/kv2_modules/data_ui/kv_ui.h) 定义文字、布局、导航及旧条目转换接口。函数只返回文本、向量、导航或事件，不访问原生 UI 和引擎状态。

| 视图 | 逻辑内容与行数 |
|---|---|
| L1 | 8 个配方、` DISP:Tw`、` MyRec`，共 10 行 |
| 配方卡 | 普通彩色 7 行，04 为 6 行，03 为 5 行 |
| 逐项列表 | 普通彩色 10 行，04 为 9 行，03 为 6 行 |
| 数值页 | 只显示实际 points，按点索引反向排列，没有额外标题 |
| 物理布局 | 固定 8 行；空白行不可选，空白行的 DISP 返回无动作事件 |

标签顺序为 Cont、High、Shad、Fade、Satu、Warm、Tint、Splt、Amt、Filt，实际显示取配方记录中的排列。03 仅有 Cont、High、Shad、Fade、Filt；04 没有 Amt；所有配方均无 Tone 项目。

每个文本先在清零的 9 B 槽中生成，最多 8 个可打印 ASCII 字符，NUL 及其后字节为零。`>` 依据最后成功应用的配方或条目计算，不跟随高亮光标。`*` 比较完整默认向量，Amount=100 不产生变化标记。普通端点和提前到顶端点均显示 `!`。两项紧凑行及单项 Filt 均有字面值断言。

数值按键只在相邻有效点之间移动，20% Amount 的末步准确为 140→150。端点按键保持值与逻辑光标。DISP 保留各层位置，数值页返回其进入来源。Amount 行及单项 Filt 直接进入数值页，两项行进入逐项列表的左项。Default 连续两次 DISP 后返回表中默认向量。

GXUI v1 仍按 11 个旧字段检查。旧位置 0、1、2、3 转为新 control 1、2、3、5，Amount 补 100，其余补 0。七个旧预留数值以及 24 B 记录的其他保留字节非零均拒绝，失败不改输出。结构转换保留四个原数值；集成人在应用前还需调用 `kv_data_request`，不把新表未列出的旧值改成邻档。

## 已执行的验证

以下数量分别在优化版和 ASan/UBSan 版执行一次，结果保存在 [RESULTS.json](RESULTS.json)。

| 检查 | 覆盖及结果 |
|---|---|
| 数据回读 | 全部 24 配方、201 项、3,430 点及元数据与编译后的 C 表一致 |
| 损坏块拒绝 | 21,460 例，覆盖所有短长度、超长、CRC、头字段、计数、保留字段、顺序、默认点、剂量域、点递增及点区偏移 |
| 单项请求差分 | 201 × 65,536 = 13,172,736 次，逐字段比较 r2 `kv2_request`；其中 3,430 次合法，13,169,306 次拒绝 |
| 隐藏项拒绝 | 2,555,865 次，遍历每个未开放 control 的全部非默认 int16 值，输出保持不变 |
| 多项请求差分 | 20,000 组确定性合法组合，逐字段比较 r2 请求；多项组合没有穷举整个笛卡尔积 |
| 数值文字 | 全部 3,430 行；检查反向索引、相邻点移动、端点停留、文字及标记 |
| 紧凑文字 | 全部 28,044 组，覆盖三个单元、两项组合及单项 Filt |
| 标题 | 10,290 次，覆盖三个首字符和各实际点的默认状态 |
| 窗口 | 144,177 例，count=1…33、全部合法 current、previous=0…255 及 `UINT_MAX` |
| 完整物理帧 | 185,101 帧，检查固定 8 行、物理光标、选择掩码、ASCII 和 NUL |
| 导航 | 16,368 次，覆盖各层 DISP、原生首尾事件、端点、填充行及 Default 确认 |
| 旧条目 | 6,674 例，覆盖四位置的全部字节值、预留字段、八个分组、32 个序号及标记 |

窗口测试按原路径编译 gen 127 的 `ui_v2_data.c`，没有重写窗口算法。链接映射按对象编号确认实际函数归属，证据分别在 [优化版 linkage.json](../../firmware/kv2_modules/data_ui/local/release/linkage.json) 和 [检查版 linkage.json](../../firmware/kv2_modules/data_ui/local/sanitized/linkage.json)。`uv_window` 属于 `gen127_ui.o`，CRC 属于 `gen127_common.o` 和 `gen127_crc.o`，`kv2_request` 属于 `r2_menu.o`。

设计末尾的紧凑行汇总数为 28,234。按冻结表的实际卡片分组，完整集合为 27,987 个两项组合加 57 个单项 Filt 值，共 28,044；差额为 190。Python 与 C 独立计数一致，逐配方明细见 [compact_coverage.json](../../firmware/kv2_modules/data_ui/local/compact_coverage.json)。没有为凑齐汇总数补出档位。本轮自身修正记录见 [development.tsv](development.tsv)。

## 集成接口与证据边界

- 数据入口为 `kv_data_open`，只读访问使用 `kv_data_recipe/item/find/point`，请求入口为 `kv_data_request`。视图发布后，调用方需保持数据块存活且不可变。
- 公共头通过 `knobs.h` 使用冻结的 `KvRequest` 定义。当前构建的头搜索路径包含 `research/knobs_v2_r2/src`。新 `UvLevels` 为 20 B；集成人需统一旧头中的同名类型，不能把旧 11 B 类型与新类型混用。
- 菜单入口为 `kv_ui_render`、`kv_ui_move`、`kv_ui_native_move`、`kv_ui_disp` 及 `kv_ui_native_disp`。L1 的 `cache` 指向八个新向量，`names` 提供八个不含序号的短名称，每个 1…5 个 ASCII 字符。L1 的配方及 MyRec 事件由集成人处理。
- `render` 返回实际窗口 top；调用方把 top 保存到当前层的导航记录。`move` 和 `disp` 返回的导航已更新窗口。向量及事件是纯模型结果，成功应用标记由调用方在实际成功后更新。
- 运行时链接现有 `uv_window` 及 `gxr2_crc_zeroed` 等 CRC 函数。本轮没有修改第七段的旧长度判断。新块及第七段 20,776 B 布局的连接、数学模块、事务流程和最终 DAT 属于后续集成。

已验证的是主机编译的真实 C 源码与整数块。尚未执行最终引擎链接、M32R 执行、RTOS、相机 UI 或图像验收，不能把本报告作为上卡结论。

## 复核入口

以下命令在仓库根运行，输出仅写入模块的 `local/`。

```sh
/usr/bin/python3 -I -B firmware/kv2_modules/data_ui/generate.py --check
/usr/bin/python3 -I -B firmware/kv2_modules/data_ui/run_tests.py --check
shasum -a 256 -c research/kv2_data_ui/SHA256SUMS
```

`SHA256SUMS` 采用仓库根相对路径，覆盖交付源码、测试、输入清单、报告、结果、整数块及选定证据，自身除外。测试入口在前后检查冻结输入，输入变化会停止执行。
