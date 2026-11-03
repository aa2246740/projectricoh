可以上卡

仅批准这份 probe3 DAT/ZIP 在仍运行 v3.9、ilaunch3 为 `8233a1c4…` 的机身上做 MOUNT 的 8 张试拍。50mm、28mm 只核对兼容性，不增加拍摄。结论覆盖交付字节、主机和声明过模型边界的原生执行；上卡及恢复时，协助者须按下面 P2-01 核对复制后的目标文件。

P1：没有阻断项。你的快速核对全部成立。

1. C 逻辑没有变化，289 个引擎变化字全部是已证明的 BSS 重定位。

build 仍为 154，body/resident/ABI ID、入口及 BSS 大小均与 probe2 相同。89 个引擎 C/H/S/链接脚本的当前哈希与 probe2 冻结值一致，28 个链接输入也一致。独立隔离重建的 DAT、engine、reloc、trust 四件均与交付物逐字节相同。

| 相对 probe2 的区域 | 独立核对结果 |
| --- | --- |
| 引擎 | 64,728 B 不变；恰好 289 个 32 位字不同，每个字高 16 位不变、低 16 位减 32。实际不同字节共 289 B。 |
| part 2/4/5/7 | 每个分段逐字节相同。 |
| part 3 | 仅三个单元目录中的配置区指针各减 32。 |
| part 6 | 3,180 B 变为 3,148 B；旧前 12 个效果描述符相同，最后三条换为节点 16 的正向条目。 |
| 头部及池元数据 | 仅长度、配置区位置、效果区长度及相应 CRC 改变。 |

774 项 GOTOFF 全查通过，含各 289 项 HI/LO BSS 引用。新 BSS 起点随文件缩短 32 B，9,280 B 的 BSS 大小不变，符号均在分配内。按这些改动从 probe2 独立构造出的整个 83,252 B 文件与 probe3 完全相同，没有剩余未解释字节。[完整字节审计](local/static-audit.json)、[289 个变化字](local/changed-engine-words.json)、[隔离重建](local/rebuild-comparison.json)。

容量在限制内：DAT 为 83,252/98,304 B，代码为 64,728/65,536 B，实际主块请求为 100,160/107,612 B。

2. 七种 MOUNT 配方正确，其它要求保留的配方也都保留。

从 G154L 独立推导完整 552 B 配方，单独重算身份和各块 CRC，再与 DAT 解析结果及生产 C 展开比较，15/15 相同。下表偏移为完整 552 B 配方中的零基载荷偏移，不含须随载荷变化的身份和 CRC 字段。

| MOUNT 条目 | 相对 M26 A 的载荷变化 | 旧产物对照 |
| --- | --- | --- |
| `M26 A` | 无。 | 完整 552 B 与 probe2、原 a30675fa 的 A 相同。 |
| `P1 R+2` | 仅 R 节点 16，偏移 395，加 2。 | 与原 a30675fa 正向 R 相同。 |
| `P1 R-2` | 仅 R 节点 16，偏移 395，减 2。 | 与 probe2 负向 R 相同。 |
| `P1 G+2` | 仅 G 节点 16，偏移 98，加 2。 | 与原 a30675fa 正向 G 相同。 |
| `P1 G-2` | 仅 G 节点 16，偏移 98，减 2。 | 与 probe2 负向 G 相同。 |
| `P1 B+2` | 仅 B 节点 16，偏移 428，加 2。 | 与原 a30675fa 正向 B 相同。 |
| `P1 B-2` | 仅 B 节点 16，偏移 428，减 2。 | 与 probe2 负向 B 相同。 |

其它两条曲线、C100 和控制字节不动，三曲线仍单调，没有 C120 改动。50mm、28mm 的八条完整旧探针与 probe2 相同；三单元原生 01/02/03/04/05/07/08 共 21 份完整配方与 G154L、probe2 相同。三份 GXMP 映射及 48 份原生记录也都与 probe2 相同。06 仍为原来的测试基底。A 使用独立三曲线、T=0，不能把 A 当作原生 `04 Std` 的像素对照。[独立配方](local/independent/)、[生产 C 展开](evidence/host.json)。

ZIP 的五个成员、内层四文件哈希、DAT、页面及机主步骤的精确副本均通过核对，没有机身、resident 或单元固件。48 份记录 CRC 及 Studio codec 的逐字节往返也通过。[codec](evidence/python.json)。

3. 本次序列没有发现白名单外写入或三单元兼容性问题。

MOUNT 按 A、R+2、R-2、G+2、G-2、B+2、B-2、A 实跑 8 步，50mm、28mm 各实跑 7 步。每步核对完整 552 B、参数回读、OK 关闭和重开，最后回原生 04/T=2。三单元四种 DAT 视图均为固定 8 行。MOUNT 全序列在 Python reference 独立重跑，frames、views、跨单元拒收、关闭、诊断、完整原生日志、calls、watch 和状态迁移都与 C 相同。三个官方单元 packer 每后端各 27 次，也逐项相同。[总收据](local/acceptance-review.json)、[MOUNT C](local/native/mount-owner-c/result.json)、[MOUNT Python](local/native/mount-owner-python/result.json)。

逐条重建 7,070 次参数半字写入，均落在旧九行白名单覆盖的半字内；涉及的 88 次白名单边缘相邻字节检查保持原值。T 的页和选择地址正确，高字节保留，低字节只出现 0/2。本次序列没有文件写入，22 次 OK 关闭后的 4,096 B 设置均与 MAIN 初始设置相同。[RPC 白名单核对](local/rpc-whitelist.json)。

header/payload/effect CRC 破坏各覆盖三个单元，共 9 次原生拒收，保留原生 7 行且无单元写入。30 次跨单元效果调用均拒绝，输出哨兵、设置、当前引用和写入次数不变。生产 C 的 61,250 个虚拟窗口检查通过，50 行被拒绝。

本轮原生执行从已冻结、已核对哈希的 MAIN 冷启动 RAM 快照进入父菜单及构造器，没有重跑 MAIN 第 0 步。独立实跑所得 12 份 post-B 设置序列化后，与既有 MAIN 重启所消费的输入完全相同；仅重算原厂校验尾部，4,092 B 载荷不动。复跑三个快照的原生 DAT 消费路径，均回到完整纯 04/T=2。用同一 MOUNT 重启输入换回 G154L 也回到完整纯 04，主块请求为 103,644 B。[重启输入](local/restart-source-review.json)、[G154L 恢复](local/native/mount-G154L-open-c/result.json)。这项证据止于逻辑持久读取边界及其后续原生执行。

4. 标签在测量区外，按键与不按键两种分析方案都能执行。

独立重渲染固定 Playwright 1.61.1 / Chromium 1228 的 10 个窗口、显示模式和 DPR 组合，每组合走完 8 步，共 80 张截图。4,160 个中央取样区逐像素符合指定 RGB，320 次四角解码通过；完整外框和底部三色块可见。标签不压任何灰块、彩块或角标；同一窗口下，固定标签区以外的框内像素在 8 步间完全相同。49 个灰码、三个彩块及内板几何与旧 P1 相同。前进、返回、首尾边界、防长按连跳和 Esc 检查均通过，零网络请求，浏览器已退出。[页面检查](local/page/check.json)、[独立像素核对](local/pixels.json)。

标签自身的字形会变化。两半反相像素配对使对应 RGB 之和恒为 240，标签区均值恒为 RGB120，截图中框内 RGB 总量也恒定。这证明数字像素恒定的范围，不证明真实屏幕的局部调光、杂光或照片像素恒定。

响应识别只接收 RAW 漂移校正后的差分、输入和六个有符号模板，不接收页码、照片顺序或标签。独立复跑旧真实测量 10 帧，覆盖全部七类；标签缺失、全部停在 `1/A`、故意给错标签时，身份和分数都不变，冲突单独保留。因此机主可按键，也可完全不按键。A 兼容判定不能证明 DAT 身份，也不能区分首尾两个 A；首尾仍按原件顺序确定，响应不清时保留 unknown。[响应回执](evidence/response.json)、[逐帧结果](local/response-checks-detail.json)。

这 8 张满足 FIELD_PROBE2 所要求的同场节点 16 正负配对。新照片仍须用首尾 A 的 RAW 核对三通道覆盖和漂移；去掉第二相位后，不能据此判定输入量化相位或 floor/round。

5. 机主步骤可以照做，恢复方向正确。

步骤明确固定 MOUNT、35mm 复刻镜头的 f/5.6、M 档、1/15、ISO 200、日光白平衡、单张 RAW＋JPG；每张按完整条目名选择、OK 后拍一张、等存储灯灭。菜单负向排在正向前，但表格按名字回选，实际 8 步已通过。允许不翻页，异常即停、保留全部照片、不补中间一张，交接也明确。

P2-01：协助者须核对复制后的卡根目标，并在恢复后冷启动。

说明给出了正确源哈希并将文件操作交给协助者，但没有明确写“对复制后的目标求哈希”。沿用 probe2 复审的补充：复制探针后核对卡根 `GXRCE.DAT` 为 `a3f831f9…`；拍完选 `04 Std`、OK、关机，将正确的 `G154L.DAT` 复制为卡根 `GXRCE.DAT`，再核对目标为 `5f6191c8…`。每次核对后安全推出，恢复后冷启动。备份源本身正确不能证明覆盖成功。卡上的备份及目标文件本轮均未读取。

协助者在实际卡上执行以下命令，完整期望值见文末。机主不用复制或校验文件。本报告的补充不要求修改 DAT 或重打 ZIP。探针及这份 G154L 只用于 v3.9。

```sh
shasum -a 256 "/实际卡根路径/GXRCE.DAT"
```

未验收的边界仍须保留。

完整 GPIO→字体/LCD 路径继承 `NAND read exceeds provisional page geometry`。本轮用 C 和 Python 各重放一次保存的故障状态，均在同一条原厂指令报同一错误；当时主块未分配、DAT 引擎未加载。这里只复核保存状态中的单条故障指令，没有将完整 GPIO 路径记为通过。[C 重放](local/boundary-c.json)、[Python 重放](local/boundary-python.json)。

未运行实体卡/FAT32、物理 LCD、相机拍照、新页真实 RAW 覆盖、物理 NAND 保存、断电时序或完整单元 MCU/真实像素管线。开拍前仍须在真机核对七种名称完整可读、菜单可正常关闭重开。上卡结论允许本次受限设备实验。

本复审只写入 `research/review_probe3_r1/`，系统围栏拒绝目录外写入和网络访问；所有计算作业 nice 15，最多两个，浏览器使用单进程模式。首次页面 runner 在切换 DPR 的第二个 browser context 时退出，改为每个 DPR 单独启动固定浏览器后全套通过，原始方法错误单独保留，不算 DAT 失败。[方法记录](local/review-method-notes.json)。没有卡、相机、网络或 Git 写操作。15,666 个冻结输入哈希均未变，临时目录已清理，无本复审计算进程残留。[输入稳定性](local/input-stability.json)、[清理](local/cleanup.json)。

关键复查命令如下，在项目根执行。原生重跑的 `--name` 须使用新名称。

```sh
nice -n 15 /usr/bin/sandbox-exec -f research/review_probe3_r1/offline.sb /usr/bin/python3 -I -B research/review_probe3_r1/static_review.py
nice -n 15 /usr/bin/sandbox-exec -f research/review_probe3_r1/offline.sb env GXR_HARNESS_BACKEND=c /usr/bin/python3 -I -B research/review_probe3_r1/run_review.py native --unit mount --name mount-new-c --snapshot research/probe_pack_r3/local/cold/m-final-cold/standby.snap.z
nice -n 15 /usr/bin/sandbox-exec -f research/review_probe3_r1/offline.sb env GXR_HARNESS_BACKEND=python /usr/bin/python3 -I -B research/review_probe3_r1/run_review.py native --unit mount --name mount-new-python --snapshot research/probe_pack_r3/local/cold/m-final-cold/standby.snap.z
```

SHA256SUMS

以下为项目根相对路径。完整 [SHA256SUMS](SHA256SUMS) 覆盖本报告、复核脚本、证据及冻结输入。

```text
a3f831f956f352e8c6f428e35a832006bdd33e1a8ace0c8f26ad2743dbe41dcb  firmware/package_v39_g154_probe3/local/SD_ROOT/GXRCE.DAT
3d924a3fa17b1974e09d317562c2c0ed107b6a239e19236ab451bffb0804df80  firmware/package_v39_g154_probe3/local/GXR-probe3.zip
5ae74766ba3c64d62bc4ac694fa947c8f56e6b1e6f3d43b7362a71c70654fff9  research/probe_pack_r3/ramp3.html
102388ab2651d5cd308de2539f500c2718daedb6dd558a129f17dd41a8f382a9  firmware/package_v39_g154_probe2/local/SD_ROOT/GXRCE.DAT
a30675fa8450a7dcb258ca494f5f0615d054743b738190b4ef3b6c0a227b6de5  firmware/package_v39_g154_probe/local/SD_ROOT/GXRCE.DAT
5f6191c88e7691472541dce245df67679390aa850ffd110e8f8eb35f4b24c681  firmware/package_v39_g154_looks18_test/local/SD_ROOT/GXRCE.DAT
8233a1c464b29ba88cfdfce1d083b9bf652586edeb216cacf6f16cf36788b25d  firmware/package_v39_g154_looks18_test/local/SD_ROOT/ilaunch3
```

```sh
nice -n 15 shasum -a 256 -c research/review_probe3_r1/SHA256SUMS
```
