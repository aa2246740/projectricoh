三条均非产品缺陷

# g129 safety 三条失败的定性

本任务的 worker（g129-safety-triage-r1，Claude Sonnet 5.5）在跑完主要证据后，因为 API 速率限制中断。报告由编排者根据它留下的运行记录写成，没有新增产品改动。

## 结论

| 用例 | 原失败现象 | 定性 | 依据 |
| --- | --- | --- | --- |
| panel_rollback | Cont=-1 的完整输出与旧期望不一致 | (a) 设计变化导致的预期变化 | 旧期望用的是旧调节数学。用冻结的 r2 整数核心重算期望后，九行全部相等。Cont=0 时新旧期望逐字节相同；Cont=-1 时只有两条曲线行（33 B 行中各有 28 B）不同，其余七行相同。这正是 knobs v2 换掉对比度曲线算法的预期结果。 |
| ready_warm | engine_ready=3，用例要求 1 | (b) 测试工具读错偏移 | 旧用例固定读 `g+2523`。gen 129 的 ready 字段已移到 `g+4844`（以当前构建的 layout.json 为准）。从正确偏移读到的值是 1；2523 处是别的字段，值为 3。 |
| write_latch | list.uncertain=1、适配层 failed=0 | (b) 测试工具用了旧布局 | 旧用例读取的是 gen 127 的布局文件（`MATERIALS/local/layout/…`）。改用当前构建的布局后，锁存状态为 uncertain=1、write_started=1、failed=1，恰好是用例要求的锁存，判定 PASS。 |

## 运行记录（`evidence/summary.json`）

| 代 | 读取方式 | 单元 | 结果 |
| --- | --- | --- | --- |
| g129 | 原读取 | 50mm | 5/8，上面三条失败 |
| g129 | 修正读取 | 50mm、28mm、mount | 各 8/8 |
| g131 | 修正读取 | 50mm、28mm、mount | 各 8/8 |
| g131 | 原读取 | 50mm | 5/8，同样三条失败 |

"修正读取"只改测试侧，见 `patches/safety_cases_triage.diff`：
- 布局改从当前构建读取；
- ready 改用当前偏移；
- panel_rollback 的期望改由 r2 参考核心计算；
- 另外增加了 UI 与核心状态的诊断输出。

产品 DAT 未改动：g129 为 `b5839674…`，g131 为 `5ca22d7b…`。

另有几组原读取复跑（28mm、mount 及 g131 的其他单元）在 worker 中断时仍在运行，只用来再次确认原失败现象，不影响结论。

## 对后续版本的处理

- **g135**（knobs + H07 修复 + v3.7 半按修复）：旧 safety 套件必须用修正读取来跑，即当前布局、当前 ready 偏移、r2 期望。不能用原读取，否则会再次报出这三条假失败。
- 修正读取应纳入以后的回归 wrapper。旧目录 `research/review_g124` 的脚本不改。
