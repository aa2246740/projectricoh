不可以上卡

本结论针对 2026-10-26 的固定候选 `firmware/lut_p0_timing/local/staged/GXRCE.DAT`，52,060 B，SHA256 `5a4f28efcf15ff4273d97b167c892c1cbab2ba3cd6d8804362afb246a9b931c5`。发现三个 P1 阻断项。两条参考计时失效路径会产生完整、ERROR=0 的错误校准日志；整个 UI 发布路径也不满足任务明确要求的“不写任何 native structure”。

独立重建与待审 DAT 逐字节相同。原有 113/114 主机流程、安装拒绝、M32R 回放均通过；这些通过项没有覆盖下面两条校准反例。全程只做主机工作，没有网络、存储卡、相机或相机 USB 操作，没有修改候选、官方文件、卡备份及其它 worker 的目录。写入限于本审查目录。

下文 `P/` 指 `firmware/lut_p0_timing/`，`S/` 指 `firmware/engine_v35_publish/candidate/engine_services/`，`R/` 指 `firmware/resident_v34c/resident/`。不带此前缀的证据文件均在本审查目录。行号针对本轮冻结文件。

## P0 / P1 / P2

- P0：未发现可由本候选触发的 IROM 安装、机身刷写、配方写入或照片缓冲改写路径。
- P1-01：首次页面发布失败后，下一次成功显示会使用零参考起点。`P/probe.c:157-160` 先把 NEW 改成 REFERENCE，再调用可能失败的 `publish()`；失败返回时没有撤销 phase。下一次打开时 `start=false`，因此不会再执行 `reference_start=p0_tick()`。而 `p0_menu` 的外层 reply 仍为 OK，`R/resident.c:69-70` 不会因此退役引擎。独立测试只让第一次 1,968 B UI 快照分配返回失败，随后恢复正常分配；第二次页面在 tick=100000 显示，用户量到 tick=110000 的 10 秒，P0 却接受 start=0、delta=110000、error=0。继续完成 72 条样本后，原解码器接受 `complete=true`，把模型中 1000 Hz 的时钟算成 11000 Hz。见 `adversarial.c:66-79`、`first-publish-retry.BIN`、`first-publish-retry.json` 和 `adversarial-results.json`。应在发布成功并取得有效起点后才提交参考计时状态，发布失败不得保留可确认的 REFERENCE。
- P1-02：参考页用 MENU 退出再打开，会把离开页面的时间算进新秒表区间。`P/probe.c:175` 只返回 CLOSE_AND_PASS，没有废弃参考起点；`P/probe.c:157-160` 又只在 NEW 时取起点。独立执行真实 H07 MENU 路径，离开 60000 ticks 后重开，再在页面量 10000 ticks。P0 接受 delta=70000、error=0，完成 72 条样本的日志被原解码器判为完整，tick_hz 偏大 7 倍。见 `adversarial.c:55-64`、`reference-reopen.BIN` 和对应 JSON。`P/REPORT.md` 虽要求中途退出后关机重来，界面和状态机却仍会给出可通过校验的结果；`P/USER_GUIDE.md:5-10` 也没有这条中断规则。应在非确认退出时使本次参考失效，或在重开时明确开始一个新的参考区间。
- P1-03：整个探针会写 native UI 结构，违反本次硬边界。`P/probe.c:88` 调用 UI_LIST 后，`S/services.c:196` 写 `0x2022F725/726` 两个游标字节，`:201` 写 `0x2022F5A8` 的列表指针和 `0x2022F5AC` 的行数。官方 ilaunch3 文件偏移分别为 `0x1E4925/26`、`0x1E47A8`、`0x1E47AC`。仅执行 H01、尚未继续原生构造器，独立差分就看到 descriptor 的四个字节改变，见 `adversarial.stdout`。游标原值恰为 1 时差分不变，但源码仍执行 store。MENU 退出又由 `R/shared.c:83-84` 写回这些原生字段。`rv_native_seed` 本身只写私有副本，不能据此声称整个 P0 不写 native。没有证据显示这些已审 UI store 会破坏 IROM，但它们确实越过任务边界。任务方若本意允许既有 UI 发布与恢复，应明确这四个字段的写入白名单；在没有该例外时，当前方案不达标。
- P2-01：批次没有按设计从小计数开始。`research/body_lut_r2/REPORT.md:150` 要求先小计数，`P/probe.c:3,116-131` 与 `P/vectors.py:6` 却先跑 4096，再跑 4、64、512；首次实际 LUT 样本已是最大长度，后五轮一个回调还会跑预热加计时共 8192 对。它有固定工作量上限，但最慢设备会在取得小批次依据之前承担最大回调。建议先小后大，或先做小批次准入，再执行正式交错 schedule。这里没有推断实机会挂起，也没有把固定对数当作毫秒上界。
- P2-02：卡 B 的旧包和回退基线交代不足。`P/USER_GUIDE.md:5,10` 只说留存旧同名文件、删 DAT 回到产品，没有区分“卡上有 114 DAT/OK”和“IROM 已装 114”，也没有说明旧产品 DAT 不应在测试结束后自动放回。P0 的确不调用 DAT→OK；旧 OK 留在卡上不会让 P0 自己安装。但是若用户恢复旧产品 DAT，就重新进入产品安装流程，可能升级仍为 113 的 IROM，或遇到已有 OK 的交付冲突。卡 B 还留有刷机包，指南应明确隔离这些文件，普通电源启动，不把更换探针变成再次刷机。认可的六步流程见文末。

两个错误校准案例的 tick 均为主机合成值，用于证明状态机和解码器会接受错误区间，不是相机频率测量。这两份日志的 LUT 分辨率仍不足，解码器没有输出 ns/对；若换成分辨率足够的实测 LUT 数据，相同校准错误会把 ns/对缩小到真实值的 1/7 或 1/11。

## 已核实的产品安全与回退

`P/build.py:81-88` 写 generation=1、tag=`LUTP0001`；头中 body ID 是官方基线 `da1980e9…cdf7`，不是修改后运行映像的 SHA。独立核对了实际运行映像 `24b1de0e…1f72`、resident build `eb96410f…a941` 和 ABI `b6353e4de1c89bd37c08ba6734efc8e0`。resident 的 payload、root pins 和所有 hook 补丁均与运行映像匹配。完整身份见 `artifact-audit.json`，重建记录见 `run.stdout`、`run/manifest.json` 和 `run/audit-results.json`。

不可安装的依据不是 generation=1 本身：

1. P0 的入口表只绑定探针函数，初始化只申请 CAP_UI，调用端只使用 UI_TEXT/UI_LIST。最终 ELF 没有 `ps_install`、产品 `ig_menu/ig_init` 或 `ig_control_off`。没有可达的 IROM、GXTS/GXLS、CTL、recipe、RPC8、rename/delete 或 GXRCE.OK 操作。服务库包含通用接口，不能仅靠字符串是否出现判定可达副作用。
2. 真实产品 gate 在 `firmware/resident_v34c/acceptance/containers/product/src/firmware/card_container_v2/gate.c:64-69` 要求模块计数与目录字段为 3，且头部 228..255 为零；P0 的相应计数为零、tag 非零、产品数据段缺失，实际先以 VERSION 拒绝。真实 `ps_install` 返回 VERIFY，没有安装、写入或交付标记。
3. 在仅用于负向测试的 envelope-only verifier 下，真实 `panel_store.c:362-365` 仍对有效 IROM 的 113、114、115、UINT32_MAX 返回 CONFLICT。115/MAX 只是内存头部夹具，不是已安装产品证据。不能把低 generation 解释为对任意未来安装器或空白/无效 IROM 都生效的不可安装标志。

`R/loader.c:84-106` 先完整尝试卡 DAT，随后才由 `:55-58` 比较有效 IROM A/B 的 generation。因此卡上的 gen 1 会优先于 113/114；它不会因为更旧而被忽略。删掉卡 DAT 后，loader 不查 GXRCE.OK，也没有其它 P0 存储源：

| 主机夹具 | 选择结果 |
| --- | --- |
| A/B 都是 113，无 DAT | A/113；A 缺失时 B/113。 |
| A/B 都是 114，无 DAT | A/114；A 缺失时 B/114。 |
| A=113、B=114，无 DAT | B/114。 |
| A=114、B=113，无 DAT | A/114。 |
| A=113、B=114，卡有 P0 | 卡/1。 |

113 真实夹具是 64,816 B、SHA `6cb63aa47c18086f5ade681ffe4dc97378394ff7a65c0688d19b3880d804c707`；114 是 65,088 B、SHA `132e56389808970b0db8a8c4a359c46f18f0fb2423ecbc11f671d18df19a49a5`。两套完整流程及额外混合 A/B 测试均核对原文件逐字节不变，见 `run/host-results.json`、`mixed-loader.stdout`、`mixed_loader.c`。产品入口只是观察 loader 选择的 double，没有在主机执行完整 113/114 产品，也没有证明当前相机实际装的是哪一代。

持久副作用仅限覆盖或新建卡上 `GXRBX0/1.BIN`。原有日志也可能被轮换覆盖，必须先备份。`blackbox.c:93-116` 的实现除了 include 未变，保留卡 ID、CRC、A/B 代次及写后读回。主机文件系统替身禁止其它 create/write 和任何 rename/delete。P0 没有读取 CTL，因此 CTL OFF 不能作为探针的停用开关；停用是关机后移走探针 DAT。

“删 DAT 回到原产品”只在原 IROM 副本仍有效、没有另行安装产品且冷启动的前提下成立。若原来装的是 113，回来仍是 113，不会自动变成 114。RAM 中会保留本次私有堆块直到冷启动；显示期间还存在 P1-03 的原生 UI 字段改动，不能把这些也称为零写入。

## 启动、菜单、中断与内存

P0 不新增启动 hook，不在电源启动时自动测速；`R/hooks.c:61-67` 在 H01 菜单入口才加载与调用它。参考阶段只保存起点和等待按键，没有 UI 忙等。每次 H08 只生成一条样本，最大计时 4096 对；预热另有最多 4096 对，随后返回菜单任务。

`P/timing.S:4-22,29-44`、内核没有关中断操作。真实 resident 在调用引擎前恢复原 PSW，UI 服务仍有既有短临界区；批次在 `P/probe.c:118,137` 检查 IE 位。主机与指令回放保住了 IE、callee-save 和 SP；没有模拟真实 IRQ、调度抢占或 watchdog。

scratch、P0State、wire、glyph、seed 和 UI snapshot 都在私有分配内。目标布局为 image+BSS 72,032 B，P0State 19,964 B，scratch 16,384 B；主块 request 79,536 B，加块头、608 B loader workspace 和 1,968 B snapshot，已知保留量 82,148 B。loader workspace、主块及已发布 snapshot 按既有 resident 策略留到冷启动，不能承诺菜单退出立即归还。独立连续退出/重开 1000 次，没有新增分配，见 `adversarial.stdout`。内核指令回放栈深 92 B，不代表整个菜单任务栈峰值。

`P/probe.c:128-133` 的计时窗只包住空调用、减计数或 LUT。重填、预热、CRC、页面发布和黑匣子 flush 都在窗外；参考终点在 flush 与关页之前取得。黑匣子原生 I/O 本身仍可能等待。没有实机毫秒上界，不能保证启动、首次加载、页面绘制、长批次或原生文件调用绝不挂起。正常 MENU 退出的 descriptor/cursor 恢复在两套夹具中通过；参考阶段 MENU 退出的计时状态错误单列为 P1-02。

## 真实 native 顺序与剩余手设值

本轮确认 H01=`0x2028709C` / file `0x23C29C`，H02=`0x202870A8` / file `0x23C2A8`，type=5 的 store 到 `0x2028712C` / file `0x23C32C` 才发生。首入 type 0/4/9、table=`0x2022F56C` 时，新 `S/native_seed.c:8-14` 构造私有 type5；旧 seed 在同一输入拒绝。capacity=256 来自真实 `S/api.c` 初始化，不是原生菜单临时分配的属性。

原生 clear=`0x201C0730` / file `0x175930`，随后 push=`0x201C07E0` / file `0x1759E0`。执行官方存储指令片段后得到 count=1、tag33、state=`0x2022F71C`，后续 type5 入口也通过。见 `run/native-order.json`、`run/seed-replay-results.json`。seed 的九个最终指令用例核对 236 B 私有内容与哨兵，state/descriptor 未被 seed 写入；这不覆盖 UI_LIST 的原生写入。

独立重编的八个对象为 services、api、shared、runtime、crc、bridges、mark、native_seed；每个 allocated section 及 relocation section 与 114 已审对象逐字节相同，复制源文件也逐字节相同。完整 archive 因编译副本路径的非分配 LTO 记录而不同，不能宣称整个 `.a` 相同；本次使用 ld、不走 LTO，最终 P0 DAT 又与被审件完全相同。见 `run/service-build.json`、`run_review.py`。

剩余主机赋值与模型边界如下，没有把它们当成实机观测：

| 位置与值 | 分类及用途 |
| --- | --- |
| `P/native_model.py:12-14,95-103` 的 32 B state、72 B descriptor、table=`0x2022F56C` | 主路径输入来自官方映像，并核对运行 body 的相关字节。type 0/4/9 由官方 writer 指令片段写入；具体首入 type 仍是覆盖参数。 |
| `P/native_model.py:79-90,101` 的 part=2、clear 参数、parent tag32/state、tag33/state 和 cursor 参数 | 主路径边界模型。存储片段是真字节，但父视图、API 参数、完整公共构造器、图形与调度没有全机执行。 |
| `P/host_checks.c:139-144` 的 PSW=0xC1、堆边界/allocator header、UI mode=8/flags=56/layer=2、jlaunch/1.51/live、S 指针与 4096 B 哨兵 | 主路径 native 替身。堆边界用于分配检验；S 哨兵用于发现设置写入。context=0、SD ID={1,2,3,4}、native 字形转换和 tick 每次加 7 也都是替身。capacity 256 则由实际服务代码设置。 |
| `P/host_checks.c:148-149,182-183,270,277-280` 的 caller、keep、按键及每次直接写入的 native cursor | H07/H08 入口投影；证明回调行为，不证明物理键完整送达、长按连发或滚动外观。 |
| `P/host_checks.c:249-252` 的 type=5、table=`0x2022F000`、cursor=1、view state；`P/seed_replay.py:21` 的同类正例 | 已标明的旧 r1 兼容回归，未作为主路径首入证据。 |
| `P/host_checks.c:241-247` 与 `P/seed_replay.py:19-33` 的未知/零 table、capacity 235/236、哨兵、固定 context/private 地址 | 拒绝/边界测试。236 是最低接受容量正例；type5+旧 table 是兼容正例，其余按用例断言拒绝。 |
| 安装测试的 IROM generation 115/MAX；tick 回绕/无效区间、BX 创建失败；本审查的 UI 分配失败和页面离开时间 | 明确的负向或故障注入。实际 DAT 113/114 没有被改写；所有修改只发生在 host 内存夹具。 |

## tick 方法与 LUT 保真度

独立从官方映像提取完整 `0x2005F164` / file `0x014364`，核对它调用 `0x0500C584` / file `0x3CBB84` 的 trap，随后取结果低 word 返回。见 `tick-complete.disasm`、`tick-trap.disasm`。`P/timing.S:5-21` 保存 r8..r13/LR，与既有 native 桥一致；回放还令 native double 故意破坏这些寄存器，再检查恢复。

参考与样本差值按 uint32 做减法，小于 2^31 ticks 才接受，参考还要求非零；单次跨 wrap 用例通过。这个门仍依赖真实间隔小于 2^31 ticks，不能自行证明未知 tick 的单位、稳定性或休眠行为。三类调用分开记录，四种 trip、六轮、轮换类别共 72 条；CRC 被比较并写进样本，没有被编译器删除。后五轮先跑 LUT 再重填属于明确的预热协议；首轮只能叫未显式预热，不能叫保证冷 cache。

`P/decode.py:42-67` 用有效参考求 `tick_hz=delta_tick/seconds`，分别拟合 empty/decrement/LUT，主结果取 LUT 斜率减 empty 斜率，再求 ns/对。完整批次净时间不足 16 ticks 或净斜率非正时只输出 inconclusive。它保留原始样本、范围、首个全长遍历和五次预热全长遍历，符合 §5 的 scratch 外推范围；没有测 CPU MHz 或照片总保存延迟。该公式本身成立，前提是先修复 P1-01/02 的参考有效性。

内核符合 §5：完整 17³×3 大端 u16 Q8.8 表共 29,478 B，坐标 256×4=1,024 B；Y 为最邻近轴，无像素内除法，稳定 tie 顺序为 Y/C2/C3。255 对应 cell15、frac256。每个像素独立插值四顶点，然后按 `(A_C0+A_C1+65536)>>17` 合并共享色度，最后 clip。单通道 A 在 0..16,776,960 内，共享和与舍入也远低于 int32 上界，没有由 u16 极值导致的有符号溢出。

先重跑候选的原始回放，得到原报告相同的 16,384 对与四个 CRC。另写 `independent_kernel.py`，不调用候选的 transform/pixel/coordinates 参考函数，以显式六种排序、直接重心加权和独立坐标计算再次回放最终 DAT 对应机器码。混合/身份/极值各 5,120 对，独立随机全表 1,024 对，共 16,384 对全部逐字节相同；身份结果等于原输入。每对实际观测到 24 次节点半字读、4 次坐标 word 读、一次输入 word 读和一次输出 word 写。四份输出字节、SHA/CRC 及结果保留于 `*-output.bin`、`independent-kernel-results.json`。数值参考是另写的；指令语义解释器仍复用冻结的有限 M32R 模型，没有伪称第二个硅片模拟器。

## 尚未证明的现场条件

- 当前机身的 IROM A/B 实际是哪一代、是否有效，必须由后续无卡 DAT 的基线冷启动及日志确认；卡上 114 DAT/OK 的存在不足以证明。
- 首个 H01 当时的 type/table、父视图与 part2 参数、真实按键送达及长按连发、LCD 首次可见与 reference_start 之间的延迟，尚未现场记录。
- native tick 的单位、单调性和相同电源状态下的频率、IRQ 行为、菜单任务总栈余量、物理堆余量、最慢回调时间、watchdog 及真实卡 I/O 等待，没有由主机测试证明。
- 私有 scratch 的 cache/内存访问不能代表主图 DMA 同步、JPEG 编码、保存延迟或颜色合格性；本件也没有测 33³。

## 认可的卡 B 流程，最多六步

当前固定 SHA 的 DAT 不获准执行下列探针步骤。P1 修复、原生 UI 写入边界明确并复核新 SHA 后，采用以下流程；本报告没有代用户操作卡。不得把旧文件重新命名就当作修复件。

根目录需要隔离的旧包是 `GXRCE.DAT`、`GXRCE.OK`、`GXRCE.CTL`，以及上次刷机的 `ilaunch*、jlaunch*、klaunch*、l06firm*、l08firm*、nlaunch*、qlaunch*、DEEPTBL*` 中实际存在的文件。移到电脑备份目录，不在卡根改成另一个会参与启动的名字。照片目录保留，卡 A 不动。移走 OK 是操作隔离，不是因为 P0 会读取或改名它。

1. 关机，保持 50mm 连接。把卡 B 上述旧包及 `GXRBX0/1.BIN` 备份到电脑，再把旧包移出卡根；不格式化、不改照片。
2. 暂不放探针，正常电源开机并打开 ADJ 的 Image Settings，记录原产品表现与新日志，再关机。这是后面要回到的 IROM 基线；它可能是 113，也可能是 114。不要按刷机组合键。
3. 只把修复后、重新审查通过的 P0 文件放到卡根，文件名为 `GXRCE.DAT`；核对该次批准的大小和 SHA，安全推出卡。50mm 保持连接，普通电源开机，打开同一配方页。
4. 看到 `P0 REF` 时启动手机秒表，留在该页约 10 秒，按 OK 同时停表并记下实际秒数。页面关闭后重开同一页。若中途退出、休眠、没看到探针页或首次显示失败，关机后重新开始，不沿用这次计时。
5. 按住向下键，若不连发就重复点按，直到 `P0 LUT17 DONE`。记录 `REF DT`、`SAMPLES 48/48 hex` 即 72 条、`ERROR 00000000`、`FLUSH 00000001` 和秒表读数，再按 MENU。错误非零或 FLUSH 为零就不采用结果。
6. 关机，把两份 `GXRBX0/1.BIN` 和实际秒数交回主机解码，删除卡根的探针 `GXRCE.DAT`，确认没有另一个产品 DAT 留在根目录，再正常冷启动核对第 2 步基线。旧产品 DAT 留在电脑，不自动放回触发另一次安装。若卡住，先关机移走探针 DAT；仍不能恢复时，沿用已验证的卡 A Stage2l、50mm 连接、“+ & 回放键”机身恢复路线。本轮没有重测该恢复入口。

## 可重跑证据与冻结检查

所有 Python 均用 `/usr/bin/python3 -I -B`。候选模块只以只读输入导入，输出路径在内存中重绑定到本目录；C 编译仍读原冻结源码，不对候选作文件修改。原始命令及 stdout/stderr 在 `run/commands.jsonl`、`run/logs/`，附加测试结果也有独立 stdout/stderr。复跑命令：

```sh
/usr/bin/python3 -I -B research/review_lut_p0/run_review.py build verify native_evidence replay seed_replay audit
/usr/bin/python3 -I -B research/review_lut_p0/run_adversarial.py
/usr/bin/python3 -I -B research/review_lut_p0/run_mixed_loader.py
/usr/bin/python3 -I -B research/review_lut_p0/independent_kernel.py
/usr/bin/python3 -I -B research/review_lut_p0/artifact_audit.py
/usr/bin/python3 -I -B research/review_lut_p0/review.py
```

初始盘点清单保留于 `protected-inputs.json`，共 6,623 条，其中误纳入 33 个并行 bridge 下载缓存文件。正式冻结范围是其余 6,590 个审查输入，覆盖指定五个 firmware 树、Ricoh 官方文件和本次设计/114 审查依据；明确排除 `decisions.tsv`、并行 worker 的工作目录与 `artifacts/downloads/bridge_public_r1/`。第一次范围误报只有 bridge 新增下载，没有任何基线文件变化；第二次是过滤 live 缓存后引起的清单范围差异。封存时另发现三个新建的 GR IV 样本下载，同样没有任何已冻结文件变化。这些新文件没有参与任何本次测试。诊断以 `guard-dev-error-*.json` 保留；下载目录按初始文件清单逐项保护，避免把并行新增资料误当作输入变化，五个冻结 firmware 树仍检查新增、删除及字节变化。修正的是审查脚本，没有重置基线、没有豁免任何已有输入漂移。最终重新核对这 6,590 项通过，详见 `frozen-verification.json`。`SHA256SUMS` 覆盖本目录除自身外的所有文件。
