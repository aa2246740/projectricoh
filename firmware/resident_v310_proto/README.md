# v3.10 固定窗口研究原型

默认 `resident/` 是保留两个 IROM 来源的中性候选，代码 7,428 B，扣除 24 B 保留量后余 632 B。单卡、单机内副本及其他尺寸筛选源在 `options/`，均未纳入默认源码。普通冷启动待机门槛尚未闭合，完整结论见 [REPORT.md](../../research/v310_window/REPORT.md)。

从项目根目录重建默认候选：

```sh
TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/v310-window-r1 \
  nice -n 10 /usr/bin/python3 -I -B firmware/resident_v310_proto/resident/build.py
```

入口先核对工作盘 UUID、可写 APFS、冻结输入和工具链，再创建指定临时目录。它只生成 resident 的 ELF、bin、map、身份和日志，输出在 `research/v310_window/options/neutral/`。

重建核心尺寸矩阵及三项占位预算：

```sh
TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/v310-window-r1 \
  nice -n 10 /usr/bin/python3 -I -B research/v310_window/rebuild.py --all
```

占位 768 B 的中性候选应被链接器拒绝。单机内副本的补充测量分别由 `measure_one_irom.py`、`tune_one_irom.py` 和 `measure_one_irom_compact.py` 重建；这些脚本放在同一研究目录。

检查入口按顺序运行，进程都留在前台：

```sh
TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/v310-window-r1 \
  nice -n 10 /usr/bin/python3 -I -B research/v310_window/jobs.py host
TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/v310-window-r1 \
  nice -n 10 /usr/bin/python3 -I -B research/v310_window/jobs.py flow
TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/v310-window-r1 \
  nice -n 10 /usr/bin/python3 -I -B research/v310_window/jobs.py routes
TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/v310-window-r1 \
  nice -n 10 /usr/bin/python3 -I -B research/v310_window/jobs.py recovery
```

运行器为每项设 1,800 秒上限，主机检查默认使用 C 后端；非 PASS 会重跑 Python。冷启动仍会返回 NOT_PASS，可分别用 `jobs.py cold baseline`、`jobs.py cold neutral` 复现。它使用 batch 模拟器、从 MAIN 起点执行，不能把 state 2 记作待机。

`fixtures.py` 只在指定 scratch 创建主机镜像和虚拟介质，g153 测试 DAT 的文件体保持原字节。复跑结束后，确认所有前台进程退出，再运行研究目录的 `finish.py` 核对原始输入、清理 scratch 并刷新校验清单。再次构建会改变测量时长等日志，应重新生成清单。
