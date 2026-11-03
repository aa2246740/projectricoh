# Gate 2：请求选行与默认 T 参数

结论：官方 `jlaunch8` 已把 `T+0x2418` 写成 `0x0500`。因此在普通路径，`Q+0x14=5` 时，Live View 的 request 16/19 与 still 的 request 32/33/34/35/36/48/49/50/51/52 都会选 tone A/B 的第 5 行：`A5=0x2012F504`（62 B），`B5=0x2012FFFC`（33 B）。这闭合了默认 contrast 5 的共同曲线行。

颜色闭合为 Live View 与 still 共用的**基础输入**行：官方默认 T 下两者都会从
`0x2012C5D4` 复制第 1 行（96 B），再经过五色 modifier/mixer。它不等于最终的
24-sector 输出字节，也没有闭合固定 matrix 行。

本目录只含 host 静态分析，未连接设备、写 RAM、执行更新或访问挂载卷。

## 可重跑证据

运行：

```sh
python3 -I -B research/stage2a_deep_isp/gate2/analyze_gate2.py
```

脚本核验官方 `jlaunch3` SHA-256 为
`951be1c659c85af58ae3e4ce98707c52f0b4514fc2075256854d59f822671673`，逐项比对
`jlaunch8-writes.json` 与逐字节 T 脚本，生成 [selection.json](selection.json) 和
[verification.json](verification.json)。

## Tone：已闭合

`0x2010E544(Q, request)` 的 request dispatch 是静态确定的：16、19 进入 Live
路径；32、33、34、35、36、48、49、50、51、52 进入 still 普通路径。still 在
`0x2010E82C..E900` 用 `Q+0x14` 的 1..9 选择 `T+0x2420..0x2410`；档位 5 精确读取
`T+0x2418`。Live 的普通分支在 `0x2010E7A4` 也读取 `T+0x2418`。

官方 `jlaunch8` 在脚本偏移 `0xBFEE` 写 `T+0x2418=0x0500`。完整九项是：

| T 偏移 | 默认 selector | curve row |
| --- | --- | --- |
| `2410` | `0900` | 9 |
| `2412` | `0800` | 8 |
| `2414` | `0700` | 7 |
| `2416` | `0600` | 6 |
| `2418` | `0500` | 5 |
| `241A` | `0400` | 4 |
| `241C` | `0300` | 3 |
| `241E` | `0200` | 2 |
| `2420` | `0100` | 1 |

公共尾部取 `(selector >> 8) & 0x3F`，行号从 1 起算。故 row 5 为：

```text
tone A: 0x2012F40C + 4*62 = 0x2012F504, 31*u16BE = 62 B
tone B: 0x2012FF78 + 4*33 = 0x2012FFFC, 33*u8   = 33 B
```

这个结论的前提是 `Q+0x14=5`，请求确实走上述普通分支，且没有 `Q+0x64` 条件 LUT
分支或 effect 17/18/22/23 的覆盖。T 是启动时从调整存储加载的可变参数；`0x0500` 是
官方脚本默认值，不是对任意机身当前 T 的保证。固件若会修改 T，运行时必须读回该半字。

直接证据：

- `research/body_rpc8_probe/evidence/tone-request-selector.txt`，`0x2010E5D4..E660`、`0x2010E7A4`、`0x2010E82C..E900`、`0x2010EB44`。
- `research/color_injection/jlaunch8-writes.json` 的 `T_offset=0x2410..0x2420` 九次写入。
- `research/color_injection/t-script-bytes.json` 的同九个大端半字。
- `research/contrast_curve/lut-packer.disasm.txt`：A/B 行号 1..22 与 62/33 字节步长。

## Color 与 B&W：部分闭合

`0x2010D9FC(Q, request)` 分派 request 16/17/19 到 `0x2010DBEC`，still 请求组到
`0x2010DEA0`。两者不是同一条简单的“contrast/vividness 选一张颜色行”的代码。

对于官方 T，`jlaunch8` 写 `T+0x1262=0x0101`。Live 这条 `DBEC` 路径在
`0x2010DD7C` 计算 `(T+0x1262)&0x1f`，即 1，并由 `0x201141C0` 复制
`0x2012C5D4` 第 1 行（96 B）到局部缓冲。随后 `0x2011396C` 以五色数组修改 24 项，
最后才复制已计算的 96 B。

still 的 32/33/34/35/36/48/49/50/51/52 请求进入 `0x2010DEA0`；它们不进入
`0x2010E3FC`（该地址属于 request 81、80、82.. 等另一请求组）。`0x2010D870` 在配置
初始化时将 `T+0x126C..0x129A` 的 24 个半字复制到 `0x20383E68..0x20383E96`。官方
`jlaunch8` 对这 24 项全部写入 `0x0101`。`DEA0` 的两轮构造在 `0x2010E060` 从该数组取
半字，`0x2010E1CC` 取低 5 位，并在 `0x2010E1D8` 两次调用 `0x201141C0`；因此两个
基础缓冲都复制 C5D4 第 1 行，之后才经 `0x2011396C` 和 mixer 处理。

这闭合的是**源表影响**：默认 T 下，Live 16/17/19 与上述 still 请求族都以 C5D4 row 1
作为输入。Color 04 与 B&W 03 也都满足此点；它们的 `Q+C`（04 为 0，03 为 7）在
`0x2010D800` 影响后续灰度/type 配置，不会改变这组默认 T selector。不能把它表述成
“最终 24-sector bytes 恒等于 row 1”，也不能据此指定一张 D0C0 matrix 行。

Color Setting1 04、B&W 03、B&W TE 06 到 Q 的静态差异也已确认：

| mode | Q 中的已确认字段 | 对选色的含义 |
| --- | --- | --- |
| `04` | 正常 profile，`Q+C` 的低字节为 0；contrast/vividness 分别归一化到 `Q+14/Q+1C`。 | 不能只由 04 推出 C5D4 行。 |
| `03` | `Q+C` 的低字节为 7。 | 不是把彩色鲜艳度调低；灰度转换器会把 7 映为内部类型 5。 |
| `06` | `Q+C` 取 TE tone enum。 | 与 03 的 7 不同，且需要单独读 tone。 |

request 16/17 的 `0x2010DD10` 读的是 `Q+13`（`Q+10` 的低字节），另一组路径在
`0x2010E144` 读 `Q+0F`（`Q+C` 的低字节）。这解释 mode 03/04 为什么仍会产出不同的
灰度/type 配置。`Q+1C=5` 只确定它在两个 vividness 跳表中落到中间内部等级；后续仍受
请求族、effect、灰度/染色值与五色 modifier 影响。

still 从 `0x2010DEA0` 进入阈值与配置构造：它读取 `Q+4`、`T+0x1FF0..0x1FF8`、
`Q+1C`，并经 `0x2011564C` / `0x20114150` 形成配置。`0x20114DAC` 的 type-28 packer
只在 `cfg+5=1..29` 时再直接从 C5D4 取行，在 `cfg+6=1..8` 时取 D0C0 matrix；其他值会
保留前面已经由 row 1 衍生的缓冲。这不否定 row 1 的 source influence，但仍不足以确定
最终 matrix row。

若实现需要保证最终 output 的特定 matrix 或绕开 modifier，最小 runtime 观测仍须同一配置构建中记录：

1. `Q+4`、`Q+C`、`Q+10`、`Q+14`、`Q+1C`，以及对应 request。
2. `T+0x1262`、`T+0x1FF0..0x1FF8`。
3. 进入 type 28 前的 `cfg+5` 与 `cfg+6`，并确认是否额外从 C5D4/D0C0 复制或保留计算结果。
4. Live 与 still 各做一次相同 mode 的观测；不可由相同 UI 值外推。

直接证据：

- `research/body_rpc8_probe/evidence/color-request-builder.txt`：`DBEC`、`DD7C`、`DD84`、`DEA0`、`DF50`、`E144`、`E3FC`。
- `research/body_rpc8_probe/evidence/matrix-helper-color-getters.txt`：`0x20114150`、`0x201141C0`。
- `research/bw_and_base_modes/REPORT.md` 第 4.3 节与 `facts.json` 的 gray mapper。
- `research/color_injection/color-table-packer.disasm.txt`：`cfg+5/cfg+6` 的表和回退行为。

## 可实施的最小表集

在官方默认 T、普通 contrast 5 且上述 tone precondition 成立时，静态允许的共同源表写集是：

1. `A5 @ 0x2012F504`，62 B。
2. `B5 @ 0x2012FFFC`，33 B。
3. `C5D4 row 1 @ 0x2012C5D4`，96 B。

第 3 项会影响 Live 与 still 的最终处理，因为二者都先读取它；它不能用于声称“Color 04 或
B&W 03 的 final 24-sector bytes 等于写入字节”。`D0C0` matrix 没有跨请求族的静态允许行，
不应进入 Stage 2a 目标写集。

## 恢复与并发边界

恢复需要在第一次写入前确定全部原始字节。可以保存实际 RAM snapshot；也可以像当前实现
一样，先把整个目标范围与嵌入的官方 stock 字节逐半字比较，全部相等才允许写入。后一种
方式的恢复数据与准入时的 RAM 内容相同；遇到任何不同字节必须拒绝，不能盲写 stock。
新机身 payload 从经哈希核对的官方 `jlaunch3` 嵌入这些副本，原厂 `ilaunch3` 没有现成的
镜头表恢复接口。

静态代码证明源表在每次相应的配置构造时被读入/复制。没有找到 AE/AWB 周期重读、ISP
reader stop/resume 或任务互斥所有权的证据；也没有 target RAM 可写、读写 transport 或重启
持久性证明。不能用 UI busy 推断一次表写与 ISP 读之间原子。
