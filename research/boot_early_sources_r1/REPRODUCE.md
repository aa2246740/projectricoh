# 本地复查

本研究的静态全集尚未闭合。先读 SOURCE_MAP.md 的覆盖矩阵，再读 SLOT_BUDGET.md 和 OPEN_ITEMS.md；不要把一致性复查通过理解为 BOOT_EARLY 已可定版。

以下命令只读输入和交付物，不运行固件，不生成构建或设备文件，默认也不改回执：

```sh
TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/boot-early-src-r1/ \
nice -n 10 /usr/bin/python3 -I -B \
/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/boot_early_sources_r1/verify.py
```

复查包括官方 ZIP 的 29 个成员、v3.9 的两个机身和两个 DAT 副本、参考输入哈希、封存窗口的原始字节与反汇编、具体返回半字、报告引用、槽位算术、未定项到观察的对应，报告正文判定标记、文本用词，以及 SHA256SUMS。它调用已经核对身份的本地 objdump 重新解码全部封存窗口，不运行目标代码，也不需要建立临时目录。输入若被其他工作更新，会明确失败，应先核对身份差异。

catalog.py 保存逐点结论，render_reports.py 生成所需报告和 JSON，budget.py 保存槽位算术。scan_static.py、scan_unitinfo.py、collect_boot.py、collect_package_types.py、collect_unit_services.py、scan_unit_t.py 保存本轮使用的检索方法；直线常量传播的结果只是定位候选，不能证明调用者全集。

verification.json 是封存前的一致性回执；SHA256SUMS 封存最终交付物。默认复查不写 verification.json，避免改变已封存文件。cleanup_receipt.json 记录临时目录清理结果。
