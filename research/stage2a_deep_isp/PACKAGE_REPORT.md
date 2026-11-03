# Stage 2a Canonical GR 候选包交付报告

两套完整候选包已通过本机验证，可供审阅。safe 包禁用深层 RPC，deep 包按指定 preflight 启用四套 SDRAM 表。相机刷写、ISO/ADJ 真机操作、SDRAM 可写性和画质验收均未执行。

本轮没有访问任何 `/Volumes/*` 路径。原厂输入和已有 Stage 1 包未改写。原厂文件实际读取自项目内 `artifacts/firmware/gxr-1.51/`，没有创建或改写 `firmware/official/`。

## 两套完整目录

- [stage2a-canonical-gr-safe](../../artifacts/stage2a-packages/stage2a-canonical-gr-safe/) 的 `candidate/SD_ROOT/` 包含 29 个固件组件、`RECIPE20.DAT`、`RECIPE21.DAT` 和额外要求的 v1 `RECIPES0.DAT`，共 32 文件。
- [stage2a-canonical-gr-deep-isp](../../artifacts/stage2a-packages/stage2a-canonical-gr-deep-isp/) 的 `candidate/SD_ROOT/` 包含 29 个固件组件、`RECIPE20.DAT`、`RECIPE21.DAT`、`DEEPISP0.DAT`、`DEEPISP1.DAT`，共 33 文件。

每套均带 `recovery-official-1.51/SD_ROOT/` 的 29 个原厂文件、根目录 `SHA256SUMS`、`manifest.json`、说明及 `evidence/`。仅候选 `ilaunch3` 改动，其余 28 组件和恢复目录全部逐字节等于原厂。

safe 的 SHA256SUMS 覆盖 91 文件，deep 覆盖 92 文件。独立 Python 读回核验和系统 `shasum -a 256 -c SHA256SUMS` 全部通过。清单包含根 manifest，不包含清单自身。

## UI 修复与 16 槽

两份最终镜像均保留原厂 `0x202BA6FC` 分派器和 `0x20377434` 跳表，只有八处已核对 hook。没有 `force_adj_image` hook 或 `recipe_force_dispatch` 函数。`rfw_ui_active()` 要求 `*0x205D9BF8 == 8`，并继续检查 layer、type、tag 和 state，旧 overlay 不能在切换功能后继续接管 ISO。

内置初始表及活动 DAT 的 16 槽依次为：

```text
01 GR Positive Film       09 GR Cross Process
02 GR Negative Film       10 GR Vivid
03 GR Hi-Contrast B&W     11 GR Natural
04 GR Standard            12 GR B&W
05 GR Bleach Bypass       13 GR Cross Magenta
06 GR Soft B&W            14 GR Cross Yellow
07 GR Warm Sepia TE       15 GR Red TE
08 GR Cool B&W TE         16 GR Green TE
```

两份 ELF 的内置 16 条完整 recipe 和初始名称指针已直接解码，与对应活动 DAT 逐字节核对。没有可读卡文件时使用内置表；已识别的损坏、未来版本及冲突库不能应用。普通灰度槽 03/06/12 使用真实 `0x03`，TE 槽 07/08/15/16 使用真实 `0x06`。

safe 的两份 v2 DAT 与 `research/canonical_gr_pack/RECIPE20.DAT`、`RECIPE21.DAT` 完全相同，SHA-256 均为 `56a93fcddfba99ca2819f085d1fd00f2d645de83921806aca34de0e05f8a3fa9`。屏摄拟合仍标记 `DIAGNOSTIC_FIT_WITH_WB_DRIFT`，run 为 `7d011fca1daed9f674b9`。前置 JSON 没有已识别的 WB 或各控件修正，故保留 WB 两轴 0 和现有 fallback，未把输出域诊断拟合塞入原生表。

v1 文件无法表达 `03` 或 `06`。`RECIPES0.DAT` 保留 16 名称和 C/S，灰度及 TE 槽降为彩色模式的 vividness 显示 1。它不是真黑白或 TE；本次 safe 固件读取 v2 `RECIPE20/21`，真正的 `03/06` 行为由 v2 提供。C importer 已读取该 v1 文件并核对全部 16 条。

## 深表配置及准入

safe 最终 ELF 中 `rfw_deep_ownership()`、`rfw_deep_id()` 和 `rfw_deep_transition()` 均为 `60001fce`，即返回零。所有 16 个表层槽可应用且不发深表 RPC。

deep 的 `rfw_deep_ownership()` 在最终 ELF 中跳到 `rfw_rpc8_preflight()`。准入要求 context=0、connection 非零、limit>8、unit-info 指针 `0x2040F818`、名称 `jlaunch\0`、MAIN `0151/0000`。每次 RPC 再查这些条件。

- 槽 01 使用 Canonical 默认 1B，即 GRD IV native row28 的 A/B 和 color row10。没有叠加 GR III 1A 或屏摄输出修正。
- 槽 02 使用 GR III/IV Negative Film GammaTuning 的 A31/B33 投影及 `chroma_only` 的 24 个色度项。全矩阵选项没有叠加，现代投影不声称等于完整原机管线。
- 槽 03 使用 GRD IV native HC row11 的 A/B，保留 stock color row1，并发布真实 `0x03` 灰度模式。
- 槽 05 使用 GRD IV native Bleach row19 的 A/B 和 color row6。

绑定比较完整名称、模式、全部 raw 和 WB 字节，不仅比较槽号。切到其他 12 槽时，先恢复 stock A5/B5/C5D4 row1，再发布 S 字段及请求 preview。四个深槽的对比度单独设为显示 5、raw3，才能在 Gate 2 已证明的默认普通 still 路径中选中 A5/B5；safe 的 fallback C3/C3/C9/C8 保持原样。deep 包内的 `RECIPE20/21` 是表层伴随库，活动库是 `DEEPISP0/1`。

## RPC 8 连续写入

`X + V` 定位和检查每行首半字，之后连续 W。W 的每个返回值必须等于写入半字，失败即停。B5 跨 `0x2012FFFE → 0x20130000` 时不重设页。

官方 `jlaunch3` 的六处指令窗口已重新核对。`0x20242D94` 只负责 `sth`；W 分支随后调用 `0x20242980` 的 `lduh`，保留该读回值、调用 `0x20242B18` 将 `0x20246158` 加 2，再格式化读回值。另有 30 个受限 leaf 模型样例，均与原始指令字节绑定，未执行真实 RPC scheduler。

每次实际换表为 A5 33 次、B5 19 次、color row1 50 次，共 102 次 RPC，含 3 次 V 和 96 次 W。首次事务另需 `X(2013) + V(001C)` 保存 B6 邻字节，因此为 104 次、4 次 V。同一深配置重复选择不发 RPC。

`0x2013001C` 是 B5 最后一个字节所在半字，低字节 `0x2013001D` 才是 B6[0]。主机用非原厂值 `0x5C` 验证读取和保留，没有把邻字节硬编码为零。邻字节只在 resident session 首次保存，后续假定没有其他 writer 改动它。

486 降至 104/102 是 RPC 包数变化，没有测量相机延迟。优化只预检每行首半字，不再宣称整行预读或整行终读。每个 W 检查即时读回；一旦可能已写入而应答失败，uncertainty 跨 ADJ 关闭/重开保留，阻止后续 S 发布和 preview，不自动重试或盲恢复。

## 本轮检查

- safe 的 host 与 ASan/UBSan 各 61 组，deep 各 69 组，通过全部 16 槽实际 ADJ/apply 路径、原生 BW/TE、内置库和 v1 companion。
- 每份最终 M32R ELF 各 36 组 ABI 模型、17 组工具测试、7 组镜像正反例及 5 项链接/布局拒绝检查通过。ABI 模型检查参数、返回值、栈和被调用者保存寄存器；inline hook 另检查 PSW。
- recipe_core 的 host 和 sanitizer 各 249 项断言，另有 18 项独立检查。v2 codec/store/apply 的 host 和 sanitizer 各 31 组通过。
- deep 覆盖全部 104 个首次事务位置的应答丢失、执行前失败及链路丢失，全部 102 个恢复应答丢失位置、全部 96 个 W 错误读回、stock 加四配置的 25 对切换。失败不发布 S 或 preview，uncertainty 不被重开清除。
- 两份最终 `ilaunch3` 的 dispatcher 模型各 25/25 通过，30 个 boot/update/OSD 窗口逐字节等于原厂。整镜像差异限于八个 hook、payload 及容器 checksum。
- 357 个本项目原厂及已有 Stage 1 包文件、44 个原 Stage 1c 源文件、3 个固定 Stage 1c 审阅产物的哈希均未变。

safe payload 为 6644 B，尾部探针前剩余 1440 B。deep payload 为 8076 B，尾部探针前剩余 8 B。两者均位于原驻留区、无可写全局/残留 relocation/undefined symbol，256 B 探针尾区保持 FF。为装入四套表，目标只读构建去掉未调用的 encoder/importer 和未调用的绘制包装，并共享经 ABI 验证的 native bridge，没有扩张写入区。

## 镜像身份

safe `ilaunch3`：

```text
9cd6a7614bb27e9a7d1db67dd5fd0e04aecae7b8a33408586f6b3e5c057cefcb
checksum 0x6a85100b
```

deep `ilaunch3`：

```text
c5f2f836a2e12c6602f9efc13c5d689844842133d455f6dec322761b1d058150
checksum 0x6a74c9f6
```

完整文件哈希见各包清单。最终状态及 ELF、镜像和测试细节见 [package_verification.json](package_verification.json)，表来源和 C5 覆盖见 [package_tables.json](package_tables.json)，原始 W 依据见 [native_rpc_contract.json](native_rpc_contract.json)。

## 设备验证边界

preflight 只证明上下文、连接及固件元数据，不证明 RPC 游标独占或 ISP 互斥。计数器在首个 V 前的状态、其他 sender、实际运行 T 选行、ISP reader、任务栈余量及同步延迟仍未闭合。deep 候选按本次要求启用，但这些风险没有被改写成通过。

还需在目标机检验 ISO、ADJ 左右、Fn、普通拍摄模式，deep 写入/切换/恢复、冷启动、Live View、JPEG 和保留 DNG。表已嵌入、主机恢复通过及原厂恢复目录完整，都不能代替这些设备检查。没有宣称完整 GR 管线或品牌外观等效。

## 复跑入口

从项目根构建并验证两包：

```sh
python3 -I -B research/stage2a_deep_isp/build_packages.py
```

仅读回现有交付：

```sh
python3 -I -B research/stage2a_deep_isp/verify_packages.py
```

构建入口还读取现有 `/private/tmp/gxr_gr_firmware/unpacked/grd4-2.30/g04firm3.bin`，逐字节核对原生 GRD IV 表；该原件缺失或哈希不符时停止，不自动下载。两个入口写入本任务目录，不访问挂载卷。命令日志在 `package_logs/`，每份包也保留 payload、ELF、map、反汇编、host/sanitizer/ABI 结果、表来源和复核 manifest。
