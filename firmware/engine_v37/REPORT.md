# engine v37 / gen 116 没有构建

resident 新 ABI 还没有链出 ELF，容器不能对着一个不存在的 build id 打包。gen 115 的 `GXRCE.DAT`（`a9743bb9…`）没有改。

黑盒和 B5 邻字节的改法还停在设计，没有写进新目录的源码：

已有 `GXRBX` 时先 `open` 已存在的 4096 字节槽，从头覆盖，再按刚写的对象读回核对。`open==-1` 不能直接 `create`，否则原生 FAT 会再分配一个同名项。每次 apply 尝试和单元装入被拒时落盘。固定记录放在现有 4096 字节日志的 `2560` 之后，并换 magic/version。

B5 邻字节不要跨 apply 缓存。每次写 B5 前重读 `map+24` 的半字，高字节必须仍等于 live 高字节。

65,536 字节上限还是够用的方向：gen 115 容器 65,252 字节，余量只有大约 284，低于 512。要保住全部功能和至少 512 字节余量，需要容器单独改用 72 KiB 上限（`73728`，文件不超过 `73216`）。这一步没有测量新代码的增量，所以没有选定。

细节在 `firmware/resident_v35/REPORT.md`。

## gen 116

`GXRCE.DAT` SHA-256 `1e033dfbcc3ca0bec0e1e5befbdb5579950e9aa8aacfbfd56f8c7342b9a97864`，66488 字节。上限用 73728，不是 65536。gen 115 已经 65252 字节，65536 下面只剩 284，守不住 512。73728 减去 66488 还剩 7240。engine 代码 56936，仍在 65536 以内。BSS 11524。file+BSS 没过 114688。三单元都是 8 行。

resident build id `9cc5359e073a3b65a223ca3af41055fd10e52b5e701db1fe08426023aea731ba`，ABI `d7387c3670059c325186de3af1b3d5c6`。body 哈希相对 gen 114 的数据区没变，resident id 和 ABI 换成了 v3.5。

黑盒 magic 改为 `GXB03501`，version 2。已有且长度正好 4096 的槽用 `rv_native_open(path, 2)` 从头覆盖；不存在才 `create`；长度不对就失败，不再 `open==-1` 就建同名项。写完用 `slot(compare=1)` 对刚写的内容核对。`flags==2` 没有置 `0x200`，按上一轮对 open 的结论这是打开已有文件并可写。这一条没有在本轮重新反汇编。

固定记录在 4096 字节日志里：2560 是 unit-load（含 `diag_early`），2688 是第一次 apply，2816 是最近一次。apply 记下 key、caller、keep、slot、T 的观测值和 W 次数。unit-load 被拒时 `safe_entry` 置上并 flush。flush 在 `RV_READY` 或本次 init 的 `RV_VALIDATED` 下允许。B5 每次要写都清掉 `neighbor_valid`，重新读 `map+24`，高字节仍要等于 live 高字节。

安装租约和 `PS_MAX_ENGINE`、文件流上限改成 73728。resident 的 `RV_MAX_FILE` 仍是 98304，`RV_MAX_CODE` 仍是 65536，机身断言没动。

宿主阶段通过：vectors、basic、first、blackbox、neighbour、t、iso、ctl、rpc-faults、conflict、accepted-f02、same-conflict、log-fault、service-quarantine、publish-failure、store-fault、daily、rejected、r33。quarantine、irom、legacy 这三组要走更老的 DAT 循环，这一轮没有再跑。

现场假设：`0x200d7fd8` 在镜头任务写它之前是 0；`open` 的 flags 不含 `0x200` 时是覆盖已有项；72 KiB 的两块安装缓冲是分配模型，不是测过的堆水位。

成片被原生 setter 盖掉时，卡 A 的 Stage2l，挂 50mm，「+ 和回放」。新机身先挂 50mm 刷。换镜头后如果卡住，挂着那个镜头再刷一次，然后回到 50mm 再查。
