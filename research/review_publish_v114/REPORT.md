可以上卡

仅放行本次固定 SHA 的 gen 114 DAT，供先 50mm、后 Mount 的一次实机验收。未发现阻止该容器更新的 P0/P1。发现三项 P2，分别涉及失败模式表述、原测试的视图构造投影，以及首轮诊断的采集步骤。没有相机、卡、USB 设备或网络操作；所有写入均在本目录。实机显示、原生调度并发和掉电持久性仍未由本次 host 审查验证。

下文 `C/` 是 `firmware/engine_v35_publish/candidate/`，`R/` 是 `firmware/resident_v34c/resident/`。本目录的脚本、反汇编、JSON 和原始 stdout/stderr 是可重跑证据。

## 发现

- P0：未发现。
- P1：未发现。
- P2-01：不能把所有 snapshot guard 拒绝都称为“原生列表完全可用”。`C/host_v34c.c:156-170` 将 table 置零后，只执行 type writer 就结束；候选 `REPORT.md:93` 据此描述了更强的可用性。独立继续到原生行消费者，`0x201FDD44` 从 state+4 取 table，`0x201FDD4C` 随后读取 `table+5*12+4`。table=0 时读取地址为 `0x40`。文件偏移分别为 `0x1B2F44`、`0x1B2F4C`，见 `rows.disasm:21-23`、`native_flow.py:126-145` 和 `native_flow.json` 的 consumers。应将保证收窄为“引擎拒绝后不破坏原生状态；原生状态本身有效时可继续原生菜单”。这不是本次新增的坏指针，也没有证据表明正常入口会产生零 table，故不作为本次容器的阻断项。
- P2-02：首帧测试的视图栈投影与真实构造链不同。`C/entry_projection.inc.c:28-33` 直接在第二槽写 tag 33 并把 count 设为 2。官方构造器实际调用 `0x201C06F4`，其中 `0x201C0730` 先清零 part 2 的 count；`0x201C07E0` 再压入 tag 33，得到 count=1、首槽 state=`0x2022F71C`。对应文件偏移 `0x175930`、`0x1759E0`，见 `view.disasm:106,150,188-194`。原测试不能独自证明原生构造链。本次补跑了 128 个原生延续用例，并在真实 count=1 的模型下复核 Fn2、退出和 snapshot 保留，均通过。运行时代码接受 count 1/2，不依赖错误的 count=2 投影。
- P2-03：黑盒尾部保存最近一次 seed，不保证保留第一次 H01 seed。`C/containers/product/blackbox.c:73-82` 每次覆盖同一 64 B；移动列表游标又会经 `adapter.c:457-465` 调用 list_bind。先滚动再取日志，通常只能看到 native 已写成的 type 5，无法回答第一次 H01 的 type。首轮应打开 Image Settings 后不移动、不按 Fn2，直接 MENU 退出并取日志。独立 C 用例验证该步骤记录 type 0、没有 RPC；移动后再退出记录 type 5，见 `extra_cases.inc.c` 和 `host/independent-*.stdout`。Fn2 会先应用当前行配方，MENU 只丢弃面板草稿，不撤回这次选配方动作，不能把它当作无副作用的取日志键。

## 1. 根因和原生流程

旧 seed 的时序缺陷成立，现场归因仍是有静态及重放支持的推断。两份真实 gen 113 日志只证明失败在 seed、没有进入行文本循环；没有记录旧 type/table/capacity，不能把现场具体 type 写成已观测值。`logs_decoded.json` 保留两份现场解码和四份独立 host 日志。

| 对象或阶段 | VMA / ilaunch3 文件偏移 | 核对结果 |
| --- | --- | --- |
| 状态和 table 初值 | `0x2022F71C` / `0x1E491C`；table 字段 `0x2022F720` / `0x1E4920` | 官方映像 32 B 状态的 type 初值为 5，+4 为 `0x2022F56C`。已刷 body 的这些字节完全相同。运行中的 type 随前一个列表变化。 |
| type-5 descriptor | `0x2022F5A8` / `0x1E47A8`，count 在 `0x2022F5AC` / `0x1E47AC` | 正好是 table+5×12，names=`0x2022D610`、count=7、hidden-map=0。它是已有的静态结构。 |
| H01 | `0x2028709C` / `0x23C29C` | 同步进入 resident，再进入 engine menu/list_bind/seed；此时尚未运行下面的 type writer。 |
| H02 | `0x202870A8` / `0x23C2A8` | 既有 H01 skip 把 cursor 放入 r0；H02 把它放入 r8，跳到 `0x20287118`，绕过原生七项枚举。`R/hooks.c:61-69`、`R/build.py:82`。 |
| type writer | `0x20287118..0x2028712C` / `0x23C318..0x23C32C` | r4=5，`stb r4,@r1` 才写 native type。见 `image.disasm:46-51`。 |
| 原生公共构造 | `0x2028579C` / `0x23A99C` | 根据 `0x205D9BCC` 的五个项写 state+13..17，并写 `0x205D9C78`。它不重写 table 指针，也不覆盖 type-5 names/count。见 `common.disasm:38-102`。 |
| 原生后续状态 | `0x2028714C,0x20287158,0x20287164` / `0x23C34C,0x23C358,0x23C364`，以及 `0x20285724` / `0x23A924` | 原生写 state+11/+12，并从 r8 写两个游标字节。H02 保住的 1..8 在全部延续用例中未被改成原生七项行号。 |
| 原生视图提交 | `0x202871A4` / `0x23C3A4` | 调 `0x201C07E0`，提交 tag 33、state=`0x2022F71C`。主菜单实际消费全局 native state。 |
| 行消费 | `0x201FDD44..0x201FDD4C` / `0x1B2F44..0x1B2F4C`；`0x201FE408..0x201FE412` / `0x1B3608..0x1B3612` | 按 type×12 读 descriptor、读 count，再按 names→ref→glyph 读标签。8 行遍历实际取到 8 个 glyph 指针；11 行 Fn2 列表按原生滚动规则取 9 个可见行，全部游标均未越界。 |

table 是映像初始化的指针，不是 `0x2028712C` 才创建的对象。本次构造链没有 table 字段 store。`0x202858A0` 的公共描述符更新器从 state+4 取表，更新表内记录；不会改 state+4 本身，见 `common.disasm:103-115`。这不是对全程序所有别名或 DMA 写入的排除证明。

capacity 由 engine 自己写。`C/engine_services/api.c:15-26` 在 context 初建时写 `ui_state_address=state_address+6144` 和 `ui_state_capacity=RV_UI_CAPACITY`；`R/resident.h:33-35` 将其定义为 256。它不是 native UI 此刻才分配的容量。独立 C 入口实测为 256，交叉编译布局也重新核对了这一分配的边界。

因此，正常初始化下 table=`0x2022F56C`、capacity=256，旧 seed 剩下的失败项就是 type!=5。另两项在 context/内存损坏或布局漂移时也能失败，gen 113 的现场日志无法直接排除它们。gen 114 保留了容量和表范围检查；只在非 type5 且 table 精确匹配已知布局时允许新路径，见 `C/engine_services/native_seed.c:8-14`。

私有快照不是“原生构造完毕状态”的逐字节副本。它在 H01 先复制 32 B 状态和前六条 descriptor，只把私有 type 设为 5；native 后面还会更新 flags、ADJ 映射和游标。这不构成当前实现中的分歧：首次 list_bind 只发布 names/count 和游标，未把原生 view 指向这个早期 snapshot；原生构造器随后提交自己的全局 state。Fn2 的 UI_LIST 会再次从当时已更新的 native state 执行 ui_seed，覆盖旧 flags，见 `services.c:154-163,185-202`。独立用例在原生字段中放入不同值后验证 Fn2 得到新值，见 `extra_cases.inc.c:29-36`。未发现后续 native 重写八行 descriptor、首帧游标丢失或标签布局不一致。

本次对官方原始字节重新 objdump，并逐段核对实际 body。构造器区仅 H01/H02 是既有 hook 差异；common、view、draw 区无 body 差异。H05 的现有 replacement 也按 manifest 对照了 body。证据在 `artifacts.json`。原生延续的 hook 结果、类别探针、图形底层、调度和中断仍是明确列出的模型边界，未冒充完整固件执行。

## 2. 写入范围和生命周期

新 seed 和诊断本身不写 native state、table 指针、descriptor 或视图数组。它们写私有 236 B 和已有日志尾部 64 B，BSS 未增加。context 的 address/capacity 先由 `api.c:28-37` 的 lease/range 检查验证。独立测试覆盖 capacity 236..256，236 B 之后的哨兵未被改写；坏输入拒绝时私有目标也保持原样。

发布阶段确实会在 type5 writer 之前写 native 结构，不能概括为“整个新路径都不写 native”。`services.c:195-201` 写 `0x2022F725/726`、descriptor 的 names/count。这些位置已经由映像初始化，尚未执行的是本次列表的 type5 构造，不是整个结构尚未存在。原有字段宽度分别为 byte/word/byte；descriptor 的 hidden-map 保持 0。独立 H01 差分检查只允许这两个游标和 descriptor 的五字节变化，状态其它字节、其它 descriptor、整个视图区均未变化。

视图数组不在 ilaunch3 的文件承载段内，不能给它虚构一个静态文件偏移。native `0x201C05F4` / file `0x1757F4` 把 `0x205A279C` 写入 `0x205A27D8`；`0x201C0730` 清 part 2 的 count；push 根据 count 写 8 B 项并增加计数。固定数组到 count `0x205A27D4` 有 56 B，受支持的两项只占 16 B。engine capture/view 发布要求固定数组和 count 1..2，见 `R/shared.c:61-72`、`services.c:206-222`。本次新增代码未写 `0x205A27D8`。

Fn2 才把 top.state 改到独立 1,968 B snapshot。UI_LIST 对 lease、字符串、零 details、行数、cursor 均继续检查，见 `services.c:165-201`。退出按 `R/shared.c:74-94` 先恢复原生 names/count/cursor，再撤回指向 snapshot 的 tag-33 指针。snapshot 不释放，也不回收给下一 engine 会话；`R/resident.c:38-46` 的 retire 同样保留已发布内存。独立检查正常退出、真实 count=1、随后 retire，snapshot 仍属于有效分配。未发现这条路径的 use-after-free。

诊断区是 log+2432..2495。环形事件在 384..2431，日志总长 4096，state 总长 6144、日志从 state+2048 开始，因此两者不重叠也不越界。诊断只读固定地址，不跟随 table 或 view 中的未知指针。实际最终 M32R 指令的 21 个用例也重新运行，见 `packed_machine/results.json`。

## 3. 失败和启动风险

容量不足但 native table 有效时，seed 在 UI_LIST 前失败，resident 不选 H01 skip，退役本次 engine，native 构造器继续得到七项 descriptor。这与当前 gen 113 的拒绝路径一致。若 native table 自身无效，不能承诺 native 可用，见 P2-01。

没有新增机身、冷启动 hook、IROM 文件名或启动阶段 native 写入；本次原生写入发生在菜单发布路径。正常布局下未复现菜单卡死、指针越界或快照释放后使用。真正 UI task/IRQ/快门并发、任务栈物理余量和 LCD 渲染仍未执行，不能据此保证相机绝不会黑屏绿灯。CTL OFF 只在 engine bootstrap 运行时生效，不是 H01 之前任意启动故障的救援机制，卡 A 恢复路径仍应保留。

## 4. 功能回归

独立重编 38 个 C 编译单元，使用 ASan/UBSan，复跑原有 259 个场景。结果及每个进程的原始 stdout/stderr 在 `host/`；针对本次改动另加三单元的写入差分、快照保留、首个日志、旧 OK 冲突检查。其它原生字节重放为 128 个构造延续、3 个 descriptor 消费、19 个完整行迭代。均以各自实际证据范围计数，不合并称为相机验收。

| 要求 | 审查结果和边界 |
| --- | --- |
| 50mm/Mount 八个真实行、28mm 原生 | C basic/first/seed/update 和新增原生行遍历通过。50mm/Mount 为 8；28mm 在 `adapter.c:449` 返回原生，保留原 descriptor 的 count=7，不把它直接说成七个可见项目。未看实际 LCD。 |
| Posi 01、Nega 02、03 Standard-mode mono | engine core/panel、所有 48 槽 552 B 展开 entry、记录及 effective-rows 与 113 一致。原数据部分仅 bank generation/CRC 和目录偏移变化。实际颜色与拍摄未验收。 |
| remember-last 只定位、重开对齐 live recipe | `eng_core.c:320-326` 在未 commit 时只读 GXLS 定 cursor；已 commit 时从 current.slot 定位。first 的 9×256 输入、history 和 daily 通过，菜单进入/移动没有 RPC、S 写入或 preview。没有将模型游标等同于已观察到的 LCD 高亮。 |
| Fn2、OK 保存、MENU 丢弃 | basic、store-fault、publish-failure、daily、history 及 count=1 的独立 Fn2 路径通过。Fn2 的首次选配方与面板草稿是两个动作。 |
| IROM 防格式化 | update114 精确使用 113 IROM + 114 DAT，验证旧 113 保留、114 写另一副本、DAT→OK，随后移除卡产品文件仍选择 IROM 114。文件系统为 host 替身，未声称真实 IROM 已写入。 |
| 重启后完整上次或纯 04 | history/daily 验证默认纯 04、记忆仅定位、显式应用后完整配方和 tweak。重启由替身重置模块 stock 并保留模拟 S/IROM；这一 native 开机行为仍是现场假设。 |
| ISO100 | iso 的六种相邻字节、neighbour、RPC faults、T gate 均通过。相关运行期代码和数据没有本次修改。 |
| 黑盒 | 四份独立 host 日志及两份冻结现场日志由新解码器校验，旧日志 seed_inputs=null；新诊断最终指令重放精确通过。slot 轮换、CRC、日志故障套件保持通过。 |

运行期 C/H/S 相对 113 仅五个文件变化：native_seed.c、services.c、adapter.c、blackbox.c、blackbox.h。其它 C 差异是 host fixture/测试。baseline C/H/S 与 resident_v34c acceptance 的对应文件完全相同；task 内 resident 副本与实际 resident 源码也相同，见 `layout_recovery.json`、`independent_source.patch`、`artifacts.json`。

## 5. 更新和恢复

loader 先尝试并完整验证卡 DAT，才考虑 IROM；这不是在三个源中统一比较最大 generation。IROM 回退时才选两个有效副本中较新的一个，见 `R/loader.c:55-58,84-106`。因此卡上有效 114 必定先于现有 IROM 113 被选。

首次 menu 在显示列表前先尝试 install，见 `adapter.c:435-454`。`panel_store.c:293-344` 保留旧副本，写临时文件、读回、提交另一副本，再比较 card 与 IROM；`engine_services/mark.c:30-46` 逐字节核对后 rename DAT→OK。独立成功场景确认 113/114 两个 IROM 副本及 114 OK 都是精确字节；去掉卡文件后仍从 IROM 选择 114。

旧 OK 必须先移走。独立保留今日 113 OK 的负例中，114 已写进另一 IROM 副本，rename 被拒后返回 RV_UNCERTAIN，resident 本次禁用，旧 OK 和新 DAT 都在。不能只看旧 OK 存在就判断“114 安装失败且已回滚”，见 `extra_cases.inc.c` 末段和 `host/independent-*.stdout`。

认可的卡 B 步骤，由用户在本审查之外执行：

1. 关机，保留 50mm。备份卡 B 根目录的 gen 113 `GXRCE.OK` 和 `GXRBX0/1.BIN`，保留卡 A 原样。
2. 从卡 B 根目录移走旧 `GXRCE.OK`、任何残留 DAT 和 CTL。只放入 `firmware/engine_v35_publish/local/staged/SD_ROOT/GXRCE.DAT`，65,088 B，SHA256 `132e56389808970b0db8a8c4a359c46f18f0fb2423ecbc11f671d18df19a49a5`。不放机身或 DEEPTBL 文件。
3. 安全推出卡，50mm、M、Start Settings Readout=Body，正常开机并打开 Image Settings。记录是否出现八个配方行。第一次不滚动、不按 Fn2，直接 MENU 返回，触发既有退出日志并保留第一次 seed 输入。
4. 关机，备份新日志和 OK/仍在的 DAT。新 OK 必须与上述 114 DAT 同大小、同 SHA；解码器应报告 engine_generation=114。OK 证明安装收据，不证明 LCD 已显示八行。若仍为原生列表，先看新 seed_inputs/receipt，不重复尝试安装来替代诊断。
5. 50mm 成功后再开机验证各行、01/02/03、04 恢复、Fn2 的 OK/MENU、重开定位及掉电后的完整配方或纯 04。Fn2 会应用当前行，应在明确选择该行后测试。
6. 关机后换 Mount，核对八行及 Fn2；再次关机换 28mm，应显示原生列表。换单元必须冷启动，本实现不会在同次启动热重绑。
7. 如需验证格式化后仍能使用，先保留卡备份，优先通过移走卡上产品文件测试 IROM，正常冷启动后开菜单确认 114。此次无需格式化照片卡。

失败时先关机，保留日志，移走未处理 DAT。114 可能已留在 IROM，移走 DAT/格式化均不会降级；有效的 113 并不会压过 114。

停用时，使用已核对的 `local/staged/recovery/GXRCE.CTL` 复制到卡根目录并冷启动。文件为 16 B、`GXRC3401`、OFF=0、CRC 有效；`blackbox.c:10-18` 校验它，`adapter.c:545-548` 在 bootstrap 拒绝 engine，早于 install 和 UI 发布。三单元 ctl 套件通过。移走 CTL 并再次冷启动会重新启用已安装的 114；这不是卸载或恢复 113。

需要机身恢复时，沿用用户已成功的卡 A、50mm 附着、“+ & playback”的 Stage2l 恢复流程。离线核对了历史 Stage2l 备份 `artifacts/flash-v32/card-backup-before-v32-20261024T005033Z/root/ilaunch3`，SHA256 `efe6587190e845b1c28364c02a6b8bde14e046e7c7411393a4c9892124b6bfd7`；其机身无 GXRCE 路径字面量。不能以另一个名为 Stage2l 的旧暂存包替换已成功的卡 A。未访问当前卡 A，历史备份不能证明它现在的字节，也未重演物理恢复。Stage2l 恢复绕开当前 container loader，不等于证明 IROM 114 被删除。官方 ZIP 的 ilaunch3 也重新逐字节核对了当前 native 证据来源，见 `layout_recovery.json`。

## 6. 二进制和预算

| 项目 | gen 113 | gen 114 |
| --- | ---: | ---: |
| DAT | 64,816 B | 65,088 B |
| engine | 55,404 B | 55,676 B |
| BSS | 11,520 B | 11,520 B |
| 单个 relocation | 8 B | 8 B |
| 文件容量余量 | 720 B | 448 B |
| image+BSS | 76,336 B | 76,608 B |

独立以冻结源代码重编 30 个 M32R 单元，重新生成 services archive 和链接 engine，分别与候选精确一致。替换重建 engine 并重算容器 CRC 后，DAT SHA 仍为指定的 `132e5638…49a5`，见 `rebuild/results.json`。recipe 数据独立与 113 比较并归一化，未用重新造一份同源 golden 来替代比较。

变化不局限于 DAT 中几个连续字节，因为重新链接会移动函数、分支及后续数据。engine 增 272 B，后续六段整体移位；目录内绝对文件偏移随之移动，三份 bank 的 generation/CRC 更新。归一化后，其它 recipe/data 字节全部一致。唯一装载 relocation 从 `(patch=55496,target=32292)` 变为 `(55768,32552)`；两个版本都重新核对了平移 ELF，除此 relocation 外所有 packed engine 字节严格平移不变，见 `artifacts.json`。

114 的 header CRC32=`CFB6B14D`，payload CRC32=`CDFA0249`，均重算通过。+80..111 build ID=`eb96410f5224f76c1cf684a3bd6789eca4c80acf34019120e30dacaeb01da941`；+212..227 ABI=`b6353e4de1c89bd37c08ba6734efc8e0`。三 pins=`F09FE7B4/FB3FBCB2/95F3DCA9`。已刷 body SHA 重新核对为 `24b1de0e46ea00adeacd224da28770e185b05a08686c40c647032c533c021f72`。header 中的 body trust 仍是官方 SHA，不把它误称为已刷 body SHA。

独立交叉编译类型布局得到 main request=84,112 B，loader=608 B、UI snapshot=1,968 B、session work=1,460 B。两个安装缓冲各 65,536 B，每块 native header 12 B：首次安装申请模型 215,840 B，已有 snapshot 时 217,820 B，常驻加全部可选块 88,196 B。比 113 的对应模型仅增 272 B。它们不是实机可用堆、碎片情况或物理峰值；未测真实堆水位。resident 未重建或改写，其原有 216 B 余量没有被占用。

## 7. 测试仍依赖哪些手工输入

新 host 测试已经从官方映像取 state/descriptor 字节，并执行真实的四种 type writer；capacity 在 C 全入口中由实际 services_init 写出。它们解决了旧测试直接塞 type5 和伪 table 的问题，但并没有模拟全部 native 初始化。以下按值的来源穷举仍用于正常模型的人工设定，以及依赖它们的路径。故障注入值和枚举输入另列为测试参数，不伪称现场初值。

现场证据评级：强表示固定字节或实际 writer 已核对；中表示有生产 guard 和 host 路径证据，但现场输入仍手填；弱表示关键 native 行为仍为替身，必须在相机验收。评级针对证据，不表示已发现同等级产品缺陷。

| 输入 | 仍未证明的现场假设及依赖路径 | 评价 |
| --- | --- | --- |
| state/table/descriptor | 官方 state 32 B、table `0x2022F56C`、names `0x2022D610`、count 7、hidden-map 0 来自文件字节；模型主动运行 ADJ writer，随后另取 type 0/4/9/5。现场确切前一 type 仍未知，运行时 table 未被旧日志保存。 | 固定布局强；现场是否保持该值为中。 |
| capacity | C 由 services_init 写 256；`machine114.py` 的 CPU fill 仍直接写 context address、private address、capacity 256，另用 235 作负例。 | 强，C 全入口已覆盖 writer；单独 packed replay 仍有布置假设。 |
| heap | `0x200D3488=0x20704800`、`0x200D348C=0x20744800`、`0x200C0DC4=0x40000`；分配头和成功的 allocator 由替身生成，RAM 先清零。 | 中，加载/安装/lease 的 host 正确性已测；真实剩余空间/碎片证据弱。 |
| S 区 | `0x200C0DAC=0x20500000`、length=`0x1000`、mode byte=`1`，`+0x6DD/+0x6DE=9`。first 测试再枚举 mode 0..255。 | 中，S 写入边界及 cursor-only 已测；真实 S 分配/保存恢复未测。 |
| 单元 | `0x2040F81C` 写 jlaunch/qlaunch/l08firm；version 1.51、cmp 0，`0x2040F804=1`；rpc_ready=1、rpc_limit=9。 | 中，三配置和换单元拒绝已测；模块 RPC 实际时序未测。 |
| W/T | 模块映射区从候选 stock 04 展开后写入假 RAM；T control=2；RPC 23/21/22 由同步替身读写，preview 总成功。 | 现场证据弱，事务/相邻字节有 host 故障矩阵，真实模块应用和颜色未测。 |
| 菜单坐标 | `0x205D9BF8=8`、`0x205D9C00=56`、`0x205A280F=2`。 | 中，ownership 依赖这些值，未回放整个原生菜单分派。 |
| view | `0x205A27D8=0x205A279C`、count=1、tag33、state=`0x2022F71C`；first 投影另设 tag32/opaque state=`0x2022D610`，并手工设 count=2。 | 中，固定 writer/push 已补证，当前相机栈未观测；错误投影见 P2-02。 |
| 字体/绘制 | language=1；ascii 替身生成 `(1,char)` 字节；layer/draw 返回成功。 | 现场证据弱，容量/指针和原生行遍历已补证，字形/LCD 未测。 |
| 卡/文件系统 | SD ID 为 1..16 的固定数组加 serial；固定文件表、缺失返回 -1；read/write 分块 73/89 B；rename 的成功/冲突由替身控制。 | 中，安装/收据/IROM 故障路径是模型证明；真实掉电持久性证据弱。 |
| 上下文/并发 | native_context=0；irq save/restore、cache sync 为替身，公开 hook 的 frame/event 参数由测试生成。 | 弱，未证明真实调度、中断、快门和任务栈的并发行为。 |
| 重启 | 重建 native stock，再按用例保留 S/IROM 文件；不是执行模块上电程序。 | 弱，full-last/pure04 的 host 分支通过，现场冷启动仍需验收。 |
| 本次补充的 native CPU 模型 | 人工布置 parent view、part2 active bit `0x205A280E=2`、五个 ADJ source 字节、类别探针 0/1；以已测 C 发布结果代替 H01/H02，H05 使用已测 details 指针；底层绘制和 memset 明确作替身。 | 中，只证明所列真实指令的写入/消费关系，不是整机仿真或全部 writer 覆盖。 |

旧 type5/table=`0x2022F000` 只保留为历史兼容负/正对照，不是正常布局证据。table=0、未知表、capacity=235、故障状态、epoch 变化、各种损坏输入均为人为反例。输入 `kind` 或直接注入源 cursor 的 packed 测试也不能单独证明它们在现场可达。

本次未发现这些未验证现场假设被 gen 114 新增为不受检查的 native 指针写入；它们限制的是实机功能和并发结论的强度。首轮现场日志需要按第 5 节保住第一次 seed，才能进一步收窄 gen 113 的现场根因。

## 复现和封存

```sh
/usr/bin/python3 -I -B research/review_publish_v114/artifact_review.py
/usr/bin/python3 -I -B research/review_publish_v114/rebuild.py
/usr/bin/python3 -I -B research/review_publish_v114/layout_and_recovery.py
/usr/bin/python3 -I -B research/review_publish_v114/host_review.py compile
/usr/bin/python3 -I -B research/review_publish_v114/host_review.py cases
/usr/bin/python3 -I -B research/review_publish_v114/native_flow.py
/usr/bin/python3 -I -B research/review_publish_v114/packed_and_logs.py
/usr/bin/python3 -I -B research/review_publish_v114/review.py check
```

候选自身 1,353 个交付清单文件及其 5,564 项外部 freeze 校验通过。本次另冻结候选、resident、image、官方文件、卡 B 备份等 10,183 文件，补充 Stage2l/历史卡恢复材料 292 文件，总计 10,475；所有冻结校验通过。`decisions.tsv` 未作为输入或散列对象，未修改其它 worker 目录。最终 `SHA256SUMS` 覆盖本审查目录中除清单自身以外的全部文件。
