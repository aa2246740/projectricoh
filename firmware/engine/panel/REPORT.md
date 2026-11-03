panel 功能和主机故障验证已交付，但 32 KiB 引擎代码段体积门未通过。panel 的独立 PIC/LTO 测量为 16,536 字节，含 GXTS 和测量桩；真实 core+panel 合并为 32,912 字节，超出 144 字节，且尚未计入服务库。最终相机侧链接不含 SHA 函数。

本任务只写 `firmware/engine/panel/`。目标是机身及三个 A12 单元的官方 1.51。未访问相机、存储卡或官方固件目录，未生成上卡镜像，未 commit 或 push。写入前核对了 `/Volumes/Workspace/AGENTS.md`、APFS、可写状态及 UUID `14BE04EB-AF49-497E-B36A-B078B2F7C5E8`。核对记录在 [volume.json](local/volume.json)，`local/` 由本目录 [.gitignore](.gitignore) 忽略。

已核实的面板行为如下。

- [panel.c](panel.c) 绑定 `eng_current` 的完整 49 字节配方身份，保存打开前的提交值和 RAM 草稿。core 的单元编号是 `0..2`，槽号是 `1..16`。存储适配转换为模块 `1..3`、槽号 `0..15`，不会把 core 的编号直接传给 STORAGE。
- 面板保持九行。标题不可选，其后是对比、饱和、高光、阴影、冷暖、色调、Default 和 Back。每行最多八个可打印 ASCII 字符并以 NUL 结束，完整 signed8 值可显示为 `Cont-128`。这是字符长度约束，实际字形裁切仍需真机验收。
- 上下键在第 1 至第 8 行移动，左右键按 `eng_metadata` 的范围改一档。参数 ID 与八维向量下标通过六项 `param_index` 映射，元数据可改变排列。固定值域、默认值和“03 饱和停用”均未写进 resident ABI。饱和停用由该参数的 `min==max` 表示。
- 每次实际改档调用一次 `eng_apply`。到达边界或同值 Default 不重复应用。编辑不调用保存。Default 使用元数据默认值，仍属于可取消的草稿。
- 参数行按 MENU/OK 确认保存。Default 行按 MENU/OK 应用默认草稿，Back 行按 MENU/OK 取消。取消只恢复打开前的提交值，不保存文件。恢复失败、绑定过期或 core 已 uncertain 时保留 `unknown`，不把显示值改回后谎报成功。
- 打开动作的释放前重复按键不会立刻改第一项参数，重复阶段一律不改档。消费的 Fn2 动作经 `pn_panel_native_result` 返回原生 0。PASS、CLOSE_AND_PASS 和 FAULT 必须走 resident 对应的重放及恢复路径，不能作为原生 shooting 返回值使用。
- 半按、关菜单、MY 召回、休眠、关机、单元、链路、视图及存储失效通知都会撤下视图。通知在调用期间到达时记录 stop 标志，调用返回后收尾。通知已晚于身份失效时不把旧快照应用到新身份。

[panel_ui.c](panel_ui.c) 使用冻结的 `UI_TEXT`、`UI_LIST` 和 `UI_VIEW`。文字、字形、指针变量、标签表、details 和 descriptor 均由稳定 context 持有，字形缓冲按四字节对齐。它先生成字形，再绑定九行和替换 part 2/tag 33 栈顶。`view_token` 接受 descriptor 中的输出，也兼容回复 token；两者同时存在而不一致时拒绝。语言号使用当前 resident 实现的 `reply.detail`。

服务位置已按最新决定处理。`PnPort.api` 是 init 注入的 `const RvApi *`；唯一服务调用点是 `pn_call` 中的 `api->call`。panel 不引用固定服务入口或原生函数地址，因此服务迁入 `resident_slim/engine_services` 不改变调用路径。本模块没有原厂 free 或 LEASE free 调用；UI release、restore、abort 均只检查服务返回的状态，不用 `native_result` 判断释放成功。将来由上层释放租约时，也必须以服务库按头部标志 1→0 返回的状态为准。服务库内部 free 实现不在本任务验收范围内。

[panel_native.c](panel_native.c) 从调用者提供的 32 字节 type 5 state、72 字节 descriptor 模板和九条合法 details 记录构造私有列表。它保留未知模板字段，改写已核实的标签表、行数、光标和隐藏项表。模板必须来自受审的 resident 适配，源码没有嵌入官方字节。恢复或 release 失败时继续持有 `ui_pinned`，拒绝重开，交由 resident 独立撤回引用。

已核实的存储行为如下。

- [panel_store.c](panel_store.c) 沿用 STORAGE 的 64/32 字节 wire 布局和固定对象，不提供任意路径。IROM 安装使用 A/B/TMP，卡仅使用 DAT 和成功确认后的 OK。临时名从不参与 A/B 选择。
- 安装顺序是扫描 A/B、比较有效性与 generation、从卡逐字节对照受理的未重定位原始容器、写 TMP、关闭两端、完整重开 TMP 核对、改名到非选中副本、重开正式名核对，然后 op 9 确认送货，最后重开 OK 再核对。源文件变短、变长或内容变化均失败。
- A/B 同代且 CRC 相同后仍逐字节比较。CRC32 碰撞不会使不同文件成为等价候选。无效高代记录不遮住低代有效记录。generation 不回绕。
- 仅在另一份正式副本已验证有效时，才删除非选中旧副本。首次无有效副本时不删除正式文件。只清理当前固定对象的临时名，不操作其它文件。
- 两个文件句柄被原厂占用时返回失败。只剩一个句柄而安装第二次 open 失败时关闭本扩展已有句柄。每个已知 token 只 close 一次，close 失败也不重试。
- rename 失败、返回结构损坏、写入数量超界或 close 失败进入 `PS_COMMIT_UNCERTAIN`。后续写入和删除被锁住，完整重启后重新选择正式副本。已保存到 IROM 但送货确认失败时，`PsInstallResult.installed=1`、`delivered=0`，两者分开报告。
- 整包上限继续按本任务原 STORAGE 合同限制为 32768 字节。最新的 32 KiB 代码段目标不直接改变整个容器对象的 I/O 上限；代码、数据和容器限额仍需统一。

微调状态直接使用 [card_container_v2/gxts.h](../../card_container_v2/gxts.h)、[gxts.c](../../card_container_v2/gxts.c) 和 [gxts_io.c](../../card_container_v2/gxts_io.c)。没有另定义生产状态格式。

- [panel_gxts.c](panel_gxts.c) 的 `PnGxts.io` 就是 `GxtsIO`。open/read/write/close/remove/rename 回调均适配到固定微调对象，`A/B/TEMP=0/1/2` 转为 resident 副本 `2/3/4`。
- `pn_gxts_load` 调用 `gxts_load`。真正缺失时调用 `gxts_defaults`，返回元数据默认值并设置 `used_defaults`。读取有 I/O 错误时不能冒充缺失。存在上一有效副本时可读取回退结果，`io_error_mask` 阻止后续保存。
- `pn_gxts_save` 只在面板确认时调用 `gxts_save`，保留上游固定 240 字节序列化、A/B generation、CRC 和完整身份比较。回调从完整读回且 close 成功的记录选择 `preserve_replica`。短读短写由上游有界推进，零写不会无限重试。
- `gxts_io.c` 的局部栈缓冲不会直接交给 resident。回调通过 `PsStore.chunk` 的稳定缓冲传输，再复制到上游函数要求的缓冲。
- 上游读取函数请求最多 257 字节以发现超长文件。适配器按 256 字节对象上限缩短每次请求，使合法 240 字节文件在短读后仍能读到 EOF。严格累计 I/O 上限的服务模型已通过读写测试；恰好达到对象上限但仍不能确认 EOF 的异常文件按 I/O 错误拒绝。

已核实的 CRC32 适配如下。

[panel_gxts_bind.c](panel_gxts_bind.c) 调用原有 `gxts_bind`。构建仅对 `gxts.c` 的哈希调用使用 `gxr2_sha256=pn_gxts_crc_field` 替换，实际函数只计算 CRC32。identity 中三个原 32 字节摘要单元分别使用 BE32 CRC32 加 28 个零字节；stock 单元按 map、八行 stock 数据及控制半字重算。GXTS 文件仍由原 serializer 写成 240 字节。

本模块使用受理的 CRC 语义视图，提供 `gxts_bind` 所需的有界参数访问器，不链接上游含 SHA 的完整语义校验器。与 core 合并时定义 `PN_GXTS_SHARED_PARAMETER` 复用 core 参数访问器，并把上游 `gxts.c` 的摘要调用映射为 core 已有的 `eng_crc_binding`，避免重复。`local/final-m32r/measurement-only.elf` 和合并测量 ELF 均检查零未解析符号及零 SHA 符号。主机生成 SHA256SUMS 使用 Python hashlib，不属于相机执行代码。`local/` 里的旧构建是过程证据，最终路径为 `final-m32r/` 和 `pic-budget/`。

需要 card_container_v2 配合的事项如下，本任务没有改动该目录。

- 把 CRC 身份单元的编码写入正式 GXTS 绑定规范，明确旧 SHA 绑定记录与新 CRC 绑定记录的识别、失配和默认值行为。当前适配保留固定格式，只替换绑定算法，不应把旧 SHA-profile 文件当作新记录。
- 将 `gxts_bind` 的两处内容/元数据 SHA 调用及 stock 绑定定义切换为正式 CRC 路径，避免集成方长期依赖编译宏。完整语义校验与打包器的 stock 身份单元也必须使用一致的 CRC 编码。
- 将只读参数访问器从包含 SHA 校验的语义编译单元分开，或接受 core 提供的 CRC 访问器。当前独立构建和合并构建都已覆盖这两个来源。

主机验证结果见 [results.json](local/results.json)、[fault-matrix.tsv](local/fault-matrix.tsv) 和 [commands.json](local/commands.json)。共 818 个故障或中断场景，分别为安装故障 479、GXTS 故障 105、安装中断 123、GXTS 中断 30、UI 故障 81。TSV 有 821 行，另三行为常规功能组结果，不将行数当作测试数量。ASan 与 UBSan 同时启用，遇错立即退出。该平台不支持 LeakSanitizer，因此 `detect_leaks=0`。原始失败日志保存在 [failures](local/failures/)。

测试使用内存文件系统与服务表、完整固定对象约束、最多两个全局句柄以及同 token 禁止重复 close 的断言。微调测试链接真实 GXTS 实现，engine 测试使用人工构造的容器 fixture。`eng_apply/current/metadata/uncertain` 是与真实 core 头同签名的主机桩，因此通过不代表实际 ISP、RPC 或预览画面通过。

每个正常事务服务步骤都注入调用前失败、调用后失败和损坏回复，并另测读写数量超界、零写、写保护、满句柄和已有 I/O 错误。断电式测试在每一步副作用之后中断，撤销句柄、增加代次、重建 context，再读取正式 A/B。覆盖了部分写入以及 rename 后源名和目标名都丢失的模型。模型只允许当前操作影响本对象，不能证明真实 FAT、目录扇区或 NAND 的断电隔离。

推断与未知必须分开使用。

- 推断：在 resident 兑现菜单 owner、epoch、lease 和原生 UI 生命周期合同时，这些 C 状态机可接入卡上引擎。主机没有兑现实际固件任务互斥或 native I/O 有界性。
- 未知：32 字节 state 模板的完整 renderer 消费范围、实际字形宽度、所有物理按键别名、MY 与休眠前通知的覆盖、预览真实延迟，以及真实存储的断电行为。测试中的模板是人工数据。
- 未知：最终 entry wiring、完整容器重定位、整包大小和设备验收。本任务的 ELF 仅作测量，不是可安装或可直接执行的交付物。

跨 worker 的存储合同协调点记录在 [integration-audit.json](local/integration-audit.json) 和 [服务库实现快照](local/engine-services.snapshot.c)。快照中的读取能力、op 9、CREATE_TEMP preserve、缺失识别及最大长度 EOF 行为均需由迁入引擎的服务库兑现。适配层不会绕过能力或状态拒绝。core 的配方选择仍需在应用前接入 `pn_gxts_load`，并把 `pn_gxts_save` 回调及六项参数映射交给面板。init 只传服务库返回的 RvApi 指针，不能把链接测量中的任何地址当成运行入口。

产出源码为 [panel.h](panel.h)、[panel.c](panel.c)、[panel_ui.c](panel_ui.c)、[panel_native.c](panel_native.c)、[panel_port.h](panel_port.h)、[panel_port.c](panel_port.c)、[panel_store.h](panel_store.h)、[panel_store.c](panel_store.c)、[panel_gxts.h](panel_gxts.h)、[panel_gxts.c](panel_gxts.c)、[panel_gxts_bind.c](panel_gxts_bind.c) 和 [eng_core_contract.h](eng_core_contract.h)。[tests/host_checks.c](tests/host_checks.c) 与 [verify.py](verify.py) 保留完整复核入口。所有目标文件、ELF、日志、反汇编和服务快照只位于忽略的 `local/`。

复核命令如下，输出仍全部落在本目录。

```sh
cd /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/firmware/engine/panel
python3 -I -B verify.py
python3 -I -B verify.py --sums
shasum -a 256 -c SHA256SUMS
git -C /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh check-ignore -v firmware/engine/panel/local/final-m32r/measurement-only.elf
```

当前第一条验证命令应退出 2，原因是代码体积门失败。主机测试及全部测量链接成功的记录仍会完整保存在 `local/results.json`，不会把体积失败隐藏成成功退出。后两条哈希命令正常通过。

已核实的 M32R 体积来自真实目标对象和 ELF，数值均为字节。

- 沿用 `resident_v2/build.py` 的 GCC 选项及 C 的 `-mmodel=medium` 覆盖，panel 自有对象 `.text=12,260`、`.rodata=176`，合计 12,436。再计 `common.c=320`、`gxts.c=2,200`、`gxts_io.c=1,532`，独立 panel 所需代码及只读数据共 16,488，不含测量桩。[size.json](local/size.json) 保存选项、工具哈希和未解析的 core 接口列表。
- PIC 紧凑配置实际链接的 panel+GXTS+桩为 18,196。合并真实 core、复用 CRC 和参数访问器后是 37,044，比 32,768 多 4,276。
- PIC 紧凑加 LTO 配置的 panel+GXTS+桩为 17,852。真实 core+panel 是 35,848，超出 3,080。
- 默认内联策略的 PIC/LTO 配置最小。panel+GXTS+桩为 16,536，桩函数的符号尺寸和为 44。真实 core+panel 为 32,912，超出 144。该合并没有 core 桩，公共 CRC 仅链接一次，且使用 core 的参数访问器及 CRC 绑定函数。
- 上述合并均未加入 `resident_slim/engine_services`，因此不能宣称完整引擎满足 32 KiB。源码、选项、入口保留列表及 `engine_services_included=false` 保存在 [pic-budget.json](local/pic-budget.json)。测量保留打开、事件、通知、取消、native 构造、GXTS 绑定/读取/保存和安装入口，没有通过删功能换取数字。测量桩对 LTO 保持不透明，避免常量返回让成功分支被编译器删除。
- 本模块无全局 data 或 BSS。调用者仍需持有 `PnPanel=832`、`PsStore=548`、`PnGxts=652`，共 2,032 字节，不含端口、模板、I/O 工作区、原始容器和调用栈。GXTS 单独使用时工作区至少 256 字节，IROM 安装完整验证工作区为 32,768 字节。最大观测单函数静态栈帧为上游 `gxts_bind` 的 976 字节，不能当作整个嵌套调用栈峰值。

最终测量文件是 [非 PIC ELF](local/final-m32r/measurement-only.elf)、[PIC/LTO panel ELF](local/pic-budget/lto/panel.elf) 和 [真实 core+panel ELF](local/pic-budget/lto/core-and-panel.elf)。所有输入哈希见 [input-hashes.json](local/input-hashes.json)，构建前后逐一比较。交付文件及过程证据由 [SHA256SUMS](SHA256SUMS) 校验。报告的结论是功能及主机验证通过、整体体积不通过，设备验收仍未知。
