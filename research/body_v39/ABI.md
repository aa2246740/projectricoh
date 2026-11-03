# v3.9 机身与 DAT 的接口合同（r7，正式冻结版）

对应源码：`firmware/resident_v39/resident/`（`resident.h`、`hooks.c`、`resident.c`、`loader.c`）和 `firmware/resident_v39/engine_services/`。本文件是复审 `protocol-freeze-r7` 要求的“正式方案、ABI 说明”。`research/body_next_plan/PLAN.md` 不在本任务的写入范围内，所以合同先写在这里，并入方案由编排者处理。

## 1. 身份

| 项 | 值 |
|---|---|
| 机身底板 | 官方 1.51 `ilaunch3` `da1980e9…`（写在 `rv_trust.body`，也写进 DAT 头 48..79） |
| build id | `firmware/resident_v39/local/resident/trust.json` 的 `resident_build_id`，由源码、服务库、链接脚本、`build.py` 和工具链哈希得出 |
| ABI id | 同一文件的 `resident_abi_id`，由 `abi.h`、`resident.h`、`engine_services.h` 得出 |
| 交叉组合 | 新旧机身与新旧 DAT 互相拒绝：DAT 头里的 build/ABI 与 `rv_trust` 不同就在第一次执行前被 `rv_header` 拒绝（`GXRCE_RESIDENT_ID`） |

## 2. 握手（C6，单次调用）

1. resident 先完成长度、头部、CRC、机身/build/ABI、section、重定位、`entry_offset` 的校验。
2. 置 `state=VALIDATED`，`capabilities=RV_READ_CAPS(0x7FFF)`，`bindings=epoch[0..11]`，然后调用一次 `entry_offset`。
3. DAT 在这一次调用里登记入口表，并完成**纯初始化**：不写 S、W、UI，不开写文件；自己打开的文件要关闭，自己认领的资源要归还。全部成功以后才回复：
   - 返回 `RV_PASS` 或 `RV_CONSUMED`；
   - `reply.status=RV_OK`，`reply.actual=40`；
   - **`reply.detail=RV_INIT_DONE (0x49)`**；
   - `reply.capabilities` = 申请的能力。
4. resident 再核对：入口表 `version=1`、`bytes=40`，9 个入口 4 B 对齐且在代码区内；`state` 仍是 VALIDATED；代次和会话复查通过。
5. 发布：`capabilities = RV_READ_CAPS | (申请 & (CAP_FILE_WRITE|CAP_UI|CAP_S|CAP_W|CAP_BODY))`，`RV_PRODUCT_CAPS=0x1F7FFF`。未知位一律丢弃。DAT 不能自己写 session 的能力。
6. 任何一步失败：`state=RV_DISABLED_UNTIL_REBOOT`，`RF_STOP|RF_ATTEMPTED` 置位，`RF_BUSY/RF_PUBLISHED`、block、lease、inflight 撤销，文件已关闭，原生列表 7 行。本次开机不再装载（`rv_load` 返回 `RV_FAULTED`）。主块和装载工作区按现有策略不释放。

VALIDATED 阶段 DAT 只有读能力：RPC 写返回 `RV_CAPABILITY`，S 计划、UI 列表、存储都被拒绝。

## 3. 入口和请求槽

所有入口经 `rv_engine`：先 `rv_check`，再关中断复查 `inflight` 和会话、认领本次进入（`++entry_serial`、`inflight=1`），在**同一段关中断区间**里写入：

| 槽 | 值 |
|---|---|
| `args[0..1]` | 本次 lease |
| `args[2..7]` | 冻结的 `epoch[0,1,2,3,6,7]`（BOOT、HEAP、LINK、UNIT、VIEW、S），`_Static_assert` 钉住 `0,1,2,3` 和 `VIEW==6`、`S==7` |
| `args[10..11]` | session 私有上下文地址，`120` |

然后恢复中断并调用 DAT。服务按冻结的值判断请求是否过期；认领之后代次变了，服务返回 `RV_STALE`，原厂写 0 次。后续服务不得重新读取当前代次来让旧请求重新有效。

各入口自己的槽：

| 入口 | 何时进 DAT | 入口表槽 | 请求/回复缓冲 | `args[8]`、`args[9]`、`args[12..13]` | DAT 的回复怎样生效 |
|---|---|---|---|---|---|
| H01/H02/H05–H08 | 与 v3.8 相同 | `menu_open`/`panel_open`/`event`/`apply_step` | `call_request/call_reply` | 与 v3.8 相同 | 与 v3.8 相同 |
| H09 拍摄指令（`0x2017098C`） | `READY`、无 `RF_STOP/RF_BUSY`、发布了 `CAP_BODY`、不在途 | `panel_event` | `call_request/call_reply` | `9`、144 B 参数块地址（只读） | 只在 `CONSUMED` 时，按 `detail` 条（≤8）编辑写入。编辑是 `(偏移<<8)|值`，两条一字，高 16 位在前，依次放在 `reply.actual, token, epoch, capabilities`；偏移 ≥144 的编辑忽略；`detail>8` 整个忽略 |
| H10 UI 事件（`0x202B120C`） | 同上，另外当前状态号 `0x205D9C00` 是 5 或 56 | `panel_event` | `call_request/call_reply` | `10`、事件码 r11 | 只在 `CONSUMED` 且 `detail<256` 时，`detail` 替换 r11。DAT 拿不到帧和消息块地址 |
| H40 编码前（`0x2015F9D8`） | 同 H09，另外 `image_state < IMG_LATCH`、K 在 18 个槽 `[0x205757A4, +18*588)` 内 | `panel_abort` | `image_request/image_reply` | `40`、K；`args[12]`=原厂 SP（外层返回地址在 `+4`），`args[13]`=原 r0 | 见 §4 |
| H41 编码后 | H40 回了 DONE | `panel_abort` | 同上 | `41`、K；`args[12]` 同上，`args[13]`=`0x201BC3AC` 的真实编码状态（包装器自己返回 0） | 结果忽略 |

单通道：`inflight` 是唯一的所有者。UI 入口（`ui_call`）和图像入口（`image_hook`）都在写请求之前先查 `inflight`，`rv_engine` 关中断时再查一次。忙的时候不调 DAT，原厂路径照常（H09 不编辑、H10 不换码、H40 照常编码）。

## 4. H40/H41 收尾（resident 固定，不依赖 DAT）

- 进入前 resident 保存 `K+0x14C..0x15B`（16 B）和 `K+0x190..0x19B`（12 B），置 `image_state=IMG_ENTERED`。
- DAT 只允许往 `image_state` 写一个值：`IMG_TOUCHED (2)`。凡是要改动两段备份以外的任何编码输入（其他 K 字段、`K+0x1C4` 指向的描述符、像素），**第一次修改之前**必须先用 volatile 写 TOUCHED，加编译器内存屏障，并在最终机器码上核对标记写在修改之前。
- 返回后：
  - `CONSUMED` 且 `detail=IMG_REPLY_DONE (1)`：保留修改，正常编码，之后进 H41；
  - 否则，如果已经 TOUCHED：r0 置 0，跳板跳过编码、返回 −1，`image_state=IMG_LATCH`，本次开机内 H40/H41 一律走原厂路径（DAT 退役后仍然有效）；
  - 否则：两段备份放回原值，正常编码。
- 写像素保持关闭，直到 `encoder-error-to-cancel-save` 闭合（两个获准调用者的错误能走到取消保存和归还缓冲）。v3.9 配套 DAT 只读。

## 5. 根（root）字段的变化

| 字段 | v3.8 | v3.9 |
|---|---|---|
| 第 7 字节 | `grain` | `retired7`：没有读者；颗粒状态在 DAT 里 |
| `grain_bytes`（偏移 236） | 保留 | `reserved_lane`：未用（单通道） |
| `grain_value`（偏移 240） | 保留 | `image_state`：只有 resident 和上面那一个 TOUCHED 写入 |
| `check_failure` | HEAP=3、HEADER=4 | 并入 SESSION=2（`rv_check` 去掉了与 `rv_session` 重复的堆界、块头检查）。黑匣子解码：2 包括原来的堆迁移和块头损坏 |

`RvSession` 增加 `image_request`（64 B）、`image_reply`（32 B）、`k_save[7]`（28 B），共 1,228 B；主块额外开销 `RV_BLOCK_OVERHEAD` 由 7,504 B 变为 7,628 B。

## 6. 配套 DAT（gen 149）在这个合同下的做法

| 入口 | 做法 |
|---|---|
| 握手 | `ig_bootstrap` 登记入口表后直接运行 `init_core`（原 `ig_init` 的主体），成功才回 `RV_INIT_DONE`；申请 `CAP_UI|CAP_S|CAP_W|CAP_BODY` |
| H09 | 原 v3.8 `rv_grain` 的判断原样搬进 DAT，答 4 条编辑：`(0x1A,21)(0x10,0)(0x32,1)(0x6F,强度)`。颗粒值由 DAT 自己保存：提交路径与 v3.8 `rv_grain_commit` 同条件；v3.8 服务库清 `r->grain` 的两处（S 计划写入到达写区、RPC W 到达原生写）改由 DAT 在服务调用返回后清 |
| H10 | ① 状态 56、我们自己的列表、L1 的配方行（0..7）、光标不在“预选”行、没有打开面板、没有锁定错误：OK 按下 `0x23` 换成 DISP `0x25`（进 H06，打开该配方的调节页）。其他页面、其他行、释放 `0x40`、长按、其他键原样。② 状态 5：Fn 码（构建时配置，正式版为 0 = 关）换成 ADJ `0x2B`，并让紧接着的一次 H01 把相邻配方作为“预选”放在光标上，按 OK 才应用 |
| H40/H41 | 只读：记录次数、外层返回地址、编码状态；外层返回地址是 `0x201558A8`、`0x2015EAA4` 时回 DONE（无修改），其余回 PASS。不写 K、描述符、像素，也不写 TOUCHED |
