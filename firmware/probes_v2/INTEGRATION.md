# 接入三个只读探针引擎

这份文档定义探针侧的接线合同。它没有修改 `resident_v2/abi.h`。当前产物尚未接入最终常驻层，也没有容器文件。原生九行空面板、loader 独立见证重新发布和真正画面刷新仍未闭合。

## 入口和私有 RAM

三个代码段共享 `engine.c`，分别编译 `PV_ENGINE=1/2/3`。每个代码段链接于 0，不含 `.data`、`.bss`、GOT、绝对内部指针或运行时重定位。`entry.S` 的十个跳板依次在代码段偏移 `0,16,...,144`。容器 header 的入口取代码段首字节在整个容器中的偏移；后续入口表也使用整个容器的偏移。

bootstrap 的 `args[10..11]` 是 resident 提供且已经验证的 `RvEngineEntries` 输出缓冲。`args[8]=0` 使用当前容器代码段起点 256；非零时必须是 resident 核验过的实际代码段起点，至少 256、4 B 对齐。bootstrap 返回 `PASS`、`reply.status=OK`、`actual=40`。初始化成功同样返回 `PASS`。`menu_open` 和列表 `apply_step` 成功返回 `CONSUMED`。

其余入口的 `args[10..11]` 指向 `PvInvocation`，其 wire 大小为 180 B。它是探针专用 payload，不是已冻结 ABI 的新增结构。resident 必须在调用前验证它与全部嵌套范围，并把它放在仍有效的受理 RAM 中。不要让卡文件提供任意裸地址。

| 字段 | resident 的责任 |
|---|---|
| `state_address/state_bytes/state_lease` | 提供清零的 `PvState` 前缀。目标 M32R 的大小和偏移由 `local/build/target-layout.json` 实测。每次入口都传同一个上下文，不用全局变量找回旧块。`args[0]` 和第二实参为相同 context token，`args[1]` 为此 state lease。 |
| `image_address/image_bytes/image_lease`、`code_address/code_bytes` | 指向这次已接纳的容器及其中准确的代码段。完整范围、身份、源摘要、内部重定位和全部入口必须在卡代码运行前验证。 |
| `ui_state_address/ui_state_bytes/view_token` | 完整 renderer state 位于同一 state lease 中，且在 `PvState` 前缀之后。resident 按已审原生布局预填，探针不猜 state 大小，也不写原生状态字段。`ui_state_bytes=0` 仅用于无 UI 的主机观察，不代表相机显示已通过。 |
| `nonce` | 提供本次新会话的非零 nonce。旧 root 与见证都丢失后，不复用同 nonce 报保持。 |
| `witness_bytes/witness_usage` | `witness_bytes` 只接受 256 或 32768。首次采样才申请一次独立 lease；本轮适配当前 `resident_impl` 的只读用途 2，最终用途枚举仍须由协调者统一。先小块验收，32 KiB 是另一个全新会话。 |
| `reference_valid/reference_replica/reference_bytes/reference_crc` | 默认 `reference_valid=0`。可信参考绑定一个固定 IROM 副本，`reference_replica` 为 2 或 3。CRC 为原始文件完整字节的 IEEE CRC32，允许为零。读另一副本时显示无参考，不把 A 的参考套到 B。参考值只放本任务 `local/` 的最终打包元数据。 |
| `input`、`refresh` | 只放 resident 在安全任务边界复制的值，不含以后再解引用的原消息指针。没有观察值时 header 清零。字段有效位的语义必须由最终 adapter 明定；当前只保留位图和原始值，不猜键名、按压阶段或 apply 阶段。 |

代码不验证配方 bank、三模块 stock pin 或 data v2 参数语义，也不应用配方。最终探针容器仍须通过常驻层的容器/信任校验；如该流程把 bank 语义下放给引擎，协调者须在探针 init 前接入已审纯校验器，或明确只读探针的独立受理规则。不能因为探针不写参数就跳过入口或容器受理。

当前 `resident_impl` 的 UI 能力位是 bit17。探针纯 init 只请求这一位，不请求 bit16 文件写、bit18 S patch、bit19 RPC W。它不是 `abi.h` 中已冻结的枚举，最终接线必须核对。服务操作支持还要逐一检查 `RvApi.services[].operations`，不能凭非空 `call` 猜可用性。

## 列表选择和物理键

adapter 把本探针拥有的列表行选择送到 `apply_step`，`args[8]=PV_SELECT_ROW`，`args[9]=0..15`。它们不是配方 param ID，不得传入普通配方 setter。列表入口对于未知行、未知命令、读失败、无文件都不返回 `PASS`。

| 用户看到的行号 | 动作 |
|---|---|
| 01..12 | 打开页号 0..11，不重新采样。 |
| 13 | 人工采样一次。 |
| 14、15 | LIFE 分别只读 IROM A、B，然后打开页 2。另两个引擎返回已消费但不支持。 |
| 16 | 人工标记号加一。 |

也可以直接传 `PV_SAMPLE`、`PV_PAGE`、`PV_READ_A`、`PV_READ_B`、`PV_MARK`。LIFE 另有 `PV_CAPACITY`，`value=0/1/2` 为首次菜单、回放之后、睡眠唤醒之后。同一阶段不重复运行。标记号和采样计数只写自有 RAM。

LIFE 共 17 页。页 5/6/7 分别显示三次容量结果；页 8..13 显示事件；页 14/15/16 分别显示三次容量的原始 alloc/free native 返回。Fn2 在 LIFE 中只做下一页，循环回页 0。因此页 12..16 不占额外菜单行。NOTICE、VIEW 仍为 12 页，事件页仍是 6..11。

LIFE 首次菜单在已有同一个 P2 见证块的条件下自动跑容量阶段 0。回放后选行 07 打开页 6，再选行 13；真正睡眠唤醒后选行 08 打开页 7，再选行 13。普通重开不重复容量测试，也不从未知 power hook 参数猜“刚睡醒”。其它入口也可明确调用 `PV_CAPACITY`。同一 session 内每阶段只有一次，保存测量时的 boot、heap、sample 和见证块大小。

每次顺序尝试 65536、49152、40960、32768、16384 B。成功的回复经过本会话 token/代次检查后，下一次服务调用立即 free。容量块没有 pointer 转换、读、写、填 canary、CRC 或 cache 操作。不主动释放 P2 见证、上下文、UI 或引擎。alloc 普通失败记录后继续下一档；释放失败、旧代次或不完整成功回复则停止并返回 FAULT，不重试 free、不冒报完整结果。结果是最大成功且已释放的档位，不是精确最大空闲块，也不是碎片统计。

`event` 只由已证明的菜单任务安全点调用。它一次读取事件环并复制可选消息值，返回 `PASS`，保留物理键的原厂行为。它不在异步通知中执行，不增加后台任务。NOTICE/VIEW 的 Fn2 draft-only 入口返回 `CONSUMED + UNSUPPORTED`；adapter 不得把它报告成已成功发布原生面板。六项草稿只用于模拟 `panel_event`，没有 UI_VIEW 替换或九行 renderer 验收。LIFE 的 Fn2 按上一段翻页。

返回枚举由 resident 翻译。Fn2 消费成功对应 native 0；H10 消费要转到收下一事件。禁止把 1 或 2 直接交 shooting dispatcher。`FAULT` 必须撤 native 引用并保留实际原因。代码或 state lease 无效时，只能由 resident 画固定错误或退出，不能再回调探针画错误页。

## 服务调用与输出规则

服务调用统一经过 `call()` 的白名单。允许的修改只限自有 RAM、lease 分配及当前菜单字形/引用。

| 服务 | 允许操作 |
|---|---|
| STORAGE | 1 caps、2 固定 IROM A/B open、4 read、6 close。 |
| LEASE | 1 alloc、3 inspect；2 free 仅用于容量探针刚取得并核实属于本次会话的新 token。探针不 free 旧块，也不自己释放仍可能被 native 引用的 UI/代码。 |
| SETTINGS | 1 snapshot、3 release。仅读取 `0x6DD/0x6DE`；release 按当前 owner/context 撤本次短期快照，其余字段为零。 |
| UNIT、SD_ID | 1 snapshot。SD_ID 使用回复 epoch 与采样前后的 coherent epochs 比较，不占用未定义的额外参数。 |
| EPOCHS、EVENTS | coherent snapshot 12、事件快照 1。没有 append_user。 |
| UI_LIST、UI_TEXT | bind/redraw/release；ASCII 转 glyph 和 language。没有产品设置写入。 |
| QUERY | 0..2 只读查询。 |

RPC8、PREVIEW、CACHE、SETTINGS patch、全部文件写/创建/删除/改名/确认都不在白名单。不会产生 RPC W/U/T，也不会发 V/X 读请求或新 preview 请求。没有可打开写能力的编译开关。

每个回复必须 version=1、bytes=32、返回状态与 `reply.status` 一致。快照必须报告准确 `reply.actual`。事件 header.bytes 可保持调用者容量 280，也可缩到 `24+16*count`，但 `reply.actual` 必须为实际有效字节数。环序号必须连续；覆盖和缺口保留为 sticky，不能解释成“没有通知”。

`UI_TEXT language` 采用当前实现的 `reply.detail`；`actual_bytes` 从 `RvUiText` 取。稳定标签采用两层引用：table[i] 指向 labels[i]，labels[i] 指向 glyph[i]。每次 16 个 ASCII 行都恰好 12 字符，glyph 容量各 96 B。

P1 一次人工动作只读一个固定对象，最多 96 次有进度的 READ，512 B 缓冲，最多 32768 B，随后再读 1 B 验 EOF。负返回、越界长度和无进展均不重试。每个成功打开的 token 最多 close 一次，关闭错误保留。原生阻塞 I/O 的时间上限仍是常驻层责任。

## 当前并行实现的接线缺口

这是对 `resident_impl` 工作中源码的静态抽查，精确 hash 和窗口见 `local/integration/snapshot.json`。不是最终常驻层运行结果。

1. loader 的 init 请求没有 `PvInvocation`，也没有分配/登记本探针的 state/UI。需要 adapter 在本任务目录之外由协调者接入，不能直接把 `engine.bin` 当完整卡文件。
2. `services.c` 先用 `q.args[1]` 验输出 buffer，LEASE inspect 又用同一字段选被查 lease。独立见证 token 与存放描述符的 state lease 不同会返回 `RV_RANGE`。把输出先放进旧见证再查会先写旧块，违背安全顺序；探针没有采用这个办法。
3. coherent EPOCHS、UNIT、SD_ID、SETTINGS snapshot 的部分成功分支未写 `reply.actual`。严格探针会拒收，不能把 OK 自动当成缓冲完整。
4. 读到对象上限 32768 B 后，当前 STORAGE 的剩余长度 guard 会拒绝额外 1 B EOF 读取。应允许有界 EOF 验证，不扩展写操作。
5. `current()` 先拒绝旧 unit/link/view/S 代次，可能使 EPOCHS coherent_snapshot 无法把新代次交给引擎。resident 必须先刷新入口代次，或明确探针可查询的新鲜度路径；本轮未绕过它。
6. 独立 loader 栈见证、完整按键复制 payload、完整原生 renderer state 和只读 apply 阶段来源都没有在冻结头文件中约定。缺的部分保持 UNKNOWN。P7 没有 frame-completion 服务，H37 post 不等于下一帧完成。

补充容量需求后，还须核对 LEASE free 是否把原生释放失败传播到 reply，而非忽略原返回后总报 OK。该分支也保存在快照中。旧 `card_container/gxrce.h` 的 32 KiB 文件/4 KiB BSS 限制不因主堆有空间自动变成 48 KiB；最终 data v2 的 header、loader 分配式、存储 READ 上限和实际 BSS 必须统一。

模拟服务表刻意实现上述严格合同，包括跨 lease 的只读 inspect 输出和准确 actual。测试通过不能证明这些接线缺口已修好。
