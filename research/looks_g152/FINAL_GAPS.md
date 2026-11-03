# 留给发布复审

本轮必跑项目按最终 DAT 摘要核对。完整 144 项由用户明确留给发布复审；本轮替换为 48 项测试卡缩减版。

| 项目 | 入口 | 理由 |
|---|---|---|
| full-locks-50mm | lock_checks.py --unit 50mm | 留给发布复审：完整 4×6×3=72 项。按用户续轮指令，本轮先做该单元 4×3×2=24 项；旧候选完整 144 项均通过，本轮核对最终改动是否改变同类路径。C 后端仍在复审，本轮不用。 |
| full-locks-mount | lock_checks.py --unit mount | 留给发布复审：完整 4×6×3=72 项。按用户续轮指令，本轮先做该单元 4×3×2=24 项；旧候选完整 144 项均通过，本轮核对最终改动是否改变同类路径。C 后端仍在复审，本轮不用。 |
| legacy-other-cases | REGRESSION_SCOPE.md  | 留给发布复审：99 条旧用例中未选部分，逐条理由见该表。 |
| core-81-groups | CORE_REGRESSION_SCOPE.md  | 留给发布复审：81 组全量回归未在本轮扩跑，逐条理由见该表。 |
| camera-and-unit-paths | REPORT.md  | 留给发布复审：真实 LCD、RPC/RTOS 时序、ISO100 单元分支、rpc_ready=0 首开和失归属时 S 待写边界仍须现场验证。 |
| image-quality | fit_results.json  | 留给发布复审：扇区模型限制及 28mm/MOUNT 独立画质标定不能由本轮编码行与主机预测代替。 |
