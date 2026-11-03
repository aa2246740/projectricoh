可以刷机

仅放行下面的分阶段试刷。本轮没有发现新增 P0/P1 或阻断性 P2，R33-01 已关闭；不代表相机验收通过，也不代表已修复今天的 50mm 启动故障。现场事实按题设采信，根因仍未知，今日恢复同时更换机身代码并刷新单元，不能拆开归因。

结论只绑定 `firmware/image_v34c/local/package/SD_ROOT` 的实际字节：

```text
ilaunch3   24b1de0e46ea00adeacd224da28770e185b05a08686c40c647032c533c021f72
GXRCE.DAT  6cb63aa47c18086f5ade681ffe4dc97378394ff7a65c0688d19b3880d804c707
full-r11   generation 113；64,816 B
```

P2 · F02，继承且已接受：较高代 IROM 连续三次只读 open=-1 时，安装仍能覆盖它。当前 C 用有效的合成 114 再现了被 113 替换；不是本轮新修复。依据：`acceptance/containers/product/src/firmware/engine/panel/panel_store.c:71` 的重试和 `:175` 的扫描跳过；[50mm 原始结果](local/logs/candidate-accepted-f02-0-0.stdout)。持续不可读的 GXTS 也不能与不存在区分。

P2 · CTL 的已约定边界：有效 OFF 文件若 open/read=-1，本次仍启用；OFF 不能阻止加载它之前的 loader/分配，也不是硬启动保险。依据：`acceptance/containers/product/blackbox.c:10`、`adapter.c:544`。228 类解析检查×三单元覆盖长度、每位破坏、短读、换卡及 open/read/close 错误；[原始结果](local/logs/attacks-ctl-fuzz-0-0.stdout)。无需改动本轮约定，但不能把放入 OFF 当作已经停用的证据。

源码路径以 `firmware/resident_v34c/` 为根。下文 adapter.c、blackbox.c 指 `acceptance/containers/product/` 下的文件，services.c 指 `acceptance/engine_services/services.c`。下面是已核实的主要结果。

- 启动：模式初始化 `202E3ADC → 202D6AE4/6BF0 → 2017098C` 确实到 H09；H05 是共享 renderer，应按启动可达处理。H01/H02 来自状态 56、项 8 的构造器；H06 是 Fn2，H07 是关闭，H08 是行回调。冷 FF 根下，H02、H05–H09 的完整桩及实际 observer 在 v3.2/v3.3/v3.4c 共 1,152 组中，与官方被替换指令的全部寄存器、PSW、SP 和有效栈存储相等，零文件、分配、RPC 或单元访问。H01 仍会加载，不能给它同一保证；20,480 组初始状态选择未到 56，但不是完整启动证明。未发现新 jlaunch 专用启动分支。[冷根机器码](local/cold-machine.json)、[原生启动复放](local/boot/boot-machine.json)；`resident/hooks.c:33`。
- 启动字节不是“没变”：相对 v3.2 共变 7,118 B，七个外部 BRA 各变一字节，包含 H05/H09；上述冷根路径的行为保持等价。相对 v3.3 共变 4,588 B，实际只有 resident 窗口 4,585 B 和 checksum 3 B，七个外部 BRA 全等。H03/H04、H10–H37、30 个更新窗口和额外确认/执行区均为官方字节；28 个兄弟文件逐字节等于官方。manifest 全部条目匹配，CTL 在 SD_ROOT 外。[映像证据](local/artifacts.json)、[恢复证据](local/recovery.json)。
- 隔离：`resident/loader.c:84,101` 锁存正面拒绝，`adapter.c:291,443` 保持锁存；服务 `services.c:78,100` 另挡 GXTS/GXLS 写操作。原 R33-01、拒绝后的瞬时/持续 -1、移除 DAT、重开和冲突均零内部保存。仅 OK、无 DAT、无卡、SD 身份不可读时，保存和冷恢复正常。开菜单后才放入旧 DAT 不会重扫；它未被读取或拒绝，符合本轮“正证据才锁存”的边界，换卡应关机。[结果](local/host-suite.json)、[迟放旧 DAT](local/logs/attacks-late-card-0-0.stdout)。
- 初始化与应用：CTL 前只有加载框架、私有 context/请求初始化及缓存身份/ready 读取；官方 `2009359C` 只是读 `200D7FD8`，不发送 RPC。CTL 通过启用分支后才初始化日志及引擎；init 无 RPC、文件写、settings、preview 或 UI 发布。恢复 GXLS 和滚动只改光标；OK/Fn2 才应用，Fn2 参数移动只改草稿，MENU 保留已提交外观。首次 T≠2 或读失败不修复、不重试；624 个新增行 RPC 故障检查未见故障后的继续 W。保存失败、后续操作、旧绑定、双残缺安装、R6/R7 历史投影通过。依据：`eng_core.c:110,164,224,306,374`、`adapter.c:338,401,466,489`；[160 次产品程序运行](local/host-suite.json)、[补充运行](local/additional-flows.json)。这里的 eng_core.c 位于 `acceptance/containers/product/src/firmware/engine/core/`。
- ISO100：独立 Python 和完整 C 对 full-r10/r11 共 96 槽展开一致；新 48 槽 entry552/record64 与 full-r10 全等，旧 448 B 前缀及记录与 full-r9 全等。A14/B14 为 50mm `2012F732/20130125`、28mm `201329C6/201333B9`、Mount `2013A3A6/2013AD99`；配方复制 A5/B5，04 九行均等于各单元官方行。B14 前后邻字节保留，旧七行和非 ISO100 选表未改；06 C/D 保留，50mm control=0、Mount control=2。先 control=2，再改行，按需 control=0，最后 settings/preview。三枚 map152||stock505 pin 复算为 `f09fe7b4/fb3fbcb2/95f3dca9`。[数据与地址](local/data.json)。
- 编译与资源：链接源码摘要与停止轮一致；engine 56,140→55,404 B，省 736 B，容器余 720 B。最终 ELF 与 DAT 引擎段全等，唯一运行期重定位及平移后的全部指令/数据匹配，无未解析符号。resident payload 7,868 B，实余 216 B，高于 200 B assertion，未增 hook。最终 IRQ save/restore 196,608 组通过，七桩重放 896 组、构造器 2,048 组通过。目标 sizeof 得主块 83,840 B，首装含头 215,568 B；已有 UI 时 217,548 B。相比批准的初版 v3.2 full 模型少 5,400 B，但比 full-r3 多 5,460 B、full-r9 多 2,348 B。H01/H07 栈模型 804/1,096 B，H05/H09 为 104 B。[源码比较](local/source-differences.json)、[目标尺寸](local/data.json)、[机器码检查](local/machine-reuse.json)。
- 黑盒：使用原有 6 KiB state 的最后 4 KiB；只写两个 ATA1 日志，不写 IROM。flush 要求 READY、前台 context、非 owner 且 RPC token=0，只在菜单关闭、明确应用后或受控失败出口调用；H05/H09/IRQ 无 flush。两镜头实际产生的主机日志均已解码，安装和发布是两个回执。依据：`blackbox.c:26,93`、`adapter.c:72,144`；[补充运行](local/additional-flows.json)。它记录不到引擎加载前的失败。

我认可的首刷与验证顺序：

1. 保留今日成功恢复的卡 A，准备满电。核对上面两个完整 SHA；首次试刷用另一张卡，只放 SD_ROOT 内 29 个固件文件，暂不放 DAT/OK/CTL。候选新 trust 会拒绝旧 IROM 引擎，不要通过 USB 尝试写只读内部存储。
2. 挂 28mm，用“+ & 回放键”进入原生更新，确认文件后更新，过程中不拔电或卡。完成后先关机，再用 28mm 冷启动，确认原厂菜单、拍照和更新入口可取消。
3. 关机换 50mm，仍不放 DAT，先验证正常冷启动和原厂拍照，暂不进 Image Settings。若普通启动再次绿灯闪/黑屏，停止扩展试验，用卡 A、“+ & 回放键”并挂着 50mm 恢复；不要只在 28mm 上回刷后就假定 50mm 已刷新。
4. 关机加入本次 DAT 和 controls/OFF/GXRCE.CTL，冷启后进 Image Settings，应保留原厂七项，DAT 不应变 OK。再关机撤掉 CTL/旧 OK，冷启后主动进入，确认八项及 DAT→OK；若只有七项，先收日志定位发布失败，不能把 OK 当作菜单成功。
5. 50mm 先测进入/移动/MENU 不改外观，再测 OK 应用、Fn2 草稿取消及 OK 保存；冷启应只恢复光标，重新按 OK/Fn2 后才恢复外观。确认 04 能还原，再拍 03/06 的 ISO100 与 ISO200 对照，检查邻行切换和正常快门。
6. 前面通过后，关机换 Mount 重复原厂启动、菜单与应用检查；28mm 应始终保留原厂七项。复制 SD 上 GXRBX0/1.BIN 到主机解码，分别核对安装/发布回执；保存已测照片与日志。

未知：完整复位/RTOS/异步启动链、真实 M32R 执行、native RPC 等待时长、完整 native/IRQ 栈和堆碎片、物理掉电/rename、快门与九行写入并发、实际照片。主机故障注入不证明 ISP 切换原子，也不保证中断刷写或坏 RAM 后仍能恢复。Mount 原有非零 WB 微调 binding 限制仍保留。

本轮只写本目录；259,944 个冻结输入复核未变，decisions.tsv 排除。未改 builder、重建或重封装候选，未访问相机/卡/USB 卷，未刷机、安装依赖、启动子代理、sleep/轮询或 commit/push。包内 `independent_review=PENDING` 未改写，以本报告记录审查结论。脚本、派生字节和日志见本目录及忽略的 `/local/`；SHA256SUMS 覆盖交付物。

```sh
/usr/bin/python3 -I -B research/review_flash_v34c/finalize.py verify
```
