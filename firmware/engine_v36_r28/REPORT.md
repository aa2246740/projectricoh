# gen 115：28mm 免拍 recipe bank

gen 115 已在主机重链、测试并暂存，可交新的独立 delta 审查。279 次当前 C 主机运行、29 个最终 M32R seed/诊断用例和 14 个最终 DAT envelope 用例全部通过；冻结的 8,118 项输入未变化。所有写入限于本目录，没有访问卡、相机、USB 设备或网络，没有提交 Git。gen 114 首次 50mm 相机结果仍待用户反馈，本报告不把它算作已通过。

交付为 [GXRCE.DAT](local/staged/SD_ROOT/GXRCE.DAT)，generation 115，65,252 B，在 65,536 B 容量内余量 284 B。

```text
SHA256 a9743bb9f0ace0ebba1d807af124210a2a098ad64f31c27083412923c841c4b8
```

[交付清单](SHA256SUMS) 覆盖任务目录；[暂存清单](local/staged/SHA256SUMS) 覆盖 DAT、layout、trust、manifest 和恢复 CTL。SD_ROOT 只有一个 GXRCE.DAT，没有 ilaunch、qlaunch 或 DEEPTBL 文件。

## 相对 gen 114 的改动

先复制 `firmware/engine_v35_publish/`，只调整副本路径，重建 gen 114。结果为 65,088 B，SHA256 精确等于 `132e56389808970b0db8a8c4a359c46f18f0fb2423ecbc11f671d18df19a49a5`，保存在 [reproduced114](local/reproduced114/manifest.json) 和 [重建输出](local/rebuild114.stdout)。原目录未运行构建或改动。

[build115.py](candidate/build115.py) 从实际 gen 114 DAT 解出 map、record64、descriptor、全部十行和 metadata，逐项核对 552 B 展开结果，再让 qlaunch 的七个非 04 owner 复制 50mm 对应 record、完整行引用和微调范围。colour 是整行替换，没有在 stock 上再加差值。qlaunch 的 04、09～16 隐藏 alias、map 和 pin 保持原字节。

| 槽 | 28mm 实际菜单标签 | 内容 |
| --- | --- | --- |
| 01 | `01 Posi` | 50mm GR IV Posi 行。 |
| 02 | `02 Nega` | 50mm GR IV Nega 行。 |
| 03 | `03 HC BW` | 保留既有标签，实际为 Standard mode、全零 colour96。 |
| 04 | `04 Std` | qlaunch 自己的原厂九行和 control=2。 |
| 05 | `05Chrome` | 50mm 05。 |
| 06 | `06ClsNeg` | 50mm 06，含 C/D、control=0。 |
| 07 | `07 Chrome` | 50mm 07。 |
| 08 | `08 Vivid` | 50mm 08。 |

owner 数由 `8/1/8` 变为 `8/8/8`，完整 16 槽访问契约保留。未复制 50mm 的 T block；T 地址和原生门禁沿用当前实现。七个 look 的 A14=A5、B14=B5，04 保留自己的 ISO100 stock 行。

48 槽比较确认，仅上述七个 qlaunch 槽的 entry、record、metadata 和保存绑定变化，其余 41 槽全部一致。qlaunch stock entry552 CRC32 仍为 `1ff40907`。它的 map 在 gen 114 的实际偏移为 `0xDBDC`，gen 115 为 `0xDBF4`，152 B 内容不变。B5 尾 halfword 仍从 map+24 读取，保留 `0x201332B1` 的 live 低字节；B20/B14 保留 `0x2013347E`、`0x201333B8` 的前邻高字节。

运行期 C/H/S 唯一变化是 [blackbox.c](candidate/containers/product/blackbox.c)，见 [精确差分](local/runtime115.patch)。日志原有 2432..2495 保存最新 seed，新增 2496..2559 保存本次启动首次 seed。初始化清零后只复制首次记录，滚动和后续 list_bind 仅更新最新值；两份都受原日志 payload CRC 保护。没有增加 BSS、改变 ABI 或占用事件环 384..2431。

[解码器](decode_blackbox.py) 的 `seed_inputs` 继续表示最新值，`first_seed_inputs` 表示首次值。113/114 日志没有首次记录时返回 null。三单元测试由真实 ADJ writer 起步，滚动 96 次后首次 type=0 保留、最新 type=5；下次启动由真实 exposure writer 写出的首次 type=4 也保留。最终 M32R 指令另验证了精确记录和首次黏性。

## 预算与固定身份

| 项目 | gen 114 | gen 115 | 差值 |
| --- | ---: | ---: | ---: |
| DAT | 65,088 B | 65,252 B | +164 B |
| engine | 55,676 B | 55,700 B | +24 B |
| envelope 与 recipe 数据 | 9,404 B | 9,544 B | +140 B |
| relocation | 8 B | 8 B | 0 B |
| BSS | 11,520 B | 11,520 B | 0 B |
| file+BSS | 76,608 B | 76,772 B | +164 B |
| 65,536 B 内容量余量 | 448 B | 284 B | -164 B |

数据增加恰为七条 20 B descriptor。行池仍为 `[7,20,16,15]` 个 A/B/colour/matrix，raw rows 仍为 3,470 B。余量满足本轮 256 B 门槛，未启用 alias compaction。packer、两块安装缓冲、PS_MAX_ENGINE、storage 和 lease 上限继续为 65,536 B，未扩到 72 KiB。

引擎按最终长度重新链接，BSS 从 65,252 开始；唯一 relocation 为 `(patch=55792,target=32576)`。目录、section 偏移和 CRC 已重算。平移 ELF 的绝对指针归一化后，其余 engine 字节与 packed engine 全等，PIC 通过。两次构建的 DAT、engine.bin、engine.elf、reloc.bin、trust.bin SHA 全等，见 [artifact115.json](local/artifact115.json)。最终 header CRC32=`cd3e3f33`，payload CRC32=`a9c80599`。

```text
已刷 ilaunch3 SHA256 24b1de0e46ea00adeacd224da28770e185b05a08686c40c647032c533c021f72
resident build ID eb96410f5224f76c1cf684a3bd6789eca4c80acf34019120e30dacaeb01da941
ABI b6353e4de1c89bd37c08ba6734efc8e0
pins f09fe7b4 / fb3fbcb2 / 95f3dca9
```

未运行 resident 身份生成器，未重建或改写机身，resident 原有 216 B 余量未使用。DAT header 的 body trust SHA 仍是官方 `da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7`，与 114 相同；它不是已刷映像 SHA。

交叉编译布局得到 main request=84,276 B，安装双缓冲各 65,536 B，loader=608 B、UI snapshot=1,968 B、session work=1,460 B。含 native allocation header 的首次安装申请模型为 216,004 B，已有 snapshot 时为 217,984 B，常驻加可选块为 88,360 B，见 [heap.json](local/evidence-v34c/heap.json)。未测真实堆水位或碎片。

## 已核实的测试

[verification115.json](local/verification115.json) 只统计最终 DAT SHA 和最终 host/history 二进制 SHA，共 279 次唯一 ASan+UBSan 运行。复制来的 114 日志、过期二进制运行和开发错误不计入通过数。子进程合并日志和命令返回码在 `candidate/local/logs/`、`candidate/local/commands.jsonl`；顶层阶段另存 stdout/stderr。

| 范围 | 结果 |
| --- | --- |
| 三单元 gate/expand、entry552/record64/metadata | PASS。48 槽展开，41 槽不变、七槽精确复用 50mm；保留 336 个早期历史槽向量及损坏版本/map/pin/descriptor 拒绝用例。 |
| 113/114 的 28mm 原生列表历史断言 | PASS。修改测试前编译的 114 host 分别加载真实 113、114 DAT，仍断言原生 descriptor count=7、engine 未接管。原断言保存在 [历史源码](local/historical114/host_v34c.c) 和[四次独立历史运行](local/historical114/results.json)；当前 fixture 按实际 owner 数选择八行或原生分支。 |
| 三单元八行及 seed 成功/失败 | PASS。三单元都恰好八个真实行、04 各用本单元 stock。ADJ/exposure/WB/image 原生 writer 重放覆盖 type 0/4/9/5；容量不足、未知 table 的回退也覆盖 qlaunch。 |
| 首帧 cursor、remember-last、live 高亮 | PASS。每单元 9×256 初态遍历；进入、移动、恢复位置没有 RPC、preview 或设置写入，保留 H01/H02/H05 路径检查。 |
| 01/02、03、06 C/D、ISO100、邻字节 | PASS。全部 look 展开、8×8 转换、六种 ISO100 邻值及 256 种邻值矩阵通过；新增同时保留 B5/B20/B14 三处相邻字节，执行 04→06→03→04。 |
| RPC/epoch、T gate、发布失败 | PASS。三单元均执行 52×6 ISO100 调用故障矩阵及 link/unit/boot/S epoch fencing、T X/V 失败、settings/preview 失败；失败后无越权追加 W。 |
| Fn2、OK 保存、MENU 丢弃 | PASS。basic、legacy、store-fault、publish-failure、daily、history 都覆盖 qlaunch。Fn2 打开时应用当前配方，MENU 只丢弃面板草稿。 |
| 114→115 GXTS/GXLS | PASS。三单元 16 槽绑定比较；八个真实配方均测试旧 GXTS 单/双副本和禁止覆盖 rename。七个新 qlaunch owner 拒绝旧绑定，从默认值起步后首次保存成功；41 个不变绑定保留。八个真实配方均检查冷启动保存值和位置，未复现 R4-01。 |
| 精确 114 IROM→115 卡更新 | PASS。保留 114，115 写另一副本，DAT→OK 精确相等；去掉卡产品文件并重启后仍选择 IROM 115。另保留旧 OK 反例，验证改名不确定时 115 可能已持久化。 |
| IROM、掉电、格式化模型、CTL、黑盒 | PASS。21 组继承场景全绿；三单元 history 共 192 个未关闭选择对、24 个 ROM-reset 槽，验证完整 look 或纯 04、光标恢复不应用 look。首次/最新记录及旧日志兼容通过。 |
| envelope/loader、PIC、最终机器码 | PASS。冻结 resident validator 对最终 DAT 和 13 个变体核对 body/build/ABI、长度、CRC、entry、重叠、relocation 拒绝；29 个受限 M32R 用例执行最终 seed/诊断和快照指令，并与 packed engine 对应。 |

accepted-F02 的既有限制仍保留：底层 `open=-1` 若隐藏全部有效 IROM 副本，现有路径无法据此证明它们不存在。该反例保留在测试和日志中。

正常 host 初始化读取官方 state/descriptor，并执行逐字节核对过的 native writer。手工 type5/table 仅保留为明确标注的历史对照，不作为正常初态。RPC、文件系统、allocator、图形和调度边界仍是替身；受限 M32R replay 也有显式输入布置，不是整机模拟。

## 相机尚未证明的部分

本轮没有 28mm 标定拍摄。七个 look 借用 50mm 行，跨镜头视觉匹配、实际颜色和任何“95%”指标均未验证。28mm 04 保持原厂，不等于七个 look 已做过 28mm 校色。

尚未观察实际 LCD、冷启动时序、异步 RPC、UI task/IRQ/快门并发、真实掉电落盘、物理堆余量和格式化后的 IROM 行为。review 114 的 P2-01/02 异常 native table/view 边界未在本轮扩大修复；本轮只落实 P2-03 首次 seed 留存。gen 114 的首次 50mm 现场反馈也仍未知。

## 审查后的卡 B 步骤

以下供独立 delta 审查通过、明确授权写卡后由用户执行，本轮没有执行。预期起点为 v3.4c 机身、gen 114 已装入 IROM、卡 B 根目录仍有 gen 114 `GXRCE.OK`。

1. 关机，先用 50mm，保留已成功的卡 A 原样。备份卡 B 的 `GXRCE.OK` 和 `GXRBX0/1.BIN`。旧 OK 应为 65,088 B、SHA256 `132e56389808970b0db8a8c4a359c46f18f0fb2423ecbc11f671d18df19a49a5`；状态不符时先核对当前包。
2. 从卡 B 根目录移走旧 `GXRCE.OK`、残留 `GXRCE.DAT`、`GXRCE.CTL`。移走 OK 不会删除 IROM 114。旧 OK 必须移走：若 rename 禁止覆盖，它会造成不确定结果，即使 115 已写进另一 IROM 副本。
3. 只复制 `local/staged/SD_ROOT/GXRCE.DAT` 到卡根目录，核对 generation 115、65,252 B、SHA256 `a9743bb9f0ace0ebba1d807af124210a2a098ad64f31c27083412923c841c4b8`。不复制 recovery CTL、机身或 DEEPTBL 文件。
4. 安全推出卡。50mm、M 档、Start Settings Readout=Body，正常开机并打开 Image Settings。loader 先验证卡 DAT，首次 menu 将 115 安装到另一 IROM 副本，保留 114；完整读回比较后 DAT 改名为 OK。先记录八行是否出现，直接 MENU 返回即可触发日志。首次 seed 现在不会被滚动覆盖；Fn2 会应用当前行，不能当成纯取日志动作。
5. 关机取回日志和新 OK/仍在的 DAT。新 OK 必须与本包 DAT 同大小、同 SHA；解码应为 `engine_generation=115`，含 `first_seed_inputs`、`seed_inputs`。OK 是安装收据，LCD 八行仍需观察。若 DAT 还在或失败，先保留现场，不以重复安装判断已回滚。
6. 50mm 检查八行、01/02、03 灰阶、04 恢复、Fn2 的 OK/MENU、重开定位及掉电后的完整配方或纯 04。关机再换 Mount，随后关机换 28mm；三单元均应显示上述八行，28mm 不再预期原生列表。本实现不支持同次启动热换单元，不要求新增 28mm 标定拍摄。
7. 如需验 IROM，先备份卡，把卡上产品文件移到主机，再冷启动打开菜单确认 115。无需为此格式化照片卡；真实格式化持久化另由用户验收。

解码已复制到主机的日志：

```sh
/usr/bin/python3 -I -B firmware/engine_v36_r28/decode_blackbox.py /绝对路径/GXRBX0.BIN
```

## 恢复

先关机、保留日志、移走未处理 DAT。115 若已进入 IROM，移走 DAT、删除 OK 或格式化卡都不会卸载 115，也不会自动恢复 114。

[recovery/GXRCE.CTL](local/staged/recovery/GXRCE.CTL) 为 16 B，`GXRC3401`、OFF=0、CRC 有效，SHA256 `c9780dc432d4d3be6553eee8146668a78ef02a5eeae4853db5d988f149ea08de`。放入卡根目录并冷启动，会在 engine bootstrap 拒绝引擎，早于 install/UI 发布；移走 CTL 再冷启动会重新启用 IROM 115。CTL 是停用，不是降级，也不保证能救回到达 bootstrap 以前的故障。

确需机身恢复时，沿用用户已成功的卡 A、50mm、“+ & playback”Stage2l 流程。本轮没有读取当前卡 A 或复演物理恢复，不应以另一份同名暂存包替换卡 A。Stage2l 绕开当前 loader，不等于删除 IROM 115。

## 复现与封存

所有 Python 使用隔离模式，依赖已有工具链，无下载。不要运行冻结目录的构建入口。复制来的 114 工具和输出只作历史材料；当前入口是 `candidate/build115.py`。顶层阶段输出固定保存在 `local/<阶段>115.stdout/.stderr`，完整命令及结果由 `finalize115.py` 核对。[run115.py](run115.py) 顺序执行两次构建、全部验收、暂存和封存，并保留这些 stdout/stderr；遇到失败会停止。

```sh
/usr/bin/python3 -I -B firmware/engine_v36_r28/run115.py
```

各阶段也可单独执行：

```sh
/usr/bin/python3 -I -B firmware/engine_v36_r28/finalize115.py protected
/usr/bin/python3 -I -B firmware/engine_v36_r28/native_evidence.py
/usr/bin/python3 -I -B firmware/engine_v36_r28/candidate/build115.py
/usr/bin/python3 -I -B firmware/engine_v36_r28/verify115.py compile
/usr/bin/python3 -I -B firmware/engine_v36_r28/candidate/verify_v34c.py vectors
/usr/bin/python3 -I -B firmware/engine_v36_r28/verify_historical115.py
/usr/bin/python3 -I -B firmware/engine_v36_r28/verify115.py seed
/usr/bin/python3 -I -B firmware/engine_v36_r28/verify115.py suites
/usr/bin/python3 -I -B firmware/engine_v36_r28/verify115.py history
/usr/bin/python3 -I -B firmware/engine_v36_r28/verify115.py decode
/usr/bin/python3 -I -B firmware/engine_v36_r28/machine115.py
/usr/bin/python3 -I -B firmware/engine_v36_r28/verify_boundaries115.py
/usr/bin/python3 -I -B firmware/engine_v36_r28/candidate/heap34c.py
/usr/bin/python3 -I -B firmware/engine_v36_r28/finalize115.py stage
/usr/bin/python3 -I -B firmware/engine_v36_r28/finalize115.py seal
/usr/bin/python3 -I -B firmware/engine_v36_r28/finalize115.py verify
```

`decisions.tsv` 未作为输入、冻结或散列对象。未修改其他 worker 的 `lut_p0_timing`、`gr4_lut_ceiling` 或任何冻结目录。测试适配中的启动前读取 session、重启计数未清零问题已修正，失败输出保留在 `candidate/local/failures/`；未放宽产品断言。当前交付只标为主机通过、待独立复审。
