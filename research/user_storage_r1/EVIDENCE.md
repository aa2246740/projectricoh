# 证据索引

所有 `local/` 片段来自已核对 SHA 的官方 ilaunch3；`collect.py` 还逐窗口核对固定 v3.6 中的对应字节相等。线性反汇编包含数据，不等于可达控制流。

| 问题 | 本任务证据 | 层级 |
|---|---|---|
| 输入、卷和受保护文件。 | `local/volume.json`、`protected-before.json`、`protected-after.json`、`protected-check.json`、`sections.json`。 | 主机文件身份。 |
| DAT 和 resident 的写权限边界。 | `local/source-excerpts.txt`、`service-source.json`、`storage_prefix.inc`、`host-service.stdout`。 | 源码静态、实际 C 的 ASan/UBSan 替身调用。 |
| H01 加载时机和固定 hooks 身份。 | `local/source-excerpts.txt`、`resident-source-equivalence.json`。 | 固定 v3.6 源码；未重建机身。 |
| S 完整持久化、加载与参数校验。 | `local/settings-persist-full.asm.txt`、`settings-storage-copy.asm.txt`、`settings-load-init.asm.txt`、`settings-default-transfer.asm.txt`、`settings-save-restore.asm.txt`、`settings-power-save.asm.txt`。 | 官方字节静态。 |
| S 直接和别名访问候选。 | `local/settings-census.json`、`settings-high-fields.asm.txt`。 | 全 16 段的有界线性候选扫描；不证明空闲。 |
| 恢复默认的边界。 | `local/source-excerpts.txt`、`restore-default-candidate.asm.txt`。 | 原厂说明书、默认处理候选；菜单完整分派未证。 |
| 打开已有文件和 mode 的 0x80 标志。 | `local/file-open-read-write-close.asm.txt`、`file-open-low.asm.txt`、`fat-open-existing.asm.txt`、`fat-file-init.asm.txt`。 | 官方字节静态。 |
| 定位、缓存对齐和假成功。 | `local/seek-wrapper-tail.asm.txt`、`seek-core.asm.txt`、`host-native-results.json`。 | 官方指令有界重放；fd/媒体边界替身。 |
| 写回、目录更新和关闭失败。 | `local/write-close-low.asm.txt`、`file-close-core.asm.txt`、`fat-directory-write.asm.txt`、`host-native-results.json`。 | 官方字节及替身重放；未执行真实 FAT/媒体。 |
| IROM 全卷格式化。 | `local/irom-update-format.asm.txt`、`irom-format-wrapper.asm.txt`、`irom-format-core.asm.txt`、`format-wrapper.asm.txt`。 | 本轮重取调用分支，结合既有格式化静态研究。 |
| 双份恢复与数据完整性。 | `storage_model.py`、`local/host-model-results.json`、`synthetic-16k.bin`。 | 全合成模型，没有理光记录或实物介质。 |
| 工具不可用范围。 | `local/rea-status.json`。 | 本次只读工具状态；未使用 REA 伪代码。 |

`seek-candidate` 和 `seek-low` 是检索时的窗口名。前者包含目录接口，后者包含其它文件数据通路；不能凭名称把它们当作已确认的定位入口。确认入口及结论以 REPORT.md 中的地址为准。

主机模型中的错误分支成功复现记为 PASS，表示探针按预期检出了问题，不表示可向照片卡开放写入。数据 CRC 模型不包含 FAT、NAND 或 RTOS 并发。
