v3.3 映像已从最终 resident ELF 重建，旧 prototype 也已重现到原暂存哈希，最终 full-r9 / 111 包已暂存。状态是 STAGED_HOST_ONLY，独立审查 PENDING，用户刷写批准 PENDING。

最终目录为 [local/package_final/SD_ROOT](local/package_final/SD_ROOT)，共 30 个文件：v3.3 `ilaunch3`、28 个官方兄弟文件和 full-r9 `GXRCE.DAT`。审批与逐文件摘要在 [manifest.json](local/package_final/manifest.json)。早先 full-r8 的 [local/package](local/package/manifest.json) 33 个文件未改。

```text
resident ELF 51e44b50862afa74c18920c001cb47d1f65210462d82da2925e67c16438cce08
build ID     0b153c53d809f18bbd05571c3a46907b19ef16cdaa7ebb77dcadd9317c60efeb
ABI ID       9583fdd751bebc36f3af305595559643
ilaunch3     7f01e7535a0c3ebe84bf2d7a060590b24b19f0e1065afc7fe1762973f3f08546
full-r8/110  37c74613056bcdb7cb211370c88292d14379a305d36c3b5ad4fa652c8cb06880
full-r9/111  7fc825755406c8dccd49d49277098afedd478ec45260d53893bf0c55d0ab6e7b
```

`ilaunch3` 为 3,993,340 B。payload=7,800 B、root=256 B，实余 284 B，链接 reserve=280 B。相对批准 v3.2，变化只在 resident 窗口、既有七处桩和 checksum；H03/H04、H10–H37 与固件更新路径保持官方字节。其它 28 个文件逐字节等于官方。新旧 resident 的桥和 ABI 相同。最终 build ID 另作信任轮换，让 prototype 110 无法在最终 body 上运行；相对原暂存机身只再改变 trust build ID 和 checksum，执行代码一致。

[独立审计日志](../resident_v33/local/recovery/final-image-audit.log) 通过；[重建与故障结果](local/verification-final/verification.json) 确认 68 个包文件重复构建相同、14/14 故障拒绝及 7 个跳转目标。恢复目录的 29 个文件等于官方。验证器独立解析，未从 builder 导入逻辑。

最终 full-r9 为 62,700 B，两单元仅 03 record/entry 换成 Standard 身份，46 槽完整展开向量不变。引擎另补旧 DAT 显式 GXTS 保存的只读检查。resident C 44 个命名用例、127,607 次断言；full-r8 2,638 次、full-r9 2,730 次主机流程通过。完整行为、原生调用范围、测试和首刷清单见 [resident 报告](../resident_v33/REPORT.md)。

需要重新生成映像时使用尚未占用的新 local 目录，打包器拒绝覆盖。仓库根命令如下：

```sh
/usr/bin/python3 -I -B firmware/image_v33/build.py \
  --official artifacts/firmware/gxr-1.51/ilaunch3 \
  --elf firmware/resident_v33/local/resident/build/resident.elf \
  --hooks firmware/resident_v33/local/hooks.json \
  --patch-manifest firmware/resident_v33/local/resident/patch-manifest.json \
  --output firmware/image_v33/local/rebuild-next
/usr/bin/python3 -I -B firmware/image_v33/audit.py \
  --package firmware/image_v33/local/rebuild-next \
  --elf firmware/resident_v33/local/resident/build/resident.elf \
  --hooks firmware/resident_v33/local/hooks.json \
  --patch-manifest firmware/resident_v33/local/resident/patch-manifest.json --verbose
```

只写这两份 v33 目录。已核对外置盘 APFS、可写与指定 UUID，原输入冻结检查未变。没有访问相机卡、刷写或安装；主机字节与 C 验证不代替相机运行验收。IROM 恢复、真实任务栈、文件系统掉电及照片仍未核实。
