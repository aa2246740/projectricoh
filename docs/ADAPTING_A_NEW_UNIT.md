# 自行适配新的 GXR 单元

本指南供愿意独立研究的开发者接手新单元，例如 P10。本项目目前研究的运行单元是 A12 50mm、A12 28mm 和 MOUNT；P10 尚未适配。机主不计划开发 P10，也不提供移植、刷机或故障支持。

这是非官方固件修改，可能导致相机或单元无法启动、照片丢失，甚至变砖。是否实验、怎样恢复及全部后果由操作者自行承担。原厂正常升级器可用时的恢复经验，不能证明损坏主程序后仍可救回。

## 先分清公开代码和本地输入

仓库提供项目自编源码、研究方法和文字结论。你需要自己取得官方固件、工具链和实验数据。原厂固件、提取表、指令清单、DAT 成品、机身映像、照片、照片派生图像、GPS、保存的理光网页、第三方 LUT 和第三方原始数据均不随仓库提供。所有 `local/` 都是本地目录。

这份公开快照也不承诺一次命令复现最新相机包。部分研究脚本依赖未公开的历史 `local/` 输入；完整模拟器含待隔离的原厂指令样例和绑定快照，本轮没有准入。正在并发修改的 `firmware/*`、`research/g162`、`research/v310b` 和卡库探针目录，须在各任务结束后另审。具体范围见 [R2 同步审计](../research/git_sync/REPORT_R2.md)。你可以采用自己的拆包器、反汇编器、模拟器和颜色建模方法，保留下面的身份、事务和验收约束。

## 认识机身、DAT 和单元的分工

机身 MAIN 是 `ilaunch3`。v3.10 把一个小型 resident 放进机身 MAIN 的固定窗口，负责菜单入口、DAT 装载、服务白名单、会话及 epoch、单元身份和错误退役。它从卡上的 `GXRCE.DAT` 或已存在的内部候选槽读取引擎，校验长度、CRC、机身身份、resident build、ABI 和重定位，再进行纯初始化。校验通过以后才发布 READY。卡 DAT 优先并不表示已经运行的引擎会随卡文件自动热换。

DAT 承载配方库、菜单与微调逻辑、颜色计算和开机策略。修改配方或 DAT 策略不一定需要重刷机身；装载之前的 resident 缺陷无法由尚未执行的 DAT 修复。入口与生命周期可从 [resident 装载器](../firmware/resident_v310_g155/resident/loader.c)、[resident 类型和容量](../firmware/resident_v310_g155/resident/resident.h)以及 [g155 报告](../research/g155/REPORT.md)读起。旧头文件里的早期默认值不等于当前产品预算。

当前系列的 DAT 使用 `GXRCE001` 标识、256 B 头和七个分区，组合代码、重定位及配方数据。配方描述符引用共享行池，运行时可展开成 552 B 记录；不能把早期 448 B 记录直接塞进当前格式。记录包含曲线、色度表、矩阵、flags、控制字段和各区 CRC。Look 通过基底槽位和行引用复用数据，用户微调再按该基底的控制合同生成目标。[格式读取器](../research/v39_g153/dat_format.py)展示当前记录的展开与校验；它只含项目格式定义，不附任何原厂记录。

颜色研究模型把曲线、C100、C080 和 C040 分开处理。

- 曲线描述输入输出节点；共享曲线和独立 RGB 曲线使用不同的记录合同。
- C100 是矩阵阶段，涉及亮度和色度分量。记录存在矩阵不表示执行路径一定启用了它，flags 也必须正确。
- C080 提供色度扇区系数，并受原厂色相、饱和度设置和截断规则影响。
- C040 描述扇区节点与角向几何。不同单元的节点不同，不能把 50mm 的节点直接用于 MOUNT 或 P10。

这仍是分条件验证的主机模型。ISO、白平衡、原厂模式、低饱和区域和整数边界会改变路径；模型分数不等于新单元拍出的 JPEG。[多单元建模代码](../research/module_adapt/unit_model.py)、[C040 读取与几何处理](../research/module_adapt/c040.py)和 [C040 修正报告](../research/model_c040_r1/REPORT.md)保留了这些限制。现有代码只枚举三个研究单元，P10 需要自行扩展。

v3.10 的 H50 记录启动机会，H51 调用共用装载器并派发一次 BOOT_RUN，H52 在 DIRTY 或 GUARD 非零时拒绝受保护的快门请求。是否自动套用、怎样解释保存记录及何时写颜色，由 DAT 决定。g158 test 与 release 的 BOOT 策略不同，不能仅凭 resident 版本推断自动套用已启用。

配方记忆使用设置块内的项目自有 40 B 记录，保存引用、微调和身份绑定，跨开机恢复依赖原厂保存链。它不保存可跨单元复用的 RAM 指针。读取记忆、接受记忆、决定自动套用和实际写入是四件事，分别记录结果。换代或换单元后拒收旧记忆可以是预期行为。[g157 报告](../research/g157/REPORT.md)说明了这次拆分。

P1 是有回读和补偿的颜色事务，手动套用和 BOOT 各有编排。先冻结单元身份、S、行、T、lease 和 epoch，计算完整目标并确认资格；PREPARE 通过以后，在第一笔单元、S 或 T 写入前置 DIRTY，再 APPLY 并核对完整目标。失败走 CANCEL 和完整纯 04 补偿，只有最终回读全部通过才清 DIRTY。无法确认补偿时保留 GUARD、拒绝快门并退役，不能只因为 RPC 返回成功就解锁。完整设置 S、颜色行和 T 必须一起检查。[g158 验收报告](../research/g158/REPORT.md)区分了主机、最终 DAT 指令和整机模型的覆盖。

## 核对文件族

官方 1.51 包的映射如下。前缀不能从字母顺序猜。

| 对象 | 文件族 | MAIN |
| --- | --- | --- |
| GXR 机身 | `ilaunch*` | `ilaunch3` |
| A12 50mm Macro | `jlaunch*` | `jlaunch3` |
| A12 28mm | `qlaunch*` | `qlaunch3` |
| MOUNT A12 | `l08firm*` | `l08firm3` |
| P10 28–300mm | `klaunch*` | `klaunch3` |
| S10 24–72mm | `nlaunch*` | `nlaunch3` |
| A16 | `l06firm*` | `l06firm3` |

P10 与 S10 的对应关系由 [六单元研究](../research/hw_mining_r3/grok/REPORT.md)核对。机身及 A12 的早期定位依据见 [固件结构报告](../research/firmware/REPORT.md)。通常 `*0` 是维护组件，`*3` 是主程序，`*4` 是资源，`*8` 是初始化脚本；A16 另有 `l06firm5`。不要把不同文件族或不同版本的地址、段表、颜色行混用。

## 1. 自行准备官方 1.51 和恢复副本

从[理光官方 GXR 下载页](https://www.ricoh-imaging.co.jp/english/r_dc/download/firmware/gxr/index.html)自行下载 1.51 ZIP，并阅读官方升级说明。仓库不提供归档或恢复包。把下载物放进本机被忽略的目录，例如 `artifacts/downloads/gxr-151.zip`；保存一份独立、未经修改的官方恢复副本。

新准备脚本只用 Python 标准库，沿用本项目已有的 29 文件哈希基准。它不依赖 `sources/` 中的第三方源码，不下载、不打补丁、不刷机。以下命令必须从仓库根执行。

```sh
nice -n 15 python3 -I -B scripts/prepare_unit_workspace.py \
  artifacts/downloads/gxr-151.zip \
  --unit p10 --output research/unit_adapt/local/p10 --extract
```

成功时会报告 `official_members_verified: 29`、`prefix: klaunch` 和 `current_engine_support: false`。未经修改的文件写入该目录的 `official/`，段表与哈希写入 `inventory.json`。所有输出继续留在本地。已有文件内容不同就停止，不覆盖。哈希匹配只证明与项目固定输入一致，不是理光签名，也不是 P10 兼容性证明。

## 2. 在本地定位段、调用链和数据

先读取 `inventory.json` 中 `ilaunch3` 和 `klaunch3` 的段表。文件偏移与运行地址不同；每次访问都必须落在唯一的有效段内。可用已有结构扫描器进一步生成本地报告。

```sh
nice -n 15 python3 -I -B research/firmware/scan_gxr_firmware.py \
  research/unit_adapt/local/p10/official \
  --output research/unit_adapt/local/p10/structure.json
```

该报告会含原厂字符串和结构数据，只能留在 `local/`。使用自己的 M32R 工具恢复调用链，逐个核对文件 SHA、段地址、读写宽度及消费者。长零区、填充区和地址相近都不能证明那里可放代码。[M32R 工具链研究](../research/tooling_m32r_c/REPORT.md)和现有解析脚本可作参考，工具链二进制需要自行准备。

## 3. 先建立单元身份门

将 P10 当成一个新的类型加入合同，不能把它伪装成 50mm 或只放宽型号字符串。逐层核对 resident 的单元快照、DAT 的单元信任项、版本检查、原厂记录 pin、模块索引、可见条目和模型枚举。当前格式多处固定三个单元，增加第四单元需要同时审查 C 解析器、打包器、所有数组边界、用户记录和主机读取器。

运行时名称、MAIN 主版本和内部子版本要与自己的官方输入及实际调用结果相符。当前 A12/MOUNT 的许可条件不能直接推给 P10；相机版本页的 CV 也不是内部子版本。记录完整版本页，再独立证明运行时字段的含义。

故意测试错误型号、旧版本、坏 pin、装载期间换身份及 READY 后 epoch 变化。预期是执行前拒绝或撤销会话，并且零颜色写入。原厂记录 CRC 或 pin 不等于整份单元 ROM 的哈希证明。

## 4. 重建 P10 自己的颜色路径

独立定位 P10 的曲线、C100、C080、C040、原厂基准记录、S/T 字段及其读写入口，证明每一项由哪条实际路径使用。现有 [模块提取脚本](../research/module_adapt/extract.py)依赖三单元的本地定位回执；不能直接用 `--unit p10`，也不能把旧单元偏移当成发现结果。

把原厂数据、原始指令和定位回执保存在新任务的 `local/`。公开部分只放读取算法、接口定义及不含原厂表的报告。给每份本地表绑定原文件 SHA、段、偏移、长度和生成脚本哈希，避免旧缓存悄悄沿用。

先做原厂 04 的恒等对照，再做一个最小自编变化。用自己的 RAW/JPEG 同次配对、固定光源和设置验证预测；分离训练页、留出页与场景，记录 ISO、WB、镜头与校正设置。现有 [交换格式](../research/module_adapt/EXCHANGE.md)、[JSON schema](../research/module_adapt/exchange.schema.json)和 [标定脚本](../research/module_adapt/calibrate.py)可以改作自己的入口，但目前的单元白名单和历史数据依赖仍需你处理。第三方 LUT 不随仓库提供，也不能把它当成新单元的实测真值。

## 5. 先做主机和模拟器验证

选择并审查自己的模拟器。仓库目前公开的研究方法和测试编排可作规格；完整 `tools/gxr_emulator*`、`tools/native_harness*`、固件映像、GNU 构建目录和运行快照不在这次准入清单中。不能以缺少输入为由编造成功返回。GNU 源码若自行使用，应遵守其许可证。

依次验证实际格式解析器、目标 M32R 代码、装载器与机身 MAIN，再谈相机。每一步保存实际构建身份及首个失败，区分声明的设备输入和真正执行的原厂指令。未知 opcode、MMIO、RPC 或曝光返回值必须停在明确的模型边界。[g158 的 slot31 说明](../research/g158/SLOT31.md)展示了为何把未知返回值填成成功会使验收失真。

至少覆盖这些独立场景。

- 验证原厂 04 恒等、完整 552 B 展开、CRC、flags、错误长度和重定位边界。
- 验证无 DAT、损坏 DAT、错误机身/build/ABI、分配失败、SD 晚到、单元晚到和旧内部槽。
- 验证首次 ADJ、重入、微调、保存、换单元、旧记忆拒收和下一次完整冷启动。
- 对 P1 每一笔写入注入写后错误、BUSY、身份变化和持续故障，证明完整补偿或 GUARD；手动与 BOOT 分别验。
- 从 MAIN 冷启动验证正常、延迟和失败路径。恢复快照不能替代存储初始化或开机时序测试。

所有读固件的 Python 命令使用 `-I -B`，计算使用 `nice -n 15`。如在同一台 Mac 并发，使用 [loadgate.py](../tools/loadgate.py) 的 `cap(running)`，每次采样最多放行一个新进程，返回原上限就继续推迟；不要因队列已有空位直接填满。计时比较改用 `quiet_for_timing()`。它依赖 macOS 的 `iostat` 和 `sysctl`，不是跨平台调度器。

## 6. 单独安排现场安全测试

只用你有权承担损失的机身、目标单元和备用卡。先备份照片，准备满电电池与独立官方恢复副本，并确认正常升级器可用。写入前冻结候选 SHA 和改动范围，核对目标型号、版本及卡文件读回；确认界面不符就退出，不猜按键继续。

先在官方固件上记录正常启动、版本页、菜单和 JPEG+DNG 基线。再按一个变化一个测试的顺序，检查候选启动、首次 ADJ、原厂 04、最小颜色变化、重入、保存及下一次开机。普通重启和取电池后的冷启动分开记录。手动套用成功后再试 BOOT；首张照片单独验，不能用之后手动套用的照片替代。

出现掉表、卡死、黑屏、颜色污染或未知状态就停止新增实验，保存第一次失败及当前版本、包哈希、单元和动作顺序。不要通过清 GUARD、放宽身份门或反复刷入来取得一次成功。写入已经开始时，不用拔电池、拔卡或拆单元中止。

[历史现场清单](../research/g158/OWNER_STEPS.md)和 [早期刷写与恢复说明](../research/phase0_drill/FLASH_AND_RECOVERY.md)描述的是对应旧包与机身，供你编写自己的 P10 清单；它们不是 P10 已获验收的步骤。

## 7. 恢复官方固件并核对结果

相机仍能启动、读卡并进入正常升级器时，按理光官方说明使用未经修改的完整 1.51 文件恢复。连接哪个单元就核对哪个单元；机身更新过不等于所有未连接单元都已更新。不要混合候选与官方文件，不把移走 DAT 当成刷回官方 MAIN。

恢复后分别核对 BODY 与 CAMERA UNIT 版本、正常关机再开机、原厂列表、拍摄、回放及 JPEG+DNG。相机仍显示 1.51 不能证明项目 resident 已不存在，需结合所用官方包和完整更新过程判断。已有官方恢复记录仅覆盖正常升级链可用的条件，坏 MAIN、无法启动或升级器不可用时的救援没有通用保证。

## 已知限制必须带进新移植

### v3.10 的早期 SD 装载缺陷

v3.10 可在首次 ADJ 之前从 H51 装载 DAT。如果此时正式文件打开失败，它可能消费装载机会并退役；SD 稍后可读也不会自动重来。关闭 DAT 内的 BOOT 策略不能修复 DAT 执行前的失败。

[unit_persist_r1](../research/unit_persist_r1/REPORT.md)已在三单元 MAIN 模型复现这条路径，并验证增加 88 B 的 loader 后补候选可保留到首次 ADJ 装载。它不保证迟到那次开机的首张自动套用，也不能单凭模型认定朋友相机就命中此根因。工作目录 `research/v310b` 正据此准备 v3.10b；本次同步开始时仍在构建，相关新固件和回执没有公开。采用前须等该任务的最终报告、严格链接、身份绑定及独立验收，不能把“+88 B 能放下”当成交付完成。

### 代数绝不复用

每个候选、诊断包和探针都使用未占用的新 generation，包括只在主机使用的探针。扫描 tracked、untracked、ignored、本地归档及 DAT 实际头，另查源码和清单并设置已知阳性对照；文件名和公开 Git 历史不足以判定空闲。多位开发者应先约定各自的编号登记方式，合并前再次查重。

[g159](../research/g159/REPORT.md)遇到了既有主机 EXIF 夹具占用，[g160](../research/g160/REPORT.md)遇到了历史诊断 DAT。对应扫描器按该次固定代数写成，不能把命令参数换成任意新数就当通用分配器。换代还要更新 gate、引擎常量、头、全部读取器及记忆拒收测试。

### 主请求内存上限

g158 参考产品的主请求上限为 107,612 B，代码上限为 69,632 B。test 的主请求为 106,940 B，代码为 69,624 B；分别只余 672 B 和 8 B。新增单元要计算实际最终 DAT、代码、BSS、重定位、对齐及 resident 主块开销，不能只算行池去重后的文件大小。数值以固定版本的 [g158 字节账](../research/g158/REPORT.md)为准，不是 P10 的实测可用堆；一般 envelope 的更大上限也不能代替产品预算。容量不足就重新设计并统一所有读者，不单独放宽一个断言。

### Look flags 跟随实际引用的基底

每个单元上，Look 的 flags 必须与它实际引用的 base 槽一致，不能要求所有 Look 都等于 05。基底还决定默认微调项和行为；把 Acros 从 03 重绑到 05–08，即使默认颜色数据不变，也可能失去 Filt 操作。[g159 的实际 C 反例](../research/g159/REPORT.md)记录了这种差异。常见共享曲线记录为 flags=1，独立 RGB 组合为 flags=7，但应以目标版本解析器为准，不能只改 flags 假装格式已经兼容。

## English summary

P10 uses `klaunch*`; S10 uses `nlaunch*`. Download official GXR 1.51 yourself, keep firmware and extracted data in ignored local directories, and independently establish the new unit's identity, color pipeline, memory budget, transactional recovery, and cold-boot behavior. The helper verifies and extracts local inputs; it does not add P10 engine support. Current simulator inputs and unfinished firmware work are excluded from this public snapshot. This is an unsupported, unofficial modification with a risk of permanent device damage. You assume responsibility for your own port and hardware tests.
