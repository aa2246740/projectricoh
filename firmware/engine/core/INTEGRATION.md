`eng_core.h` 保持委派时的签名。核心内部用 `EngPort`，生产入口将它绑定到 init 收到的 `RvApi` 表；所有服务调用都经保存的 `api->call`。服务实现位于 `firmware/resident_slim/engine_services`，作为引擎内部库，服务编号与语义沿用冻结 ABI。core 不依赖服务的代码位置，也不直接调用原生地址。当前测量含 core、完整容器语义与 R2 微调，不含 panel、GXTS、服务库；合并链接由主任务处理。

## 加载合同

1. 加载门采用 48 KiB 文件上限与 32 KiB 总 engine 上限，校验原始文件、入口、内部重定位、身份和三单元 CRC pin。总 engine 包括 core、panel、GXTS、服务库、容器语义，不给每部分各分配 32 KiB。
2. resident 将源重读到最终私有 lease，复验后重定位、清 BSS、同步代码。
3. resident 调用 `eng_bootstrap`。`args[10]` 指向可写的 40 B `RvEngineEntries`，`args[11]=40`。输出都是整个容器内的偏移。
4. resident 验证九个入口后，调用 init。`args[10]` 指向 44 B `EngInitWire`，`args[11]=44`。`gate_view_address` 指向真实 gate 产生的受保护 C view，`gate_view_bytes=sizeof(Gxr2View)`。这个 view 是本机结构，不是从文件反序列化的 wire。
5. `image_address/image_bytes` 必须与 view 的私有 image 相同。view 在 init 期间有效；image、code、BSS 和 UI lease 保留到会话结束。单元换代只撤绑定，不释放代码。
6. core 调用上游完整语义层，检查旧 stock entry CRC 和当前单元 pin，并只读启动 T。resident 在 init 成功及全部能力检查后最后批准 READY。

init 不写 S、不发 W、不写文件、不调用 native UI。有效非 2 的启动 T 只记为待修复，首次安全菜单才 X/V/W/V 修复；这同时满足纯 init 和 Stage2l 的启动修复要求。失败 X/V 留待下一安全菜单重试。

非存储服务保留 `RvRequest.args[0..7]` 的 context、lease 和六个预期代次。入口适配把间接栈缓冲拷入 engine BSS 的 80 B scratch，避免把普通任务栈伪装为受理 lease。owner、能力、task、代次、在途代码生命和返回复核的语义不变，具体检查随服务库与 slim resident 的分工集成。

`RvApi` 表和它的 dispatch 在整个会话有效；init 保存表指针，后续入口拒绝另一个表指针或 context。服务库可以随 engine 重定位，core 不缓存原生函数地址。主机入口测试由传入的 mock API 处理全部调用，并验证换表后在服务执行前拒绝。

## CRC32 绑定

`eng_semantic.c` 直接包含只读的 `card_container_v2/semantic.c`，通过 `eng_crc_bindings.h` 将 `gxr2_sha256` 绑定到 `eng_crc_binding`。后者只算 CRC-32/ISO-HDLC，输出 `BE32(crc) || 28*00`。`common.c` 直接链接，不链接 `sha256.c`。

现有 32 B 绑定字段保留宽度，含义改为上述 CRC tag。容器模块目录 `+32..63` 也必须由打包器写成 CRC tag。旧 SHA tag 会被拒绝。主机脚本保留 SHA256SUMS 和来源 SHA，主机审计不属于相机运行代码。

`rv_unit_pin(uint8_t unit)` 的弱桩只返回下列常量，不做服务调用，unit 为 0..2。常量来源由常驻层负责人决定；若后续改成服务查询，也必须经 init 的 `RvApi`，不能导入裸代码地址或自行增加冻结服务编号。

| unit | 身份 | map128 拼 stock410 的 CRC32 | 旧 stock entry448 CRC32 |
|---:|---|---|---|
| 0 | jlaunch，0151/0000 | df2bcaf5 | 0d2b0ea9 |
| 1 | qlaunch，0151/0000 | 6700e6ff | 341ddbee |
| 2 | l08firm，0151/0000 | 1b3c7000 | 4686301b |

完整语义层验证全部三单元的 CRC tag。core 在 READY 前再以流式 CRC 核对当前单元，并单独验证展开后的三个 stock entry CRC。两个 CRC 口径不互换。

panel 编译 `gxts.c` 时可使用同一适配：

```sh
-include /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/firmware/engine/core/eng_crc_bindings.h
```

链接 `eng_crc_compat.c` 和上游 `common.c`，排除上游 `sha256.c`。GXTS 的 layout、table、algorithm 绑定须统一采用 CRC tag；旧 SHA 绑定记录不能沿用。这个链接由 panel/storage 集成执行，本任务没有写它们的目录。

## 列表、参数和退出

列表保持 16 行，unit 为 0..2，slot 为 1..16。`EngTweak.v[]` 按 GXTM 的实际 param_id 表解释；活动 ID 为 1..6，两个 ID=0 的保留位必须为零。R2 算法内部的 0..5 索引不作为 wire ID。

native event adapter 的 `args[8]` 使用本引擎局部事件种类，`args[9]` 为选择值：1 选槽、2 关闭列表、3 作废绑定、4 重新绑定。物理按键 0x25/0x22 及 resident hook 到这些局部事件的翻译仍由 resident/panel 集成处理。

apply_step 接受 `args[8]=param_id`、`args[9]=int32 value`，也接受 `args[10..11]` 指定完整 8 B `EngTweak`。所有值都从不可变基础条目重算。相同提交向量不会重复请求预览；不同向量只写有变化的深层行和实际有变化的 S 字节。

影调和饱和的已实现范围为 ±8。WB 可接受元数据声明的 signed8 范围，先把基准加编辑值，再限幅到原生 ±8，编码为 1..17。`EngPort.wb[]` 只供经过验证的 lane/sign 元数据适配；当前 GXTM 没有这些字段，因此 native init 拒绝伪造绑定，非零冷暖/色调应用返回 ENG_REJECTED。零编辑保留 canonical WB 字节的原顺序。

slot4 的范围必须允许零向量，保证退出可恢复真正 stock；Default 仍返回各槽元数据的默认值。`eng_restore_stock` 使用当前私有 RAM 的 stock，经正常事务恢复零向量，不读卡。shutdown/abort 先撤 UI，再尝试这次有界恢复；uncertain 时不重试 W，返回 RV_FAULT。resident 必须把该结果翻译到已审的原生失败分支。

bootstrap 的三个 panel 入口目前指向 `panel_unlinked`，返回 RV_UNSUPPORTED 和 CLOSE_AND_PASS。集成时用 panel worker 的入口替换它们；不能把这三个入口当成已完成的面板。

## 颗粒发布

`EngInitWire.grain_address/grain_bytes` 指向 resident 明确授予的 32 B `EngGrain`；零地址关闭发布。core 不猜 root.flags 的归属，也不直接使用固定 root 地址。resident_impl 需给这个快照分配明确的 root 字段，并按 epoch 和临界区规则读写。

事务开始先清 armed；W 尝试前置 sticky uncertain。S、预览请求和 release 都成功后才发布新 identity、向量、阶段和颗粒快照。失败保留实际阶段，不发布新 applied_slot。

`eng_grain.c` 是独立的常驻捕获门实现。resident 可把这份 C 链进常驻代码；H09 不得回调堆上的 engine。捕获时需在 resident 的快照/epoch 临界区调用它。它只检查已提交快照和 packet/S 字段，不访问文件、RPC 或堆引擎状态。

## 构建边界

`build.py --data-bytes N` 的 N 为七 section 中 engine 和 relocation 以外的数据总字节，不含 256 B 头。BSS 的 GOTOFF 常量取决于最终文件长度，因此实际打包必须按最终数据大小重新链接。不能把默认最坏数据预算的 engine 段放入另一长度容器。

默认 N=24960，对应容器 worker 已验证的 25216 B 数据底座，含头。构建产生测量 ELF、engine 段和 relocation 段，均在 local/，不产生 DAT、SD_ROOT、固件更新包或卡目录。`engine.ld` 严格限制总 engine 32768 B、容器 49152 B、BSS 4096 B。

48 KiB 文件门另算：最坏数据底座占 25216 B，留给总 engine 加 relocation 的空间为 23936 B。报告同时列出 32 KiB 代码门余量和 48 KiB 文件门余量；服务库与 panel 合入后，必须同时满足两者。标准 PIC 的对象贡献来自实际链接 map；LTO 跨文件内联，只报告整个 core 交付范围的实测值，不按源文件虚分。

两次平移链接逐字节一致，且所有入口 4 B 对齐、位于 engine 内。当前 runtime relocation 为零；GOTPC、GOTOFF、内部相对分支在静态链接时解析。完整 panel/GXTS 链接后仍须重跑最终大小、重定位和无 SHA 审计。

## card_container_v2 需要配合的修改

- `gxrce.h`、`gate.c`、`pack.py` 的文件/engine 上限从 32768/10240 改为 49152/32768，更新对应拒绝测试和预算说明。core 已测得 32768 B engine 形状在完整语义层通过，32772 B 在接入门拒绝；旧上游 gate 对新尺寸形状仍会拒绝。
- 打包器和信任交换格式把模块目录原 SHA 单元改为 CRC tag，并将字段名及格式说明改为 CRC 含义。保留 map+stock CRC 和 stock entry CRC 两个独立口径。
- 语义层原生改为 CRC32 后，可去掉本任务的编译别名和 32 B 兼容 tag。变更字段宽度前仍须统一目录、trust、GXTS 和外部 ABI 标识。
- GXTS 的三种绑定改为 CRC32，明确旧记录失效规则。禁止把 `sha256.c` 带入相机链接。
- resident gate 与 engine 使用同一份受保护 Gxr2View 布局及最终 CRC 许可。重新生成与发布实际 resident/ABI 标识，不能用 host fixture 标识作产品许可。
