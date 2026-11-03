# Stage 2e

包在 `artifacts/stage2e-packages/stage2e/`。没有上机，没有动 SD 卡，没有 git commit。`firmware/stage2d_phase1/` 没有改。源在新目录 `firmware/stage2e/`。

这一版把 GR 正片、负片、高对比黑白、原生 Standard，和富士 Classic Chrome、Classic Neg.，以及两行临时扇区探针，收进同一次 8 行列表。01、02、05、06、07、08 都发布原生 Standard（`S+0x36E = 0x01`），曲线各走各的。色表除了 07、08 的六个扇区，都是 stock row 1。

## 改了什么

配方名在 payload 的 `rfw_defaults`、`DEEPISP0.DAT`、`DEEPISP1.DAT`、`RECIPE20.DAT`、`RECIPE21.DAT` 里是同一套，CRC 按 v2 重算过。四份 DAT 逐字节相同，SHA-256 是 `9b04ab6b5fe30c2a59d2b88c3219ffca6220791e7f4c5ba1bbf11b4c2278cb38`。

| 行 | 名字 | 行为 |
| --- | --- | --- |
| 1 | `01 Posi` | 原生 Standard，13 个 raw 为 0 且不写，WB 0,0。深槽写 Posi 曲线和 stock row 1 |
| 2 | `02 Nega` | 表面与 01 相同。深槽写 Nega 曲线和 stock row 1 |
| 3 | `03 HC BW` | 不变。真黑白 `0x03`，对比度 raw 3、锐度 raw 4。调子仍是原生 row 20，末节点 4095 存成 4094 |
| 4 | `04 Std` | 不变。原生 Standard，计划只有 `S+0x36E = 0x01` 和 WB 9,9。选中时恢复 stock A5/B5/colour |
| 5 | `05Chrome` | 表面与 01 相同。深槽写 Classic Chrome 的 type-26 行和 stock row 1 |
| 6 | `06ClsNeg` | 表面与 01 相同。深槽写 Classic Neg. 的 type-26 行和 stock row 1 |
| 7 | `07 PrbA` | 表面与 01 相同。调子是 stock row 5。色表相对 stock row 1 只改扇区 0,4,8,12,16,20 |
| 8 | `08 PrbB` | 表面与 01 相同。调子是 stock row 5。色表相对 stock row 1 只改扇区 2,6,10,14,18,22 |

`05 Chrome` 和 `06 ClsNeg` 带空格是 9 个字符，超过已经上机验证过的 8 字符名宽，所以写成 `05Chrome`、`06ClsNeg`。07、08 是临时行，试拍后的下一版删掉。

槽 9..16 是空的。深槽是 `rfw_deep_slots = {1,2,3,5,6,7,8}`。写入目标没变：A5 `0x2012F504`、B5 `0x2012FFFC`、colour row 1 `0x2012C5D4`。选 04 时 deep id 是 0，走原来的非深槽恢复。

05、06 的 31 个输入和 33 个输出来自 `research/fuji_phase2/local/fit.json` 现在的 `fits.classic_chrome.chosen` 和 `fits.classic_neg.chosen`。这次用的曲线字节 SHA-256（31 个 u16 大端接 33 个 u8）是：

- Classic Chrome `dc2b2b9879e24d9d9ae81320796c2743da35b743047e7dbbe8937845a1c99a4c`
- Classic Neg. `59786a11d0a58092268559144882ca18ab8c00bd009cd23949d9d4b24038df88`

`fit.json` 本身是 `5b2400a01ace34e419e0beb9a3863dfa9491c8e1f6d1c6030cd9896df3c6396d`。Classic Neg. 和 GR 负片的 31 个输入都与 stock row 5 的输入逐字节相同，生成器把这张输入表复用了。Chrome 用自己的输入节点。

07、08 的色字来自 `research/stage2d_verification/measurements.json` 的 `probes`。已核对：不在名单里的扇区与 stock row 1 逐字节相同，名单里的六个扇区都变了。这一版把完整的 96 字节色表放进 rodata，没有走运行时合成。

没改的行为：类别门仍是 {0, 4}；`rfw_cursor_commit` 在 `rfw_is_active()` 时仍返回 1；W 之前的深槽失败仍发布 S，W 已经开始之后仍粘住并失败关闭；RPC-8 仍只接受 V/W/X，U 拒绝。分派器文件 `0x26F8FC` 仍是 `d2 c0 20 5e`。跳表 `0x20377434` 仍是原厂。`jlaunch3` 与官方逐字节相同。其余 28 个组件和恢复树 29 个文件等于官方。

## count = 8 为什么站得住

`adj_count_16` 仍打在 VMA `0x2022F5AC`（文件 `0x1E47AC`）。原厂是 `0x07`，stage2c 是 `0x10`，stage2d 是 `0x04`，这一版是 `0x08`。相对已经上机的 stage2d，payload 以外只有校验和的低 3 字节，以及这个 count 字节。另外七个 hook 与 stage2d 逐字节相同。

绘制窗口。已对官方 `ilaunch3` 复核 `0x201FDD4C` 起的字节：`ldub r0,@(4,r7)` 读 count，`cmpui r0,#10`，`bc`。GNU `m32r.cpu` 里 `cmpui` 在源寄存器小于立即数时置条件位，`bc` 在条件位为真时跳。count 为 8 时 8 < 10，可见行数就是 8，不是被收成 9。8 行都在一屏里。

滚动。`0x201FDD38` 先把窗口起点写成 0。`0x201FE3A4` 是 `cmpu r9,r3 -> bnc 0x201FE584`，r9 是前面存进栈的 9，r3 是 count。count ≤ 9 时条件 9 < count 为假，`bnc` 跳到 `0x201FE584`。这段后续没有再写栈上的窗口起点。所以 count 为 8 时根本走不到 `0x201FE3B4`。

`0x201FE3B4` 本身也只在光标大于 8 时进公式。控制块 `+10` 是当前选择（`research/stage1_ui/lever-FINDINGS.md`）。这里 `addi r9,#-1` 把 9 收成 8，再 `cmpu` 8 和光标。光标大于 8 才 `bc` 到 `0x201FE45C`，那里在末项写 `cursor-9`，否则写 `cursor-8`。光标 1..8 不进。count 为 8 时这条路双保险：外层已经跳过，内层条件也不会真。

附加表。type 5 仍改指向 `rfw_no_details`，16×12 个零。光标 8 用的是下标 7，落在这张表里。这个 hook 与 stage2d 逐字节相同。

1..7 钳位。原厂 `0x2028725C` 起：`cmpui r0,#1` 后 `bc` 到改写，`0x20287264` 的 `cmpui r0,#8` 在光标小于 8 时跳过改写。光标 ≥ 8 会落到 `0x2028726C`，把 `0x2022F726` 写成 1。这段只在函数 `0x202871D8` 里面。官方镜像里构出 `0x202871D8` 再 `jl` 的调用点有 5 处，和 stage2d 的 `build.py` 核对的是同一组：`0x202B8D98`、`0x202BD88C`、`0x202BEA50`、`0x202C2D70`、`0x202C2D80`。对全部 16 段做了 8 位、16 位和 24 位 PC 相对分支扫描，没有一条从函数外面落到 `0x20287250..0x20287278`。

入口仍被 `adj_confirm_close` 换成 `bra ricoh_recipe_action`。`abi.S` 里 `rfw_is_active()` 为真就去 `ricoh_recipe_apply`，用调用者原来的 lr 返回，不会 `bra native_action_resume`（`0x202871DC`）。活动时这条函数体，包括 `0x20287264`，不会执行。光标是 8 还是 1 都不参与这个分支。`rfw_is_active()` 只看页面是不是配方页，不看光标。stage2c 的门在真机上是开的（R3 读数 `T=05`、`A=08`、`V=01`），stage2d 没改这个谓词。

拨盘那条是另一个 hook。`recipe_live_commit` 在 `rfw_cursor_commit()` 返回非 0 时跳到 `0x202BCF58`，不回到七模式 setter。活动时 `rfw_cursor_commit` 先 `rfw_select` 再返回 1，光标 8 也一样。

stage2c 的 count 是 16，真机记录是「M 档配方都能选」（`decisions.tsv` 的 `stage2c_first_run_success`）。那份银行 16 槽都有配方，所以这句话盖住了光标 8、12、16；照片没有按这三个光标分开归档。宿主测试从 stage2b 起就点名这三行：关闭、busy、`load_status==EMPTY` 时 `commit()` 为 1，S 不动。stage2c 报告写明这几条没改，stage2d 留着，这一版也留着，并且另外测了装好的银行在光标 1..8 上真的套用。

`matching_slot` 仍扫 16 槽。01、02、05..08 的表面计划都是选择器 `0x01` 加 WB 9,9，靠整份配方算出来的 deep id 分开。重开时高亮比的是计划字节和 `deep.active`。测过关掉再打开，高亮回到刚才那一行，包括 04。没有匹配时 `rfw_open` 仍收成 1。

因此 count 用 8。没有退回 4，也没有回到 16。

## 空间

上限仍是探针保留区。payload 从 `0x2005276C` 起，探针尾从 `0x20054700` 起，中间最多 8084 字节。stage2d 用了 7680 字节，停在 `0x2005456C`，余 404 字节。

这一版 payload 8060 字节，停在 `0x200546E8`，SHA-256 `3d9297340582a355a9dc4106164ef1824992ba4c3e365788949ac53a99e52673`。探针尾前面还空 24 字节，尾本身仍是 `0xFF`。没有扩大区域。

放得下，靠的是去重，不是删行：

- 01、02、03、05、06 的色表共用 stock row 1。
- 07、08 的调子共用 stock row 5。
- GR 负片和 Classic Neg. 的输入节点共用 stock row 5 那张输入表。Chrome 的输入和输出、Classic Neg. 的输出、两份探针色表是新的。

完整的两份 96 字节探针色表就在镜像里。另编过一版运行时合成：色表只留 6 个扇区的替换字，写入时按扇区盖上去。宿主 86 项能过，色差仍只在那六个扇区。同一套编译器链出来的镜像却比完整色表更大，停在探针保留区里面约 68 字节。合成函数和调用点比省下的 192 字节色表更贵，所以这一版不用它。

若下次重拟合让 Classic Neg. 的 31 个输入不再等于 stock row 5，会多一张 62 字节的表。现在只剩 24 字节，那次链接会失败。稀疏那条路也塞不进去。到那时要先裁代码或证明另一块空闲区，不能靠这次的生成器自动变出来。

## 中性块预测

曝光沿用 stage 2d 那批：1/80、f/2.5、ISO 500。传感器码取自 `04 Std` 那张六个中性块的 `u×4095`，八行用同一组码。预测是曲线在该码上的分段线性值，四舍五入到整数。07、08 的调子就是 stock row 5，所以和 04 相同。色表不进这条亮度模型。

| 块 | 01 Posi | 02 Nega | 03 HC BW | 04 Std | 05Chrome | 06ClsNeg | 07 PrbA | 08 PrbB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| D6 | 16 | 30 | 8 | 29 | 20 | 26 | 29 | 29 |
| D5 | 41 | 65 | 12 | 59 | 49 | 49 | 59 | 59 |
| D4 | 91 | 119 | 29 | 107 | 104 | 101 | 107 | 107 |
| D3 | 148 | 170 | 93 | 155 | 156 | 166 | 155 | 155 |
| D2 | 189 | 205 | 180 | 191 | 184 | 199 | 191 | 191 |
| D1 | 214 | 226 | 219 | 214 | 204 | 218 | 214 | 214 |

stage 2d 报告里 stock row 5 的 D1 写成 215、row 20 的 D1 写成 220。那组用的是 HC 那张自己的 `u`。这里八行共用 04 的 `u`，D1 因此是 214 和 219。

## 测试

宿主和 ASan/UBSan 都是 86 项。stage2d 是 84 项。多出来的是：

- 顺序 `04 → 01 → 02 → 05 → 06 → 07 → 08 → 04 → 03 → 04` 每次切换后 A5/B5/colour 与该 profile 一致，关掉再打开高亮回到该行。04 恢复 stock。
- 01、02、05、06、07、08 的计划只有 WB 两轴和 `S+0x36E = 0x01`，13 个色彩字段和黑白字段都不写。

同一轮还检查了：07、08 相对 stock 色表恰好差那 6 个扇区；stock、Posi、Nega、HC、Chrome、ClsNeg 和两份探针调子单调且在范围内。探针调子就是 stock row 5。

既有的七模式守卫没有改。关闭、busy、EMPTY 时 8、12、16 的 `commit()` 仍为 1。类别门仍是 K=0 和 K=4 套用，K=1、2、3、7、255 冲突且 S 不动。K=4 下槽 1..8 都套用，9..16 为 `EMPTY`。

分派器 25/25。ABI 模型 36。工具测试 17。镜像审计 7。保护窗口 30 个与原厂相同。

稀疏色表那条只跑了宿主 86 项，没有进这个包。

## 哈希

新 `ilaunch3` 是 `a3e699601cd50e5a97706081962c2956ecac5f060396ed3554bd34fe1c50bb45`。校验和 phase 0 是 `0x6A73BA8B`。高字节仍是 `0x6A`，低 3 字节在文件 `0x16D..0x170`。审计脚本按 `sum(body[i] * ((i-0x200)%6+2))` 重算过。

相对 stage2d 的 `99373f42…`，payload 以外只有两处：上面的 3 字节校验和，以及文件 `0x1E47AC` 的 count，`0x04` 变成 `0x08`。payload 里有 110 段、1436 字节不同。`shasum -a 256 -c SHA256SUMS` 在包目录里通过。

相对官方，29 个组件里只有 `ilaunch3` 不同。恢复树 29 个文件等于官方。四份 DAT 是新增文件，彼此相同。

写报告前后用来对照的官方哈希没有变：

- 官方 `ilaunch3` `da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7`
- 官方 `jlaunch3` `951be1c659c85af58ae3e4ce98707c52f0b4514fc2075256854d59f822671673`

## 重跑

拟合更新 `fit.json` 之后，键名不变的话一条命令即可。它会打印实际链进去的曲线 SHA-256。

```bash
python3 -I firmware/stage2e/tools/regen.py \
  --fit research/fuji_phase2/local/fit.json
```

中性块预测：

```bash
python3 -I research/stage2e/predict_neutrals.py
```

## 已验证、推断、未知

已验证：count 字节、绘制窗口、滚动入口、附加表下标、钳位函数的唯一入口和活动时不落入原函数，都对照了官方字节或这一版的链接结果。宿主和 ASan 的 86 项、审计、分派器和包内 `shasum` 都跑过。探针色表相对 stock 只差指定的六个扇区。四份 DAT 相同。`jlaunch3` 和另外 28 个组件等于官方。

推断：stage2c「都能选」盖住了 16 行里的光标 8、12、16，但没有这三行各自的照片。静态路径已经说明活动时光标 8 进不了钳位函数。这不是新的真机记录。

未知：这一版没有上机。系数角和 JPEG 色相的比例仍未知，所以 07、08 只是探针。Classic Neg. 的输入若在重拟合后离开 stock row 5，现有 24 字节余量不够，稀疏编码也更大，链接会失败。
