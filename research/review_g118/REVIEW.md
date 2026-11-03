不可以上卡。

gen 118 的正常预览、退出接受和短暂故障补偿在最终 DAT 的 native 模型中通过，但另一个原生列表可以在预览期间接管共用状态，外层 H08 随后仍把该列表的行号当成配方号，并重画它的光标。持续 RPC 失败也仍会留下混合行，只是 engine 已停用。前者是新增 P1，后者是已有失败类型被扩大到每次导航；均不满足本次上卡要求。

本审查只写 `research/review_g118/`，没有编译、链接、打包新固件，没有访问相机或存储卡，也没有启动子代理。所有 Python 均用 `/usr/bin/python3 -I -B`。审查从 2026-10-27 04:56:26 UTC 开始，时间盒截止 07:26:26 UTC。证据类型为最终 M32R 机器码的静态分析、解释执行和明确列出的设备边界模型，不是实机、LCD 或断电验收。

1. 分级发现

P0：未发现新增的可达文件写入或越界写反例。下面的 P1 足以阻断上卡。

P1-01：预览返回时没有重验原生列表的归属，会接受别的菜单行并改写其光标。

- 复现从真正的 Image ADJ 列表冷开 04，向下移动到 05。在第一次 RPC 边界用共享 RAM、独立寄存器与栈的第二任务上下文执行官方 item-7 arm `0x202BA380→0x202BA3C8`，再执行官方另一个列表构造器 `0x20285E00`。没有手写活动项、光标、native state 指针或 resident 状态。
- 新列表形成后，活动项为 7、overlay 为 21、native type 为 2；`0x205A293C` 仍指向共用的 `0x2022F71C`，该列表的当前行为 7。resident `inflight=1`，view epoch 仍为 1。外层 H08 的 `ig_apply` 第 483–487 行只读 `F726` 和检查 1..8，继续把 7 当成配方目标；最终九行完整匹配配方 07，发生两次预览，root 仍 READY=3。
- 在另一列表构造完成后，最终 DAT 又写 `F726=07`（PC `0x2070F75C`）、`F725=07`（`0x2070F768`）及缓存 `0x205A2944=07`（`0x20705028`）。活动项 7、overlay 21 没有退回配方上下文。用户正在另一个菜单里，配方却继续改变，且该菜单的选中标记和高亮被覆盖。
- `cursor_cache` 的指针相等守卫只能证明地址属于这块共用状态，不能证明现在仍是 Image 配方页；`RV_UI_LIST` op 3 的租约和 epoch 在这个交错中同样没有阻止误写。普通嵌套上下键通过，不能关闭这个反例。
- 这是有具体官方指令和实际写入轨迹的构造器交错反例。case arm 和构造器是真机器码，入口由 review 在 RPC 点调度，没有从硬件输入分派器一路投递；图形锁、UI semaphore 仍处于既有模型边界。本轮没有证明实机会在该点抢占。若原生 UI 在整个 H08/RPC 期间必定串行，调度/锁不变量可以关闭此条件反例；当前没有这份证据。
- 修复方向：在读取“最后一行”和迟到的 op 3 / cache 写入前，重验原生活动项、列表身份和这次 view 的归属。发生归属变化时应安全结束已有单元事务，不再解释外来 `F726`，也不重画外来列表；不能在已经写了一部分后直接中断事务。

证据：[反例及写入轨迹](native/adversarial-foreign-50mm.json)、[完整输出](adversarial-foreign-item7.stdout)、[构造器和 item arm](local/native/image-item-arm.txt)、[源码差异](source.patch)。原生任务交错复现入口：

```sh
/usr/bin/python3 -I -B research/review_g118/adversarial.py foreign 50mm
```

P1-02：持续断链时只能停用，无法把已部分写入的九行收敛到完整配方或纯 04。

- 冷开 04，真正 native 向下进入 05；第 16 次 RPC 先在设备模型执行 W，再向调用者返回错误，其后所有 RPC 都失败。最终共 18 次 RPC、10 次 W；补偿和纯 04 回退各在首个 X 失败，九行不匹配 01–08 中任何完整配方。
- 最终 `uncertain=1`，root DISABLED=6、flags `0xA7`、block=0；原生模式为 Standard=1、overlay=0，原生七项页的行号和黄点为 7。九行合并哈希为 `5e450bcb21f32a2d9cf9f1fbaebeaaa4753f6ac8534e28c7d669553daf4d7b7f`。这不是完整 04，也不是完整 05。
- 没有到达预览提交；模型只证明设置和单元内存已混合，不能据此断言 LCD 显示了怎样的颜色。可确定的用户线索是配方页被撤下；没有可见的“已经安全回退”证据，也没有本路径显示明确错误消息的证据。停用 engine 防止继续写，不会撤销已经送达的 W。
- 与 gen 117 的增量对照：117 的同一次 H08 为 0 RPC、0 W，九行仍是纯 04；随后 OK 的 H07 使用同样故障注入，留下与 118 完全相同的混合行哈希。因此“持续失败会部分写入”不是 118 新发明的风险，新增的是每次光标导航都暴露这个窗口；118 的有限补偿确实改善了后续通信恢复时的结果。
- 作者已披露这个限制，本轮独立复现。真正关机、掉电后单元如何复位或保存这些行未验证。新建 harness 的冷启动按模型初始化 stock 行，不能证明实机关机后一定完整；本次要求的“关机后只能完整配方或纯 04”仍没有证据关闭。

证据：[118 持续故障](native/persistent-50mm.json)、[117 对照](native/baseline-delta.json)、[补偿实现](source.patch)。复现入口：

```sh
/usr/bin/python3 -I -B research/review_g118/run_native.py persistent 50mm
/usr/bin/python3 -I -B research/review_g118/baseline_delta.py
```

P2-01：每格成本的计数可信，但不能把 12.3–46.5 ms 当成实机延迟；中间旧黄点帧也未验收。

96 次独立计量完整执行 CRC 位循环，RPC、W 字节、指令和基础周期均与作者逐步记录一致。不过 CPU 数字建立在未确认的 150–230 MHz 与 70%–100% CPU 份额假设上，不含 RPC 等待、原生字体/预览边界、内存等待和 LCD。若平均每个 RPC 为 2 ms，正常每格已约 0.26–0.50 秒，再加显示等待，足以明显卡顿。详细区间和缓解见第 7 节。

原生上下键先画列表，再进 H08；118 在 RPC 前补画，最终黄点和高亮重合。它不能阻止更早的原生绘制，所以短暂显示旧黄点的风险仍在。解释器绘制调用记录不能证明 LCD 看不到这一帧。

2. 冻结输入、范围与产物身份

| 对象 | 本轮核实值 |
| --- | --- |
| gen 118 卡上 DAT | `e557c7266c05ea5b997bd369b505ea364c660e87aef07180c784207ffd0f3f2d`；56,840 B |
| gen 117 绑定 DAT | `35ce20ac843764b9cdd452785683ebf99004c47b77ae90720c2e3dc716c31211`；55,500 B |
| gen 118 ELF | `108bdd2b6546df7ebb0f58cf165e5c86864f293e17aa49b76fef06ac5c067383` |
| 卡包 `ilaunch3` | `50720c80696ca88f25dc25a85285acd0e0f19906e1d7da1dd404f6cc243f9008`；与 117/v3.6 相同 |
| resident build id | `b779cc756a740506415ca5df8eb5c8f08e1b04ea9d8c4c614f7ae971e92b94f7`；不变 |
| ABI | `d7387c3670059c325186de3af1b3d5c6`；不变 |
| 官方 ZIP | `3705984b8433c40d2ed4fd2600c11f03ed8a6de7dbe7f66efd38ee5ca15fc898` |
| ZIP 内原版 `ilaunch3` | `da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7` |

先核 SHA，再读取报告、源码和机器码。未使用 `04168d00…` 那份 ilaunch3。23 个原生分析窗口由本轮脚本从已核实 ZIP 重取，另提取 settings accessor 窗口；索引记录 VMA、文件偏移、字节哈希和 objdump 命令。[窗口索引](local/native/index.json)、[提取脚本](official_windows.py)。

生产 C/H/S 比较只发现四个变化文件：`containers/product/adapter.c`、`containers/product/src/firmware/engine/core/eng_core.c`、`eng_core.h`、`eng_internal.h`。48 份 552 B 展开结果、48 份 records、48 份 metadata、三份 map 和 pin 与 117 全部相同。卡包共 30 个文件，28 个官方伴随文件逐字节等于 ZIP；除 DAT 外另 29 个文件等于 117。`CARD_SHA256SUMS` 自检 30/30 OK。[源码范围](source-scope.json)、[独立展开比较](data-equality.json)、[卡包检查](package.json)。

DAT 头和 payload CRC、ELF 的 code 段、engine.bin 以及卡包 DAT 的内嵌 code 逐字节一致；身份与作者 identity.json 相同。engine 为 47,288 B、BSS 9,716 B，相比 117 各增加 1,340 B、64 B；DAT 距 65,536 B 门限余 8,696 B。[身份](identity.json)。

“可复现构建”证据分两层：作者保存的默认 v3.6 trust 重建记录声明 DAT/ELF 完全相同，本轮核对其两个完整哈希确实对应当前冻结产物；本轮未再次运行编译器或 packer，遵守“不构建新产物”边界。因此可以确认记录对应同一产物，不能称为本轮独立编译复现。[复现范围](reproducibility-scope.json)。

输入冻结覆盖 25,068 个已有文件；前后完整复查见 [input-integrity.json](input-integrity.json)。review 内的 ELF/DAT 文件是输入原件的证据副本，relocated dump 是解释器检查用字节，不是新候选固件。

3. 最终机器码的零文件写入审计

两条 `ig_init` 成功路径在最终 DAT 中均只请求 `0x000E0000`。loader 的 `0x00007FFF` 与之合成正常会话能力 `0x000E7FFF`，不含 `CAP_FILE_WRITE=0x00010000`。`CAP_W` 允许的是单元 RPC 写入，不等于文件写权限。

本轮逐一列出 21 个 native 文件调用点、19 个固定 native bridge 和 9 个间接转移点。所有 code 字节等于最终 DAT；直接转移没有绕开 service 的文件入口，未发现新增 truncate 或文件 sync 入口。`RV_CACHE` 是 CPU cache 服务，不是文件同步。`rv_call` 和只读文件函数的编译改码通过第 6 节 A 验证；同码 native/IRQ 汇编入口另核 23 个。[调用点](final-file-calls.json)、[bridge](final-native-bridges.json)、[间接调用](final-indirect-transfers.json)、[机器切点与重定位](final-no-write-cutpoints.json)。静态审计地址使用检查基址 `0x21000000`；本轮 native image 基址为 `0x20704ED4`、code 起点为 `0x20704FD4`，两者不混用。

从有效初始化状态出发，只有带写权限的 file create 才能生成 mode=write token；该能力不存在。open 始终 flags=0，read token 不能通过 write 的 mode 检查。rename、delete、mark 同样受能力门禁。close 只处理有效只读 fd；官方 close 的既有审查随不变 body 与本轮等价桥接复用，本轮没有重跑旧审查全部 29 个 wrapper。

在最终装载的 `rv_call` 上单独重放服务边界：查询文件能力=3；create/rename/delete/mark 均返回 -12；打开真实只读文件得到 token，随后 write 返回 -10，close 返回 0；重复初始化仍为 `0xE7FFF`。所有文件变更计数为 0。[机器执行门禁](machine-gates.json)。这个测试明确设置 resident inflight 以满足直接服务入口契约，不计作“自然 native UI 反例”。

三单元 a–h 包括旧 GXLS/GXTS、坏卡包、IROM 及移除卡的路径，均未打开旧偏好文件、未修改这些文件。冷启动值为 04，Fn2 只保留本次 RAM 值。没有任何以“文件打不开”为由转 create 的可达新路径。

4. 新状态机、原生出口和写入边界

H08 顺序核实为：验证行 → `RV_UI_LIST` op 3 同步黄点/高亮 → compute → settings acquire → delta deep W → 设置更新 → preview → settings release → 发布完整 live。发布前失败不会先标记成已确认。`confirmed` 与 `live/current` 分开；成功预览的 `previewing=1`，确认后保存实际配方和实际 tweak。

正常 OK/ADJ 接受同一份已验证 live 时，不再重复 RPC 或 preview。首次冷开尚未应用某行时才按 RAM 默认值应用。纯 04 回退后，`accept_preview` 取实际 zero tweak 并同步 RAM cache，未重放之前给 04 保存的 contrast+1；本轮专门执行此反例，额外 RPC=0、preview=0。[纯 04 接受](native/adversarial-fallback-50mm.json)。

resident inflight 和 adapter active 拒绝 engine 重入。在相同配方页内，RPC 期间再执行真正 native 上下键，嵌套 H08 被跳过，外层串行应用最后停留行，RPC 最大嵌套深度为 1。三单元完整矩阵验证这一点；另在 50mm 的首个 RPC 插入 OK、ADJ、半按，最后均为完整 05、READY=3。[嵌套出口](native/adversarial-nested-50mm.json)。这只证明同页交错的收敛；P1-01 表明“最后行”检查缺少菜单归属条件。

| 实际执行入口 / 输入 | H07 观察与语义 |
| --- | --- |
| `0x23` OK、`0x2B` ADJ，keep=0 | 调用者 `0x202C2D84`；接受完整 03，engine list close，native 页撤下；无额外 RPC。 |
| 同上，keep=1 | 调用者 `0x202C2D74`；接受完整 03，engine list 仍 opened=1、8 行；原生外层仍把 overlay 撤为 0，不能把 keep=1 解释成画面必留。 |
| 第一列 `0x2029FDC4`，`0x29/0x63` | 此状态下直接撤页而不进 H07；live 03 保持，下次 H01 接受该 live，重新高亮 03。 |
| 独立第二列 `0x202BD724`，`0x29/0x63` | 经过 H07 `0x202BD890`，keep=0；送到 engine 的 native raw 为 `0x38`，接受完整 03。 |
| helper `0x202BE978`，`0x29/0x63` | 经过 H07 `0x202BEA54`，keep=0，raw 同为 `0x38`；接受完整 03。这是实际 helper 执行，不冒充物理按键投递验收。 |

上表所有调用者在 50mm 定向重放；三单元完整矩阵另覆盖正常 ADJ、OK、半按及 H01 重开。keep 由官方 setter `0x20265818` 设置，没有直接写原生 flag。对于这些已执行路径，所有离开均保留所见配方，没有取消回滚。[出口证据](native/adversarial-exits-50mm.json)、[官方确认分派](local/native/confirm-dispatch.txt)、[两列快门](local/native/half-first-handler.txt)、[第二列](local/native/half-second-handler.txt)。

新增 cache helper 实际只读 `0x205A293C` 的 32 位 state 指针，只写 `0x205A2944` 一个字节；不写指针地址本身。守卫为 state 等于官方 Image 全局 `0x2022F71C` 或 resident `ui_block`。32 个独立函数 fixture 验证了这两类、外来指针和邻接字节；相邻字节不变。[缓存边界](cursor-cache-guard.json)。helper 自身不截断 row，调用者保证配方 1..8、Fn2 1..11；成功 UI 发布下 `ui_block` 非零。fixture 中 null==null 也满足比较，但未找到合法发布路径到达这一组合。

op 3 的正常调用值域合法，首次导航重画发生在 RPC 前，补偿改变目标行后再画；最终绘制记录的 F725/F726 相等。地址范围检查通过不等于上下文归属检查通过，P1-01 正是后者失效。

5. 补偿与既有反例重跑

失败恢复不信任 delta 的旧 live 账本。先取最后 confirmed，未确认则取纯 04；强制重写全部九行并逐 halfword 读回，包含奇数边界相邻字节保护，再核 T、设置、preview 和 token release。若 confirmed 补偿也失败，绑定仍有效时再试完整纯 04；仍失败就停用，保留 uncertain。

三单元定向 trace 均核实完整补偿包含 253 次 W 和 253 次 V；503 B 有效行跨半字边界后共读写 506 B。50mm 的 B5 从 `0x2012FFFC`、`0x2012FFFE` 跨入 `0x20130000` 时，确实先重发 X=`0x2013`，随后 V 的低位参数为 0，没有把大于 65535 的地址交给 V。28mm/MOUNT 的对应行不跨该页边界。settings token 为 18、20，失败事务释放后才取新 token，最终均释放。[50mm 九行及跨页轨迹](native/adversarial-recovery-50mm.json)、[28mm](native/adversarial-recovery-28mm.json)、[MOUNT](native/adversarial-recovery-mount.json)。

| 继承场景 / 本轮增量 | 50mm | 28mm | MOUNT |
| --- | --- | --- | --- |
| gen 117 的 a–h 全场景 | PASS | PASS | PASS |
| 冷开纯 04、零单元写、零文件写 | PASS | PASS | PASS |
| 01/02 经 H07 后仍为完整配方、原生 mode=1 | PASS | PASS | PASS |
| v3.5 detached snapshot 反例；H08 退役后跳过 `0x202BB96C`，不再写 Setting2 | PASS | PASS | PASS |
| 28mm 首次未 ready 保留 7 行，第二次 ready 才 8 行 | 不适用 | PASS | 不适用 |
| 41 次连续上下移动，逐步核对九行、T、最终黄点/高亮 | PASS | PASS | PASS |
| 第 16/140 次 RPC 错误，含设备执行后报错；恢复完整 confirmed | PASS | PASS | PASS |
| 补偿再失败，回退完整纯 04 | PASS | PASS | PASS |
| 同页 native 重入、Fn2 contrast+1 和半按后重开 | PASS | PASS | PASS |

最终结果为 [50mm matrix](native/matrix-50mm.json)、[28mm matrix](native/matrix-28mm.json)、[MOUNT matrix](native/matrix-mount.json) 及 [50mm a–h](native/ah-50mm.json)、[28mm a–h](native/ah-28mm.json)、[MOUNT a–h](native/ah-mount.json)。a–h 包括菜单进入、stock、01/02、退役反例、Fn2、坏 resident 绑定、旧偏好与 IROM、移除卡及同启动不重试。

这些测试没有 `0x20271FEC` 固定返回 1 的替身；实际需要 getter 时执行原生正文。H08 退役场景保留完整九行并检查 continuation，未用最终模式值掩盖中间 Setting2 写入。功能矩阵只保留已验证 CRC-32 等价加速边界；性能和持续故障重放执行真实 CRC 位循环。文件系统、单元 RPC、字体/绘图、preview 仍是设备边界模型；合成 settings/WB 初值也不构成实机证据。a–h 复用脚本输出中遗留的“117”文字不是产物身份：实际 DAT 哈希、generation=118 及相应断言已独立记录。

6. LTO 共享函数的 A / B / C 关闭

123 个共享 typed 符号中 92 个机器码变化、31 个同码；另新增 5 个、删除 2 个，总计 130 个逐名义务。92 个变化符号对应 85 个真实代码区间。每项的类别、证据和依赖列在 [完整 TSV](codegen-closure.tsv) 和 [闭包 JSON](codegen-closure.json)，没有未分类项。

| 变化的共享符号类别 | 数量 | 方式 |
| --- | ---: | --- |
| A | 83 | 完整指令、控制流、地址目标、普通数据、g 字段迁移的翻译验证。 |
| C+A | 3 | `a4_move`、`ig_panel_open` 的明确 callee 替换；`end` 的 RV_UNCERTAIN 特例；其余逐指令等价。 |
| B | 1 | `ig_init` 10,000+64 对，另 81 组字节/合并 word 守卫。 |
| C+B | 4 | `ig_apply`、`ig_event`、`ig_menu`、`list_bind`；有意改动明确切分，保留正文各 10,000+64 对。 |
| C | 1 | `eng_apply` 有意重构为 live 接受、确认与有限恢复。 |

新增 `panel_render.constprop.0` 与旧 `pn_ui_render.constprop.0` 跨名称对应，另做 10,000+64 对 B。共六项 60,384 对随机/边界差分，比较返回值、r8–r15（含 SP/LR）及按对象映射的全部公共字节写入历史；内部栈不是公共状态。再补 709 对定向输入：ig_init 81、list_bind 240、panel_render 100、ig_event 288。callee 边界和 C 投影在 [differential.py](differential.py) 明列；不把整段入口替换成预设结果。

| B 正文 | 原随机/边界分支结果覆盖 117 / 118 | 加定向后 117 / 118 |
| --- | --- | --- |
| ig_init | 80/122；80/122 | 81/122；81/122 |
| list_bind | 18/28；18/28 | 28/28；28/28 |
| panel render | 52/68；53/70 | 67/68；69/70 |
| ig_menu | 64/72；65/76 | 同左 |
| ig_event | 25/38；26/38 | 29/38；35/38 |
| ig_apply | 5/12；5/24 | 同左 |

覆盖率不是 100%。未执行结果逐 PC 解释于 [分支关闭表](branch-closure.json)：冻结私有 image 的 gate/stock/map/metadata 不变量，固定 ID/occupied，render 生成文本的第 8 字节必为 NUL，或明确属于有意新增/删除的 C 域。`ig_event` 的 B 使用旧版合法 OK/caller 域且强制 `eng_current=STALE`，新 live 接受由真实 native 出口和纯 04 反例执行；`ig_apply` 的 B 是保留 ingress/init/Fn2 外壳，新预览/drain 全属 C。没有把这些 C 分支假称为差分等价，也没有把任意损坏 DAT 当成同一冻结程序。

A 从最终 DAT 与 ELF 的真实字节解码；只按 ELF 明列的地址重定位和逐目标映射转换地址，opcode、寄存器和非地址常量仍按字节比较。g 从 2,476 B 到 2,540 B 的字段位移用前向指针分析核对，不能凭“偏移相差 59”一概放行。匿名常量采用既有 117 保留标签 ELF 的完整对象边界，先验证它的 engine 等于当前 117；包含尾部填充。旧常量池 332 B 映射到新 340 B，仅新增的 8 B 全零 tweak 常量被明确归属。

两个 `rv_call` switch 表共 108 B、27 个目标及全部 packet 模式、分支落点和 call 返回位置均验证；23 个 native/IRQ 汇编叶子字节相同。函数指针数据 `rv_api+16` 的 4 B 重定位递归指向已关闭 `rv_call`，其余 156 B 原样比较。151 个依赖节点闭合，无未解析目标。[packet](packet-modes.json)、[switch](switch-tables.json)、[匿名常量](anonymous-data-pool.json)、[依赖](codegen-dependencies.json)。

C 表示机器码变化有明确源码来源，不表示该变化安全。P1-01/P1-02 仍然阻断产品验收。

7. 每格成本与实机延迟判断

独立执行三单元各 32 次移动，共 96 次、16 种相邻转移、每种 6 个样本；CRC 加速调用和 RPC 错误均为 0。实计 RPC 122–227 次，单元 W 为 220–412 B，非 NOP 指令 2,141,922–3,680,818，基础周期 2,835,538–4,879,838。与作者同一 SHA 的逐步记录完全一致。[独立计量](measurements.json)、[16 格明细](cost-table.md)。这些是默认/零 tweak 的正常相邻移动成本，不是任意 Fn2 或失败恢复的上界。

CPU 估计公式为 `基础周期 / (频率 × CPU份额)`：低端用 230 MHz ×100%，高端用 150 MHz ×70%，得到 12.328–46.475 ms。基础周期只计已解释指令、串行 NOP、乘法和 taken control transfer 的模型罚时；它没有计齐内存等待或原生边界成本。`cpu_speed_r1` 的 tick=1 ms 是静态语义证据，不会把几百万条指令自动换成实机毫秒，也没有为上述频率提供本轮硬件实测。

按 `总耗时≈CPU + RPC次数×平均RPC耗时 + 显示等待`，可给下列条件区间，均尚未加显示等待：

| 平均每次 RPC | 每格条件耗时 |
| --- | ---: |
| 0.1 ms | 24.5–69.2 ms |
| 1 ms | 134.3–273.5 ms |
| 2 ms | 256.3–500.5 ms |
| 5 ms | 622.3–1,181.5 ms |

不能从现有离线证据给实机硬上限；RPC 超时、调度和 LCD 都未计。平均 RPC 接近 2 ms 时，227 次调用已足以让一格接近半秒；持续滚动会明显受影响。三单元有限故障矩阵实计每次导航含补偿为 555–680 RPC、526–758 B 单元写入，比正常格更慢；这些故障路径保留 CRC 等价加速，只采信 RPC/W 计数，不用其主机运行时间估实机 CPU。

不改事务架构的缓解办法是将连续输入合并，光标停留约 100–150 ms 后再预览；OK/ADJ/半按退出必须先完成最后目标的应用和验证，不能提前接受旧画面。实现应使用现有事件/计时机制，不在 H08 中阻塞等待。还可缓存不变的配方标签 glyph，减少每次 op 3 重画前重复的文本转换；不能因此跳过菜单归属、读回或 token 检查。这些是待实现的建议，本轮没有修改候选。

8. 相对 gen 117 的裁决与证据边界

减少的风险：后续通信恢复时，partial W 后会强制完整补偿；B5 跨页 V 正确重发 X；已验证 live 的确认不再重复写，纯 04 不被旧 RAM tweak 覆盖；Fn2 的 native cursor cache 同步及半按重开状态清理已有实际执行证据。

增加的风险：每次 H08 从移动光标变为单元写事务；每格大量 RPC 增加等待和失败暴露；新增的末行 drain、F725/F726 重画和 cache 写入缺少原生菜单归属复验。文件 create/write/rename/delete 路径没有因此重新开放，配方数据和 resident 也未改变。

本轮已完成输入/差异、最终机器码文件门禁、A/B/C 闭包、三单元既有 a–h、正常预览矩阵、失败补偿跨页与持续故障、原生出口和成本复核。最终证据汇总含 18 份运行记录和 671 处零文件变更计数观察，不把观察次数当作独立场景数。保留的未验层是：独立编译复现（本任务禁止构建）、实机 RPC 时间和 LCD 中间帧、实际 UI 调度可达性、关机/掉电后单元行的复位与持久性。不能用新建模型的“冷开 04”代替最后一项。

首轮 harness 前提错误也保留：file op9 的参数位置、keep=1 对 overlay 的错误预期，以及脚本自身的解析/切点错误，分别留下初始 stderr/失败 JSON，后续只修 review 脚本，没有改固件取通过。有效结果以 [acceptance.json](acceptance.json) 列出的最终文件为准；其它初始诊断文件不计作产品反例或通过。

复核脚本均只写本 review 目录；命令从仓库根目录运行。完整代码与 native 重放需要既有工具链反汇编器和冻结输入，不调用编译器、不需要相机：

```sh
/usr/bin/python3 -I -B research/review_g118/artifacts.py
/usr/bin/python3 -I -B research/review_g118/machine_static.py
/usr/bin/python3 -I -B research/review_g118/machine_gates.py
/usr/bin/python3 -I -B research/review_g118/codegen.py
# ig_init、list_bind、panel_render、ig_menu、ig_event、ig_apply 各执行一次：
/usr/bin/python3 -I -B research/review_g118/differential.py ig_event 10000
/usr/bin/python3 -I -B research/review_g118/init_guard_cases.py
/usr/bin/python3 -I -B research/review_g118/targeted_differential.py
/usr/bin/python3 -I -B research/review_g118/targeted_differential.py event
/usr/bin/python3 -I -B research/review_g118/branch_closure.py
/usr/bin/python3 -I -B research/review_g118/close_codegen.py
# 对 50mm、28mm、mount 分别执行 matrix、ah、perf：
/usr/bin/python3 -I -B research/review_g118/run_native.py matrix 50mm
/usr/bin/python3 -I -B research/review_g118/adversarial.py recovery 50mm
/usr/bin/python3 -I -B research/review_g118/measurements.py
/usr/bin/python3 -I -B research/review_g118/collect_results.py
```

恢复说明：把卡上的 GXRCE.DAT 换回 gen 117（35ce20ac…）即可；若相机异常，用卡 A（Stage2l-50mm）挂 50mm，开机时按"+ 与回放"进入更新。

`SHA256SUMS` 覆盖本目录内全部文件，按惯例不含清单自身；最终逐文件自检结果见 [checksum-selfcheck.json](checksum-selfcheck.json)，全部 OK。
