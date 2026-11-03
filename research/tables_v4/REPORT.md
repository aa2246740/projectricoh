# v4 preliminary 表集

八套表均通过 Stage 2j 普通与 ASan/UBSan 主机加载、RPC、RAM 和字段差异检查。严格的全部设置回到初始值门槛未通过：原顺序 03→04 会保留两个黑白参数，两个 v3 基线也一样。所有表保持 `firmware_ready=false`，相机验收为 `pending`。六套 T1 仅预制，等待探针选择，没有一套标为就绪。

对象为 GXR 机身 1.51、GR LENS A12 50mm 单元 1.51 和 Stage 2j。DEEPTBL 文件格式仍为 v3；v4 是表集版本。本轮没有操作相机、SD 卡或 Git 提交。

## 交付与哈希

以下目录均在 `artifacts/stage2j-packages/`。每套包含完全相同的两份 3600 B DAT、`SHA256SUMS`、`manifest.json`、`NOTICE` 和 `field_diff.json`。校验和覆盖其余五个文件，并从磁盘重新读回核对。

| 表集 | DEEPTBL0/1.DAT 共同 SHA-256 |
|---|---|
| tables-v4-noprobe | `18a4b36f382da6898113c2361f5ee1fd851d51020e70ed77f2e8b09a38f0d4ee` |
| tables-v4-probe2 | `2d75ff50c9c8cd0b02d2f2c141801ea88364585da59f72663653a627f2e2896e` |
| tables-v4-t1/b5B_cG_dR | `ee7619c3448355cd1e249cd1a6245baafce13db5d8d50651e0b98f43f3844022` |
| tables-v4-t1/b5B_cR_dG | `8bb57ed55ed19958a0f7054b00baa20e9cead0c87c37784d8d8f14937c683f2e` |
| tables-v4-t1/b5G_cB_dR | `1d208b7af87323c0e72bf71277f54c5116290ae274d556f39ab6b596c0ee4e45` |
| tables-v4-t1/b5G_cR_dB | `8dd019a371f7d7b639ca92c0486565f8408b5b8be6e82c2f75208315024a4877` |
| tables-v4-t1/b5R_cB_dG | `ab687490e2df9e3f2a6d4e18b377f6ac5652cccbdb71fa7cd1dfecae63c27ee1` |
| tables-v4-t1/b5R_cG_dB | `a3fb5a78331f25f890e38c9421e30630368f2b761120168082c4500f2d1619c9` |

## 来源与主代理决策

基线 `tables-v3` 与 `tables-v3-noprobe` 的双份 DAT 及交接 SHA-256 均已核对。三份 fit 和 probe2 条目的哈希也符合交接值，具体输入路径及哈希见 validation.json。

02 使用 round4 的 `fit_v4_noT1.json`。源文件 `accepted=false`；主代理明确接受相对现用 02 的 LOO p90 +0.07、ISO 1600 灰块中位 +0.05，并以噪声范围内处理，覆盖原拒绝决定后批准装配。这里记录该决定，没有重算拟合指标，也没有修改源文件标记。

无 T1 的 06 使用 `accepted=true` 的 `fit_v4_noT1.json`，保留 v3 曲线，更新 Y 分支、分色矩阵和扇区。

06 T1 使用 `fit_v4_T1.json`，源文件 `accepted=false` 是相对无 T1 版本的严格比较结果。主代理的决定是：若相机证明 T1 有效，优先采用它。六种排列都通过原 `map_channels.py.mapped()` 生成，仅代表绝对曲线语义下的假设，没有把预填排列当作探针测量结果。

## 字段差异

01、03、04、05、07 的完整 entry 与 tables-v3 逐字节相同。A20/B20 全部不变，颗粒位全关。

| 表集 | 对照基线 | 仅有的配方字段变化 |
|---|---|---|
| tables-v4-probe2 | tables-v3 | 02 的扇区和两行 Y；06 的扇区、Y 分支及分色矩阵；08 的 C。 |
| tables-v4-noprobe | tables-v3-noprobe | 02 的扇区和两行 Y；06 的扇区、Y 分支及分色矩阵。 |
| 六套 tables-v4-t1 | tables-v3-noprobe | 02 同上；06 的 B5、两行矩阵、扇区、C/D、mask=0x07、control=0x0000。 |

各变化只另带对应行 CRC 和文件 CRC。02 和无 T1 的 06 的 A5/B5 保持原样。T1 的 06 保留 A5 节点，以指定排列分配 B5/C/D，矩阵只保留候选 Y 行和推导 row 2，没有分色行。C/D 单调且末值至少 128。02 和两版 06 的 row 2 均与原 `matrix_model.row2_from_row1()` 结果完全相同。

probe2 的 08 完整 entry 与交接条目一致。其余七套的 08 与旧 PrbB 完全相同。每个 field_diff.json 同时列出相对 tables-v3 和 tables-v3-noprobe 的实际变化，包括跨基线比较时继承的 08 差异；不列未改字段。精确偏移只存 local/diffs/。

## 构建和主机验证

build_v4.py 只读导入原 make_table_files.py 的 src，调用原 entry()/seal()/parse()。08 合并和 RPC/RAM 校验复用 probe2 所用的父目录 helpers，不调用现有构建器 main()。所有成品均完成 parse、逐条 entry 重建、seal 和再次 parse，重建字节与磁盘 DAT 完全一致。

C 构建使用原 Stage 2j 七个源文件与等价驱动，参数为 `-std=c11 -O1 -g -Wall -Wextra -Werror`，定义 `RECIPE_FW_HOST`、`RFW_DEEP_ENABLED=1`、`EQUIV_2H`、`EQUIV_2I`。ASan/UBSan 另加 `-fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer`。

原顺序为 04 → 01 → 02 → 05 → 06 → 07 → 08 → 04 → 03 → 04。另用 scratch 驱动独立运行 04 → 02 → 04、04 → 06 → 04、04 → 08 → 04，覆盖每个变化槽。只替换 scratch 副本的 order 声明，原驱动保持不变。

最终完整校验轮编译 8 次、运行 80 次，其中 v4 为 64 次、两个基线为 16 次。全部退出 0，编译及运行日志均为空，没有 ASan/UBSan 诊断；普通与 sanitizer 的 40 对完整记录逐字节相同。

下表 RPC 数量对普通与 ASan/UBSan 均成立。六种 T1 排列的计数相同，payload 各自核对。

| 表集 | 顺序 | V | W | X | 其它 RPC | T 写入次数 |
|---|---|---:|---:|---:|---:|---:|
| tables-v4-probe2 | 040204 | 10 | 248 | 10 | 0 | 0 |
| tables-v4-probe2 | 040604 | 10 | 248 | 10 | 0 | 0 |
| tables-v4-probe2 | 040804 | 15 | 260 | 13 | 0 | 2 |
| tables-v4-probe2 | original | 41 | 1072 | 39 | 0 | 2 |
| tables-v4-noprobe | 040204 | 10 | 248 | 10 | 0 | 0 |
| tables-v4-noprobe | 040604 | 10 | 248 | 10 | 0 | 0 |
| tables-v4-noprobe | 040804 | 8 | 192 | 8 | 0 | 0 |
| tables-v4-noprobe | original | 34 | 1004 | 34 | 0 | 0 |
| 六套 T1 | 040204 | 10 | 248 | 10 | 0 | 0 |
| 六套 T1 | 040604 | 17 | 316 | 15 | 0 | 2 |
| 六套 T1 | 040804 | 8 | 192 | 8 | 0 | 0 |
| 六套 T1 | original | 41 | 1072 | 39 | 0 | 2 |

T 写入仅在 probe2 的 08 或 T1 的 06 进入、退出时出现。进入前先检查 stock T，C/D 写完后才把控制置 0 并读回；退出先恢复控制 2 并读回，再恢复行。noprobe 完全没有 T 写入。

全部 RPC 仅有 V/W/X，逐次请求、返回和顺序均符合原 helper 的预期。每次选择的七行 RAM、邻接与保护字节、T、设置区和重开菜单均已核对，颗粒探测始终为 0。每次返回 04，包括最后一次，七行、T 和保护字节均恢复 stock；4096 B 设置逐字节等于相同顺序的 v3 基线。

独立的 04→02/06/08→04 均把所有设置恢复到初始 04。原始完整顺序在最后 03→04 后，S+0x645/0x646 保留 03 的黑白对比度、锐度原始值 3/4，而初始驱动值为 0xa5/0xa5。原因是 recipe_v1/recipe_apply.c 对 Standard 的参数写入数为 0，保留不活动的黑白参数。这在两套 v3 和八套 v4 的普通与 sanitizer 运行中都一致；它不是本次 DAT 引入的差异，但确实不满足任务字面要求的全部设置回到初始值。固件为只读，本轮保留并报告这一缺口。

## 保全与复跑

首轮诊断在原顺序最终 04 的严格设置比较处停止；当轮已编译 1 次并运行 10 个原顺序驱动。复核两个基线和参数写入代码后，保留该失败门槛的记录，再跑上述完整校验轮。初始诊断见 local/initial-settings-check.json；完整校验结果没有将全部设置恢复判为通过。

写入前已检查指定 UUID 的可写 APFS 卷并运行 df。构建依赖清单共 47 个文件，起止内容哈希、大小、mtime 和 mode 相同。共享仓库另有工作者，未据此声称整个检出零变化。

本任务只写三个指定 v4 包根目录、research/tables_v4/ 和 /tmp/tv4/。DAT、映射数据、RPC/RAM 记录位于已通过 git check-ignore 的目录。公开文件只含代码、说明、计数和哈希，不含 48 B 以上派生原始字节串或表数组。编译器临时文件及驱动副本放 /tmp/tv4/。

完整结果见 [validation.json](validation.json)，原始记录在 local/transcripts/，命令和日志在 local/commands/ 与 local/logs/。

```sh
python3 -I -B /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/tables_v4/build_v4.py
```

静态确认：格式、来源、排列打包和字段边界。主机观察：真实 C 加载器的模拟 RPC 与状态恢复。未知：相机上的 T1 通道映射、绝对曲线语义和照片效果。本交付不构成相机验收。


## v4r2：替换 05 Classic Chrome

八套 v4r2 已生成，普通与 ASan/UBSan 校验完成；现有八套 v4 包的全部文件和目录元数据保持原样。六套 T1 仍仅预制，firmware_ready=false，相机验收 pending。

05 改用 research/color_fit_v2/05_classic_chrome/round4/local/fit_v4_noT1.json，输入 SHA-256 为 `09ff782e1c26f0e907ed53500d2def49238be57230685f1a6e2448a25176ac89`。源文件 accepted=false 保持原样，主代理明确覆盖该决定。

覆盖理由由主代理提供：它仅因额外 Y 行规则被拒，ISO1600 LOO 差 0.003；相对 v3，两种 ISO 的全部主指标均改善，LOO 中位 3.15→2.67、ring 2.41→1.65，两项 p90 和灰块偏色也改善。本次只核对格式与源数据，没有重算这些指标。

以下目录均在 artifacts/stage2j-packages/；每套两份 DAT 完全相同、各 3600 B，并包含 SHA256SUMS、manifest.json、NOTICE 和 field_diff.json。

| 表集 | DEEPTBL0/1.DAT 共同 SHA-256 |
|---|---|
| tables-v4r2-probe2 | `40665151292dcb2405d22f80092a474caa7959d9f60aceeb11d55755c19ae0ef` |
| tables-v4r2-noprobe | `7f951a4dc5193dd6c5d00173f0016ab8804f33675c330a50c74b76fbdef4c4dd` |
| tables-v4r2-t1/b5R_cG_dB | `0b716e938bd523c2a26d87b0e55c0274e397d439b5aa0fd9b7b996a57ab287e0` |
| tables-v4r2-t1/b5R_cB_dG | `507fd71abffb3768e34a4d53dc2db9e2c66615d0df2ffb5a5ad3011b95f56f8a` |
| tables-v4r2-t1/b5G_cR_dB | `e50c003fc7fa7af683168b394acf3916cbe1de9ceadc85e1870c978670b74317` |
| tables-v4r2-t1/b5G_cB_dR | `f74fa7e8379ba5143f2d88fad6728066ea56bf6dc4195df73e5f2ae4c5483b7d` |
| tables-v4r2-t1/b5B_cR_dG | `e370153cc9ed69c118af4d4ed32ee6063570199574f9d974d2625867a06f3bbf` |
| tables-v4r2-t1/b5B_cG_dR | `690546efbd36a8f9a581e5bac549e89e86a6453879c95f533a3092684f2db449` |

相对各自 v4，差异仅在 entry4，即槽位 05 的扇区、矩阵和两项行 CRC，以及文件 CRC。05 的 A5/B5 与 v4、v3 逐字节相同；其余七个完整 entry、mask、控制字、A20/B20/C/D 均保持原样。矩阵 row2 与原 matrix_model.row2_from_row1() 推导结果一致。

每套 field_diff.json 列出实际变化字段、字节数和字段哈希，精确偏移仅保存在 local/r2/diffs/。全部成品均从磁盘读回并完成 entry()/seal()/parse() 字节相同的往返及 SHA256SUMS 复核。

使用与 v4 相同的原始 Stage 2j C 源、编译参数和校验 helpers。原完整顺序及 04→02→04、04→06→04、04→08→04 均重跑，并新增独立 04→05→04。10 次编译、160 次驱动运行全部退出 0，其中八套 v4r2 为 80 次，八套匹配 v4 对照为 80 次；普通与 sanitizer 的 80 对完整记录逐字节相同，编译和运行日志均为空，没有 ASan/UBSan 诊断。

下表计数对普通及 ASan/UBSan 均成立。六种 T1 排列的计数相同，各自 payload 分别核对。

| 表集 | 顺序 | V | W | X | U | T 写入次数 |
|---|---|---:|---:|---:|---:|---:|
| tables-v4r2-probe2 | original | 41 | 1072 | 39 | 0 | 2 |
| tables-v4r2-probe2 | 040204 | 10 | 248 | 10 | 0 | 0 |
| tables-v4r2-probe2 | 040504 | 10 | 248 | 10 | 0 | 0 |
| tables-v4r2-probe2 | 040604 | 10 | 248 | 10 | 0 | 0 |
| tables-v4r2-probe2 | 040804 | 15 | 260 | 13 | 0 | 2 |
| tables-v4r2-noprobe | original | 34 | 1004 | 34 | 0 | 0 |
| tables-v4r2-noprobe | 040204 | 10 | 248 | 10 | 0 | 0 |
| tables-v4r2-noprobe | 040504 | 10 | 248 | 10 | 0 | 0 |
| tables-v4r2-noprobe | 040604 | 10 | 248 | 10 | 0 | 0 |
| tables-v4r2-noprobe | 040804 | 8 | 192 | 8 | 0 | 0 |
| 六套 T1 | original | 41 | 1072 | 39 | 0 | 2 |
| 六套 T1 | 040204 | 10 | 248 | 10 | 0 | 0 |
| 六套 T1 | 040504 | 10 | 248 | 10 | 0 | 0 |
| 六套 T1 | 040604 | 17 | 316 | 15 | 0 | 2 |
| 六套 T1 | 040804 | 8 | 192 | 8 | 0 | 0 |

RPC 只有 V/W/X，数量和 T 写入位置与匹配 v4 完全相同。noprobe 零 T 写入；probe2 只在 08、T1 只在 06 进出时写 T。进入先预检，C/D 后置控制 0；退出先恢复控制 2 并读回，再恢复行。无颗粒，七行 RAM、T、邻接和保护字节、设置区及重开菜单均核对。

新增 04→05→04 以及其余独立往返均恢复全部设置到初始 04。原顺序最终 03→04 仍保留S+0x645/0x646 的黑白参数 3/4，与 v4 相同；七行 RAM、T 和保护字节恢复 stock。没有把既有的全设置初始值恢复缺口改判通过。

构建依赖 78 个文件的 SHA-256、大小、mtime 和 mode 起止相同；原 v4 包 57 项文件及目录记录也相同。本报告原 v4 部分逐字节保留，validation.json 保留原记录并新增 v4r2 节。

脚本为 build_v4r2.py；原始记录、命令、日志和起止保护清单位于 local/r2/；临时驱动与二进制位于 /tmp/tv4/r2/。原始数据所在目录已验证 git check-ignore。未操作相机或 SD，未改共享工具或固件，未提交 Git。

```sh
python3 -I -B /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/tables_v4/build_v4r2.py
```


## v4r3：round5 GR 与 T3 测试槽

八套 v4r3 已生成并完成普通与 ASan/UBSan 主机验证。所有既有 v4/v4r2 包和 T3 来源包保持原样。03/05/06/08 与匹配 v4r2 逐字节相同；六套 T1 仍未就绪，相机验收保持 pending。

01/02 分别采用 gr_round5/local/fit_01_r5.json 与 fit_02_r5.json，源 accepted=true、firmware_ready=false。两份输入 SHA-256 符合交接值，曲线节点/输出逐值和合并曲线哈希均与 v4r2 相同；装配保留原曲线字节。两行矩阵 row2 均与原 matrix_model.row2_from_row1() 结果相同，色度系数和偏置保持原样。

probe 的 07 合并 tables-v4r2-probe3/entry07_t3.json，其条目 SHA-256 为 `55f6e41127c4356a089851459de325b1ba65b5fa7153de41142f97443c8c8e1c`。除 stock colour 的 sector11.d 解码减 30、sector17.c 解码加 18 外，其余均为 stock；mask=0、control=2，无 T。07 的原生模式、WB 和参数仍与 04 一致，菜单配方库未改。

T3 源 camera_handoff_ready=false 反映未通过工作者采用的 45°最坏情况模型界限。主代理明确批准它作为仅写 RAM、无 T、离开 07 后恢复的测试槽。该决定已写入 probe manifest；源标记保持 false，没有重算或把原模型门槛改判通过。

以下目录均在 artifacts/stage2j-packages/。每套包含两份完全相同的 3600 B DAT、SHA256SUMS、manifest.json、NOTICE 和 field_diff.json。

| 表集 | DEEPTBL0/1.DAT 共同 SHA-256 |
|---|---|
| tables-v4r3-probe | `c4ba8cdb6564fb9e211428675dabc2f277a1dcc748cd2cecbe14837bacbed6a8` |
| tables-v4r3-noprobe | `88c82f28ce2a3554317325a76bcadaa92c136d797d92e68a4d1ae84d6de93aa0` |
| tables-v4r3-t1/b5R_cG_dB | `bbb184ccfab9071cd62aee9ee6dd24834fe9f009d34684666df349d946a70df3` |
| tables-v4r3-t1/b5R_cB_dG | `5b913dd0abfc5296b1945b299dd56dc7a993b9f26bd854b52e92608c60c1b48c` |
| tables-v4r3-t1/b5G_cR_dB | `f299df3a225bac587179ce3a8a2ea6f40e5a5f24de045a75ab80e3e68bc48fad` |
| tables-v4r3-t1/b5G_cB_dR | `81e4c26a434277537bd12ae29901cdd81f6f1b9a46005a21b285162e4562f3b3` |
| tables-v4r3-t1/b5B_cR_dG | `fcfd1c805d57d28a754f1fdfe39f5d70d0d599141d9e155370e4770ba13940bb` |
| tables-v4r3-t1/b5B_cG_dR | `64fb2e0b3b2f02f9f0283e16ae454ddaddb12466c8c3faf7b648ff22deb0a15d` |

相对匹配 v4r2，仅 entry1、entry2 的扇区、两行矩阵 Y 与对应 CRC，以及文件 CRC 改变；probe 另外替换 entry6 的 T3 colour 和 colour CRC。其它 entry 完全相同。noprobe 的 07/08 仍为 PrbA/PrbB；六套 T1 从新 noprobe 构建，只复制匹配 v4r2 的 06 T1 完整条目。

成品均经磁盘读回、原 entry()/seal()/parse() 字节一致往返和 SHA256SUMS 检查。字段差异见每套 field_diff.json，逐偏移原始差异仅存 local/r3/diffs/。

C 构建参数与前两轮相同，普通版及 ASan/UBSan 各编译六个顺序：原完整顺序、04→01→04、04→02→04、04→07→04、04→08→04、04→07→04→08→04。只改 scratch 驱动副本的 order 声明。12 次编译、192 次驱动运行全部退出 0；其中八套 v4r3 为 96 次，八套匹配 v4r2 对照为 96 次。普通与 sanitizer 的 96 对完整记录逐字节相同，编译及运行日志均为空，无 ASan/UBSan 诊断。

下表计数对两种构建均成立。六种 T1 排列计数相同，每套 payload 分别核对。

| 表集 | 顺序 | V | W | X | U | T 写入次数 |
|---|---|---:|---:|---:|---:|---:|
| tables-v4r3-probe | original | 41 | 1072 | 39 | 0 | 2 |
| tables-v4r3-probe | 040104 | 10 | 248 | 10 | 0 | 0 |
| tables-v4r3-probe | 040204 | 10 | 248 | 10 | 0 | 0 |
| tables-v4r3-probe | 040704 | 8 | 192 | 8 | 0 | 0 |
| tables-v4r3-probe | 040804 | 15 | 260 | 13 | 0 | 2 |
| tables-v4r3-probe | 0407040804 | 21 | 452 | 19 | 0 | 2 |
| tables-v4r3-noprobe | original | 34 | 1004 | 34 | 0 | 0 |
| tables-v4r3-noprobe | 040104 | 10 | 248 | 10 | 0 | 0 |
| tables-v4r3-noprobe | 040204 | 10 | 248 | 10 | 0 | 0 |
| tables-v4r3-noprobe | 040704 | 8 | 192 | 8 | 0 | 0 |
| tables-v4r3-noprobe | 040804 | 8 | 192 | 8 | 0 | 0 |
| tables-v4r3-noprobe | 0407040804 | 14 | 384 | 14 | 0 | 0 |
| 六套 T1 | original | 41 | 1072 | 39 | 0 | 2 |
| 六套 T1 | 040104 | 10 | 248 | 10 | 0 | 0 |
| 六套 T1 | 040204 | 10 | 248 | 10 | 0 | 0 |
| 六套 T1 | 040704 | 8 | 192 | 8 | 0 | 0 |
| 六套 T1 | 040804 | 8 | 192 | 8 | 0 | 0 |
| 六套 T1 | 0407040804 | 14 | 384 | 14 | 0 | 0 |

RPC 仅有 V/W/X，数量和 T 写入位置与匹配 v4r2 完全相同。noprobe 零 T 写入；probe 仅 08、T1 仅 06进出时写 T。进入先预检，C/D 后写控制 0；退出先恢复控制 2 并读回，再恢复各行。T3 的 07 无 T 位，原顺序离开 07 到 08、独立及组合顺序离开 07 到 04，colour RAM 全行均恢复 stock。

无颗粒；七行 RAM、T、邻接和保护字节、设置区与重开菜单均核对。各独立及组合往返在每次 04 都恢复全部设置到初始 04。原完整顺序最终 03→04 仍保留 S+0x645/0x646 黑白参数 3/4，与既有基线相同；七行、T、保护字节均 stock，没有把原全设置初始值恢复缺口改判通过。

构建依赖 137 个文件的内容、大小、mtime 和 mode 起止相同；既有包 122 项文件/目录记录也相同。REPORT 原 v4/v4r2 内容逐字节保留，validation.json 保留旧记录并新增 v4r3 节。

复跑脚本为 build_v4r3.py；原始记录、命令、日志和保护清单位于 local/r3/，临时驱动和二进制位于 /tmp/tv4/r3/。原始数据均在已验证 git check-ignore 的目录。未操作 SD 卡、相机或创建 Git 提交。

```sh
python3 -I -B /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/tables_v4/build_v4r3.py
```
