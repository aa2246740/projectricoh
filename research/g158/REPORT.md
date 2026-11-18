可以交复审（M/S 首次 ADJ 为模型边界，待现场确认）

# g158 验收补齐

本轮只补验收。两包 SHA、产品源码、配方、机身 v3.10 a04f1ed4 和 resident 都保持不变。test 代码区仍为 69,624/69,632 B，只余 8 B。原有 g158 门仍保留旧许可，并增加 M04/U00–03 与各自实测 N 的精确匹配；release BOOT 仍关闭。

本轮开始 2026-11-05 05:03:27 UTC，当前截止 2026-11-05T08:03:27+00:00。最新回执 2026-11-05T07:33:57.777642+00:00。全部 nice15。调度前段按原 load1 门；机主于本日批准后改用 `tools/loadgate.py` 的 iostat CPU idle、空闲内存和保留两核规则，每次调用最多启动一个新进程，单队列最多六个。`load.jsonl`、`admissions.jsonl` 保留完整采样 info。

原有两个参考 P1 进程先自然结束，随后恢复未完成队列；未向它们发送终止或暂停信号，也未重复启动。切换记录见 `local/accept-r2/loadgate-transition/`，最终调度审计见其 `verification.json`。只改变调度，所有输入、断言和检查精度保持不变。本轮未做速度比较；运行时长仅用于调度日志，后续计时实验必须使用 `loadgate.quiet_for_timing()`。

| 包 | SHA-256 | DAT B | 代码 B | 主请求 B | 预算余量 B |
| --- | --- | ---: | ---: | ---: | ---: |
| test | `6a40262c3fc5b94e7152012c655f5c7d2dc98bf6186cf3e80d2429b76f45fcee` | 94,952 | 69,624 | 106,940 | 672 |
| release | `756d5840da9d0393f29411a4f8f61c7e2bb88fb546c814b316982ca8c7cb24f6` | 92,484 | 67,392 | 104,472 | 3,140 |

本轮关键回执：原生29条完整回归 6/6；MOUNT参考整机P1 2/2；S重放 48/48。各项只有完整断言通过才计数。

主请求上限仍为107,612 B。预算余量不代表真实可用堆。本轮相对已封存 g158 的 DAT 差异为0 B；相对 g157 r1 的旧审计保持有效：两包各增加84 B，差异位置82,381/80,110均由模式门、代数、重定位和校验解释，未解释字节0。全部552 B配方逐条相同。

## slot31 与现场旁证

[SLOT31.md](SLOT31.md)记录原厂快门/光圈曝光参数路径。返回值是参与曝光换算的有符号数量；单元会更新曝光状态并按实时状态和校准量计算，不能统一填一个成功值。完整固件地址、原厂文本和派生表只在被忽略的 `local/accept-r2/slot31/`。

本轮没有给模型补造成功回执，也没有修改产品以绕开原厂请求。六组只读冷启动对照的实际结论见 `local/accept-r2/slot31/verification.json`；MODEL_BOUNDARY 表示已定位严格模型缺项，不表示首次 ADJ 成功。

机主报告的 g157 test 实机旁证：M/S 冷启动首次 ADJ 都正常，B11 诊断后能返回列表；M 档手动套用后再开 ADJ 全天正常。两条流程使用同一个原厂曝光路径，颜色 S 写计划不包含该路径的快门/光圈输入。BOOT 先于第一次原厂菜单初始化写颜色，手动套用发生在菜单已经建立之后，单元初态的先后仍有区别。当前模拟器从已声明 AUTO 输入冷启动，在 BOOT 派发边界声明 M/U/N，没有重建物理 M/S 下的单元完整曝光启动。g157 旁证不能替代 g158 BOOT 后首次 ADJ 的现场结果。

## 验收回执

| 项目 | 状态 | 范围 |
| --- | --- | --- |
| 静态解析、全部配方与布局 | PASS | 实际 C parser；156 条完整记录；机身/resident 和 arena。 |
| 模式门全部 uint8 模式/子模式与 N 边界 | PASS | 实际旧/新 C 门；原许可保持，仅新增四个实测组合。 |
| P1 全写入矩阵 P | PASS | 实际产品 C/math 和新门；声明 peer/services；每个 W 的写后回执错误/BUSY，逐 S 字段与持续故障。 |
| P1 全写入矩阵 A | PASS | 实际产品 C/math 和新门；声明 peer/services；每个 W 的写后回执错误/BUSY，逐 S 字段与持续故障。 |
| P1 全写入矩阵 M | PASS | 实际产品 C/math 和新门；声明 peer/services；每个 W 的写后回执错误/BUSY，逐 S 字段与持续故障。 |
| P1 全写入矩阵 S | PASS | 实际产品 C/math 和新门；声明 peer/services；每个 W 的写后回执错误/BUSY，逐 S 字段与持续故障。 |
| BOOT 独立补偿矩阵 | PASS | test 的 BOOT C 编排；共享 deep/readback，但不调用 apply_impl/recover_confirmed。release 策略关闭。 |
| 最终 DAT 指令 test/c | PASS | MOUNT，四个实测子模式的关键故障点与实际 H52；声明 services/peer；完整全 W 另由 C 矩阵覆盖。 |
| 最终 DAT 指令 test/python | PASS | MOUNT，四个实测子模式的关键故障点与实际 H52；声明 services/peer；完整全 W 另由 C 矩阵覆盖。 |
| 最终 DAT 指令 release/c | PASS | MOUNT，四个实测子模式的关键故障点与实际 H52；声明 services/peer；完整全 W 另由 C 矩阵覆盖。 |
| 最终 DAT 指令 release/python | PASS | MOUNT，四个实测子模式的关键故障点与实际 H52；声明 services/peer；完整全 W 另由 C 矩阵覆盖。 |
| 原生 P 档关键流程 test/50mm | PASS | 新门 P 档，Acros 单记录、读回、DISP、OK/ADJ 关闭再开；全 29 条回归另列。 |
| 原生 P 档关键流程 test/28mm | PASS | 新门 P 档，Acros 单记录、读回、DISP、OK/ADJ 关闭再开；全 29 条回归另列。 |
| 原生 P 档关键流程 test/mount | PASS | 新门 P 档，Acros 单记录、读回、DISP、OK/ADJ 关闭再开；全 29 条回归另列。 |
| 原生 P 档关键流程 release/50mm | PASS | 新门 P 档，Acros 单记录、读回、DISP、OK/ADJ 关闭再开；全 29 条回归另列。 |
| 原生 P 档关键流程 release/28mm | PASS | 新门 P 档，Acros 单记录、读回、DISP、OK/ADJ 关闭再开；全 29 条回归另列。 |
| 原生 P 档关键流程 release/mount | PASS | 新门 P 档，Acros 单记录、读回、DISP、OK/ADJ 关闭再开；全 29 条回归另列。 |
| 原生完整回归 test/50mm | PASS | 旧许可 AUTO；已逐条验过 29/29，整组还要求光标/DISP、OK/ADJ 关闭再开。PASM 新路径单列。 |
| 原生完整回归 test/28mm | PASS | 旧许可 AUTO；已逐条验过 29/29，整组还要求光标/DISP、OK/ADJ 关闭再开。PASM 新路径单列。 |
| 原生完整回归 test/mount | PASS | 旧许可 AUTO；已逐条验过 29/29，整组还要求光标/DISP、OK/ADJ 关闭再开。PASM 新路径单列。 |
| 原生完整回归 release/50mm | PASS | 旧许可 AUTO；已逐条验过 29/29，整组还要求光标/DISP、OK/ADJ 关闭再开。PASM 新路径单列。 |
| 原生完整回归 release/28mm | PASS | 旧许可 AUTO；已逐条验过 29/29，整组还要求光标/DISP、OK/ADJ 关闭再开。PASM 新路径单列。 |
| 原生完整回归 release/mount | PASS | 旧许可 AUTO；已逐条验过 29/29，整组还要求光标/DISP、OK/ADJ 关闭再开。PASM 新路径单列。 |
| PASM 首次待机实际颜色 P | PASS | 快后端新 MAIN；在首次 ADJ 前读取实际九行/T。不是 JPEG 或实机照片。 |
| PASM 首次 ADJ 整机 P | PASS | 四个实测 N 组合；不替换未声明的单元请求。 |
| PASM 首次待机实际颜色 A | PASS | 快后端新 MAIN；在首次 ADJ 前读取实际九行/T。不是 JPEG 或实机照片。 |
| PASM 首次 ADJ 整机 A | PASS | 四个实测 N 组合；不替换未声明的单元请求。 |
| PASM 首次待机实际颜色 M | PASS | 快后端新 MAIN；在首次 ADJ 前读取实际九行/T。不是 JPEG 或实机照片。 |
| PASM 首次 ADJ 整机 M | MODEL_BOUNDARY | 四个实测 N 组合；不替换未声明的单元请求。 六组 BOOT 开/关对照与原厂曝光代码已定位；原始同 SHA 冷启动回执及请求参数逐项匹配，严格模型仍停止，未补造回执。 |
| PASM 首次待机实际颜色 S | PASS | 快后端新 MAIN；在首次 ADJ 前读取实际九行/T。不是 JPEG 或实机照片。 |
| PASM 首次 ADJ 整机 S | MODEL_BOUNDARY | 四个实测 N 组合；不替换未声明的单元请求。 六组 BOOT 开/关对照与原厂曝光代码已定位；原始同 SHA 冷启动回执及请求参数逐项匹配，严格模型仍停止，未补造回执。 |
| 拒绝域诊断 SCENE-domain | OPEN，补充项 | raw01 是合成非许可域，原厂菜单未进入；不能把它当作实测 SCENE 码或声称出现过诊断页。实际编码按用户约定保持现场 OPEN。 |
| 拒绝域诊断 MY-domain | PASS | 声明的 SCENE 非许可域、MY 和未知子模式反例；实际 SCENE/MY 内部编码尚未现场采样。 |
| 拒绝域诊断 unknown-submode | PASS | 声明的 SCENE 非许可域、MY 和未知子模式反例；实际 SCENE/MY 内部编码尚未现场采样。 |
| g157 记忆拒收 test | PASS | 当前 g157 r1 的 03 与官方 Acros 高索引记录；保持原生颜色。 |
| g157 记忆拒收 test-high | PASS | 当前 g157 r1 的 03 与官方 Acros 高索引记录；保持原生颜色。 |
| g157 记忆拒收 release | PASS | 当前 g157 r1 的 03 与官方 Acros 高索引记录；保持原生颜色。 |
| g157 记忆拒收 release-high | PASS | 当前 g157 r1 的 03 与官方 Acros 高索引记录；保持原生颜色。 |
| 主机 Look 记忆 c | PASS | 108 个 Look 的实际指令构建/解码。 |
| 实际 op5 test/c | PASS | 真实服务权限/锁/IRQ；声明合法 part=1/task=0。不是 NAND 提交证明。 |
| 实际 op5 release/c | PASS | 真实服务权限/锁/IRQ；声明合法 part=1/task=0。不是 NAND 提交证明。 |
| 主机 Look 记忆 python | PASS | 108 个 Look 的实际指令构建/解码。 |
| 实际 op5 test/python | PASS | 真实服务权限/锁/IRQ；声明合法 part=1/task=0。不是 NAND 提交证明。 |
| 实际 op5 release/python | PASS | 真实服务权限/锁/IRQ；声明合法 part=1/task=0。不是 NAND 提交证明。 |
| 参考整机 reference-test-AUTO | PASS | 独立 Python 设备/指令，新 MAIN；旧许可 AUTO。PASM 参考另列。 |
| 参考整机 reference-release-AUTO | PASS | 独立 Python 设备/指令，新 MAIN；旧许可 AUTO。PASM 参考另列。 |
| 参考整机 reference-P1-test-AUTO | PASS | 独立 Python 设备/指令，新 MAIN；旧许可 AUTO。PASM 参考另列。 |
| 参考整机 reference-P1-release-AUTO | PASS | 独立 Python 设备/指令，新 MAIN；旧许可 AUTO。PASM 参考另列。 |
| PASM MOUNT 参考关键路径 P | PASS | 独立 Python 设备/指令；实测 M/U/N，完整 BOOT 到首次 ADJ。 |
| PASM MOUNT 参考关键路径 M | MODEL_BOUNDARY | 独立 Python 设备/指令；实测 M/U/N，完整 BOOT 到首次 ADJ。 六组 BOOT 开/关对照与原厂曝光代码已定位；原始同 SHA 冷启动回执及请求参数逐项匹配，严格模型仍停止，未补造回执。 |
| S 块交叉重放 48 次 | PASS | g157 完整关闭 S 源仅换 g158 记录绑定/记录 CRC，保留原 whole-S 校验，再建仅校验双组；实际 48 个新 g158 MAIN；AUTO。不是新 g158 GPIO 源会话。 |
| 相对 g157 的全部字节审计 | PASS | 仅门逻辑、代数及其重定位/校验变化；配方全 552 B、body/resident 相同。 |
| 参考 P1 完整04与原厂图像设定 test | PASS | 逐一核对真实单元九行/T补偿、Standard/WB有效值和关闭后的护栏；不只接受驱动自报通过。 |
| 参考 P1 完整04与原厂图像设定 release | PASS | 逐一核对真实单元九行/T补偿、Standard/WB有效值和关闭后的护栏；不只接受驱动自报通过。 |
| 非许可模式 BOOT 拒绝与完整04 | PASS | 合成 raw01；只验 BOOT 拒绝和完整04，不冒充 SCENE 实机或首次 ADJ 页面。 |
| 本轮产品源码和两包零改动 | PASS | 逐一核对链接时 source/header SHA，以及三个实际 DAT 副本；没有重建或重写 DAT。 |
| slot31 原厂请求与 BOOT 开关对照 | PASS | 同一曝光请求在旧 g157 拒绝 BOOT、g158 release 关闭 BOOT 和 g158 test 已套用后都触达；这项是边界诊断，不是 ADJ 成功。 |

release/50mm P 的首轮 ADJ 关闭在原厂恢复7行表、尚未转入待机时提前取样，原失败保留。新冷启动使用相同输入，全部原按键与状态、失败点首个样本均原样复现；随后不加按键、不改状态，在原90个等待窗口上限内继续原厂指令，稳定到 state=5，完整552 B颜色与40 B记忆保持不变。终点断言没有放宽，产品没有修改。逐项对照见 `local/accept-r2/close_wait/verification.json`，新运行标签为 `r2c-critical-release-50mm-P`。

原有主机、全写入故障矩阵、旧记忆拒收及字节审计复用已封存同 SHA 的回执。本轮新目录使用 r2 前缀，首轮错误、中止和结果都保留；`local/accept-r2/aliases.json`明确列出新旧结果路径，没有覆盖失败现场。

S 重放已断言 48/48。原先5个已通过的新 g158 MAIN 保留，只补其余43个。S 来源仍是已完成的 g157 r1 GPIO 关闭记录，只替换记忆绑定及记录校验并建立 whole-S 校验双组；这是明确派生夹具，不是新 g158 GPIO 源会话，也不是实际 NAND 或关机证明。每个重放都是新 MAIN，没有恢复 CPU/设备检查点。

原生全29条回归与 P 档单记录关键流程分开列。参考整机 P1 使用与复审反例相同的输入和写后回执故障点，检查完整04补偿或护栏，不能用 C harness 代替该项。

模拟器没有 LCD 像素输出。已发布八行文本及逐字符 glyph 缓冲是替代证据，位于各次 `ui-first-adj.json`，不是像素截图。未完成的 M/S ADJ 不制造页面证据。

P/A 首次列表分别见 `local/runs/field-P-native/ui-first-adj.json` 和 `local/runs/field-A-native/ui-first-adj.json`；B11/B12 分别见 `local/runs/unknown-submode/ui-first-adj.json` 和 `local/runs/MY-domain/ui-first-adj.json`。本轮六组原生回归的首个页面与诊断后列表保存在各自运行目录，路径由 `local/accept-r2/aliases.json` 绑定。

## 仍需现场确认

M/S 的 g158 test 必须分别冷启动验证“ADJ在先、不按快门”和“首拍在先”，再与手动重开作对照，见 [现场步骤](OWNER_STEPS.md)。拍照会经过原厂曝光流程，不能把两种顺序互相替代。实际 JPEG、LCD 扫描及单元完整 AE 初态未由本轮模拟器证明。

按用户已接受的范围，SCENE、MY1–3、动态影像和 AUTO 原始 M/U/N/Y 的现场采样继续 OPEN，按现有模型拒绝未许可组合。合成 raw01 的原厂菜单未进入，不把它冒充实测 SCENE；新增独立断言只确认其 BOOT 拒绝和完整04。B11/B12 页面本身已有未知子模式/MY模型回执。可选 Status 采集保持为逐档冷启动，页面读取启动快照。

g157 复审的 P2-03（关机后整表消失定责、DAT 缺席/装载失败诊断）与 P3-01（真实可用堆）按原约定保留，详 [原复审](../review_g157_r1/REVIEW.md)。这些既有现场范围不冒充本轮已关闭的软件验收。

## 换代和降级

g157 记录被 g158 的新绑定干净拒收。首次换入后先手动成功保存一次，再正常关机重开检验 BOOT。降级前必须先在当前 g158 实际保存纯04；当前已是04时先离开一行再回04，确认无 Unsaved/ERR/护栏，关闭再开仍为04，再关机换旧 DAT。

