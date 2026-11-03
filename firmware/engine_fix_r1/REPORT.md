# 引擎修复与 full-r2 交付报告

首要接口缺陷已修复，full-r2 已生成。文件为 59,328 B，主块申请量由 89,240 B 降至 78,224 B，减少 11,016 B。最终 189 项主机检查通过，冻结的 v3.2 完整 C 校验器接受三单元数据。机身映像与常驻身份保持原值；相机上是否加载成功仍未知。

日期：2026-10-24。对象为 GXR 机身 1.51、GR LENS A12 50mm、A12 28mm、MOUNT A12 官方 1.51。所有结果均为本机离线证据。

## 1. 交付物与结论边界

- 容器：[full-r2/GXRCE.DAT](local/product/candidates/full-r2/GXRCE.DAT)，generation=104。
- SHA-256：`6ba63d294e86a591e5752d7c237cf7b88aeda1f3b0b51064439709b5feed9cc0`。
- 大小：59,328 B。引擎代码 49,900 B，BSS 11,392 B。
- 主块 request：78,224 B，即 76.390625 KiB。原生分配头另加 12 B。
- 全部文件校验清单：[SHA256SUMS](SHA256SUMS)。产品目录也有独立清单。

已核实：只向 `firmware/engine_fix_r1/` 写入；容器、二进制、生成头文件、信任字节、展开条目、对象文件、差异和日志均在忽略的 `local/`。`git check-ignore -v` 命中 `firmware/engine_fix_r1/.gitignore:1:/local/`。卷为可写 APFS，UUID 为 `14BE04EB-AF49-497E-B36A-B078B2F7C5E8`。记录的 3,102 个输入中，3,101 个全文件哈希未变，原有 tracked Git 状态未变。共享 `decisions.tsv` 在任务期间被追加了 1 行，其旧前缀 SHA 与基线一致；追加内容保留在 [observed-shared-decisions-append.tsv](local/observed-shared-decisions-append.tsv)。本任务未写入或回退共享日志。

已核实：未连接相机、访问 `/Volumes` 下的存储卡、刷机、重链接常驻 ELF 或生成机身映像。未安装包、启动子代理、commit 或 push。所有 Python 命令使用系统 `/usr/bin/python3 -I -B`。

推断：修复直接覆盖诊断报告 §2.1 的首要故障链，并降低第二嫌疑涉及的连续块门槛。它应能消除该特定缺文件兼容问题；这不是对相机那次失败现场的确认。

未知：M32R 指令在相机上的执行、实际堆碎片、原生文件系统、UI 时序、RPC 与掉电持久性。本次的文件、分配器、RPC、glyph 和 UI 为 host doubles；主机调度经过验证的入口 offset 到真实 C 函数，没有执行 M32R 机器码。

## 2. 只读 open 的语义与安全性

修复在容器携带的 [engine_services/services.c](engine_services/services.c) 内。固定路径和对象参数验证通过后，仅 `op==2 && n==-1` 返回 `RV_UNAVAILABLE`。其它负值返回 `RV_IO`。`op==3` 的 create 即使返回 -1，也不会进入缺失分支。

| 调用位置 | -1 的处理 | 核对结果 |
| --- | --- | --- |
| IROM 引擎 A/B、GXTS A/B 的只读 open | 不可用或不存在 | 安装扫描或默认微调可继续。 |
| TMP 存在性检查、卡 DAT/OK 的固定对象只读 open | 不可用或不存在 | 不会把后续 read 失败当成缺失。 |
| create、read、write、close | I/O 故障 | create/read/write/close 的服务返回 `RV_IO`；write 会置不确定标记，close 的上层仍可进一步 fence。 |
| rename、delete | 破坏性 I/O 故障 | 保留 `RF_UNCERTAIN` 与 `RV_UNCERTAIN`，没有缺失特例。 |
| `es_storage_mark` 中 DAT 与已安装副本的直接 open/read/EOF/close | 验证或 I/O 失败 | 这是安装确认的必需见证，不放宽成默认或成功；失败不执行 DAT→OK。 |
| 只读 `resident_v32/resident/loader.c` | 原逻辑 | loader 的 probe、全文读取和选择回退均未改。 |

[panel_store.c](containers/product/src/firmware/engine/panel/panel_store.c) 在删除受限对象前先做只读存在性检查并成功 close。只有 probe 的 `RV_UNAVAILABLE` 可以跳过删除；实际 delete 的 -1/-2 不再被翻译为缺失。原来针对 delete(-2) 的特例已移除。任意路径、owner、epoch、SD ID、capability 与 lease 的校验继续先于原生操作。

官方包装器不能区分 ENOENT 与其它 open 故障，因此这里没有声称 -1 证明文件不存在。安全依据在后续提交协议：引擎来源先做完整格式、身份、CRC 和语义校验；TMP 写完后必须完整读回、逐字节比较并验证；改名后还要读取正式副本。GXTS 同样核对 240 B 全记录、绑定、generation 和参数范围。DAT→OK 前再比较来源与正式副本，并检查 EOF、close、CRC 和 SD ID。

所以，把真正的只读 open I/O 故障判作不可用，最坏会重新安装、使用默认微调，或让这次安装/保存失败。它不会跳过完整读回，也不会把未验证数据报告为安装或保存成功。`install-readback-open` 和 `gxts-readback-open` 专门在写后回读时注入 -1，确认没有发布新正式副本；前者保留 DAT，后者按不确定状态退出。实际磁盘的掉电原子性不在主机证据内。

## 3. 引擎内存与文件差异

| 项目 | resident_v32 原 full | full-r2 | 差值 |
| --- | ---: | ---: | ---: |
| 引擎代码 | 50,044 | 49,900 | -144 |
| BSS | 23,576 | 11,392 | -12,184 |
| 数据段合计 | 7,852 | 9,164 | +1,312 |
| 容器文件 | 58,160 | 59,328 | +1,168 |
| 主块 request | 89,240 | 78,224 | -11,016 |

1. 去掉 16 份常驻 `PnGxts` 事务对象。16 行只缓存微调值与各行 `io_error_mask`；参数索引共享。预加载和保存时申请一份 652 B 临时 lease，预加载循环复用它，结束后释放。失败路径也释放已申请对象。A4 的移动不打开文件；保存前重建绑定，并恢复缓存的读错误标志，防止用健康副本掩盖另一副本的 I/O 故障。
2. 去掉 adapter 的重复完整语义验证和 view 副本，复用 core 已验证的 view。完整语义、stock entry CRC 与三个模块的 pin 校验仍在 core READY gate 内执行。
3. 把 stock pin、GXTS 内容与 metadata 的 CRC 改成逐段累加，删除 538 B、411 B 与 256 B 拼接缓冲。GXTS encode 在参数检查后直接写调用方输出，删除 240 B 中转缓冲。删除两份重复 `EngData` 中转对象。48 槽的新旧绑定与 GXTS 编码逐字节一致。
4. 继续使用原 `--gc-sections` 与 LTO/PIC 选项删除未引用代码；没有调整编译优化等级或用新工具链换取大小。最终引擎小 144 B。Mount 校准池增加 1,312 B，因此容器整体仍增加 1,168 B。

安装用的两块 64 KiB 仍是用完释放的 lease。它们需要容纳未重定位来源和最大合法旧副本的完整比较，未为缩小峰值放宽提交协议。UI 列表数据仍留在主块：当前 ABI 要求 UI state、table 与 details 同属一个 lease，且 native view 持有该 lease；不能直接把它们改成调用结束即释放的临时内存。固定 6,144 B resident state 也未改。

### 3.1 从已批准 ELF 计算实际主块

[inspect_artifacts.py](inspect_artifacts.py) 用原工具链交叉编译只读 loader 的 layout 常量对象，得到 session=1104、state=6144、UI capacity=256，合计 overhead=7504。再读取已批准 ELF，核对 `0x20053764` 的 `84 a4 1d 50 / add3 r4,r4,#7504` 与 `0x200537BC` 的 session 立即数，且整个常驻 payload 与批准映像逐字节一致。这里没有沿用 6,916 旧常数。

```text
request = overhead + align4(file + BSS)
        = 7,504 + align4(59,328 + 11,392)
        = 78,224 B
含原生 12 B 分配头 = 78,236 B
另计 loader 工作区 608+12 B、首次列表快照 1,968+12 B
三块含头合计 = 80,836 B
```

三单元 `firstboot-empty` 用真实 resident C 观察到的 `root.block_bytes` 均为 78,224，并确认正常预加载、保存后没有遗留临时 lease。这些大小不代表现场一定有足够连续空闲块。详细数据见 [artifact-inspection.json](local/artifact-inspection.json)、[bss-symbols.json](local/bss-symbols.json)。

## 4. full-r2 数据与身份

只列引擎与数据变化。常驻机身部分、其 build/ABI 和三个 pin 均不变。

| 单元与槽 | full-r2 来源 | 与旧 full 的关系 |
| --- | --- | --- |
| 50mm 01/02、03/04 | 原版 | 保持原 full 条目。 |
| 50mm 05/06 | v6 的 05/06 | 保持原 full 条目。 |
| 50mm 07/08 | Leica Chrome / Leica VIVID | 保持原 full 条目。 |
| 50mm 09/10 | v6 的 01/02，重绑为 Posi6 / Nega6 | 保持原 full 条目。 |
| 50mm 11–16 | 50mm 原厂别名 | 保持原 full 条目。 |
| Mount 01–08 | `research/mount_calib_r1/local/entries/pack_model_input.json` 的八条校准输入 | 01–06 含无 T1 的 06，07 为 Chrome、08 为 Vivid；源标签 `07 LChr` / `08 LViv` 保留。 |
| Mount 09–16 | Mount 原厂别名 | 保持原 full 条目。 |
| 28mm 01–16 | 28mm 原厂别名 | 保持原 full 条目。 |

Mount map128、stock410、stock entry 与 l08firm 原厂 pin 分别核对；从源 record 建立 49 B 身份，重算 record CRC 与 entry 身份 CRC。源中旧 SHA-shaped pin 不能直接当本产品 CRC profile 的 pin，打包时使用冻结 l08firm 的 CRC32+零填充编码。三单元 pin 为 `DF2BCAF5 / 6700E6FF / 1B3C7000`。全部八个 Mount 条目均无 aux/T1 位，控制半字为 2。容器的全局 row pool 继续去重。

冻结 v3.2 完整 C 校验器与新 C 校验器均验证 final DAT，独立 C 展开 48 槽。50mm 的全部 16 槽、28mm 的全部 16 槽和 Mount 09–16 与冻结旧 full 逐字节一致；Mount 01–08 与校准源按最终身份重绑后逐字节一致。证据见 [data-and-gxts-compatibility.json](local/data-and-gxts-compatibility.json)、[manifest.json](local/product/candidates/full-r2/manifest.json)。generation 从 103 升到 104，文件长度、BSS、重定位、header/payload CRC 随内容重算。

冻结身份如下，final DAT 的 80 B 身份与 resident ELF 完全相同：

```text
approved image SHA256 = 05b46ee65f4861f2e09e9b7c519cbcc2dffb195158a40c3bb033540b36a98d8c
resident ELF SHA256   = f25899258471d0652a8fef8980b9f0a83a0ca7cd4ddc6bbe8fcc337467362b58
body SHA256           = da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7
resident build        = 2eea6eb324790b035d37d33395d60880a1909b4e693414a939dee45f96bfbae7
resident ABI          = 9583fdd751bebc36f3af305595559643
```

常驻 `.payload` 为 7,772 B，与批准映像中同 VA 字节全等；root pins 也全等。本任务没有重新发放 resident 身份。

## 5. 全部测试结果

| 检查组 | 数量 | 结果与证据 |
| --- | ---: | --- |
| 修复前真实 C + 原 full，缺文件原始码仅改为 -1 | 3 | 三单元均出现预期失败 `state=6 fault=-5`。见 [baseline-native-minus1.json](local/baseline-native-minus1.json)。 |
| 完整 C 校验，base / huzi / full-r2 × 三单元 | 9 | 全通过。 |
| 原 18 类端到端场景 × 三单元 × 两组容器 | 108 | 全通过，包含首次安装、IROM 重启、格式化回退、S 迁移与全部原失败注入。 |
| 原生边界 7 操作 × -1/-2 × 三单元 | 42 | open 仅 -1 可为缺失；其它操作不把失败当缺失。 |
| 新增 10 个端到端场景 × 三单元 | 30 | 全通过。 |
| 冻结 v3.2 完整 C 校验器对 final DAT | 3 单元 | 全通过，独立于改写后的校验源。 |
| C 展开、源条目与 GXTS wire 对照 | 48 槽 | 全等。 |
| M32R PIC、重定位与服务归档 | 每次构建 | 零未解析符号、无运行时 SHA、容器重定位 1 项，归一化平移至 `0x21004000` 后其它机器字节相同。 |

最终产品与负例合计 **189 项通过**，均启用 ASan/UBSan，未出现 sanitizer 故障。原 18 场景为 `flow, s-entry, badcrc, bad-layout, bad-tweak, image-limit, truncated, readfail, rename-install, rename-mark, alloc-main, alloc-work, heap-load, sd-write, unit-rpc, unit-entry, a4-save-open, a4-save-rename`。

新增十场景为 `firstboot-empty, gxts-read-failure, gxts-partial-io, install-readback-failure, install-readback-mismatch, install-readback-open, gxts-readback-open, gxts-readback-mismatch, lease-preload, lease-save`。其中 `firstboot-empty` 从空 IROM/GXTS 打开，显示 16 项，完成 IROM 安装与 DAT→OK，应用全部 16 项后重启，再从 generation=104 的 IROM 加载成功。`gxts-partial-io` 验证健康副本可读时仍保留另一副本的读错误，并阻止保存覆盖。

为让所有写入失败点真实执行，full-r2 故障组使用同数据的 generation=103 测试输入，再升级到实际 generation=104。该输入明确标记 `production_container=false`，不把等代相同文件跳过提交的结果计作 rename 故障覆盖。此前发现的该夹具失败和开发阶段编译失败均保留在 `local/failures/`。

原始逐例输出见 [product/acceptance.json](local/product/acceptance.json)、[extra-acceptance.json](local/extra-acceptance.json) 和 `local/logs/`；汇总见 [test-summary.json](local/test-summary.json)。所有成功结论限于上述主机与静态机器码证据。

## 6. 重跑与审阅

从仓库根目录运行，不安装依赖：

```sh
/usr/bin/python3 -I -B firmware/engine_fix_r1/reproduce_before.py
/usr/bin/python3 -I -B firmware/engine_fix_r1/build.py
/usr/bin/python3 -I -B firmware/engine_fix_r1/verify.py
/usr/bin/python3 -I -B firmware/engine_fix_r1/inspect_artifacts.py
/usr/bin/python3 -I -B firmware/engine_fix_r1/finalize.py
```

工具链沿用 resident_v32 的 `research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc`、`tooling_m32r_asm/prefix/bin/m32r-elf-ld`、`tooling_m32r/prefix/bin/m32r-elf-objdump`。产品保持原 `-Os -flto -fpic -m32r -mmodel=medium -msdata=none -G0` 与原链接审计；服务归档沿用批准 service FLAGS 及原 medium 覆盖。未重建 resident。

源代码变动见 [source-diff.patch](local/source-diff.patch) 与 [source-changes.json](local/source-changes.json)。执行参数和返回码在 [commands.jsonl](local/commands.jsonl)，只读边界结果在 [scope.json](local/scope.json)。`finalize.py` 生成清单后逐项重新计算 SHA-256。
