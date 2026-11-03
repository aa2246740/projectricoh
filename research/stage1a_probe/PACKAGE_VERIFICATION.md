# 最终包独立落盘核验

最终目录 `artifacts/stage1a-probe/packages/stage1a-probe-ok-ng` 已通过电脑上的独立核验。探针版与恢复版各 29 个文件；其余 28 个文件及全部恢复文件与官方逐字节相同。真机执行、区域持久性和本机恢复均待测。

核验脚本：[verify_package.py](verify_package.py)。它直接读成品，未调用构建器的 build 或接受其返回数据作字节证据。

| 项目 | 结果 |
|---|---|
| 实际变更文件 | 仅 ilaunch3 |
| 文件长度 | 3,993,340 字节，保持原长度 |
| 等长替换跨度 | 88 字节（80 字节探针＋两处 4 字节调用） |
| 实际变化字节 | 86 个 payload 字节＋3 个校验字节＝89 字节；cmp -l 独立确认 |
| 未改写的检查区 | 文件 [0x796C,0x99B0)，8,260 字节全部 FF |
| 校验 | 相位 0；0x6ACDB212 → 0x6ACCE776；逐字节标量重算相同 |
| ELF/payload/map/spec/approval | 全部与 manifest 哈希相同 |
| 最终挂钩字节 | 0x2CEE7C: FE F4 EA CD；0x2CD664: FE F4 F0 D3；独立反汇编均指向 0x200547B0 |
| 构建器验证 | 52 项通过，含 14 个正向项目、38 个拒绝项目；0 失败 |
| 原有 build_drill.py 与四份指定报告 | 与测试前哈希相同 |

SHA-256 身份如下。

| 文件 | SHA-256 |
|---|---|
| 探针 ilaunch3 | `6818c492c7a9d9e1025650e2d514bea3bb7996add5a080f6b25b93573abf526b` |
| 探针 SHA256SUMS | `c8c6f1b2c5b7eaecea5eae6ec5f437b54ef2789c1ede5138b9d77834b33d5693` |
| 官方恢复 SHA256SUMS | `51a4d618f4cc0871b44bbb8b2492a380bfea7924729b9717d2ef61acbab405b0` |
| manifest.json | `69fca583962623ee8950ac5cc11c0942f37a4f99189fce8118cfba551289f6a0` |

证据：[package-verification.json](evidence/package-verification.json)、[builder-verification.json](evidence/builder-verification.json)、[cmp 差异](evidence/final-ilaunch3-cmp.txt)、[探针 29 文件哈希](evidence/final-probe-shasum.txt)、[恢复 29 文件哈希](evidence/final-recovery-shasum.txt)。

最终成品的两个挂钩窗口包含未改动的参数准备和返回后的栈清理，见 [正常回放](evidence/final-window-20319c5c.txt)、[另一份回放](evidence/final-window-20318444.txt)。探针 [最终代码](evidence/final-window-200547b0.txt) 的 ELF 原始反汇编另存于 `firmware/stage1a_probe/build/probe.disasm.txt`。

没有对 SD 卡或 `/Volumes` 执行写入。相机执行测试是 [FLASH_AND_CHECK.md](FLASH_AND_CHECK.md) 中的待测步骤；宿主重放没有执行完整原厂格式化函数或相机硬件。
