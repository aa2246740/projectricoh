复审仍在执行；最终结论看 REVIEW.md，逐组状态看 REGRESSIONS.md。

任务 review-g129-r1，UTC 起点 2026-10-28 23:18:41，四小时终点 2026-10-29 03:18:41。唯一调度器 PID 57349、终端会话 61681，03:14 停止未闭合验证，留出封存时间。不得启动第二个调度器。当前队列容量3，所有手工专项均结束，只有唯一主队列仍在运行。settings-r6三单元均36/36通过，GXUI三单元96条转换通过。

候选 DAT 为 b58396748f1d5bba5ed480c1e7a81bc881a9df08968db2b778086c7c1a9cbf48，89308 B。实现方 SHA256SUMS 372 项初检通过，本轮冻结 400 项；最终还须复核实现方 746 项输入。只写本目录，设备、卡、网络、子代理均未使用。一次错误 JSON 汇总带出了旧 traceback 源码行，已向用户说明；最终必须清理生成日志。

已闭合：28mm/mount cold_reentry 各四案，三单元完整 product 菜单及42028条完整通信审核；原始数学13330+2504，全部3430菜单点及S计划对照；三单元M32R 1133/1134/1163点和原Python后端样本；13292条金标准经菜单引擎，1条非法Fade和29条不支持的Amount拒绝；4054帧、402端点、24 Default。8条CORE_ONLY仍不能算实际菜单入口全量。

GXUI原包为空。主机96转换与960保留字段拒绝通过；新的legacy_model.py在三单元各建新M32R会话，全部32个20B向量均核对，代码与最终DAT相同，ig_init访问数各1。legacy-model-results.json为最终汇总。此前裸RAM重放和legacy_post.py的尝试未通过，不能采用。

settings_cases的有效复跑为settings-r6-50mm、settings-r6-28mm，各36/36通过；mount也已36/36通过。初次工具适配错误仍保留。ui_adapter.py现在绑定实际staged DAT和ELF、读实测布局；r2_oracle.py使用原始r2 C参考，unit/slot来自会话，不改原参考缓冲或完整比较断言。当前ASCII两个实际控制返回0/1，1为预期断言控制；字典和共用常量自检通过。

源码与堆检查已补到15个原文相同的文件/函数、另12个归属函数；后者仅向量类型名和keep_view的点表游标变化。KvWork偏移2556、尺寸2288B，在会话图像BSS。主请求107496B；source-results.json、gate-results.json已生成。27条g122历史记录已逐条判断；history123三单元完整命令通过。

最终顺序：继续唯一队列至03:14；用空出的工作槽运行reference_changes.py生成旧/新具体参考值表；collect_runs.py；seal.py --prepare清理生成诊断；collect_runs.py与summarize.py更新最终表；核对REVIEW.md最终数字和未闭合项；复核400/746/372与卷身份；seal.py生成并自检仓库根相对SHA256SUMS；确认不再有验证工作进程。
