# resident-impl 实现与验收报告

本次未达到“完整实现并严格装进 8340 B”的交付目标。补充决定已经纳入，主机故障注入通过；全 hook 配置仍超出 7624 B，删除全部三级 hook 后仍超出 7288 B。没有可安装的 resident ELF，也没有生成机身映像、更新包或供存储卡使用的文件。

## 已核实：补充决定后的实测体积

| 配置 | 代码与常量 | root | 合计 | 窗口 | 剩余空间 | 严格链接 |
|---|---:|---:|---:|---:|---:|---|
| 全部 H01–H37 | 15452 B | 512 B | 15964 B | 8340 B | -7624 B | 失败 |
| 删除全部三级 hook | 15116 B | 512 B | 15628 B | 8340 B | -7288 B | 失败 |

严格链接保留代码上限 `0x20054600`、root `[0x20054600,0x20054800)`，未扩大正式窗口。原始错误见 [constrained-link.log](local/constrained-link.log)：

```text
resident code exceeds 7828B before 512B root
section .root ... overlaps section .payload ...
```

为了计数，另外生成 `OVERSIZE-NOT-A-CANDIDATE.elf`，仅在该诊断链接中将 root 移到 `0x20060000`。这些 ELF 不满足地址合同，补丁清单的 `installable` 均为 false。严格失败 map 与诊断 map 分别保留，不以诊断链接代替通过。

下表是 map 中保留下来的输入节贡献；字符串合并和对齐差额另列，合计与最终 `.payload` 一致。

| 部分 | 全 hook | 删除三级 hook |
|---|---:|---:|
| `hooks.o` | 1232 | 1212 |
| `linked_hooks.o` | 1140 | 824 |
| `resident.o` | 2424 | 2424 |
| `loader.o` | 2542 | 2542 |
| `services.o` | 6330 | 6330 |
| `runtime.o` | 144 | 144 |
| `validate_envelope.inc.o` | 1196 | 1196 |
| `bridges.o` | 368 | 368 |
| `trust.o` | 92 | 92 |
| 链接合并与对齐差额 | -16 | -16 |
| 最终 `.payload` | 15452 | 15116 |

## 已核实：本任务写入的实现

- 从 `resident_v2` 复制骨架，`abi.h` 与原文件逐字节相同。只写 `firmware/resident_impl/`，该目录的 `/local/` 已由任务自己的 `.gitignore` 忽略。所有固件原字节、生成信任常量、反汇编、ELF、map 和补丁字节均在 `local/`。
- gate 只处理执行外壳：头 magic/外层版本/长度/section 数、头和数据 CRC32、机身 ID、resident build/ABI ID、各 section 的范围和交叠、入口、代码区内的重定位位置以及本 image+BSS 内的目标。保留重定位数量、排序和原 patch word 一致性检查。不解析单元目录、map、GXDP/GXDT、bank、行、身份或参数元数据。内层 data_version 不再阻止文件演进。
- 文件上限为 49152 B，代码 section 上限为 24576 B，整个 image+BSS 上限为 57344 B。BSS 按 `bss <= 57344 - file_bytes` 检查。主块另含 328 B resident 会话元数据，一次申请 57672 B；分配失败回原厂。只从已审主堆分配，并检查返回范围、lease token/反码和 boot/heap 代次。
- loader 单次只持有一个 fd；支持短读，探测 EOF，拒绝截断、超长、读错误、越界返回和 close 失败。依次验证 A/B/卡，先筛有效性再比较 build_number；同代候选逐字节比较，CRC 碰撞不视为等价。选中源重新读取并复验后，重定位、清 BSS、同步 cache，再 bootstrap、校验九个入口并调用纯 init。
- bootstrap 允许 PASS 或 CONSUMED，要求回复成功且 actual=40。纯 init 使用 36 B 引擎局部输入，含 image 地址/长度，grain 地址和 WB 绑定暂为零；不是 `abi.h` 结构变更。只有 init 成功、lease/全部代次仍一致，才在 IRQ 临界区最后发布 READY。引擎请求的 UI/S/W 能力在此后才可批准。
- root 内保留 boot/heap/link/unit/SD/IROM/view/S/mode/segment/power/io 代次；溢出停止该会话，不重用旧 token。link/unit 作废时保留代码块，在安全菜单边界重复纯 init；heap 作废后不读、不执行、不 free 旧 lease。破坏性通知中发现 inflight 只记录不确定状态，尚无安全排空证明。
- `ui_abort` 不调用引擎、不解引用失效堆。它撤自有名称表，恢复原厂数量 7、合法 cursor 和仍属于自己的 part2 栈顶完整 tag 记录及原厂 state；H05 失去所有权后恢复原厂 details 路径。外部已更换的记录不被覆盖。
- H09 的颗粒函数只读 root 的已提交快照和原生 S，不调用堆代码、文件或 RPC。packet 的五个门字段、category 0/4、S 长度、selector/base_mode 和 size 集合均按 Stage2l 条件检查；只改允许的四个 packet 字节，WB 与 picture-style 的其它字节保持原值。当前还没有与真实引擎接通快照发布，产品颗粒保持关闭。
- 16 项事件环采用短 IRQ 临界区，sequence 最后提交；提供带 dropped 和可读序号范围的快照。H10 复制原入口 SP+28 起的三个消息头 word，不保留原栈指针。Fn2 消费后给原生返回 0；H10 消费后走下一事件，不把引擎的 1/2 直接交原生 shooting 分派。

resident ELF 不含 SHA-256 实现、常量表或移位运行库。服务 16 保留编号，返回 UNSUPPORTED。Python 在主机上用 SHA-256 生成 build/ABI ID 和交付哈希，不进入目标机代码。

## 已核实：pin 公开与纯 init 测试

三个常量只公开给引擎，resident 不再读取任何 stock 行。

| module_id | 单元 | CRC32(map128 + stock410) |
|---:|---|---|
| 1 | 50mm / jlaunch | `df2bcaf5` |
| 2 | 28mm / qlaunch | `6700e6ff` |
| 3 | Mount / l08firm | `1b3c7000` |

已实现最小 QUERY 扩展：service=14、operation=3，`q.args[8]` 为 module_id 1..3，其余额外参数为零；成功时 `reply.detail` 为 pin，`reply.actual=4`，token 为零。允许零 context 的只读查询，纯 init 也可使用。API 的 QUERY 操作位包含 op3，服务号、请求/回复结构和入口表都未改。

主机夹具读取 `card_container_v2/local/candidate-final` 的 GXDP/GXDT 数据，在 Python 中独立重建三份 map128+stock410，并用标准 CRC32 复核上述值。C 的模拟引擎在 init 内读取 QUERY pin，自行遍历当前单元的去重行并比较；不符就失败。该解析器只编入主机测试，不进入 resident。

## 已核实：故障注入结果

```text
PASS_HOST checks=39570 sanitizer=ASan+UBSan transport=mock engine=mock native_execution=0
```

计数包括逐次 mock I/O 和循环中的断言，不代表独立测试场景数量。ASan 与 UBSan 均开启；本机 ASan 明确不支持 LeakSanitizer，已保留原错误，使用分配账本补查失效代次和未受理堆地址。测试中的文件、native API 和引擎执行都是模拟接口，未执行 M32R 堆代码。

| 场景 | 观察结果 |
|---|---|
| 发布顺序、bootstrap/入口表错误、init 失败、init 返回时 S/view 通知 | READY 不提前发布；失败后无 S、RPC W、文件写或 UI 写入；自有可信分配收尾。 |
| 截断、超长、短读、读/close 错、越界读长、CRC/机身/ABI 错、重定位越界 | 在执行或 READY 前拒绝，fd 收尾；不发布扩展页面。 |
| 错目录单元、错 map pin | 外层 gate 接受结构安全的外壳，模拟引擎 init 拒绝；无写入、无 READY。 |
| 卡/IROM A/B、同代异内容、坏的高版本 | 保留有效旧副本；有效新卡可解开 A/B 同代冲突；同代卡冲突保留 IROM 并记录冲突。 |
| 同代、同长度、同 CRC、不同原始字节 | Python 构造 CRC 碰撞夹具，loader 按字节识别冲突。 |
| 49152 B 文件 + 8192 B BSS、24576 B 代码 | 外层边界接受；多一字节 BSS、代码超限、文件超限均拒绝；主堆分配失败回原厂。 |
| load 的 alloc/open/read/close/SD-ID/cache 返回处注入通知 | 作废候选；修复了 cache 返回后误覆盖通知状态的问题。失败清理期间重入 loader 返回 BUSY。 |
| link、unit 接收成功/失败、SD、heap、非破坏段、段 0/1 | 绑定作废、保留或撤销 lease 与合同相符；安全菜单重绑有 host 证据。未证明真实破坏性路径的在途生存。 |
| 独立 ui_abort、外部已换 tag | 即使会话 heap 无效仍恢复自有原厂引用；不覆盖外部接管记录。 |
| 颗粒门、消息头、Fn2、面板行与原七项 setter、事件环与代次耗尽 | 拒绝时整包不变；消息按值复制；面板行不进入原 setter；环覆盖和停止状态可观察。 |

所有 35 个完整配置代码桩的原指令重放和续接地址均与最终诊断 ELF 对照。PSW/寄存器的完整保留只有源码和反汇编审计证据，没有原生执行证据。

## 栈用量

沿用 `resident_v2/build.py` 的 M32R 工具链、`-Os` 和 C medium model，保留 `-fstack-usage`，另加函数/数据分节及链接 GC。完整原始 `.su` 在 `local/build/`，汇总见 [stack.json](local/stack.json)。

| 函数 | 编译器报告的静态帧 |
|---|---:|
| `rv_load` | 328 B |
| `read_one` | 184 B |
| `rv_validate` | 148 B |
| `rv_hook_observe` | 132 B |
| `rv_service` | 108 B |
| `rv_engine` | 40 B |

inline hook 保存现场 68 B，普通 native 桥另加 28 B。加载读路径已知帧叠加约为 68+132+328+184+28=740 B。原厂文件层、RPC、引擎以及异步回调的额外栈未知，不能把此值当整条调用链的安全上界。

## 有意取舍、未闭合项与 spec 差异

1. 按最新补充，pin 验证移到引擎纯 init，gate 不再解析任何单元目录或行池；旧 spec 的 resident SHA pin 已废止。49152/24576/57344 B 限制覆盖旧上限。`abi.h` 不改，ABI ID 仍为 `78b8cd23a6411337980dbd8a041256a7`。
2. 全 hook 配置保留全部观察点；priority 配置删除 H24、H26–H30、H33–H37，仅节约 336 B，仍未达窗口要求。H24/H33–H36 缺失会使 P2 生命周期矩阵失去这些直接回放路径的定位记录；H26–H28 缺失会使 P2 的省电路径观察不完整；H29/H30 缺失会使 P2/P6 的原 mode 写入路径失去覆盖；H37 缺失使 P7 没有 preview pre/post，P8 也缺相应 preview 关联。未以其它探针代替这些覆盖。
3. 按用户有意取舍，H23/H24/H33–H36 只记录与作废，不取消回放，也不向原 mode caller 返回服务错误码。对于 06/T1/control 0，回放和模式切换期间 T control 可以仍是 0；必须由仍有效的引擎在下一次安全菜单事务中恢复并读回 stock 2。撤 UI、停颗粒不能证明 T 已恢复，本任务没有实机恢复证据。
4. H17/H18 对段 0/1 仅 pre 作废，不把 LR 改到可能随 resident 一同被覆盖的 post 地址。其它段有 post 桩。独立见证未实现，root 与代码同时丢失仍是 UNOBSERVED；这未满足一级 hook 的完整要求。H15 暖/冷重入尚无独立证明，当前保守作废，不能宣称长期保持。
5. H25 只保守停止和撤 UI，没有有界的引擎 shutdown/恢复事务。原生 I/O/RPC 的阻塞上界、任务 owner 与原厂文件并发也未闭合。代次事后核对不能救回已经被覆盖的在途堆代码。
6. 文件 open/read/close、lease、cache、RPC8、preview、S、unit、SD ID、UI 与事件服务均有 C 实现，但文件写能力不会被本稿批准，mark_delivered 明确拒绝。送货确认所需的正式副本读回登记、16 B SD 身份和原始内容绑定没有完整接线。UI_VIEW restore_owned 当前退到原厂，而非完整返回外层配方页；renderer 全部字段与异步引用寿命未审完，不能称产品面板验收通过。
7. `rv_grain_commit` 及根快照门有 host 证据，但真实引擎的 EngGrain32 发布块尚未与 root 对接，init 的 grain 地址保持零。H09 因此尚不具备真实产品的 Stage2l 功能对等。

## ABI 修订建议与刷机前阻断

- 协调引擎采用已实现的 QUERY op3，在每次可发布 READY 的纯 init/重绑路径内验证当前单元 pin。当前读取的 `engine/core` 快照仍写着 resident 已验证 pin，并使用旧表池假设；不能直接与本稿新 gate 拼装。本任务没有改其它 worker 目录。
- 协调 36 B init 局部输入、bootstrap/纯 init 的 0/1 成功合同、init 回复的 capabilities，以及重绑能否重复 init。当前核心入口拒绝已经 initialized 的 init；本稿 host 重绑通过不能证明它已兼容。UI/S/W 分别用内部能力 bit17/18/19；bit16 文件写保持关闭，须统一这些语义后再接真实引擎。
- 协调原生事件到引擎内部事件编号的翻译、RPC 事务 token 的位置、UI release/cursor 的参数以及稳定 renderer descriptor。不得把各 worker 的独立 mock 通过当作联调通过。
- 为颗粒明确一个 root 内的原子提交结构和发布合同，继续保证 H09 无堆解引用。不要让引擎自行猜 root 保留字段。
- 本轮读取的 `card_container_v2/gxrce.h`、`gate.c` 与 `engine/core/eng_data.c` 仍包含 32768/4096 或旧代码限制；需由各目录 owner 同步为本次 48/24/56 KiB 决定。已记录相关依赖快照，未越界代改。
- 首要阻断是体积。必须重构常驻实现并重新严格链接；删三级 hook 仅节约 336 B。未借用未知段空间，也未以移动正式 root 换取通过。随后还需关闭独立启动/段见证、inflight 生存、H25、文件写与送货确认、UI 生命周期及真实引擎 pin/语义校验。

这些阻断关闭后，才可进入经用户另行授权的映像打包与相机验收。本次没有触碰相机，没有访问任何 `/Volumes` 下的存储卡，没有 commit 或 push。

## 产出与复核命令

| 文件 | 用途 |
|---|---|
| `resident.c/.h`、`loader.c`、`services.c`、`hooks.c`、`validate_envelope.inc.c` | 常驻实现与外层 gate。 |
| `abi.h`、`bridges.S`、`resident.ld`、`runtime.c` | 冻结 ABI、桥接、严格布局和 freestanding 支持。 |
| `build.py`、`verify.py`、`make_fixture.py`、`host_checks.c` | 可复跑构建、审计与主机故障注入。 |
| `local/build/resident.map`、`local/constrained-link.log` | 正式窗口的真实链接失败。 |
| `local/build/OVERSIZE-NOT-A-CANDIDATE.elf`、`local/build/oversize.map` | 全 hook 诊断 ELF 和 map。 |
| `local/priority/build/OVERSIZE-NOT-A-CANDIDATE.elf`、`local/priority/build/oversize.map` | 删除三级 hook 的诊断 ELF 和 map。 |
| `local/patch-manifest.json`、`local/priority/patch-manifest.json` | 每个 hook 的地址、官方原字节、替换字节；另保留 Stage2l 参考字节，均不可安装。 |
| `local/host-checks.log`、`local/verification.json`、`local/failures.log` | 成功 host 日志、明确 BLOCKED 状态及历史原始错误。 |
| `local/trust.json`、`local/size.json`、`local/stack.json`、`local/inputs.json` | 身份、pin、体积、栈与输入哈希。 |
| `SHA256SUMS`、`checksums.py` | 全部交付文件的哈希与复核工具。 |

全 hook 诊断 ELF SHA256 为 `c39a1bc65c88a871df13ecd880d8be420795d88b7ac65538da29304ad4d1183e`；priority 诊断 ELF SHA256 为 `1bf8edb332a9ff84a95d5959835015d1ea80ef56709e7dad0d4e60472aa06218`。这些摘要只绑定本地诊断产物。

```bash
cd /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh
python3 -I -B firmware/resident_impl/verify.py
python3 -I -B firmware/resident_impl/build.py --drop-probes
git check-ignore -v firmware/resident_impl/local/check
cd firmware/resident_impl
python3 -I -B checksums.py --verify
```

前两个命令当前应返回 2，明确表示窗口验收失败。`verify.py` 会先运行 ASan/UBSan 并输出 PASS_HOST，再报告 BLOCKED_WINDOW_OVERFLOW。重建会改变部分主机产物与日志；重新交付时先运行 `report.py`，再运行 `checksums.py` 更新索引。
