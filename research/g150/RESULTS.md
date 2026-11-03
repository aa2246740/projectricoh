# g150 测试结果（由 make_summary.py 从回执生成）

## 用例

| 作业 | 用例 | 状态 | 秒 | g139 秒 | DAT | 开始 | 写入 | 新鲜 |
| --- | --- | --- | ---: | ---: | --- | --- | --- | --- |
| f-held-busy-half-50mm | 50mm-held-busy-half | PASS_M32R | 194.454 |  | 68418fe7 | 19:08:16Z | 19:11:31Z | 是 |
| f-held-busy-menu-50mm | 50mm-held-busy-menu | PASS_M32R | 197.111 |  | 68418fe7 | 19:11:31Z | 19:14:49Z | 是 |
| f-held-busy-ok-28mm | 28mm-held-busy-ok | PASS_M32R | 180.452 |  | 68418fe7 | 19:23:58Z | 19:26:59Z | 是 |
| f-held-busy-ok-50mm | 50mm-held-busy-ok | PASS_M32R | 196.049 |  | 68418fe7 | 19:08:16Z | 19:11:32Z | 是 |
| f-held-busy-ok-mount | mount-held-busy-ok | PASS_M32R | 180.101 |  | 68418fe7 | 19:29:54Z | 19:32:54Z | 是 |
| f-held-lock-g150-28mm | 28mm-held-lock-g150 | PASS_M32R | 176.794 |  | 68418fe7 | 22:26:07Z | 22:29:04Z | 是 |
| f-held-lock-g150-50mm | 50mm-held-lock-g150 | PASS_M32R | 176.976 |  | 68418fe7 | 22:23:04Z | 22:26:01Z | 是 |
| f-held-lock-g150-mount | mount-held-lock-g150 | PASS_M32R | 176.884 |  | 68418fe7 | 22:29:14Z | 22:32:11Z | 是 |
| f-offer-busy-28mm | 28mm-offer-busy | PASS_M32R | 173.846 |  | 68418fe7 | 19:26:59Z | 19:29:53Z | 是 |
| f-offer-busy-50mm | 50mm-offer-busy | PASS_M32R | 175.642 |  | 68418fe7 | 19:21:02Z | 19:23:58Z | 是 |
| f-offer-busy-mount | mount-offer-busy | PASS_M32R | 174.022 |  | 68418fe7 | 19:32:55Z | 19:35:49Z | 是 |
| f-offer-stock-tweak-fixed-50mm | 50mm-offer-stock-tweak-fixed | PASS_M32R | 161.661 |  | 68418fe7 | 19:23:51Z | 19:26:33Z | 是 |
| f-race-at-s-half-28mm | 28mm-race-at-s-half | PASS_M32R | 268.106 |  | 68418fe7 | 19:26:34Z | 19:31:02Z | 是 |
| f-race-at-s-half-50mm | 50mm-race-at-s-half | PASS_M32R | 278.965 |  | 68418fe7 | 19:14:49Z | 19:19:29Z | 是 |
| f-race-at-s-half-mount | mount-race-at-s-half | PASS_M32R | 269.519 |  | 68418fe7 | 19:31:02Z | 19:35:32Z | 是 |
| f-race-at-s-menu-50mm | 50mm-race-at-s-menu | PASS_M32R | 278.979 |  | 68418fe7 | 19:16:22Z | 19:21:02Z | 是 |
| f-race-at-s-ok-50mm | 50mm-race-at-s-ok | PASS_M32R | 288.202 |  | 68418fe7 | 19:11:33Z | 19:16:21Z | 是 |
| f-record-busy-once-50mm | 50mm-record-busy-once | PASS_M32R | 147.936 |  | 68418fe7 | 19:21:23Z | 19:23:51Z | 是 |
| f-transient-busy-fixed-50mm | 50mm-transient-busy-fixed | PASS_M32R | 112.485 |  | 68418fe7 | 19:19:29Z | 19:21:22Z | 是 |
| g139-fixed-held-busy-ok | 50mm-held-busy-ok | FAIL | 181.09 |  | 2378a88c | 18:43:05Z | 18:46:06Z | 是 |
| g139-fixed-race-at-s-ok | 50mm-race-at-s-ok | FAIL | 182.87 |  | 2378a88c | 18:43:31Z | 18:46:35Z | 是 |
| g139-review-busy-settings-exit | 50mm-busy-settings-exit | OBSERVED_P1 | 217.025 |  | 2378a88c | 18:39:53Z | 18:43:31Z | 是 |
| g139-review-transient-busy-half | 50mm-transient-busy-half | OBSERVED_P1 | 190.601 |  | 2378a88c | 18:39:53Z | 18:43:05Z | 是 |
| h-28mm-00 | 28mm-cold-none | PASS | 128.7 | 126.6 | c4878f66 | 21:24:24Z | 21:26:33Z | 是 |
| h-28mm-00 | 28mm-gr-bb | PASS | 237.2 | 231.2 | c4878f66 | 21:24:24Z | 21:30:31Z | 是 |
| h-28mm-00 | 28mm-held-lock | FAIL | 110.4 | 162.4 | c4878f66 | 21:24:24Z | 21:32:21Z | 是 |
| h-28mm-01 | 28mm-my-1 | PASS | 129.2 | 139.4 | c4878f66 | 21:25:11Z | 21:27:20Z | 是 |
| h-28mm-01 | 28mm-offer | PASS | 133.2 | 124.8 | c4878f66 | 21:25:11Z | 21:29:33Z | 是 |
| h-28mm-01 | 28mm-offer-adj | PASS | 133.4 | 130.5 | c4878f66 | 21:25:11Z | 21:31:47Z | 是 |
| h-28mm-02 | 28mm-offer-ok | PASS | 332.0 | 332.6 | c4878f66 | 21:31:47Z | 21:37:20Z | 是 |
| h-28mm-02 | 28mm-p101-partial | PASS | 186.5 | 195.7 | c4878f66 | 21:31:47Z | 21:40:27Z | 是 |
| h-28mm-02 | 28mm-preview-fail-reopen | PASS | 358.5 | 364.4 | c4878f66 | 21:31:47Z | 21:46:25Z | 是 |
| h-28mm-03 | 28mm-record-busy | PASS | 157.4 | 164.4 | c4878f66 | 21:32:21Z | 21:34:59Z | 是 |
| h-28mm-03 | 28mm-t-boot | PASS | 209.9 | 211.8 | c4878f66 | 21:32:21Z | 21:38:29Z | 是 |
| h-28mm-03 | 28mm-tail-random | PASS | 164.2 | 169.3 | c4878f66 | 21:32:21Z | 21:41:13Z | 是 |
| h-28mm-04 | 28mm-tail-user | PASS | 231.0 | 231.6 | c4878f66 | 21:41:14Z | 21:45:05Z | 是 |
| h-28mm-04 | 28mm-users | PASS | 390.0 | 373.5 | c4878f66 | 21:41:14Z | 21:51:35Z | 是 |
| h-28mm-04 | 28mm-value-ends | PASS | 420.9 | 409.4 | c4878f66 | 21:41:14Z | 21:58:36Z | 是 |
| h-50mm-00 | 50mm-bad-crc | PASS | 131.8 | 126.2 | c4878f66 | 20:11:55Z | 20:14:07Z | 是 |
| h-50mm-00 | 50mm-bad-dataid | PASS | 127.4 | 129.1 | c4878f66 | 20:11:55Z | 20:16:14Z | 是 |
| h-50mm-00 | 50mm-bad-flags | PASS | 127.4 | 126.7 | c4878f66 | 20:11:55Z | 20:18:22Z | 是 |
| h-50mm-01 | 50mm-bad-garbage | PASS | 130.6 | 129.0 | c4878f66 | 20:12:07Z | 20:14:18Z | 是 |
| h-50mm-01 | 50mm-bad-level | PASS | 126.6 | 127.1 | c4878f66 | 20:12:07Z | 20:16:24Z | 是 |
| h-50mm-01 | 50mm-bad-magic | PASS | 126.4 | 128.4 | c4878f66 | 20:12:07Z | 20:18:31Z | 是 |
| h-50mm-02 | 50mm-bad-slot0 | PASS | 127.0 | 126.8 | c4878f66 | 20:18:22Z | 20:20:30Z | 是 |
| h-50mm-02 | 50mm-bad-slot9 | PASS | 126.4 | 128.8 | c4878f66 | 20:18:22Z | 20:22:36Z | 是 |
| h-50mm-02 | 50mm-bad-unit | PASS | 125.8 | 126.7 | c4878f66 | 20:18:22Z | 20:24:42Z | 是 |
| h-50mm-03 | 50mm-bad-version | PASS | 127.7 | 128.7 | c4878f66 | 20:18:31Z | 20:20:39Z | 是 |
| h-50mm-03 | 50mm-cold-none | PASS | 126.8 | 127.6 | c4878f66 | 20:18:31Z | 20:22:46Z | 是 |
| h-50mm-03 | 50mm-gr-bb | PASS | 228.0 | 231.5 | c4878f66 | 20:18:31Z | 20:26:34Z | 是 |
| h-50mm-04 | 50mm-held-lock | FAIL | 107.9 | 160.7 | c4878f66 | 20:24:42Z | 20:26:30Z | 是 |
| h-50mm-04 | 50mm-inel-extension | PASS | 128.0 | 126.6 | c4878f66 | 20:24:42Z | 20:28:38Z | 是 |
| h-50mm-04 | 50mm-inel-mode4 | PASS | 106.9 | 105.7 | c4878f66 | 20:24:42Z | 20:30:25Z | 是 |
| h-50mm-05 | 50mm-inel-raw | PASS | 106.9 | 106.3 | c4878f66 | 20:26:34Z | 20:28:22Z | 是 |
| h-50mm-05 | 50mm-inel-source | PASS | 107.5 | 105.4 | c4878f66 | 20:26:34Z | 20:30:09Z | 是 |
| h-50mm-05 | 50mm-inel-t0 | PASS | 127.0 | 128.3 | c4878f66 | 20:26:34Z | 20:32:16Z | 是 |
| h-50mm-06 | 50mm-inel-wb | PASS | 105.9 | 107.5 | c4878f66 | 20:30:26Z | 20:32:12Z | 是 |
| h-50mm-06 | 50mm-my-0 | PASS | 125.2 | 124.3 | c4878f66 | 20:30:26Z | 20:34:17Z | 是 |
| h-50mm-06 | 50mm-my-1 | PASS | 125.3 | 127.7 | c4878f66 | 20:30:26Z | 20:36:23Z | 是 |
| h-50mm-07 | 50mm-my-2 | PASS | 126.3 | 125.9 | c4878f66 | 20:32:17Z | 20:34:23Z | 是 |
| h-50mm-07 | 50mm-my-3 | PASS | 125.4 | 127.8 | c4878f66 | 20:32:17Z | 20:36:28Z | 是 |
| h-50mm-07 | 50mm-my-replay | PASS | 2.4 | 2.3 | c4878f66 | 20:32:17Z | 20:36:31Z | 是 |
| h-50mm-08 | 50mm-offer | PASS | 126.0 | 125.5 | c4878f66 | 20:36:23Z | 20:38:29Z | 是 |
| h-50mm-08 | 50mm-offer-adj | PASS | 129.0 | 129.5 | c4878f66 | 20:36:23Z | 20:40:38Z | 是 |
| h-50mm-08 | 50mm-offer-disp | PASS | 305.4 | 306.9 | c4878f66 | 20:36:23Z | 20:45:44Z | 是 |
| h-50mm-09 | 50mm-offer-half | PASS | 129.2 | 129.0 | c4878f66 | 20:36:31Z | 20:38:41Z | 是 |
| h-50mm-09 | 50mm-offer-move-ok | PASS | 316.0 | 308.7 | c4878f66 | 20:36:31Z | 20:43:57Z | 是 |
| h-50mm-09 | 50mm-offer-ok | PASS | 330.3 | 331.9 | c4878f66 | 20:36:31Z | 20:49:27Z | 是 |
| h-50mm-10 | 50mm-offer-unconfirmed | PASS | 126.1 | 123.7 | c4878f66 | 20:45:44Z | 20:47:51Z | 是 |
| h-50mm-10 | 50mm-p101-five-mode4 | PASS | 310.5 | 310.1 | c4878f66 | 20:45:44Z | 20:53:01Z | 是 |
| h-50mm-10 | 50mm-p101-normal | PASS | 144.7 | 146.1 | c4878f66 | 20:45:44Z | 20:55:26Z | 是 |
| h-50mm-11 | 50mm-p101-partial | PASS | 185.8 | 189.9 | c4878f66 | 20:49:27Z | 20:52:33Z | 是 |
| h-50mm-11 | 50mm-preview-fail-reopen | PASS | 358.4 | 365.8 | c4878f66 | 20:49:27Z | 20:58:32Z | 是 |
| h-50mm-11 | 50mm-race-length-op2 | PASS | 195.9 | 194.2 | c4878f66 | 20:49:27Z | 21:01:48Z | 是 |
| h-50mm-12 | 50mm-race-length-op5 | PASS | 147.4 | 148.8 | c4878f66 | 20:55:26Z | 20:57:54Z | 是 |
| h-50mm-12 | 50mm-race-version-op5 | PASS | 147.4 | 146.5 | c4878f66 | 20:55:26Z | 21:00:21Z | 是 |
| h-50mm-12 | 50mm-record-busy | PASS | 159.4 | 157.3 | c4878f66 | 20:55:26Z | 21:03:01Z | 是 |
| h-50mm-13 | 50mm-record-busy-reopen | PASS | 179.5 | 181.7 | c4878f66 | 21:01:48Z | 21:04:48Z | 是 |
| h-50mm-13 | 50mm-t-boot | PASS | 210.3 | 209.8 | c4878f66 | 21:01:48Z | 21:08:18Z | 是 |
| h-50mm-13 | 50mm-t-error | PASS | 150.7 | 149.5 | c4878f66 | 21:01:48Z | 21:10:49Z | 是 |
| h-50mm-14 | 50mm-tail-badcrc | PASS | 165.7 | 165.0 | c4878f66 | 21:03:01Z | 21:05:47Z | 是 |
| h-50mm-14 | 50mm-tail-gxr1 | PASS | 167.1 | 167.9 | c4878f66 | 21:03:01Z | 21:08:34Z | 是 |
| h-50mm-14 | 50mm-tail-nomagic | PASS | 169.5 | 165.3 | c4878f66 | 21:03:01Z | 21:11:24Z | 是 |
| h-50mm-15 | 50mm-tail-own | PASS | 144.8 | 146.3 | c4878f66 | 21:10:49Z | 21:13:15Z | 是 |
| h-50mm-15 | 50mm-tail-race | PASS | 144.8 | 144.4 | c4878f66 | 21:10:49Z | 21:15:39Z | 是 |
| h-50mm-15 | 50mm-tail-random | PASS | 167.5 | 165.6 | c4878f66 | 21:10:49Z | 21:18:27Z | 是 |
| h-50mm-16 | 50mm-tail-user | PASS | 231.7 | 251.1 | c4878f66 | 21:11:24Z | 21:15:16Z | 是 |
| h-50mm-16 | 50mm-tail-v2 | PASS | 166.0 | 167.7 | c4878f66 | 21:11:24Z | 21:18:02Z | 是 |
| h-50mm-16 | 50mm-users | PASS | 381.7 | 410.5 | c4878f66 | 21:11:24Z | 21:24:24Z | 是 |
| h-50mm-17 | 50mm-value-ends | PASS | 402.5 | 398.6 | c4878f66 | 21:18:27Z | 21:25:10Z | 是 |
| h-mount-00 | mount-cold-none | PASS | 126.6 | 126.3 | c4878f66 | 21:46:25Z | 21:48:33Z | 是 |
| h-mount-00 | mount-gr-bb | PASS | 237.9 | 218.6 | c4878f66 | 21:46:25Z | 21:52:31Z | 是 |
| h-mount-00 | mount-held-lock | FAIL | 115.9 | 162.2 | c4878f66 | 21:46:25Z | 21:54:26Z | 是 |
| h-mount-01 | mount-my-1 | PASS | 138.8 | 138.4 | c4878f66 | 21:54:27Z | 21:56:46Z | 是 |
| h-mount-01 | mount-offer | PASS | 126.2 | 125.2 | c4878f66 | 21:54:27Z | 21:58:52Z | 是 |
| h-mount-01 | mount-offer-adj | PASS | 129.3 | 130.3 | c4878f66 | 21:54:27Z | 22:01:02Z | 是 |
| h-mount-02 | mount-offer-ok | PASS | 332.8 | 332.6 | c4878f66 | 21:58:36Z | 22:04:10Z | 是 |
| h-mount-02 | mount-p101-partial | PASS | 190.2 | 195.5 | c4878f66 | 21:58:36Z | 22:07:20Z | 是 |
| h-mount-02 | mount-preview-fail-reopen | PASS | 368.1 | 367.7 | c4878f66 | 21:58:36Z | 22:13:28Z | 是 |
| h-mount-03 | mount-record-busy | PASS | 155.5 | 161.3 | c4878f66 | 22:01:02Z | 22:03:38Z | 是 |
| h-mount-03 | mount-t-boot | PASS | 212.5 | 211.8 | c4878f66 | 22:01:02Z | 22:07:10Z | 是 |
| h-mount-03 | mount-tail-random | PASS | 167.9 | 165.6 | c4878f66 | 22:01:02Z | 22:09:58Z | 是 |
| h-mount-04 | mount-tail-user | PASS | 229.3 | 226.6 | c4878f66 | 22:09:59Z | 22:13:48Z | 是 |
| h-mount-04 | mount-users | PASS | 370.5 | 369.6 | c4878f66 | 22:09:59Z | 22:19:59Z | 是 |
| h-mount-04 | mount-value-ends | PASS | 431.1 | 434.0 | c4878f66 | 22:09:59Z | 22:27:10Z | 是 |
| r-busy-settings-exit-50mm | 50mm-busy-settings-exit | FAIL | 111.898 |  | 68418fe7 | 19:35:33Z | 19:37:25Z | 是 |
| r-dat-release-test-50mm | 50mm-dat-release-test | PASS_M32R | 146.573 |  | 68418fe7 | 19:54:01Z | 19:56:28Z | 是 |
| r-dat-test-release-50mm | 50mm-dat-test-release | PASS_M32R | 146.839 |  | c4878f66 | 19:54:18Z | 19:56:45Z | 是 |
| r-exit-menu-50mm | 50mm-exit-menu | PASS_M32R | 132.425 |  | 68418fe7 | 19:47:23Z | 19:49:36Z | 是 |
| r-first-apply-readback-50mm | 50mm-first-apply-readback | PASS_M32R | 186.473 |  | 68418fe7 | 19:39:50Z | 19:42:57Z | 是 |
| r-fn2-dispatch-50mm | 50mm-fn2-dispatch | PASS_M32R | 130.913 |  | 68418fe7 | 19:42:57Z | 19:45:09Z | 是 |
| r-glyph-parent-50mm | 50mm-glyph-parent | FAIL | 131.496 |  | 68418fe7 | 19:51:49Z | 19:54:01Z | 是 |
| r-glyph-parent-cleanup-50mm | 50mm-glyph-parent-cleanup | OBSERVED_INHERITED_UI_RESTORE | 132.397 |  | 68418fe7 | 19:52:05Z | 19:54:18Z | 是 |
| r-lock-matrix-50mm | 50mm-lock-matrix | PASS_M32R | 568.124 |  | 68418fe7 | 19:39:52Z | 19:49:20Z | 是 |
| r-logical-fn2-exit-50mm | 50mm-logical-fn2-exit | PASS_M32R | 133.097 |  | 68418fe7 | 19:45:09Z | 19:47:23Z | 是 |
| r-logical-fn2-parent-preview-50mm | 50mm-logical-fn2-parent-preview | PASS_M32R | 148.208 |  | 68418fe7 | 19:49:36Z | 19:52:05Z | 是 |
| r-logical-fn2-parent-settings-50mm | 50mm-logical-fn2-parent-settings | PASS_M32R | 147.938 |  | 68418fe7 | 19:49:21Z | 19:51:49Z | 是 |
| r-offer-stock-tweak-50mm | 50mm-offer-stock-tweak | FAIL | 129.117 |  | 68418fe7 | 19:37:42Z | 19:39:52Z | 是 |
| r-op2-length-large-50mm | 50mm-op2-length-large | PASS_M32R | 198.309 |  | 68418fe7 | 20:03:40Z | 20:06:58Z | 是 |
| r-op5-length-large-50mm | 50mm-op5-length-large | PASS_M32R | 148.873 |  | 68418fe7 | 20:06:58Z | 20:09:28Z | 是 |
| r-op5-pointer-50mm | 50mm-op5-pointer | PASS_M32R | 150.994 |  | 68418fe7 | 20:09:35Z | 20:12:07Z | 是 |
| r-op5-tail-last-50mm | 50mm-op5-tail-last | PASS_M32R | 145.918 |  | 68418fe7 | 20:09:28Z | 20:11:54Z | 是 |
| r-op5-version-50mm | 50mm-op5-version | PASS_M32R | 147.741 |  | 68418fe7 | 20:07:07Z | 20:09:35Z | 是 |
| r-record-busy-attempts-50mm | 50mm-record-busy-attempts | FAIL | 144.295 |  | 68418fe7 | 19:37:25Z | 19:39:50Z | 是 |
| r-tail-first-byte-50mm | 50mm-tail-first-byte | PASS_M32R | 173.285 |  | 68418fe7 | 19:56:29Z | 19:59:22Z | 是 |
| r-tail-last-byte-50mm | 50mm-tail-last-byte | PASS_M32R | 173.025 |  | 68418fe7 | 19:56:45Z | 19:59:39Z | 是 |
| r-transient-busy-half-50mm | 50mm-transient-busy-half | FAIL | 112.253 |  | 68418fe7 | 19:35:49Z | 19:37:42Z | 是 |
| r-users-fcc2-50mm | 50mm-users-fcc2 | PASS_M32R | 241.226 |  | 68418fe7 | 20:03:05Z | 20:07:07Z | 是 |
| r-users-none-50mm | 50mm-users-none | PASS_M32R | 221.87 |  | c4878f66 | 19:59:22Z | 20:03:05Z | 是 |
| r-users-replaced-50mm | 50mm-users-replaced | PASS_M32R | 240.02 |  | 30929c19 | 19:59:39Z | 20:03:39Z | 是 |

## 回归组

| 运行 | 覆盖的组 | 状态 | 秒 | g139 秒 | 超时 | 产物数 | 产物时间 | DAT |
| --- | --- | --- | ---: | --- | ---: | ---: | --- | --- |
| group124-mount-nested | group124-mount-nested | PASS | 436.98 | 435.547 | 10800 | 205 | 22:32:23Z–22:39:39Z | c4878f66 |
| group126-mount-nested | group126-mount-nested | PASS | 435.59 | 438.401 | 10800 | 205 | 22:32:23Z–22:39:38Z | c4878f66 |
| group124+126-mount-safety | group124-mount-safety、group126-mount-safety | PASS | 422.148 | 372.891 / 368.281 | 10800 | 181 | 22:39:38Z–22:46:40Z | c4878f66 |
| group124-mount-locked | group124-mount-locked | PASS | 364.367 | 313.539 | 10800 | 181 | 22:39:39Z–22:45:44Z | c4878f66 |
| group126-mount-locked | group126-mount-locked | PASS | 310.434 | 312.117 | 10800 | 181 | 22:45:44Z–22:50:54Z | c4878f66 |
| group124-mount-cutpoints | group124-mount-cutpoints | PASS | 240.985 | 242.123 | 10800 | 179 | 22:46:40Z–22:50:41Z | c4878f66 |
| group126-mount-cutpoints | group126-mount-cutpoints | PASS | 243.452 | 241.798 | 10800 | 179 | 22:50:41Z–22:54:44Z | c4878f66 |
| group124+126-mount-labels-g139 | group124-mount-labels-g139、group126-mount-labels-g139 | PASS | 221.189 | 223.916 / 222.144 | 10800 | 169 | 22:50:54Z–22:54:35Z | c4878f66 |
| group124-mount-half | group124-mount-half | PASS | 154.053 | 156.769 | 10800 | 293 | 22:54:36Z–22:57:09Z | c4878f66 |
| group126-mount-half | group126-mount-half | PASS | 154.392 | 158.238 | 10800 | 294 | 22:54:45Z–22:57:19Z | c4878f66 |
| group124+126-50mm-safety | group124-50mm-safety、group126-50mm-safety | PASS | 373.663 | 385.972 / 372.661 | 10800 | 181 | 22:57:10Z–23:03:23Z | c4878f66 |
| group124-50mm-locked | group124-50mm-locked | PASS | 317.305 | 327.16 | 10800 | 181 | 22:57:19Z–23:02:36Z | c4878f66 |
| group126-50mm-locked | group126-50mm-locked | PASS | 308.372 | 312.746 | 10800 | 181 | 23:02:36Z–23:07:44Z | c4878f66 |
| group124-50mm-nested | group124-50mm-nested | PASS | 431.773 | 457.818 | 10800 | 205 | 23:03:23Z–23:10:35Z | c4878f66 |
| group126-50mm-nested | group126-50mm-nested | PASS | 430.008 | 434.057 | 10800 | 205 | 23:07:45Z–23:14:54Z | c4878f66 |
| group124-50mm-cutpoints | group124-50mm-cutpoints | PASS | 239.294 | 262.51 | 10800 | 179 | 23:10:35Z–23:14:34Z | c4878f66 |
| group126-50mm-cutpoints | group126-50mm-cutpoints | PASS | 239.667 | 239.941 | 10800 | 179 | 23:14:34Z–23:18:34Z | c4878f66 |
| group124-50mm-exits | group124-50mm-exits | PASS | 966.898 | 996.375 | 10800 | 283 | 23:14:55Z–23:31:01Z | c4878f66 |
| group126-50mm-exits | group126-50mm-exits | PASS | 973.96 | 970.816 | 10800 | 284 | 23:18:34Z–23:34:48Z | c4878f66 |
| group124+126-50mm-transitions | group124-50mm-transitions、group126-50mm-transitions | PASS | 900.016 | 905.12 / 875.676 | 10800 | 334 | 23:31:02Z–23:46:01Z | c4878f66 |
| group124+126-50mm-values | group124-50mm-values、group126-50mm-values | PASS | 1689.256 | 1724.374 / 1667.107 | 10800 | 191 | 23:34:48Z–00:02:57Z | c4878f66 |
| group124-50mm-view-reentry | group124-50mm-view-reentry | PASS | 759.613 | 782.739 | 10800 | 310 | 23:46:02Z–23:58:41Z | c4878f66 |
| group126-50mm-view-reentry | group126-50mm-view-reentry | PASS | 758.166 | 764.327 | 10800 | 311 | 23:58:41Z–00:11:19Z | c4878f66 |
| group124-50mm-reentry-six | group124-50mm-reentry-six | PASS | 1216.463 | 1306.997 | 10800 | 568 | 00:02:57Z–00:23:13Z | c4878f66 |
| group126-50mm-reentry-six | group126-50mm-reentry-six | PASS | 1224.837 | 1266.174 | 10800 | 569 | 00:11:20Z–00:31:44Z | c4878f66 |
| group124-50mm-users | group124-50mm-users | PASS | 599.367 | 637.55 | 10800 | 177 | 00:23:14Z–00:33:13Z | c4878f66 |
| group126-50mm-users | group126-50mm-users | PASS | 625.033 | 613.56 | 10800 | 178 | 00:31:44Z–00:42:09Z | c4878f66 |
| group124+126-50mm-project-g139 | group124-50mm-project-g139、group126-50mm-project-g139 | PASS | 1529.167 | 1575.044 / 1510.998 | 10800 | 141 | 00:33:13Z–00:58:42Z | c4878f66 |
| group124+126-50mm-labels-g139 | group124-50mm-labels-g139、group126-50mm-labels-g139 | PASS | 219.169 | 226.108 / 223.426 | 10800 | 169 | 00:42:09Z–00:45:48Z | c4878f66 |
| group124-50mm-half | group124-50mm-half | PASS | 152.685 | 154.631 | 10800 | 293 | 00:45:49Z–00:48:21Z | c4878f66 |
| group126-50mm-half | group126-50mm-half | PASS | 154.252 | 155.549 | 10800 | 294 | 00:48:21Z–00:50:55Z | c4878f66 |
| group126-50mm-other-users | group126-50mm-other-users | PASS | 536.005 | 537.896 | 10800 | 224 | 00:50:56Z–00:59:51Z | c4878f66 |
| group124+126-28mm-safety | group124-28mm-safety、group126-28mm-safety | PASS | 372.51 | 379.262 / 377.494 | 10800 | 181 | 00:58:42Z–01:04:54Z | c4878f66 |
| group124-28mm-locked | group124-28mm-locked | PASS | 307.304 | 323.394 | 10800 | 181 | 00:59:52Z–01:04:59Z | c4878f66 |
| group126-28mm-locked | group126-28mm-locked | PASS | 309.627 | 315.58 | 10800 | 181 | 01:04:55Z–01:10:04Z | c4878f66 |
| group124-28mm-nested | group124-28mm-nested | PASS | 435.599 | 447.391 | 10800 | 205 | 01:04:59Z–01:12:14Z | c4878f66 |
| group126-28mm-nested | group126-28mm-nested | PASS | 450.592 | 448.092 | 10800 | 205 | 01:10:04Z–01:17:35Z | c4878f66 |
| group124-28mm-cutpoints | group124-28mm-cutpoints | PASS | 248.344 | 250.305 | 10800 | 179 | 01:12:14Z–01:16:22Z | c4878f66 |
| group126-28mm-cutpoints | group126-28mm-cutpoints | PASS | 259.516 | 249.247 | 10800 | 179 | 01:16:23Z–01:20:42Z | c4878f66 |
| group124-28mm-exits | group124-28mm-exits | PASS | 1486.551 | 1006.649 | 10800 | 283 | 01:17:35Z–01:42:21Z | c4878f66 |
| group126-28mm-exits | group126-28mm-exits | PASS | 1455.0 | 1033.09 | 10800 | 284 | 01:20:42Z–01:44:57Z | c4878f66 |
| group124+126-28mm-transitions | group124-28mm-transitions、group126-28mm-transitions | 留给发布复审 | | | | | 用户本轮不使用 28mm；28mm 表数据与 g139 逐字节相同；引擎代码三单元共用，50mm/MOUNT 同组已过 | |
| group124+126-28mm-values | group124-28mm-values、group126-28mm-values | 留给发布复审 | | | | | 用户本轮不使用 28mm；28mm 表数据与 g139 逐字节相同；引擎代码三单元共用，50mm/MOUNT 同组已过 | |
| group124-28mm-view-reentry | group124-28mm-view-reentry | 留给发布复审 | | | | | 用户本轮不使用 28mm；28mm 表数据与 g139 逐字节相同；引擎代码三单元共用，50mm/MOUNT 同组已过。另：视图重入：引擎代码三个单元共用；同一套件 50mm 两个家族在 g150 上 PASS；28mm 表数据与 g139 逐字节相同。时间预算内优先 28mm reentry-six | |
| group126-28mm-view-reentry | group126-28mm-view-reentry | 留给发布复审 | | | | | 用户本轮不使用 28mm；28mm 表数据与 g139 逐字节相同；引擎代码三单元共用，50mm/MOUNT 同组已过。另：同上 | |
| group124-28mm-reentry-six | group124-28mm-reentry-six | 留给发布复审 | | | | | 用户本轮不使用 28mm；28mm 表数据与 g139 逐字节相同；引擎代码三单元共用，50mm/MOUNT 同组已过 | |
| group126-28mm-reentry-six | group126-28mm-reentry-six | 留给发布复审 | | | | | 用户本轮不使用 28mm；28mm 表数据与 g139 逐字节相同；引擎代码三单元共用，50mm/MOUNT 同组已过。另：同一套件 50mm 两个家族、28mm 124 家族在 g150 上跑；引擎共用，28mm 表数据未变 | |
| group124-28mm-users | group124-28mm-users | 留给发布复审 | | | | | 用户本轮不使用 28mm；28mm 表数据与 g139 逐字节相同；引擎代码三单元共用，50mm/MOUNT 同组已过。另：用户条目装载与标题：g150 没有改用户条目、扩展区或标题代码；28mm 表数据逐字节未变；50mm 两个家族 PASS | |
| group126-28mm-users | group126-28mm-users | 留给发布复审 | | | | | 用户本轮不使用 28mm；28mm 表数据与 g139 逐字节相同；引擎代码三单元共用，50mm/MOUNT 同组已过。另：同上 | |
| group124+126-28mm-project-g139 | group124-28mm-project-g139、group126-28mm-project-g139 | 留给发布复审 | | | | | 用户本轮不使用 28mm；28mm 表数据与 g139 逐字节相同；引擎代码三单元共用，50mm/MOUNT 同组已过。另：全档位计算（M32R 与主机 C）：g150 没有改 kv 计算代码；28mm 表数据与旋钮块逐字节未变；50mm PASS | |
| group124+126-28mm-labels-g139 | group124-28mm-labels-g139、group126-28mm-labels-g139 | 留给发布复审 | | | | | 用户本轮不使用 28mm；28mm 表数据与 g139 逐字节相同；引擎代码三单元共用，50mm/MOUNT 同组已过。另：标签文案：g150 只改了 L1 已应用行取哪组 levels（P2-01），由 offer-stock-tweak-fixed 和 82 项主机测试覆盖；50mm PASS | |
| group124-28mm-half | group124-28mm-half | 留给发布复审 | | | | | 用户本轮不使用 28mm；28mm 表数据与 g139 逐字节相同；引擎代码三单元共用，50mm/MOUNT 同组已过。另：原厂半按路径不进入 DAT；与半按相关的新行为由 held-busy-half、race-at-s-half（三个单元）覆盖；50mm 两个家族 PASS | |
| group126-28mm-half | group126-28mm-half | 留给发布复审 | | | | | 用户本轮不使用 28mm；28mm 表数据与 g139 逐字节相同；引擎代码三单元共用，50mm/MOUNT 同组已过。另：同上 | |
| group126-28mm-other-users | group126-28mm-other-users | 留给发布复审 | | | | | 用户本轮不使用 28mm；28mm 表数据与 g139 逐字节相同；引擎代码三单元共用，50mm/MOUNT 同组已过。另：其他用户条目组合：用户条目代码未改；28mm 表数据未变；50mm PASS | |
