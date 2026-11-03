2026-10-25 v3.4c 开始。卷身份、可写 APFS、df 已核实。v3.4b 两份交付摘要一致。
冻结保护输入 42680 项，排除 decisions.tsv。只写 resident_v34c 与 image_v34c。
复制 v3.4b 源码，不复制旧验收结果。无子代理、设备、卡、安装或提交。

STOP_CONTAINER_TOO_LARGE：首次 full-r11 布局 65552 B，超过 65536 B 上限 16 B；打包器拒绝，未输出 DAT。resident payload 7868 B、root 256 B、余量 216 B。engine 56140 B，比 v3.4b 增 52 B。按用户明示停止条件停止，不继续修改、重建、产品测试或暂存。
已写新增正反测试源码，尚未编译运行。产品测试运行数 0。body image 与 SD_ROOT 均未生成。

停止后冻结核对通过：42680 项未变，decisions.tsv 排除。两份 REPORT 明确未交付、0 产品测试、无 DAT/body/SD_ROOT。

续跑通过：只改编译设置省 736 B，full-r11/113 为 64816 B、余 720 B；resident 实余 216 B。250 个当前候选程序、44 例 resident 与全部历史反例通过，已暂存 STAGED_HOST_ONLY。尺寸测量、原始日志与冻结核验均在 local/。
