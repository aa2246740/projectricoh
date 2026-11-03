窗口放得下

默认中性版本新增 540 B，真实严格链接后余 92 B，满足新增不超过 600 B 的目标。单机内副本余 272 B，仅卡余 608 B。全部 BOOT 策略由后续 DAT 承担；resident 只保留三个入口、一次派发和固定 dirty/guard 拒绝。最终 47 组检查通过，其中两组 root 检查各含 1,952 项位翻转。本结论是窗口和主机模型验收，不是完整 DAT 颜色事务或相机验收。

## 窗口与变体

固定窗口仍为 `[0x2005276C,0x20054800)`，8,340 B。root/pins 共 256 B，另保留原链接脚本的 24 B，代码上限为 8,060 B。未改 resident.ld，没有新增固定 RAM、可分配数据节或未解决重定位。

| 变体 | 基线代码 B | thin 代码 B | 新增 B | 扣 root/pins/24 B 后余 B | 严格链接 | 构建时间 s |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
| 中性 A+B+C+D，默认 | 7,428 | 7,968 | 540 | 92 | PASS | 0.724 |
| 单机内副本 one_irom_tune_00 | 7,304 | 7,788 | 484 | 272 | PASS | 0.482 |
| 仅卡 card_combined，未采用 | 7,024 | 7,452 | 428 | 608 | PASS | 0.460 |

使用真实 GCC 13.4.0、GNU ld 2.43，以及原 `-flto -fno-guess-branch-probability`。单机内副本沿用该选项的 `-fno-ipa-sra`。变体的差值来自完整链接，不能把单项节省相加。默认源码保留两个机内来源；单机内副本及仅卡只在 scratch 独立替换 loader 测量，没有替换默认方案。

常量 resident 关闭门也做了真实链接，代码 7,984 B，余 76 B，成本恰为 16 B。按机主补充裁定不采用，默认余量保留为 92 B；启用完全交给 DAT。诊断证据见 [gate-cost.json](evidence_r2/gate-cost.json)。

| resident.bin | SHA-256 |
| --- | --- |
| 中性 | `45809881d9a499033c15dd6838e0504b24852e6270a6632fa759c5f1ba2bb41d` |
| 单机内副本 | `6865f2008f05c35ac1b6c44bc1e0eafb293f4a19d4f6360bea51e9f48f00d90c` |
| 仅卡 | `66e37069456c1df4309224e82d1be22ca3948f00ce3589f3ba0cf81257e95129` |

ELF、map、原字节和替换表、目标布局、命令、工具摘要与反汇编见 [evidence_r2](evidence_r2)。R1 的 resident_v310_boot 和原证据保持不变；旧 ABI、进度和摘要分别另存为 ABI_R1.md、PROGRESS_R1.md、SHA256SUMS_R1。

## 薄机身内容与 ABI

源码从默认中性原型复制到 `firmware/resident_v310_thin/`。原 resident.c、loader.c、shared.c、通用/对齐校验器、resident.ld、bridges.S、基础 ABI 等 10 个文件逐字节未改。移除新增的三个入口分支并还原 H50 的冷初始化调用资格后，原 hooks.c 逐字节一致。因此原身份、CRC、退役、dirty-refusal 和八行保护没有被删减。源边界核对见 [audit.json](evidence_r2/audit.json)。

| 入口 | 已证位置 | thin 行为 |
| --- | --- | --- |
| H50 | T02，0x2029EBC0。 | 重放原厂 setter 后，只在实际 state 5 且固定字为 0 时置 PENDING。合法冷 root 复用原全 FF 检查及 rv_reset。 |
| H51 | C03，0x202B1310。 | 消费 PENDING，先置 ATTEMPTED，共用 rv_load；READY 后仅一次 BOOT_RUN。错误或退役且 dirty 仍在时置 guard。 |
| H52 | C01，0x202AFE98。 | 处理 raw 13/14 的按下或长按时，DIRTY/GUARD 非零则返回事件 0；否则重放原序言。按下时间不作判定。 |

完整合同见 [ABI.md](ABI.md)，R2 固定副本为 [ABI_R2.md](ABI_R2.md)。操作号 `args[8]=0x101`，入口为现有 `panel_event`，`args[9]=0x200547EC`，传入 DAT 可写的固定四字节地址。原 lease、epochs 和 private context 仍由现有 rv_engine 填入；请求/回复为 64/32 B，不加服务或写白名单。

固定字仍在 root 偏移 236。bit 0=PENDING，由 H50 置、H51 消费；bit 1=ATTEMPTED，由 H51 置且本次会话不清；bit 2=DIRTY，由 DAT 在首笔单元/S/T 写之前置，只有完整目标或纯 04 最终验证后可清；bit 3=GUARD，DAT 可置，resident 在错误/退役且 dirty 时置，本次会话不清。其余位保持 0。DAT 必须保留一次性位，rv_retire 不清该字。

不保留 resident 模式门或关闭门。未经复审和现场验证的发布 DAT 必须对 BOOT_RUN 返回 `RV_PASS / RV_UNSUPPORTED`，颜色零写、不设 dirty/guard。MY1–MY3 和未知模式同样收到 BOOT_RUN，由 DAT 先依据已证 MY/模式字段返回“不适用”，保持 W、S、T 和 dirty/guard 零写。旧 g153 对未知操作的无写 PASS 也已实际验证。

resident 不执行资格、PREPARE/APPLY/CANCEL、额外 lease/epoch 比较或补偿，不新增现有服务白名单之外的写能力。成功回复为 CONSUMED/OK；“不适用”同样 CONSUMED/OK，detail=2。resident 不解码 detail。DIRTY 没清时，无论回复是什么，H52 都拒绝受保护请求。

## 快门保护与恢复边界

2026-11-02 编排者决定按处理时判定。H52 在 C01 处理当前请求时检查 DIRTY/GUARD，不依据按下时间；原厂队列保留的请求在完整颜色确认、清位之后才处理时可以续接。H52 不等待、不管理队列、不重发请求，等待次数为 0。DAT 在整个颜色事务前置 DIRTY，完整结果确认后才清；途中错误或代码校验退役留下 DIRTY，resident 加 GUARD，后续 C01 请求持续返回事件 0，直到完整冷重启。此项只同步契约，未改生产代码。补偿是否回到纯 04、各原生等待的时间上界，都由 DAT 负责，本轮没有补偿耗时测量。

实际执行了 H50/H51/H52 的机器码和原厂续接。H51 的 r2/r0 重放值正确；H52 清洁路径执行原生压栈，dirty/guard 路径保持 SP 并返回 0；PSW 保持。取消路径没有进入记录的后续设置/服务消费者。固定 shared 框架为 64 B，外层 LR 4 B；这不是完整 task 6/IRQ 栈峰值证明。

移除或更换 DAT 的恢复方式针对下一次完整冷启动。已加载的 DAT 不因卡文件消失立即退出，删文件也不会清已置位的 dirty/guard。H52 当前证明的是 C01 原始键入口；持键、连拍、自定时和全部最早消费者仍由后续 DAT 复审与现场验证关闭。

## 最终测试结果

功能主机测试使用 tools/native_harness_c 的 PythonBackend，`GXR_HARNESS_BACKEND=c`。所有进程继承 nice 10，前台执行，测试 timeout 为 1,800 s；无指令数性能门槛。最终功能检查没有非 PASS，因此无需 Python 后端确认。恢复检查才使用只读的 batch 模拟器工具，并设置 `GXR_EMULATOR_BATCH=1`。

| 检查 | 后端 | 组数或项数 | 时间 s | 结果 |
| --- | --- | ---: | ---: | --- |
| 中性 BOOT 矩阵 | C host | 10 组 | 22.849 | PASS。 |
| 单机内副本 BOOT 矩阵 | C host | 10 组 | 26.588 | PASS。 |
| 仅卡 BOOT 矩阵 | C host | 10 组 | 22.398 | PASS。 |
| 中性 g153 H01，三单元 | C host | 3 组 | 81.850 | PASS，与旧基线的规范化结果相同。 |
| 单机内副本 g153 H01，三单元 | C host | 3 组 | 88.538 | PASS，同上。 |
| 仅卡 g153 H01，三单元 | C host | 3 组 | 93.185 | PASS，同上。 |
| 旧 g153 收 BOOT_RUN 后再进 H01，三单元 | C host | 3 组 | 19.866 | PASS，BOOT 零颜色写，初始化始终一次。 |
| H01、H50 root 位翻转 | C host | 各 1,952 项 | 4.129 | 全拒绝，DAT 入口执行数为零。 |
| 中性更新确认路径 | batch | 1 组 | 104.675 | PASS，全部新旧入口与 resident 执行数为零。 |
| 单机内副本更新确认路径 | batch | 1 组 | 114.357 | PASS，同上。 |
| 仅卡更新确认路径 | batch | 1 组 | 109.622 | PASS，同上。 |

BOOT 每个变体均覆盖以下十组，直接读取实际回复并核对固定字及 H52 续程：

| 场景 | 实际结果 |
| --- | --- |
| 不支持 | status=-4、detail=0；dirty/guard=0，W/S/T 零写，H52 放行。 |
| 成功 | status=0、detail=1；观测到先置 dirty 再清，最终固定字 2，H52 放行。 |
| 途中错误 | status=-1、detail=3；固定字 14，dirty/guard 保持，H52 返回 0。 |
| 调用期间退役 | 桩改已执行代码字，真实 rv_engine 代码抽检以 reason=5 退役；固定字 14，H52 返回 0。 |
| MY1、MY2、MY3、未知模式 | 各收到一次 BOOT_RUN，status=0、detail=2；W/S/T 零写，dirty/guard=0，H52 放行。 |
| DAT 缺失 | 无 DAT 入口，固定字仅 ATTEMPTED，dirty/guard=0，H52 放行。 |
| 非 T02 写入 state 5 | 不建立锁存、不装载、不发 BOOT_RUN。该负例不是维护类别全集证明。 |

每个已派发场景还用实际 setter 和跳板再走两次 32→5，BOOT_RUN 次数始终为 1；DAT 缺失始终为 0。纯初始化不设 dirty/guard。测试桩只改固定字，不执行真实颜色写；其“成功”和“错误”用于验证 resident 合同，不能当作完整目标或纯 04 的颜色验收。桩代码、ELF、DAT 都仅在 scratch 构建，最终不保留 DAT 文件。

H01 比较覆盖界面、移动、原厂退出/重开、实际九行与 T、S 及记录前 28 B。g153 夹具只改身份和头 CRC，256 B 之后与原测试 DAT 逐字节相同。新身份容器没有被混用为旧 DAT 的原始身份。

恢复检查复用 research/body_v39/tests/recovery_path.py，只适配输出和虚拟介质路径，增加三个替换字的观测。三次都在观测的第 65,975,242 步到确认页，里程碑、NAND 操作及停止原因与旧基线相同；没有把相同步数用作性能门槛。此结果只到更新确认页，不是更新完成或实际相机恢复证据。

普通启动模型由 host 给定序列并执行原厂 setter 与真实跳板，不是从 MAIN 自发运行到待机。题定完整模拟器冷启动仍停在 state 2 的缺口没有重跑或修改。维护隔离的实跑证据覆盖恢复确认分支；其他维护类别全集仍未闭合，不能把非 T02 负例扩大为全集结论。DAT 收到未知上下文必须零写拒绝。

原始结果和时间见 [test-summary.json](evidence_r2/test-summary.json)。只读审计还核对 1,149 个唯一冻结输入无变化、R1 机身证据未变、三变体产物绑定及原保护源码。初次构建的路径元数据记录问题另存 initial-output-path-issue；真实链接当时已通过，后续仅适配加载器的路径序列化并重跑，没有改原构建器文件。

## DAT 后续必查项

1. MY 零写必须由真实 DAT 保证。先核对 MY1–MY3、pending、原厂实际模式及未知类别，再处理记录；W、S、T、dirty/guard 均须在不适用时保持零写。发布 DAT 未经复审和现场验证，BOOT_RUN 一律不支持。
2. 实现同型号有效 v1 记录和精确纯 04 双读，核对所有 CRC、DAT 身份、控制点和对象；未知非零尾部只读。不能拿期望值或上次快照代替实际状态。
3. 实现 DAT 内 PREPARE/APPLY/CANCEL、首 W 前锁门、每次让出后的 lease/epoch/对象/单元重验、全量行写和逐字读回、完整预览后的最终核对。dirty 必须先于第一笔单元/S/T 写，只有完整目标或完整 04 可清。
4. 保留现有服务白名单和真实 BOOT 归属；不能伪造菜单资格。首次 H01 从已提交目标建立界面，不重复归一或补套，MY 不建立自有基线。恰好 8 行，每行最多 13 字符。
5. 本轮按默认原型保留 RV_MAX_CODE=65,536 B；g153 代码 65,268 B，仅余 268 B。完整 BOOT DAT 必须压缩代码，或另行统一所有读者的代码上限。本轮没有扩大到 68 KiB，也没有验证完整新 DAT/BSS、主堆、工作区和栈峰值。
6. 关闭 C07–C11、C14/C15 的完整消费者、持键、连拍、自定时和原生时间上界；在新 DAT 复审及现场验收前不能宣称所有首拍都受保护。

## 易错点清单

按 [CHECKLIST_NEUTRAL.md](../pitfalls/CHECKLIST_NEUTRAL.md) 的 15 类核对。

| # | 类别 | 本轮证据与剩余范围 |
| --- | --- | --- |
| 1 | 中断与残留进程 | nice 10、前台、有界运行；进度和原始收据保留，最终清理见 cleanup.json。 |
| 2 | Studio 管线一致性 | 不适用。 |
| 3 | 归属、重入与指针寿命 | 原 rv_engine 检查未改；inflight 时不写请求；退役后短路，不读旧 reply。真实颜色事务由 DAT 后续验证。 |
| 4 | 夹具预置或替代原厂代码 | host 序列及模式值 0 明确为模型前提，真实 setter/跳板执行；没有把模型写成完整冷启动。 |
| 5 | 原厂时机和隐藏分支 | 入口只取 T02/C03/C01 已证点；MY/未知由 DAT 零写；其他消费者和类别未扩大结论。 |
| 6 | 未跑完或套件过时 | 最终 47 组有收据；九组 H01 与旧基线规范化输出逐项相同；无功能非 PASS。 |
| 7 | 未核实状态和相邻字节 | 桩未写颜色，不能代替完整 04 双读或行边界验收；真实 DAT 仍须全读回。 |
| 8 | 原厂续接和八行保护 | 原保护源码可还原为逐字节相同；三单元 H01、原厂退出和重开均通过。 |
| 9 | 打不开与不存在 | 默认多源 loader 原样保留；缺失 DAT 关闭本功能，无新增文件创建或保存。 |
| 10 | 失败收尾和提示 | 途中错误、真实退役均保持 dirty/guard，H52 返回 0；现场提示及完整补偿不在本轮。 |
| 11 | 物理按键和显示 | 未接触相机，未验证物理快门、持键或成片。 |
| 12 | 返回值、锁与等待 | 实际回复值已核对；H52 等待为零。DAT 原生等待上界仍待证明。 |
| 13 | 断电后的状态 | 未更新持久记录；完整重新加载的 root 清理与异常断电验收仍须现场及新 DAT 验证。 |
| 14 | 只测 50mm | 三变体的 H01 均覆盖 50mm、28mm、MOUNT；BOOT 矩阵用 50mm 模型，未外推颜色行为。 |
| 15 | 现场变量混杂 | 无现场试验；body/ELF/DAT 身份、原始输入及规范化比较均绑定摘要。 |

## 复跑与交付

在项目根目录设置指定 TMPDIR 后执行。测试 DAT 只落在该 scratch；完成后删除整段 scratch。

```sh
export TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/v310-resident-r1/
nice -n 10 /usr/bin/python3 -I -B research/v310_resident/measure_r2.py
GXR_HARNESS_BACKEND=c nice -n 10 /usr/bin/python3 -I -B research/v310_resident/boot_check_r2.py neutral,one_irom_tune_00,card_combined --matrix
GXR_HARNESS_BACKEND=c nice -n 10 /usr/bin/python3 -I -B research/v310_resident/harness_r2.py neutral,one_irom_tune_00,card_combined --matrix flow
GXR_HARNESS_BACKEND=c nice -n 10 /usr/bin/python3 -I -B research/v310_resident/harness_r2.py neutral --case dirty
GXR_HARNESS_BACKEND=c nice -n 10 /usr/bin/python3 -I -B research/v310_resident/root50_r2.py neutral --case dirty
GXR_HARNESS_BACKEND=c nice -n 10 /usr/bin/python3 -I -B research/v310_resident/g153_boot_r2.py neutral
GXR_EMULATOR_BATCH=1 nice -n 10 /usr/bin/python3 -I -B research/v310_resident/recovery_r2.py neutral one_irom_tune_00 card_combined
nice -n 10 /usr/bin/python3 -I -B research/v310_resident/audit_r2.py
```

单个 C host 非 PASS 用相同命令加 `--side python` 确认，不改产品代码或工具。计指令门槛另用 Python；本轮没有此类门槛。

最终摘要见 SHA256SUMS、SHA256SUMS_R2；R1 摘要仅把更新文档的路径指向保留副本，原摘要另存 SHA256SUMS_R1_ORIGINAL。最终输入稳定性和 scratch 清理见 evidence_r2/audit.json、evidence_r2/cleanup.json。只写 thin、研究目录与指定 scratch，未访问相机或 SD 卡，未写 Git，未生成相机安装包，未修改其他工作负责的区域。
