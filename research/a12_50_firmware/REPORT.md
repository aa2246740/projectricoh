# A12 50mm：My Settings `.IFO` 离线分析

结论：原厂 My Settings 的单条记录是固定 **1024 字节**，有效槽号硬编码为 **1–6**，其中真正恢复到运行设置的负载位于记录偏移 `0x100–0x21F`，共 **288 字节**。把现有上限 `7` 改成 `17` 不能直接得到 16 个独立色彩配方：保存、加载、删除和多处枚举都带有六槽假设，而且 288 字节负载会恢复大量拍摄设置。首版应新建只含 Image Settings（必要时加白平衡）的 16 条配方库，复用已确认的文件 I/O 和完整性算法形状，不直接调用整条 My Settings 恢复。

本轮只读取 Ricoh GXR 1.51 固件，没有生成补丁、运行固件、连接相机或更改全局配置。核验日期为 2026-10-12。

## 证据边界

| 结论 | 级别 | 直接证据 |
| --- | --- | --- |
| `ilaunch3` 目标窗口属于第 4 段：文件偏移 `0xBE200` 对应 VMA `0x20109000` | 静态分析已确认 | [反汇编清单](disassembly-manifest.txt)；工具链的[逐段映射](../tooling_m32r/sections/ilaunch3-sections.csv) |
| 保存函数 VMA `0x2011D728`（文件偏移 `0xD2928`）；加载函数 VMA `0x2011E350`（文件偏移 `0xD3550`） | 静态分析已确认 | 保存函数从[反汇编第 18 行](ilaunch3-myset.disasm.txt#L18)开始，加载函数从[第 796 行](ilaunch3-myset.disasm.txt#L796)开始 |
| 每条 `.IFO` 固定读写 1024 字节，短读/短写均失败 | 静态分析已确认 | 写入长度与返回值检查见[第 771–782 行](ilaunch3-myset.disasm.txt#L771)；读取见[第 858–866 行](ilaunch3-myset.disasm.txt#L858) |
| 保存缓冲区为当前栈帧 `sp+100`；加载缓冲区为当前栈帧 `sp+80` | 静态分析已确认 | 保存清零参数见[第 124–129 行](ilaunch3-myset.disasm.txt#L124)；加载读取参数见[第 858–862 行](ilaunch3-myset.disasm.txt#L858)。它们是运行时栈地址，没有固定绝对地址 |
| 记录负载从 `0x100` 开始，长度 288；记录头偏移 `0x20` 保存数值 288 | 静态分析已确认 | `record+0x100` 建立在[第 20–23 行](ilaunch3-myset.disasm.txt#L20)，头字段写入见[第 248–249 行](ilaunch3-myset.disasm.txt#L248)，最后一字节写到负载 `+0x11F` 见[第 761–765 行](ilaunch3-myset.disasm.txt#L761) |
| 完整性值存于记录偏移 `0x50`，覆盖记录偏移 `0x100–0x21F`（含两端） | 静态分析已确认 | 算法循环见[第 8–17 行](ilaunch3-myset.disasm.txt#L8)；保存参数和写回见[第 763–773 行](ilaunch3-myset.disasm.txt#L763)；加载重算比较见[第 870–877 行](ilaunch3-myset.disasm.txt#L870) |
| 保存和加载均拒绝槽 0 以及槽号 `>=7`，枚举从 1 递增到 6 | 静态分析已确认 | 保存边界见[第 44–46 行](ilaunch3-myset.disasm.txt#L44)，加载边界见[第 813–815 行](ilaunch3-myset.disasm.txt#L813)，枚举边界见[第 2692–2695 行](ilaunch3-myset.disasm.txt#L2692) |
| 288 字节负载双向复制大量全局设置，不能把整条 My Settings 当成“只切色彩”的配方 | 静态分析已确认 | 保存端连续取全局对象字段见[第 251–762 行](ilaunch3-myset.disasm.txt#L251)；加载端把相同负载写回全局对象，例如[第 2452–2501 行](ilaunch3-myset.disasm.txt#L2452) |
| Setting 1/2 的 26 个具体颜色字段在记录中的偏移 | **尚未确认** | 已找到多组双向字段复制，但固件没有符号，当前没有样本差分或菜单调用链把某组字段与 Setting 1/2 语义绑定 |

固件和工具哈希：

- `ilaunch3`：`da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7`
- A12 50mm `jlaunch3`：`951be1c659c85af58ae3e4ce98707c52f0b4514fc2075256854d59f822671673`
- GNU Binutils 2.43 `m32r-elf-objdump`：`8d3712c11cac0ffc63b790148c49a916f25d96fceabbb3c1daa125cf4904368a`

工具已用 GNU 官方 M32R 测试向量核验混合 16/32 位指令，固件按大端逐段映射。工具来源、已知向量和复跑结果见[工具报告](../tooling_m32r/REPORT.md)。

## `.IFO` 记录与调用链

第 4 段的换算关系是：

```text
file_offset = 0xBE200 + (VMA - 0x20109000)
```

关键位置如下：

| 用途 | VMA | `ilaunch3` 文件偏移 |
| --- | ---: | ---: |
| 完整性函数 | `0x2011D700` | `0xD2900` |
| 保存入口 | `0x2011D728` | `0xD2928` |
| 保存的槽上限比较 | `0x2011D794` | `0xD2994` |
| 保存写调用 | `0x2011E2F8` | `0xD34F8` |
| 加载入口 | `0x2011E350` | `0xD3550` |
| 加载的槽上限比较 | `0x2011E398` | `0xD3598` |
| 加载读调用 | `0x2011E44C` | `0xD364C` |
| 枚举槽上限比较 | `0x201200F8` | `0xD52F8` |

路径代码使用 `/ATA1/MYSET`、`/MYSET`、`.IFO` 和 `/ATA1/MYSET/MYSET` 字符串。槽号经除 10 和取余 10 转成两个 ASCII 数字，因此现有命名形状可以表达 `01` 到 `16`；这只证明文件名容得下两位数。保存、加载、删除和至少五个枚举循环仍需逐一处理六槽边界，菜单表和 RAM 容量也没有得到扩容证据。

新文件先把 1024 字节缓冲区清零，再填记录头和负载。记录头包含高位变换后的 `MY SETTING CARD`、`GXR            `、数值 288，以及偏移 `0x50` 的完整性值。已有文件会先清零缓冲区，再读取原文件前 256 字节，更新部分头字段，最后重新写出完整 1024 字节。因此，前 256 字节是记录头，不能把未识别字节全部当成可自由占用空间。

`0x2011D700` 的完整性函数可以恢复为以下等价伪代码：

```text
sum = 0
for i = first_offset through last_offset:   # 两端都包含
    sum = (sum + record[i] * ((i & 0x0f) + 1)) & 0xffffffff
return sum
```

保存和加载传入 `first_offset=256`、`last_offset=543`，即恰好覆盖 `0x100–0x21F` 的 288 字节负载。GNU M32R 定义确认 `cmp r6,r5` 设置条件为 `r6 < r5`，`bnc` 在条件为假时跳转，见官方 Binutils 源码中的 [`cmp`](../tooling_m32r/src/binutils-2.43/cpu/m32r.cpu#L1131) 和 [`bnc`](../tooling_m32r/src/binutils-2.43/cpu/m32r.cpu#L1017) 语义，因此末尾 `543` 也参与计算。它是加权和，不是 CRC。

## Setting 1/2 的当前边界

静态分析确认负载会保存并恢复一个大型全局设置对象。该对象的指针存放于 `0x200C0DAC`。例如，负载相对偏移 `0x102–0x112` 的 17 个字节来自全局对象偏移 `0xED0、0xEDA、…、0xF5C、0xF6F、0xF79`，保存复制见[第 677–727 行](ilaunch3-myset.disasm.txt#L677)，加载端在 VMA `0x2011FD30–0x2011FDF4` 写回相同位置，见[第 2452–2501 行](ilaunch3-myset.disasm.txt#L2452)。这个“每隔 10 字节”的形状像设置数组，但目前没有控制流或样本证明它就是 Setting 1/2。

因此，本轮能确认 **My Settings 会保存大量参数**，不能确认其中哪 26 个字节对应两套 Setting 1/2。这里的 26 个实际颜色字段是：每套 3 个全局项（鲜艳度、对比度、锐度）加 5 组颜色（橙、绿、蓝、红、洋红）各自的色相与鲜艳度，共每套 13 个。没有证据时不能把邻近 17 字节候选硬标成这些字段。

## 对 16 条独立配方的实施判断

建议保留原厂六个 My Settings 槽，新增独立的 16 条配方记录。每条记录只保存配方名、13 个 Image Settings 字段、可选白平衡字段、版本和完整性值。选择配方时只更新这些字段，不调用 `0x2011E350` 的完整 My Settings 加载路径，因为后者会同时恢复曝光、对焦、按钮等设置，违反产品范围。

可以复用的已确认形状包括：

- 两位十进制编号的路径构造。
- `0x200A449C` 读调用、`0x200A45E8` 写调用及精确长度检查。符号名缺失，角色由调用参数和返回值确认。
- 先写临时缓冲区、记录内版本字段、负载完整性值和读取后校验的流程。

仍缺少三项，不能开始制作可刷构建：

- Setting 1/2 的 13 字段到机身全局对象及 A12 50mm 模块参数的准确映射。
- 新配方菜单的入口、16 行列表资源、命名编辑器和运行时内存预算。
- 失败时的文件处理、恢复入口和真机启动证据。

JPEG+DNG 约束应通过“配方切换不改 Picture Quality”落实。官方 GXR 手册已经确认 RAW 拍摄生成 DNG 和 JPEG，Image Settings 只作用于 JPEG；来源为 [Ricoh GXR Camera Body User Guide](https://www.ricoh-imaging.co.jp/english/r_dc/support/manual/pdf/gxr/GXR_E.pdf)，印刷页 63 / PDF 物理页 75。`jlaunch3` 中已定位到 `MngRecStill_SaveDngFile1/2`、`RAWBUF` 和 `.DNG` 字符串，但本轮没有建立可达调用链，所以它们仍是线索，不能用于声称模块保存路径已经定位。

## 相机回来后的最小定位实验

先采样，不刷写：

1. 在同一 My Settings 槽保存基线并导出 `.IFO`。
2. 只改 Setting 1 的一个字段后再次保存和导出。依次覆盖 3 个全局项，以及橙、绿、蓝、红、洋红各自的色相与鲜艳度，共 13 次；Setting 2 再做同样 13 次。
3. 每次只比较记录负载 `0x100–0x21F`，记录稳定变化的偏移、符号编码和取值范围；忽略记录头中可能变化的设备字段，并用已恢复的加权和核验样本。
4. 用“相同画面、相同曝光、RAW Picture Quality”拍一组基线和配方样本，确认一次快门产生一张带配方 JPEG 与一张可正常解码的原厂 DNG。

如果单字段实验没有在 `.IFO` 中产生稳定差分，说明 Setting 1/2 没有随 My Settings 卡记录保存，下一步应直接从菜单 setter 的运行时写地址定位。这个结果仍不会阻塞独立配方库，只会决定 13 字段从哪里读取和写入。

## 复跑

从项目根目录运行：

```sh
python3 research/a12_50_firmware/analyze_static.py \
  artifacts/firmware/gxr-1.51 \
  --output research/a12_50_firmware/static-index.json

python3 research/a12_50_firmware/disassemble_regions.py \
  artifacts/firmware/gxr-1.51 \
  research/tooling_m32r/prefix/bin/m32r-elf-objdump \
  --output-dir research/a12_50_firmware

python3 research/a12_50_firmware/extract_myset_evidence.py \
  research/a12_50_firmware/ilaunch3-myset.disasm.txt \
  --output research/a12_50_firmware/myset-evidence.json
```

第三条命令会按准确 VMA 断言 26 条关键指令；本次输出为 [`myset-evidence.json`](myset-evidence.json)，确认槽号 1–6、记录 1024 字节、负载 288 字节、完整性范围和两个栈缓冲区。它不为任何负载字节赋予菜单语义。
