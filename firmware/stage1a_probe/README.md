# 回放 ISO 执行探针

这是一份 80 字节的原厂 ABI 汇编探针，限定用于 Ricoh GXR＋A12 50mm 1.51 的阶段 1a 实验。相机执行、区域持久性和故障后的恢复尚待真机验证。

`probe.S` 放在 `0x200547B0..0x20054800`，检查前面的 8,260 字节是否全为 FF。它只改调用栈上的格式指针，随后跳入原厂格式化函数 `0x200BBC7C`。正常回放两处纯调用指令字改为 BL24，保留原参数准备与返回位置。解释和地址证据见 [研究报告](../../research/stage1a_probe/REPORT.md)。

按以下顺序复跑。

```sh
python3 -I research/stage1a_probe/audit_candidate.py
python3 -I firmware/stage1a_probe/build_probe.py
python3 -I scripts/verify_build_code_patch.py
python3 -I scripts/build_code_patch.py firmware/stage1a_probe/spec.json
```

加 `--output artifacts/stage1a-probe/packages/<新名称>` 可生成新实验目录。构建器拒绝覆盖已有包和写到 SD 卡或 `/Volumes`。

`build_probe.py` 只汇编、链接、导出字节并生成 `approval.json` 与 `spec.json`；它不会生成 29 文件更新包。`approval.json` 是本任务的实验范围记录，包含候选 VA/文件范围、完整原字节哈希、静态清点哈希、两处挂钩的原指令和参数窗口。`spec.json` 绑定 ELF、payload、map 的 SHA-256 和三个内部相对分支。

原厂普通参数在 r4..r7；这里的可变参数在调用栈 sp+0（格式）和 sp+4（ISO）。探针只使用 r0..r3，没有 GCC 参数转换、额外栈帧、堆、设置或文件接口。两条 BL24 修改 lr 后，探针用 jmp 尾转入原函数；原函数会回到原调用点的下一指令字。

`verify_build_code_patch.py` 对最终机器码重放已使用的指令，在原格式化入口停止。它验证前、中、末部损坏都选 NG、完整 FF 区选 OK，以及寄存器、参数和返回位置。这是宿主验证，未执行相机硬件或完整原厂格式化函数。

构建输入与字节输出在 `build/`，构建器测试和静态证据在 `research/stage1a_probe/evidence/`。刷写、观察和有条件恢复步骤见 [FLASH_AND_CHECK.md](../../research/stage1a_probe/FLASH_AND_CHECK.md)。
