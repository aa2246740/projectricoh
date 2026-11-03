gen 122 已产出，W 前失败和 H01 延后核对已实现；完整模型验收未完成（INCOMPLETE），见第 3 节。 完整拍摄仍受设备模型边界限制；说明区提示与非锁定短码未实现。

最终 DAT 为 `firmware/package_v36_g122/SD_ROOT/GXRCE.DAT`，63,380 B，generation 122，SHA256：`9724268c3d8a2c8c60650b903db1d536ca6ab594f95144d5991cb3b964ebb262`。本表只认此 SHA。

## 1. W 前失败和首次开表的界面行为

H08 或面板操作在 W 前失败后，不撤回仍归本引擎的视图。列表保持八行，面板保持十一行；光标、原生缓存及小圆点回到最后核对有效的行或数值。尚未应用时使用标准 04 选择，内部 applied 为 0。下一次 H08、H06 或 H07 先重绑并完整核对，再执行这次操作。只有视图归属丢失、界面绑定失败或会话身份不再有效时才结束该视图。

H01 已改为把核对与发布分开。已加载会话在通信失败、ready 为 0 或可重新绑定的 epoch 变化时，先用已验证的卡内数据发布八行，把光标放在当前确认的配方；核对推迟到下一次 H08/H06/H07。延后本身不锁定，也不发送 W。若实际 W 后全部补偿失败，仍使用原 ERR 原因码与锁定规则。

测试从官方构造函数和原生按键建立状态。`native/first-open-*.json` 覆盖三单元 H01 的通信失败、ready 为 0、settings epoch 与通信失败、ready 为 0 且行已复位四种条件及三种后续入口。列表绘制观察点必须始终读到八行。最终 `native/keep-cases-*.json` 使用十二例核心组合：列表和面板的通信失败分别测试方向键、DISP、确认三个入口，再分别测试连续三次失败、ready、settings epoch 后的方向键重试。完整三十六例组合尚未全部重跑；mode epoch 与行复位的其余入口不列作已验收。epoch 条件由明确的设备模型变化建立，不充当真实拍摄会改变 epoch 的证据。

用户在 12:31 补充的 gen 121 / 50mm 真机事实已纳入：DISP 能打开面板，原始 0x15 → 逻辑 0x25 → H06 已在该单元实机确认；R8051485、R8051486、R8051487 均完整应用配方，灰块无可见偏色，参数为 ISO200、1/60、f/2.5。首开七行、左右切一次 ADJ 项目后恢复八行是已确认的界面现象。本轮没有读取相片或操作相机。

resident 仍有 DAT 够不到的入口：`hooks.c:70` 在 inflight 或 RF_BUSY 非零时先返回，H01 的 early 不改续程，因此这时 DAT 没有被调用，不能发布八行。`hooks.c:71` 的 rv_check 失败会退役并停用会话。RF_BUSY 只由加载器设置和清除，inflight 只包围 rv_engine 调用；源码未见拍摄直接设置这两个字段。rv_check 硬失败也不能靠普通左右切换恢复，和现场可恢复的表现不符。现场没有这些字段的读数，唯一根因仍未知。`native/resident-entries-*.json` 单独核对这些限制，不把预期的七行边界写成首开修复通过。冷启动时 ready 为 0、DAT 尚未加载，同样无法由卡内代码修复。

确认键还有固定机身收尾限制：`hooks.c` 在 H07 的 keep=0 时，即使 DAT 返回 CONSUMED，也会执行 rv_ui_abort 并关闭列表。本轮确认重试通过指单元已恢复后进入引擎并成功核对；若确认重试时仍忙，DAT 无法阻止固定收尾关闭。持续失败后确认仍保留界面的要求未完成，不把方向键和 DISP 的保留结果扩展成该路径已通过。

追加的 H01 视图切换检查在前序候选 10fa4ca0… 中发现四次 DAT 对其他界面的写入。最终候选在列表服务的 IRQ 临界区核对 activity=8、state=56，失配即返回 STALE，不发布或重绘该列表。三单元最终记录见 native/h01-view-change-*.json，DAT 写入为零。不过固定机身在 H01 返回后仍继续原生构造，三个模型中的另一界面光标均由 7 变成 2；该后续写入来自固定机身，不是 DAT。此边界未消除，本轮没有把 DAT 零写入写成整个原生界面完全保持。

说明区目前维持空记录。当前 DAT 的 RV_UI_LIST 明确拒绝十二字节说明记录中任何非零字，且没有已审阅的文字记录复制和指针重定位约定。H05 使用的又是脱离引擎缓存的原生快照；只填入字符串地址不能证明记录格式、归属和寿命安全。因此没有显示 DISP: Tweak，也没有在其后显示非锁定短码。这两项未实现，不以空记录绘制代替提示文字验收。来源见 `resident-and-details-boundaries.json`。

面板保留 Cont、Satu、HiLt，改用完整的 Shadow。原有预算是八个 ASCII 字符、18 B 字形，带符号数值至少占两字符；Contrast、Saturation、Highlight 至少需 10、12、11 字符，Shadow+5 恰为八字符。最终原生绘制与字形提交记录由三单元四参数测试和 `native/fn2-step-counts-*.json` 保留。它们验证现有字体接口预算，实体 LCD 仍未在 gen 122 上检查。

## 2. 开表通信成本

| 单元 | gen 121 冷开 | gen 122 冷开 | gen 121 正常重开 | gen 122 正常重开 | gen 121 复位后重开 | gen 122 复位后重开 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| A12 50mm | 0 | 0 | 265 | 20 | 805 | 825 |
| A12 28mm | 0 | 0 | 264 | 20 | 803 | 823 |
| MOUNT A12 | 0 | 0 | 264 | 20 | 803 | 823 |

计数读取实际槽 8 的 X/V/W 调用。每代每单元在一次官方构造会话中连续重开两次，记录必须有八行、光标 5、无失败响应且 W=0；两次计数的范围见 `rpc-measurement-review.json`。正常重开读取 T，再读九行各一个完全位于行内的半字，共 20 次 RPC；不发送 W。哨兵不一致时先完整读回，再恢复；epoch 变化或前次检查未完成时直接完整核对。因此复位恢复路径会比 gen 121 多一轮廉价检查，正常路径调用次数下降。预览内部的单元通信未由设备模型展开，未计入。未跑五次交替延迟试验，主机也处于繁忙状态；真机开表耗时仍无结论，计数不是相机毫秒数。

哨兵按当前有效行与标准 04 的差异选择：每条发生变化的行，取第一个在行内且值不同的对齐半字。只有非对齐边缘不同、找不到这种半字时，退回完整读取。未变化的行取第一个行内半字。三单元每个非 04 配方至少有五条行与原厂不同，完整原厂复位一定改变检查向量；标准 04 与共享行本来相同，无法为它们构造不同值，也无需因原厂复位重写它们。原生设置计划仍在每次重开检查。逐行地址、位置和值见 `sentinel-proof.json`，最终真实二十次调用及行内边界见 `open-counts-122-*.json`。

## 3. 最终 DAT 的完整验收表

| 功能组 | A12 50mm | A12 28mm | MOUNT A12 |
| --- | --- | --- | --- |
| 原审查主矩阵 | PASS | PASS | PASS |
| 原始通信日志复核 | FAIL | FAIL | FAIL |
| 四参数全部 RPC 与 preview 切点 | PASS | PASS | PASS |
| 其余原审查 24 条命令 | INCOMPLETE 2/24 | INCOMPLETE 2/24 | INCOMPLETE 2/24 |
| W 前失败保留列表和面板，三种入口重试 | PASS | PASS | PASS |
| H01 首开核对失败仍发布八行，三种入口重试 | PASS | PASS | PASS |
| d1：连续三次 W 前通信失败后重试 | PASS | PASS | PASS |
| d2：部分 W 后连续四次通信失败后恢复 | PASS | PASS | PASS |
| d3：ready 临时为 0 后恢复 | PASS | PASS | PASS |
| 四次确认配方、一次或两次 04、再试原目标 | PASS | PASS | PASS |
| DISP 原始键打开面板、循环四参数、保留结果 | PASS | PASS | PASS |
| Fn2 切走再回来 | PASS | PASS | PASS |
| W 前两个 ready 边界 | PASS | PASS | PASS |
| 工作区与界面分配失败后重试 | INCOMPLETE | INCOMPLETE | INCOMPLETE |
| ERR 原因码、单行光标及空说明 | INCOMPLETE | INCOMPLETE | INCOMPLETE |
| 列表与面板合并循环各 16 轮 | INCOMPLETE | INCOMPLETE | INCOMPLETE |
| 四参数各 20 格通信计数 | PASS | PASS | PASS |
| 十六种相邻行转换计数 | PASS | PASS | PASS |
| resident 三种 H01 入口限制的边界核对 | PASS | PASS | PASS |
| H01 核对中视图切换：DAT 不改其他界面 | PASS | PASS | PASS |
| H07 keep=0 且重试仍失败后的界面保留 | INCOMPLETE_FIXED_RESIDENT：固定收尾会关闭 | INCOMPLETE_FIXED_RESIDENT：固定收尾会关闭 | INCOMPLETE_FIXED_RESIDENT：固定收尾会关闭 |
| 参数名预算与原生文字路径 | PASS：Shadow，其余保留短名 | PASS：Shadow，其余保留短名 | PASS：Shadow，其余保留短名 |
| 拍摄前缀 (a) ADJ 离开后半按、全按、重开 | INCOMPLETE_DEVICE_REGISTER | INCOMPLETE_DEVICE_REGISTER | INCOMPLETE_DEVICE_REGISTER |
| 拍摄前缀 (b) 列表内半按、全按、重开 | INCOMPLETE_CAPTURE_COMPLETION | INCOMPLETE_CAPTURE_COMPLETION | INCOMPLETE_CAPTURE_COMPLETION |
| 拍摄前缀 (c) Fn2 往返后半按、全按、重开 | INCOMPLETE_CAPTURE_COMPLETION | INCOMPLETE_CAPTURE_COMPLETION | INCOMPLETE_CAPTURE_COMPLETION |
| 说明区 DISP: Tweak 提示 | 未实现：非空说明记录不受当前接口支持 | 未实现：非空说明记录不受当前接口支持 | 未实现：非空说明记录不受当前接口支持 |
| 说明区非锁定短诊断码 | 未实现：依赖同一说明记录约定 | 未实现：依赖同一说明记录约定 | 未实现：依赖同一说明记录约定 |

每条原审查命令的参数、返回值及执行源文件摘要见 `acceptance.json` 与 `command-records/`；由队列执行的命令另有耗时和日志。四参数全切点要求四个参数分别完成参考操作的每一个实际 RPC 切点和 preview 切点，缺一组仍为 INCOMPLETE。后续重跑保留原错误及历史记录；前序候选不计入此表。

主队列与补跑队列分别保留日志。相同命令按完整参数、最终 DAT SHA 和执行源文件摘要复用已结束且返回 0 的记录，文件锁阻止同一命令同时写同一结果；实际命令记录见 `command-records/`、`tail-*.json`。这只减少重复执行，未结束或失败的组不会因另一组通过而被补成通过。

| 单元 / 拍摄前缀 | 开表 | 半按后 | 全按前缀后 | 模型重开后 |
| --- | --- | --- | --- | --- |
| A12 50mm / a | 1 × 12 | 1 × 12 | 未知 | 未知 |
| A12 50mm / b | 1 × 12 | 1 × 12 | 1 × 12 | 1 × 12 |
| A12 50mm / c | 1 × 12 | 1 × 12 | 1 × 12 | 1 × 12 |
| A12 28mm / a | 1 × 12 | 1 × 12 | 未知 | 未知 |
| A12 28mm / b | 1 × 12 | 1 × 12 | 1 × 12 | 1 × 12 |
| A12 28mm / c | 1 × 12 | 1 × 12 | 1 × 12 | 1 × 12 |
| MOUNT A12 / a | 1 × 12 | 1 × 12 | 未知 | 未知 |
| MOUNT A12 / b | 1 × 12 | 1 × 12 | 1 × 12 | 1 × 12 |
| MOUNT A12 / c | 1 × 12 | 1 × 12 | 1 × 12 | 1 × 12 |

每格表示十二项 epoch，顺序为 boot、heap、link、unit、SD、IROM、view、settings、mode、segment、power、IO；“1 × 12”只在实际十二项全为 1 时使用。未知格没有执行到该位置。模型重开不表示实体拍摄完成或拍后回显完成。

## 4. 安全核对

改动函数的源文件、目标反汇编与边界说明见 `source-safety.json`、`source-change.patch` 和 `compiled/`。完整读回只遍历九条已验证映射行及 T；每条逻辑比较长度恰为映射长度。哨兵地址由行基址加对齐偏移得到，发送前检查 offset+2 不超过该行长度。重应用沿用已核对的 deep/apply_impl，仅从相同映射和 T 生成 X/V/W；B5 邻字节地址来自映射。

33 B 行与奇地址行使用半字协议，完整读回和原有写回在物理边缘会同时访问一个相邻字节。该字节不属于有效行数据：读回忽略它，写回保留当时读到的原值。新增哨兵完全在逻辑行内。运行时范围检查和原始 RPC 日志逐一核对映射半字边界及邻字节原值，不能把这一点省略成物理访问永不超出 33 B。详见 `record-safety.json`。

界面操作继续使用现有自有列表和面板服务；光标缓存沿用归属及状态地址检查。不手工预置原生界面字段；其他菜单在每个通信和绘制切点的保持情况由完整切点组及原审查命令核对。RPC/界面重试没有无上限循环：九行、最多 96 B/行，列表与面板合并各最多 16 轮，补偿最多四次确认配方加两次标准 04。`compiled-loop-limits.json` 核对目标计数器，三单元 bounded-moves 核对实际返回。

两次初始化都不申请文件写位；安装入口直接返回不可用，storage 代码保持只读策略。最终重定位 DAT 的服务分派检查见 `machine-gates.json`，所有已执行会话的 create/write/rename/delete/write_open 必须为零。界面写入来源和通信地址检查见 `record-safety.json`；最终复核受保护输入见 `protected-input-check.json`。固定 resident 既有 H07 同步收尾及 H01 并发重入的限制未因 DAT 修改而消失，本表只评价这些续程在模型中实际执行到的部分。

最终原始日志复核返回 FAIL：三份主矩阵中的故障事件摘要仅含 at/cmd/value，复核器把它们误当作带完整页状态的 RPC 流，报 current page。尚未修正并重跑该复核器；这不是已确认的越界写证据，也不能列作安全核对全部通过。实际调用的运行时范围检查和原生写入来源检查保留原记录，汇总失败见 record-safety.json。本项在时间盒结束时交回。

## 5. 每格操作的通信次数

完整逐格数据见 `communication-steps.tsv`，含单元、列表或面板、参数、前后值、方向、RPC、W、写字节数及 preview。列表计数优先取独立计数运行；若该运行未结束，则从最终主矩阵已经逐步完成并核对的连续移动中选择十六种相邻转换。总矩阵即使尚未结束，也只统计已完成步骤；来源文件、总矩阵状态和 SHA 保存在 `native/list-counts-derived-*.json`，不声称另跑了一次设备模型。

| 单元 | 参数 | 已完成格数 | 每格 RPC 范围 |
| --- | --- | ---: | --- |
| A12 50mm | Cont | 20 | 42 至 42 |
| A12 50mm | Satu | 20 | 32 至 82 |
| A12 50mm | HiLt | 20 | 42 至 42 |
| A12 50mm | Shadow | 20 | 42 至 42 |
| A12 28mm | Cont | 20 | 42 至 42 |
| A12 28mm | Satu | 20 | 32 至 82 |
| A12 28mm | HiLt | 20 | 42 至 42 |
| A12 28mm | Shadow | 20 | 42 至 42 |
| MOUNT A12 | Cont | 20 | 42 至 42 |
| MOUNT A12 | Satu | 20 | 32 至 82 |
| MOUNT A12 | HiLt | 20 | 42 至 42 |
| MOUNT A12 | Shadow | 20 | 42 至 42 |

本快照包含 288 条已完成正常操作；缺少的单元或组仍为 INCOMPLETE。失败、补偿和再次重试使用对应 case 的完整 rpc_log，不混入正常每格计数。

## 6. 未覆盖的设备边界与交付

完整拍摄、单元完成消息及拍后回显仍未建模。(a) 的全按路径若停在原生 PC 0x203CE0EC 对 0xF0218814 的读取，就保留实际 traceback，记 INCOMPLETE_DEVICE_REGISTER，不提供编造的寄存器值。(b)/(c) 即使完成原始按键、状态分派与重开，也只能说明已执行前缀，记 INCOMPLETE_CAPTURE_COMPLETION。三单元的实际位置与十二项 epoch 读数保留在 `field/122-*-capture_*.json`。没有把显式 busy、epoch 或行复位条件当成真实照片完成。

实体相机上的 gen 122 首开、LCD 文字、完整拍摄与拍后回显本轮未验收。若现场第一次 H01 在 resident 的 inflight/RF_BUSY/rv_check 分支提前结束，DAT 也无法改变；本包没有修改固定 resident 或机身。

卡目录含完整 30 个文件，29 个固定文件逐字节复制自 gen 120b，只替换 DAT；CARD_SHA256SUMS 覆盖全部 30 个。映射、配方记录、metadata 和全部有效行与 gen 120b 相同，记录头 generation 与 CRC 随 122 更新。机身 SHA 为 50720c80696ca88f25dc25a85285acd0e0f19906e1d7da1dd404f6cc243f9008；官方 ZIP SHA 为 3705984b8433c40d2ed4fd2600c11f03ed8a6de7dbe7f66efd38ee5ca15fc898，包内 ilaunch3 为 da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7。

构建命令如下，卡包保留同一组固定 29 个文件。

```sh
/usr/bin/python3 -I -B firmware/engine_v44_keep/candidate/build122.py
/usr/bin/python3 -I -B research/g122_keep_list/build_package.py
```

时间盒为 2026-10-28T03:51:22Z 至 2026-10-28T06:51:22Z。只在 engine_v44_keep、package_v36_g122、g122_keep_list 三个新目录写入；未操作相机、存储卡或网络，未启动子代理，长命令均由前台进程等待。所有 Python 命令使用 /usr/bin/python3 -I -B。SHA256SUMS 覆盖这三个目录的所有普通文件，仅排除清单自身，自检结果见 checksum-selfcheck.json。

报告快照：2026-10-28T06:52:36.234589+00:00。
