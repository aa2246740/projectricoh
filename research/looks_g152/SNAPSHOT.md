# 首次事务的实际此前状态

`g.live` 初始化时含原厂 04 模板。未建配方基线时，只有当前事务成功捕获并验证的 `g.live` 才能用于本次补偿；`live_verified` 的旧值不能给下一次事务授权。`baseline` 表示已有可信的配方基线，两者含义不同。

复审 P1-01 修复后，未建基线的快照在 `apply_impl` 开始时过期，目标计算成功后必须重新读取实际九行/T；同一事务结束时再次撤销资格。`eng_require_recheck`、菜单关闭/重开、失去归属、失效和重绑定边界也撤销未提交快照的资格。`t_checked`、`t_pending`、`neighbor_valid` 一并过期，`snapshot_fault` 和 uncertainty 保留。首次 op 6 拒绝后、写 S BUSY 补偿后及退出后，未建基线的 `live_verified` 都必须为 0。

`validate_live` 不再用未提交快照恢复配方；有可信基线时，无论是否已提交选择，都在菜单重开时比较实际行。确认入口同样要求可信基线。当前/确认配方引用、一次性的记忆配方提示和 `s_refused` 恢复策略都不授予未提交快照跨事务资格。

首次应用先算出目标，再通过原有 RPC 读回实际 T 和九行。T 只接受 0 或 2，十条展开行按正式效果行规则校验。随后再读一遍，要求每个自有字节与 T 相同，epoch 和界面归属仍有效，才重算行 CRC 并设置 `live_verified`。读取只复制自有行中的字节，不把奇地址行旁边的字节纳入快照。

S 的预检查通过后，若写 S 才遇 BUSY，事务从快照写回全部九行和 T，并逐字节读回。成功才清 uncertainty 并普通拒绝。没有可信快照、快照不稳定、行格式不符或补偿失败时，事务锁存 `snapshot_fault` 和 uncertainty，界面显示 ERR；普通重试和确认态恢复不会清掉这个错误。

观测快照只用行结构规则，不套用目标效果的 T/C/D 尾值关系。原厂启动可能是标准九行配 T=0；这仍是可读回、可比对的真实此前状态。原始 `t-boot` 回归在前一候选上发现这一校验边界，最终包用未改的旧用例在两个单元专项复跑，结果见 `evidence/t0-*.json`。

普通 BUSY 拒绝也会保留实际 S。`s_refused` 阻止退出和重开边界把此前设置自动归一化到当前配方模板；新有效目标计算成功后才重新允许设置同步。矩阵在按键、退出、重开三个时点都逐字节要求 S 等于真实此前状态，不再接受模板的另一份 S 作为例外。

`legacy/previous_state_checks.py` 是复审原文件的逐字复制。其 late 分支断言第三种状态出现，因此修复后该旧断言必须失败。`unverified_checks.py --original late` 记录这个结果，并独立断言实际 02 九行、T=2、S=4 保留，退出再打开仍相同。held 和 idle 分支保留原期望。

正常合同检查分别把 02、效果 1、效果 2、效果 3 的完整行与 T 作为明确的单元模型输入，S=4。这样可以验证四种来源与目标组合的首次事务。真实菜单第一次到达效果前会经过内置预览，因此这里在原生按键到达 `uv_preview` 的函数边界提供目标参数；效果目标转入现有 `uv_effect`，不预置引擎或界面变量。该组证明未建基线的事务合同。`lock_checks.py` 另用真正的菜单方向键和 OK 建立来源身份，证明物理 Looks 导航中的四种切换。两组证据的范围分别记录，不能互相替代。

复审入口如下；是否通过以各 JSON 的实际状态和最终 `REPORT.md` 为准。

| 范围 | 回执入口 |
|---|---|
| 原始非原厂 late 用例 | [50mm](evidence/unverified-50mm-original-late.json)、[MOUNT](evidence/unverified-mount-original-late.json)；复制源的 SHA256 及旧断言位置一并记录。 |
| 未建基线的四种切换 | `evidence/unverified-{50mm,mount}-{builtin-effect,effect-same-base,effect-other-base,effect-builtin}-late-*.json`，共 8 条。 |
| 捕获或补偿失败 | [50mm 捕获](evidence/unverified-50mm-effect-other-base-capture-fail-ok.json)、[MOUNT 捕获](evidence/unverified-mount-effect-other-base-capture-fail-ok.json)、[50mm 补偿](evidence/unverified-50mm-effect-other-base-restore-fail-ok.json)、[MOUNT 补偿](evidence/unverified-mount-effect-other-base-restore-fail-ok.json)。 |
| 快照格式与稳定性 | [格式不符](evidence/unverified-50mm-effect-other-base-capture-invalid-ok.json)、[二次读取变化](evidence/unverified-50mm-effect-other-base-capture-race-ok.json)；均要求 W=0、ERR 和 uncertainty 保留。 |
| 当前态与确认态 | `evidence/lock-reviewfix-{50mm,mount}-*.json` 的 48 项最终矩阵逐字比较引用及实际状态；独立身份组保留旧回执，未计为本轮新 DAT 执行。 |
| 跨退出两次事务 | `review_fix/evidence/after-refusal-{50mm,mount}-{4,8}.json`，分别变成实际 04 与 08，late BUSY 后核对真实此前九行/T 和完整 S。 |
| 同类变体 | `review_fix/evidence/{effect,multiple}-{50mm,mount}-state.json` 与 `photo-final-{50mm,mount}.json`；变成效果、原生半按后模拟拍摄恢复单元行、连续拒绝后再成功。真实快门与单元 ISP 不由本模型执行；半按后的旧行数元数据不作为归属断言。 |
| 独立稳定性用例 | `review_fix/evidence/snapshot-race-{mount-T,50mm-rows}.json`，原复审函数从逐字副本执行，要求 W/S 零写且 ERR/uncertainty 通过三种退出保持。 |
