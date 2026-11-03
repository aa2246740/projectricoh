可以上卡

仅批准这份 DAT/ZIP 在仍运行 v3.9、ilaunch3 为 `8233a1c4…` 的机身上做 MOUNT 的 13 张测试。50mm、28mm 只核对兼容性，本轮不增加这两个单元的拍摄。验收层为产物、主机和有明确边界的模拟器。复制上卡前执行下面 P2-01 的目标哈希核对。

P1：没有阻断项。

1. C 逻辑与已审的 a30675fa / G154L 相同。28 个链接输入的当前哈希与 r1 相同，隔离重建的 DAT、engine、reloc、trust 四件都与交付物逐字节相同。代码的 323 个变化字节全是 BSS 地址重定位。全部 774 个 GOTOFF 引用均已核对，含 289 个 HI、289 个 LO BSS 引用；平移链接也一致。BSS 为 9,280 B，所有符号在分配内。

2. 已从旧 DAT 独立构造出完整 83,284 B 新文件，每一字节都吻合。相对旧探针多 160 B，同一文件偏移比较共有 8,135 处不同，分解如下。

| 差异归属 | 不同或新增字节数 | 核对方法 |
| --- | ---: | --- |
| 文件头长度、节位置和 CRC | 14 | 独立重算，剩余头字段沿用旧文件。 |
| BSS 重定位 | 323 | 逐项解码，重新构造代码。 |
| 三单元目录的后移位置 | 5 | 仅调整原有配置区的引用。 |
| 行池长度字段 | 4 | 按新增效果区长度重算。 |
| 效果条目与新增行 | 224 | 从声明的曲线扰动独立编码。 |
| 原配置区整体后移 | 7,565 | 移位后的全部 11,296 B 与旧区相同，末尾新增字节也计入。 |

证据为 [完整字节审计](local/static-audit.json)、[每个差异字节](local/every-byte-diff.csv)、[重建比较](local/rebuild-comparison.json)。映射、记录、重定位表及非 BSS 代码均保留。

3. 每条效果的完整 552 B 均由独立解析器推导，再与生产 C 输出比较，15/15 一致。MOUNT 的 `M26 A` 与旧探针完整相同；P1 三条各只改对应 R/G/B 曲线零基节点 16 的一个载荷字节，减 2；P2 三条各只改对应曲线节点 8、19 的两个载荷字节，各加 2。相关身份和 CRC 单独重算，其余载荷不动，三曲线保持单调。50mm、28mm 各四条旧探针完整保留；三模块原生 01/02/03/04/05/07/08 共 21 份完整配方与 G154L 相同。没有 C120 改动。A 使用独立三曲线，不能当成原生 04 的像素对照。

4. 没有发现新增白名单外写入路径。三单元 GXMP 映射逐字节相同，曲线记录也没有引入新地址。实际 MOUNT/50mm/28mm 序列共检查 7,004 次参数半字写入，均在旧九行白名单对应的半字内；88 次边缘相邻字节检查均保持原值，T 只出现 0/2。没有文件写入或设置块变化。[RPC 核对](local/rpc-whitelist-all.json)。

反例输入也已执行：header、payload、effect CRC 破坏各覆盖三个单元，共 9 次原生拒收，保留原生 7 行且无单元写入；30 次跨单元效果调用均拒绝，输出哨兵、当前引用、设置及写入次数不变。主机还穷举 61,250 个窗口，50 行被拒绝。新增负向值和双节点值未突破行校验。

5. 三模块从 MAIN 第 0 步批量冷启动，无原生 UI、设置或锁字预置。MOUNT 按机主的 13 步，另两单元各按 7 步，逐次完成选择、完整参数回读、OK 关闭和重开，四种 DAT 视图均为 8 行。MOUNT 全序列已在 Python reference 独立重跑，帧、视图、拒收、关闭、诊断和完整原生日志与 C 相同；三个官方单元 packer 每后端各 27 次，C/Python 相同。[独立总收据](local/acceptance-review.json)。

三模块共 15 份实际 post-B 设置只更新原厂校验尾部，4,092 B 载荷不动，再从逻辑持久读取边界重新冷启动。原厂消费的 4,096 B 与给定输入相同，三模块随后均为纯 04、T=2。另以同一 MOUNT post-B 输入换回 G154L，冷启动和完整 552 B 也回到纯 04。恢复源哈希正确，探针和 G154L 都只用于 v3.9。[持久输入](local/restart-source-review.json)、[G154L 恢复](local/native/mount-G154L-open-c/result.json)。卡上备份本身没有被本轮读取。

容量也在限制内：DAT 83,284/98,304 B，代码 64,728/65,536 B，主块实际请求 100,192/107,612 B。换回 G154L 的实际主块为 103,644 B。

本轮关键命令如下，均在项目根执行；原生重跑的 `--name` 要换成未存在的新名称。逐项原始调用保存在 [串行作业收据](local/c-suite-jobs.json)。

```sh
nice -n 15 env GXR_HARNESS_BACKEND=c /usr/bin/python3 -I -B research/review_probe2_r1/local/run_review.py build
nice -n 15 env GXR_HARNESS_BACKEND=c /usr/bin/python3 -I -B research/review_probe2_r1/local/run_review.py host
nice -n 15 env GXR_HARNESS_BACKEND=c /usr/bin/python3 -I -B research/review_probe2_r1/local/static_review.py
nice -n 15 env GXR_HARNESS_BACKEND=c /usr/bin/python3 -I -B research/review_probe2_r1/local/run_review.py native --unit mount --name mount-owner-c-rerun --snapshot research/review_probe2_r1/local/cold/mount-review-cold/standby.snap.z
nice -n 15 env GXR_HARNESS_BACKEND=python /usr/bin/python3 -I -B research/review_probe2_r1/local/run_review.py native --unit mount --name mount-owner-python-rerun --snapshot research/review_probe2_r1/local/cold/mount-review-cold/standby.snap.z
```

P2-01：机主步骤缺少“复制后核对目标文件”的明确动作，本报告补齐。

步骤给出了恢复源哈希和安全推出，但没有要求核对复制后的 `GXRCE.DAT`。反例是电脑备份正确、实际复制了别的同名 DAT，或覆盖没有成功；源文件的哈希不能证明卡根目标正确。

上卡前对卡根的目标 `GXRCE.DAT` 求 SHA-256，探针应为 `102388ab…`；恢复后再次核对同一目标，应为 `5f6191c8…`，完整值见文末。两次都在核对后安全推出。这个补充不要求修改 DAT 或重新制作 ZIP。

下面是交给机主执行的命令，本复审没有访问该卡。把路径占位替换为实际卡根路径。

```sh
shasum -a 256 "/实际卡根路径/GXRCE.DAT"
```

现有拍摄步骤可以照做：固定 MOUNT、35mm f/2 复刻镜头的实际 f/5.6、1/15、ISO 200、日光白平衡、RAW＋JPG；按完整条目名选，不记行号，OK 退出后只按一次快门，等存储灯停。开拍前核对七种 MOUNT 名称完整可读。第 5 张后切 P2，第 6 张仍拍 A；这两张 A 都需要。出现异常即按既有停止及恢复步骤处理。

P3-01：13 张足够执行这两项最小实验，不足以预先宣布全颜色 L1 通过。

入口顺序在 DAT、机主表格和实际 C/Python 序列中一致：

```text
P1：A、R−2、G−2、B−2、A，共 5 张。
P2：A、R+2、G+2、B+2、R+2、G+2、B+2、A，共 8 张。
```

P1 可与今天已有的正向结果按输入位置比较符号、局部线性和量化相位，保留原肤色用于追查 Cb 反号。每通道只有一张新负向照片，不能单独估计负向重复性。P2 每通道两次可查跨亮度段迁移和重复，两个 A 查首尾漂移；没有节点 8、19 的单独对照，不能独立证明两节点可加性或排除相互作用。不要从节点 16 的结果扩大其它亮度段的权限。

页面覆盖已从冻结的逐块 RAW 重新独立计算，未只读取生产脚本的 PASS。四种传递模型各加 0.9/1.0/1.1 输入倍率，共 108 项通道/节点检查，全部左右各至少 2 点且跨过支持区两端。名义 sRGB 的峰值左右点数如下。

| 页 / 节点 | R 左/右 | G 左/右 | B 左/右 |
| --- | --- | --- | --- |
| P1 / 16 | 8/11 | 8/8 | 7/7 |
| P2 / 8 | 4/4 | 4/3 | 3/3 |
| P2 / 19 | 5/5 | 4/4 | 3/4 |

P1 肤色仍为 RGB 190/137/111；蓝块改为 72/119/156，B 的 RAW_WB 预测约 656.5，位于节点 16 的 561–783 代理轴响应带。P2 两段支持区为 90–150 和 900–1152，在局部插值工作模型下分离。1/15、f/5.6 与规划来源的正式组一致，固定一档曝光有依据。

反例是屏幕亮度、预设、机位或光照偏离旧组，使新 A 的实际输入离开这些区间。新页面还没有真机 RAW，108 项只是覆盖预测。拍后必须检查两段首尾 A 的逐块 RAW，并分别分析 Y/Cb/Cr；相机直方图不能替代这一步。原肤色 Cb 反号不能用单一正倍率吸收。[独立覆盖计算](local/page-coverage.json)、[原因与原实验](../probe_pack_r1/FIELD_20261103_RAMP.md)。

固定 Playwright 1.61.1 / Chromium 1228 已独立重渲染两页在三个窗口下的拍摄显示，共 6 例。312 个中央取样区逐像素色值相同，24 次角标解码通过，最小编码距离为 4，标签不压取样区，切页位置相同，离线且零网络请求。浏览器正常退出。这不证明真实屏幕光谱或照片定位、失焦、摩尔纹。[页面收据](local/page/result.json)、[像素检查](local/page-pixels.json)。

P3-02：完整 GPIO→字体/LCD、实体卡、物理保存和真实像素管线仍未验收。

上一轮保存的故障点是 `NAND read exceeds provisional page geometry`。本轮核对该指令属于同一份冻结 v3.9 机身，并分别用 C 和 Python 重放保存的故障状态，结果相同；当时主块尚未分配、DAT 引擎尚未加载。这里只复核故障指令，没有重跑完整 GPIO 路径，也没有把该路径记作 PASS。[C 重放](local/boundary-c.json)、[Python 重放](local/boundary-python.json)。

未运行实体卡/FAT32、相机拍照、物理 NAND 保存、断电时序、完整单元 MCU 启动或像素管线，也未测新页的真实 RAW 覆盖。上卡结论是允许受限设备实验，不是保证相机不会出现菜单或存储异常。已有的七名称检查和异常停止步骤要保留。

本复审只写入 `research/review_probe2_r1/`。计算作业使用 nice 15；页面使用单进程 Chromium，渲染时短暂停下本复审的 Python reference，结束后恢复，未与两项计算同时运行。没有子代理、Git 写操作、卡、相机或网络操作。临时目录已清理，本复审计算进程已结束。13,968 个工程输入的哈希保持不变；额外观察的共享 `decisions.tsv` 在复审期间发生外部更新，本复审未写入，它不参与构建或运行，起止哈希单独保留。其它任务也新增了目录外输出，工作区状态变化另存，不据此改写或接受本轮工程输入。[清理](local/cleanup.json)、[输入稳定性](local/input-stability.json)、[账本变更](local/external-ledger-change.json)、[工作区活动](local/workspace-status.json)、[方法修正记录](local/review-method-notes.json)。

SHA256SUMS

以下为项目根相对路径。完整清单覆盖本复审报告、脚本、证据及关键输入，见 [SHA256SUMS](SHA256SUMS)。

```text
102388ab2651d5cd308de2539f500c2718daedb6dd558a129f17dd41a8f382a9  firmware/package_v39_g154_probe2/local/SD_ROOT/GXRCE.DAT
13d97c5755868e6227b20437d7c0ed432cffb2f68abb225370bd90ee45980ec0  firmware/package_v39_g154_probe2/local/GXR-probe2.zip
a30675fa8450a7dcb258ca494f5f0615d054743b738190b4ef3b6c0a227b6de5  firmware/package_v39_g154_probe/local/SD_ROOT/GXRCE.DAT
5f6191c88e7691472541dce245df67679390aa850ffd110e8f8eb35f4b24c681  firmware/package_v39_g154_looks18_test/local/SD_ROOT/GXRCE.DAT
8233a1c464b29ba88cfdfce1d083b9bf652586edeb216cacf6f16cf36788b25d  firmware/package_v39_g154_looks18_test/local/SD_ROOT/ilaunch3
```

```sh
nice -n 15 shasum -a 256 -c research/review_probe2_r1/SHA256SUMS
```
