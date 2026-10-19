# Stage 1a probe v3 sentinel

电脑端完成，真机未验，待主代理复核与用户确认。

`rewrite.S`/`rewrite.ld` 只使用两个官方 212 字节生产函数槽位。`build_rewrite.py` 生成冻结 spec、ELF、map、反汇编和等长 patched ilaunch3；本地 `build_function_rewrite.py` 沿用原 builder 的段/长度/校验和逐分支重编码，增加 8 哨兵规格与 v3 包门槛。

仅写本任务 v3 目录。原官方/v2/scripts 保持只读，Python 用 `python3 -I -B`。重建不覆盖既有 build、spec 或包。

验收与复跑见 [REPORT.md](../../research/stage1a_probe_v3/REPORT.md)，用户操作草案见 [FLASH_AND_CHECK.md](../../research/stage1a_probe_v3/FLASH_AND_CHECK.md)。
