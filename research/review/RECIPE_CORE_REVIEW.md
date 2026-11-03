# Recipe core 独立复核

复核日期：2026-10-12  
Reviewer：GPT-6.1 review

## 当前结论

源码初审发现 **1 个低严重度文档偏差**，暂未发现会破坏槽隔离、错误后输出或删除语义的实现问题。host tests、verify 产物和目标 GCC 对象尚未完成复核，因此当前不能给最终通过结论。

## Finding

### [低] 设计文档把保存路径写成单个槽缓冲

- **位置**：`design/recipe_core/RATIONALE.md:26`；`firmware/recipe_core/recipe_core.c:236-240`
- **证据**：设计写“核心只使用单槽缓冲和临时 Recipe”。`recipe_save` 实际同时声明 `expected_record[64]`、`stored_record[64]` 和 `Recipe stored_recipe`。
- **影响**：实现仍然每次只处理一个槽，也没有 1024 字节整库缓存；但“单槽缓冲”容易被理解为只有一个 64 字节缓冲。C 源码局部变量大小也不能直接证明目标对象的栈峰值。
- **具体修法**：改成“保存路径使用两个 64 字节单槽记录缓冲和一个临时 `Recipe`；无 heap、无整库缓存。实际目标栈和代码尺寸以目标 GCC 对象报告为准。”不要宣称已经证明栈小于 128 字节。

## 静态检查通过项

- **16 槽边界和隔离**：三个入口都先拒绝 1–16 之外的槽号。存储回调只接收一个 `RecipeSlot`；记录本身也保存槽号，读取与保存后的读回都要求记录槽号等于请求槽号。源码没有整库地址或跨槽循环。
- **读取输出不变**：`recipe_read` 先读入局部记录并解码到局部 `Recipe`，只有完整长度、格式、槽号、保留字节和 CRC 全部通过后才复制到调用方输出。空槽、无效参数、坏槽、I/O、短记录和损坏记录都不会修改输出。
- **错误分类**：读取不存在返回 `RECIPE_EMPTY`；存储回调失败返回 `RECIPE_IO_ERROR`；长度、格式、槽号、规范化字节或 CRC 错误返回 `RECIPE_CORRUPT`。三类状态没有合并。
- **保存边界**：`recipe_save` 在调用存储前检查 `core`、`recipe`、read/write 回调、槽号和 1–32 字节名称。`recipe == NULL` 返回 `RECIPE_BAD_ARGUMENT`，不会触发删除或写入。
- **短写与读回**：write 状态异常或 `written_length != 64` 返回 I/O 错误。完整写入后重新读取同一槽，要求长度为 64、格式与 CRC 有效、解码值匹配，并要求 64 字节记录与预期逐字节相同。
- **明确删除**：删除只有 `recipe_delete` 一个入口。remove 返回已不存在仍继续读取确认；只有后续 read 返回 `RECIPE_STORE_MISSING` 才成功。因此重复删除幂等，存储仍可读到任何记录时都会失败。
- **确定性格式**：编码先清零全部 64 字节，只写 magic、版本、槽号、名称长度、已用名称字节、13 个颜色字节和 CRC。解码要求 flags、未用名称区和 reserved 全零，格式与设计文档一致。
- **依赖边界**：核心只包含项目头、`stddef.h` 和 `stdint.h`，自有清零、比较与 CRC 循环；未调用 libc 字符串/内存函数，也没有 heap 分配。公共数据只含 opaque 名称字节和 13 个合成颜色字节，没有白平衡或整块相机配置指针。

## 尚待最终复核

- 16 槽宿主适配器是否真的把每个槽映射到独立存储，覆盖或删除一个槽后其他 15 槽是否逐字节不变。
- 测试是否覆盖空槽、损坏、短读、I/O、短写、写后缺失、写后字节变化、重复删除和所有错误后的输出不变。
- host verify 是否保留输入/输出哈希和重读证据。
- 目标 GCC 对象是否保持无未解析 libc/heap 符号，以及实际 `.text`、`.bss` 和栈报告。

所有结果仍是 host 核心与记录 codec 证据，不能解释为相机运行、RAW/JPEG、菜单、恢复或可刷固件验证。

## 最终交付复核

复核日期：2026-10-12  
Reviewer：GPT-6.1 review

**No flags。** 上一轮唯一低严重度 finding 已解决。最终 `recipe_save` 复用一个 64 字节记录缓冲，并使用一个临时 `Recipe`；`design/recipe_core/RATIONALE.md:26` 也已改为相同描述，同时明确解码有自己的局部变量，真实目标栈必须包含嵌套调用和平台回调，不能从源码局部变量推断 128 字节或其他上限。

对初审记录作一处状态说明：上文“要求 64 字节记录与预期逐字节相同”描述的是实现中间态。最终实现清空并复用同一缓冲，读回后先验证规范格式与 CRC，再比较名称和 13 个颜色值。由于有效 v1 记录的未用区必须为零，其余头字段也固定，这仍会拒绝任何有效但语义不同的读回；对应测试已覆盖。

最终复核证据如下：

- `firmware/recipe_core/recipe_core.c` 的 SHA-256 为 `a728036dbbcc71f8d6367607b764a267ed23e979b3b73b38477f9ee448c9955f`，与根验证清单一致。公共头、存储头、测试、验证脚本和运行脚本的当前哈希也全部匹配 `artifacts/development/recipe-core-root-verification.json`。
- 根实际复跑的严格 Clang 测试通过 249 项，ASan/UBSan 同样通过 249 项。freestanding host 对象的 `nm -u` 为空；这证明当前 host 对象没有未解析的 libc/heap 符号，不代表目标 ABI 已通过。
- `artifacts/recipe-core/verification.json` 的 18 项独立检查全部通过，且与根验证 JSON 内嵌的 host 结果完全一致。固定 64 字节向量由 Python `zlib.crc32` 得到 `0x2ff80ab5`；实际 slot 16 文件也独立核对了 magic、版本、槽号、名称、13 个颜色字节、零填充和 CRC。
- 16 个槽都实际保存并读取。覆盖槽 8 后，测试逐字节确认其他 15 个槽保持不变；记录内槽号也必须与读取槽号一致。核心和两个存储 adapter 都只按单个 `RecipeSlot` 寻址，没有跨槽写循环。
- `recipe_read` 的空槽、坏槽、短/长记录、CRC、记录槽号、flags、未用名称字节、reserved 和存储 I/O 失败路径均以 sentinel 验证输出不变。
- 名称长度 0 和 33 被拒绝，1 和 32 被接受；名称内容保持 opaque，测试包含 `0x00` 和 `0xff`。13 个颜色字节也只按合成 opaque 数据处理。
- `recipe_save(..., NULL)` 在任何 write/remove 前返回 `RECIPE_BAD_ARGUMENT`。短写返回 I/O 错误；写后 missing/I/O 返回 I/O 错误；写后短读返回损坏；写后返回另一条格式与 CRC 都有效、但名称和颜色不同的记录时返回损坏。
- 删除只有 `recipe_delete` 一个入口。删除已不存在槽仍会再次读取确认；只有确认 `RECIPE_STORE_MISSING` 才返回成功。remove 声称成功但记录仍存在时返回 I/O 错误。
- 格式文档、README 和源码一致：64 字节、`GXRRCP01`、版本 1、槽 1–16、opaque 名称 1–32 字节、13 个 opaque 颜色字节、规范化零区域和大端 CRC。README 明确这些 `.bin/.rcp` 不是原厂 `.IFO`、固件更新或真实胶片预设。
- host 文件 adapter 会直接覆盖目标槽；README 明确不承诺原子保存或掉电恢复。核心没有 Picture Quality、曝光、对焦、白平衡或通用相机状态指针。

**Remaining：host 交付无剩余 flags。** M32R 汇编/链接工具向量与 host 核心是不同证据。GCC 13.4 目标对象、目标 ABI、代码和栈尺寸、相机实际执行、13 字段映射、菜单、恢复以及真实 JPEG/DNG 都仍未验证；当前结果不能称为可刷固件。

## M32R 目标编译增量复核

复核日期：2026-10-12  
Reviewer：GPT-6.1 review

**No flags。** GCC 13.4 目标编译结果支持“同一 host 核心可以生成 M32R 可重定位对象”这一有限结论；现有证据没有把它扩大为已链接、已放置、已执行或可刷固件。

- 根复编输入 `recipe_core.c` 的 SHA-256 仍为 `a728036dbbcc71f8d6367607b764a267ed23e979b3b73b38477f9ee448c9955f`。根对象与 tooling 对象逐字节一致，SHA-256 均为 `ee83dab8450c7a7e8146ef43b37af6b0c3062cc93e7e8d35aa535b172529a23c`。
- `artifacts/development/m32r-c-root-check/verification.json`、`file` 和段报告一致：对象是 32 位、大端、机器号 88 的 M32R **可重定位 ELF**，不是已链接映像。
- `.text` 为 `0x4c4`，即 1,220 字节；`.rodata` 为 8 字节；`.data`、`.bss` 和 `.sbss` 均为 0。外部未定义符号列表为空。这里的“无未定义符号”不包含运行时平台保证：read/write/remove 仍通过调用方提供的函数指针执行。
- `.text` 内仍有两项 `R_M32R_24_RELA` 重定位，位置为 `0x90` 和 `0x2bc`，都指向 `.rodata`。因此 1,220 字节的 `.text.bin` 缺少 8 字节 magic 数据及最终重定位结果，不能作为完整 payload、注入块或更新包。
- `.su` 记录的是各函数自身的静态 frame：`copy_recipe=0`、`crc32_iso_hdlc=0`、`decode_record=64`、`recipe_read=136`、`recipe_save=144`、`recipe_delete=84` 字节。这些数值不能相加或单独解释为完整调用路径的栈上限；嵌套调用、间接存储回调、中断和最终集成环境仍未计入。
- tooling 验证与根复编都使用 `m32r-elf-gcc 13.4.0`、相同源码和相同 flags。结果证明编译具有确定性，并确认生成了可被 M32R 工具解析的目标对象。没有目标执行证据，也不需要在当前无模拟器、无相机条件下伪造执行测试。

**Remaining：本次增量无 flags。** GNU `m32r-elf` ABI 尚未与 Ricoh 原厂 ABI 匹配；`.rodata`、重定位、链接布局、可用代码空间、hook、菜单、13 字段地址、存储 adapter、相机执行、RAW/JPEG、恢复和更新包均未验证。当前仍没有可刷固件。
