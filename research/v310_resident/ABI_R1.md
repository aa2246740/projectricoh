# v3.10 resident BOOT ABI r1

本 ABI 是机身侧研究合同。实际 DAT 尚未提供，自动写入策略返回 0。候选或未定的静态条件不能由 DAT、自有 RAM、模式号或测试结果补成写许可。没有生成相机安装文件。

## 入口与身份

- H50 在普通拍摄 state 32 的 `0x2029EBC0` 调用原厂状态 setter 后观察真实 state 5。原字为 `148c1ec0`，先重放原调用，再锁存，不执行长事务。证据为静态已证 T02。
- H51 在 task 6 的 after 返回点 `0x202B1310` 调用 `boot_step`，然后重放 `12806002`，续接 `0x202B1314`。这是 C03 所证 after 调用的局部返回点，不是全部单元参数初始化完成的证明。
- H52 在 C01 已证键解析器 `0x202AFE98` 的原厂序言之前核对原始快门消息。正常重放 `287f297f` 并续接 `0x202AFE9C`；取消时返回事件 0，不重放按键。
- 三个跳板复用现有 shared 保存框架，保存 r0–r13、LR 和 PSW。shared 帧为 64 B，外层保存 LR 另占 4 B。H50 的原厂 setter 在进入 shared 前正常调用。长事务时 IRQ 保持入口状态，只有固定字更新使用短临界区。实际 task、IRQ、栈峰值和续程还须由运行证据核对。
- `rv_load`、父块、初始化握手、READY 和 `RF_ATTEMPTED` 与 H01 共用。新 BOOT 尝试位独立于装载尝试位，不重复装载已 READY 的 DAT，也不在之后的状态 5 重试。
- 新 build 和 ABI ID 由 `measure.py` 生成。原容器在首次 DAT 执行前因身份不符拒绝。测试 g153 只能在测试目录中换身份与头 CRC，256 B 之后不改。

## 固定状态

沿用 256 B `RvRoot`，`reserved_lane` 的偏移为 236，地址为 `0x200547EC`，对齐 4 B。偏移 240 的 `image_state` 和 244 的 pins 不变。代码静态断言核对偏移和总长。此字仅 resident 可写，DAT 只能读取。

| 位 | 名称 | 含义 |
| --- | --- | --- |
| 0 | `BO_SEEN` | 已锁存 state 32 到真实 state 5 的首次转换。 |
| 1 | `BO_PENDING` | 等待 task 6 完成点处理。 |
| 2 | `BO_ATTEMPTED` | 本次开机的 `boot_step` 已消费，后续不重试。 |
| 3 | `BO_BUSY` | 正在装载、只读准备、应用或补偿。 |
| 4 | `BO_DIRTY` | 已授予过目标写许可，尚未确认完整结果。 |
| 5 | `BO_GUARD` | 快门请求必须取消。 |
| 6 | `BO_CANCEL` | 事务期间收到快门请求，锁存取消意愿。 |
| 7 | `BO_PERMIT` | 当前 APPLY 调用持有目标写许可。 |
| 8–15 | result | `0 NONE / 1 PREPARED / 2 TARGET / 3 PURE04 / 4 SKIPPED / 5 ERROR`。 |
| 16–23 | error | `0 NONE / 1 EVIDENCE / 2 MY / 3 ROOT / 4 DAT / 5 REPLY`。后两类预留可进一步细分。 |
| 24–31 | reserved | 必须为 0。 |

只对 pins 前完整 244 B 全 FF 的冷 root 调用 `rv_reset`。非全 FF 且身份无效的 root 直接退役。`rv_retire` 保留此字；事务中退役只撤销许可和 busy，保留 dirty、快门取消与固定保护，并记录 ERROR。只有完整 TARGET 或 PURE04 返回可清 dirty 和 guard。DAT 缺失、错误、未知结果及退役均不能清除它们。

## 显式 BOOT 操作

BOOT 使用已校验的 `entries.panel_event` 入口；它与 H09、H10 的选择值分开。操作号固定为 `args[8]=0x100`。`RvRequest` 仍为 64 B，`RvReply` 仍为 32 B，不扩展入口表。

| 参数 | 值与所有者 |
| --- | --- |
| `args[0..1]` | `rv_engine` 写入本次 lease 两份。 |
| `args[2..7]` | `rv_engine` 在短临界区冻结 BOOT、HEAP、LINK、UNIT、VIEW、S epoch。 |
| `args[8]` | `0x100`，显式 BOOT 操作，不能解释成 MENU。 |
| `args[9]` | `0 PREPARE / 1 APPLY / 2 CANCEL`。 |
| `args[10..11]` | 现有 private context 地址与 120 B 长度。 |
| `args[12]` | `0` 无颜色写许可；`1` 仅当前目标事务；`2` 仅向实际 04 快照补偿。 |
| `args[13]` | 只读固定 BOOT 字地址 `0x200547EC`。 |

`rv_boot_proven()` 必须同时返回 CATEGORY、CONSUMERS、WAIT、MODE 四项已审事实，即 15，才可装载并发起 BOOT。当前返回 0。MY 原字节 `0x205D9AA3` 或 pending `0x205DA00B` 非零、状态不为 5、dirty、固定错误、root 不可信、STOP、BUSY、UNCERTAIN、inflight 或会话校验不通过，均没有目标写许可。CATEGORY 不能从 B04/B05 的候选位推断；MODE 还必须绑定原厂循环实际选择的非 MY 模式。

PREPARE 是 READY 后的独立只读操作，不属于纯初始化握手。它必须验证 40 B v1 记录的格式、控制点、型号、版本、DAT 身份与全部 CRC，并对当前对象和单元的精确纯 04 双读。精确纯 04 包含已审 S 地址及 0x1000 长度、S 的 Standard/WB/Body 条件、实际 503 B 九行、T 控制值 2 和规范控制点。不能用缓存、期望值或旧快照代替实际状态。非零未知记录只读。

PREPARED 回复必须为 `RV_CONSUMED=1`、`status=RV_OK=0`、`token=当前 lease`、`epoch=当前 UNIT epoch`、`actual=7`、`detail=1`。`actual` 的三位分别证明纯 04、MY 及实际模式排除、同型号有效记录。PREPARE 完成后仍没有写许可；APPLY 必须重新检查这些条件及对象、代次、原厂锁和取消标志。

resident 在调用 APPLY 之前先置固定 dirty、guard、busy、permit，再在 `args[12]` 授予 1。该许可只覆盖当前 lease、冻结 epochs、PREPARE 的同一 S 对象和单元、相同记录与重算目标。权限仅包括已审 S 白名单、当前单元行 map 和已审 T 控制。它不授予文件写入、菜单发布、MY 设置覆盖、任意地址写入或持久意愿更新。DAT 服务层必须单独实现并验证此 BOOT 资格，不能仅凭旧 MENU 权限或当前空闲状态写入。即使 S 计划为空，第一笔 W 前仍须核对原厂锁。

## 返回与收尾

所有有效回复必须回显当前 lease 与 UNIT epoch，且 resident 的调用后会话校验仍成功。

| 阶段与返回 | resident 动作 |
| --- | --- |
| PREPARE 返回 PREPARED 1 | 核对资格位及 MY/pending。无取消请求时才能进入 APPLY。 |
| PREPARE 返回 PURE04 3 | 已确认完整 04，结束且不授予写许可。无有效意愿也使用此结果。 |
| PREPARE 期间收到快门请求 | 取消该请求；只读准备确认 04 后结束，本次开机不再套用。 |
| APPLY 返回 TARGET 2 | 完整目标已最终读回，S 待写为零，完整预览已发布，再确认结果；清 dirty、guard、busy、permit。 |
| APPLY 返回 PURE04 3 | DAT 已完整补偿并最终读回 04；清相同状态，不更新意愿。 |
| APPLY 返回其他值或请求取消，且 DAT 仍 READY | 仅调用一次 CANCEL，`args[12]=2`；目标写许可已撤销，只能恢复当前事务的实际 04。 |
| CANCEL 返回 PURE04 3 | 关闭事务并保留快门取消记录；机主必须重新按快门。 |
| CANCEL 失败、结果不认识、身份变化或 DAT 已退役 | 锁存 ERROR、dirty 和 guard，退役 DAT，禁止受保护的快门请求；不继续写、不重试、不借新对象补偿。 |
| 装载失败或 PREPARE 无法确认 | ERROR 与 guard 留在固定 root；没有工作 DAT 也能拒绝受保护的快门请求。 |

负状态、`RV_PASS`、`RV_CLOSE_AND_PASS`、`RV_FAULT`、版本或长度错误、lease/epoch 不符都不是 BOOT 成功。BOOT 不能把菜单 `settings_pending` 退出当成功，也不使用菜单的四次再两次恢复循环。

## 快门选择与当前边界

选择取消当前请求并回到完整 04。H52 对原始 `0x700B`、键号 13/14 的按下或长按，在原厂服务与键设置读取之前检查固定字。busy、dirty 或 guard 时返回事件 0，立即锁存 CANCEL，不递归进入 DAT，不等待信号量，不缓存或重放全按码。APPLY 必须在每次原生调用返回后、每笔写之前观察 CANCEL；已写时最多一次完整补偿。补偿完只允许重新按键产生新请求。

保护函数的等待次数为 0，DAT 调用次数为 0。一次事务最多 PREPARE、APPLY、CANCEL 各一次。这不是补偿耗时上界。原生 RPC、文件与预览返回上界尚未证明，C07–C11、C14/C15 的完整消费者及持键、自定时、连拍路径也未闭合，因此实际写许可保持关闭。已证 C02 说明 H10 太晚，不能用旧 H10 或 H09 代替 H52。此版本不承诺未闭合路径的实机拍摄保护。

DAT 侧还须从已提交 TARGET 建立首次 H01 界面，避免再次归一到 04；MY 不建立自有颜色基线。所有自有界面继续保持恰好 8 行和每行最多 13 字符。resident 只提供固定结果，不在此任务实现 DAT 的界面或颜色事务。
