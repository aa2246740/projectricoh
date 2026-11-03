补充命令结果。ENDED 只表示命令正常结束；切点记录的 OBSERVED 另表列出。
SETUP_ERROR 是 mount 映像登记遗漏的早期前置错误，修正后的 repeat 命令单列。
两个 expected=1 的控制用于证实断言仍执行以及 ASCII 上限变化，符合预期时不计固件失败。

| 命令组 | 来源 | 预期返回码 | 实际返回码 | 秒 | 命令结果 |
| --- | --- | --- | --- | --- | --- |
| crc-settings-fast | initial | 0 | 0 | 65.399 | ENDED |
| crc-settings-native | initial | 0 | 0 | 64.985 | ENDED |
| crc-route-default | initial | 0 | 0 | 86.453 | ENDED |
| crc-route-flag | initial | 0 | 0 | 86.528 | ENDED |
| preview-window-50mm | initial | 0 | 0 | 68.675 | ENDED |
| crc-route-native | initial | 0 | 0 | 90.155 | ENDED |
| settings-check-50mm | initial | 0 | 0 | 92.918 | ENDED |
| h07-parent-50mm | initial | 0 | 0 | 67.838 | ENDED |
| preview-window-28mm | initial | 0 | 0 | 68.883 | ENDED |
| preview-window-mount | initial | 0 | 1 | 0.852 | SETUP_ERROR |
| settings-check-mount | initial | 0 | 1 | 0.848 | SETUP_ERROR |
| h07-parent-mount | initial | 0 | 1 | 0.834 | SETUP_ERROR |
| settings-check-28mm | initial | 0 | 0 | 94.876 | ENDED |
| h07-parent-28mm | initial | 0 | 0 | 67.965 | ENDED |
| h07-parent-rebuilt-50mm | priority | 0 | 0 | 65.359 | ENDED |
| crc-native-rebound | additional | 0 | 0 | 65.892 | PASS |
| repeat-preview-window-mount | additional | 0 | 0 | 66.74 | PASS |
| repeat-settings-check-mount | additional | 0 | 0 | 90.79 | PASS |
| repeat-h07-parent-mount | additional | 0 | 0 | 67.997 | PASS |
| repeat-settings-check-50mm | additional | 0 | 0 | 91.918 | PASS |
| repeat-settings-check-28mm | additional | 0 | 0 | 91.003 | PASS |
| preview-deferred-50mm | additional | 0 | 0 | 91.839 | PASS |
| preview-deferred-28mm | additional | 0 | 0 | 90.41 | PASS |
| plain-ascii-control | additional | 0 | 0 | 0.11 | PASS |
| rebound-ascii-control | additional | 1 | 1 | 0.163 | PASS |
| rebound-assertion-control | additional | 1 | 1 | 0.16 | PASS |
| preview-deferred-mount | additional | 0 | 0 | 90.155 | PASS |
| pending-read-50mm | additional | 0 | 0 | 111.806 | PASS |

| 证据 | 状态 | 晚到 S store | 晚到预览 | 返回 pending | 重开 pending |
| --- | --- | --- | --- | --- | --- |
| crc-settings-default-50mm | PASS | 0 | 0 | 0 | None |
| crc-settings-flag-50mm | PASS | 0 | 0 | 0 | None |
| crc-settings-native-50mm | PASS | 0 | 0 | 0 | None |
| h07-parent-native-28mm | OBSERVED | 0 | 0 | 1 | None |
| h07-parent-native-50mm | OBSERVED | 1 | 0 | 1 | None |
| h07-parent-native-mount | OBSERVED | 1 | 0 | 1 | None |
| h07-parent-preview-native-mount | OBSERVED | 0 | 1 | 0 | None |
| pending-read-native-50mm | PASS | 0 | 0 | 1 | 0 |
| preview-deferred-native-28mm | PASS | 0 | 0 | 1 | 0 |
| preview-deferred-native-50mm | PASS | 0 | 0 | 1 | 0 |
| preview-deferred-native-mount | PASS | 0 | 0 | 1 | 0 |
| preview-window-native-28mm | OBSERVED | 0 | 1 | 0 | None |
| preview-window-native-50mm | OBSERVED | 0 | 1 | 0 | None |
| preview-window-native-mount | OBSERVED | 0 | 1 | 0 | None |
| settings-check-native-28mm | PASS | 0 | 0 | 1 | 0 |
| settings-check-native-50mm | PASS | 0 | 0 | 1 | 0 |
| settings-check-native-mount | PASS | 0 | 0 | 1 | 0 |
