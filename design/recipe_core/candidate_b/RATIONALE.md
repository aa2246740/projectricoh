# Candidate B：单个定长配方库

## Problem

宿主 C 核心要表达 16 个可命名、可替换、可删除的独立配方，并保证重读后保持。它只能持有 13 个颜色值，不能接触整块相机状态。字段编码、菜单 ABI、代码空间、相机文件能力和救援入口仍未知，所以本设计只定义合成数据的内存模型与 byte-buffer codec，不生成 `.IFO`、固件或写盘事务。

## Usage (caller's view)

调用方只使用三个核心调用；函数体和外部 adapter 均未实现。

```c
/* Callsite 1: 启动时加载；存储不存在时显式创建空库。 */
RecipeLibrary bank;
RecipeStatus s = have_saved_bytes
    ? recipe_library_load(&bank, saved_bytes, RECIPE_LIBRARY_BYTES)
    : recipe_library_load(&bank, NULL, 0);
```

```c
/* Callsite 2: 菜单选择只把 13 个值交给未来的相机 adapter。 */
Recipe chosen;
if (recipe_library_read(&bank, (RecipeSlot){ .one_based = 6 }, &chosen)
        == RECIPE_STATUS_OK) {
    camera_apply_13_colors(&chosen.colors); /* NOT IMPLEMENTED; no state pointer. */
}
```

```c
/* Callsite 3: 替换/删除后编码整库；宿主测试再加载以证明保持。 */
RecipeMutation edit = { .kind = RECIPE_MUTATION_REPLACE,
                        .slot = { .one_based = 6 }, .replacement = draft };
uint8_t next_bytes[RECIPE_LIBRARY_BYTES];
recipe_library_apply(&bank, &edit, next_bytes);
/* storage_write_whole(next_bytes) is a future adapter, not a core guarantee. */
RecipeLibrary reread;
recipe_library_load(&reread, next_bytes, sizeof next_bytes);

RecipeMutation remove = { .kind = RECIPE_MUTATION_DELETE,
                          .slot = { .one_based = 6 } };
recipe_library_apply(&reread, &remove, next_bytes);
```

## Shape

单个库固定为 1024 字节：64 字节头加 16 个 60 字节槽。槽 `n` 的偏移始终是 `64 + (n - 1) * 60`。线格式固定如下：

```text
header: 0..7 "RCPBHOST"; 8..9 version=1; 10..11 header=64;
        12..13 slots=16; 14..15 slot_size=60; 16..19 total=1024;
        20..23 CRC-32; 24..63 zero
slot:   0 state(0 empty/1 present); 1 name_length; 2..3 zero;
        4..35 name; 36..48 colors[13]; 49..59 zero
```

CRC 使用 CRC-32/ISO-HDLC 参数（reflected polynomial `0xEDB88320`，init/xorout 均为 `0xFFFFFFFF`），计算整库时把 `20..23` 置零。空槽的 60 字节必须全零。所有多字节整数用大端，但该 magic 和格式都是项目自有宿主设计，不能标成原厂 `.IFO`。

codec 独占格式、校验、空槽规范化和直接寻址规则。`RecipeLibrary` 是 1024 字节调用方工作区；核心不分配 heap，私有自动变量预算不超过 64 字节。最重的 `apply` 调用需要调用方提供 1024 字节库、1024 字节输出和 48 字节 mutation，总显式 RAM 上限为 2,160 字节（含核心 64 字节私有预算）；调用方可把两个大缓冲区放在静态 RAM。`recipe_library_apply` 直接在输出缓冲区构造下一状态，成功后同步工作区。删除空槽和重复替换产生相同字节。名称暂定严格 UTF-8、1–32 字节且不含 NUL；相机菜单字符集未知，未来 adapter 必须验证或转换。版本 1 不含白平衡。

模块图：`recipe_core.h` 是唯一公共面；计划中的 `recipe_core.c` 拥有 codec 与变更规则；未来 `recipe_store_adapter` 只搬运完整 1024 字节，不承诺 rename/fsync；未来 `recipe_camera_adapter` 只接收 `RecipeColors`。三个模块不共享写者，核心也无法取得曝光、对焦、画质或按钮字段。这个小接口隐藏了格式和完整性规则，避免调用方协调 load/validate/encode 阶段。

## Synthesis decision

Candidate B 选择单个定长库作为完整方案：它用一次校验覆盖统一版本和全部 16 槽，并把“槽号到地址”的关系固定在 codec 内。根代理可将它与逐槽小文件候选比较；本候选不混入两种持久化方式。

## Tradeoffs accepted

- 接受每次编辑重编码 1024 字节，换取单一版本、单一校验和确定的整库快照。
- 接受任一字节损坏会拒绝整库，换取不向调用方暴露部分恢复策略。
- 接受 UTF-8 和 32 字节名称只是宿主假设，换取现在可测试的确定格式。

## Alternatives considered

逐槽独立文件能隔离单槽损坏，但把版本、枚举、缺失文件和多文件提交策略暴露给存储层与调用方，接口更浅。可变长 TLV 库便于以后加字段，但需要索引、边界扫描和更大临时状态；当前固定 13 字节与 16 槽不需要这层复杂度。

## Open questions and risks

- 真机映射能否证明 13 个值都是单字节，并确定其顺序、符号和范围？
- 相机菜单能显示哪种名称编码和最大长度？
- 目标 ABI 与代码空间能否容纳 1024 字节工作区、CRC 和未来 adapter？
- 存储层实际支持哪些失败恢复动作，整库拒绝时是否需要只读诊断工具？

## Next implementation step

先实现纯 host codec 和字面量向量，覆盖空库、16 槽寻址、替换、删除、截断、CRC 错误及编码后重载；不接文件系统或固件。
