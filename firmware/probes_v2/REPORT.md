# probes-v2 实现报告

三个只读探针离线引擎已实现；新增主堆容量探针并入 LIFE，不增加一种引擎。源码、M32R 代码段、模拟测试、行名解码器和中文操作说明已经交付。尚未接入最终 resident/data v2，不能把代码段直接放卡。本轮没有相机结果，不能据此批准“48 KiB 文件加 BSS”。

工作目录为 `/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/firmware/probes_v2/`。全部写入限于该目录；未操作相机、存储卡、刷机、commit 或 push，未生成卡文件。官方固件目录只读。研究目录和并行 worker 的文件没有改写。

## 已核实

### 三个引擎与八项观察

| 引擎 | 探针 | 实现的观察 | 保留的边界 |
|---|---|---|---|
| LIFE | P1 | 固定 IROM A/B 只读；512 B 串流、短读、精确参考长度、额外 1 B EOF、完整 CRC32、关闭结果、存储与 SD 代次。 | 无可信参考只报完整读到 EOF，不报校验通过。缺文件不创建，不切记录媒体。 |
| LIFE | P2 | 只申请一次独立 256 B 或 32 KiB 见证；全块 pattern/CRC，首中尾各 4 B canary；代码段 CRC；每次重开查 coherent epochs 和 lease。 | 旧 heap/root 或 lease 失配时不读、不执行、不 free、不重分配冒充保持。未新增运行堆返回桩的 A/B 取指实验。 |
| LIFE | P3 | H15/H16/H17/H18 自然事件、pre/post 计数、原始 a/b、session、序号缺口。 | loader 栈见证重新发布没有冻结服务，固定保留 UNKNOWN。不能凭 root 计数自证没有重载。 |
| NOTICE | P4 | 全部 16 B SD ID 比较；区分 ID 改变与同 ID 新 epoch；保存 H22 pre/post 和原返回。 | 缓存失败/全零/采样期间换代撤有效位；环覆盖不解释成没有通知。 |
| NOTICE | P5 | 完整 name8、MAIN/Cmp、unit/link/rx_sequence；同名重连计数；H19/H20/H21 事件。 | 不 RPC、不主动上电、不写新单元；原生失败不继承有效身份。 |
| NOTICE | P6 | 逻辑事件和复制后的 source/edge/activity/state/part/tag/top/count/view epoch；原始 H06/H10/H11..14 轨迹。 | 不预命名 0x25/0x22，不保存消息指针。只有 RAM 草稿，原生九行空面板仍未验。 |
| VIEW | P7 | 被动 H37 pre/post、关联序号和可选的已复制 apply 阶段记录。 | 没有写入驱动，不发 RPC，不主动请求 preview；行验证、发布和真正下一帧不得混为同一成功。 |
| VIEW | P8 | 每次重新取 S snapshot，只读 0x6DD/0x6DE，检查长度/代次/raw 1..17；输出 raw 和 raw-9，释放短期快照。 | AB/GM 次序、正方向、WB 使能保持 UNKNOWN；默认不改原厂设置。 |

P7/P8 的写入部分只在操作说明中单独列为另行批准阶段，没有可打开写服务的编译开关。用户提供的 GXR/三单元官方 1.51 与 2k-p0 实机结果作为前提沿用，不是本轮复测结果。

### 补充的主堆容量探针

LIFE 在首次菜单自动测一次；回放之后、真正睡眠唤醒之后各由明确的人工选择测一次。后两次不从未知 power/mode 参数推断，也不在后台等待。每阶段每 session 只执行一次，结果分开保留。

每阶段严格按 64、48、40、32、16 KiB 各申请一次，普通申请失败后尝试下一档。每次成功后，下一次服务调用立即 free 新取得的 token。容量块不映射、不读、不写、不填 canary、不算 CRC、不执行代码；只在原有自有上下文记录结果和菜单字形。P2 的见证块始终是另一项已有探针，不被容量探针释放。

成功回复必须完整并属于本次 boot/heap，且 token 不得为上下文、代码或 P2 见证。释放失败、不完整回复、旧代次均使测试进入 FAULT，并停止后续阶段；不重试未知 free。报告的最大档位只计成功申请且成功释放的块。

三次均记录 session、sample、boot、heap、P2 见证大小、五档分配/释放结果与原生返回。容量页为 LIFE 5/6/7，原始错误页为 14/15/16，额外页用 Fn2 翻到。解码器只合并同 session、同 boot/heap、相同见证大小且三阶段都完整的数据，给出三次最大成功档位的最小值。它始终保留 `file_plus_bss_accepted=false`。

模拟夹具中的 48/40/32 KiB 是人为设定的三阶段结果，用于验证解码与取最小值，不是这台相机的测量值。64 KiB 成功也只证明至少该档能分配，不能称为精确最大空闲块。

### 编译与实测体积

| 产物 | M32R 代码段 | 私有上下文 | 单函数最大静态栈帧 | 运行时重定位 |
|---|---:|---:|---:|---:|
| LIFE | 9544 B | 4984 B | 104 B | 0 |
| NOTICE | 6740 B | 4984 B | 104 B | 0 |
| VIEW | 6364 B | 4984 B | 104 B | 0 |

上下文之外还要有已审完整 native UI state。LIFE 的 P2 见证为 256 或 32768 B；容量测试最多同时持有一个新的 65536 B 临时块，不把五档一起持有。上表不是最终容器或总 RAM 占用。

目标 M32R 实测 `PvInvocation=180 B`、`RvApi=160 B`；具体偏移见 `local/build/target-layout.json`。ELF 自身无 `.bss/.data/.rodata/GOT/PLT`，上下文由 adapter 提供，最终容器 BSS 预算尚未定。104 B 是单函数帧，不包含调用链或 resident/native 栈。

沿用 `resident_v2/build.py` 的工具链和 FLAGS，C model 同其实际构建覆盖为 medium。另加 `-fno-jump-tables` 与 `-fno-tree-switch-conversion`，禁止编译器产生依赖绝对地址的隐式表。所有链接期重定位只允许内部 PC-relative；未定义符号、剩余运行时重定位和禁止 section 会失败。三个引擎分别在 0 和 0x21000000 重链接，代码段字节完全相同。

新增容量档位后，第一次目标审计确实捕获 `R_M32R_HI16_SLO_RELA .rodata`、`R_M32R_LO16_RELA .rodata`。禁用整数查表转换后通过；失败对象、原源码、重定位与反汇编保存在 `local/failures/capacity-table-*`，没有放宽重定位 gate。

冻结 `resident_v2/abi.h` 的 SHA256 为 `78b8cd23a6411337980dbd8a041256a7f3d6ffd98b8d42b3f02d9fe47594fb7d`。编译器、链接器、指定 objdump 的完整 SHA 和命令见 `local/build/summary.json`、`commands.json`。

### 模拟服务与编解码测试

系统编译器编译同一份 `engine.c`，通过 32 位 wire 地址映射调用实际入口。模拟服务独立拒绝写服务和全部 RPC，用 AddressSanitizer、UndefinedBehaviorSanitizer 验证。

最终通过 32045 个 C 断言、58 个 Python 检查，44 个真实 C 编码页面/向量，禁止调用计数为零。断言数包含每次服务边界检查，不等于这么多个独立场景。

验证覆盖如下。

- CRC32 标准向量、合法零 CRC、12 字符行、16 行整页大端 CRC、多个引擎/页面、缺行、错字、混引擎、重复行、显式 OCR 纠错和部分抄录不报 verified。
- IROM 短读、额外尾字节、短文件、错 CRC、无参考、缺源、越界实际读长、READ 负值、96 次预算、32 KiB 边界及关闭只调用一次。
- 同一见证不重新申请，32 KiB canary/CRC 损坏、旧 lease 不解引用、root/heap 换代、代码损坏、环缺口与不重复消费、错误 reply header。
- 全 16 B 卡 ID 的末字节变化、同 ID 新代次、同名单元重连、失败快照撤有效位、读取过程中 SD/unit/S 换代、复制输入值和 WB 新快照。
- 容量五档顺序、成功后 alloc/free 服务相邻、三阶段只测一次、全失败、非连续档位失败、最大成功档位、释放失败后不再分配。容量地址在主机夹具里根本没有映射，任何读写都会失败。
- 所有列表选择和未知 probe 命令都不会 PASS 到普通配方应用；物理 event 保持 PASS。稳定两层标签、glyph 描述符和显式 redraw 经过模拟服务检查。

主机 glyph 是夹具编码，没有验证原生字体、实际菜单或相机显示。模拟服务支持安全的跨 lease inspect 输出和准确 `actual`；不表示并行常驻实现已经支持它们。

## 推断

17 页 LIFE 与 12 页 NOTICE/VIEW 都复用同一组 16 行，三种引擎足以覆盖八项问题与容量测量，预计只需两次换引擎文件。这个操作次数依赖最终容器选择/加载 adapter；本轮没有实际换卡文件。

若三时机在同一会话都成功到某档，且原生 free 返回真实可靠，可把三者最小成功档位作为当时条件下的保守分配候选。最终完整分配仍必须满足“文件实际长度 + 实际 BSS + loader 同块开销 + 对齐”。探针运行时自身已有代码、上下文和 P2 见证，不能不加说明地把其结果当成替换后容器的净预算。

## 未知与交给协调者的接线项

精确源 hash 和 13 个只读窗口保存在 `local/integration/snapshot.json`，时间为 2026-10-23T17:09:15.644989+00:00。这是并行工作中源码的静态快照，后续源改动需重审；不是 resident 的运行测试。

1. loader 尚未向探针提供 180 B `PvInvocation`、私有 state 和完整 UI state。probe payload、UI capability bit17 与用途值 2 是接线约定，未改冻结 `abi.h`。纯 bank/data v2 校验的归属也必须接上，不能把只读当成省略容器受理的理由。
2. LEASE inspect 用 `args[1]` 同时选目标 lease 和验证输出缓冲，独立见证与 state 不是同一 token 时会拒绝。先向旧块写描述符再 inspect 不安全，本实现未绕过。
3. 快照成功分支的 `reply.actual` 必须准确填写；探针不会把 OK 自动当成完整缓冲。快照时旧 unit/link/view/S 请求怎样取得新 epochs，也须统一。
4. STORAGE 在对象上限之后仍要允许有界的额外 EOF 检查。旧 `card_container/gxrce.h` 目前写的是文件 32768、BSS 4096；最终 data v2 的 48 KiB 计划、READ 上限和 loader 实际分配式须一起更新/校验，容量成功不会自动解除格式上限。
5. 快照中的 LEASE free 忽略 `rv_native_free` 原返回后直接报 OK。容量结论依赖真实释放成功，必须由协调者核实 native free 合同并传播失败，不能把模拟的释放失败测试当成此分支已修好。
6. loader 独立栈见证、完整按键复制合同、原生九行面板、P7 被动阶段来源和 frame-completion 都未闭合。启动盲区、执行中 heap/段覆盖、真正睡眠和取景变化仍无本轮实机证据。

没有真实三时机容量、没有 final resident/data v2 运行结果、没有卡包、没有相机 acceptance。P7/P8 的写入及原生 WB 方向必须另行批准并采证。

## 产出与复核

| 文件 | 用途 |
|---|---|
| `engine.c`、`probes.h`、`entry.S`、`runtime.c`、`engine.ld` | 三引擎共用实现、私有 wire payload、固定入口跳板与零基址链接。 |
| `build.py`、`support.py` | 外置盘预检、M32R 编译、大小、重定位、双基址与 target layout 审计。 |
| `host_checks.c`、`verify.py` | 严格服务表、只读/容量行为与编解码测试。 |
| `decode.py` | 从手抄或已有 OCR 文字还原字段、整页 CRC 与三时机容量档位。 |
| `USER_GUIDE.md`、`INTEGRATION.md` | 中文最短操作顺序、需要协调者接入的具体合同与缺口。 |
| `audit_resident.py`、`checksums.py` | 只读接线窗口快照和两份 SHA256 manifest 的生成/复核。 |
| `local/build/{life,notice,view}/` | `engine.bin`、空 `relocations.bin`、`metadata.json`、ELF/map、栈用量和原始日志。仅离线段。 |
| `local/tests/`、`local/integration/`、`local/failures/` | 主机程序、44 个编码输出及解码、验证摘要、共享源码快照和保留的失败证据。 |
| `.gitignore`、`SHA256SUMS`、`local/SHA256SUMS` | 忽略全部 local；分别校验可审源码/说明与私有二进制/日志。 |

原始字节、二进制段、打包元数据和反汇编都在 `local/`。`git check-ignore -v` 已确认为本目录 `.gitignore:1:/local/`。写入前以及脚本运行前均验证外置盘 APFS、可写、UUID `14BE04EB-AF49-497E-B36A-B078B2F7C5E8`。

复核命令如下，均不会打包、访问卡或部署。

```sh
cd /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh
python3 -I -B firmware/probes_v2/build.py
python3 -I -B firmware/probes_v2/verify.py
python3 -I -B firmware/probes_v2/audit_resident.py
python3 -I -B firmware/probes_v2/decode.py firmware/probes_v2/local/tests/life-rows.txt
git check-ignore -v firmware/probes_v2/local/build/life/engine.bin
python3 -I -B firmware/probes_v2/checksums.py --check
```

重建或更新快照后，私有日志/编译物 hash 可能变化；重新生成 manifest 使用 `python3 -I -B firmware/probes_v2/checksums.py`。当前源码与产物的最终 SHA 以两份 manifest 为准。
