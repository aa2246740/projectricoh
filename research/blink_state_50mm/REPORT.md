# 50mm 黑屏、绿灯持续闪烁：静态研究

日期：2026-10-25。结论：最符合现有事实的是，机身在 50mm 的启动、通信或后续初始化处停住，启动指示灯一直没有被清除。不能据此判定 MAIN 已损坏，或单元正在刷写。内部存储格式化后仍复现，已排除“内部存储里的引擎文件是本次触发条件”。

建议把“50mm 接着机身，用已审查的 v3.4 完整包进入原生更新器”作为一次有条件的恢复尝试。它不是已证明能绕过故障的救援入口；必须看到单元更新阶段，才能判断是否真的尝试写了 50mm。

## 范围与证据等级

用户提供的五条现场事实作为前提，不重测。只读分析官方 1.51、指定研究和现有包；没有访问相机、卡或 RICOHDCI/DCX，没有构建、刷写。卷身份、可写 APFS 和写入前的 df 记录见 [preflight](local/preflight.json)、[df](local/df-h.txt)。

“已核实”均指静态字节或源码；“推断”指对现场症状的解释；“未知”不能由此次 host 工作补齐。29 个官方文件的长度、加权和均复算一致；1,241 个受保护输入结束时复核，排除 decisions.tsv。文件 SHA 见 [官方清单](local/official-inventory.json)，交付物见 [SHA256SUMS](SHA256SUMS)。

## 1. 绿灯是谁驱动，为什么可以一直闪

已核实：机身的 LED0 同时用于启动和更新。控制链如下，地址是装载 VMA，括号是 ilaunch3 文件偏移：

```text
启动初始化表 0x200C1498 → 0x2006BD5C (+0x20F5C)
  → 0x2006BD3C(LED=0, initial=1, period=250) (+0x20F3C)
  → 0x2006BC9C → 设备 48+LED，ioctl 0x2F05
  → 0x20075234 → 0x20075134 (+0x2A334)
  → 设备37，ioctl 0x2529
  → 0x20070980 → 0x2006FAD4 (+0x24CD4)
```

250、500 被驱动映射成模式 3、2，再编码为控制字节 2..5；没有闪烁次数参数。LED0 的输出映射是 0xD0。常亮/关闭走 `0x2006BD1C → 0x2006BC18`，ioctl 分别为 0x2F03 / 0x2F02。`initial=0` 仍是闪烁模式，不是关闭。[API](local/disassembly/ilaunch3-e03-led-api.txt)、[驱动](local/disassembly/ilaunch3-e04-led-driver.txt)、[底层](local/disassembly/ilaunch3-e07-led-bios-mode.txt)

推断：现场绿色指示灯对应这个启动/更新 LED0。二进制没有直接给出灯的物理颜色；250/500 的实际周期单位和一次亮灭是否算一周期，也未用相机校准。

已核实的闪烁入口分组如下。完整 17 个地址构造点及文件偏移在 [led-call-sites.tsv](local/led-call-sites.tsv)。

| 路径 | 控制点 | 与现场的关系 |
|---|---|---|
| 共用启动 | `0x2006BD5C` 设置 250 | 最符合“初始化未走完，灯未清除”；无需卡或引擎。 |
| 应用唤醒 | `0x20374340` 设置 500；`0x20374354..B0` 等状态 `*(0x205E5368)==2` | 缺少后续事件可以持续等待；正常结束分支会关灯。尚未闭合到具体 50mm 事件。 |
| 单元/机身更新 | `0x2036FAC8 / F73C / F2B4` 设置 500，返回后关灯 | 更新中也闪；正常路径还调用 LCD 更新页，闪灯本身不证明更新。 |
| 底层更新回调 | `0x2008E5EC` 的四个分支 | 可选 250/500、初始亮/灭；其调用者是更新路径。 |
| 文件任务、菜单助手 | `0x20174408/1C`、`0x202C340C/3458/3484` | 普通活动也能用同一盏灯，不能把它当专用错误码。 |
| 应用助手、工程命令 | `0x2036C5A4`、`0x203B72B4` | 可选闪烁；没有证据表明本次正常开机走到工程命令。 |

未知：这些 LED 函数本身不控制 LCD。此次覆盖了该闪烁 API 的常量构造引用及下层调用，但不是完整间接控制流证明，不能声称穷尽了所有“闪灯且 LCD 黑”的组合。未找到某个低层死循环以此灯型唯一表示 MAIN 损坏。已定位的停机自环也不自行设置闪烁。

按现场排序（推断，中等置信度）：50mm 相关启动/通信之后未完成初始化最贴近；单元错误、MAIN/BACKUP 异常仍是候选。卡访问或机身引擎文件不能解释已经无卡、空内部存储仍持续复现；50mm 自己的 IROM、共同启动状态及硬件问题没有被格式化排除。

### -50 会不会弹错

已核实：`0x20063798`（file `0x18998`）最多等 500 次，每次调用 delay(1)，到限返回 -50；它不是无限握手循环。`0x20063894` 在负值时直接返回，没有 LCD 报错。共用初始化器 `0x2005C1D8` 在 `0x2005C2CC` 调用它，随后立即覆盖 r0，没有处理这个错误。故“-50 必然弹错误页”和“-50 自己无限闪灯”都不成立。后续仍可能因缺少单元就绪状态停住，具体位置未知。[握手](local/disassembly/ilaunch3-e02-handshake.txt)、[调用者](local/disassembly/ilaunch3-e01-common-initializers.txt)

## 2. 不按组合键，也会进入更新吗

已核实：可以请求更新流程，不必先按组合键。单元 `jlaunch3:0x20081214..40`（file `0x36414`）比较收到的兼容字段与自身 MAIN 头 `+0x16`，较低时发送命令 65、参数 2。机身 `0x20092A6C`（file `0x47C6C`）把参数 1/2 转为启动标志 0x200000/0x800000；启动分派再调用 `0x2036D4E8(8/16)`。这是兼容性请求，不是普通版本号变化必定重刷的证明。[单元](local/disassembly/jlaunch3-e29-unit-compatibility-request.txt)、[机身接收](local/disassembly/ilaunch3-e17-update-request-and-alternative.txt)、[启动分派](local/disassembly/ilaunch3-boot-dispatch.txt)

已核实：正常请求进入确认页。`0x2036D684..6CC` 使用 UI 79，普通完整更新使用 UI 73；只有确认返回 1 才走 `0x2036D714` 后续路径。官方当前机身与 jlaunch3 的兼容字段均为 0x35。没有找到“插入含 jlaunch 文件的卡就无确认擦写单元”的路径。[确认分支](local/disassembly/ilaunch3-e19-update-confirm.txt)

另有更早的 Safe Boot 分支：`0x2008FE00 → 0x200911CC`（file `0x45000 → 0x463CC`）用 GPIO 对 `(0x7B,0x85)`、`(0x7A,0x83)` 检测，两个输入均为 0 时打印“SysUnit is Safe Boot”。随后 `0x20097424`（file `0x4C624`）启用另一套接收任务，并在 `0x20097484` 循环，不再返回普通初始化。它在上述默认启动闪烁初始化之前。[检测](local/disassembly/ilaunch3-e15-safe-boot-test.txt)、[接收环境](local/disassembly/ilaunch3-e16-safe-boot-task-start.txt)

未知：Safe Boot 到实际擦写的完整链、现场是否进入该状态，以及它是否能自行取卡上的文件。本次只证明启动了接收环境，诊断文字中的 rewrite 不能当作擦写收据。因此不能完全排除异常启动层参与，也没有证据认定发生过中断自动更新。

推断：Mount 更新时未连接的 50mm 不会被那次机身到单元的链路直接写入。MAIN 内容先写、头后写，中断确实能留下不完整程序；但“曾写过”这个前提现场没有证据。卡 B 曾插入不足以补上它。

## 3. MAIN 坏了会怎样；Stage2l 会留下什么

已核实：jlaunch0 是 BACKUP，jlaunch3 是 MAIN。BACKUP 的 `0x27E36C4C`（file `0x36E4C`）读取 MAIN 头，调用 `0x27E352B4` 检查，失败返回 NULL。它检查头尾标识和类型等；不能由此推导每次复位都校验完整 payload。[头读取](local/disassembly/jlaunch0-e46-main-header-getter.txt)、[头检查](local/disassembly/jlaunch0-e47-main-header-check.txt)

BACKUP 信息构造器 `0x27E1570C`（file `0x1590C`）即使拿不到 MAIN 头，仍设置 `NL1/jlaunch`；MAIN 版本 `info+0x30/+0x32` 留为初始 FFFF/FFFF，并计算信息包校验。`0x27E154DC` 初始化它，再注册命令 13 的 2048 字节信息提供者。BACKUP 也独立注册更新检查命令 10 和写入命令 3（`0x27E3A528 / 0x27E3A62C`，file `0x3A728 / 0x3A82C`）。[信息构造](local/disassembly/jlaunch0-e48-backup-info-builder.txt)、[通信注册](local/disassembly/jlaunch0-e49-backup-info-link.txt)、[更新注册](local/disassembly/jlaunch0-e50-backup-update-registration.txt)

推断：如果 BACKUP 真能启动并建立通信，机身有机会识别 jlaunch，取得“MAIN 头无效”的信息并更新；BACKUP 本身并不等于静默黑屏。未知：硬件复位/MONITOR 怎样选择 BACKUP、payload 坏或运行时卡死是否触发回退，以及机身如何显示上述 FFFF。`MainLoad error` 启动原因打印只证明这种状态被设计过，没有闭合自动回退。[原因打印](local/disassembly/jlaunch0-e45-main-load-reason.txt)

已核实的持久化边界：

| 对象 | 代码与行为 | 对本次的判断 |
|---|---|---|
| Stage2l 的 T 操作 | deep_isp.c 限制 RPC 字母为 V/W/X；X12C0 选 T，V 定位，W 写 RAM。U 被边界检查拒绝。 | 已读源码没有正常路径提交 T；不能把每天用 Stage2l 等同每天写校准存储。 |
| 单元 T 提交 | `0x20065DB0`（file `0x1AFB0`），已定位调用来自 UEE00 处理及 UEE53 导入。 | 厂内校准、导入或脚本显式提交能留下状态；不是普通 W 自带保存。 |
| COMMAND.NL1 | `0x20240C28`（file `0x1F5E28`）解释 `/IROM/COMMAND.NL1`；`0x2022DBC0` 通过命令注册范围 0xC000/0x200 调用。 | 没有找到正常开机自动执行它的链，也没有 Stage2l 创建它的证据。 |
| 已知 T+0x2444 | 消费者 `0x2010EB30/94`、`0x20118F5C` 在图像参数生成；官方 jlaunch8 的 file `0xC11B/C122` 写回 0x0002，末尾 `0x1165E` 为 UEE00。 | 未找到该控制字阻塞早期启动的路径。完整 ADJCOM 可恢复此字段，不代表覆盖全部校准。 |

证据：[Stage2l 源码摘录](local/stage2l-T-source.txt)、[提交](local/disassembly/jlaunch3-e34-T-default-and-commit.txt)、[命令文件](local/disassembly/jlaunch3-e41-command-file-interpreter.txt)、[官方脚本字节](local/official-adjcom-control-and-commit.json)。格式化机身内部存储不能证明单元 T 或单元 IROM 已清空。

## 4. 机身 S 或按单元保存的设置

已核实：S 指针在 `0x200C0DAC`，块长 4096；`0x20067BB4`（file `0x1CDB4`）计算块校验并经 `0x200997CC / 0x2009AC80` 保存。Stage2l 已知使用的字段包括 S+0x36E（图像设置选择）、0x36F..374 与 0x8AC..8BF（两个自定义设置）、0x641..646（黑白/调色）、0x6DD/6DE（白平衡）、0xC9D（颗粒）。

`0x20271FEC..20272074` 对图像设置选择作范围处理，`0x2026E634/69C` 对白平衡值作范围处理。唤醒路径还读取 S+0xF3E，写 S+0x3A9/3AA/3F4；F3E 的语义未还原。没有找到其中某字段形成“只挂 50mm 才死等”的链。原生 Start Settings Readout 的 Body/Camera Unit 选择已有文档，但本次没有定位其字段和完整按单元还原过程。[保存](local/disassembly/ilaunch3-e25-S-persist.txt)、[范围处理](local/disassembly/ilaunch3-e26-S-recipe-validation.txt)、[唤醒读取](local/disassembly/ilaunch3-e28-S-at-wakeup.txt)

推断：原生 reset settings 可作为 S 异常的诊断，但不修复单元 MAIN，也不等于重置 T/校准；用好单元执行，是否连 50mm 保存的那份设置一起重置仍未知。它的优先级低于记录版本和确认更新入口。

## 5. 恢复次序与 v3.4 是否等效

已核实：组合键进入的是应用更新器 `0x2036F244`（file `0x324444`），调用 `0x2036D4E8(3)`。共用低层初始化先运行，因此它不能保证绕过早期单元卡点或 Safe Boot 分支。

完整更新的旧协议链是：确认 → 传送 `0x2036FE48 → 0x2010D4B4` → 命令 10 检查 → `0x2036FAC8 → 0x2009005C(3,0)` 写单元 → 机身写入。另有协议状态 6 使用命令 70/69 的分支；实际故障机选择哪条未知。单元已验证文件的标记进入 `0x2007C630` 后，类型 2 写 MAIN，类型 5 直接执行 ADJCOM，未在该解释分支按相同版本跳过。[顺序](local/disassembly/ilaunch3-e20-full-update-order.txt)、[写单元](local/disassembly/ilaunch3-e22-unit-write.txt)、[逐文件处理](local/disassembly/jlaunch3-e31-update-perfile.txt)

这支持“完整流程能处理同版本官方文件”，不能证明黑屏单元实际收到了文件、所有协议都会重写每个程序文件，或看到机身版本变化就算单元恢复。此前 t_recovery 的“同版本 ADJCOM 重跑”适用于走到该完整处理链的条件，不能扩成无条件恢复保证。

建议顺序（未来相机会话，本次未执行）：

1. 先记录屏幕能否进入版本页、原生播放/更新入口及原有设置，不再用格式化重复排查引擎文件。USB 成功仅说明机身 MSC 分支能运行，不能证明 50mm MAIN 完整。
2. 充足电量、拔 USB、关机挂 50mm；使用最终已核对的 v3.4 卡按“+ & playback”。先记录确认页是否识别单元，再决定执行该次完整更新。进入真实写入阶段后遵照原生提示，不以“黑屏已经很久”作为拔电指令。
3. 若能走完整个单元阶段、机身阶段和原生完成/重启，再检查 50mm 正常启动。若在确认页之前仍同样黑屏，不能算作已重刷；现有工具没有已证明能越过这一层的 USB/卡救援方法，不盲目重复。
4. 若想先做设置诊断，可在好单元下记录后执行原生 reset，再试 50mm。恢复支持 S/设置因素；无变化不能完全排除按单元保存状态。无需为了这个诊断先刷 Stage2l 包。用 28mm/Mount 刷 v3.4 只能改变机身，不能修复未连接的 50mm。

v3.4 的判断：作为“官方单元文件恢复尝试”，有条件等效。要求完整保留官方 jlaunch0/3/4/8、原生传送/检查/写入路径，且 50mm 能进入并完成单元阶段。只放 jlaunch3 或只完成机身阶段不等效。v3.4 最终产物尚未提供，本次没有批准或验证它的整包。

现有 v3.2 包的机身 SHA 与现场给定的 05b46ee6…98d8c 一致；其四个 jlaunch 文件均逐字节等于官方。现有 Stage2l 包亦然；两份机身的 11 处相关原生范围与官方一致。[比较记录](local/package-compatibility.json) 卡 A/B 的实际内容本次未读取。

## 6. 下一次只靠屏幕和卡文件收什么

| 收集项 | 结果指向 |
|---|---|
| 记录闪的是哪个灯、10 秒内亮灭次数、是否变频，屏幕是无背光还是背光黑；与好单元作同条件对照。 | 接近 250/500 两档只能缩小启动/唤醒范围；更新、存储也复用，不能单独定性。 |
| 尝试原生版本页（“- & playback”），完整抄下机身及单元各字段；再记原生播放能否显示。 | 能显示单元信息支持通信已建立；MAIN 缺失/异常版本支持头无效/BACKUP。显示 1.51 不证明完整校验通过。两种入口均无界面，仍不能区分 MAIN、通信、供电/触点/机构。 |
| v3.4 的确认页、首次阶段文字、每次阶段转换、单元阶段是否真正出现、原生完成/错误文字及重启结果。 | 卡文件未识别是介质/包选择问题；单元检查失败指向通信/文件验证；单元写入报错指向写入/校验。仅机身完成不证明单元更新。完整后恢复也不能单独区分 MAIN 与 ADJCOM，因为两者一起处理。 |
| 会话前后卡上现有文件的清单、大小、SHA，保留自然产生的 SYSTEM.LOG、DCIM/SYSLOG、MECH/OPE/FALL CSV（若存在），不主动运行工程日志命令。 | 日志若含 Safe Boot/MainLoad/更新错误才有定位价值；不存在无排除力。固件文件原样保留不能证明或否定写入。GXRCE.DAT→GXRCE.OK 只说明引擎安装，不是单元更新收据。 |
| 可选的原生 reset 前后结果；更新后的无卡正常启动结果。 | reset 后独立恢复支持设置因素；完整更新仍失败，应转查未覆盖的单元状态、通信/硬件或机身软件，不能宣布“MAIN 已排除”。 |

尚缺的决定性证据是：50mm 能否到更新确认页、是否可识别单元、是否走完单元更新。完整地址/偏移索引见 [evidence-index.json](local/evidence-index.json)；搜索边界和复核方法见 [EVIDENCE.md](local/EVIDENCE.md)。
