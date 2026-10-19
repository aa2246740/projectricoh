# Stage 2d phase 1

包在 `artifacts/stage2d-packages/stage2d-phase1/`。没有上机，没有动 SD 卡。`firmware/stage2c_category_gate/` 没有改。源在新目录 `firmware/stage2d_phase1/`。

这一版把机上已经验证过的 16 行列表收成 4 行。`04 Std` 是相机自己的 Standard，其余三行用我们的曲线。Posi 和 Nega 这一轮故意继续用 stock colour row 1，曲线和色彩表分开测。

## 改了什么

配方名在 payload 的 `rfw_defaults`、`DEEPISP0.DAT`、`DEEPISP1.DAT`、`RECIPE20.DAT`、`RECIPE21.DAT` 里是同一套，CRC 按 v2 重算过。四份 DAT 逐字节相同，SHA-256 是 `194e74b94fb081893e442484bf1532cf8daae31434fafb36d7d9d04645c8528d`。

| 行 | 名字 | 行为 |
| --- | --- | --- |
| 1 | `01 Posi` | deep，base mode `0x04`，对比度、锐度、鲜艳度和全部色彩字段都是 display 5（raw 3），WB 0,0 |
| 2 | `02 Nega` | 表面设置与 01 相同，曲线不同 |
| 3 | `03 HC BW` | deep，真黑白 base mode `0x03`，对比度 display 5（raw 3，选第 5 行），锐度 display 6（raw 4，与 stage2c 槽 3 相同） |
| 4 | `04 Std` | 原生 Standard，发布 `S+0x36E = 0x01`，13 个 raw 字段为 0 且不写，WB 0,0 |

槽 5..16 在文件里是空的。无卡或两路 IO 都失败时，回退只发布能通过校验的默认配方，空槽不再被标成 occupied。

深槽是 `rfw_deep_slots = {1,2,3}`：stock 恢复、Posi、Nega、HC。Bleach 去掉了。写入目标没变：A5 `0x2012F504`、B5 `0x2012FFFC`（B6 邻居仍在 `0x2013001C/1D`）、colour row 1 `0x2012C5D4`。三个深槽的色彩行都写 stock row 1。HC 的色度不会被黑白路径使用，写回 stock 即可。

Posi / Nega 的 31 个输入和 33 个输出取自 `research/phase1_curves/curves.json`。HC 的调子从官方 `jlaunch3` 的原生第 20 行读出（A 在 VMA `0x2012F8A6`，B 在 `0x201301EB`；section-3 文件偏移 `VMA - 0x200F2000 + 0xA7200`，与分段表一致），并与 `firmware_and_fit.json` 的 `gxr_native_row20` 对过。原生最后一个输入节点是满幅哨兵 4095，不在 1..4094 里；前一个节点小于 4094，所以这一处存成 4094，其余输入和全部输出保持原生。0 和 4095 仍是曲线两端的隐含端点。四条调子（stock、Posi、Nega、HC）都已检查：输入严格递增且在 1..4094，输出非递减且在 0..255。

`deep_tables.c` 由 `tools/generate_deep_tables.py` 生成，仍被 `/firmware/**/deep_tables.c` 忽略。行 20 和 stock 的字节没有写进报告或其它跟踪文本，只留了 SHA-256，在 `tables_manifest.json`。

没改的行为：类别门仍是 {0, 4}；`rfw_cursor_commit` 在 `rfw_is_active()` 时仍返回 1；W 之前的深槽失败仍发布 S，W 已经开始之后仍粘住并失败关闭；RPC-8 仍只接受 V/W/X，U 拒绝。分派器文件 `0x26F8FC` 仍是 `d2 c0 20 5e`。跳表 `0x20377434` 仍是原厂。`jlaunch3` 与官方逐字节相同。其余 28 个组件和恢复树 29 个文件等于官方。

## count = 4 为什么站得住

`adj_count_16` 仍打在 VMA `0x2022F5AC`（文件 `0x1E47AC`）。原厂字节是 `0x07`，stage2c 是 `0x10`，这一版是 `0x04`。4 小于原厂的 7，消费者按描述符里的 count 取项时，下标停在原厂 7 项表的前 4 项里。

光标初始化：`0x202870A8` 仍是 `mv r8, r0` 然后跳到 `0x20287118`，跳过七模式 switch。`rfw_open` 的返回值直接写进 `0x2022F725` 和 `0x2022F726`。对本银行，匹配结果是 1..4，没有匹配时打开函数把它收成 1。

绘制窗口：`0x201FDD4C` 从描述符 `+4` 读 count，和 10 比。count 为 4 时可见行数就是 4。滚动入口在 `0x201FE3B4`，只有光标大于 8 才走进 `cursor-8` / 末项 `cursor-9` 那条公式。光标 1..4 走不进那条路，窗口起点是 0，四行都在屏上。末项公式在 count 为 4 时不会被用到。

附加表：type 5 仍改指向 `rfw_no_details` 的 16×12 个零。光标 4 用的是下标 3，原厂 7 项表和这张零表都盖得住。

`matching_slot` 仍扫 16 个槽，空槽跳过，所以对本银行它只会返回 1..4，或者 0。0 表示没有一行对上，`rfw_open` 照旧把高亮收成第 1 行。重开时高亮比的是整份写入计划，再加当前 deep profile。Posi 和 Nega 的表面字节相同，靠名字在内的整份配方和 `deep.active` 分开。`04` 的计划只有 `S+0x36E = 0x01` 和两轴 WB（编码 9，也就是补偿 0）。色彩字段不参与比较，所以它们是什么都不影响 04 的高亮。WB 不是 0 时，选择器虽然是 `01`，也不会高亮 04。

`rfw_cursor_commit` 在光标为 4 时调用 `rfw_select(4)`。槽 4 有配方。活动时返回值仍是 1。光标 8、12、16 在关闭、busy、EMPTY 这三条安全测试里的行为没有改：commit 仍返回 1，S 不动，也不会进七模式 setter。

原厂 `0x20287264` 的 1..7 钳位在 `0x202871D8` 里面。配方 UI 活动时这个入口仍被 hook 走掉。就算落到原函数，光标 4 也在 1..7 里，不会被改回 1。会出问题的是大于 7 的光标，不是 4。

因此 count 用 4，没有退回 16。

## 原生 Standard 写什么

`0x20268768` 从 `*(u32*)0x200C0DAC` 取出 S，在 `0x20268774` 执行 `stb r4, @(878, r1)`，也就是只写 `S+0x36E`，然后 `jmp lr`。Image Settings 里 Standard 的提交在 `0x202BB9D8`：`ldi r4, #1`，再调用这个 setter。这条路径没有色彩字段写入，Standard 也没有编辑子页（子页只接 `04/05/03/06`）。

`04 Std` 写的就是这一字节，再加上和其它槽一样的 WB 两轴 0,0（S 里存 9,9）。13 个 raw 字段必须是 0，计划里没有它们，所以不会改 `S+0x36F/370/371`、`S+0x8AC..0x8B5`，也不会改黑白字段。选中 04 时 deep id 是 0，走原来的非深槽恢复，把 A5、B5 和 colour row 1 写回 stock。

## 测试

宿主和 ASan/UBSan 都是 84 项。stage2c 是 80 项。多出来的 4 项是：

- 光标 1..4 依次套用后关掉再打开，高亮回到刚才那一行，包括原生 Standard。
- 新 cache 上 `S+0x36E == 0x01` 且 WB 为 0,0 时，打开高亮 04。色彩字节不参与这次匹配。
- 顺序 `04 → 01 → 02 → 04 → 03 → 04` 每次深槽切换后的 A5/B5/colour 与该 profile 一致；04 恢复 stock。HC 发布 `0x03`，只写 `S+0x645/646`；04 发布 `0x01`，不写色彩字段。
- stock、Posi、Nega、HC 四条调子单调且在范围内。

既有的七模式守卫没有改：关闭、busy、EMPTY 时 8/12/16 行的 `commit()` 仍为 1。类别门仍是 K=0 和 K=4 套用，K=1、2、3、7、255 冲突且 S 不动。真实的新 `DEEPISP0.DAT` 在 K=4 下走完槽 1..4。

为了换成 4 行，改过的断言只有这些：

- 银行占用从「16 槽全满」改成「1..4 有配方，5..16 空」。套用循环停在 4，5..16 必须 `EMPTY`。
- 无卡回退只复制校验通过的默认项。字形检查只覆盖这四个名字。
- 深槽身份从 4 个（含 Bleach）改成 3 个。转移矩阵从 5×5=25 改成 4×4=16，stock、Posi、Nega、HC 的每一对仍都查。RPC 仍是冷启动 104、之后 102、其中 W 为 96，因为三行都还写。
- 类别冲突的第二个占用槽从 16 改到 4。槽 16 现在是空的，`select` 在进门之前返回 `EMPTY`，`commit` 仍返回 1，S 不动。
- 卡银行里「非 0/4 类别」那次探测从光标 6 改到光标 4。槽 6 已空，再探测它只会得到 `EMPTY`，测不到门。
- 原来用槽 6 恢复 stock（选择器 `0x03`）的地方改成槽 4。选择器是 `0x01`，表仍恢复 stock。
- v1 伴随文件不再装 16 个彩色名。它有 Posi、Nega，以及 HC 的彩色降级（对比度 display 5、锐度 display 6、鲜艳度 display 1）。04 不在里面，因为 v1 写不出 mode `0x01`。导入结果仍是彩色，不能冒充真黑白。
- `test_recipe_v1` 里「未知 base mode」的探针从字节 1 改成字节 2。字节 1 配上残留的色彩 raw 现在返回 `CORRUPT`。
- 宿主预览桩接受选择器 `0x01`，原有的 `0x04/0x03/0x06` 仍接受。
- `full_library_test` 仍用独立的 16 槽验证夹具，测的是文件格式还能装 16 槽，不是这台相机的配方银行。那组断言没改。

分派器 25/25，和官方落到同一条 case，活动字不改。ABI 模型 36。工具测试 17。镜像审计 7：整镜像通过，改组件、改 hook、改分支、加回 `force_adj_image`、错偏移、改 payload 都被拒绝。`recipe_v1` 的 base-mode 用例宿主和 ASan 都是 68，其中包含 Standard 只写选择器和 WB。容器校验和、声明范围外无改动、探针尾 `0xFF`，由 `audit_image.py` 和打包脚本各算了一次。保护窗口 30 个与原厂相同。

## 哈希

新 `ilaunch3` 是 `99373f423ef1142467bdf681a4625a7da50ea55fc93904eab537fdec91411e7b`。payload 7680 字节，SHA-256 `2e777ebec4b77d4246bb2b8c1e5e13daa9064eec97a3d848caeaa11e4ef21cc6`，从 `0x2005276C` 到 `0x2005456C`。探针尾 `0x20054700..0x20054800` 是 `0xFF`，前面还空 404 字节。校验和 phase 0 是 `0x6a784a28`，按 `sum(body[i] * ((i-0x200)%6+2))` 从偏移 `0x200` 起独立重算过。

写报告前后这三个文件的 SHA-256 没变：

- 官方 `ilaunch3` `da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7`
- 官方 `jlaunch3` `951be1c659c85af58ae3e4ce98707c52f0b4514fc2075256854d59f822671673`
- stage2c `ilaunch3` `11d0e9839fa93f6d23f4e9a92b8fc1b569d32498a911412769cb1babc44d7a0c`

`shasum -a 256 -c SHA256SUMS` 在包目录里通过。

## 和 stage2c 的字节差

相对 `11d0e983…` 共 4982 个字节不同，分成 312 段。payload 以外只有四段：

1. 文件 `0x16D..0x170` 的 3 字节。校验和在 `0x16C` 的高字节没变，整值是 `0x6A784A28`。
2. `adj_empty_details`，文件 `0x1B3DEB`，1 字节。`rfw_no_details` 指针的低字节随 rodata 挪了。
3. `adj_name_table`，文件 `0x1E47AB`，1 字节。关闭表指针的低字节同样挪了。
4. `adj_count_16`，文件 `0x1E47AC`，1 字节。`0x10` 变成 `0x04`。

另外五个 hook（`init_recipe_cache`、`init_cursor_bypass_enum`、`fn2_no_editor`、`adj_confirm_close`、`live_recipe_commit`）与 stage2c 逐字节相同。入口 `ricoh_recipe_open` 还在 `0x2005276C`，所以指向它的 hook 不用改立即数。分派器、跳表、探针尾都没变。

payload 从文件 `0x796C` 起。前 71 字节与 stage2c 相同。其后 `0x79B3..0x976A` 有 307 段、4652 字节不同。代码骨架大多还在，差的是重定位后的立即数，以及新的配方记录和表；周围指令相同，所以差集是碎的，不是一整块替换。`0x976C..0x98B0` 的 324 字节是 stage2c payload 多出来的尾巴，这一版不再占用，恢复成 `0xFF`。完整的偏移和长度在 `evidence/diff-vs-stage2c.json`，里面没有表字节。

payload 变短是因为 Bleach 的表去掉了，色彩行三份深槽共用 stock 的同一份，同时 `rv1_plan` 加了 Standard 分支，`rfw_open` 加了空槽判断。这些长度变化把后面的绝对地址挪了一点，payload 内部指向 rodata 的立即数就跟着变。

## 上机时按这个顺序拍

同一场景、同一光线。快门 1/80，光圈 f/2.5，ISO 500，白平衡固定，不要自动。按这个顺序拍，每张记下文件名和槽：

1. `04 Std`
2. `01 Posi`
3. `02 Nega`
4. `04 Std`
5. `03 HC BW`
6. `04 Std`
