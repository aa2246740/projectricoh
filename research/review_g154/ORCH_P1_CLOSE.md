# P1-01 关闭记录（编排者）

2026-11-02 编排者按 REVIEW.md 文末命令在 Python 后端串行补跑 MOUNT 两条 continuation 作业（新名称，nice 10，offline.sb，TMPDIR 在 Scratch，结束后已删）。

| 作业 | 后端 | 用时 | 结果 |
|---|---|---:|---|
| orch-mount-python-followup（g154） | python | 446.7 s | PASS（颜色/S/单元写入检查）；与 continuation-g154-mount-c 的 650 个结果字段逐项相同（排除时间/后端/摘要类字段） |
| orch-mount-g153-python-followup（g153 对照） | python | 约 450 s | PASS；与 continuation-g153-mount-c 的 605 个字段逐项相同 |

g154 与 g153 的 Python 结果只在列表标签与行数（`>Looks`/` MyRec` → `>M9 STD`/` HNCS HiCon`，11 → 22 行）及原生名字缓冲地址上不同，这是平铺列表的预期差异。S 摘要、单元 W、原生九行、帧行、原厂游标、游标缓存、unit_W 共 100 个字段完全相同。两项 OPEN 观察在 MOUNT 上 C=Python，且与 g153 行为相同，按 P2-01/P2-02 记录。P1-01 关闭，g154 测试 DAT `ac4263a0…` 可以上卡。
