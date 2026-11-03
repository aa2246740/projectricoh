# probe_mcm_r1 交付报告

本轮交付 **BASE + CPU/L17 的只读候选 DAT**，不具备“一次上机测清四项硬件行为”的完整能力。包含固定 RAM 读回比对、手机秒表参考、E 空包装、D 减计数循环、完整 17³ L17 内核及八行分页结果。C120、C004±、C100、C040 均按任务第 6 条删去：源写入到此次配置重建、完成确认和活动镜像核对的链路未静态闭合。

最终 DAT 的文件写路径和单元 W 路径均已删除；CAP 为 `0x00020000`，无 CAP_FILE_WRITE、设置写、RV_PREVIEW。最终 ELF/DAT 的桥接、重定位和服务拒绝审计通过；正常、取消、错误、重入及非 50mm 测试中的文件变更、单元 W 调用均为 0。单元参数从未改写，故无需参数回滚；原生 UI 的四个字段与自有 view 槽另做精确撤回检查。

准确的最终 DAT 已通过真实 H01 加载、11 项功能、18 项故障、49 组合法游标、24 个拒绝场景、80 B 绑定逐字节破坏、计时包装和公式测试；重构建字节相同。两份 SHA256SUMS 由交付脚本逐项核验。以上均为 native harness/静态证据，没有相机、LCD、墙钟或真实 CPU 速度读数。

仍有一项 CPU 规格缺口：冻结 v3.6 只初始化 mode/power epoch，未找到自然模式切换、休眠更新这些值的路径。实际 ELF 只有 H01/H02/H05–H09 执行入口；被禁用的模式、sleep hook 窗口仍逐字节等于官方代码，见 `evidence/lifecycle-closure.json`。注入 epoch 变化后会拒绝，不能推出真实事件必然失效。本候选因此**未通过完整 PROBE_SPEC 的上机准入**；手机参考、真实堆余量、调度与电源事件也未实测。

## 1. 交付物与绑定

- 探针：[GXRCE.DAT](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/firmware/probe_mcm_r1/local/package/GXRCE.DAT)；SHA-256：`eb4dae4a9a557f046c5af0625b007b37fd4d480c0b86a0aa45151f327a89523f`。
- 换卡步骤：[CARD_SWAP.md](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/firmware/probe_mcm_r1/local/package/CARD_SWAP.md)；中文指南：[USER_GUIDE.md](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/firmware/probe_mcm_r1/USER_GUIDE.md)，共 9 行，包内同份。
- 源树：`../../firmware/probe_mcm_r1/`；设计：[DESIGN.md](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/probe_mcm_r1/DESIGN.md)；原始 stdout/stderr：`../../firmware/probe_mcm_r1/local/logs/`；执行命令：`local/commands.jsonl`（相对于源树）。
- 唯一菜单标识：`MCM1 351b6621`。源指纹用于区分界面版本；完整 DAT SHA 才是产物身份。

机身固定为现有 v3.6，实际 ilaunch3 SHA 为 `50720c80696ca88f25dc25a85285acd0e0f19906e1d7da1dd404f6cc243f9008`；resident build id `b779cc756a740506415ca5df8eb5c8f08e1b04ea9d8c4c614f7ae971e92b94f7`，ABI `d7387c3670059c325186de3af1b3d5c6`。trust.json 与真实 resident.elf 的 80 B trust 均核对。DAT header 的原始机身 trust 是官方基线 SHA `da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7`，不是已注入 v3.6 的 ilaunch3 文件 SHA，两者没有混用。

冻结 loader 提供身份绑定、长度和 CRC 校验，没有密码学签名认证。真实 loader 在模型中已有两份 gen117 IROM DAT 时仍选择本份卡上 DAT（source=3），未打开 IROM；两份 gen117 的 SHA 为 `35ce20ac843764b9cdd452785683ebf99004c47b77ae90720c2e3dc716c31211`。

| 项目 | 最终值 | 上限 |
| --- | ---: | ---: |
| 文件 | 50220 B | 98304 B |
| code | 49892 B | 65536 B |
| image+BSS | 53568 B | 114688 B |
| 探针 state | 3348 B | 6144 B |
| 主 lease（含 resident overhead） | 61072 B | 65536 B |
| 另一个工作 lease（usage 4，含 guard） | 16392 B | 65536 B |

未放宽任何容量门限。L17 完整表 29478 B，coord 1024 B，表 SHA `c7eff480c613007f84a989325f686483928ac029f0c8f89ec604a39e09da6f99`；33³ 表 215622 B，未装入，界面显示 `33 NOT FIT`。

## 2. 探针取舍与证据

硬件字段的位置与符号沿用给定 VALIDATION §9，不据此补猜生命周期。补查确认机身 `202D6F38 -> 201709CC -> 2005E034` 发出 144 B 的 2F03 消息；单元 `201AB860/864 -> 201ABA1C -> 201AA9B4` 识别该消息，`201AAB18..24 -> 201055B4(request16)` 确实存在。缺的是机身 task 15 至单元接收/staging 的完整传送、完成通知和本次 H01 的活动源选择。证据见 `evidence/supplemental-path-review.json` 及对应反汇编。

| 删除项 | 不能代替的证据 |
| --- | --- |
| C120 | request16 的 live-view 选择来自 T+1262；静帧路径才读取六个 20383E68 缓存。不能把 preview 的返回值当作 gain=60、六缓存=2101 已进入活动镜像。 |
| C004+ / C004− | 普通彩色源到 packer 的字段存在，但当前构建所选源行及重建完成未闭合；不改 2012D0BA，也不动 B&W 2012D0B4。 |
| C100 | 无法证明此次构建会保留所选源行的附加字段；不能用直接修改镜像冒充源到镜像命中。 |
| C040 | 节点字段可定位，但标记旋转、节点改动到同一次活动镜像的触发生命周期未闭合；未改 2012C104。 |

本版不存在这些行的 A→B→A 或 OK/MISS 验证。没有为了保留行数而直接写活动镜像；写失败后的全部恢复测试也未执行，不能用“强制 W 被拒绝”冒充回滚通过。RLUT、机身 F034 跟踪、T 写入均未加入。

BASE 在首次成功 H01 读取 14 个固定范围、260 B（含 gain 相邻半字的重复覆盖），之后逐字节比对。范围在 `baseline.c`，包含 C040 的完整 48 B；它既不是全单元快照，也不建立活动镜像生效关系。读失败报错；不符报 BASE 错误，不尝试覆盖外部变化。

## 3. 八行操作与测速行为

| 行 | 行为 |
| --- | --- |
| BASE | 比对首次 H01 的固定读回；重新打开显示 BASE OK 或错误。没有参数写入需要恢复。 |
| TIME | OK 置待启动，原生关闭后重开；成功发布 REF RUN 后才取 start，下一次有效 OK 先取 end 再撤回。最多保留三个参考。 |
| LUT | 至少两个有效参考才允许进入；只在已确认 DOWN 回调推进一次准入或一次原始 E/D/L17 样本。 |
| RESULTS | 八行分页显示准入最多 8 条、正式最多 48 条样本的 run、N、类型、start/end/delta、CRC、序号与有效状态。 |
| REF HISTORY | 显示各参考的完整十进制 RAW TICK 与 run。 |
| 33 NOT FIT | 只作容量说明。 |
| MCM OMITTED | 说明颜色写探针删除。 |
| MCM1 351b6621 | 版本与源指纹。 |

H07 只接受已核对的 caller `202C2D74/202C2D84`、reason `0x23`，遵守 keep=0 的原生关闭。H08 的 reason 实际为 0，不是按键码；DOWN 由 caller `202BB4E8` 与八行游标下一位置确认，UP 不运行内核。H01、重绘及 DONE 后操作不自动重跑。参考进行中，未知事件、MENU、H06 或再次 H01/H08 使参考作废；每次进入探针观察到绑定 epoch 变化时，也会清除有效参考和样本。REF RUN 首屏不显示尚未取得的 start，停止后到历史页读准确值；样本页显示 run 编号。

L17 是原封不动的 `firmware/lut_p0_timing/kernel.c`，无 LTO；固定种子覆盖六个四面体、端点和相等分量，原生执行结果按独立 Python 向量 CRC 比对。工作区独立 lease，逐样本核对范围、非别名与头尾 guard。初始化、CRC、文字转换、RPC 均在内核计时区之外。tick 用 `2005F164`，包装保存 r8..r13/lr；D 是 `addi r8,#-1; bnez r8`，中断前后均须开启。

准入 L 的 N=4/64/512/4096，D 的 N=2^14/2^16/2^18/2^20；每回调一档，软预算为最新 reference_delta/600，只有上一档不超过预算一半才扩大。预算只能在返回后检查，不能打断已开始的长回调。正式样本交替 E→work、work→E，每个已准入长度三次，至少两个长度。valid 最后提交，回绕用 uint32 差并拒绝半圈及倒退；净差不足 16 tick 标 LOW RES。

`analyze.py` 校验手抄 JSON 的协议、准确 DAT SHA、参考、完整样本、CRC、准入与重复次数，输出秒/tick、tick/像素对、重复的 min/median/max、量化与假设手误差范围。两次参考相差超过 5%，或偏离名义 1 ms 超过 5%，拒绝秒数外推。各长度按净差 ±2 tick 形成区间；它们与最大两个长度的斜率 ±4/(Nhi−Nlo) 没有公共交集时标 LENGTH INCONSISTENT，不硬拟合。D 的 Cloop=4/5/6 仅为条件有效速率；物理 MHz 恒为 null。主图模型是 6106112 像素对，即 12212224 像素；不含真实 DMA、JPEG、主图缓冲和并发。

公式测试中的 0.001 s/tick、47.704 s 与 Cloop4 的 131.072 MHz 全是人为构造的 oracle，不是相机速度。模型 tick 每次调用增加固定值，也不反映 M32R 指令耗时；真实内核执行只证明指令与输出正确。没有报告本机实测 MHz。

## 4. 原生验证与限制

所有正式记录均包含上面同一 DAT SHA。完整命令与 stdout/stderr 保存在源树 local/，证据 JSON 在本目录 evidence/。

| 检查 | 结果及证据 |
| --- | --- |
| 冷 H01 与 BASE | 11 项通过；实际 v3.6 机身/loader/引擎指令，移除 20271FEC 替身且执行真实 getter；未提前填原生 type/table/rows/cursors/view。`native-functional.json`。 |
| 测速流程 | 两个 30000 raw tick 参考（含 uint32 回绕）、8 次准入、48 个正式 E/D/L 样本、结果分页、LOW RES 与 DONE 不重跑通过。tick 是明确的设备模型。 |
| P1 | 49 对 1..7 游标精确保存/恢复；24 个越界或错误上下文拒绝，发布写为零；ui_list/ui_view 共用原子 capture 条件，外部 owner 不撤回。`p1-native.json`。 |
| 包装与事件 | 故意让 tick clobber r8..r13 后包装仍保存寄存器、栈、返回与 IRQ；两个 H07 caller 的 keep0/1 接受，未知 caller 拒绝。`native-contracts.json`。 |
| 故障与非 50mm | 18 项通过；全部 storage op、W/T 页面拒绝，读失败/不符、回绕、预算、guard、IRQ、重入、语言、部分发布、分配失败、retire、28mm 与 mount。`native-faults.json`。 |
| 绑定 | 真实 rv_header 接受准确头；body32/resident32/ABI16 共 80 B 分别翻转并重算 CRC 后拒绝，另拒绝 5 种长度和坏 CRC。`native-binding.json`。 |
| 公式与构建 | 10 种错误输入、LOW RES、参考不一致、名义 tick 不符、L/D 长短斜率不一致均拒绝；PIC 平移相同；重构建 DAT 逐字节相同。`formula-checks.json`、`rebuild-reproducible.json`。 |
| 产物审计 | 最终 ELF 与 DAT code 相同，header/payload CRC、尺寸、外部桥接、重定位与禁用路径通过。`final-artifact-audit.json`。 |
| 既有输入 | 事前清单的 5302 个文件哈希无变化，受保护树无新增文件；这不是全仓库所有文件的审计。`protected-verification.json`。 |

P1 矩阵与 H07 契约用例是在真实 H01/H07 到达边界后注入的故障/参数，不是手工造一个可成功运行的原生菜单。错误 P1 状态在 stock replay 前截停；它们不能证明相机上自然产生过所有输入，也不能证明 stock 会如何继续处理损坏状态。

harness 沿用工具自带的 S 设置输入夹具（对象内容及 r8 引用）、字体资源引用、类别 getter、RTOS/信号量及图形边界模型，另模拟只读文件、SD ID、单元信息/RPC 与 tick。原生菜单表、行数、游标和 view 的创建与发布由真实 H01 执行，没有提前填这几个发布字段；完整机身冷启动、RTOS 与字体任务没有运行。20271FEC 的 getter 替身和 preview 替身均已移除。单元模型加载官方段与 BSS 供固定 X 读回，没有初始化并执行单元配置 builder。模型来源与限制另见 `evidence/harness-models.json`。

CRC 加速前先核对实际链接 CRC 的完整/增量向量，之后仅在计时区外替换 CRC 实现。harness 仍是模型，不是独立硅实现或整机仿真。

P1 修复保留了两处 capture 内的 IRQ 原子检查；不在关中断区分配、转换文字或测 kernel。初次仅接受原表 2022D610、七行、两个游标各 1..7，以及真实支持的 tag32/33 上下文；已有自有八行视图只验证原始 restore、epoch 和 lease。语言变化、错误 owner 与中途失败均不覆盖原快照。

早期失败日志保留在 `evidence/failures/`、`evidence/iterations/` 与源树 `local/failures/`：包括错误假设 H01 必须有 tag32 父层、把 H08 reason 当作按键、空字符串被文字服务拒绝，以及初始 harness PSW 配置和编译错误。正式验收按最终 SHA 选择记录，没有删除失败来取得通过。

## 5. 零写入、撤回与断电语义

最终机器码不含文件 open/read/close/write/create/delete/rename、storage mark、preview 或 blackbox 实现/重定位；允许的外部桥接完整列于产物审计。RV_STORAGE 整类及 RV_SETTINGS/RV_PREVIEW/RV_CACHE 直接返回 CAPABILITY。RPC 仅 cmd21(X)、23(V)，W/op3 在调用原生桥接前拒绝，页地址仅允许 2012/2014/2038，不接受特殊 T 页。resident 装载 DAT 的只读 open/read/close 是机身已有动作，文件边界同时断言 flags=0，任何变更调用立即使测试失败。

本版从不写单元校准/配置 RAM，因此 BASE 与错误路径无需做恢复性 W；测试还比较了模型单元已映射区的整段 digest，保持一致。这里“零写入”指零文件变更、零单元参数 W、零 T 持久写，不是全机零 RAM store：私有 lease、结果、glyph 和原生 UI 正常使用机身 RAM。退出核对四个发布字段及自有 tag33 槽精确撤回，未宣称分配器与全机 RAM 恢复到开机字节。没有所有权时绝不替他人 abort。

从无文件/T 写入口及 loader 的 BSS 清零可推断：普通断电、冷启动后，本探针私有状态丢失，没有由探针写入的持久参数可残留。该推断没有覆盖真实断电、SD/FAT 或其它固件自身的持久化行为，未做物理断电测试。用户原定的“调参后掉电自然恢复”也未实测，因为四项调参已删除。

## 6. 复现、剩余工作与边界

在仓库根目录运行；仅这两个目录允许写，工具链与冻结输入已由脚本核验：

```sh
/usr/bin/python3 -I -B firmware/probe_mcm_r1/build_probe.py
/usr/bin/python3 -I -B firmware/probe_mcm_r1/verify_probe.py --rebuild-compare
/usr/bin/python3 -I -B firmware/probe_mcm_r1/finalize_probe.py
/usr/bin/python3 -I -B firmware/probe_mcm_r1/finalize_probe.py --check-only
```

`build_probe.py` 是本候选唯一构建入口；从 gen117 复制保留的旧 package117/build 脚本不属于本候选构建、测试或交付入口。公式 JSON 结构可参考 `evidence/formula-synthetic-input.json`，不能把它当实测数据。实际手抄后用 `analyze.py <绝对路径JSON> --seconds <各参考实际秒数>`；只把 JSON 放在本任务授权目录内。

仍需补齐：

1. 找到只读、可证明的真实模式/唤醒事件序号，或等价生命周期证据；让自然 mode/sleep 使参考失效，再跑原生路径回归。不能仅改 epoch 的测试来放行。
2. 闭合机身发包到单元 builder 完成与活动源行；通过真实单元初始化路径运行 harness，不能预置镜像制造命中。再逐项恢复硬件探针及 A→B→A、失败回滚验证。
3. 在另行安排的相机测试中核实实际堆/栈、UI、秒表、时钟/调度、休眠和镜像行为。本轮未触相机、卡或 T，未改机身，未执行刷写/提交。

工作开始于 2026-10-27 04:26:54 UTC，3 小时时间盒截止 07:26:54 UTC。
