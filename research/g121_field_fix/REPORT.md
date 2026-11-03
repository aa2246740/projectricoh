gen 121 DAT 候选已产出，但尚未通过完整验收：失败后的单次移动重绑仍为 FAIL；完整拍摄完成与拍后回显、物理按钮名称对应及真机乱码的独立根因仍为 INCOMPLETE。最终候选补上了重开的原生设置核对，修正过宽的永久锁定条件和重开时未核对单元行，增加有限次补偿，并缩短 ERR 文案、约束单行提示的光标与空说明。最终 SHA 的逐组状态见第 4 节，前序版本的通过结论未计入。OK 仍受固定 resident 的关闭路径限制，本包保留既有 H06/0x25 面板入口。

本轮最终对象为 `firmware/package_v36_g121/SD_ROOT/GXRCE.DAT`，61,224 B，generation 121，SHA256：

```text
3b9342ee28c523d7737e320abac1cc37ee3e6c6d122a72d5fe90cd2a3f2ee131
```

## 1. ERR 根因与证据

已确认的代码根因是把可恢复的错误写成了永久故障。gen 120b 的 `finish()` 在 `ENG_IO`、`comm_failed` 或 uncertain 时设 `n.failed=1`；`ui_finish()` 也把仍有视图归属的 `RV_FAULT` 设成同样的永久标志。列表绑定、工作区和预载失败被合并为 `ENG_IO`，因此显示 ERR 并不能证明 W 已开始或单元中留下了混合行。

基线复放的具体反例保存在 `previous-121/field/baseline-50mm-prewrite_busy.json`：首次三次通信失败，W 为 0，CPU 在 `0x20707E68` 把 `n.failed` 写成 1。阶段为 T，12 个 epoch 均未变化。该例后续重开触发旧提示，原用例要求八行，因而保留为 FAIL；这正是需要修正的旧行为，不计为 gen 121 失败。基线部分 W 后短暂忙也在同一 PC 锁定。最新基线对照和提示观察分别见 `previous-121-r3/field/baseline-50mm-*.json`、`baseline-notice.json`。

另有两个恢复缺口：旧服务把单元 ready 与会话身份绑在一起，ready 临时为 0 会使服务查找失败，甚至阻止 RPC 事务关闭；旧引擎把缓存的单元行当成仍然有效，拍摄或模式切换若重置行，再次打开不会重新应用配方。`row_reset` 的基线比较失败记录保留了预期与实际行哈希。

用户两张照片之后那一次 ERR 的唯一触发入口仍未知：卡上没有日志，Fn2 与拍摄顺序也未知。上面是已复现的缺陷及其触发条件，不能把它们写成那次真机事件的唯一解释。

gen 121 只在 `record_failure()` 写入永久标志，条件同时要求 `eng_uncertain()` 和实际 W 入口回执 `eng_write_started()`。DAT 服务在执行原生 W 调用前写 `reply.detail=1`；若在 fresh、ready、身份或服务检查处返回，回执仍为 0，不能被当成已经发送 W。其后恢复仍无法获得完整九行和 T 的确认，才保留 ERR。成功补偿会清掉 uncertain 与 W 标志。

`failure-store-actors.json` 将实际 CPU 写入与精确 ELF 对应：基线写入 `0x20707E68` 位于 `finish()`；最终候选持续失败写入为 `0x20709da0`，位于 `record_failure()`。相应机器码摘录保存在 `failure-store-*.txt`。新增前缀与 busy 序列是否写入 1，逐例记录在第 4 节和 `field-sequences.json`。

补偿最多先尝试四次已确认配方，再尝试两次标准 04，每次完整重写九行并逐字读回。身份或绑定失效时提前停止，避免对已更换的单元继续通信。当前已审阅的 16 项 DAT 服务没有延时入口，所以采用固定次数重试；没有声称实际总用时小于两秒。

W 之前的通信错误、过期 epoch、UI/列表绑定或 lease 错误会撤回自有视图，保持会话可重试；下一次 H01 重新绑定。服务查找继续核对缓存单元身份，具体通信操作另查 ready，事务关闭不再依赖 ready。每次重开有已应用配方的列表时，读取并比较全部自有行及 T；不一致就完整恢复已确认配方。boot/heap/link/unit 必须保持同一身份，settings/mode/view 可在重新核对后更新绑定。

尚未满足“下一次移动即重新绑定”：`native/next-move-*.json` 观察到 W 前失败撤回视图后是原生七行，下一次方向键仍为七行，没有进入引擎；重开才恢复八行。固定 resident 的 H08 在不拥有视图时不会调用 DAT，此项记 FAIL_MOVE_REBIND。

前序候选 `c40088ea…` 在这条补例中还出现设置不同步：三单元都由原生移动把 mode 从 1 改成 4，重开后光标显示 04，但 mode 仍是 4，见 `previous-121-r3/native/next-move-*.json`。最终候选新增 recheck 标志，W 前错误后即使尚未提交配方，重开也会核对全部行、T 和原生设置计划；设置不同而行一致时只补设置与预览。设置补齐过程在 W 前失败会清除不属于单元行的 uncertain，下次仍可重试。最终三单元证明见 `native/settings-retry-*.json`；未完成的记录不计为通过。

旧版提示的本次原生对照没有复现左上角乱码：`baseline-notice.json` 中光标与圆点都为 1，原生说明记录也是 12 个零字节。真机乱码的独立触发条件尚未定位。

ERR 的旧文案已改成 14 字符。原生层、单行描述、光标和圆点均落在第 1 行，说明记录保持 12 个零字节；H05 在拥有视图时指向自有空记录，构造前段允许使用原生第 1 行的空记录。三单元通过记录见 `native/notice-details-*.json`。这证明本包的指针、行号及字形提交条件，不能代替实体 LCD 的乱码修复验收。

变更全文见 `source-change.patch`，精确源文件及哈希见 `source-update.json`。`implement.py` 可将最终源文件集合应用到已准备的构建树；构建和打包命令如下。

```sh
/usr/bin/python3 -I -B firmware/engine_v43_fix/candidate/build121.py
/usr/bin/python3 -I -B research/g121_field_fix/build_package.py
```

## 2. 按键方案与未闭合项

本包保留原有 H06/逻辑事件 `0x25` 入口。原始消息 `0x700B`、阶段 1 经 `0x202AFE98`，再由原生 `0x202B1100` 状态分派执行；`0x20289A9C` 的转换也单独读回。启动前导、ADJ 项目切换和列表构造执行原生代码，没有给活动项、行号、视图或 getter 预置结果。完整按键组记录来自同一固定机身的前序候选，见 `previous-121-r3/field/121-*-*.json`、`key-probe.json`、`key-state-routes.json`；最终 DAT 的全按键组没有在时间盒内重跑，不计为最终包通过项。

| 操作名称或候选名称 | 原始编号 | 逻辑事件 | 在列表中的已观察行为 |
| --- | --- | --- | --- |
| Fn1 / 左候选 | 0x11 | 0x21 | 从相邻 ADJ 项目返回；不是面板入口。 |
| Fn2 / 右候选 | 0x12 | 0x22 | ADJ 槽 2 → 3，activity 8 → 9；左键返回槽 2。 |
| ADJ 拨杆左 / 右候选 | 0x1A / 0x1B | 0x30 / 0x2F | 沿原生水平导航路径。 |
| ADJ 压入候选 | 0x17 | 0x2B | 确认当前值并离开。 |
| +/上、−/下候选 | 0x0F / 0x10 | 0x1F / 0x20 | 原生纵向移动；面板内改变数值。 |
| 另一上下输入族 | 0x21 / 0x22 | 0x2D / 0x2C | 原始转换与列表分派已复放，物理名称未确认。 |
| MENU/OK 候选 | 0x18 | 0x23 | 原生 keep=0，resident 关闭列表。 |
| DISP 候选 | 0x15 | 0x25 | 可到 H06，保持列表，打开面板并循环四参数。 |
| 另一个功能键候选 | 0x16 | 0x26 | 不把它当作已确认的 DISP 别名。 |
| 快门半按 / 全按候选 | 0x0D / 0x0E | 0x29 / 0x2A | 原始键、原生状态处理已执行；释放为 0x46 / 0x47。 |

表中编号到逻辑事件及原生行为已经复放；按钮外壳上的名称仍是依据手册和行为的对应推断。尤其不能仅凭 `0x15 → 0x25` 宣称实体 DISP 已经验收。旧的“Fn2 = 0x25”命名不成立：用户实测的水平导航符合 `0x22` 路径，原始右输入的复放也确实切走 ADJ 项目。

`previous-121-r3/key-map-summary.json` 合并了三单元 42 条原始路由及通用 UI 转换结果：逻辑 0x21/0x22 → UI 12/14，0x1F/0x20 → 19/20，0x23 → 50，0x25 → 10，0x26 → 11，0x2B → 83，0x2C/0x2D → 52/53；0x29/0x2A/0x2F/0x30 的通用结果为 98，具体行为仍由原生状态表分派。没有把这些层次合并成一个按键编号。

仅改 DAT 无法让本次观察到的 OK 保持列表：固定 resident 在 keep=0 时无条件转关闭续程，DAT 返回 consumed 也不能改变这一点。因此没有把 OK 接到面板入口。本包的面板仍由 `0x25` 打开并切换对比、饱和、高光、阴影，ADJ 与半按保留当前值并离开。

最小 resident 方案仅作说明，未修改或构建：在 H07 且 `owned()` 成立时，限定 saved r8=`0x23`、caller LR=`0x202C2D74/0x202C2D84`，把请求送到现有 `panel_open`，保留视图；成功时走一个专用短续程。该续程弹出 H07 保存的 LR，将 r0 置 3，再进入 `0x202C33E0` 的原生收尾，返回事件循环而不走 `0x202C3384` 的 activity 清零尾段。仅把 keep 改成 1 不够，因为原调用者仍会执行关闭尾段。该方案还需机器码、栈平衡、所有其他 H07 来源及新 resident 绑定验证。

## 3. 原因码

格式为 `ERR ESP.QQ OFF`，共 14 个 ASCII 可见字符。例如已实际绘制的 `ERR 811.16 OFF`：入口 8，最后阶段 1，状态 1，RPC 尝试序号低八位为十六进制 16。

| 位置 | 解码 |
| --- | --- |
| E | 1=菜单打开；6=H06 面板入口；7=H07 确认/离开；8=H08 列表或面板移动。 |
| S | 0=空闲；1=T；2=九行；3=原生设置；4=预览；5=已确认；6=浏览。 |
| P | 0=ENG_OK；1=REJECTED；2=UNCERTAIN；3=STALE；4=IO；5=FAULT。 |
| QQ | RV_RPC8 操作 2–4 的服务调用尝试计数，低八位十六进制，256 次回卷。 |

S/P 是锁定时最后一次恢复留下的阶段与返回状态，QQ 也包括在服务检查处被拒绝的尝试；它们不是首次失败的完整历史。没有写卡上日志。

ERR 表示单元行仍未获完整确认，不能把 OFF 提示当成关机已经恢复九行与 T 的证据；实体单元的掉电复位未测试。

## 4. 测试结果

只把最终 SHA 对应的记录计入本节。`previous-121`、`previous-121-r2`、`previous-121-r3`、`previous-121-r4` 和 `history` 保留前序版本及原始失败，不充当最终 DAT 通过证据。前序 60,336 B 候选的三单元主矩阵、四参数全部切点和 240 格计数均已完成；61,204 B 候选补上设置核对后，又在工作区分配失败重开时暴露了行数初始化顺序问题，见 `previous-121-r4/native/cases/allocation-retry-*-workspace.json`。最终候选先初始化可见行数，再核对行和设置。最终全矩阵仍为 INCOMPLETE，本节只列实际结束的组。测量脚本读取编译器导出的 `panel.parameter=549`；一次中间检查误读了 `panel.param_index=519` 映射表，原始版本与失败摘要保存在前序 history 和 `parameter-check-failures.json`。

| 功能组 | A12 50mm | A12 28mm | MOUNT A12 |
| --- | --- | --- | --- |
| 原审查主矩阵 | INCOMPLETE | INCOMPLETE | INCOMPLETE |
| 四参数全部 RPC 与 preview 切点 | INCOMPLETE | INCOMPLETE | INCOMPLETE |
| 四参数各 20 格计数 | PASS | PASS | PASS |
| W 前两个 ready 边界 | PASS | PASS | PASS |
| 工作区与 UI 分配失败后重开 | PASS | PASS | PASS |
| ERR 行、光标及空说明 | PASS | PASS | PASS |
| 列表与面板合并循环 16 轮 | PASS | PASS | PASS |
| 其余原审查命令 | INCOMPLETE 0/24 | INCOMPLETE 0/24 | INCOMPLETE 0/24 |
| 释放视图后单次方向键重新绑定 | FAIL_MOVE_REBIND | FAIL_MOVE_REBIND | FAIL_MOVE_REBIND |
| 四次确认配方失败后标准 04 与再次重试 | INCOMPLETE | INCOMPLETE | INCOMPLETE |
| 原生模式恢复与 W 前预览失败后重试 | PASS | PASS | PASS |
| 十六种相邻行转换计数 | PASS | PASS | PASS |

原审查主矩阵包含冷开 04、41 格连续导航、OK/ADJ/半按、失败补偿、面板保留与重新启动。其余 24 条命令每单元覆盖 a–h、H07 全状态、保留与失败、退出、名称、切入面板、另一个菜单切换、绘制末端、输入合并和 W 前失败；完整命令、日志及替代重跑状态见 `acceptance.json`。四参数全切点仍在独立分组内，缺一组就不把完整矩阵记成 PASS。

原 78 条完整审查命令的最终完成情况与待跑命令逐一列在 `unfinished-commands.json`。最终候选优先完成初始化顺序修正相关的三单元检查，未完成的整组没有用前序候选替代。

两个 16 轮上限还核对了最终 ELF 的计数器初始化与递减，见 `compiled-loop-limits.json`；实际持续输入返回见 `native/bounded-moves-*.json`。这不是整份新引擎的完整编译改码审查。

| 新增序列 | 三单元执行状态 | n.failed 观察 |
| --- | --- | --- |
| (a) 列表选配方、ADJ 离开、半按与全按、重开 | INCOMPLETE | 最终候选未完成此序列 |
| (b) 列表内半按与全按、重开 | INCOMPLETE | 最终候选未完成此序列 |
| (c) Fn2 右移、左移回来、半按与全按、重开 | INCOMPLETE | 最终候选未完成此序列 |
| (d1) W 之前连续三次通信失败后恢复 | INCOMPLETE | 最终候选未完成此序列 |
| (d2) 部分 W 后连续四次通信失败后恢复 | INCOMPLETE | 最终候选未完成此序列 |
| (d3) ready 暂时为 0 后恢复 | INCOMPLETE | 最终候选未完成此序列 |
| 单元行复位后重开并核对已确认配方 | 3 × PASS | 0 次写入 1 |

完整拍摄序列的 INCOMPLETE 有具体边界，来自 `previous-121-r3/field` 的完整前序复放：(a) 在 ADJ 退出后完成半按前缀，全按到原生 PC `0x203CE0EC` 读取尚未建模的设备寄存器 `0xF0218814` 时停止，未执行到重开；原始 traceback 保留，按缺少设备模型记为 INCOMPLETE_DEVICE_REGISTER。(b)/(c) 已执行原始键、状态表和重新开表，半按到 state 12、全按到 state 15 的分支可以复放，但未提供单元拍摄完成消息及拍后回显链。前序已执行前缀未观察到 `n.failed=1`，不能推广成拍摄完成后也不会写。最终候选未完成这三条完整序列；设备行复位和短暂忙模型也不能冒充 RAW+JPEG 拍摄。

前序逐条序列的 12 项 epoch 见 `previous-121-r3/epoch-sequences.json`，顺序是 boot、heap、link、unit、SD、IROM、view、settings、mode、segment、power、IO。前序已执行前缀各项均为 1 → 1；不能据此编造真实拍摄会增加 settings 或 mode。引擎 `fresh()` 比较其中 boot/heap/link/unit/settings/mode 六项，view 单独用于 UI 归属；单元行变化通过实际读回检查。最终候选对应序列未完成，读数如下。

| epoch | 开表 | 半按后 | 全按前缀后 | 重开后 |
| --- | --- | --- | --- | --- |
| boot | INCOMPLETE | INCOMPLETE | INCOMPLETE | INCOMPLETE |
| heap | INCOMPLETE | INCOMPLETE | INCOMPLETE | INCOMPLETE |
| link | INCOMPLETE | INCOMPLETE | INCOMPLETE | INCOMPLETE |
| unit | INCOMPLETE | INCOMPLETE | INCOMPLETE | INCOMPLETE |
| SD | INCOMPLETE | INCOMPLETE | INCOMPLETE | INCOMPLETE |
| IROM | INCOMPLETE | INCOMPLETE | INCOMPLETE | INCOMPLETE |
| view | INCOMPLETE | INCOMPLETE | INCOMPLETE | INCOMPLETE |
| settings | INCOMPLETE | INCOMPLETE | INCOMPLETE | INCOMPLETE |
| mode | INCOMPLETE | INCOMPLETE | INCOMPLETE | INCOMPLETE |
| segment | INCOMPLETE | INCOMPLETE | INCOMPLETE | INCOMPLETE |
| power | INCOMPLETE | INCOMPLETE | INCOMPLETE | INCOMPLETE |
| IO | INCOMPLETE | INCOMPLETE | INCOMPLETE | INCOMPLETE |

最终候选未完成的格保持 INCOMPLETE；(a) 的全按后及重开值未知，(b)/(c) 的真实拍摄完成与回显之后的值也未知。固定 resident 的 epoch 写入只见初始化赋 1，本轮没有手工增加 epoch 来制造拍摄变化。

本轮沿用原生指令解释器；文件、单元通信、字形输出和必要 RTOS 服务在设备边界提供模型响应，加载后保留既有 CRC 等价计算边界。`runtime_guard.py` 检查原生 UI 写入来源，禁止主机赋值原生 UI，getter 替代已移除。当前汇总：零文件写检查 PASS，记录 346 份，UI 来源审计 73 份；详见 `zero-file-write-audit.json`。

最终重定位 DAT 的文件服务检查通过：创建、改名、删除和标记返回 -12，只读 token 写返回 -10，关闭返回 0；两次初始化能力不含文件写位。`storage-source-check.json` 证明 storage 函数与基线一致，`machine-gates.json` 保留实际 dispatcher 记录。各已完成会话的 create/write/rename/delete/write_open 计数均为 0。固定 resident 既有的 H07 同步后写入及 H01 重入审查项未在本轮消除，本轮没有把不改 resident 当作消除这些已知问题的证据。

文件服务检查单独提供了 dispatcher 要求的 inflight 条件，只验证文件 API 边界，不把它当成菜单原生序列的证据；菜单序列没有预置原生 UI 字段。

## 5. 每格操作通信次数

完整逐格数据在 `communication-steps.tsv`：每行含单元、列表/面板、参数、前后值、方向、RPC、W、写字节数和 preview 次数。只统计最终 DAT 已完成的正常操作；失败补偿另看对应序列的完整 rpc_log。

| 单元 | 操作 | 参数 | 有效格数 | 每格 RPC 范围 |
| --- | --- | --- | --- | --- |
| A12 28mm | list | all | 16 | 122–227 |
| A12 28mm | panel | Cont | 20 | 42–42 |
| A12 28mm | panel | HiLt | 20 | 42–42 |
| A12 28mm | panel | Satu | 20 | 32–82 |
| A12 28mm | panel | Shad | 20 | 42–42 |
| A12 50mm | list | all | 16 | 122–227 |
| A12 50mm | panel | Cont | 20 | 42–42 |
| A12 50mm | panel | HiLt | 20 | 42–42 |
| A12 50mm | panel | Satu | 20 | 32–82 |
| A12 50mm | panel | Shad | 20 | 42–42 |
| MOUNT A12 | list | all | 16 | 122–188 |
| MOUNT A12 | panel | Cont | 20 | 42–42 |
| MOUNT A12 | panel | HiLt | 20 | 42–42 |
| MOUNT A12 | panel | Satu | 20 | 32–82 |
| MOUNT A12 | panel | Shad | 20 | 42–42 |

| 列表行转换 | A12 50mm RPC | A12 28mm RPC | MOUNT RPC |
| --- | --- | --- | --- |
| 1 → 2 | 188 | 188 | 188 |
| 1 → 8 | 188 | 188 | 188 |
| 2 → 1 | 188 | 188 | 188 |
| 2 → 3 | 188 | 188 | 188 |
| 3 → 2 | 188 | 188 | 188 |
| 3 → 4 | 188 | 188 | 188 |
| 4 → 3 | 188 | 188 | 188 |
| 4 → 5 | 188 | 188 | 188 |
| 5 → 4 | 188 | 188 | 188 |
| 5 → 6 | 227 | 227 | 188 |
| 6 → 5 | 225 | 225 | 188 |
| 6 → 7 | 225 | 225 | 188 |
| 7 → 6 | 227 | 227 | 188 |
| 7 → 8 | 122 | 122 | 122 |
| 8 → 1 | 188 | 188 | 188 |
| 8 → 7 | 122 | 122 | 122 |


INCOMPLETE：开表计数未汇总。
RPC 计数覆盖槽 8 的 21/22/23 调用；事务开始与关闭是本地服务。原生 preview 采用设备边界模型，其内部通信未计入，因此这里不是整台相机总线活动的总数。计数不是相机毫秒数。重新开表增加完整行核对；未复位时只读，不发送 W，复位时才完整恢复。未测相机 CPU、调度、通信等待或 LCD 总时延。

## 6. 交付与完整性

`SD_ROOT` 只有 `GXRCE.DAT`。卡包没有机身或镜头固件；resident 源码、机身文件和所有旧目录保持只读。resident build ID 为 `b779cc756a740506415ca5df8eb5c8f08e1b04ea9d8c4c614f7ae971e92b94f7`，ABI 为 `d7387c3670059c325186de3af1b3d5c6`，绑定同一 v3.6 机身 SHA `50720c80696ca88f25dc25a85285acd0e0f19906e1d7da1dd404f6cc243f9008`。

引擎 51,672 B，BSS 9,880 B，DAT 余量 4,312 B，8/8/8 个配方，行池 7/20/16/15。三单元 map、16 条配方记录、参数 metadata 与 gen 120b 相同，全部有效行逐字节相同；配方记录头中的 generation 与头 CRC 随 121 更新，不作为配方颜色差异。详见 `final-data-check.json` 和构建树 `candidate/local/full-r13/manifest.json`。

官方 ZIP SHA 为 `3705984b8433c40d2ed4fd2600c11f03ed8a6de7dbe7f66efd38ee5ca15fc898`；其 `ilaunch3` 为 `da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7`。受保护输入复核 PASS，40734 个文件，变更 0 个，见 `inputs-before.json`、`protected-input-check.json`。输入路径使用十六进制保存，避免旧路径名称进入新文本。

`firmware/package_v36_g121/CARD_SHA256SUMS` 覆盖卡目录的 DAT。`research/g121_field_fix/SHA256SUMS` 覆盖本轮三个新目录的全部普通文件，按惯例不含自身；自检见 `checksum-selfcheck.json`。文本用语检查见 `language-check.json`。

时间盒：2026-10-28T00:44:36Z 至 2026-10-28T03:44:36Z；本报告快照 2026-10-28T03:43:33.627975+00:00。仅在三个获准目录写入长期文件；没有操作相机、存储卡或网络，没有子代理，也没有 sleep 轮询。原生用例是前台命令，Python 均用 `/usr/bin/python3 -I -B`。实体按钮、LCD、拍摄完成与拍后回显仍未验收。
