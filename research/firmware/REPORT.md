# Ricoh GXR 1.51 色彩配方固件研究（首轮）

日期：2026-10-12  
优先机型：GXR 机身 + GR LENS A12 50mm F2.5 MACRO、GR LENS A12 28mm F2.5  
研究范围：公开资料与官方 1.51 升级包的只读静态分析；未操作相机、未刷写、未写入配置。

## 结论

**新增配方的首个定位候选是机身 `ilaunch3` 中的 SD 卡 My Settings `.IFO` 文件路径和文件接口地址。现在还不能直接改固件：Setting 1/2 的内部色彩参数是否随每个 My Settings 槽独立保存仍未确认，`.IFO` 结构和 A12 模块侧的色彩应用函数也未定位。**

原厂 1.51 已经提供 3 个拨盘 My Settings、6 个机身 Box 和 6 个 SD 卡槽。官方手册说 My Settings 会保存大多数拍摄菜单项，但没有明确说 Setting 1/2 下面的 3 个全局字段（鲜艳度、对比度、锐度）以及橙、绿、蓝、红、洋红 5 组颜色各自的色相和鲜艳度会复制进每个槽。因此 6 个 SD 槽可能只保存“选择 Setting 1”这一项，所有槽仍共享同一套 Setting 1 参数。这个问题必须先用一张备用 SD 卡做单变量实验。

固件中已经确认 `/ATA1/MYSET`、`/ATA1/MYSET/MYSET… .IFO`，并找到路径和文件接口地址的静态构造候选。它们都在机身主程序 `ilaunch3`；A12 50 的 `jlaunch3` 和 A12 28 的 `qlaunch3` 没有 `MYSET` 字符串。两款模块各有自己的程序和 `LADJ` 调整数据路径，说明机身负责卡文件界面和路径的可能性很高，模块仍可能负责色彩状态的生成、应用或序列化。

当前没有可证明安全的代码空洞。`ilaunch3` 的 15 个段间 `0xFF` 间隙没有装载地址，不能直接放运行代码；段内长零区和 `0xFF` 区也没有经过引用、用途和内存权限验证。现有中文补丁只在原函数位置做等长替换。

## 证据表

| 判断 | 级别 | 直接证据 |
|---|---|---|
| Image Settings 的 Setting 1/2 可调 3 个全局字段，以及 5 组颜色各自的色相和鲜艳度 | 官方文档已确认 | [GXR Camera Body User Guide](https://www.ricoh-imaging.co.jp/english/r_dc/support/manual/pdf/gxr/GXR_E.pdf)，PDF 物理页 83–84（印刷页 71–72）；A12 28 [官方 FAQ](https://www.ricoh-imaging.co.jp/english/r_dc/support/faq/bp/gxr/05/gxr05012.html) |
| My Settings 有 MY1/MY2/MY3、Box 1–6；1.50 起可保存到 Card 1–6 | 官方文档已确认 | 同一机身手册 PDF 物理页 141–144（印刷页 129–132）；[1.50 功能对应表](https://www.ricoh-imaging.co.jp/english/r_dc/download/firmware/gxr/bymodes.html?sscl=f_n2fc01)；[官方功能说明](https://www.ricoh-imaging.co.jp/english/products/gxr/firmware.html)；[官方比较 FAQ](https://www.ricoh-imaging.co.jp/english/r_dc/support/faq/bp/gxr/06/gxr06000.html) |
| My Settings 保存大多数拍摄菜单项；设置会随相机模块而不同 | 官方文档已确认 | 机身手册 PDF 物理页 141–144（印刷页 129–132） |
| 关机时设置会保存到机身和相机模块，开机可选从 Body 或 Camera Unit 读取 | 官方文档已确认 | 机身手册 “Start Settings Readout”，PDF 物理页 162（印刷页 150） |
| 官方升级包区分机身和六种模块，装上相应模块后各自更新 | 官方文档已确认 | [GXR 固件下载页](https://www.ricoh-imaging.co.jp/english/r_dc/download/firmware/gxr/index.html?sscl=f_n1fc03ql) |
| 当前官方 ZIP SHA-256 是 `3705984b…fc898`；29 个文件与固定上游哈希一致 | 静态分析已确认 | `artifacts/firmware-inventory.json:1-7`；哈希基准在 `sources/gxr-language-patch/gxr_firmware_modifier.py:19-49`。这个检查只能证明文件与固定源码表一致；Ricoh 未提供可验证签名。 |
| CPU 指令集是 Renesas M32R | 静态分析已确认 | 固件反复出现 M32R `BL` 的 `0xFE + pcdisp24` 编码，项目编码器见 `gxr_firmware_modifier.py:94-101`；编码定义见 [Renesas M32R Family Software Manual](https://www.renesas.com/en/document/mah/m32r-family-software-manual)。具体芯片型号仍未知。 |
| `ilaunch3` 是 16 段专用可执行容器，头长 `0x200` | 静态分析已确认 | 段表见 `research/firmware/ilaunch3-sections.csv:1-17`；上游结构说明见 `sources/gxr-language-patch/研究资料/报告/GXR_1.51_逆向初步报告.md:132-159`。 |
| 加权校验的初始相位随容器类型变化 | 静态分析已确认 | 本轮重跑 29 个文件：所有 `*launch0/*firm0` 匹配 phase 2，`l06firm5` 匹配 phase 4，其余 21 个文件匹配 phase 0。结果在 `research/firmware/scan.json` 的 `weighted_checksum_matching_phases`；算法及适用范围修正见 `sources/gxr-language-patch/研究资料/报告/GXR_1.51_英文入口重定向简体中文_保底包报告.md:99-123`。phase 0 不匹配不表示文件损坏。 |
| 语言补丁只修改机身 `ilaunch3` | 源码已确认 | 输出清单见 `gxr_firmware_modifier.py:277-294`；输入 29 文件哈希检查见 `:205-245`。 |
| 语言补丁没有证明存在空闲代码空间 | 源码已确认 | English 模式替换文件偏移 `0x1C348/0x1C774/0x1C778/0x176150`，见 `gxr_firmware_modifier.py:140-152`；Unlock 模式替换 `0x2D1C8/0x30FDC8/0x327140`，见 `:155-188`。这些位置都有原始指令匹配，是等长覆盖。 |
| 仅改资源且通过校验仍可能真机失败 | 上游真机报告 | 首次七个 `*launch4` 资源重定向实验出现乱码，见 `sources/gxr-language-patch/研究资料/报告/GXR_1.51_英文入口重定向简体中文_保底包报告.md:1-15`。这说明静态资源和校验通过不能替代完整初始化路径验证。 |
| REA 当前不能直接分析这个无 ELF 外壳的 M32R 多段程序 | 源码已确认 | REA 只接收提取后受支持的 ELF；不提供 raw flash profile，见 `sources/rea/docs/firmware-analysis.md:1-10,125-128`。本项目专用段解析器更适合首轮定位。 |

## 升级文件与模块职责

本轮静态证据支持以下映射：

| 文件前缀 | 单元 | 直接证据 |
|---|---|---|
| `ilaunch*` | GXR 机身 | `ilaunch3` 标记 `R_NS1_REFLECTOR`；包含 BADJ、BKIZ、My Settings 卡路径和机身 UI 字符串。 |
| `jlaunch*` | A12 50mm Macro | `jlaunch3` 文件偏移 `0x7A2F8` 是 `RICOH GR LENS A12 50mm F2.5 MACRO`；SHA-256 `951be1c6…1673`。 |
| `qlaunch*` | A12 28mm | `qlaunch3` 文件偏移 `0x7A320` 是 `RICOH GR LENS A12 28mm F2.5`；SHA-256 `e487d00b…6690`。 |

`jlaunch3` 的 `/ATA1/LADJRAM.DAT` 位于文件偏移 `0x713ED` 和 `0x71647`；`qlaunch3` 位于 `0x71415` 和 `0x7166F`。两者都有 `/ATA1/PARAM.DAT`，但没有 `MYSET`。这只能证明字符串与静态路径分布，不能证明 My Settings 的完整数据只存在机身侧。

升级包的同前缀文件大致分工如下：`*0` 是 Monitor/维护组件，`*3` 是多段主程序，`*4` 是资源容器，`*8` 是寄存器/控制初始化文本。上游的结构依据见 `sources/gxr-language-patch/研究资料/报告/GXR_1.51_逆向初步报告.md:161-214`。`l06firm5` 是 A16 专有的第五文件，本轮没有推断其业务职责。

## My Settings 卡文件定位

### 字符串和地址

`ilaunch3` 第 4 段映射为：文件偏移 `0xBE200` → 运行地址 `0x20109000`，初始化长度 `0x39C9C`。相关字符串位于：

| 内容 | 文件偏移 | 运行地址 |
|---|---:|---:|
| `/ATA1/MYSET` | `0xF6870` | `0x20141670` |
| `/MYSET` | `0xF687C` | `0x2014167C` |
| `.IFO` | `0xF6883` | `0x20141683` |
| `MY SETTING CARD` | `0xF6888` | `0x20141688` |
| 第二个 `MY SETTING CARD` | `0xF6898` | `0x20141698` |
| 第一组 `/ATA1/MYSET/MYSET` | `0xF68B8` | `0x201416B8` |

从 `0xF68B8` 到 `0xF69AD` 还有多组完整路径和 `.IFO` 后缀。重复次数代表多条操作路径，不能直接解释成槽数。

### 静态地址构造候选和文件接口

M32R 代码可通过 `SETH` + `OR3` 组成 32 位地址。本轮脚本在文件区间 `0xD2000–0xD6000` 找到以下 4 字节对齐的静态地址构造候选。脚本没有解码控制流，也没有证明两个指令之间的寄存器未被覆盖，因此这些结果不能单独证明运行时会调用对应函数：

| 作用 | 函数地址 | 地址构造候选示例（文件偏移 → 运行地址） |
|---|---:|---:|
| 打开读取候选 | `0x200A40B4` | `0xD3620` → `0x2011E420`；另有 11 处 |
| 关闭候选 | `0x200A437C` | `0xD366C` → `0x2011E46C`；另有 12 处 |
| 读取 | `0x200A449C` | `0xD364C` → `0x2011E44C`；区间内共 9 处 |
| 写入 | `0x200A45E8` | `0xD34F8` → `0x2011E2F8` |
| 删除 | `0x200A4910` | `0xD51C8` → `0x2011FFC8` |
| 目录操作候选 | `0x200A4958` | `0xD29E0` → `0x2011D7E0` |
| 创建/写入打开 | `0x200A544C` | `0xD2AB8` → `0x2011D8B8` |

文件接口名称来自独立调用链。`/ATA1/PARAM.DAT` 的导入/导出代码把同一组地址解释为读取、写入、删除和创建函数，见 `sources/gxr-language-patch/研究资料/报告/GXR_参数打印与镜像差异_第六阶段.md:36-59`。My Settings 路径附近又出现这些地址的构造候选。`0x200A40B4`、`0x200A437C` 和 `0x200A4958` 的更细名称仍标为候选。

关键路径地址构造候选包括：

| 路径/标签 | 候选文件偏移 | 候选运行地址 |
|---|---:|---:|
| `/ATA1/MYSET` | `0xD29BC` | `0x2011D7BC` |
| `MY SETTING CARD` | `0xD2AE8` | `0x2011D8E8` |
| 第二个 `MY SETTING CARD` | `0xD2BA0` | `0x2011D9A0` |
| `/ATA1/MYSET/MYSET…` | `0xD35C0` | `0x2011E3C0` |
| 同类路径 | `0xD47EC` | `0x2011F5EC` |
| 同类路径 | `0xD5130` | `0x2011FF30` |
| 同类路径 | `0xD5220` | `0x20120020` |

完整可重跑结果在 `research/firmware/mysettings-trace.json`，生成脚本是 `research/firmware/trace_mysettings.py`。

### 尚未定位的数据

- `.IFO` 的真实文件名、槽编号格式、文件长度、头部、版本、校验和记录布局。
- Setting 1/2 的 13 个字段是复制进每个 `.IFO`，还是保存在机身/模块的一份全局结构里。
- `CONTRAST`、`HUE`、`SATURATION`、`SHARPNESS` 出现在 `ilaunch3` 文件偏移 `0x35E099/0x35E0C3/0x35E0D1/0x35E0DF`，运行地址 `0x203A8E99/0x203A8EC3/0x203A8ED1/0x203A8EDF`。它们和亮度、增益、白平衡、Gamma 同处一个调整参数名表，目前没有证据把它们等同于用户 Image Settings 结构。
- A12 50 和 A12 28 的色彩处理函数、机身到模块的设置消息，以及两个模块是否共用序列化结构。

## 代码空间与持久化边界

`ilaunch3` 有 15 个段间填充区，全部是 `0xFF`，长度从 `0x5A` 到 `0x3F0`。最大的两个是 `0x3F0`。它们不属于任何段记录，所以升级加载器不会把这些字节装入运行地址。修改段表可能影响装载、校验、BSS 邻接和内存布局；当前没有这种修改的真机证据。

段内较大的均匀区包括：

| 文件偏移 | 运行地址 | 长度 | 字节 | 结论 |
|---:|---:|---:|---:|---|
| `0x796C` | `0x2005276C` | `0x2094` | `FF` | 已装载候选；用途未知 |
| `0x3BC4D4` | `0x204072D4` | `0x2004` | `FF` | 已装载候选；用途未知 |
| `0xBB56C` | `0x2010636C` | `0x1E8E` | `00` | 已装载候选；可能是保留表/缓冲 |
| `0x86A38` | `0x200D1838` | `0x1C48` | `FF` | 已装载候选；用途未知 |
| `0x1DC760` | `0x20227560` | `0x1AEB` | `00` | 已装载候选；可能是保留表/缓冲 |

这些位置只有“长均匀字节”证据。投入代码前至少要证明：无静态引用、无运行时写入、所在段可执行、不会覆盖持久缓冲、A12 50/28 的启动路径都不使用该区。当前一个也没有满足。

## 可实施路径

### 路径 1：先利用原厂 My Settings Card

这是优先路径。若最小实验确认每个 `.IFO` 独立包含 Setting 1/2 子参数，原厂已经可以保存 6 套卡配方，Box 1–6 还可作为机身内的另一组来源。先做一个电脑端配方库，在相机之外备份、命名和轮换 `.IFO` 文件，可以避免首版固件修改。

这个路径的条件是验证 `.IFO` 的完整性字段、模块标识和跨卡复制行为。官方 FAQ 只承诺同一 GXR、相同模块组合的卡设置可用，不能把 A12 50 的卡文件直接当成 A12 28 配方。

### 路径 2：扩展现有 `.IFO` 槽枚举

若目标必须在相机内显示超过 6 套配方，优先验证并复用 `ilaunch3` 中现有的文件路径和文件接口候选：

1. 从 `0x2011D7BC–0x20120908` 的路径构造和文件操作代码向上恢复函数边界。
2. 用真实 Card 1/2 文件定位槽编号、最大值 `6`、目录枚举和 `.IFO` 校验。
3. 在 `ilaunch3` 改槽枚举和选择逻辑；如果显示资源需要新文本，再改 `ilaunch4`。
4. 只有在 `.IFO` 不包含色彩子参数时，才继续追踪机身到 `jlaunch3/qlaunch3` 的设置传输和模块侧应用函数。

这里还没有可写补丁：菜单数量、结构大小、代码放置地址、异常回滚和两款 A12 的兼容性都未确认。

### 路径 3：新增独立 Recipe 结构

这是成本最高的路径。它需要定义配方记录、版本、校验、模块类型和迁移规则，还要在机身 UI、SD 持久化、模块色彩应用三处接线。只有当原厂 `.IFO` 无法承载独立 Setting 1/2 参数时再采用。

建议的最小记录字段是：`version`、`module_id`、`image_setting_mode`、鲜艳度/对比度/锐度/单色颜色/色调、名称、记录校验。字段的真实宽度和取值范围必须来自 Card 文件差分或模块反汇编，当前不能自定后写入相机。

## 最小下一步实验

先做**原厂功能实验，不刷固件**。A12 50 和 A12 28 各用一张相机格式化的备用 SD 卡，步骤相同：

1. 记录当前 Setting 1 的全部 13 个字段：全局鲜艳度、对比度、锐度，以及橙、绿、蓝、红、洋红各自的色相和鲜艳度。只改一个字段，例如全局对比度从 `0` 改成 `+1`。
2. 保存到 Card 1。再把同一个参数改成 `-1`，保存到 Card 2。
3. 用电脑只读复制整张卡，记录 `/MYSET` 下的真实文件名、长度、SHA-256 和 FAT 时间。
4. 在相机上再把全局 Setting 1 改成第三个值并关机重启，然后分别调用 Card 1、Card 2。
5. 检查 UI 中全部 13 个字段是否分别恢复，并在固定曝光、固定白平衡、同一场景拍 JPEG；DNG 不作为色彩效果判断。
6. 对 Card 1/2 文件做二进制差分。确认按槽独立保存后，对 13 个字段逐个做单变量差分；每次只改一个字段，再重复一次相邻数值，找稳定变化字节和可能校验字段。

判定标准：

- 若 Card 1/2 调用后能恢复各自的 13 个字段，且 `.IFO` 有稳定单变量差分，直接沿 `.IFO` 路径扩展配方。
- 若两个槽调用后都使用最后一次全局 Setting 1，My Settings 只保存了模式选择；下一步要跟踪 Setting 1/2 的全局持久化结构。
- 若 A12 50 和 A12 28 的文件大小或差分位置不同，分开实现和版本化，不能共用裸记录。

当前协议禁止本轮操作相机和写配置，所以这里只给出实验设计，没有执行。

## 最终验收项

实现后需要在 A12 50 和 A12 28 上分别验证：新增配方选择、编辑、保存、关机重启保留、覆盖、删除；SD 卡缺失、只读、文件损坏时的行为；JPEG 的可见效果；与原有 Setting 1/2、MY1/MY2/MY3、Box 1–6、Card 1–6 的一致性；官方 1.51 恢复路径。静态构建、校验匹配和桌面文件测试不能替代这些真机验收。

## 可重跑命令与版本

来源版本：

- `sources/gxr-language-patch` commit `5a5366dd017827bc4c4e9e65a0253c4b947a78a0`
- `sources/rea` commit `ee50ed121e38cc6e1a2ff0dc8b789f15f71c5402`

本轮命令：

```bash
python3 research/firmware/scan_gxr_firmware.py \
  artifacts/firmware/gxr-1.51 \
  --output research/firmware/scan.json

python3 research/firmware/trace_mysettings.py \
  artifacts/firmware/gxr-1.51/ilaunch3 \
  research/firmware/ilaunch3-sections.csv \
  --output research/firmware/mysettings-trace.json

(cd sources/gxr-language-patch && \
  GXR151_OFFICIAL_DIR="$PWD/../../artifacts/firmware/gxr-1.51" \
  python3 -m unittest discover -s tests -v)
```

扫描器处理 29 个文件；所有文件都找到一个匹配的校验 phase。语言补丁测试使用当前官方固件样本后为 7/7 通过。
