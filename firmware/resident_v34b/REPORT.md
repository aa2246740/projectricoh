v3.4b / full-r10 主机验收通过，包已标为 STAGED_HOST_ONLY，等待独立审查。本轮未访问相机或任何卡，未刷写。

已核实：resident payload 7832 B，root 256 B，实余 252 B。相对 v3.3 增 32 B，只增加隔离锁存。链接预留从 280 降为 200 B，以容纳这 32 B；没有新增 hook，也没有 H40。

```text
resident ELF  fcee63608ee0cafe5b86f27d1e69b7b88caa242bae9f8e8329c91cb4cb9b355d
build ID      0f03d6733e30f00e525ce99dd067e7bf4a88f512b54b31a7ece8235f45ebc2bb
ABI ID        b6353e4de1c89bd37c08ba6734efc8e0
ilaunch3      abd500a52931a8bbd13e7b4d3242664e15c53e19882a7ce5ddb4206ccdbac34d
full-r10/112  18424a588fbbb80cf554b0c5a821d605fbac6326cc4a9111aad4eeb46e8cbf29
pins          f09fe7b4 / fb3fbcb2 / 95f3dca9
```

full-r9 → full-r10：文件 62700 → 65500 B；engine 53524 → 56088 B；BSS 11288 → 11520 B；主块申请 81492 → 84524 B。首装含原生头的模型峰值 213220 → 216252 B；已有 snapshot 再加 1980 B。会话 state 仍为 6144 B。容器仅余 36 B。这些是申请量模型，不是相机堆水位。

改动位置：

- [resident/build.py:67](resident/build.py#L67)：新 build/ABI 与三枚 ISO100 pin，旧容器拒绝。

- [resident/loader.c:84](resident/loader.c#L84)：拒绝或未知卡源锁存至冷启动。

- [acceptance/engine_services/services.c:77](acceptance/engine_services/services.c#L77)：服务独立拒绝 GXLS/GXTS 的 create/write/rename/delete。

- [acceptance/containers/product/adapter.c:548](acceptance/containers/product/adapter.c#L548)：第一步读 CTL；有效 OFF 走现有停用路径。

- [acceptance/containers/product/src/firmware/engine/core/eng_core.c:110](acceptance/containers/product/src/firmware/engine/core/eng_core.c#L110)：纯初始化；开列表和 GXLS 不应用；第一次明确应用查 T，不修复、不重试。

- [acceptance/containers/product/adapter.c:460](acceptance/containers/product/adapter.c#L460)：移动光标只选中；OK/Fn2 才应用，面板草稿也由 OK 应用。

- [acceptance/containers/product/blackbox.c:26](acceptance/containers/product/blackbox.c#L26)：现有 6144 B state 中取末尾 4096 B，双回执与 64×32 B ring。

- [acceptance/containers/product/blackbox.c:93](acceptance/containers/product/blackbox.c#L93)：仅菜单关闭、明确应用结束、干净失败出口刷 SD，close 后完整读回。

- [acceptance/containers/product/src/firmware/card_container_v2/semantic.c:3](acceptance/containers/product/src/firmware/card_container_v2/semantic.c#L3)：GXMP v2/152、GXDT v6/20、DEEPTBL v4/552 与九行验证。

- [acceptance/build_r10.py:13](acceptance/build_r10.py#L13)：full-r9 的 48 槽旧行和记录不变，A14/B14 按各自 A5/B5 扩展，04 为真正 stock14。

正常开机保持原厂入口。50mm/Mount 进入 Image Settings 后显示八行，首帧定位 live 配方或 GXLS 记住的光标；无记忆定位 01。进入、重绘、上下移动和恢复光标均不发 RPC8、不写模块。OK 应用当前行；Fn2 先明确应用当前行再开微调面板，移动参数只改草稿，OK 应用并保存，MENU 丢弃草稿。首次明确应用的 T 不是 2 或读取失败，就退出且本次开机不再重试。28mm 保持原生七项。

默认启用，卡上无需 CTL。将 [ON](../image_v34b/local/package/controls/ON/GXRCE.CTL) 或 [OFF](../image_v34b/local/package/controls/OFF/GXRCE.CTL) 以 GXRCE.CTL 放在卡根。只有 CRC、完整长度/EOF、close 和 SD 身份都通过的 OFF 才停用至冷启动。OFF 若 open/read=-1 不会被识别；退路是不进入 Image Settings，或另行授权后刷回 Stage2l。

拒绝、未知或冲突卡源的隔离在同次开机保持，移除 DAT、恢复读取或重开菜单都不清除。原生 -1 无法区别无文件和不可读，所以无 DAT 的 IROM 回退也会禁止 GXLS/GXTS 保存；既存配方和微调仍可读，GXLS 只定位光标。物理无卡、SD 身份读失败时跳过 GXLS/GXTS，以配方默认微调运行。要重新允许保存，冷启动时需有可读的当前 DAT。隔离不禁止 SD 黑盒日志。

日志在卡根 GXRBX0.BIN/GXRBX1.BIN，各 4096 B。只在菜单关闭、明确应用结束或干净失败出口覆盖较旧完整槽；写后 close，再读至 EOF 并 close 验证。启动、H05、H09、IRQ、RPC 事务内均不刷盘，日志不写内存盘。解码：

```sh
/usr/bin/python3 -I -B firmware/resident_v34b/decode_blackbox.py <主机上的日志副本>
```

已核实的检查：[最终清单](local/final-tests.json) 共 204 个产品主机程序运行。resident 44 例/127607 断言；IRQ 196608、七 hook replay 896、H07 桩 256、H01/H02/H05 147、改动 loader 指令 3584；实际映像 constructor 2048；首帧 6912 输入与 1530 次未应用重开；新增 52 个 X/V/W × 六种故障 × 两单元，共 624 例；旧绑定 3584 次显式保存；三单元与 105–111 的 IROM 状态 189 组。另覆盖 CTL 30 组、B14 前后邻字节各 256 值、所有八槽互切、04 恢复、06 C/D、GXLS/GXTS 失败后继续操作和黑盒 I/O 失败。48 个新 entry 与 full-r9 的旧 448 B、record64 全等；全部新 binding 改变。历史容器由冻结旧 C 展开 336 槽；不冒充旧 M32R 引擎执行。

推断：最小 resident 改动保留 v3.3 首帧行为，隔离锁存关闭 R33-01 的瞬时 -1 放行路径。未知：真实 M32R/原生文件系统、掉电、堆碎片、LCD、快门并发与照片。九行顺序不等于 ISP 原子性，尚无切换中途拍摄的设备证明。Mount 06 按 full-r9 保持 control=2，50mm 06 保持 C/D control=0。Mount 原有 WB 非零微调缺少有效 lane/sign binding，仍拒绝应用。黑盒无法记录引擎尚未加载成功前的失败。既有 F02 仍在：IROM 副本持续 open=-1 隐藏更高代时，安装无法证明它不存在；同 trust 的 113 合成夹具仍可被 112 替换。这是既有接受限制，未把它写成已修复。栈模型 H01/H02/H05/H06/H07/H08/H09 为 860/180/104/872/1232/560/104 B，不含完整 native、IRQ 和任务已有帧，不能称全局栈安全。

独立审查通过且另行获批后，首刷挂 28mm 或 Mount；更新结束关机，再挂 50mm 冷启动确认能正常启动，先不进 Image Settings，再逐项测进入/移动/OK/Fn2/04/06/ISO100 和日志。恢复用卡 A 加“+ & 回放键”，必要时挂 50mm 重刷 Stage2l 与官方单元。用户今日已现场验证这条恢复；本轮未执行，不把它扩大为坏 RAM 或中断升级也能救援的保证。

复跑入口为 resident/build.py、resident/verify.py、machine_checks.py、entry_machine.py、acceptance/build_r10.py、acceptance/verify_v34b.py 和 evidence_v34b.py。Python 均用 /usr/bin/python3 -I -B，沿用指定 M32R GCC/ld/objdump，无安装。阶段记录见 [PROGRESS](PROGRESS.md)。保护输入 38988 项未变，decisions.tsv 排除。写入仅限两个 v34b 目录；无子代理、sleep、轮询、commit 或 push。
