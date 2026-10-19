本地构建并核对完成，没有上机，也没有写 SD 卡。包在 `artifacts/gate-probe-packages/gate-probe-r1/`。探针 `ilaunch3` 的 sha256 是 `94c797cb1f98e450aaaf312fb5ff5b4f80e04e5fa7be246ed0eac13b36c685c0`，新校验是 `0x6AA27CB7`。下面每一项都通过，没有没过的验证。

`gate_probe_render` 钉在 `0x20052EAC`。它先按被调用者保存 `r8..r13/lr`，再进 C 主体。主体采样五个门控值，把 9 行十六进制和 7 行 `........` 写入 `probe_glyphs`，然后调用 `gxr_list_paint(2, 0x2022F71C, 0)`。链接进来的原生入口只有 `gxr_ascii`、`gxr_language`、`gxr_list_paint`。从字形表到代码结束是 2928 字节，其中代码 1072 字节，结束于 `0x200532DC`（文件 `0x84DC`）。`0x84DC..0x98FF` 仍是 `FF`，`0x98FF` 的重入字节初值是 0，`0x9900..0x9A00` 仍是 `FF`。

## 官方自检

```text
python3 -I firmware/gate_probe/tools/build.py
```

脚本先读 `artifacts/firmware/gxr-1.51/ilaunch3`。sha256 是 `da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7`。文件 `0x16C` 的大端字和 `sum(image[0x200+i] * (i % 6 + 2))` 的低 32 位都是 `0x6ACDB212`。`0x796C..0x9A00` 共 8340 字节全是 `FF`。五个钩子的原字节、五处要求保持的原字节、跳转表 44 字节，都和设计表一致。不等的话脚本会停，这一步没有停。

## 宿主测试

`firmware/gate_probe/tests/test_host.c` 只编译判据和格式串，不链接 `0x201FD360`。

```text
cc -std=c11 -Wall -Wextra -Werror -DPROBE_HOST firmware/gate_probe/tests/test_host.c -o firmware/gate_probe/build/test_host
firmware/gate_probe/build/test_host
```

输出 `host-ok`。覆盖了：五个条件都成立且 tag 为 33、state 为 `0x2022F71C` 时 `V=1`；活动字、part、count、type、空指针、未对齐、区间外都不读条目且 `V=0`；count 为 2 时读的是 `entries+8`；tag 或 state 不对时读了条目但 `V=0`。格式串核对为 `A=08`、`T=05`、`P=02`、`C=01`、`G0=21`、`S=2022F71C`、`V=01`、`W=00000008`、`E=205A279C`，不能解引用时是 `G0=--` 和 `S=--------`，第 10 到 16 行是 `........`。

## 与官方逐字节比对

探针 `ilaunch3` 和官方只在下面这些区间不同。区间是半开的，列出的是真正变了的连续字节。payload 里有的指令字节碰巧仍是 `FF`，所以代码段被拆成多段；文件 `0x84DC..0x98FF` 整段没变，仍是 `FF`。

| 文件区间 | 长度 | 属于 |
| --- | --- | --- |
| `0x16D..0x170` | 3 | 校验字。首字节 `6A` 与官方相同，所以从 `0x16D` 起算 |
| `0x796C..0x80DC` | 1904 | payload |
| `0x80DD..0x80E8` | 11 | payload |
| `0x80E9..0x80F4` | 11 | payload |
| `0x80F5..0x8163` | 110 | payload |
| `0x8164..0x816A` | 6 | payload |
| `0x816B..0x816E` | 3 | payload |
| `0x816F..0x817B` | 12 | payload |
| `0x817C..0x8207` | 139 | payload |
| `0x8208..0x820B` | 3 | payload |
| `0x820C..0x8222` | 22 | payload |
| `0x8224..0x8292` | 110 | payload |
| `0x8293..0x8296` | 3 | payload |
| `0x8297..0x829A` | 3 | payload |
| `0x829B..0x82B2` | 23 | payload |
| `0x82B3..0x82B6` | 3 | payload |
| `0x82B7..0x82CA` | 19 | payload |
| `0x82CB..0x82CE` | 3 | payload |
| `0x82CF..0x82E2` | 19 | payload |
| `0x82E3..0x831A` | 55 | payload |
| `0x831B..0x8322` | 7 | payload |
| `0x8323..0x834B` | 40 | payload |
| `0x834C..0x837B` | 47 | payload |
| `0x837C..0x8386` | 10 | payload |
| `0x8388..0x83A2` | 26 | payload |
| `0x83A3..0x83BE` | 27 | payload |
| `0x83BF..0x83DA` | 27 | payload |
| `0x83DB..0x8422` | 71 | payload |
| `0x8423..0x844A` | 39 | payload |
| `0x844B..0x846A` | 31 | payload |
| `0x846B..0x8482` | 23 | payload |
| `0x8483..0x84DC` | 89 | payload，代码在文件 `0x84DC` 结束 |
| `0x98FF..0x9900` | 1 | 重入字节，初值 0 |
| `0x1B3DE7..0x1B3DE8` | 1 | 附加表钩子里变了的字节 |
| `0x1B3DEA..0x1B3DEC` | 2 | 同上 |
| `0x1E47A9..0x1E47AD` | 4 | 名字表指针和行数。指针首字节 `20` 没变 |
| `0x23C3C7..0x23C3C8` | 1 | 采样钩子里变了的字节 |
| `0x23C3CA..0x23C3CC` | 2 | 同上 |
| `0x23C3D8..0x23C3DA` | 2 | 确认函数 `jmp lr`。后两字节 `F000` 没变 |

这些字节全部落在 `[0x16C, 0x170)`、`[0x796C, 0x9900)` 和五个钩子位点里。头部 `[0, 0x16C)` 和 `[0x170, 0x200)` 没动。

五个钩子写完后的整段新字节：

| 位点 | 文件 | 新字节 |
| --- | --- | --- |
| 采样并绘制 | `0x23C3C4` | `d0c0200580e02eac` |
| 确认函数 | `0x23C3D8` | `1fcef000` |
| type5 名字表 | `0x1E47A8` | `20052dac` |
| 行数 | `0x1E47AC` | `10` |
| type5 附加表 | `0x1B3DE4` | `d2c0200582e22dec` |

保持原字节的位点在探针镜像里仍是原字节：`0x2028709C` = `d0c0202780e01fec`，`0x202870A8` = `12806005`，`0x202BA6FC` = `d2c0205e`，`0x202BB968` = `dbc02022`，`0x202BE24C` = `d0c02026`。跳转表 `0x20377434` 起 44 字节仍是

```text
00fc0118007002bc01540000001c0038005402bc00e0008c
00a800c401bc01d802bc0250026c02bc028802a4
```

`probe_labels[0]` 是 `20 05 27 6C`，`probe_table[0]` 是 `20 05 2D 6C`，第 15 项分别是 `20 05 2D 0C` 和 `20 05 2D A8`。

## 反汇编和写入范围

```text
research/tooling_m32r/prefix/bin/m32r-elf-objdump -d -z firmware/gate_probe/build/payload.elf
```

全文在 `firmware/gate_probe/build/payload-disasm.txt`。构建脚本按 objdump 逐条执行。binutils 把同一字里顺序执行的两条 16 位指令印成 `->`，真正并行才印 `||`。本 payload 里的 `||` 只有 `|| nop`。脚本对每条 store 做了地址证明，共走过 121376 个状态。

非栈 store 只有这些：

| 地址 | 指令 | 落到 |
| --- | --- | --- |
| `0x20052F9A` | `stb r5,@r4` | 重入字节 `0x200546FF`，写入 1 |
| `0x2005314C` | `stb r5,@r4` | 同一字节，返回前写回 0 |
| `0x200530C4` | `stb r6,@r5` | 清零字形格，地址 `0x2005276C..0x20052D6B` |
| `0x200530EE` | `stb r5,@r11` | 调用 `gxr_ascii` 前把该格首字节写 0，地址是 16 个格的起点，最后一格是 `0x20052D0C` |
| `0x200532C0` | `stb r7,@r6` | ASCII 回退拷贝，最高写到 `0x20052D14`，仍在最后一格内部 |

其余 store 都是 `push` 或相对 `sp` 的栈写入，包括格式串和两个 hex 辅助函数写到调用者栈缓冲。没有 4 字节 store 碰到重入字节，所以 `0x20054700` 不会被这条 `stb` 带上。

`jl`/`bl` 的目标：

| 调用点 | 目标 | 是什么 |
| --- | --- | --- |
| `0x20052EBC` `bl` | `0x20052F74` | `gate_probe_render_body` |
| `0x2005306C` `jl` | `0x20052EE0` | `gxr_language` 桥 |
| `0x20053104` `jl` | `0x20052ED4` | `gxr_ascii` 桥 |
| `0x2005313C` `jl` | `0x20052EEC` | `gxr_list_paint` 桥 |
| `0x20053218` `jl` | `0x20052F24` | `probe_put_hex2` |
| `0x20053260` `jl` | `0x20052F48` | `probe_put_hex8` |
| `0x20052F10` `jl r0` | `0x201D73E0` / `0x201DC180` / `0x201FD360` | 三个原生入口，由桥里的立即数决定 |

没有对 `0x200C0DAC`、`0x205D9BF8`、`0x2022F71C`、`0x205A280F`、`0x205A27D4` 的 store。代码里也没有 `0x202D6F38`、`0x201C092C`、`0x2009005C` 的调用或立即数。`0x2022F71C` 只被读，并作为 `gxr_list_paint` 的参数放进 `r5`。

## 校验、哈希、恢复树

探针校验是 `0x6AA27CB7`，写在文件 `0x16C`，按同一公式再算一次仍是这个值。

```text
cd artifacts/gate-probe-packages/gate-probe-r1 && shasum -a 256 -c SHA256SUMS
```

58 个文件全部 `OK`。`candidate/SD_ROOT` 和 `recovery-official-1.51/SD_ROOT` 各 29 个文件。恢复树 29 个与 `artifacts/firmware/gxr-1.51/` 逐字节相同。候选树里除 `ilaunch3` 外的 28 个也逐字节相同。`jlaunch3` 仍是 `951be1c659c85af58ae3e4ce98707c52f0b4514fc2075256854d59f822671673`。包内没有 `._*` 文件。复制用的是 `cp -X`，读回后再对哈希。

## 未知

真机上这九行会显示什么，未知。本包没有刷进相机。画家的子调用会不会重入初始化函数，未知；重入字节只在进入时挡住第二次绘制。电源键或其他离开路径会不会另写设置，未知。`0x2028579C` 会不会再改类型字节、`0x201C3D08` 会不会再压栈，仍按设计标为未知；探针读的是 `0x202871C4` 当时的字节，不假定它们还是静态形状。
