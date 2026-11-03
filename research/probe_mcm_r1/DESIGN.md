# probe_mcm_r1 设计

本版只包含 BASE 只读 RAM 快照核对、TIME 手机秒表参考、D 原生减计数循环和 L17 私有 LUT 内核。C120、C004±、C100、C040 全部删去。源行到 packer 的静态证据成立，但 RV_PREVIEW 到目标单元 builder 的执行、完成时点及返回后镜像可读性没有闭合。本版不发送任何单元 W，不写 T，不提供颜色探针已验收的结论。

## 输入和调用模型

- 输入是 engine_v38_b36 的源树副本，resident_v36 及官方文件只读。v3.6 的 build id、16 B ABI、机身 SHA 均固定；不构建或替换 resident。
- H01 在 stock 构造器设置 type 5 前调用 menu_open。引擎必须走 `rv_native_seed` 的真实构造器重入顺序，不能在测试里提前补 type 或游标。H08 只导航；测速页的 DOWN 才推进一个短样本。H07 按已核实 caller 和 reason 识别 OK，keep=0 时接受 resident 关闭。
- 现有 harness 在 `0x20271FEC` 以常数 1 代替图像模式 getter。本版移除它，执行真实 getter。只模拟文件读取、unit 链路包、字体和外部 tick，不手工设置原生表、行数、游标、type、view 栈。
- `202D6F38 -> 201709CC -> 2005E034` 证明发送 144 B、消息 2F03，返回值检查发送结果。单元 `201AB860/864 -> 201ABA1C -> 201AA9B4` 识别 2F03，`201AAB18..24 -> 201055B4(request 16)` 也已找到。仍未证明机身 task 15 到单元接收与 staging 的完整传送、完成确认，以及本次 H01 下的活动源行。证据保存在 evidence/supplemental-path-review.json。
- C120 另有路径差异：live view 的 request 16/17/19 从 T+1262 取选择，静帧路径读取 20383E68 缓存。不能以 preview 的成功推断六缓存修改在此次重建有效。

## 两个候选与选择

候选 A 保留硬件行，在 preview 返回后读镜像。它依赖未证明的队列完成和 builder 选择，不能满足用户第 6 条，拒绝采用。候选 B 删除全部单位 RAM 改动，仅保留只读基线和纯私有测速，采用。用户明确禁止子代理，两个候选由当前 agent 自行比较。

## 模块和接口

`probe.c` 处理 ingress、八行 UI、参考状态机和原始结果；`baseline.c` 通过受限 X/V 读取固定地址清单并比较首次 H01 快照；`kernel.c` 原样复制 lut_p0_timing 的 17³ 内核；`timing.S` 包装 tick、empty、原生 r8 减计数循环；`services/` 是 v3.6 服务源副本，收窄为 UI、查询、lease 和 X/V。

调用示例：H01 打开八行菜单，BASE OK 核对快照，TIME OK 发布 REF RUN 后取 start，下一次有效 OK 先取 end 再关闭；至少两个参考后 LUT OK 进入准入页，DOWN 每次只运行一个样本；RESULTS OK 进入八行原始结果页，DOWN 翻页，OK 返回。MENU、H06、未知事件或参考中再次 H01 使参考失效。没有计时期间的 glyph、CRC 或 baseline RPC。

状态：`NEW -> REF RUN -> REF DONE -> ADMISSION -> BENCH -> DONE`。错误或参考中取消清除有效参考与预算，必须重新参考；残留 RAM 条目不再视为有效历史。每个样本先清 valid，完整写 start/end/N/checksum 后最后置 valid。REF RUN 首屏不显示尚未取得的 start，提示到停止后的历史页查看；各样本页同时显示当前 run，避免混抄。

固定八行是 BASE、TIME、LUT、RESULTS、REF HISTORY、33 NOT FIT、MCM OMITTED、版本和源指纹。结果与参考页各八行，完整十进制 start/end/delta，页间不截断高位。33³ 不测。H08 的 args[13] 实际为 0；用已确认调用者 202BB4E8、reason 0 和游标按八行向下变化识别 DOWN，不把这个字段猜成按键码。空白标签用一个空格，避免原生文字转换拒绝空串。

## P1 与服务边界

所有 ui_list/ui_view 的 capture 前，在原有 rv_irq_save 之后使用同一权威条件。首次只接受 stock 表 2022D610、7 行、两个游标各 1..7、受支持的 tag32/33 和 state。真实初次 H01 允许单层 tag33；不能凭旧假设强要 tag32 父层。已拥有八行视图则核对原始 restore 记录、owner、epoch、lease，不再次捕获原值。分配和 glyph 转换保持 IRQ 开启；语言 getter 的原始值 2023EAB8 在转换前后及最终 capture 内一致，raw10 按原生规则归一到 1。任何拒绝不写原生发布字段、不调用没有所有权的 abort。撤回必须同时验证 lease stamp、自己的列表与 view slot；不能仅凭 restore[0] 非零撤回他人视图。

整个 RV_STORAGE、RV_PREVIEW、RV_SETTINGS 写入、RPC W 和未知 X 页被服务分发表拒绝。最终不链接 file open/read/write/create/rename/delete、storage mark、preview 和产品 blackbox。resident 为加载 DAT 进行只读 open/read/close 不计作探针文件写入。

## 测速和验证合同

沿 PROBE_SPEC：完整 17³ Q8.8、1024 B coord、确定种子、guard、IRQ 前后检查；准入 N=4/64/512/4096，每个 callback 一档，仅上档不超过 reference_delta/1200 才升档，软预算 reference_delta/600。D 为 2^14/2^16/2^18/2^20。每种 E/D/L17、至少两个长度各至少三次；交错 E/L 和 L/E，记录首次与后续调用。预算结束检查不等同硬抢占。净差不足 16 ticks 标 LOW RES，不给物理 MHz。

主 lease 含映像、BSS 和 resident overhead，为 61072 B；工作缓冲另用 usage 4 的 16392 B lease，含 4096 对像素与两端 guard。每块核对 lease、范围与不别名。没有把任一 lease 上限调高。准入 8 条和正式 48 条样本均保留原始字段；旧版中超过 65536 B 的合并分配不沿用。

尚未满足完整 PROBE_SPEC：冻结 v3.6 的 epoch 在 rv_reset 初始化，未见自然模式切换、休眠事件更新 RV_MODE_E/RV_POWER_E。review_lifecycle.py 又核对真实 ELF 仅有 H01/H02/H05–H09 执行入口，禁用的 mode/sleep 窗口仍为官方字节。本版能拒绝参考期间可见的 MENU/H06/H01/H08 异常以及注入的 epoch 变化，不能证明所有真实模式切换或休眠都会触发失效。CPU 部分因此只是候选。墙钟公式会拒绝相互差异超过 5% 或偏离名义 1 ms 超过 5% 的参考，但这不能替代休眠事件检测。

构建需证明 v3.6 loader 选择实际 DAT，header 与 payload CRC、长度、PIC translation、所有重定位和 ABI；从最终 DAT 还原的机器码跑真实 H01/H07/H08。P1 覆盖 49 组合法游标、0/8..13/255、错误表/行数/view、glyph 与分配故障、capture 之前状态改变、重入、epoch/语言变化和精确撤回。所有基线地址逐字节不变；非 50mm 无 RPC、无单元写入；强制 storage 和 W 被拒绝。任何没有执行的要求在 REPORT 标明，不能用 Host 或设备替身代替。

本版不含颜色写入，因此“写失败后源和镜像恢复”不适用，不能报告为已通过。断电丢失仅涉及私有结果与 UI 状态；不触碰任何持久单元参数，也不假设相机电源故障已验收。
