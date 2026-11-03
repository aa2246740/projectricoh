# Ricoh GXR 色彩配方与 My Settings 官方能力核验

核验日期：2026-10-12

适用范围：用户原话为“我用的 A12 两个都有”。本报告暂按 GR LENS A12 28mm F2.5 与 GR LENS A12 50mm F2.5 MACRO 两款研究，并补充其他模块的差异。具体模块型号和机身当前固件版本仍待确认。

## 结论

GXR 官方固件已经提供保存更多“完整拍摄配方”的路径。A12 50mm 和 A12 28mm 升到 1.50 或 1.51 后，可把 My Settings 保存到机身的 My Settings Box 1 至 6，也可保存到 SD 卡的 Card 1 至 6，再把其中一项分配给 MY1、MY2、MY3 拨盘位置。拨盘始终只有 3 个快速调用位置。机身盒子和 SD 卡各有 6 个库位。[官方 1.50 功能表](https://www.ricoh-imaging.co.jp/english/r_dc/download/firmware/gxr/bymodes.html?sscl=f_n2fc01)；[官方固件功能介绍](https://www.ricoh-imaging.co.jp/english/products/gxr/firmware.html)；[官方 GXR 宣传册，第 13 页](https://www.ricoh-imaging.co.jp/english/r_dc/support/brochure/pdf/GXR.pdf)。

这条路径保存整套拍摄设置。记录中包括 Image Settings、白平衡、ISO、曝光补偿、拍摄模式，以及 A、S、M 模式对应的光圈或快门等。它会连同曝光设置一起切换。Image Settings 仍只有两个自定义彩色样式。[机身手册第 129 页](https://www.ricoh-imaging.co.jp/english/r_dc/support/manual/pdf/gxr/GXR_E.pdf)列出了 My Settings 的保存范围。

机内真正的自定义彩色图像样式仍只有 `Setting 1` 和 `Setting 2`。每个样式可调全局鲜艳度、对比度、锐度，还可分别调整橙、绿、蓝、红、洋红五组颜色的色相与鲜艳度。[官方 Image Settings FAQ](https://www.ricoh-imaging.co.jp/english/r_dc/support/faq/bp/gxr/05/gxr05012.html)；[机身手册第 71 至 72 页](https://www.ricoh-imaging.co.jp/english/r_dc/support/manual/pdf/gxr/GXR_E.pdf)。

My Settings 能作为现有官方替代方案使用。它适合保存“色彩参数加白平衡加曝光”的完整配方。官方文档没有把 Box/Card 称为独立的色彩样式槽，也没有公开每条记录的文件格式。文档同样没有逐字段说明 Setting 1/2 的内部参数数组是否在每个 My Settings 记录中独立复制。真机需要补做两条记录使用同一个 `Setting 1`、但参数不同的交叉测试。完成这项测试前，不能宣称机身已有 12 个彼此独立的 Setting 1/2 参数组。

## 两套机制的区别

| 项目 | Image Settings 的 Setting 1/2 | My Settings |
|---|---|---|
| 用途 | 定义 JPEG 的颜色和锐度处理 | 保存一整套拍摄状态 |
| 数量 | 2 个固定自定义彩色样式 | MY1/MY2/MY3 三个拨盘位置，机身 Box 1 至 6，SD 卡 Card 1 至 6 |
| 可命名 | 官方手册没有提供 Setting 1/2 改名功能 | My Settings 可命名，最长 32 个字符，见机身手册第 133 页 |
| 颜色参数 | 鲜艳度、对比度、锐度；橙/绿/蓝/红/洋红各自的色相和鲜艳度 | 保存 Image Settings 这个拍摄菜单项目，同时保存白平衡、ISO、曝光等项目 |
| 调用 | 在 Image Settings 菜单中选 Setting 1 或 2 | 把 Box 或 Card 记录分配给 MY1/MY2/MY3，再转动模式拨盘 |
| SD 卡 | 没有单独导出 Setting 1/2 的官方功能 | 固件 1.50 起，A12 28mm/50mm 可保存至 Card 1 至 6 |

`Recall Settings` 还有两个同名但用途不同的入口，容易混淆：

- Image Settings 内的 `Recall Settings` 把一个现有图像样式的数值取出，允许修改后写入 Setting 1 或 Setting 2。这个入口不会增加配方库容量。[官方调节 FAQ，第 82 至 93 行所述操作](https://www.ricoh-imaging.co.jp/english/r_dc/support/faq/bp/gxr/05/gxr05013.html?sscl=f_n5fc02)。
- Key Custom Options 内的 `Recall My Settings` 把 My Settings Box 中的完整记录分配给 MY1、MY2 或 MY3。机身手册第 131 页说明了目标和来源选择。

## Image Settings 可调参数

### Setting 1 和 Setting 2

官方 FAQ 给出的字段如下：

- 全局鲜艳度。
- 对比度。
- 锐度。
- Individual Color Settings 中，橙、绿、蓝、红、洋红各有独立的色相和鲜艳度。

官方资料对档位数有一处冲突。Image Settings 总览 FAQ、GXR 宣传册第 13 页和机身界面都写或显示 9 级。另一篇调节 FAQ 的第 36 行把前三项写成 5 级，同时把各颜色参数写成 9 级。这里采用 9 级作为较可信结论，并保留该冲突，等待真机菜单核对。[9 级总览 FAQ](https://www.ricoh-imaging.co.jp/english/r_dc/support/faq/bp/gxr/05/gxr05012.html)；[存在 5 级表述的 FAQ](https://www.ricoh-imaging.co.jp/english/r_dc/support/faq/bp/gxr/05/gxr05013.html?sscl=f_n5fc02)。

### 其他可调图像样式

- Black & White 可调对比度、锐度。
- B&W (TE) 可选 Sepia、Red、Green、Blue、Purple 色调，并可调鲜艳度、对比度、锐度。
- Vivid、Standard、Natural 是固定样式。`Recall Settings` 可把它们的数值作为 Setting 1/2 的起点。

以上项目由官方 FAQ 和机身手册第 71 至 72 页直接确认。

## My Settings 保存和调用关系

### 三个拨盘位置

MY1、MY2、MY3 是拍摄时直接调用的位置。转到对应位置，机身载入保存的拍摄模式和其他项目。进入 MY 模式后临时修改的值，在切到其他模式或关机时会恢复为已保存值。[机身手册第 57 页](https://www.ricoh-imaging.co.jp/english/r_dc/support/manual/pdf/gxr/GXR_E.pdf)。

### 机身 My Settings Box

机身有 Box 1 至 6。`Reg. My Settings` 可把当前设置保存到某个 Box。`Recall My Settings` 再把某个 Box 分配给 MY1、MY2 或 MY3。直接保存到 MY1/2/3 的记录与 Box 记录可以彼此独立。机身手册第 130 至 131 页还说明，编辑一个已经分配给拨盘的 Box 后，下次转到该拨盘位置时会读到更改；直接保存到 MY1/2/3 的设置不会反向改写 Box。

### SD 卡 Card 1 至 6

固件 1.50 给 A12 28mm、A12 50mm、S10、P10 增加 Card 1 至 6。GXR MOUNT A12 和 A16 的官方手册把该功能列为初始能力。1.51 包含 1.50 及此前更新，所以六种模块在 1.51 下都支持 Card 1 至 6。[官方按模块功能表，第 113 至 119 行](https://www.ricoh-imaging.co.jp/english/r_dc/download/firmware/gxr/bymodes.html?sscl=f_n2fc01)；[1.50 补充手册 PDF 第 1 页](https://www.ricoh-imaging.co.jp/english/r_dc/download/firmware/docs/gxr_vup_en.pdf)。

Ricoh 的官方页面在 A12 50mm 这一格存在冲突。按模块功能表的本地快照 `feature-table.html:533-541` 把 A12 28mm 和 A12 50mm 都标为 `v1.50`；官方固件功能介绍的本地快照 `product-firmware.html:306-311` 也明确把 A12 50mm 列入可保存 My Settings 到 SD 卡的模块。固件修订历史中的另一张 1.50 矩阵却在 A12 50mm 列显示 `--`，见 `firmware-index.html:568-577`。本报告保留前两份直接材料共同支持的“1.50 起支持”结论，同时把第三张矩阵记录为官方资料冲突。真机实验开始前必须同时核对固件版本和菜单中是否实际出现 `Card 1` 至 `Card 6`。

官方宣传册写明 Box 与 SD 卡中的 My Settings 可快速分配到模式拨盘。官方 1.50 介绍还明确说，SD 卡保存功能用于让用户交换拍摄设置。因此，官方支持的“导出/导入”形态是把完整 My Settings 保存到 SD 卡，再从 SD 卡记录调用。官方没有公布电脑可编辑的文件格式、文件名、校验方式，也没有说明能否在菜单中直接执行 Box 与 Card 之间的复制。

### 机身设置与模块设置

`Start Settings Readout` 是另一套机制。关机时，当前设置会同时写入机身和相机模块；开机时可选从 Body 或 Camera Unit 读回。它用于换模块时决定采用哪一份当前拍摄状态，不会增加 My Settings 配方槽。[机身手册第 150 页](https://www.ricoh-imaging.co.jp/english/r_dc/support/manual/pdf/gxr/GXR_E.pdf)。

## My Settings 会保存哪些内容

机身手册第 129 页列出以下范围：

- 拍摄模式，包括 Auto、P、A、S、M、Scene。
- A、M 模式的光圈，S、M 模式的快门速度。
- 手动对焦、微距、闪光灯、自拍、显示模式。
- 除 Interval Shooting、Auto Aperture Shift、Switch Shooting Mode 外的全部 Shooting menu 项目。这里包含 Image Settings、曝光补偿、白平衡、ISO、测光、画质、降噪等。
- 一组指定的 Setup 项目，包括 ISO Auto-High、曝光/闪光补偿步进、水平仪和网格等。
- 白平衡补偿默认不随 My Settings 保存。先把 `My Settings WB Comp.` 设为 On 才会保存。
- Fn1/Fn2 分配默认不随 My Settings 保存。先把 `My Settings for Fn Settings` 设为 On 才会保存。

因此，一条用于“色彩配方”的 My Settings 至少会连同拍摄模式和一批拍摄参数一起调用。若要减少副作用，可把各条记录统一设成同一个拍摄模式、测光、ISO 逻辑和按钮配置，只改变 Image Settings、白平衡及所需曝光补偿。

## 固件 1.51

Ricoh 于 2012-06-26 发布 1.51。官方页面列出机身及 A12 28mm、A12 50mm、GXR MOUNT A12、A16、S10、P10 的 1.51 固件，并说明每换一个模块都要重新执行一次更新。[官方 1.51 下载页](https://www.ricoh-imaging.co.jp/english/r_dc/download/firmware/gxr/index.html?sscl=f_n1fc03ql)。

对 A12 28mm 和 A12 50mm，1.51 新增的相关修正只有一项：改善负曝光补偿与 Multi-P AUTO 白平衡组合下的图像质量。SD 卡 My Settings 是 1.50 加入的。1.51 没有增加新的 Image Settings 槽，也没有增加新的 My Settings 槽。

当前机身版本未知。若低于 1.50，A12 28mm/50mm 不会出现 Card 1 至 6。可在 Setup 菜单的 `Firmware Version` 查看版本。此项菜单在较早固件中已加入，1.50 又加入了从菜单启动升级的能力。[官方版本功能表](https://www.ricoh-imaging.co.jp/english/r_dc/download/firmware/gxr/bymodes.html?sscl=f_n2fc01)。

## 模块差异

| 模块 | 1.51 下 Card 1 至 6 | My Settings 的模块专属项 | 证据 |
|---|---:|---|---|
| A12 50mm Macro | 有，1.50 加入 | Focus Ring Settings；固定焦距，无 Zoom Position | [A12 50mm 手册第 20 页](https://www.ricoh-imaging.co.jp/english/r_dc/support/manual/pdf/gxr/GRLENS_E.pdf)；[1.50 功能表](https://www.ricoh-imaging.co.jp/english/r_dc/download/firmware/gxr/bymodes.html?sscl=f_n2fc01) |
| A12 28mm | 有，1.50 加入 | Focus Ring Settings、Spot AF Area Setting；固定焦距，无 Zoom Position | [A12 28mm 手册第 28 页](https://www.ricoh-imaging.co.jp/english/r_dc/support/manual/pdf/gxr/a12-28_e.pdf)；[1.50 功能表](https://www.ricoh-imaging.co.jp/english/r_dc/download/firmware/gxr/bymodes.html?sscl=f_n2fc01) |
| GXR MOUNT A12 | 有，初始支持 | 可在 My Settings 的 Lens Info. Input 编辑镜头名、焦距、光圈；这些信息写 Exif，不改变拍摄设置 | [MOUNT A12 手册第 38 页](https://www.ricoh-imaging.co.jp/english/r_dc/support/manual/pdf/gxr/mount_a12_en.pdf) |
| A16 24-85mm | 有，初始支持 | Spot AF Area Setting、Zoom Position | [A16 手册第 34 页](https://www.ricoh-imaging.co.jp/english/r_dc/support/manual/pdf/gxr/a16_en.pdf) |
| S10 24-72mm | 有，1.50 加入 | Step Zoom、Zoom Position | [S10 手册第 23 至 25 页](https://www.ricoh-imaging.co.jp/english/r_dc/support/manual/pdf/gxr/RLENS_E.pdf)；[1.50 补充手册第 1 页](https://www.ricoh-imaging.co.jp/english/r_dc/download/firmware/docs/gxr_vup_en.pdf) |
| P10 28-300mm | 有，1.50 加入 | Step Zoom、Zoom Position | [P10 手册第 46 至 49 页](https://www.ricoh-imaging.co.jp/english/r_dc/support/manual/pdf/gxr/P10_E.pdf)；[1.50 补充手册第 1 页](https://www.ricoh-imaging.co.jp/english/r_dc/download/firmware/docs/gxr_vup_en.pdf) |

A12 28mm、A12 50mm、A16 的官方对比表列出的 Image Settings 选项相同，都是 Vivid、Standard、Natural、B&W、B&W (TE)、Setting 1、Setting 2。[官方三模块对比 FAQ](https://www.ricoh-imaging.co.jp/english/r_dc/support/faq/bp/gxr/06/gxr06000.html?sscl=f_n6fc01)。

## 已确认、推断和未知

### 官方文档已确认

- A12 28mm 和 A12 50mm 在 1.50/1.51 上可保存到 Card 1 至 6。
- 机身有 6 个 My Settings Box，SD 卡有 6 个 Card 记录，拨盘有 3 个快速调用位置。
- My Settings 保存整套拍摄设置，并包括 Image Settings 这个 Shooting menu 项目。
- My Settings 可以命名，最长 32 字符。原始机身手册对 MY1/2/3 和 Box 明确说明此能力。
- SD 卡中的 My Settings 可用于交换拍摄设置并分配给模式拨盘。
- Setting 1/2 有全局鲜艳度、对比度、锐度，以及五组颜色各自的色相与鲜艳度。

### 有依据的推断

- Card 记录应沿用 My Settings 的名称。1.50 补充文档把 Card 列为同一个 `Reg. My Settings` 的保存位置，但没有再次写出 Card 条目的改名步骤。
- SD 卡记录应包含 Image Settings、白平衡和曝光等完整项目。官方称其为 My Settings，并说明它用于交换 shooting settings，但没有公开 Card 记录的逐字段结构。

### 仍未知

- 同时保存两条都选择 `Setting 1`、但内部颜色参数不同的 My Settings 后，二者能否保持各自的参数。官方手册没有逐字段说明 Setting 1/2 参数数组的复制方式。
- Card 项能否在机内单独改名，以及名称在换卡、换机身、换模块后是否完整保留。
- SD 卡上的实际文件路径、文件格式、校验字段及跨固件兼容规则。
- SD 卡缺失、写保护、损坏或 Card 槽数据损坏时的回退行为。
- A12 28mm 创建的 Card 记录在 A12 50mm 下调用时，模块专属字段如何处理。

## 最小真机实验

1. 确认机身配 A12 28mm 和 A12 50mm 时各自显示的固件版本，并检查 `Reg. My Settings` 菜单是否实际出现 Card 1 至 6。两组都应为 1.50 或 1.51，最好为 1.51。A12 50mm 必须保留菜单照片，用于裁定三份官方页面的冲突。
2. 在 P 模式建立记录 A。选择 Setting 1，把鲜艳度和红色色相调到容易辨认的两个极值，同时设置独特白平衡补偿和曝光补偿。保存到 Box 1 和 Card 1，并命名。
3. 改动同一个 Setting 1 的颜色参数，建立记录 B。保存到 Box 2 和 Card 2。
4. 依次把 A、B 分配给 MY1，关机重启后拍摄同一静物 JPEG。每次记录菜单值、Exif、直出 JPEG 和屏幕照片。
5. 拔卡后重复调用 Box 1/2，确认机身槽不依赖 SD 卡。再插入另一张空卡，记录 Card 菜单和错误行为。
6. 在两个 A12 模块之间交换同一张卡，分别调用 Card 1/2，核对名称、颜色参数、白平衡、曝光和模块专属项。

这组实验会直接回答官方资料没有写清的核心问题：My Settings 是否复制 Setting 1/2 的内部颜色参数，还是只保存对两个全局样式的选择。

## 后续实现验收

若后续仍要修改固件以增加独立配方槽，验收至少包括：新增配方选择、编辑、命名、保存、关机重启保留、覆盖、删除、SD 卡缺失和损坏、A12 两模块切换、JPEG 可见效果，以及与现有 Setting 1/2、MY1/2/3、Box、Card 的兼容。没有真机 JPEG 和重启证据时，不能宣称新增配方已经可用。

## 本地证据与哈希

官方资料保存在 `research/recipes/sources/`。本次没有下载或运行固件二进制。

| 文件 | 内容 | SHA-256 |
|---|---|---|
| `GXR_E.pdf` | GXR 机身英文手册，204 页 | `8c02e4499294fe6c1fcabb825f644773bcda357b57ffa463a5ff560677870b14` |
| `gxr_vup_en.pdf` | 1.17 至 1.50 功能扩展补充手册，2 页 | `1d88241d13699a890e9b3d62ac503051af12afccfb9fab37342ded23053684b5` |
| `GXR-brochure.pdf` | GXR 官方宣传册 | `fb49ae003611acb5b253005fb3df0bdb6d853696973a9a23b54d66bd606f4726` |
| `a12-28_e.pdf` | A12 28mm 英文手册 | `acf5df1420981941eba95976ef39a0cc4c11157399433ddec13e2c7c646c5515` |
| `GRLENS_E.pdf` | A12 50mm Macro 英文手册 | `61aecd405c01185ebb5e34732871fcddea92b8bf2a9314690451274b5bc6936e` |
| `mount_a12_en.pdf` | MOUNT A12 英文手册 | `d257604ca7df3a001148bfa2c3e577588f57fb572157523cf9fcc12d5831e368` |
| `a16_en.pdf` | A16 英文手册 | `edbc19601ea0f3ba9b3484fec72a26f098f43eb139f6675e7f9349925e904740` |
| `RLENS_E.pdf` | S10 英文手册 | `2a922c27e4b35c068a35fa98967ca109619b4f99295a7cbd9b8be6a4f2de86cf` |
| `P10_E.pdf` | P10 英文手册 | `79b86f6ad99dd329f36fd5ec969876470f93297f4f9f1954e83b8d721f5a926d` |
| `firmware-index.html` | 1.51 下载页与修订历史 | `45afd03e0691dc8183564dd84c3f63fff1b24ed76ab1c7e38ad95f02b7d8dcb5` |
| `feature-table.html` | 按模块整理的功能版本表 | `2ef700e9c02636fe93cc6dd0eb18c39b5a7c857f0d9d8c20f5c18c03e7d12cf9` |
| `image-settings-faq.html` | Image Settings 官方 FAQ | `e3fc885d9403400d136490cd8a6c9d22275ec49328d74c610f663734fb774cb1` |
| `image-settings-adjust-faq.html` | 参数调节官方 FAQ | `46a805fc87ea81e910919cb589a16d394387eaa52b2ad6020f34647902085d0f` |
| `product-firmware.html` | 官方固件功能介绍 | `bde21bf3a29407c428806d59e70e8a25723d37318742d132422ddfed8ab3a752` |

主要检查命令：

```sh
pdfinfo research/recipes/sources/GXR_E.pdf
pdftotext -layout research/recipes/sources/GXR_E.pdf /tmp/gxr_manual.txt
pdftotext -layout research/recipes/sources/gxr_vup_en.pdf /tmp/gxr_vup_en.txt
rg -n "Image Settings|Reg. My Settings|Recall My Settings|My Settings Box|Card" /tmp/gxr_manual.txt /tmp/gxr_vup_en.txt
shasum -a 256 research/recipes/sources/*
```
