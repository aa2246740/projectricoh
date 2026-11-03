# 2026-10-30 晚：暂停时的状态和恢复办法

19:05（CST）用户下班，要求暂停所有任务，到家后继续。四个工作者都已取消，没有残留进程。恢复时**在各自原来的对话里发"继续"**，不要新开任务（用户规则：可以恢复的任务不要关掉重开）。

## 相机和卡

- 机身是 v3.8（`d4fa3b46`），在 50mm 上实测通过：
  - 拍完照后第一次打开菜单正常；
  - 列表首尾循环、旋钮、保存都正常。
- 28mm 推 ADJ 显示的是原厂菜单。这颗 28mm 的单元固件是 V1.51（用户已确认，固件更新提示里选的是 No）。
- B 卡（序列号 0x3928b118）在 Mac 读卡槽里，已推出：
  - GXRCE.DAT 是 g137（`78dcbb9a`），已经换回来了；
  - 卡上还有 G137.DAT 副本、PROBE1.DAT（`a79020be`）和 DIAG37.DAT。
- 峰值对焦 P1 试验的结果是阴性：P1 MOD 状态下描边仍然是白色。我建议先搁置，等用户决定。照片存在 `captures/peaking-p1-field-20261030`。

## 暂停的四个任务

| 任务 | 对话 | 暂停时的进度 | 恢复时要说的 |
| --- | --- | --- | --- |
| 第 138 版：关机记住配方，用户条目标题改显示条目名 | g138-persist-r1（Opus 5.5 high） | `research/g138_persist/` 已有 FEASIBILITY.md 和工具脚本。主块余量是 0 B，复审第 84 行写明上限是 108,124 B | 先汇报 FEASIBILITY 的结论（上限是谁定的、能腾出多少空间），再继续实现。另外加一条：去掉旋钮行和数值页上的 `!` 标记，用户觉得多余，去掉还能省出空间 |
| 28mm 显示原厂菜单 | unit28-stock-r1（Opus 5.5 high） | `research/unit28_stock/` 已有 m32r_listing.py 和 repro_g137.py，还没写报告 | 继续。28mm 的固件 V1.51 已确认 |
| 电脑端后端 | studio-v2-backend（Grok 4.7） | REPORT.md 写着"未完成"：`make check` 卡在 ruff，原因是前端的 `tests/test_web_frontend.py:231` 一行有 152 个字符，超过限制 | 等前端把这一行改掉之后，跑完全量检查、干净克隆，以及 JPG 近似配方的留出测试 |
| 电脑端前端 | studio-v2-frontend（Haiku 5.5） | 第二阶段实现中，还没有 IMPLEMENTATION_REPORT。它起的测试实例用了内置盘的 TMPDIR，违反了规则 | 先修 `test_web_frontend.py:231` 超长的那一行；TMPDIR 必须放到外置盘；继续 COPY.md 全量改文案，交 COPY_DIFF.tsv |

文案的裁定都在 `research/studio_v2/COPY.md`（第 3.9 节是补充裁定 1）。合同在 `research/studio_v2/PRD.md` 第 10 节。全部完成后交给 GPT-6.1-Sol max 验收。

## 清理

- 停掉了前端遗留的测试实例（端口 18767）。
- 删掉了内置盘上 1.4 GB 的 studio pytest 临时目录（`pytest-of-wu` 98–100）。
- 用户自己正在用的工作室（127.0.0.1:49667）没有动。
