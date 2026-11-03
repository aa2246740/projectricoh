停止实施：保留既有完整回归所要求的 Fn2 行为时，存在必须在 H07 通信的状态，未产出 gen 120 候选。

P1-01、P1-02 均未修复，A/B/C 未闭合。本轮未改配方包，也未改 resident；只在 `research/ux_preview_dot_r4` 写入可重跑的验证脚本和证据。遗留风险仍是 gen 119 的菜单并发收尾、首次 W 前持续失败提示及 `rv_call` 编译改码缺口；上一轮 `engine_v41_ux` 诊断版本仍未通过验收，不能作为本轮候选。已按用户指定的停止条件交回决定。

## 阻断状态：Fn2 已改草稿，但尚未确认

“高亮配方就是当前生效配方”只覆盖配方列表，不能推出 Fn2 数值草稿也已在单元生效。冻结 gen 119 和上一轮草稿中的实现相同：

1. H08 把 05 应用为完整配方，Fn2 打开 11 行数值页。
2. 对比度从 0 移到 +1 时，`a4_move` 只更新 `p->draft`、光标和绘制；它不调用 `eng_apply`。单元仍为对比度 0 的完整 05。
3. OK/ADJ 进入 H07 后，`ig_event` 才调用 `a4_finish(&n.panel, 1)`；后者执行 `eng_apply(&p->recipe, &p->draft)`，成功后才把草稿复制到 RAM 缓存及 `p->committed`。
4. 此时草稿与当前 tweak 不相等，`eng_apply` 的元数据快速路径不成立，必须进入 `apply_impl` 写入曲线并预览。

若 H07 只做 `confirmed = live`，这次 OK/ADJ 会保留对比度 0，丢掉用户选定的 +1，违反完整回归中的 Fn2 RAM 微调要求。这不是错误或不确定状态，而是正常可达的 Fn2 编辑状态。

[静态证据和两代最终 ELF/DAT 绑定](static-fn2.json) 保留了逐函数源行及机器调用点。gen 119 的关键位置为：`a4_move=0x6018`，H07 的 Fn2 分支在 `0x8B6C` 调用 `eng_apply=0x545C`；`0x54C4` 比较当前 tweak 与草稿，`0x54C8` 在不相等时转到事务路径，`0x5520` 调用 `apply_impl=0x42AC`。上一轮草稿的对应调用点为 `0x8C34→0x5508→0x55CC→0x4358`。PC 为各 ELF 内相对地址，原生记录另保留实际加载地址。

## 三单元真实原生对照

每例都从正常冷开、原生 Image 构造器及原生箭头进入 05，再打开 Fn2 并把对比度从 0 改为 +1。箭头阶段均为零 RPC、零预览，九行及 T 仍等于修改前的完整 05。确认及半按均执行原生按键路径，没有手工设置正常菜单、光标或 resident 状态，`0x20271FEC` 固定返回替身不存在。

下表计数仅覆盖编辑后的退出按键，格式为“RPC / W / preview”：

| 单元 | OK，最后为 +1 | ADJ，最后为 +1 | 半按，最后仍为 0 | 证据 |
| --- | ---: | ---: | ---: | --- |
| 50mm / jlaunch | 42 / 34 / 1 | 42 / 34 / 1 | 0 / 0 / 0 | [原生记录](native/fn2-contract-50mm.json) |
| 28mm / qlaunch | 42 / 34 / 1 | 42 / 34 / 1 | 0 / 0 / 0 | [原生记录](native/fn2-contract-28mm.json) |
| MOUNT / l08firm | 42 / 34 / 1 | 42 / 34 / 1 | 0 / 0 / 0 | [原生记录](native/fn2-contract-mount.json) |

九个场景均核对完整九行、T 与当前配方预期，而非只读 RAM 元数据。OK/ADJ 每例都记录到一个 H07 配方事件和后续真实事务；半按每例都没有新的配方入口、RPC、W 或预览，仍保留未编辑的完整配方。[文件观察](file-observations.json) 中 create、write、rename、delete、write-mode open 五项计数均为 0；这只说明本次九个原生场景，未代替新候选的完整文件审计。

执行的是冻结 DAT、v3.6 resident 和原生菜单的 M32R 指令。单元通信响应、文件系统、字体资源、绘制提交及部分系统边界仍是模型；沿用既有 CRC-32 等价计算边界。没有触碰相机或存储卡，也没有实机结论。

## 为什么不能直接提前到箭头应用

既有完整回归还明确要求放弃未确认的 Fn2 草稿。`fn2_half_exit` 在已保存对比度 +1 时，再把草稿移到 +2，半按后立即核对单元仍为 +1，随后重开和浏览仍使用 +1。原始用例及哈希已绑定在 [static-fn2.json](static-fn2.json)；本轮用 0→+1 的独立原生对照验证了同一条放弃路径。

若改成箭头立即把草稿写入单元，半按后将保留新值；本轮原生记录证明这条退出路径没有新的配方回调来恢复旧值。等到下一次 H01 再恢复，也不能满足“半按后立即仍为旧值”的原有断言。因此，提前应用需要同时改变 Fn2 的退出语义，不能把修改该断言后的结果计为原完整回归继续通过。

| 处理方式 | 结果 |
| --- | --- |
| 继续只改 RAM 草稿，H07 接受当前 live。 | 零通信，但 OK/ADJ 不再应用选定微调。 |
| 箭头立即应用，H07 接受当前 live。 | OK/ADJ 可零通信，但半按不再丢弃未确认草稿。 |
| 保留当前微调确认和半按放弃行为。 | 脏草稿在 OK/ADJ 的 H07 中仍需通信，触发本轮停止条件。 |

需要由用户选择是否允许“Fn2 箭头立即生效、半按也保留 live”，或保留原交互并调整 H07／resident 的约束。本轮没有擅自改变这项行为。

## 其它状态与未继续的工作

| 状态 | 静态结论 | 本轮边界 |
| --- | --- | --- |
| 冷开停在 04，直接 OK/ADJ。 | 单元是完整原厂 04，可设计为只确认 04 元数据。 | 没有实施新分支。 |
| H08 成功后的普通列表。 | `current/live/tweak` 已指向实际生效项，可设计为只确认元数据。 | 没有实施新分支。 |
| 预览失败且补偿成功。 | `recover_confirmed` 经实际事务更新 current/live 和光标；应接受补偿后的实际值。 | 没有重跑新候选。 |
| 首次 W 前持续失败。 | 可保持完整 04 并锁定提示；仍须把实际返回的 `ENG_REJECTED` 纳入处理。 | P1-02 未改码。 |
| 部分写入后持续失败。 | 只能维持既有不确定锁定，不能确认一个未经核实的 live。 | 未改现有路径。 |
| Fn2 打开但未改草稿。 | 已有应用的草稿与 live 相同，确认可纯元数据化。 | 不代表已编辑草稿也可如此处理。 |
| Fn2 已改草稿。 | 若保留上述完整回归，OK/ADJ 必须应用不同于 live 的值。 | 已由三个单元的 OK、ADJ、半按对照核实，决定停止。 |
| 28mm 首次未 ready。 | 配方包尚未发布，原生七行页由原生路径处理；第二次 ready 后回到冷开 04 情况。 | 这是源代码检查，未另计为本轮原生用例通过。 |

由于静态前提不成立，本轮没有签署“H07 所有调用均无让出点”，没有继续改 finish/ui_finish，也没有构建 `engine_v42_ux` 或 `package_v36_g120b`。完整菜单切换矩阵、gen 120 的零文件写入机器审计、A/B/C、`rv_call` 遗留项和 `start_view` 均未继续，状态为 INCOMPLETE。Fn2 上一轮已经通过的并发保护保持原文件不变，但没有被本轮重新宣称为新候选验收。

## 输入身份、只读范围和复跑

| 输入 | SHA-256 或身份 |
| --- | --- |
| gen 119 DAT | `d11e88eae677f7ee3aeba4dc602c2085ef92b9c81f5c70286c8eb038211e4bbc` |
| 上一轮诊断 DAT，仅静态对照 | `b22928a818c02d2e2534164853f83f587ae06341390fe4059b5efb0e7dcf64ed` |
| v3.6 ilaunch3 | `50720c80696ca88f25dc25a85285acd0e0f19906e1d7da1dd404f6cc243f9008` |
| resident build id | `b779cc756a740506415ca5df8eb5c8f08e1b04ea9d8c4c614f7ae971e92b94f7` |
| resident ABI | `d7387c3670059c325186de3af1b3d5c6` |
| 官方 ZIP | `3705984b8433c40d2ed4fd2600c11f03ed8a6de7dbe7f66efd38ee5ca15fc898` |
| ZIP 内原版 ilaunch3 | `da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7` |

外置盘的 APFS、挂载状态及卷 UUID 已核对。既有 g120 包保持只读；为本轮预留的 g120b 没有创建。输入清单先核 SHA，再读取；r3 研究、v41 构建树、既有 g120 包、g119b 和 g117 r2 的清单逐项通过，见 [input-manifests.json](input-manifests.json)。

本轮冻结的 40,581 个既有文件前后哈希相同，见 [input-integrity.json](input-integrity.json)。 Python 写入审计钩子把路径限定在题定三个目录；本轮实际仅写研究目录。未编译或链接固件，未启动子代理，未使用等待循环。命令输出及源文件哈希保存在 [commands](commands)，脚本来源见 [harness-provenance.json](harness-provenance.json)。

复跑原生对照：

```sh
/usr/bin/python3 -I -B research/ux_preview_dot_r4/fn2_contract.py 50mm
/usr/bin/python3 -I -B research/ux_preview_dot_r4/fn2_contract.py 28mm
/usr/bin/python3 -I -B research/ux_preview_dot_r4/fn2_contract.py mount
```

[停止状态](task-stop.json)、[SHA256SUMS](SHA256SUMS) 和 [自检结果](manifest-selfcheck.json) 保留本轮结论。清单逐项重读重算，不包含自身。
