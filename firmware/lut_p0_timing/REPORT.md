# P0：v3.4c 私有缓冲 LUT 测速容器

2026-10-26。本探针仅供主机验证和独立复核。它测原生 tick 与完整 17³ 内核，不处理照片，不安装产品。相机上的 tick 单位、ns/像素对和整张照片延迟尚未测得。

## 候选与绑定

交付文件为 `local/staged/GXRCE.DAT`，53,100 B，距 65,536 B 安装/存储链上限余 12,436 B。SHA-256：

```text
75edcedac2219d31a1cc2e789e9ecc7381df528ee1e94d4b5e08329a668c2e87
```

| 字段 | 最终值 |
| --- | --- |
| 目标运行 ilaunch3 SHA-256。 | `24b1de0e46ea00adeacd224da28770e185b05a08686c40c647032c533c021f72`。 |
| 容器头 body ID。 | `da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7`。 |
| resident build ID。 | `eb96410f5224f76c1cf684a3bd6789eca4c80acf34019120e30dacaeb01da941`。 |
| resident ABI。 | `b6353e4de1c89bd37c08ba6734efc8e0`。 |
| 既有执行 hook。 | H01/H02/H05/H06/H07/H08/H09；不新增 hook。 |
| 探针代次及身份。 | generation=1，头部保留区 `LUTP0001`。 |

## r3 changes

本轮修复 `research/review_lut_p0/REPORT.md` 的三个 P1 与两个 P2，等待新的独立复核。旧 r2 DAT、SHA256SUMS、源码和验证产物完整保存在 `local/staged_r2/`，`preserved.json` 逐项保护 254 个文件，未替换审查目录里的反例或报告。

- P1-01：`p0_menu` 只在 UI_LIST 发布成功、取得非零 tick 后才提交 REFERENCE。失败保持 NEW/start=0，并调用原 gen 114 UI_VIEW 撤回服务；没有可确认的区间。零 tick 直接进入 ERROR。原分配失败刺激重跑后，重试的 start=100000、end=110000、delta=10000，完整日志解码为合成的 1000 Hz，原 11 倍反例消失。
- P1-02：H07 的非确认退出、H06 close、参考页发布失败以及再次 H01 打开都会使运行区间失效，清 start/end/delta，并粘住 INTERRUPTED 和 ERROR=7，直到冷启动。重开显示 `P0 REF RESTART`，重新取起点，同时显示 `INVALID: power off, restart`；OK 也不会进入测速。原 MENU 反例在重开后得到新的 10000 ticks 区间，但错误仍为 7、样本为 0，不能生成有效结果。
- decoder 在原 `LUTP0001` 日志的保留 32 B 内要求 `P0R3` 协议、STARTED+CONFIRMED、非零起点及批次准入记录。INTERRUPTED、无协议的旧 r1/r2 日志和伪造的 interrupted DONE 均拒绝。参考有效但批次未完成或报错时，只报告无效/不完整，不输出 tick_hz。两份冻结的旧完整 ERROR=0 反例也不再被接受。
- P1-03：按任务方本轮明确决定，允许下表四个 UI 字段由未改的 gen 114 UI_LIST 服务发布、由已审 shared 撤回；P0 不直接写 native。另核对 tag-33 state 指针退出时恢复。H08 发布失败及 H06 close 由同一 UI_VIEW 撤回服务恢复后返回 CONSUMED，避免 resident 通用 `close_owned` 对白名单外 `0x2037F3BC` 的清零 store。没有修改 resident、services 或 body。
- P2-01：先用四个独立 H08 回调依次跑 4、64、512、4096 对 LUT。每档检查 CRC、IE 与 tick 差，超过 `reference_delta/200` 就 ERROR=9，不跑下一档。四档通过后，原四长度、三类别、六轮的 72 条交错日程保持不变。四个准入档都覆盖超预算拒绝；准入每回调最多 4096 对，正式回调含预热最多 8192 对，均返回菜单任务后才开始下一块。预算是参考区间 1/200 的 ticks，按约 10 秒参考约为 50 ms；这不是已测的相机响应上界。
- P2-02：`USER_GUIDE.md` 保持中文六步，明确卡 B 旧产品 DAT/OK/CTL 与刷机文件移到电脑、无探针基线冷启动、批准 SHA、参考中断须关机重来、DONE/72/ERROR/FLUSH 检查、保留两份日志及实际秒数、删探针后核对原基线。照片和卡 A 保持原样，旧产品 DAT 绝不自动放回；恢复保留卡 A Stage2l、50mm、“+ & playback”。本轮没有操作任何卡。

| native 白名单字段 | 宽度 | ilaunch3 文件偏移 |
| --- | ---: | --- |
| cursor `0x2022F725`、`0x2022F726` | 各 1 B | `0x1E4925`、`0x1E4926` |
| list pointer `0x2022F5A8` | 4 B | `0x1E47A8` |
| row count `0x2022F5AC` | 1 B | `0x1E47AC` |

`r3_verify.py` 在本任务 local 下为全部真实 resident/probe/gen 114 C 单元的 LLVM O0 store 和 memcpy/memset 加观察器，连“把零写回零”也记录。只允许上述精确地址和宽度，以及 tag33 项的 4 B state slot；发布/撤回还必须来自 services.c/shared.c。host 映射的私有 P0State、resident root 和已分配扩展堆块单独判定为私有内存。任何其它 native store 立即退出 93。负控实际执行对 `0x2037F3BC` 的同值写，必须失败，不能靠前后字节无变化漏报。

退出矩阵在真实 gen 113、114 DAT 夹具下分别核对四字段与 tag33 指针的精确 native 值，覆盖 REF、四档准入边界、正式 kernel batch、DONE、ERROR 的 MENU，参考/测速/DONE 的 OK，H06，首次 UI 分配失败、无终止符字形触发真实 UI_TEXT VERIFY 拒绝、参考/准入/kernel 中途发布失败、两条审查重试及 1000 次重开。每套记录 9,170 次 native store，其中四字段各 2,292 次、tag33 指针 2 次，白名单外为 0。正常 P0 不切换 tag33 指针；另用原 UI_VIEW 服务实际切到 snapshot，再验证退出精确恢复，避免只测试一个没变过的指针。原生构造器本身在追踪窗口外，期望值在发布前抓取；不能把它合法写入的 type、游标和视图栈计为 P0 写入。

证据为 `local/r3-results.json`、`local/r3/{113,114}/` 和 `local/logs/r3-*`。`r3_replay.py` 只重绑冻结审查者独立 oracle 的输出路径与 helper，数值公式、刺激及机器码断言原文执行；`local/independent-kernel-results.json` 记录 16,384 对逐字节一致，并与冻结 r2 的四份输出逐字节比较。普通主机流程、新增 r3 矩阵及冻结混合 A/B 测试均通过 ASan/UBSan；写追踪另用 O0，以保留同值 store。两版矩阵的所有日志逐字节相同。它们覆盖 C 和有限 M32R 模型，不是相机、真实按键、native 绘图或完整系统调度验收。

`local/protected-inputs-r3.json` 保护 8,668 个现有输入，覆盖五个指定 firmware 树、两个审查依据目录、官方文件及卡备份。五个 firmware 树和审查目录还检查新增/删除。下载集合只核对已冻结文件，排除并行 bridge 缓存，避免把别人的新下载当作输入漂移。原 5,458 项清单未重置，逐项哈希不变；最初旧脚本的新增下载范围误报保存在 `local/failures/freeze-r2-new-downloads-only.json`。`decisions.tsv` 从不作为输入或进入摘要，两个并行研究目录未写入。

## r2 changes

- 改用本目录副本重编的 gen 114 services，8 个目标对象的分配段和重定位与原对象一致，见 `local/service-build.json`。GCC LTO 记录含副本路径，归档 SHA 因而不同；探针用 `ld` 链接，不使用 LTO。
- 补测非 type5 首入、后续 type5 入口，以及原生清栈后 count=1 的 push 顺序。新 seed 首入发布成功，旧 seed 在相同状态下拒绝。旧手设状态仅留作兼容回归。详细输入、指令和模型边界见下方验证表。
- 真实 gen 113、114 DAT 夹具均通过完整操作、黑匣子 flush、MENU 和移除 DAT 后的 A/B 回退。114 夹具为已审查的 `132e5638…49a5`。
- generation、`LUTP0001` 和非安装设计不变。内核、计时桥和探针运行源码不变，两个目标对象也与 r1 相同。r1 DAT 及校验文件在 `local/staged_r1/`，原源码、ELF 和验证记录在 `local/r1-evidence/`。

body ID 是原官方基线的身份，不是包含 resident 自身的修改后映像 SHA。本轮从真实 resident ELF 提取 80 B trust，并与 full-r11 头逐字节比较。把 `24b1…` 填入头部 body ID 的反例确实被真实 `rv_validate` 以 BODY_ID 拒绝。`audit.py` 另把 resident 的 `.payload`、`.root_pins` 和全部 hook 补丁与冻结运行映像逐字节比对。

## 只读与退出设计

探针初始化只申请 `CAP_UI`。容器没有产品适配器或 `ps_install`，不调用 IROM 写入、GXTS/GXLS、CTL、配方、RPC8、设置或 GXRCE.OK 的接口。UI 使用 ABI 匹配 v3.4c 的 gen 114 `RvApi`、`rv_native_seed`、UI_TEXT、UI_LIST 和 UI_VIEW 撤回服务；探针直接写入的 seed、字形、样本、scratch 和入口表都属于私有扩展堆块。服务会发布和恢复上表白名单内的 native UI 字段，不能称整个探针零 native 写入。它不移植旧 P0 的 `0x20052800/0x2005280C` 显示帮助函数。

`rv_load` 的规则是卡优先，再在 IROM A/B 中选较新者。代次 1 不妨碍探针从卡加载，又严格低于当前及后续产品 113、114、115…；身份字段和缺少产品目录也让它无法通过产品格式门。主机实际运行了真实 `ps_install`：产品 gate 拒绝该文件；把 verifier 放宽到只接受 resident 外壳后，113、114、115、UINT32_MAX 四种已安装代次仍返回 CONFLICT，且无创建、写入、改名或交付标记。

移除卡上 DAT 后，真实 loader 在两套主机夹具中分别选回 gen 113、114 的 IROM A，A 缺失时选 B，原文件逐字节保持不变。这里执行的是 loader 和服务的真实 C；产品入口由仅用于观察选择结果的 double 代替，没有声称在主机运行完整产品或验证实机冷启动。

唯一可持久写出的数据是既有 `GXRBX0/1.BIN` 黑匣子。构建只替换原 `blackbox.c` 的两个 include，其 flush 函数原样保留；在参考区间结束、测速结束或 OK 退出时，于计时区间外调用。它保留原有卡身份、上下文、A/B 代次、CRC 和写后读回检查。宿主夹具对任意其他文件写入或任何 rename/delete 直接报错。flush 失败时屏幕显示 0，不能把内存样本当成已保存日志。

## 操作与调度

详见 [USER_GUIDE.md](USER_GUIDE.md)，共六步。50mm 保持连接，打开 ADJ 的 Image Settings 配方页，出现 `P0 REF` 后用手机量约 10 秒，再按 OK 结束。参考起点在首次页面发布后读取，终点在 H07 的 OK 回调中读取，flush 和关闭页面发生在终点之后。

参考区间用 OK 结束。官方键表的 0x23 指向 `0x202c2abc`，其中 `0x202c2d74/84` 调 H07。真实 resident 会在 keep=0 时强制关页，探针也显式返回 CLOSE_AND_PASS。再开 ADJ 页，按住向下键推进测速。键表的 0x20 与连发 0x2c 均进入 `0x202c25b8`，连发被转成 0x20，再经 `0x202c27dc` 调入带 H08 的移动函数。DONE 后按 MENU，测试使用 key=0x29、keep=0；官方 `0x202bd88c` 调入带 H07 的 `0x202871d8`，返回地址为 `0x202bd890`。证据在 `local/native/` 和 `local/native-contract.json`；实际按键送达和屏幕外观仍待上机。

每个 H08 回调只处理一档准入或一条正式样本，然后回到菜单任务。先经过四档小到大准入，每档最多 4096 对。正式样本每条最多计时 4,096 对；热表轮次另做一次不计时的预热，故单回调最多执行 8,192 对 LUT。初始化、预热、scratch 重填、两次 CRC、UI 和文件 I/O 均不计入内核时间。内核和 tick 桥不关中断，并在批次前后检查已知 PSW 的 IE 位；既有 UI 服务仍使用其原有短临界区。这里给出的是固定工作量上限，尚无实机毫秒级响应上界。

## 算法与样本合同

`kernel.c` 使用完整 17³ 表，14,739 个大端 u16 Q8.8 通道值，共 29,478 B；256 个打包坐标 word 共 1,024 B。坐标在构建时生成，像素内不做除法。255 映射到 cell=15、frac=256。相同小数稳定保留 Y、C2、C3 轴顺序，按 Y 最邻近的布局取四顶点。

```text
A = 256*v0 + f1*(v1-v0) + f2*(v2-v1) + f3*(v3-v2)
Yout = clip((A_Y + 32768) >> 16)
Cout = clip((A_C_pixel0 + A_C_pixel1 + 65536) >> 17)
```

每组输入为 `[Y0,Y1,C2,C3]`，先读一个 32-bit word，分别插值两个像素，最后合并共享色度并写一个 word。最终机器码回放逐组检查了 24 次节点半字读、4 次坐标 word 读以及一个输入 word 读、一个输出 word 写。CRC 被校验并写入样本记录，编译器不能把结果当成无用计算。

测试表是完整的、非可分离的诊断表，覆盖 u16 极值；它不是 GR IV 配方。输入含平滑块、0/255 极端值、差异很大的 Y0/Y1、六种排序、相等小数和散列打乱的 cell。另用身份表、极值表和固定种子随机全表回放。参考实现按四顶点重心权重直接求和，与目标的相邻差分实现独立。

三类正式样本为空调用、原生汇编减计数循环、完整 LUT。准入后 trip count 仍按 4096、4、64、512 轮换，六轮，每轮各类次序轮换，共 72 条。正式首轮不另加预热，但它发生在准入之后，不能叫整个探针的首次全长遍历；四档准入的 ticks 单独保留。后五轮在每条计时前，先跑同长 LUT 并核对 CRC，再重填输入。这个过程定义“预热后”协议，不假定未知的物理 cache 容量，也不承诺首轮一定是冷 cache。全部原始样本保留 start/end tick、对数、类别、轮次、预热标记和输出 CRC，不删除调度离群值。

完整 33³ Q8.8 表为 215,622 B，单表已超过 65,536 B 文件上限和 114,688 B image+BSS 上限。本探针只测 17³，没有把平面或部分节点冒充 33³。free-list 快照也跳过，当前没有已审清的 allocator 一致性协议。

## 主机验证

| 检查 | 证据及结果 |
| --- | --- |
| 真实 M32R 内核。 | `local/replay-results.json`；混合、身份、极值各 5,120 对，随机全表 1,024 对，共 16,384 对，逐字节等于参考。身份输出也逐字节等于输入。 |
| 桥与内存访问。 | 最终 DAT 代码等于 ELF；另基址链接归一化后全字节相同。内核保存 GCC callee-save，零 trip 不访存，tick 桥保存 r8–r13/LR，减计数和空调用均回放。 |
| 最终 M32R seed。 | `local/seed-replay-results.json`；从最终 DAT 对应代码执行 seed、copy、clear，未替换服务调用。9 例覆盖首入 type 0/4/9、后续 type 5、旧手设兼容、未知表、零表、容量 235 拒绝和 236 接受。私有快照逐字节准确，236 B 后哨兵不变，原生 state 和 descriptor 未被写。 |
| 原生构造顺序。 | `local/native-order.json`、`local/native_model.h`；H01 前执行官方 type 0/4/9 writer，table=`0x2022F56C`，capacity 由真实服务写 256。首入发布 16 行，旧 seed 拒绝；H02 后执行 type5 writer、`0x201C0730` 清 count 和 push 存储，得到 count=1、tag33、state=`0x2022F71C`。随后 type5 入口通过。parent tag32、part2 参数、外部图形调用仍是模型边界，前一 type 不是现场观测值。 |
| loader/UI/安装。 | `local/host-results.json`；真实冻结 C 和 gen 114 服务源码在 ASan/UBSan 下通过。gen 113、114 夹具各覆盖非 type5 首入发布、后续发布、H07 两种 keep、72 条 H08 样本、MENU、完成后重开、A/B 回退、坏绑定回退、计时回绕、无效区间、黑匣子创建失败和安装拒绝。native 分配、字形、时钟、文件系统为 double。 |
| 绑定与完整日志。 | `local/audit-results.json`；真实 v3.4c `rv_validate` 接受新容器及原 ABI/build 绑定，坏 body/build/ABI 被拒绝。运行映像、resident、全部补丁、DAT 节点与坐标吻合；两套日志各解码 72 条样本，拒绝截断、payload 损坏、错误输出 CRC、错误 schedule 和错误参考区间。公式另用显式合成数据检查。 |
| 冻结输入。 | `local/protected-inputs-r3.json` 及 `local/logs/freeze-before-stage.stdout`；本轮 8,668 项复核，原 5,458 项清单保留并逐项确认无变化。`decisions.tsv` 不作为输入，不进入摘要；两个并行研究目录未写入。 |

主机日志中的 tick 是脚本值。解码器把这些结果判为分辨率不足，没有从它们生成相机性能结论。机器码回放是有界指令语义模型，不模拟实际流水线、中断、cache、DMA 或相机运行。

最终 image+BSS 为 73,100 B；私有 state 为 19,992 B，其中 scratch 为 16,384 B。按目标 M32R 的真实布局，主块 request 为 80,604 B；加各自 12 B 块头、608 B loader 工作区和 1,968 B UI 快照，已知保留量合计 83,216 B。这不是实测空闲堆。内核栈回放深度为 92 B；`.su` 和指令证据保留在 local，未把局部栈模型当作原生菜单任务总水位。

## tick 与每对像素耗时的换算

只复用 `0x2005F164`，官方文件偏移 `0x014364`，其实际调用链到 `0x0500C584`。桥沿用旧 P0 的完整 native callee-save 规则。不读取未知控制寄存器，不猜 cycle counter，也不从 tick 推断物理 MHz。

```text
tick_hz = reference_delta_tick / external_seconds
ns_per_tick = 1e9 / tick_hz
b = (delta_tick_LUT - delta_tick_harness) / P_test
ns_per_pair = b * 1e9 / tick_hz
P = H * W/2
T_LUT = P * b / tick_hz
T_extra = T_entry + T_DMA_to_CPU + T_LUT + T_CPU_to_DMA + T_queue
T_saved = T_stock_same_settings + T_extra
```

4288×2848 的 P 为 6,106,112。解码器保留全部 raw，并对后五轮各长度取中位数和范围，分别拟合空调用、减计数、LUT 的斜率及固定开销。主结果用 LUT 斜率减空调用斜率；首个正式全长样本、五个预热后全长样本和四档准入另列。最大批次扣除空调用后不足 16 ticks，或斜率非正时，返回 inconclusive，不输出 ns/对外推。所有区间仅接受小于 2³¹ ticks 的无符号差，参考起点和区间均须非零；协议/参考标记无效直接拒绝，任何错误或不完整批次都不输出 tick_hz。

把用户实际秒数填入命令，在主机上分别解码两份日志，选记录完整且 error=0 的最新一份：

```sh
cd /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh
/usr/bin/python3 -I -B firmware/lut_p0_timing/decode.py /主机副本/GXRBX0.BIN --seconds 10.12
/usr/bin/python3 -I -B firmware/lut_p0_timing/decode.py /主机副本/GXRBX1.BIN --seconds 10.12
```

手机读数与按键误差决定参考精度；计时途中退出页面、休眠或时钟状态变化，应关机重来。未来若要计算 cycles/对，须另有独立成立的 CPU Hz。本探针只支持 tick/对、ns/对和 scratch 内核外推；真实照片的总线、同步、队列、编码和保存成本须留给后续 P3。

## 失败、恢复与复核

若 tick 单位或原生调用合同不成立，可能得到零值、错误时间或菜单挂起；地址、重定位或返回约定有误时还可能破坏堆/栈。CRC 或错误标志不通过时不采用耗时结果。本轮没有证明实际按钮时延、菜单响应、物理 IRQ 行为、native I/O 或硬件恢复。

恢复先关机，删除卡上这个 `GXRCE.DAT`，再冷启动，让既有 loader 选择已安装产品。若仍不恢复，按用户指定机身恢复路线使用卡 A Stage2l，保持 50mm 连接，通过“+ & 回放键”开机。本轮未重测该恢复入口。

复核可按以下顺序重建并运行；所有 Python 均隔离执行，所有输出留在本目录的 ignored `local/`：

```sh
cd /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh
/usr/bin/python3 -I -B firmware/lut_p0_timing/freeze.py
/usr/bin/python3 -I -B firmware/lut_p0_timing/build.py
/usr/bin/python3 -I -B firmware/lut_p0_timing/native_evidence.py
/usr/bin/python3 -I -B firmware/lut_p0_timing/verify.py
/usr/bin/python3 -I -B firmware/lut_p0_timing/r3_verify.py
/usr/bin/python3 -I -B firmware/lut_p0_timing/replay.py
/usr/bin/python3 -I -B firmware/lut_p0_timing/r3_replay.py
/usr/bin/python3 -I -B firmware/lut_p0_timing/seed_replay.py
/usr/bin/python3 -I -B firmware/lut_p0_timing/audit.py
/usr/bin/python3 -I -B firmware/lut_p0_timing/stage.py
```

当前状态为 `STAGED_HOST_ONLY_REVIEW_PENDING`。实现侧验证不替代下一轮独立复核；本轮没有写卡、连接相机、USB、联网、提交或改机身。
