# v3.10 thin resident BOOT ABI r2

机主裁定全部 BOOT 策略在 DAT。resident 只保留首次状态 5、共用装载、一次 BOOT_RUN，以及 dirty/guard 下的 C01 快门拒绝。R1 合同保存在 ABI_R1.md。

## 启用和资格

启用与否完全由 DAT 决定。resident 不保留 rv_boot_proven，也不加 MY、模式、记录、纯 04 或事务许可门。常量关闭门实测多用 16 B；按机主补充裁定不采用，保留仅换 DAT 即可启用和调整的能力。

未经复审和现场验证的发布 DAT 对 BOOT_RUN 一律返回“不支持”，单元 W、S、T 零写，dirty/guard 不置位。测试桩 DAT 只能在 host model 使用，不得发布或封装到相机安装文件。

MY1–MY3、MY/pending 未就绪、未知模式或类别未确认时，DAT 必须在任何颜色写或 dirty 之前返回“不适用”。M01 已证 MY 原字节 0x205D9AA3 和 pending 0x205DA00B；C02 已证模式原字段 0x205D9A7F。字段位置已证不等于所有模式值或物理拨盘绑定已证，MY=0 单独不足以启用。DAT 还须核对原厂实际选中模式。

同型号/版本有效记录、精确纯 04 双读、模式排除、锁、目标计算、PREPARE/APPLY/CANCEL 顺序、对象和代次重验、最终读回、预览和完整纯 04 补偿，均由 DAT 实现。BOOT 不增加现有服务白名单之外的写能力，不把 state 5 冒充菜单归属。DAT 服务层须正确处理 BOOT 上下文与现有 S/行/T 白名单。

## 入口和装载

| 入口 | 位置（原字节见本地副本） | 行为 |
| --- | --- | --- |
| H50 | T02 的 0x2029EBC0，原字节仅存本地副本。 | 先执行原厂 setter，再核对真实 state 5。只在该分支锁存，固定字为 0 才置 PENDING。 |
| H51 | C03 task 6 after 返回点 0x202B1310，原字节仅存本地副本。 | 精确 PENDING 时先置 ATTEMPTED，共用 rv_load，READY 后一次 BOOT_RUN；重放原字节并续接 0x202B1314。 |
| H52 | C01 键解析器序言 0x202AFE98，原字节仅存本地副本。 | 对 0x700B、raw 13/14 的按下或长按，dirty/guard 非零即返回事件 0；否则重放并续接 0x202AFE9C。 |

三个跳板复用 shared 保存 r0–r13、LR、PSW，shared 帧 64 B，外层 LR 4 B。H51 重放按原语义设置 r2/r0；H52 正常序言压入 r8/r9。

MY 与未知模式也发出 BOOT_RUN，由 DAT 零写拒绝。非 T02 的 state 5 不建立锁存。通用 setter 无新入口。更新确认路径须独立核对三个新替换点及整个 resident 执行均为零。

初始化仍采用现有纯读 RV_INIT_DONE 握手。H01、H51 共用父块、rv_load、READY 和一次性装载状态，READY 后不重复装载。BOOT 尝试在装载之前消费，缺失或暂未就绪不在后来的 state 5 补套。

## 固定字

RvRoot.reserved_lane 位于偏移 236，地址 0x200547EC，4 B 对齐，volatile uint32，M32R 大端。root 仍 256 B，image_state 偏移 240，pins 偏移 244。原生产代码没有该字段访问者；合法冷全 FF 检查和 rv_reset 沿用现有逻辑。

| 位 | 名称 | 谁置位 | 谁清除 |
| --- | --- | --- | --- |
| 0 | PENDING=1 | H50，仅整个字为 0 时。 | H51 消费，替换为 ATTEMPTED。 |
| 1 | ATTEMPTED=2 | H51，在任何文件/DAT 调用前。 | 本次会话不清，DAT 必须保留。 |
| 2 | DIRTY=4 | DAT，在第一笔单元、S 或 T 写入前。 | 仅 DAT，在完整目标或完整纯 04 已最终验证后清。 |
| 3 | GUARD=8 | DAT 可在不确定时置位；resident 在错误/退役且 DIRTY 仍为 1 时置位。 | 本次会话不清；完整冷重新加载与合法 rv_reset 才清。 |
| 4–31 | reserved | 无。 | 保持 0。 |

DAT 只可改变 DIRTY/GUARD，必须保留 PENDING/ATTEMPTED 和保留位。结果、补偿日志与事务资格放 DAT 自有内存。DAT 调用期间 H52 只读，H51 在返回后才可能置 GUARD。

rv_retire 保持原代码，不清固定字。DAT 缺失或退役也不能消除 dirty/guard。错误途中 DIRTY 留下后，受保护的快门请求持续取消，直到完整冷重启；resident 不补偿、不排队、不重发快门。

## 请求

操作号 args[8]=0x101，使用已校验的 entries.panel_event。它与 H09=9、H10=10、R1 操作 0x100 分开。不扩展入口表、API 服务、写白名单或固定 RAM。

| 参数 | 内容 |
| --- | --- |
| args[0..1] | 现有 rv_engine 填入 lease 两份。 |
| args[2..7] | 现有 rv_engine 冻结 BOOT、HEAP、LINK、UNIT、VIEW、S epoch。 |
| args[8] | 0x101，BOOT_RUN。 |
| args[9] | 可写固定字地址 0x200547EC。 |
| args[10..11] | 现有 private context 地址和 120 B 长度。 |
| args[12..13] | 0，保留。 |

请求/回复仍为 64/32 B。新 build/ABI 身份随 thin 机身生成；旧身份容器在执行前拒绝。g153 回归夹具只在 scratch 改 build、ABI 和头 CRC，256 B 之后逐字节保留。

## 返回

| DAT 结果 | wire 回复 | resident 动作 |
| --- | --- | --- |
| 不支持，关闭功能 | RV_PASS=0，status=RV_UNSUPPORTED=-4，detail=0。 | DIRTY=0 时不加 GUARD。兼容旧 DAT 对未知操作的零写 PASS。 |
| 不适用，如 MY/未知 | RV_CONSUMED=1，status=RV_OK=0，detail=2。 | 不读 detail；DIRTY=0 时续程，H52 放行。 |
| 完整目标成功 | RV_CONSUMED=1，status=RV_OK=0，detail=1。 | 不读 detail；DAT 必须已经清 DIRTY。 |
| 完整回到纯 04 | RV_CONSUMED=1，status=RV_OK=0，detail=3。 | 同上。 |
| 错误或退役 | 非 OK status、非 CONSUMED 返回，或现有校验使 DAT 退役。 | DIRTY=1 时置 GUARD；否则没有额外动作。 |

resident 不新增 lease/epoch 回复比较，不解码策略结果，不安排补偿。现有身份、CRC、会话、代码抽检、范围和回复格式校验全部保留。即使 DAT 误报成功但留下 DIRTY，H52 也会拒绝 C01 请求。

## 边界

本轮保持默认原型 RV_MAX_CODE=65,536 B、RV_MAX_FILE=98,304 B 和 RV_MAX_IMAGE=114,688 B，不沿用 R1 的 68 KiB 规划。完整新 DAT 须先满足这些限制；扩大上限必须另行统一所有读者。

移除/更换 DAT 的恢复方式针对下一次完整冷启动。已加载 DAT 不会因卡文件消失立即退役，删除文件也不会清已经置位的 dirty/guard。

H52 等待为零，只证明 C01 原始键入口的拒绝。持键进入 state 15、连拍、自定时、完整最早消费者与真实 RTOS 时序仍须后续 DAT 复审及现场验证。测试桩只检查派发与固定字，不证明配方或纯 04 的颜色结果。完整模拟器冷启动的 state 2 缺口保持原状。
