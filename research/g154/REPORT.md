可以交复审

ADJ 现在是一张列表：内置 1–8、DAT 顺序的十个 Looks、DAT 顺序的已存配方，最后保留 DISP:Tw 提示行。发布包 19 行，测试包 22 行。没有 Looks 或 MyRec 分组入口。滚到名字就完整应用并预览；Look 和已存配方的 OK/DISP 沿用内置行的微调入口，从卡片页首按 DISP 返回原来那一行。每个自有页面始终发布 8 个物理行，每行最多 13 个字符，使用中的 > 与微调后的 * 保留。

这是 DAT 实现交付。全程主机验证，未访问相机或 SD 卡、未联网、未写 Git、未开子代理。机身没有重建。两条与 g153 相同的原厂续接观察尚未通过：完整 keep=1 续接，以及原始半按后的直接 part1 重显与关闭。两条均保留为 OPEN，留给发布复审，不计入缓存修正通过。

两个包的最终文件如下。

| 包 | 用户条目 | DAT B | SHA-256 |
|---|---:|---:|---|
| [package_v39_g154](../../firmware/package_v39_g154/MANIFEST.json) | 0 | 89,624 | `3c63ae08a1387af9aa5c7d30107a17e37ec743b592c6f8833e70374e8b760449` |
| [package_v39_g154_test](../../firmware/package_v39_g154_test/MANIFEST.json) | 3 | 89,624 | `ac4263a0083aff1f04ab1433029b7ba354d67083ad09292f2af49bbc59abb83e` |

| 项 | 实测 B | 上限 B | 余量 B |
|---|---:|---:|---:|
| 主请求 | 106,532 | 107,612 | 1,080 |
| DAT | 89,624 | 98,304 | 8,680 |
| 代码 | 64,728 | 65,536 | 808 |
| BSS | 9,280 | 按链接结果计入主请求 | — |

主请求按实际链接值计算：`7,628 + align4(89,624 + 9,280) = 106,532 B`。相对 g153，主请求少 540 B。没有削减效果数据。

两包各 29 个升级文件逐字节等于 package_v39_g153。ilaunch3 的 SHA-256 为 `8233a1c464b29ba88cfdfce1d083b9bf652586edeb216cacf6f16cf36788b25d`，build 为 `785706aa2323d8f1c313e37c4eab94fdd2899c2f66d40e3dda9d505f32235f81`，ABI 为 `dd55f5b9c81d35bd9f520b9449a6c463`。所有 resident 与 engine_services 文件均与 g153 相同。

源文件差异见 [source.diff](evidence/source.diff)。生产 DAT 的代数检查只改 pack.py、gate.c、eng_data.c、ui_v2_data.c。L1 由 adapter 负责完整列表，kv_ui 继续负责卡片、逐项和数值页；分组渲染与跳转已删。UvState 的旧空闲字段保留，目标编译器测得布局与 g153 相同。

用户条目的格式上限是 32 条。逻辑行数为 `8 + K + U + 1`，窗口最多 49 行，因此运行时要求 `U <= min(32, 40 - K)`，K 是本单元可见 Looks 数。当前 K=10，最多 30 个用户条目。超限整份 DAT 拒收，保持原厂 7 行且没有单元或 S 写入，不截掉条目。工具按三个单元中最大的可见 Looks 数检查，保证同一份文件在三个单元都不超限。30/10 和 32/8 的 49 行通过，31/10 与 32/10 拒收，32/0 与 0/0 也通过。

完整 552 B 比较绑定最终两个 DAT，包含九行、T、ISO100 行、身份及 CRC。主机 C 分别编译 g153 与 g154 的查询和数学代码，再用最终文件的实际展开条目比较；原生导航另对照同一完整结果。逐份二进制保存在 [outputs](evidence/outputs)，汇总见 [equality](evidence/equality-50mm-c.json)。

| 单元 | 内置默认值 | Looks 默认值 | 测试用户条目 |
|---|---:|---:|---|
| 50mm | 8/8 相同 | 10/10 相同 | 3/3 相同 |
| 28mm | 8/8 相同 | 10/10 相同 | 3/3 相同 |
| MOUNT | 8/8 相同 | 10/10 相同 | 1/3 相同，另外两条属于修正 B |

MOUNT 两个用户输出的差异如下，其他 61 份输出逐字节相同。

| 用户条目 | 基底 | Cont / High / Shad / Satu | 改变的字节数 |
|---|---:|---|---:|
| FCC*002 | 05 | 1 / 0 / 0 / 0 | 18 |
| GRN*001 | 02 | 2 / 5 / 5 / -5 | 78 |

修正 B 只让 kv_data_recipe 的 MOUNT 01–03、05–08 查询 50mm 的旋钮记录。7,904 B R3 块及已存条目扩展均保持原字节；MOUNT 04、50mm 和 28mm 的旋钮输出不变。相同合法档位的剂量改为 50mm 的剂量，因此 MOUNT 的微调输出会变化。未微调的内置和 Look 输出不变。

| MOUNT 控制 | g153 | g154 |
|---|---|---|
| 01 Satu 上限 | +8 | +6 |
| 03 High 上限 | +9 | +8 |
| 08 Satu 上限 | +9 | +8 |
| 01 Amount 步距 | 20% | 25% |
| 05、07 Amount 步距 | 10% | 20%，保留 150% 端点 |
| 08 Amount 步距 | 10% | 25% |

发生档位集合或剂量变化的控制如下。其余控制与 g153 相同；各控制的全部变化档位在 knobs.json 的 changed_controls 中逐项列出，新剂量逐字节等于同档位的 50mm 记录。

| MOUNT 配方 | 有变化的控制 |
|---|---|
| 01 | Amount、Cont、High、Shad、Fade、Satu、Warm、Tint、Splt |
| 02 | Cont、High、Shad、Fade、Satu、Warm、Tint、Splt |
| 03 | Cont、High、Shad、Fade、Filt |
| 05 | Amount、Cont、High、Shad、Fade、Satu、Warm、Tint、Splt |
| 06 | Cont、High、Shad、Fade、Satu、Warm、Tint、Splt |
| 07、08 | Amount、Cont、High、Shad、Satu、Warm、Tint、Splt |

逐档参照比较了未改变路径 2,435 项、MOUNT 映射 1,005 项、双旋钮完整 552 B 2,034 项及 Looks 单旋钮 4,401 项，见 [knobs.json](evidence/knobs.json)。Amount 非 100 仍以实际 MOUNT 的 04 为端点。06 的 Splt 按原算法启用 T1，不能把它一概当作 04；原生 +1 用例核对 T=0 和全部 552 B。原生 UI 还核对上述上限与 Amount 档位，见 [mount_knobs](evidence/mount_knobs-mount-c.json)。

缓存修正只写现有地址 0x205A2944。导航期间保留当前物理高亮行；实际撤回前写 resident 保存的 ui_restore[11]。H07 keep=0 经 finish → keep_view 的重画成功路径在最后一次重画后补写。release_view 只在实际撤回或 H07 将关闭时回写，避免保留 ERR 时先写原行。三单元各 34 项，包含 22 个基础场景、5 个平铺行、3 层微调页和 4 个错误返回组合；错误组记录 DAT 返回值、实际恢复路径、缓存写入 PC 及原厂读取片段。v3.9 的 panel_abort 仍是 H40/H41 图像入口，不是 UI 关闭入口，本轮没有改动。

平铺后的长名称另修正一处提示：原先只复制 Unsaved 的 8 个字符，会保留名称后缀成为 >UnsavedCon。C 和 Python 都复现；现在连结束符一起复制。新旧候选只相差代码中的 8→9 一个字节和八个 CRC 字节，其余六个段逐字节相同，见 [text-change-bytes.json](evidence/text-change-bytes.json)。单元完整配方和 S 状态不受此文字修正影响。最终提示用例及所有正式组均在重新构建的 DAT 上执行。

eng_core.c 与 g153 逐字节相同，SHA-256 为 `c62ca5337493c3ce974a30e8e7ca4b8bc68d593a0b965d1600dcc0fdeee7482d`。本轮没有改变配方提交、补偿或 g152 跨退出快照修正。12 项锁忙在新 Look 与用户行分别覆盖 held、S 写时遇忙、短暂忙；拒绝后逐字节保留此前九行/T、全部 4,096 B S 和 56 B 引用，退出、重开后再比较。锁场景的 WB=10 和锁时序均是明示模型输入。跨退出原场景另检查 04/08 实际此前状态，以及行或 T 在快照期间变化的错误路径。

断电行为保留：v1 记录只存内置。上次用内置时，下次 ADJ 高亮该内置，但开机实际仍是纯 04，等用户确认才应用。Look 或用户条目在记忆写入成功后清掉已知 v1 记录，冷启动的 ADJ 因而高亮 04。若记忆写忙并显示 Unsaved，原有效内置记录可能保留，下次会高亮它，实际仍是纯 04；本轮另以最后有效记录为 08 的场景验证。换到新 DAT 的第一次启动，旧记录也因 DAT 身份变化不再预选。三个单元用保存的完整 S 建立新实例验证；这不是物理断电证据。

本轮正式选择的作业如下。机器码场景使用 C 指令后端；552 B 全量比较与旋钮逐档比较使用主机编译的 C 查询和数学代码。每项新名称从头运行，前台等待，nice=10，超时 10,800 秒。批次内部串行，定位时最多三个作业。原生边界仍采用现有模型；没有用 core.op 统计钩子改变 C 执行。

| 作业 | 后端 | 秒 | 结果 |
|---|---|---:|---|
| [accepted-pending](evidence/job-accepted-pending.json) | C 指令 | 18.3 | PASS |
| [accepted-cache-50mm](evidence/job-accepted-cache-50mm.json) | C 指令 | 320.8 | PASS |
| [accepted-cache-mount](evidence/job-accepted-cache-mount.json) | C 指令 | 335.8 | PASS |
| [accepted-cache-28mm](evidence/job-accepted-cache-28mm.json) | C 指令 | 329.2 | PASS |
| [accepted-navigation-50mm](evidence/job-accepted-navigation-50mm.json) | C 指令 | 74.4 | PASS |
| [accepted-cards-50mm](evidence/job-accepted-cards-50mm.json) | C 指令 | 33.3 | PASS |
| [accepted-navigation-mount](evidence/job-accepted-navigation-mount.json) | C 指令 | 73.9 | PASS |
| [accepted-cards-mount](evidence/job-accepted-cards-mount.json) | C 指令 | 33.8 | PASS |
| [accepted-navigation-28mm](evidence/job-accepted-navigation-28mm.json) | C 指令 | 66.4 | PASS |
| [accepted-cards-28mm](evidence/job-accepted-cards-28mm.json) | C 指令 | 33.5 | PASS |
| [accepted-busy-50mm](evidence/job-accepted-busy-50mm.json) | C 指令 | 127.1 | PASS |
| [accepted-busy-mount](evidence/job-accepted-busy-mount.json) | C 指令 | 126.5 | PASS |
| [accepted-cross-50mm](evidence/job-accepted-cross-50mm.json) | C 指令 | 52.1 | PASS |
| [accepted-cross-mount](evidence/job-accepted-cross-mount.json) | C 指令 | 49.2 | PASS |
| [accepted-exits-50mm](evidence/job-accepted-exits-50mm.json) | C 指令 | 177.7 | PASS |
| [accepted-exits-mount](evidence/job-accepted-exits-mount.json) | C 指令 | 174.7 | PASS |
| [accepted5-lifecycle-50mm](evidence/job-accepted5-lifecycle-50mm.json) | C 指令 | 33.6 | PASS；重显观察另列 OPEN |
| [accepted5-lifecycle-mount](evidence/job-accepted5-lifecycle-mount.json) | C 指令 | 32.2 | PASS；重显观察另列 OPEN |
| [accepted5-lifecycle-28mm](evidence/job-accepted5-lifecycle-28mm.json) | C 指令 | 33.3 | PASS；重显观察另列 OPEN |
| [accepted3-power-50mm](evidence/job-accepted3-power-50mm.json) | C 指令 | 60.4 | PASS |
| [accepted3-power-mount](evidence/job-accepted3-power-mount.json) | C 指令 | 60.4 | PASS |
| [accepted3-power-28mm](evidence/job-accepted3-power-28mm.json) | C 指令 | 62.2 | PASS |
| [accepted3-ownership-50mm](evidence/job-accepted3-ownership-50mm.json) | C 指令 | 12.7 | PASS |
| [accepted3-ownership-mount](evidence/job-accepted3-ownership-mount.json) | C 指令 | 11.9 | PASS |
| [accepted3-ownership-28mm](evidence/job-accepted3-ownership-28mm.json) | C 指令 | 12.5 | PASS |
| [accepted3-cap-50mm](evidence/job-accepted3-cap-50mm.json) | C 指令 | 95.9 | PASS |
| [accepted3-cap-mount](evidence/job-accepted3-cap-mount.json) | C 指令 | 94.2 | PASS |
| [accepted3-knobs](evidence/job-accepted3-knobs.json) | 主机 C | 7.3 | PASS |
| [accepted3-mount-knobs](evidence/job-accepted3-mount-knobs.json) | C 指令 | 224.0 | PASS |
| [accepted3-pending-power](evidence/job-accepted3-pending-power.json) | C 指令 | 24.7 | PASS |
| [accepted7-identity](evidence/job-accepted7-identity.json) | C 指令 | 33.5 | PASS |
| [accepted-equality](evidence/job-accepted-equality.json) | 主机 C | 3.0 | PASS |

共 32 个正式作业，耗时合计 47.1 分钟。生命周期内的原厂重显观察单列 OPEN，其他所选断言通过。逐组用例数在对应 JSON 中；不存在未结束却计为 PASS 的组。最终输入核对 493 项无变化，完整结果见 [audit.json](evidence/audit.json)。

初始失败全部保留。原厂完整 OK 续接 keep=1 后，父视图标记变 0，下一次方向键不进入 DAT；50mm 的 g153/g154 在 C、Python 上相同。这条继承路径不计作修正通过，留给发布复审。最终 keep=1 证据使用真实 rv_engine 调 DAT 事件入口，之后继续原厂导航和 keep=0 关闭，属于 DAT 调用层。

直接 part1 重显也保留了一项未通过观察：50mm 的 g153/g154 在 C、Python 上都保留逻辑行 8、物理行 6，但原厂把游标和缓存改为 2；随后完整 OK 续接没有 DAT 事件入口。g154 的三个单元均记录了这项 OPEN。这条原厂重显与关闭路径不计逻辑高亮或缓存修正通过，留给发布复审。生命周期作业另验证重画失败时撤回和真实 ig_stop 后恢复；原始半按与 part1 只按已知对照记录，不代表整条路径通过。

错误矩阵曾把 DAT 主动撤回也要求为 resident 恢复，C、Python 都确认实际游标和缓存正确，现按真实关闭方断言。卡片测试从第一条用户配方走到提示行时已预览第三条，旧的重开预期仍写第一条；Python 确认后改为第三条及完整 552 B。文字错误测试曾误用服务 9，改为 abi.h 的 UI_TEXT=11 后才实际触发错误返回。身份测试先建立匹配单元模型，再按 g153 共用方法在文件边界提供待核对 DAT。封闭环境的首次磁盘查询、复制脚本的路径错误保留为准备问题。早期可重建的主机中间文件及数量测试的临时变体曾放在获准研究目录，最终入口改到指定 Scratch，旧目录也已清理。旧入口源码副本与哈希保留。初版 DAT 的 smoke 和导航回执只作历史记录，不计最终测试；中间批次在作业边界停止，未启动的组不计通过。对应关系见 [issue-resolutions.json](evidence/issue-resolutions.json)。

| 非 PASS 作业 | 后端 | 秒 | 记录 |
|---|---|---:|---|
| [accepted-lifecycle-50mm](evidence/job-accepted-lifecycle-50mm.log) | c | 13.9 | 保留，未计为正式通过 |
| [accepted2-lifecycle-50mm](evidence/job-accepted2-lifecycle-50mm.log) | c | 14.5 | 保留，未计为正式通过 |
| [accepted3-identity](evidence/job-accepted3-identity.log) | c | 18.2 | 保留，未计为正式通过 |
| [accepted4-lifecycle-50mm](evidence/job-accepted4-lifecycle-50mm.log) | c | 21.7 | 保留，未计为正式通过 |
| [accepted6-identity](evidence/job-accepted6-identity.log) | c | 24.2 | 保留，未计为正式通过 |
| [cache-50mm-c-r2](evidence/job-cache-50mm-c-r2.log) | c | 337.4 | 保留，未计为正式通过 |
| [cache-50mm-c](evidence/job-cache-50mm-c.log) | c | 123.7 | 保留，未计为正式通过 |
| [cache-error-keep1-python](evidence/job-cache-error-keep1-python.log) | python | 136.5 | 保留，未计为正式通过 |
| [cache-errors-c-observe](evidence/job-cache-errors-c-observe.log) | c | 25.3 | 保留，未计为正式通过 |
| [cache-keep1-control-c](evidence/job-cache-keep1-control-c.log) | c | 6.8 | 保留，未计为正式通过 |
| [cache-keep1-control-python-r2](evidence/job-cache-keep1-control-python-r2.log) | python | 126.4 | 保留，未计为正式通过 |
| [cache-keep1-control-python](evidence/job-cache-keep1-control-python.log) | python | 0.0 | 保留，未计为正式通过 |
| [cache-keep1-python](evidence/job-cache-keep1-python.log) | python | 124.8 | 保留，未计为正式通过 |
| [cards-reopen-python](evidence/job-cards-reopen-python.log) | python | 416.7 | 保留，未计为正式通过 |
| [final-cards-50mm](evidence/job-final-cards-50mm.log) | c | 35.5 | 保留，未计为正式通过 |
| [identity-marker-python](evidence/job-identity-marker-python.log) | python | 72.9 | 保留，未计为正式通过 |
| [identity-python](evidence/job-identity-python.log) | python | 380.8 | 保留，未计为正式通过 |
| [lifecycle-50mm-python](evidence/job-lifecycle-50mm-python.log) | python | 235.0 | 保留，未计为正式通过 |
| [lifecycle-font-python](evidence/job-lifecycle-font-python.log) | python | 365.3 | 保留，未计为正式通过 |
| [lifecycle-g153-c](evidence/job-lifecycle-g153-c.log) | c | 14.7 | 保留，未计为正式通过 |
| [lifecycle-g153-python](evidence/job-lifecycle-g153-python.log) | python | 239.4 | 保留，未计为正式通过 |
| [part1-close-g153-c](evidence/job-part1-close-g153-c.log) | c | 15.2 | 保留，未计为正式通过 |
| [part1-close-g153-python](evidence/job-part1-close-g153-python.log) | python | 244.6 | 保留，未计为正式通过 |
| [part1-close-python](evidence/job-part1-close-python.log) | python | 239.8 | 保留，未计为正式通过 |
| [pending-before-c](evidence/job-pending-before-c.log) | c | 15.6 | 保留，未计为正式通过 |
| [pending-before-python](evidence/job-pending-before-python.log) | python | 251.8 | 保留，未计为正式通过 |

身份组确认新 DAT 在 8233a1c4 装载；g151、g137、g139、g150、g152 和探测 DAT 在当前机身的拒绝，以及新 DAT 在旧 v3.9/v3.8 机身的拒绝均保留，这些不匹配组合为零 DAT 入口。g153 与 8233a1c4 仍然匹配并正常装载，因为机身未改。新 DAT 仅改成旧代数标记时，机身身份仍匹配，经过一次 init 后由 DAT 代数检查拒收；原厂 7 行、完整 S 和单元状态均正确。

留给发布复审：完整 144 项锁忙、99 条旧回归全组合、81 组总回归、int16 全域与全部格式拒收、完整重入和切点矩阵、ISO100 全链、首次开机 ready 时序、真实 FAT/RTOS/IRQ/栈、LCD/物理键、真实拍照/JPG/DNG/编码、真实断电与 NAND。原厂完整 keep=1 续接、直接 part1 重显与关闭，以及 resident 在 DAT 运行前自行退役的缓存限制也留给发布复审。

以下按 CHECKLIST_NEUTRAL.md 主项自查。PASS 只覆盖本轮列出的层级。

| 项 | 结果 | 核对与边界 |
|---|---|---|
| 1 流程、中性文字、进程 | PASS | 无子代理；正式批次前台串行、nice 10；定位时最多三个模拟器作业；全部初始失败和回执保留。 |
| 2 Studio 管线 | 不适用 | 未改 Studio。 |
| 3 归属、重入、指针 | PASS，差量 | 复用原归属场景；实际关闭才写缓存；完整重入矩阵留给发布复审。 |
| 4 模型与原生分开 | PASS，主机层 | 游标、S 和锁初值均明示；构造、按键、导航和关闭运行机器码。 |
| 5 原厂时机与隐藏路径 | OPEN，继承 | 三单元错误重画撤回与 ig_stop 恢复通过；直接 part1 重显和完整 OK 续接未通过，50mm 的 g153 对照相同，留给发布复审。ISO100 和首次 ready 时间线未跑。 |
| 6 范围、布局、结束回执 | PASS | 目标编译器重测布局；最终 DAT 回执完整；未跑总回归的项明确列出。 |
| 7 基线、未知值、邻接字节 | PASS，差量 | 核心不变；跨退出比较全部单元行/T 与完整 S，不用槽号代替字节。 |
| 8 原厂续接、八行窗口 | PASS，所测范围 | 所有自有窗口发布 8 行，49 行边界通过；完整 keep=1 原厂续接单列继承限制。 |
| 9 文件语义与 FAT | PASS，离线范围 | 未增加任何相机文件写入；真实 FAT 留给发布复审。 |
| 10 失败、退出、恢复 | PASS，差量 | 错误 close、锁忙、退出和重开通过；机主步骤有移除 DAT 与拔电池 10 秒恢复。 |
| 11 物理键和显示 | 未运行 | 只有原生逻辑事件、H10 站点与模型消息分发；留给发布复审。 |
| 12 返回值、锁、有界循环 | PASS，差量 | 锁返回值和 S 零写明确断言；行数上限 49，原 16 轮重入界限保留。 |
| 13 断电状态 | PASS，模型层 | 三单元新实例验证内置预选及 Look/用户后的纯 04；真实断电未运行。 |
| 14 三个单元 | PASS，主机层 | 50mm/MOUNT 完整列表，28mm 子集；三单元完整 552 B 比较。 |
| 15 现场变量、官方文件 | PASS，离线范围 | 两包 29 个升级文件逐字节等于 g153；机身和 DAT 分别绑定哈希。 |

附节一的 16 项也逐项核对。

| 项 | 结果 | 核对 |
|---|---|---|
| A1 尺寸门槛 | PASS | 只用本任务 107,612 / 98,304 B。 |
| A2 余量与硬限分开 | PASS | 按实测 1,080 / 8,680 B 报告，不增加门槛。 |
| A3 共享函数 | PASS | 核心、resident、services 源码逐字节不变。 |
| A4 前提 | PASS | 原厂 keep=1 续接已用 g153 对照，不把旧预期当事实。 |
| A5 有界输入 | PASS | 32 条格式容量、49 行总上限及原 16 轮界限明确。 |
| A6 旧布局 | PASS | 用目标编译器重测，未套用旧整数偏移。 |
| A7 冻结恢复规则 | PASS | 机身恢复字段未改；缓存按同一 ui_restore[11] 回写。 |
| A8 只读语义 | PASS | 未新增诊断遍历或相机 I/O。 |
| A9 快照语义 | PASS | 复用 g152 已修正的事务资格期限，不承诺跨 RPC 原子状态。 |
| A10 设置字节 | PASS | 所测拒绝与退出比较完整 4,096 B S，不只比较 selector。 |
| A11 冻结机身限制 | PASS | 原厂续接和 resident 自行退役的继承边界明示。 |
| A12 交付门槛 | PASS | 结论是交复审，不是上机批准。 |
| A13 机主步骤 | PASS | 只换 DAT、检查平铺列表、移除 DAT 和拔电池 10 秒。 |
| A14 输入交接 | PASS | 源码、回执、哈希和模型来源都在本目录。 |
| A15 分阶段与未跑项 | PASS | 未运行组明确留给发布复审。 |
| A16 文字 | PASS | 新写脚本和文档使用中性工程用语。 |

附节二的物理边界均未运行，不计 PASS。原厂构造、缓存读取和消息分发的主机证据只用于上述具体路径。

复跑示例，名称必须使用新值：

```sh
TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/g154-impl-r1 GXR_HARNESS_BACKEND=c nice -n 10 sandbox-exec -f research/g154/offline.sb /usr/bin/python3 -I -B research/g154/run.py --name review-navigation-50mm research/g154/verify.py navigation --unit 50mm
```

完整串行入口为 batch.py；单组均可用 run.py 直接重跑。保留旧失败结果，不读旧 PASS 代替执行。源码重放为 prepare.py，构建为 build.py，组包为 package.py；不重建机身。最终重构建逐字节比较见 evidence/reproduce.json，清理见 evidence/cleanup.json，封存清单为 SHA256SUMS。
