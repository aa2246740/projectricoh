# 只读复查

从仓库根执行。脚本只写 `research/reentry_reachability/`，检查外置卷身份并拒绝 Python 网络操作。不运行构建、打包、相机或旧复审脚本。

保留现有 `inputs-before.json` 和各项输入身份文件。不要为了让检查通过而覆盖它们。

```sh
/usr/bin/python3 -I -B research/reentry_reachability/audit.py verify
/usr/bin/python3 -I -B research/reentry_reachability/bindings.py
/usr/bin/python3 -I -B research/reentry_reachability/claims.py
/usr/bin/python3 -I -B research/reentry_reachability/replay.py
```

第一项会如实报告共享 `tools/gxr_emulator/observe.py` 相对初始基线的变化并返回 1，详情见 `inputs-after.json` 和 `integrity.json`。这项失败不应通过覆盖基线消除。后面三条可独立执行，验证 resident 字节绑定、具体边及按键片段。片段包含说明过的主机边界，不运行 RTOS 调度。

需要重做静态索引和附表时执行以下命令。`collect` 会在本目录 `local/` 重新抽取并反汇编全部初始化段。

```sh
/usr/bin/python3 -I -B research/reentry_reachability/audit.py collect
/usr/bin/python3 -I -B research/reentry_reachability/tables.py
/usr/bin/python3 -I -B research/reentry_reachability/callers.py
/usr/bin/python3 -I -B research/reentry_reachability/flow.py --tables 20093d48 201c3d08 202bb4bc 202871d8 201d330c
/usr/bin/python3 -I -B research/reentry_reachability/range_refs.py
/usr/bin/python3 -I -B research/reentry_reachability/closure.py 201fd360 201d73e0 201dc180 201c092c 2009005c
/usr/bin/python3 -I -B research/reentry_reachability/closure.py 201c49f4
/usr/bin/python3 -I -B research/reentry_reachability/notes.py
```

`flow` 和 `closure` 是候选遍历，输出保留未解析的寄存器调用和自动跳表边界，不是全程序可达性证明。首次探索和方法修正保留在 `commands.jsonl`、`local/method-notes.json`。

检查交付完整性时，使用最终清单。运行上面的复查会追加命令日志并更新研究结果，因而应先核对原始交付清单，再复跑，不能将复跑导致的输出变化说成输入损坏。

```sh
/usr/bin/shasum -a 256 -c research/reentry_reachability/SHA256SUMS
```

确需重新封存研究输出时，最后运行以下脚本。它保留初始输入身份，核对独立证据与文档链接，再重建当前摘要清单；已知共享源码变化仍单列为 `PARTIAL_SOURCE_DRIFT`。

```sh
/usr/bin/python3 -I -B research/reentry_reachability/finalize.py
```
