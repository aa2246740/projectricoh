# REA 与 GXR 静态分析工具审计

结论：REA 6.4.0 可以作为项目内、只读 CLI 留下来，但它不能反编译 Ricoh GXR 的主程序。GXR 现有样本被判定为 Renesas M32R 专用多段映像，REA 发布包不支持裸二进制，REA 当前源码的裸二进制入口也没有 M32R。为这项研究安装 Ghidra、JDK 或 radare2 不会补上这个缺口。

第一条产品路线应先验证官方 My Settings。固件 1.51 已有 6 个机身 My Settings Box 和 6 个 SD 卡槽。必须先确认每个槽是否独立保存 Setting 1/2 的色彩数值。若只保存“选择 Setting 1 或 Setting 2”，实际可保存的完整色彩配方仍然只有两套。

审计日期为 2026-10-12。REA 源码工作树为 `ee50ed121e38cc6e1a2ff0dc8b789f15f71c5402`。npm 6.4.0 发布包的 `gitHead` 是 `a56f7bb668ab23fec8d33f7af353ac7ed2fe1895`。两者版本号相同，功能不同。

## 能否胜任

| 任务 | 判断 | 直接证据 |
| --- | --- | --- |
| 启动本地 CLI，查看版本、provider 与诊断 | 可以 | 项目内 smoke 已证明 `--version` 和 `providers --json` 退出码为 0，[完整 probe 记录](../../artifacts/rea/probes.json)。 |
| 分析普通 ARM/AArch64/x86/x64 有头可执行文件 | 可以，需要 Hopper、Ghidra 或 IDA | REA 的 native 命令只是统一 CLI，真正分析由外部 provider 完成，[README 148-181](../../sources/rea/README.md#L148-L181)。 |
| 分析 MIPS | 有严格边界 | npm 6.4.0 只接收带 ELF 声明的 MIPS32r2/o32 形状。当前文档也明确区分 MIPS 家族识别和 provider 支持，[`ghidra-mips.md` 9-23](../../sources/rea/docs/ghidra-mips.md#L9-L23)。MIPS 与 M32R 是不同 ISA。 |
| 分析 ARM 裸二进制 | 当前 main 可以，npm 6.4.0 不可以 | 当前 main 只允许 `x86/x86_64/arm/arm64`，[`rawBinary.ts` 7-16](../../sources/rea/src/domain/rawBinary.ts#L7-L16)，并把 ARM 固定为小端 ARMv7，[`raw-binary.md` 28-45](../../sources/rea/docs/raw-binary.md#L28-L45)。发布 tarball 中没有 `raw-binary` 代码，[发布包 `dosCom.js` 3-6](../../tools/rea/package/dist/domain/dosCom.js#L3-L6)把 `--target-format` 限定为 `dos-com`。 |
| 分析 GXR `ilaunch3` | 不可以 | GXR 报告把它判为 Renesas M32R，并记录 16 个装载段，[初步报告 13-21](../../sources/gxr-language-patch/研究资料/报告/GXR_1.51_逆向初步报告.md#L13-L21)。REA 不支持 M32R，也不能表达 16 段各自的文件偏移、装载地址和 BSS。 |
| 用 REA 固件命令拆 GXR 官方 ZIP | 不推荐 | 固件 provider 依赖 Binwalk 3.1.x、Unblob 26.6.x 和 Linux `prlimit`，首个里程碑只在 Linux x64 验证，[`firmware-analysis.md` 1-26](../../sources/rea/docs/firmware-analysis.md#L1-L26)。GXR 已有能解析其专用头和段表的只读脚本。 |
| 使用 Ghidra 12.1.4 的 M32R 后端 | 不可以 | [Ghidra 12.1.4 官方 Processor 目录](https://api.github.com/repos/NationalSecurityAgency/ghidra/contents/Ghidra/Processors?ref=Ghidra_12.1.4_build)没有 M32R、FR、FR-V 或 TX19。Ghidra 官方文档说明每种 CPU 必须有对应 language module，[Processor Languages](https://github.com/NationalSecurityAgency/ghidra/blob/Ghidra_12.1.4_build/Ghidra/Features/Base/src/main/help/help/topics/LanguageProviderPlugin/Languages.htm)。 |
| 使用 radare2 的 M32R 后端 | 不可以 | [radare2 官方源码树](https://api.github.com/repos/radareorg/radare2/git/trees/master?recursive=1)没有 M32R、FR、FR-V 或 TX19 插件。radare2 的插件文档也说明完整 CPU 支持需要专门的 `r_arch` 实现，[官方插件开发说明](https://github.com/radareorg/radare2-book/blob/master/src/plugins/dev.md)。radare2 也不是 REA 的 native provider。 |

`FR/MIPS/TX19/ARM` 不能作为“可能差不多”的替代选择。M32R 是现有逆向证据给出的高置信度判断，并非 Ricoh 的公开 CPU 声明。重新判断 ISA 时应使用独立 opcode 对照和控制流一致性，不应根据厂商或年代猜架构。

## 发布包与 current main 的边界

[npm registry 的 6.4.0 元数据](https://registry.npmjs.org/rea-agents/6.4.0)给出的发布事实如下：

- tarball SHA-1：`c919f5c7742ab2abf601db422e4e8fea36d511c2`
- tarball SHA-512：`563d7359f4a59dae5ba611a86a823f4dc541b98bf37bdbbe3b23c2dd2873f18901a9a093a81e023a79d1a17ed70f0329c08db86651447a5db2123d24f0b4d611`
- 本次下载实测 SHA-256：`59eb1604b8db75f522d4a975c36ce6b4a2ad465e43bad165f9a8f728391db9b8`
- registry 记录 1,161 个文件，解包大小 7,776,450 字节；下载 tarball 实测 1,825,761 字节。
- 发布 `gitHead` 为 `a56f7bb668ab23fec8d33f7af353ac7ed2fe1895`。

当前源码文档自己也记录了这个发布 commit，并提醒 main 的功能可能尚未发布，[`installation.md` 83-112](../../sources/rea/docs/installation.md#L83-L112)。因此不能用 current main 的 `raw-binary` 文档声称 npm 6.4.0 已支持该功能。

REA 是 host/CLI wrapper 的具体含义如下：

- `scripts/rea.mjs` 负责分派 CLI 或 MCP，并检查 `dist` 是否存在，[发布包入口 33-63](../../tools/rea/package/scripts/rea.mjs#L33-L63)。
- native 反汇编、反编译和 xref 来自 Hopper、Ghidra 或 IDA。REA 负责选择 provider、启动隔离进程、统一结果和证据格式。
- 固件识别和拆包来自调用者提供的 Binwalk 与 Unblob。REA 不内置这两个引擎，[`firmware-analysis.md` 12-47](../../sources/rea/docs/firmware-analysis.md#L12-L47)。
- REA 的 Java bridge 扩展 Ghidra 调用流程，但不会凭空增加 Ghidra 没有的 CPU language module。

## macOS arm64 的最小项目内安装

推荐只安装 npm 发布包和非浏览器依赖，不运行 `install.sh`、`setup` 或 `update`。上游 `install.sh` 默认执行全局 npm 安装，并在有终端时继续启动 `rea setup`，[发布包 `install.sh` 88-121](../../tools/rea/package/install.sh#L88-L121)。这不符合本项目的隔离要求。

发布包要求 Node.js 22.19+、24.11+ 或 26+，[发布包 `install.sh` 62-70](../../tools/rea/package/install.sh#L62-L70)。本机 smoke 使用 Node.js 26.7.0。

`playwright-core@1.58.2` 是生产依赖，[发布包 `package.json` 265-300](../../tools/rea/package/package.json#L265-L300)，但 native CLI 不需要它。发布 CLI 只在执行 browser scenario 时动态加载对应实现，[`cliBrowserScenarioCommands.js` 21-30](../../tools/rea/package/dist/cliBrowserScenarioCommands.js#L21-L30)；Electron active 命令也在执行时才加载，[`electronCommands.js` 23-43](../../tools/rea/package/dist/cli/electronCommands.js#L23-L43)。MCP 把可选 provider 的加载错误单独记录，[`optionalObservationProviders.js` 16-52](../../tools/rea/package/dist/composition/optionalObservationProviders.js#L16-L52)。本项目从独立依赖清单中删掉 `playwright-core`，也不运行任何 REA browser/Electron active 命令。

项目已经按这个边界完成安装。`tools/rea/package/` 保存官方 tarball 的原始解包内容；`tools/rea/deps/package.json` 是单独的运行依赖清单，其 `dependencies` 复制发布包依赖并删除 `playwright-core`。`tools/rea/package/node_modules` 只链接到 `../deps/node_modules`，没有改发布包的 `package.json`。

```sh
# 1. 核对已经下载的官方 tarball。
shasum -a 256 artifacts/downloads/rea-agents-6.4.0.tgz
shasum -a 512 artifacts/downloads/rea-agents-6.4.0.tgz

# 2. 从锁文件重建项目内依赖。禁用全部生命周期脚本。
npm ci --prefix tools/rea/deps --omit=dev --ignore-scripts --no-audit --no-fund

# 3. 不运行 setup，通过项目 wrapper 调用发布入口。
sh scripts/rea --version
sh scripts/rea providers --json
```

安装后的依赖目录为 `tools/rea/deps/node_modules`，实测约 75 MiB；发布包约 9.9 MiB。该依赖树没有 `playwright-core`。`--ignore-scripts` 会跳过依赖的原生构建脚本，因此若某个可选原生模块不可用，应保留这个限制，不能为 GXR 目的放开全部脚本。

已执行的 smoke 结果保存在 [`artifacts/rea/probes.json`](../../artifacts/rea/probes.json)：

- `--version` 返回 `6.4.0`，退出码为 0。
- `providers --json` 返回能力清单，退出码为 0；Ghidra 状态是 `not_configured`。
- `inspect-artifact artifacts/downloads/gxr-151.zip --json` 成功列出 ZIP 内 32 个节点，但只证明通用 ZIP 清单能力。
- 直接 `inspect ilaunch3 --provider ghidra --json` 返回 `unsupported binary format`。
- `--target-format raw-binary` 返回 `Invalid input: expected "dos-com"`。
- `inspect-firmware-regions ilaunch3 --json` 返回需要 Linux 和调用者提供的 Binwalk 路径。

若主机已有 Ghidra 和 JDK，可只做诊断，不做 setup：

```sh
GHIDRA_INSTALL_DIR=/absolute/path/to/ghidra_12.1.4_PUBLIC \
JAVA_HOME=/absolute/path/to/jdk-21 \
sh scripts/rea doctor --provider ghidra --json
```

REA 接受 Ghidra 12.1.x 和该安装声明的 64 位 full JDK。当前 12.1 需要 JDK 21 或更新版本；上游只用 Ghidra 12.1.4 和 JDK 21 做过 bridge 验证，[`installation.md` 684-751](../../sources/rea/docs/installation.md#L684-L751)。这些依赖对 GXR M32R 没有帮助，所以本项目无需为 REA 新装它们。

发布能力的负向 smoke 可以直接证明 raw 入口不存在：

```sh
sh scripts/rea inspect artifacts/firmware/gxr-1.51/ilaunch3 \
  --target-format raw-binary --provider ghidra --json
```

本机实测退出码为 1，参数校验拒绝 `raw-binary`，并提示只接受 `dos-com`。它证明 npm 6.4.0 的 CLI 边界，不证明 current main，也不证明任何相机固件行为。

## 网络、密钥和配置副作用

事实：

- CLI 静态 native 分析不需要 LLM、模型账号或 API key。发布依赖中没有 OpenAI、Anthropic 或遥测 SDK。发布 README 声明分析在本机运行，[README 51-55](../../tools/rea/package/README.md#L51-L55)。
- 使用 MCP 时，REA 会把结果交给连接的 agent。agent 的模型提供商有自己的数据政策，[README 267-270](../../tools/rea/package/README.md#L267-L270)。本报告建议只用 CLI。
- `setup` 会写用户级 agent/MCP 配置和 skill；在批准后还可能安装 Hopper。Quick start 明确写了这些副作用，[README 59-75](../../tools/rea/package/README.md#L59-L75)。不要运行。
- `update` 与 `npx @latest` 会访问 npm。不要用于离线分析。
- `npm ci` 需要联网取依赖。安装完成后，本报告列出的版本查询、ZIP 清单和 native 静态分析命令不需要联网。
- 固件 provider、Ghidra provider 本身处理本地文件。某些其他 REA 功能会连接指定浏览器、下载 Hopper、访问本地调试端口或调用外部工具。只执行本报告列出的命令。
- REA 会建立临时 Ghidra project、私有 runtime/cache/config/temp 目录，关闭时清理。它用 `-readOnly` 和 `-deleteProject`，不会改可执行文件，[`installation.md` 753-767](../../sources/rea/docs/installation.md#L753-L767)。若清理身份无法确认，它会保留临时资源供诊断。

固件 provider 的资源限制是 128 MiB 输入、120 秒、单进程 1 GiB 地址空间、8 MiB JSON 报告、默认 256 MiB/10,000 项输出，[`firmware-analysis.md` 130-150](../../sources/rea/docs/firmware-analysis.md#L130-L150)。官方 `gxr-151.zip` 实测 11,277,528 字节，SHA-256 为 `3705984b8433c40d2ed4fd2600c11f03ed8a6de7dbe7f66efd38ee5ca15fc898`，体积在限制内。但 macOS 缺少这条已验证的 Linux `prlimit` 路径，且 Binwalk/Unblob不会理解 GXR 专用装载段语义。

## GXR 的可用离线分析路径

现有项目脚本比 REA 更贴合样本：

- [`gxr151_analyzer.py` 75-95](../../sources/gxr-language-patch/研究资料/工具/只读分析/gxr151_analyzer.py#L75-L95)解析 20 字节大端段记录，并保留文件偏移和运行地址映射。
- 同一脚本能提取 16 个初始化段供外部反汇编器使用，[`gxr151_analyzer.py` 236-253](../../sources/gxr-language-patch/研究资料/工具/只读分析/gxr151_analyzer.py#L236-L253)。
- GNU Binutils/GDB 的官方源码历史包含 M32R disassembler 和 simulator，[`m32r-dis.c` 变更记录](https://sourceware.org/pipermail/binutils-cvs/2020-June/053652.html)与 [M32R simulator 变更记录](https://sourceware.org/pipermail/gdb-cvs/2021-July/051004.html)。后续若需要完整指令清单，应固定一个含 M32R target 的 Binutils 版本，在项目内构建，再对每个段使用独立的装载地址。不要把它接成 REA 的 MIPS 或 ARM provider。

建议的反汇编命令形状如下。它是后续工具验收目标，尚未在本轮安装或运行：

```sh
m32r-elf-objdump -D -b binary -m m32r -EB \
  --adjust-vma=0x2004B000 ilaunch3_sec00_load_2004b000.bin
```

必须用已知函数的 opcode 和分支目标做正向校验。项目现有实验脚本提供一个待复核的测试向量：M32R 直接 `BL` 的首字节为 `0xFE`，24 位有符号位移乘 4 后加到对齐 PC，[`build_gxr151_bkizram_export_experiment.py` 74-90](../../sources/gxr-language-patch/研究资料/工具/实验构建/build_gxr151_bkizram_export_experiment.py#L74-L90)。如果固定版本的 objdump 对这些位置解不出相同目标，先停止后续分析。

## 三条配方扩展路线

### 1. 先用现有 My Settings

推荐先做这条。GXR 用户手册说明 Image Settings 的 Setting 1 和 Setting 2 各自包含 vividness、contrast、sharpness、颜色和 hue，[官方 GXR 手册](https://www.ricoh-imaging.co.jp/english/r_dc/support/manual/pdf/gxr/GXR_E.pdf)，印刷页 71。手册同时说明 My Settings 可以保存拍摄菜单选项，最多建立 6 套机身设置，印刷页 129 至 132。官方功能表显示固件 1.50 加入 6 个 SD 卡槽，1.51 沿用该功能，[官方功能表的本地证据 533-542](../recipes/sources/feature-table.html#L533-L542)。A16 与 MOUNT A12 手册明确写为 My Settings Box 1-6 和 Card 1-6，[A16 手册](https://www.ricoh-imaging.co.jp/english/r_dc/support/manual/pdf/gxr/a16_en.pdf)印刷页 34，[MOUNT A12 手册](https://www.ricoh-imaging.co.jp/english/r_dc/support/manual/pdf/gxr/mount_a12_en.pdf)印刷页 38。

未知项：文档只证明 My Settings 保存 Image Settings 这个拍摄菜单项。它没有证明每个 My Settings 记录都嵌入 Setting 1/2 的五组数值。数值可能仍来自两个全局槽。

最小验证不需要刷机：

1. 把 Setting 1 调成极端组合 A，保存到 Card 1。
2. 把 Setting 1 调成明显不同的组合 B，保存到 Card 2。
3. 召回 Card 1，进入 Setting 1 编辑页，逐项记录数值，再召回 Card 2 重复。
4. 各拍一张同场景 JPEG，并保留 EXIF、照片和操作视频。
5. 在电脑上只读捕获 SD 卡的实际目录布局。固件字符串给出的静态候选路径包括 `/ATA1/MYSET`、`/MYSET`、`.IFO` 和 `/ATA1/MYSET/MYSET*.IFO`，这些字符串还不是实际 SD 卡取证结果。记录捕获到的文件名、大小、SHA-256 和 A/B 二进制差异。

若 A/B 数值能随 Card 1/2 恢复，官方机制可以保存多套完整拍摄配方。它会连曝光等拍摄设置一起切换，仍不能算独立色彩配方库；只切换颜色参数的产品目标需要另做。若两者都变成最后编辑的 B，My Settings 只保存选择，不能算完整色彩配方槽。

### 2. 直接增加 Setting 槽

这条改动最大。至少要同时找到并验证：

- Setting 枚举和菜单项表；
- 每槽色彩参数结构、数组长度和默认值；
- NVRAM/配置序列化长度、版本与校验；
- body 到 camera unit 的命令和结构；
- JPEG 处理链对新槽的实际应用；
- 每个 camera unit 固件的兼容行为。

`ilaunch3` 是 16 段 M32R 专用映像，[段表 CSV](../../sources/gxr-language-patch/研究资料/结构化结果/gxr151_ilaunch3_sections.csv)。官方手册也说明 My Settings 可保存项目随 camera unit 而变化，[GXR 手册印刷页 129](https://www.ricoh-imaging.co.jp/english/r_dc/support/manual/pdf/gxr/GXR_E.pdf)。因此不能只改机身菜单数量。新增菜单项、能选中和不崩溃都不能证明参数已保存或影响 JPEG。

最小静态验证应先在 `ilaunch3` 和每个 `j/k/n/q/l06/l08 ...3` 中定位相同的默认值、范围和 body/unit 通信，再构造一个离线 round-trip：编码现有 Setting 1，解析回来后每个字段与原始值相同。没有这个结构证据前，不制作刷写包。

### 3. SD 外部配方

官方 1.51 已有固定的 Card 1-6，不是任意数量文件的配方浏览器。最小改法可以把外部配方导入一个现有 Card 槽，再用官方 Recall My Settings 调到 MY1/MY2/MY3。直接扫描任意文件会新增文件枚举、命名、版本、校验、camera unit 匹配、损坏文件处理和 SD 拔出行为，风险接近新增一套持久化系统。

先完成 Card 1/2 的文件取证。确认一个 `.IFO` 是否包含完整色彩数值、是否绑定机身或 camera unit、是否有校验。随后才能判断外部配方是“复制一个已知格式文件”还是“需要修改固件 loader”。未知来源 `.IFO` 不应直接放入相机测试。

## 恢复机制的判断标准

正常启动后从菜单重刷官方 1.51 只能算回滚流程。它不是砖机救援。若修改后的 `ilaunch3` 无法启动，用户可能无法进入官方升级菜单。

现有研究确认 `ilaunch0` 是 Monitor/维护组件，并发现 ROM 擦除、转储、升级和备份程序命令，[初步报告 161-183](../../sources/gxr-language-patch/研究资料/报告/GXR_1.51_逆向初步报告.md#L161-L183)。这些字符串和静态代码还不能证明主程序损坏时仍有可操作、可重复的恢复入口。

在任何首次刷写前，恢复验收必须独立于被修改的 `ilaunch3`：

1. 明确由 `ilaunch0` 或更低层启动代码接管的按键或 SD 入口。
2. 证明它在主程序不可启动的模拟条件下仍读取官方包。
3. 证明它校验并恢复官方 `ilaunch3`，不会覆盖序列号、校准和调整区。
4. 记录失败断电点及再次恢复行为。

当前没有这些证据，所以本阶段只能做离线分析和官方 My Settings 的无刷机验证。
