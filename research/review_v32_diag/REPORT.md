可以用

可以把这个冻结 DIAG 用作 full-r3 的只读预检。未发现阻止这次 DIAG 采样的 P0/P1 缺陷。它能确认小容器加载与列表发布、此时的连续申请能力，以及 full-r3 文件的读取、外壳和当前单元 pin；不能承诺一次开机就证明 full-r3 能完整加载、安装和运行。

已核实的是下面的最终字节检查、主机执行和包文件比较。相机尚未运行 DIAG。本轮没有接触相机、卡或其它卷，没有修改 DIAG、产品、常驻或机身映像。已接受的 engine_fix_r2 审查 F02 不在本轮复审范围。

审查发现按严重程度列在这里。

P0/P1：没有发现新增阻断。

P2 R01：decode.py 的错误码说明仍针对旧 full，会误导 full-r3 的判读。

位置为 `firmware/v32_load_diag/decode.py:49`。反例是本轮健康的 full-r3 三单元输入：A/B 原始 open 都为 -1，所有文件、外壳、pin、精确申请检查通过，但解码 JSON 仍写“在产品服务中是 RV_IO，只有 -2 才会触发缺文件默认值”。full-r3 已改变只读 open 的映射，这句话不适用于本次目标。见 [健康解码结果](local/host/good-decoded.json) 和 `firmware/engine_fix_r2/REPORT.md` 的错误码约定。数值、屏幕 CRC、DIAG 机器码不受影响，本项不阻止采样。

最小修复建议是仅把 contract 文案改成版本明确的说明：“这里保存 native 原始返回值。full-r3 将只读 open 的 -1/-2 映为 RV_UNAVAILABLE；负值本身不证明文件不存在。”本轮没有修改该文件，阅读原 decoder 输出时按本报告解释。

下面是安全检查的证据。

| 检查 | 已核实的结果 | 证据 |
| --- | --- | --- |
| 无持久写入。 | 最终容器只包含 open/read/close、alloc/free、ASCII、language、context 这八个 native 桥。所有 open 的 flags 为 0。没有 create/write/rename/delete、RPC8、preview、settings 或 storage_mark 链接符号。DIAG 不发 X/V/W/T，不读写 DEEPTBL、配方或设置。 | `firmware/v32_load_diag/diag.c:16`、`:35`、`:78`、`:180`；[最终身份及桥指令](local/identity-and-container.json)、[最终反汇编](local/logs/diag-final-disassembly.log)。 |
| 临时探测块的所有权与释放。 | 每次非零分配先由 rv_allocation 核对堆范围、next、flag=1、大小，再调用 free，随后读 user pointer - 8，只有 flag=0 才记释放成功。不使用 native free 的返回寄存器。 | `diag.c:156`；最终 free 调用在容器偏移 0x460，0x464 的字节 a599fff8 是 ldub r5,@(-8,r9)。见 [机器码证据](local/machine-safety.json)。 |
| 释放失败后停止。 | 坏头置 D01 bit24；free 后仍非零置 bit25。两种情况均跳出档位循环，并阻止最后的 full 精确探测。向十一档和精确申请的每一次 free 分别注入失败，都没有后续探测。 | `diag.c:161`、`:163`、`:175`、`:190`；[25 个补充用例](local/adversarial-results.json)、`local/logs/adversarial-free-at-1.log` 到 `adversarial-free-at-12.log`。 |
| fd 上限。 | DIAG 自己一次最多持有一个 fd。独立补充 fixture 把可用 fd 收紧为两个，所有失败 open 改为真实约定的 -1，三单元、缺文件及 UI 错误路径仍通过。原 fixture 的四 fd / 部分 -2 不能单独充当此项证据。 | `diag.c:35`、`:62`、`:75`、`:182`；[补充 fixture](local/host/adversarial-fixture.c)、[补充结果](local/adversarial-results.json)。 |
| UI 固定数组。 | 发布前要求 *0x205A27D8=0x205A279C、count=1 或 2、native type=5 和 descriptor 的有限 RAM 范围；关中断后再核 array/count 并调用 rv_ui_capture。不接受任意堆数组，不替换固定 view 的 state 指针，只发布名称、数量与游标。 | `diag.c:211` 至 `:249`；`firmware/resident_v32/resident/shared.c:61`；最终 publish 指令见 [机器码证据](local/machine-safety.json)。 |
| UI 与失败撤回。 | array 不符、count 0/3、type/table 不符、UI 分配失败/坏头、ASCII 失败、空 glyph、末尾未终止，都退回原生七项并停用。count=2 可用，H01 的父 tag 尚非 33 仍按批准 LIST 合同发布。逐一选择 16 行不应用配方；退出恢复七项，重开不再次采样。 | [32 个原用例](local/host-results.json)、[补充用例](local/adversarial-results.json)；`diag.c:264`、`:271`；`firmware/resident_v32/resident/hooks.c`。 |
| IRQ 极性与恢复。 | 最终 save 为 1090f00081c0ffbf10a11fce，restore 为 10a01fce。save 读取原 PSW，以 AND 0xFFBF 清 IE；restore 写回 token。按这些实际指令字节核对 65,536 个 16 位 PSW 和嵌套语义，没有把 IE 置一。 | 容器偏移 0x22C、0x238；[最终字节检查](local/identity-and-container.json)。这是受限指令语义检查，不是整段 M32R 执行。 |
| 栈。 | 最终 ELF 调用图配合逐字节一致重编的静态 .su，DIAG 自身最大帧是 menu 的 112 B；含实际 hook 保存与 resident 调用前缀的最大模型为 356 B。无递归或动态栈分配，状态和 512 B 流缓冲在 resident state 内。 | [栈模型](local/stack-model.json)、`local/rebuild/*.su`、[重编结果](local/rebuild.json)。 |
| 身份与可接受的外壳。 | DIAG、full-r3 的 body/build/ABI 全部 80 B 与批准 resident ELF 相等；resident payload 和 pins 与批准 ilaunch3 对应地址相等。最终 DIAG 的 header/payload CRC 正确，BSS=0、重定位数=0，十个入口 thunk 都指向预期函数。实际 resident C loader 接受最终 DIAG。 | [身份及容器检查](local/identity-and-container.json)、[host 结果](local/host-results.json)。 |

“分配必须释放”针对这里临时取得的探测块逐次核验。批准的 resident 合同另保留主块、loader 工作区和 UI 快照到重启，不能在 UI 仍引用它们时强行释放。DIAG 的主块 request 为 15,052 B，含原生头 15,064 B；loader 为 620 B；首次发布 UI 后再保留 1,980 B，正常合计 17,664 B。DiagState 为 3,364 B，位于既有 6,144 B state 中，没有另行分配。

若一次 free 未确认，该块不会被当作已回收，不重试 free，也不继续探测。它会占用或至少不能再计作可用堆空间，直到关机重启；最大档是 96 KiB，含头 98,316 B。坏分配头同样不能安全盲目 free。D01 bit24/25 出现后应停止 full-r3 试用并重启。后续为显示诊断而申请 UI 快照，不是继续做内存探测；若 UI 也申请不到，则只剩原生菜单。

失败不都等于退出诊断。GXRCF 读取、CRC、pin 或普通申请失败时，DIAG 保持可见并把失败写进 D 行；发布自身失败才走 CLOSE_AND_PASS，撤回到原生菜单。主机的这些有限路径已通过 ASan/UBSan，没有挂起或越界。真实 native I/O、分配器和 glyph 调用的阻塞行为没有在设备上验证。loader 原有的 IROM 回退策略没有改变；“缺 DIAG 退七项”的测试以 IROM 没有其它可执行引擎为前提，不能外推为任意 IROM 内容都不会执行。

356 B 是新增调用链模型，不是任务 6 的实测总水位。16 KiB 预算内还包括原生调用者、native 函数内部和 IRQ 栈，这些不在模型里。批准 v3.2 的同类模型峰值为 876 B，DIAG 未增加该上界；未用 356 B 冒充完整栈安全证明。

full-r3 的兼容性结果如下。

原 `host_checks.c:147` 写死 58,160 B，后面的健康断言写死 89,240 B，不能直接用它证明新产品失败。本轮先原样运行，确实以 exit 91、`full_bytes==58160` 退出，原始日志保留在 [失败日志](local/failures/original-fixture-full-r3.log)。然后仅在本 review 的 local 副本中，把期望文件量换为 59,704、主块换为 78,380，并让三单元用例都打印屏幕行。真实 DIAG C、resident C、原 DIAG 二进制和 full-r3 字节均未修改。

精确申请从最终 resident 指令和 full-r3 头部得到：

```text
full-r3 header.file_bytes                 59,704
full-r3 header.bss_bytes                  11,172
align4(file + BSS)                        70,876
resident overhead                         7,504
  session 1,104 + state 6,144 + UI 256
传给 native_alloc 的主块 request           78,380 = 0x0001322C
另加原生分配头 12 后的主块占用              78,392
```

`0x20053764` 的最终指令为 add3 r4,r4,#7504，随后调用 alloc。见 [resident 最终分配指令](local/logs/resident-main-request.log)。DIAG 的 stream 在 header 通过后调用同一个 `rv_block_bytes` 算法，sample 最后把 D0A 原值传给 probe；三单元均观测 D0A=0001322C，D01 的精确分配与释放 bit22/23 均置位。因此它试的是 resident 的 78,380 B request，报告中的 78,392 B 不能再作为 request 多算一次头。

| 单元 | unit 名 | GXRCF 字节 / 全文件 CRC32 | 外壳 / 当前 map+stock pin | 精确申请 / 释放 | 原 decoder |
| --- | --- | --- | --- | --- | --- |
| GR LENS A12 50mm。 | jlaunch | 59,704 / D68068F2 | OK / DF2BCAF5 相等。 | 78,380 / 两者通过。 | 16 行和屏幕 CRC 通过。 |
| GR LENS A12 28mm，仅主机。 | qlaunch | 59,704 / D68068F2 | OK / 6700E6FF 相等。 | 78,380 / 两者通过。 | 16 行和屏幕 CRC 通过。 |
| MOUNT A12。 | l08firm | 59,704 / D68068F2 | OK / 1B3C7000 相等。 | 78,380 / 两者通过。 | 16 行和屏幕 CRC 通过。 |

完整记录在 [32 个主机用例](local/host-results.json)，另有 [25 个补充用例](local/adversarial-results.json)。[交付复核](local/delivery-audit.json) 还以长度仍正确的八位 D04 改动，确认 decoder 拒绝真正的屏幕 CRC 错误。host 运行的是实际 resident loader/hooks 与 DIAG C；rv_invoke 按已核入口映到 C，native 文件、堆、显示和 IRQ 是 double。最终机器码另作上表的字节审查与独立重编，未声称 CPU 模拟器、相机或真实文件系统执行通过。

健康运行的 D00 到 D0F 期望如下。表中是最大档也能成功的健康 host 示例，成功 fd 固定为 20。相机可变项必须按说明判读，不能要求照片逐字等于 host 示例。

| 行 | 50mm host | 28mm host | MOUNT host | 相机可变项及含义 |
| --- | --- | --- | --- | --- |
| D00 | D1320101 | D1320101 | D1320101 | 固定协议签名。 |
| D01 | 00FFFFFF | 00FFFFFF | 00FFFFFF | 可变。十一档及精确请求全部成功并释放才是此值。 |
| D02 | 00000000 | 00000000 | 00000000 | 健康目标为四个状态都通过。 |
| D03 | 0000E938 | 0000E938 | 0000E938 | 本包 full-r3 固定 59,704 B。 |
| D04 | D68068F2 | D68068F2 | D68068F2 | 本包 full-r3 全文件 CRC32。 |
| D05 | 6A6C6175 | 716C6175 | 6C303866 | 随单元变化，unit 名前四字节。 |
| D06 | 6E636800 | 6E636800 | 69726D00 | 随单元变化，unit 名后四字节。 |
| D07 | 01510000 | 01510000 | 01510000 | main=0151，cmp=0000。 |
| D08 | DF2BCAF5 | 6700E6FF | 1B3C7000 | 随单元变化，候选 map128+stock410 的 CRC。 |
| D09 | DF2BCAF5 | 6700E6FF | 1B3C7000 | 随单元变化，resident 的对应 pin。 |
| D0A | 0001322C | 0001322C | 0001322C | 固定 78,380 B，只是大小，不单独代表申请成功。 |
| D0B | 7FFF0014 | 7FFF0014 | 7FFF0014 | 低 16 位是相机实际 fd，可变；两缺失微调路径返回 -1 时高 16 位应为 7FFF。 |
| D0C | 03220120 | 03220120 | 03220120 | 首次干净进入的通常值；flags 随运行状态变化。 |
| D0D | 00000000 | 00000000 | 00000000 | 健康为 fault=0、check_failure=0；只记录本次 DIAG。 |
| D0E | 00000000 | 00000000 | 00000000 | 事件数/丢弃数，随本次历史变化。 |
| D0F | 86E25B68 | 9F7A7FFB | 01C57674 | 可变。D00 到 D0E 的 BE32 CRC，必须交给 decoder 重算。 |

原始三组行和逐行解码位于 `local/host/good-rows.txt`、`unit-q-rows.txt`、`unit-m-rows.txt` 及对应 decoded.json。原 decoder 已逐组实际运行，命令与输出在 `local/commands.jsonl`、`local/logs/decode-*.log`。正式照片抄齐十六行后也用同一 decoder，R01 文案按本报告修正理解。

go/no-go 表用于决定是否继续尝试 full-r3。GO 只表示本项通过，整体放行仍须其它必查项同时通过；UNKNOWN 表示证据不够，不能当成 GO。

| 要判断的事 | 行与字段 | GO | NO-GO 或 UNKNOWN |
| --- | --- | --- | --- |
| resident 已加载 DIAG，列表已发布。 | 拍齐 D00 到 D0F，D00=D1320101，decoder 的 screen_crc=PASS。 | 在相机上看到并成功解码才是设备证据。 | 仍是原生七项或缺行属于 UNKNOWN，不能据此定位是加载、分配还是 UI 失败；先不进入 full-r3。 |
| 最大连续块档位。 | D01 bit0..10 为 96、88、80、72、64、56、48、40、32、24、16 KiB 分配；bit11..21 是各自释放。 | 取成功且释放的最大档；96 成功只说明至少 96 KiB。 | 不是精确最大值。bit24/25 后的零是未尝试；最大仅 72 KiB 也不能替代 78,380 B 精确结果，属于 UNKNOWN。 |
| full-r3 主块在此刻可申请。 | D0A=0001322C，D01 bit22=1、bit23=1，bit24/25 均为 0。 | 直接证明 DIAG 上下文曾成功申请并释放 78,380 B。 | bit22=0 时此上下文不满足，先 NO-GO；不能推断移除 DIAG 后仍失败。bit22=1、bit23=0 是未确认释放，NO-GO，关机重启。 |
| full-r3 文件读取与 CRC。 | D02 四字节依次为 I/O、header、outer、pin；D03=0000E938，D04=D68068F2。 | D02=0 且长度、CRC 全等。 | I/O 非零、gate 非零/255、长度或 CRC 不符均 NO-GO。不能只看 D0A 或申请成功位。 |
| 当前单元与已批准数据相合。 | D05/D06 是正确 unit 名，D07=01510000；D08=D09 且为上表对应 pin。 | 当前单元 pin MATCH。 | 单元未知、cmp 非零、pin 不等或解析失败均 NO-GO。只覆盖当前单元的候选 map/stock，不证明镜头 ROM 全部内容。 |
| 两个缺失 IROM 微调文件的 native open 约定。 | D0B bit23..29 与 bit16..22 按 signed7 解码，期望 A=-1、B=-1。 | 确认本次 raw=-1，支持采用 full-r3 的新只读 open 映射。 | -1 本身不证明 ENOENT；-64 是未测/超出范围，-63 是 close 失败，均 UNKNOWN。非负表示文件已存在，不能按空微调目录解释；意外 -2 也须核对现场。 |
| T/RPC。 | D0B 高两位=1，decoder T=SKIPPED。 | 没有此项 GO 证据。 | 始终 UNKNOWN，不表示 T 值正确、RPC 可用或 W/T 写入安全。 |
| resident 的本次健康状态。 | D0C 按 state/flags/inflight/version 拆字节，通常 03/22/01/20；D0D=0。 | READY、version=32、无 STOP/UNCERTAIN、fault/check_failure=0。 | 异常值先 NO-GO；D0E 只是饱和计数，不能恢复上一次 full 失败原因。 |
| 这组抄录可以用于判断。 | D0F。 | decoder 校验完整通过。 | 缺行、冲突行或 CRC 不符，先补拍/修正抄录，全部结果暂作 UNKNOWN。 |

D02 的 I/O 码为 0 正常、1 open 失败、2 读错或超量返回、3 超过上限、4 close 失败。header/outer 的 255 是未知。pin 为 0 匹配、1 不匹配、2 单元未知、3 布局错、4 读取或边界错、5 前置 gate 未通过。

DIAG 不能告诉我们的事如下。

1. 它不同时持有 full-r3 主块和两个 64 KiB 安装缓冲，不能证明含头 210,108 B 的首次空 IROM 安装峰值可满足。首次采样时 UI 快照还没申请，连 DIAG 自己最终的 17,664 B 保留量也不能当成探测时的完整布局。
2. 它不执行 full-r3 的 bootstrap/init/menu、服务映射、全部语义校验、session work、真实 RPC、T/W、应用配方、设置提交或产品 UI。通过只是允许进入另一次产品试用，不能宣称 full-r3 已加载成功。
3. 它不安装或校验 IROM 引擎双副本，不测试 generation 选择、持久不可读副本、掉电恢复、rename 的现有目标语义，也不会把 DAT 改为 OK。文件未改名在本次 DIAG 中是预期行为。
4. 连续档位和精确申请都受 DIAG 自占堆、碎片和其它原生任务影响。不能把 DIAG 大小简单加回去推导另一次开机的最大块，也不证明多块并发申请、长时稳定性或重启后的同一布局。
5. D0C 到 D0E 只属于本次 DIAG 开机，不能回看旧 full 那次失败；完全没有 D 行时，同一套 H01/UI 输出路径不能给出唯一根因。
6. 28mm 只有主机结果。相机屏幕、真实 fd/文件系统、native free、cache/RAM 执行、真实栈水位及相机生命周期仍未在本轮验收。

待复制包和清单如下。

包目录为 [local/package/SD_ROOT](local/package/SD_ROOT/)，共 31 个文件。29 个文件逐一来自 `firmware/image_v3/local/candidate-v32/candidate/SD_ROOT`，其中 ilaunch3 是唯一获批 v3.2 映像，另外 28 个是该冻结包的官方文件。新增 GXRCE.DAT 为原 DIAG，GXRCF.DAT 是 full-r3 的逐字节副本，绝不是 `firmware/v32_load_diag/local/GXRCF.DAT` 里的旧 full。GXRCF 名称不在 resident 的引擎加载源列表中。

全部 31 个目标与各自源先逐字节比较，再各自计算 SHA-256，全部相等。每个文件的源路径、大小、摘要和 byte_equal 在 [package-verification.json](local/package-verification.json)。以下清单同时保存在 [包的 SHA256SUMS](local/package/SHA256SUMS)，路径相对于 local/package。

```text
8ba2c9097ddcfec5ead739ad24ceef50e76b3f2bd7aefbd352860724150da9cd  SD_ROOT/GXRCE.DAT
0f49317ac8b2609cb268a7951ec263959e8a2fedef818c7d9dd8e530796c7885  SD_ROOT/GXRCF.DAT
b896f40d9f330c4235d99bd6e32963876f9701293530a927672fd6fab7281e65  SD_ROOT/ilaunch0
05b46ee65f4861f2e09e9b7c519cbcc2dffb195158a40c3bb033540b36a98d8c  SD_ROOT/ilaunch3
c9271288f8d395296623a3fe5358b2d83dec8730a89ed138a48ff8a2e8f14a5a  SD_ROOT/ilaunch4
071d207858c5863f72fda37274372ab881d86f6ecd2b1a826ad825f90047e478  SD_ROOT/ilaunch8
0606a54c673e6db2b7708598f4ad7f1bebb93ade534087b1d0e28f7aff8e2de9  SD_ROOT/jlaunch0
951be1c659c85af58ae3e4ce98707c52f0b4514fc2075256854d59f822671673  SD_ROOT/jlaunch3
377e980401d98ba303246f00b4633468ef5affa54ffbc22d24659cc4b1c5e8ca  SD_ROOT/jlaunch4
92554edf413e0090550f192973d0555ee13770cee0764802be209f491f2c424f  SD_ROOT/jlaunch8
4b8c1fd4c24cc7112d49290e94f8d9d75523df395aec7c8fff7ad6ac881b0bf6  SD_ROOT/klaunch0
491f39a619e7d85eeb28ba5c55494ccaa274872b63b2a98169ee14e8f4757bee  SD_ROOT/klaunch3
2dd87ee852b4cea2aff881da9903871a57910da71b27402b1dd29c8dc77fdfe2  SD_ROOT/klaunch4
8fc3ff589088b90a8922a200a077aa3f9daed1dbb5d37992c0642c0b63f69f1a  SD_ROOT/klaunch8
d7b74b86ec829e90dd4b5c1092abc892b90422fd975942f3d4a6b99ea24e24ef  SD_ROOT/l06firm0
6538b919848ee979c3e92ac14a19a29fb8439a1297147c7e0e601afcd135ae8d  SD_ROOT/l06firm3
c0aa8256c682a41ad96277eea075e2c58dca5335dc9bc824e09e78fe69ab10d0  SD_ROOT/l06firm4
1ddd60028a33aa021169014f07abe263099404522097ad3a267d3fe0387a9c69  SD_ROOT/l06firm5
61aae4cfb39ee599eb9647fb72da7b4fd186edcbda298dcb6551fe1fd78d718d  SD_ROOT/l06firm8
05cc3f648f84dc1123dc8207a0edbd796a70bec9a01c36fa43199a5959b78e9f  SD_ROOT/l08firm0
0a4dff6d3be9b9a9b56dfcbd98a2df59efcb31f7d4eaca6b0c3fbdb1641fde44  SD_ROOT/l08firm3
0f787a6fa51893d98bcc778c9e91b2a46ce4fef139828332f418142aa4f36060  SD_ROOT/l08firm4
59a75b3ea1cb7dc71d79349e20d49e809eb1678731111678a7b0ef4c8df0db4d  SD_ROOT/l08firm8
480c5b195c983100a80ca3e3128cd2a0686de0f7b482c025ec23db3f8a78f527  SD_ROOT/nlaunch0
f96c5b84b8fb442706dd694828f51bea4f5f38ea11a7c6881d050d479df9aabf  SD_ROOT/nlaunch3
f2bbc71463d9272adc0da8801bc2997a2c147b0ce33c10aaeac01a506e4c678d  SD_ROOT/nlaunch4
52921ca9311de0f093d5dea1531e2c83876f2bf91d7032cf45f60a50328b26be  SD_ROOT/nlaunch8
3bbc37c6c12c6fedaa190927cdc0594d059919cffee29309ef211122734c6dc5  SD_ROOT/qlaunch0
e487d00b5539aa1e3ca9373829456e00676b37310dc717f0a5bcb5235bac6690  SD_ROOT/qlaunch3
eb2533fdb26ee61cc2135c40fa73a2d6f618bd6f1872f594b256ce4b586aa90b  SD_ROOT/qlaunch4
9d81ca7c1e33df4cd9f0c5532b22ad55b1c11a492707839705ab4e69f9019e45  SD_ROOT/qlaunch8
```

操作说明只有 [USER_GUIDE.txt](USER_GUIDE.txt) 的五行，恢复使用用户自己的 Stage2l 卡 A 和同一种加号键加播放键刷法。这里交付的是工作盘上的待复制包，没有向相机卡复制，也没有刷机。

复跑从项目根目录开始。review.py 所有写入都受本 review 目录约束，使用既有工具，不调用原 build.py/verify.py 的写入入口。

```sh
python3 -I -B research/review_v32_diag/review.py snapshot
python3 -I -B research/review_v32_diag/review.py inspect
python3 -I -B research/review_v32_diag/review.py rebuild
python3 -I -B research/review_v32_diag/review.py host
python3 -I -B research/review_v32_diag/review.py safety
python3 -I -B research/review_v32_diag/review.py package
python3 -I -B research/review_v32_diag/review.py audit
python3 -I -B research/review_v32_diag/review.py finalize
```

本目录 `.gitignore` 为 `/local/`。根 [SHA256SUMS](SHA256SUMS) 覆盖报告、指南、脚本、忽略规则及全部 local 证据和包文件，按惯例不含清单自身。最终 [scope.json](local/scope.json) 确认冻结的 324 个只读输入均未变化。共享仓库同时新增 `research/status_report_20261024/report.html`，本轮未触及该文件，保留并记录了这项 Git 状态差异，没有声称整个仓库状态不变。原始命令和失败均保留在 local。
