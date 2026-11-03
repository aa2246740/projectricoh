# 集成 knobs v2 整数数学

1. 将 `kv_math.c` 和 `kv_i64.c` 加入引擎构建，包含 `kv_math.h`。使用 C11、`-ffreestanding` 和 `-fno-builtin`。本目录的 `test_` 文件只供测试。
2. 在会话 BSS 中保留一份 `KvWork`，调用期间保持该会话排他。工作区为 2,288 B，按八字节对齐也不增加尺寸。
3. 向 `kv_apply_work(stock, base, request, out, stats, work)` 传入本单元未修改的原厂 04、未修改的原配方和完整请求。每次调用都从这两个底子重算。

`out` 可与任一输入完整或部分重叠。`work` 必须与 `stock`、`out`、`stats` 分离；`base=work->base` 和 `request=&work->request` 可用。返回 0 时提交完整输出和统计；返回 -1 或 -2 时保持输出和调用方统计不变。

菜单调用方令 `dose[9]=0`。其余字段及下标与冻结 `knobs.h` 相同。核心保留参考中的 Tone 计算，以复跑扩展语料。

在仓库根构建独立模块：

```sh
/usr/bin/python3 -I -B firmware/kv2_modules/math/build.py
```

构建产物位于本目录被忽略的 `local/`。完整验收见 [中文报告](../../../research/kv2_math/REPORT.md)，复跑步骤见 [REPRODUCE.md](../../../research/kv2_math/REPRODUCE.md)。
