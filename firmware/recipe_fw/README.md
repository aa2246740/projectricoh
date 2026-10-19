# 构建 ADJ 16 配方实现

在项目根目录运行以下命令。输出都在 `firmware/recipe_fw/` 与 `research/stage1b_integration/`。

```sh
python3 -I firmware/recipe_fw/tools/verify.py
python3 -I firmware/recipe_fw/tools/report.py
```

第一条构建 payload，运行宿主、ASan/UBSan、汇编桥接模型、工具和拒绝条件测试，并验证更换链接地址。第二条从最终产物生成[整合报告](../../research/stage1b_integration/REPORT.md)。验证结果在 [verification.json](build/verification.json)，原字节与最终新字节在 [hooks.json](hooks.json)。这些文件供协调 worker 审查和后续整合；本目录不生成升级容器。

只重新构建时运行：

```sh
python3 -I firmware/recipe_fw/tools/build.py
```

更换链接地址时，同时传入该地址可用的容量。容量包含探针的末尾保留空间。构建器要求新位置处于原容器已初始化段内、被覆盖的原字节均为 `FF`，并拒绝跳转越界。以下命令把起点向后移 4 字节，保留相同末尾地址：

```sh
python3 -I firmware/recipe_fw/tools/build.py \
  --base 0x20052770 --capacity 8336 --probe-reserve 256 \
  --out firmware/recipe_fw/build/relocated
```

协调 worker 使用完整链接后的 `build/payload.bin`，同时读取 `build/payload.elf`、`build/payload.map`、`build/manifest.json` 和 `hooks.json`。保持每条修改等长，核对原字节，保留末尾探针空间。候选位置未经真机批准，报告中的待验证项由协调 worker 与探针 worker 接手。

## 生成电脑端配方文件

编辑 [example_recipes.json](tools/example_recipes.json)，运行：

```sh
python3 -I firmware/recipe_fw/tools/make_recipes.py \
  firmware/recipe_fw/tools/example_recipes.json \
  --output firmware/recipe_fw/build/RECIPES0.DAT
```

生成文件固定长 1056 字节。把它作为 SD 卡根目录的 `RECIPES0.DAT` 使用；相机路径为 `/ATA1/RECIPES0.DAT`。这里没有执行复制或连接相机。`RECIPES1.DAT` 存在时，UI 按 generation 选择有效的新库；编辑已有卡库时，让 JSON 的 generation 比两份现有库更新。计数按 u32 回绕，相差 `0x80000000` 会被拒绝。

JSON 每条记录包含 `slot`、英文 `name`、13 项 `parameters` 和 `wb`。参数是相机显示值 1..9，工具负责转换为原始枚举。名称允许 1..32 个可打印 ASCII 字符。`wb=[axis0,axis1]` 范围为 -8..8，分别对应 `S+0x6DD` 和 `S+0x6DE`，工具保持轴顺序。未列出的槽会生成带 CRC 的规范空记录。

示例包含 Amber Print、Cool Chrome、Soft Pastel、Deep Forest 四组不同参数。它们用于测试和开始调色，尚没有真机效果照片。

## 实现文件

- `abi.S` 实现两种 ABI 方向及 ADJ 分派、Fn2 和光标提交挂钩。
- `platform.c` 实现固定配方路径的文件回调、每次重读 S 的设置回调及预览请求。
- `ui.c` 复用堆缓存、校验只读库、转换名称、应用选择、处理重复回调和关闭状态。
- `payload.ld` 接收链接参数，拒绝可写全局节、额外初始化器及探针空间重叠。
- `tests/` 测试模拟原厂接口、桥接指令模型、配方生成器、挂钩原字节与构建拒绝条件。

`recipe_v1/` 的三个 C 文件直接作为只读输入参与构建。没有复制修改版，也没有改 `recipe_core/` 或 `scripts/`。

## 2026-10-15 缓存修订

删除了 `0x201C092C` 的通用界面关闭挂钩，改为在 ADJ 描述符保持指针期间复用 3520 B 缓存。关闭不释放名称地址；重开重新读取配方。构建器保护整个 `0x201C092C..0x201C0CF4` 函数，任何修改重叠都报错。

独立复核后又补上类型 5 检查。其他共用 ADJ 状态的页面回到原厂函数；配方页即使加载失败也不会把第 8–16 项交给原厂七模式 setter。缓存使用前先核对原厂堆边界、对齐和表内指针。

当前仍为电脑端代码和测试产物。真实 UI、候选区执行、RAW+JPEG、关机后的配方选择，以及段重装载是否重置缓存指针均待验证。相机端编辑和保存界面尚未接入；现阶段通过电脑生成配方文件。

`tools/validation_recipes_16.json` 填满 16 个命名槽位，使用中性值、低/高对比度、锐度、鲜艳度、五色鲜艳度和白平衡单轴变化，便于首轮辨认选择是否生效。`verify.py` 生成 `build/validation-RECIPES0.DAT`，再用实际 C 加载与应用代码逐项核对。这是功能验收库，尚未经过相机调色。

## 2026-10-15 原厂活动判断修订

Fn2 和即时提交挂钩分别后移到 `0x202BE24C`、`0x202BB968`。原厂活动判断在 payload 之前执行，非 Image 活动直接走原厂分支。构建器保护原厂判断的 24 B，桥接模型在两个入口各检查 257 种非 Image 活动。配方页面不活动时，包装器重放被替换的 `seth`，恢复现场并回到原厂续点。

新 payload 为 7304 B，SHA-256 `012bcd24e77bfe9ece8aa9b41fd65593957a8962fc145a1e9ad528b1daae8563`。53 项 C 行为检查及 ASan/UBSan、27 项 ABI 模型、12 项工具、5 项构建拒绝和 6 项镜像审计通过。[机器码独立复核](../../research/review/STAGE1B_NATIVE_GATES_REVIEW.md)通过，范围限电脑行为和静态证据。

[新版实验包](../../artifacts/stage1b-candidate/packages/stage1b-16-recipes-012bcd24e77b/README.md)已生成，旧包保留。候选与官方恢复目录各 29 文件已读回；当前未上卡、未在相机运行。读回检查不写固件或 SD：

```sh
python3 -B -I research/stage1b_recovery/check_native_gates_candidate.py
```

正常升级路径的静态核对见[本轮恢复检查](../../research/stage1b_recovery/RECOVERY_PLAN.md)。坏 MAIN 救援仍未证明。
