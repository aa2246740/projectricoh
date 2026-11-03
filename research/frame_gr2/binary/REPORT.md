# FRAME-GR2 WN3 与 GXR 固件静态对比

结论：FRAME-GR2 的 README 声称在 **GR II** 上提供“16 个机内位置、命名和独立保存”，并公开发布了固件；本轮未实机验证这些功能，现有发布物也不能直接复用于 GXR。WN3 使用 `UNITY FILE V1.10` 双层容器，组件变化集中在高熵、不透明的 `b01firm8`；GXR 的 `ilaunch3/jlaunch3` 则是带 16 段大端加载表、已能可靠解码为 M32R 的另一种镜像。公开仓库只有 README，没有实现源码、函数符号、地址或记录格式。

本轮仅下载和读取公开文件，没有安装 FRAME 应用、运行任何相机固件、连接相机或制作更新包。核验日期为 2026-10-12。

## 输入与来源

| 输入 | SHA-256 | 来源 |
| --- | --- | --- |
| FRAME `FRAME-GR2-WN3-Firmware.zip`，9,160,352 字节 | `af2e231d9ed9a7b604b1e7f63c6dcefd984951f80eb9595421fdc2bdeccc9bcd` | [GitHub Release v0.62.1-wn3](https://github.com/Lyle-xub/FRAME-GR2/releases/tag/v0.62.1-wn3)；GitHub 资产大小和 digest 见 [`release-latest.json:151–181`](../sources/release-latest.json#L151) |
| FRAME 内层 `rg2_v003.frm`，14,466,476 字节 | `6a978ce29143f53c1620e23581851ca1ed5fa7c6b8b3c00972dfb8ae0eb744ff` | ZIP 内 `SHA256SUMS.txt` 与本地重算一致 |
| Ricoh 官方 GR II 3.00 ZIP | `76d28c8e48c37123f226b8aa6d236e23655146bc08070738d9e734290ea6b13d` | [Ricoh GR II 3.00 页面](https://www.ricoh-imaging.co.jp/english/support/digital/gr2_s.html)及其公开下载 `firmware/rg2_v003.zip` |
| 官方内层 `rg2_v003.frm`，14,033,920 字节 | `3643850f2ae74ae967eb336794048f554caa1b11d05b8569824d5719f1838331` | 官方 ZIP 本地提取与重算 |
| GXR 1.51 `ilaunch3` | `da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7` | 项目已核验官方固件 |
| GXR 1.51 A12 50mm `jlaunch3` | `951be1c659c85af58ae3e4ce98707c52f0b4514fc2075256854d59f822671673` | 项目已核验官方固件 |

仓库固定在 commit `3f819a5749e5ccb1781337098da646bf77fd2c2c`，tree `17784099a8a2d62bab94966a245c80da8eb711a3`。完整 tree 只有一个 `README.md`，见 [`tree-main.json:1–15`](../sources/tree-main.json#L1)。因此没有可直接审阅或移植的相机源码。

## 容器和修改范围

FRAME 与官方 GR II 文件都以 ASCII `UNITY FILE V1.10 / RICOH COMPANY` 开头。大端头字段与文件长度、记录数和嵌套边界自洽：

| 层级 | 官方 GR II 3.00 | FRAME WN3 | 已确认差异 |
| --- | ---: | ---: | --- |
| 外层 Unity 总长度 | `0xD62400` | `0xDCBDAC` | FRAME 增加 `0x699AC`，即 432,556 字节 |
| 外层记录数 | 2 | 2 | 相同 |
| `b01firm6` | `0x787E80` | `0x787E80` | SHA-256 完全相同：`501c8a76095e02d1d579d156b203f622bae49be40888c4eee4d5d9e09c058a81` |
| 第二记录 | `rg2_v001up`，内嵌 Unity | 同左 | 容器扩大 432,556 字节 |
| 内层 `b01firm8` | `0x5D9254` | `0x642C00` | 扩大 432,556 字节；内容不同 |

`b01firm8` 的 FRAME SHA-256 为 `5627577dc8e160c7a3bdf022d2385016fdcb1f411f1715f6008e5d2c1f006d6d`，官方为 `861493173b8b6089f34ce7ba42c8c76011e18378663df66554a00059ed7dbed3`。两者重叠区只有前 41 字节连续相同，重叠区有 4,875,829 个字节不同。`b01firm6` 则逐字节相同。这说明 WN3 的实际变化位于 `b01firm8` 所属部分；不透明负载可能包含加密、压缩或其他变换，本轮不能进一步给它命名。

两个 GR II 负载的熵都接近 8 bit/byte。直接搜索只得到偶然短序列：官方和 FRAME 在相同未修改位置都命中一次 `WN3` 和 `DNG`，FRAME 另命中一次 `RAW`；没有 `FRAME`、`LUT`、`.cube`、`MYSET`、`SETTING`、`.IFO` 或 `/ATA1` 明文。短字节命中没有控制流和可读上下文，不能当成函数名或存储路径。

## 与 GXR 的差别

GXR `ilaunch3` 和 A12 50mm `jlaunch3` 都不含 Unity magic。它们各自的头部可以解析出 16 个大端段记录，每段明确给出文件偏移、加载地址、初始化大小和 BSS。项目内 GNU Binutils 2.43 已用官方 M32R 混合 16/32 位测试向量核验，并能在 GXR 目标窗口产生连续控制流，见 [`research/tooling_m32r/REPORT.md`](../../tooling_m32r/REPORT.md)。

FRAME 的 `b01firm8` 当前仍是不透明高熵负载，没有可靠的段/VMA 映射，也没有足够证据指认 ISA。把它强行交给 M32R、ARM 或其他反汇编器都会把任意数据解释成合法指令，不能据此声称 GR II 与 GXR 共用 CPU 或函数。

因此不能复用：

- GR II 的固件地址、补丁字节、容器长度和升级入口。
- `b01firm8` 中尚未恢复的菜单函数、滤镜算法或 16 槽存储格式。
- FRAME README 中的 GR II 更新步骤和恢复预期。

可以借鉴的是公开的功能说明：README 声称支持 `.cube`、XMP 和 JSON 导入，提供 16 个机内位置、添加/替换/启用/删除、离开 App 后独立使用和 0–10 浓度，见 [`README.md:84–94`](../sources/README.md#L84)；它也展示用名字、图标、配色和样片管理滤镜，见 [`README.md:168–170`](../sources/README.md#L168)。这可以作为 GXR“独立 16 条配方库 + 列表选择 + 命名”的产品参照，不能证明 GXR 有对应代码空间或持久化结构。

## JPEG 与 DNG 的证据边界

README 的“保留 JPEG 与 DNG 原始画质”位于手机/电脑导出照片章节，语义是文件传输不缩小、不重新压缩，见 [`README.md:172–176`](../sources/README.md#L172)。它没有说明 LUT 作用于成像管线的哪一层，也没有证明传感器 RAW 未被改写。README 另称装饰写入最终 JPEG，见 [`README.md:125–135`](../sources/README.md#L125)，同样不能外推到自定义 LUT 或 GXR。

GXR 的“配方 JPEG + 原厂 DNG”仍应依赖 GXR 官方 RAW 行为和 A12 50mm 实机验收。FRAME 图片、README 和 GR II 固件差分都不能替代这项证据。

## 下一步价值

当前不建议继续从 WN3 猜测函数地址。若 FRAME 作者以后公开以下任一资料，再做映射才有直接技术价值：

- `b01firm8` 的解包/重打包工具和校验说明。
- 16 个位置的记录结构、持久化路径和菜单调用点。
- 滤镜应用点与 RAW/JPEG 分支的源代码或符号。

在这些资料出现前，FRAME 对 GXR 的价值是产品参照。GXR 实施仍以已经定位的 `ilaunch3` My Settings I/O、A12 50mm 参数映射和独立配方菜单为主线。

## 复跑

从项目根目录运行：

```sh
python3 research/frame_gr2/binary/analyze_firmware.py \
  --frame artifacts/frame-gr2/binary/rg2_v003.frm \
  --official artifacts/frame-gr2/binary/official-rg2_v003.frm \
  --gxr-ilaunch3 artifacts/firmware/gxr-1.51/ilaunch3 \
  --gxr-jlaunch3 artifacts/firmware/gxr-1.51/jlaunch3 \
  --output research/frame_gr2/binary/analysis.json
```

本次输出为 [`analysis.json`](analysis.json)。脚本只读输入，核验 Unity 边界，计算组件哈希、熵、字节差分、精确 ASCII 命中，并解析 GXR 的 16 段头；它不解密或执行固件。
